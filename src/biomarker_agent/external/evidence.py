from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from biomarker_agent.evidence import build_external_framework
from biomarker_agent.external.http import ExternalSourceError
from biomarker_agent.external.mygene import query_mygene
from biomarker_agent.external.pubmed import AMBIGUOUS_DISEASE_LABELS, search_pubmed
from biomarker_agent.resolver import AmbiguousIdentifierError, OfflineResolver, UnresolvedIdentifierError
from biomarker_agent.schemas import (
    BiomarkerEntity,
    ContextOfUse,
    EvidenceScore,
    ExternalEvidenceResult,
    LiteratureRecord,
)
from biomarker_agent.version import __version__, runtime_versions


def _resolve_entity(query: str) -> tuple[BiomarkerEntity, list[dict[str, Any]], list[str]]:
    limitations: list[str] = []
    offline_entity: BiomarkerEntity | None = None
    try:
        offline_entity = OfflineResolver().resolve(query)
    except (AmbiguousIdentifierError, UnresolvedIdentifierError) as exc:
        limitations.append(
            f"Offline resolver returned {exc.entity.resolution_confidence}; attempted MyGene.info lookup."
        )
    try:
        mygene_entity, database_records = query_mygene(query)
        if offline_entity is not None and offline_entity.resolution_confidence == "unique":
            return offline_entity, database_records, limitations
        return mygene_entity, database_records, limitations
    except ExternalSourceError as exc:
        limitations.append(str(exc))
        if offline_entity is not None:
            return offline_entity, [], limitations
        return (
            BiomarkerEntity(
                query=query,
                id_type="external_query",
                resolution_confidence="unresolved",
                mapping_source="offline_and_mygene_failed",
            ),
            [],
            limitations,
        )


def assess_external_evidence(
    biomarker_id: str,
    disease: str,
    retmax: int = 10,
    email: str | None = None,
    context_of_use: ContextOfUse | None = None,
) -> ExternalEvidenceResult:
    entity, database_records, limitations = _resolve_entity(biomarker_id)
    context = context_of_use or ContextOfUse(category="unspecified", disease=disease)
    if warning := AMBIGUOUS_DISEASE_LABELS.get(disease.strip().upper()):
        limitations.append(warning)
    symbol = entity.hgnc_symbol or biomarker_id
    literature_query = ""
    literature_records: list[LiteratureRecord] = []
    try:
        literature_query, literature_records, _ = search_pubmed(symbol, disease, retmax=retmax, email=email)
    except ExternalSourceError as exc:
        limitations.append(str(exc))

    scores = _score_external(entity, database_records, literature_records)
    overall = _overall_confidence(scores)
    evidence_domains, evidence_conclusion = build_external_framework(entity, context, literature_records)
    if not literature_records:
        limitations.append("No PubMed literature records were retrieved for the disease-specific query.")
    limitations.append(
        "External literature evidence is metadata-level only; no full-text extraction or effect-size verification is performed."
    )
    limitations.append("Publication count and retrieval limit do not increase the supported evidence stage.")
    limitations.append(
        "Public database lookup currently uses MyGene.info identity metadata, not TCGA/CPTAC expression reanalysis."
    )
    return ExternalEvidenceResult(
        entity=entity,
        disease=disease,
        literature_query=literature_query,
        literature_records=literature_records,
        database_records=database_records,
        context_of_use=context,
        evidence_domains=evidence_domains,
        evidence_conclusion=evidence_conclusion,
        evidence_scores=scores,
        overall_confidence=overall,
        limitations=limitations,
        provenance={
            "generated_at": datetime.now(UTC).isoformat(),
            "software": "biomarker-evidence-assessment",
            "software_version": __version__,
            "phase": "phase_2_claim_bounded_assessment",
            "runtime_versions": runtime_versions(),
            "sources": ["MyGene.info v3 query API", "NCBI E-utilities PubMed ESearch/ESummary"],
            "retrieval_limit": retmax,
            "scoring": "metadata_retrieval_signal_only",
        },
    )


def _score_external(
    entity: BiomarkerEntity,
    database_records: list[dict[str, Any]],
    literature_records: list[LiteratureRecord],
) -> dict[str, EvidenceScore]:
    direct_count = sum(record.evidence_class == "direct" for record in literature_records)
    indirect_count = sum(record.evidence_class == "indirect" for record in literature_records)
    resolved_symbol = (entity.hgnc_symbol or "").upper()
    exact_database_records = [
        record for record in database_records if str(record.get("symbol", "")).upper() == resolved_symbol
    ]
    return {
        "id_certainty": EvidenceScore(
            dimension="id_certainty",
            score=5
            if entity.resolution_confidence == "unique"
            else 2
            if entity.resolution_confidence == "ambiguous"
            else 0,
            justification=f"Entity resolution confidence is {entity.resolution_confidence} via {entity.mapping_source}.",
        ),
        "database_identity_support": EvidenceScore(
            dimension="database_identity_support",
            score=5
            if exact_database_records and entity.resolution_confidence == "unique"
            else 1
            if database_records
            else 0,
            justification=(
                f"{len(exact_database_records)} exact symbol record(s) and {len(database_records)} total candidate record(s) were retrieved; this supports identity only."
            ),
        ),
        "direct_literature_support": EvidenceScore(
            dimension="direct_literature_support",
            score=1 if direct_count else 0,
            justification=(
                f"{direct_count} PubMed record(s) matched title-level disease terms. Metadata retrieval is a signal, not study-level evidence."
            ),
        ),
        "indirect_literature_support": EvidenceScore(
            dimension="indirect_literature_support",
            score=1 if indirect_count else 0,
            justification=(
                f"{indirect_count} PubMed record(s) lacked title-level disease matching. Study relevance was not appraised."
            ),
        ),
        "statistical_validation": EvidenceScore(
            dimension="statistical_validation",
            score=0,
            justification="No external expression matrix was downloaded or statistically reanalysed in this external metadata mode.",
        ),
        "clinical_utility": EvidenceScore(
            dimension="clinical_utility",
            score=0,
            justification="No baseline-vs-biomarker clinical model comparison was performed from external sources.",
        ),
    }


def _overall_confidence(scores: dict[str, EvidenceScore]) -> Literal["high", "moderate", "low", "insufficient"]:
    if scores["id_certainty"].score == 0:
        return "insufficient"
    if scores["direct_literature_support"].score or scores["indirect_literature_support"].score:
        return "low"
    return "insufficient"
