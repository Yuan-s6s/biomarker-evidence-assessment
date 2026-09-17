from __future__ import annotations

from typing import Any

from biomarker_agent.external.http import get_json
from biomarker_agent.schemas import LiteratureRecord


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


DISEASE_SYNONYMS = {
    "LSCC": ["LSCC", "lung squamous cell carcinoma", "laryngeal squamous cell carcinoma"],
    "HNSCC": ["HNSCC", "head and neck squamous cell carcinoma"],
}


def disease_terms(disease: str) -> list[str]:
    return DISEASE_SYNONYMS.get(disease.upper(), [disease])


def build_pubmed_query(symbol: str, disease: str) -> str:
    terms = disease_terms(disease)
    disease_clause = " OR ".join(f'"{term}"' for term in terms)
    return f'({symbol}[Title/Abstract]) AND ({disease_clause}) AND (biomarker OR expression OR prognostic OR diagnostic OR survival)'


def search_pubmed(symbol: str, disease: str, retmax: int = 10, email: str | None = None) -> tuple[str, list[LiteratureRecord], dict[str, Any]]:
    query = build_pubmed_query(symbol, disease)
    params: dict[str, Any] = {"db": "pubmed", "term": query, "retmode": "json", "retmax": retmax, "sort": "relevance", "tool": "biomarker_validation_agent"}
    if email:
        params["email"] = email
    search_payload = get_json(f"{EUTILS_BASE}/esearch.fcgi", params)
    ids = search_payload.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return query, [], {"search": search_payload, "summary": None}

    summary_params: dict[str, Any] = {"db": "pubmed", "id": ",".join(ids), "retmode": "json", "tool": "biomarker_validation_agent"}
    if email:
        summary_params["email"] = email
    summary_payload = get_json(f"{EUTILS_BASE}/esummary.fcgi", summary_params)
    result = summary_payload.get("result", {})
    records = []
    for pmid in ids:
        item = result.get(pmid, {})
        title = item.get("title", "")
        record_terms = _matched_terms(title, disease)
        records.append(
            LiteratureRecord(
                pmid=pmid,
                title=title,
                journal=item.get("fulljournalname") or item.get("source"),
                publication_date=item.get("pubdate"),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                evidence_class="direct" if record_terms else "indirect",
                matched_terms=record_terms,
            )
        )
    return query, records, {"search": search_payload, "summary": summary_payload}


def _matched_terms(text: str, disease: str) -> list[str]:
    lowered = text.lower()
    return [term for term in disease_terms(disease) if term.lower() in lowered]
