from __future__ import annotations

import re
from time import monotonic, sleep
from typing import Any, Literal
from xml.etree import ElementTree

from biomarker_agent.external.http import ExternalSourceError, get_json, get_text
from biomarker_agent.schemas import (
    EffectEstimateCandidate,
    EffectMeasure,
    LiteratureRecord,
    LiteratureScreeningDecision,
    LiteratureSearchSummary,
    PubMedSearchResult,
)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_NAME = "biomarker_evidence_assessment"
DEFAULT_MAX_RECORDS = 500
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 200
PUBMED_ESEARCH_MAX = 10_000

DISEASE_SYNONYMS = {
    "LUNG SQUAMOUS CELL CARCINOMA": ["lung squamous cell carcinoma", "LUSC"],
    "LARYNGEAL SQUAMOUS CELL CARCINOMA": ["laryngeal squamous cell carcinoma", "laryngeal SCC"],
    "HNSCC": ["HNSCC", "head and neck squamous cell carcinoma"],
}

AMBIGUOUS_DISEASE_LABELS = {
    "LSCC": "LSCC can refer to lung or laryngeal squamous cell carcinoma; use the full disease name.",
}

RELEVANCE_TERMS = (
    "biomarker",
    "expression",
    "prognostic",
    "prognosis",
    "diagnostic",
    "diagnosis",
    "survival",
    "outcome",
    "predictive",
    "prediction",
)
NUMBER_PATTERN = r"(?:\d+(?:\.\d+)?|\.\d+)"
INTERVAL_SEPARATOR = r"(?:-|–|—|−|to|,)"
RATIO_PATTERN = re.compile(
    rf"\b(?P<label>hazard\s+ratio|odds\s+ratio|risk\s+ratio|relative\s+risk|HR|OR|RR)\b"
    rf"(?:\s*(?:\((?:HR|OR|RR)\)|\[(?:HR|OR|RR)\]))?"
    rf"\s*(?:was|of|=|:|,)?\s*(?P<estimate>{NUMBER_PATTERN})"
    rf"\s*[,;)]*\s*\(?(?:95\s*%\s*)?(?:CI|confidence\s+interval)\s*[:=,]?\s*"
    rf"[\[(]?\s*(?P<lower>{NUMBER_PATTERN})\s*{INTERVAL_SEPARATOR}\s*(?P<upper>{NUMBER_PATTERN})",
    flags=re.IGNORECASE,
)
DISCRIMINATION_PATTERN = re.compile(
    rf"\b(?P<label>AUC|area\s+under\s+(?:the\s+)?(?:receiver\s+operating\s+characteristic\s+|ROC\s+)?curve|"
    rf"C[- ]?index|concordance\s+index)\b"
    rf"(?:\s*(?:\(AUC\)|\[AUC\]|\(C[- ]?index\)|\[C[- ]?index\]))?"
    rf"\s*(?:was|of|=|:|,)?\s*(?P<estimate>{NUMBER_PATTERN})"
    rf"\s*[,;)]*\s*\(?(?:95\s*%\s*)?(?:CI|confidence\s+interval)\s*[:=,]?\s*"
    rf"[\[(]?\s*(?P<lower>{NUMBER_PATTERN})\s*{INTERVAL_SEPARATOR}\s*(?P<upper>{NUMBER_PATTERN})",
    flags=re.IGNORECASE,
)


def disease_terms(disease: str) -> list[str]:
    normalized = disease.strip()
    return DISEASE_SYNONYMS.get(normalized.upper(), [normalized])


def build_pubmed_query(symbol: str, disease: str) -> str:
    terms = disease_terms(disease)
    disease_clause = " OR ".join(f'"{term}"' for term in terms)
    return (
        f"({symbol}[Title/Abstract]) AND ({disease_clause}) "
        "AND (biomarker OR expression OR prognostic OR diagnostic OR survival)"
    )


def search_pubmed(
    symbol: str,
    disease: str,
    retmax: int = DEFAULT_MAX_RECORDS,
    email: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    api_key: str | None = None,
) -> PubMedSearchResult:
    """Search PubMed and fetch title/abstract records in auditable pages.

    ``retmax=0`` requests every record available through the first 10,000
    PubMed ESearch results. Abstract text is processed transiently and is not
    copied into the result object.
    """
    if retmax < 0:
        raise ValueError("retmax must be zero or a positive integer")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

    query = build_pubmed_query(symbol, disease)
    common_params = _common_params(email, api_key)
    search_payload = get_json(
        f"{EUTILS_BASE}/esearch.fcgi",
        {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": 0,
            "sort": "relevance",
            "usehistory": "y",
            **common_params,
        },
    )
    search_data = search_payload.get("esearchresult", {})
    total_hits = _as_nonnegative_int(search_data.get("count"))
    retrieval_cap = None if retmax == 0 else retmax
    available_hits = min(total_hits, PUBMED_ESEARCH_MAX)
    target_count = available_hits if retrieval_cap is None else min(available_hits, retrieval_cap)

    if target_count == 0:
        return PubMedSearchResult(
            query=query,
            summary=LiteratureSearchSummary(
                total_hits=total_hits,
                retrieval_cap=retrieval_cap,
                page_size=page_size,
                truncated=total_hits > 0,
            ),
        )

    webenv = str(search_data.get("webenv") or "")
    query_key = str(search_data.get("querykey") or "")
    if not webenv or not query_key:
        raise ExternalSourceError("PubMed ESearch did not return a usable history token.")

    records_by_pmid: dict[str, LiteratureRecord] = {}
    pages_fetched = 0
    retrieval_warnings: list[str] = []
    last_request_at = monotonic()
    for retstart in range(0, target_count, page_size):
        _respect_ncbi_rate_limit(last_request_at, api_key)
        batch_size = min(page_size, target_count - retstart)
        try:
            xml_text = get_text(
                f"{EUTILS_BASE}/efetch.fcgi",
                {
                    "db": "pubmed",
                    "query_key": query_key,
                    "WebEnv": webenv,
                    "retstart": retstart,
                    "retmax": batch_size,
                    "retmode": "xml",
                    "rettype": "abstract",
                    **common_params,
                },
            )
            page_records = parse_pubmed_xml(xml_text, symbol, disease)
        except ExternalSourceError as exc:
            retrieval_warnings.append(f"EFetch page starting at record {retstart} failed: {exc}")
            break
        last_request_at = monotonic()
        pages_fetched += 1
        for record in page_records:
            records_by_pmid.setdefault(record.pmid, record)

    records = list(records_by_pmid.values())
    summary = summarize_literature_search(
        records,
        total_hits=total_hits,
        retrieval_cap=retrieval_cap,
        page_size=page_size,
        pages_fetched=pages_fetched,
        truncated=len(records) < total_hits,
        retrieval_warnings=retrieval_warnings,
    )
    return PubMedSearchResult(query=query, records=records, summary=summary)


def parse_pubmed_xml(xml_text: str, symbol: str, disease: str) -> list[LiteratureRecord]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise ExternalSourceError(f"Failed to parse PubMed EFetch XML: {exc}") from exc

    records: list[LiteratureRecord] = []
    for pubmed_article in root.findall(".//PubmedArticle"):
        citation = pubmed_article.find("MedlineCitation")
        article = citation.find("Article") if citation is not None else None
        if citation is None or article is None:
            continue
        pmid = _element_text(citation.find("PMID"))
        title = _element_text(article.find("ArticleTitle"))
        if not pmid or not title:
            continue

        abstract_parts = []
        for abstract_node in article.findall("Abstract/AbstractText"):
            abstract_text = _element_text(abstract_node)
            if not abstract_text:
                continue
            label = abstract_node.attrib.get("Label")
            abstract_parts.append(f"{label}: {abstract_text}" if label else abstract_text)
        abstract = " ".join(abstract_parts).strip()
        combined_text = f"{title} {abstract}".strip()
        title_terms = _matched_terms(title, disease)
        combined_terms = _matched_terms(combined_text, disease)
        title_symbol = _contains_symbol(title, symbol)
        combined_symbol = _contains_symbol(combined_text, symbol)
        screening_decision, screening_reasons = _screen_record(
            combined_text,
            symbol_found=combined_symbol,
            matched_disease_terms=combined_terms,
            abstract_available=bool(abstract),
        )
        effect_estimates = extract_effect_estimates(abstract, symbol=symbol)
        evidence_class: Literal["direct", "indirect", "background"] = (
            "direct"
            if title_symbol and title_terms
            else "indirect"
            if combined_symbol and combined_terms
            else "background"
        )
        records.append(
            LiteratureRecord(
                pmid=pmid,
                title=title,
                journal=(
                    _element_text(article.find("Journal/Title"))
                    or _element_text(article.find("Journal/ISOAbbreviation"))
                    or None
                ),
                publication_date=_publication_date(article),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                evidence_class=evidence_class,
                matched_terms=combined_terms,
                abstract_available=bool(abstract),
                screening_decision=screening_decision,
                screening_reasons=screening_reasons,
                effect_estimates=effect_estimates,
            )
        )
    return records


def extract_effect_estimates(abstract: str, symbol: str | None = None) -> list[EffectEstimateCandidate]:
    """Extract conservative abstract-level effect-and-95%-CI candidates.

    When a symbol is provided, the biomarker and estimate must occur in the
    same sentence. This reduces, but cannot eliminate, treatment-effect and
    covariate-effect false positives.
    """
    matches: list[tuple[int, EffectEstimateCandidate]] = []
    for pattern, measure_kind in (
        (RATIO_PATTERN, "ratio"),
        (DISCRIMINATION_PATTERN, "discrimination"),
    ):
        for match in pattern.finditer(abstract):
            if symbol and not _contains_symbol(_sentence_containing(abstract, match.start()), symbol):
                continue
            estimate = float(match.group("estimate"))
            lower = float(match.group("lower"))
            upper = float(match.group("upper"))
            if lower > upper or not lower <= estimate <= upper:
                continue
            label = match.group("label").lower().replace("-", " ")
            if measure_kind == "ratio":
                if estimate <= 0 or lower <= 0:
                    continue
                measure: EffectMeasure = (
                    "hazard_ratio"
                    if label in {"hr", "hazard ratio"}
                    else "odds_ratio"
                    if label in {"or", "odds ratio"}
                    else "risk_ratio"
                )
            else:
                if not 0 <= lower <= estimate <= upper <= 1:
                    continue
                measure = "c_index" if "index" in label else "auc"
            matches.append(
                (
                    match.start(),
                    EffectEstimateCandidate(
                        measure=measure,
                        estimate=estimate,
                        ci95=(lower, upper),
                        extraction_method=(
                            "rule_based_same_sentence_biomarker_effect_and_95ci_v1"
                            if symbol
                            else "rule_based_effect_and_95ci_v1"
                        ),
                    ),
                )
            )

    deduplicated: list[EffectEstimateCandidate] = []
    seen: set[tuple[str, float, tuple[float, float]]] = set()
    for _, candidate in sorted(matches, key=lambda item: item[0]):
        key = (candidate.measure, candidate.estimate, candidate.ci95)
        if key not in seen:
            seen.add(key)
            deduplicated.append(candidate)
    return deduplicated


def summarize_literature_search(
    records: list[LiteratureRecord],
    *,
    total_hits: int,
    retrieval_cap: int | None,
    page_size: int,
    pages_fetched: int,
    truncated: bool,
    retrieval_warnings: list[str] | None = None,
) -> LiteratureSearchSummary:
    return LiteratureSearchSummary(
        total_hits=total_hits,
        retrieval_cap=retrieval_cap,
        page_size=page_size,
        pages_fetched=pages_fetched,
        records_retrieved=len(records),
        records_screened=len(records),
        records_included=sum(record.screening_decision == "include_candidate" for record in records),
        records_excluded=sum(record.screening_decision == "exclude" for record in records),
        records_uncertain=sum(record.screening_decision == "uncertain" for record in records),
        abstracts_available=sum(record.abstract_available for record in records),
        records_with_effect_estimates=sum(bool(record.effect_estimates) for record in records),
        effect_estimates_extracted=sum(len(record.effect_estimates) for record in records),
        truncated=truncated,
        retrieval_warnings=retrieval_warnings or [],
    )


def _screen_record(
    text: str,
    *,
    symbol_found: bool,
    matched_disease_terms: list[str],
    abstract_available: bool,
) -> tuple[LiteratureScreeningDecision, list[str]]:
    lowered = text.casefold()
    relevance_matches = [term for term in RELEVANCE_TERMS if term in lowered]
    missing = []
    if not symbol_found:
        missing.append("biomarker identifier")
    if not matched_disease_terms:
        missing.append("disease term")
    if not relevance_matches:
        missing.append("biomarker relevance term")
    if not missing:
        return (
            "include_candidate",
            ["biomarker, disease, and relevance terms were present in the title/abstract"],
        )
    if not abstract_available:
        return "uncertain", [f"abstract unavailable; missing from title: {', '.join(missing)}"]
    return "exclude", [f"missing from title/abstract: {', '.join(missing)}"]


def _common_params(email: str | None, api_key: str | None) -> dict[str, str]:
    params = {"tool": TOOL_NAME}
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def _respect_ncbi_rate_limit(last_request_at: float, api_key: str | None) -> None:
    minimum_interval = 0.11 if api_key else 0.34
    remaining = minimum_interval - (monotonic() - last_request_at)
    if remaining > 0:
        sleep(remaining)


def _as_nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return 0


def _element_text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def _publication_date(article: ElementTree.Element) -> str | None:
    date_node = article.find("ArticleDate")
    if date_node is None:
        date_node = article.find("Journal/JournalIssue/PubDate")
    if date_node is None:
        return None
    medline_date = _element_text(date_node.find("MedlineDate"))
    if medline_date:
        return medline_date
    parts = [_element_text(date_node.find(component)) for component in ("Year", "Month", "Day")]
    rendered = " ".join(part for part in parts if part)
    return rendered or None


def _contains_symbol(text: str, symbol: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(symbol)}(?!\w)", text, flags=re.IGNORECASE))


def _sentence_containing(text: str, offset: int) -> str:
    boundaries = list(re.finditer(r"[.!?](?=\s|$)", text))
    start = 0
    end = len(text)
    for boundary in boundaries:
        if boundary.end() <= offset:
            start = boundary.end()
        elif boundary.start() >= offset:
            end = boundary.end()
            break
    return text[start:end]


def _matched_terms(text: str, disease: str) -> list[str]:
    lowered = text.casefold()
    return [term for term in disease_terms(disease) if term.casefold() in lowered]
