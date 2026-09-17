from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from biomarker_agent.external.http import ExternalSourceError
from biomarker_agent.external.mygene import query_mygene
from biomarker_agent.external.pubmed import search_pubmed
from biomarker_agent.resolver import AmbiguousIdentifierError, OfflineResolver, UnresolvedIdentifierError
from biomarker_agent.schemas import BiomarkerEntity, EvidenceScore, ExternalEvidenceResult, LiteratureRecord


def _resolve_entity(query: str) -> tuple[BiomarkerEntity, list[dict[str, Any]], list[str]]:
    limitations: list[str] = []
    offline_entity: BiomarkerEntity | None = None
    try:
        offline_entity = OfflineResolver().resolve(query)
    except (AmbiguousIdentifierError, UnresolvedIdentifierError) as exc:
        limitations.append(f"Offline resolver returned {exc.entity.resolution_confidence}; attempted MyGene.info lookup.")
    try:
        mygene_entity, database_records = query_mygene(query)
        if offline_entity is not None and offline_entity.resolution_confidence == "unique":
            return offline_entity, database_records, limitations
        return mygene_entity, database_records, limitations
    except ExternalSourceError as exc:
        limitations.append(str(exc))
        if offline_entity is not None:
            return offline_entity, [], limitations
        return BiomarkerEntity(query=query, id_type="external_query", resolution_confidence="unresolved", mapping_source="offline_and_mygene_failed"), [], limitations


def assess_external_evidence(biomarker_id: str, disease: str, retmax: int = 10, email: str | None = None) -> ExternalEvidenceResult:
    entity, database_records, limitations = _resolve_entity(biomarker_id)
    symbol = entity.hgnc_symbol or biomarker_id
    literature_query = ""
    literature_records: list[LiteratureRecord] = []
    try:
        literature_query, literature_records, _ = search_pubmed(symbol, disease, retmax=retmax, email=email)
    except ExternalSourceError as exc:
        limitations.append(str(exc))

    scores = _score_external(entity, database_records, literature_records, limitations)
    overall = _overall_confidence(scores)
    if not literature_records:
        limitations.append("No PubMed literature records were retrieved for the disease-specific query.")
    limitations.append("External literature evidence is metadata-level only; no full-text extraction or effect-size verification is performed.")
    limitations.append("Public database lookup currently uses MyGene.info identity metadata, not TCGA/CPTAC expression reanalysis.")
    return ExternalEvidenceResult(
        entity=entity,
        disease=disease,
        literature_query=literature_query,
        literature_records=literature_records,
        database_records=database_records,
        evidence_scores=scores,
        overall_confidence=overall,
        limitations=limitations,
        provenance={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": ["MyGene.info v3 query API", "NCBI E-utilities PubMed ESearch/ESummary"],
            "scoring": "rule_based_metadata_level",
        },
    )


def _score_external(entity: BiomarkerEntity, database_records: list[dict[str, Any]], literature_records: list[LiteratureRecord], limitations: list[str]) -> dict[str, EvidenceScore]:
    direct_count = sum(record.evidence_class == "direct" for record in literature_records)
    indirect_count = sum(record.evidence_class == "indirect" for record in literature_records)
    return {
        "id_certainty": EvidenceScore(
            dimension="id_certainty",
            score=5 if entity.resolution_confidence == "unique" else 2 if entity.resolution_confidence == "ambiguous" else 0,
            justification=f"Entity resolution confidence is {entity.resolution_confidence} via {entity.mapping_source}.",
        ),
        "database_identity_support": EvidenceScore(
            dimension="database_identity_support",
            score=5 if database_records else 2 if entity.mapping_source.startswith("offline") and entity.resolution_confidence == "unique" else 0,
            justification=f"{len(database_records)} external database candidate record(s) retrieved.",
        ),
        "direct_literature_support": EvidenceScore(
            dimension="direct_literature_support",
            score=5 if direct_count >= 5 else 3 if direct_count >= 2 else 1 if direct_count == 1 else 0,
            justification=f"{direct_count} PubMed record(s) matched the biomarker and disease terms in title metadata.",
        ),
        "indirect_literature_support": EvidenceScore(
            dimension="indirect_literature_support",
            score=3 if indirect_count >= 3 else 1 if indirect_count else 0,
            justification=f"{indirect_count} PubMed record(s) mention biomarker evidence without direct disease-title matching.",
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


def _overall_confidence(scores: dict[str, EvidenceScore]) -> str:
    if scores["id_certainty"].score == 0:
        return "insufficient"
    if scores["direct_literature_support"].score >= 5 and scores["statistical_validation"].score >= 3:
        return "high"
    if scores["direct_literature_support"].score >= 3:
        return "moderate"
    if scores["direct_literature_support"].score or scores["indirect_literature_support"].score:
        return "low"
    return "insufficient"
