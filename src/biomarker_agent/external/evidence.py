from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from biomarker_agent.evidence import build_external_framework
from biomarker_agent.external.http import ExternalSourceError
from biomarker_agent.external.mygene import query_mygene
from biomarker_agent.external.pubmed import (
    AMBIGUOUS_DISEASE_LABELS,
    DEFAULT_MAX_RECORDS,
    DEFAULT_PAGE_SIZE,
    search_pubmed,
)
from biomarker_agent.resolver import AmbiguousIdentifierError, OfflineResolver, UnresolvedIdentifierError
from biomarker_agent.schemas import (
    BiomarkerEntity,
    ContextOfUse,
    EvidenceScore,
    ExternalEvidenceResult,
    LiteratureRecord,
    LiteratureSearchSummary,
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
    retmax: int = DEFAULT_MAX_RECORDS,
    email: str | None = None,
    context_of_use: ContextOfUse | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    api_key: str | None = None,
) -> ExternalEvidenceResult:
    entity, database_records, limitations = _resolve_entity(biomarker_id)
    context = context_of_use or ContextOfUse(category="unspecified", disease=disease)
    if warning := AMBIGUOUS_DISEASE_LABELS.get(disease.strip().upper()):
        limitations.append(warning)
    symbol = entity.hgnc_symbol or biomarker_id
    literature_query = ""
    literature_records: list[LiteratureRecord] = []
    literature_summary = LiteratureSearchSummary(
        retrieval_cap=None if retmax == 0 else retmax,
        page_size=page_size,
    )
    literature_search_failed = False
    try:
        literature_search = search_pubmed(
            symbol,
            disease,
            retmax=retmax,
            email=email,
            page_size=page_size,
            api_key=api_key,
        )
        literature_query = literature_search.query
        literature_records = literature_search.records
        literature_summary = literature_search.summary
    except ExternalSourceError as exc:
        literature_search_failed = True
        literature_summary.retrieval_warnings.append(str(exc))

    scores = _score_external(entity, database_records, literature_records)
    overall = _overall_confidence(scores)
    evidence_domains, evidence_conclusion = build_external_framework(
        entity,
        context,
        literature_records,
        literature_summary,
    )
    if literature_summary.total_hits == 0 and not literature_search_failed:
        limitations.append("No PubMed records matched the disease-specific query.")
    elif not literature_records:
        limitations.append("PubMed reported matching records, but no records were successfully retrieved.")
    elif literature_summary.records_included == 0:
        limitations.append("No retrieved record passed the automated title/abstract candidate-screening rules.")
    if literature_summary.truncated:
        limitations.append(
            f"Retrieval was truncated: {literature_summary.records_retrieved} of "
            f"{literature_summary.total_hits} PubMed hits were processed."
        )
    limitations.extend(f"PubMed retrieval warning: {warning}" for warning in literature_summary.retrieval_warnings)
    limitations.append(
        "Title/abstract screening is automated and is not a full-text eligibility assessment or systematic review."
    )
    limitations.append(
        "Abstract effect estimates are unverified same-sentence biomarker candidates; they are not used to raise the evidence stage or score."
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
        literature_summary=literature_summary,
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
            "sources": ["MyGene.info v3 query API", "NCBI E-utilities PubMed ESearch/EFetch"],
            "literature_retrieval": literature_summary.model_dump(mode="json"),
            "scoring": "title_abstract_retrieval_signal_only",
            "ncbi_notice": "NCBI data use policies and disclaimers apply; abstract text is processed transiently and is not reproduced in reports.",
        },
    )


def _score_external(
    entity: BiomarkerEntity,
    database_records: list[dict[str, Any]],
    literature_records: list[LiteratureRecord],
) -> dict[str, EvidenceScore]:
    screened_candidates = [record for record in literature_records if record.screening_decision == "include_candidate"]
    direct_count = sum(record.evidence_class == "direct" for record in screened_candidates)
    indirect_count = sum(record.evidence_class == "indirect" for record in screened_candidates)
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
                f"{direct_count} PubMed record(s) matched the biomarker and disease in the title. Retrieval is a signal, not study-level evidence."
            ),
        ),
        "indirect_literature_support": EvidenceScore(
            dimension="indirect_literature_support",
            score=1 if indirect_count else 0,
            justification=(
                f"{indirect_count} PubMed record(s) matched through title/abstract content but not both terms in the title. Full-text relevance was not appraised."
            ),
        ),
        "statistical_validation": EvidenceScore(
            dimension="statistical_validation",
            score=0,
            justification="No external expression matrix was downloaded or statistically reanalysed in this title/abstract workflow.",
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
