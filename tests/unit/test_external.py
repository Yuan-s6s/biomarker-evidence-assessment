from biomarker_agent.evidence import build_external_framework
from biomarker_agent.external.evidence import assess_external_evidence
from biomarker_agent.external.http import ExternalSourceError
from biomarker_agent.external.pubmed import (
    build_pubmed_query,
    extract_effect_estimates,
    parse_pubmed_xml,
    search_pubmed,
    summarize_literature_search,
)
from biomarker_agent.schemas import BiomarkerEntity, ContextOfUse, LiteratureSearchSummary, PubMedSearchResult


def test_pubmed_query_mentions_symbol_and_disease():
    query = build_pubmed_query("RAB38", "LSCC")
    assert "RAB38" in query
    assert '"LSCC"' in query
    assert "lung squamous cell carcinoma" not in query
    assert "laryngeal squamous cell carcinoma" not in query

    explicit_query = build_pubmed_query("RAB38", "lung squamous cell carcinoma")
    assert "lung squamous cell carcinoma" in explicit_query
    assert "LUSC" in explicit_query


def test_external_assessment_with_mocked_sources(monkeypatch):
    def fake_query_mygene(query):
        from biomarker_agent.schemas import BiomarkerEntity

        return (
            BiomarkerEntity(
                query=query,
                id_type="external_query",
                hgnc_symbol="FAKE1",
                entrez_id="1",
                mapping_source="mygene_v3",
                resolution_confidence="unique",
            ),
            [{"source": "MyGene.info", "symbol": "FAKE1"}],
        )

    def fake_search_pubmed(symbol, disease, retmax=500, email=None, page_size=100, api_key=None):
        from biomarker_agent.schemas import LiteratureRecord

        records = [
            LiteratureRecord(
                pmid="1",
                title="FAKE1 expression in lung squamous cell carcinoma",
                journal="Example",
                publication_date="2026",
                url="https://pubmed.ncbi.nlm.nih.gov/1/",
                evidence_class="direct",
                matched_terms=["lung squamous cell carcinoma"],
                abstract_available=True,
                screening_decision="include_candidate",
            )
        ]
        return PubMedSearchResult(
            query="FAKE1 AND LSCC",
            records=records,
            summary=LiteratureSearchSummary(
                total_hits=1,
                retrieval_cap=retmax,
                page_size=page_size,
                pages_fetched=1,
                records_retrieved=1,
                records_screened=1,
                records_included=1,
                abstracts_available=1,
            ),
        )

    monkeypatch.setattr("biomarker_agent.external.evidence.query_mygene", fake_query_mygene)
    monkeypatch.setattr("biomarker_agent.external.evidence.search_pubmed", fake_search_pubmed)
    result = assess_external_evidence("FAKE1", "LSCC")
    assert result.entity.hgnc_symbol == "FAKE1"
    assert result.evidence_scores["direct_literature_support"].score == 1
    assert result.overall_confidence == "low"
    assert result.evidence_conclusion.stage == "literature_signal"
    assert result.evidence_domains["study_quality"].status == "not_evaluated"
    assert result.literature_summary.total_hits == 1
    assert result.literature_summary.records_included == 1
    assert result.provenance["software_version"] == "0.3.0"
    assert result.provenance["runtime_versions"]["pydantic"]
    assert any("lung or laryngeal" in limitation for limitation in result.limitations)


def test_publication_count_does_not_raise_metadata_evidence_score(monkeypatch):
    def fake_query_mygene(query):
        from biomarker_agent.schemas import BiomarkerEntity

        return (
            BiomarkerEntity(
                query=query,
                id_type="external_query",
                hgnc_symbol="FAKE1",
                mapping_source="mygene_v3",
                resolution_confidence="unique",
            ),
            [{"source": "MyGene.info", "symbol": "FAKE1"}],
        )

    def fake_search_pubmed(symbol, disease, retmax=500, email=None, page_size=100, api_key=None):
        from biomarker_agent.schemas import LiteratureRecord

        records = [
            LiteratureRecord(
                pmid=str(index),
                title=f"FAKE1 expression in Example disease study {index}",
                url=f"https://pubmed.ncbi.nlm.nih.gov/{index}/",
                evidence_class="direct",
                matched_terms=["Example disease"],
                abstract_available=True,
                screening_decision="include_candidate",
            )
            for index in range(1, 21)
        ]
        return PubMedSearchResult(
            query="FAKE1 AND Example disease",
            records=records,
            summary=LiteratureSearchSummary(
                total_hits=20,
                retrieval_cap=retmax,
                page_size=page_size,
                pages_fetched=1,
                records_retrieved=20,
                records_screened=20,
                records_included=20,
                abstracts_available=20,
            ),
        )

    monkeypatch.setattr("biomarker_agent.external.evidence.query_mygene", fake_query_mygene)
    monkeypatch.setattr("biomarker_agent.external.evidence.search_pubmed", fake_search_pubmed)

    result = assess_external_evidence("FAKE1", "Example disease", retmax=20)

    assert len(result.literature_records) == 20
    assert result.evidence_scores["direct_literature_support"].score == 1
    assert result.evidence_conclusion.stage == "literature_signal"
    assert result.overall_confidence == "low"


def test_pubmed_failure_is_a_retrieval_concern_not_a_no_results_claim(monkeypatch):
    def fake_query_mygene(query):
        from biomarker_agent.schemas import BiomarkerEntity

        return (
            BiomarkerEntity(
                query=query,
                id_type="external_query",
                hgnc_symbol="FAKE1",
                mapping_source="mygene_v3",
                resolution_confidence="unique",
            ),
            [],
        )

    def fake_search_pubmed(*args, **kwargs):
        raise ExternalSourceError("PubMed unavailable")

    monkeypatch.setattr("biomarker_agent.external.evidence.query_mygene", fake_query_mygene)
    monkeypatch.setattr("biomarker_agent.external.evidence.search_pubmed", fake_search_pubmed)

    result = assess_external_evidence("FAKE1", "Example disease")

    assert result.evidence_conclusion.stage == "identity_confirmed"
    assert result.evidence_domains["literature_retrieval"].status == "concern"
    assert any("PubMed unavailable" in limitation for limitation in result.limitations)
    assert not any("No PubMed records matched" in limitation for limitation in result.limitations)


def test_effect_extraction_requires_effect_and_95_percent_ci():
    abstract = (
        "TP53 was associated with survival (HR = 2.10, 95% CI 1.20-3.40; p=0.01). "
        "Discrimination was AUC 0.82 (95% CI 0.75 to 0.89). Another result had p=0.03 only."
    )
    estimates = extract_effect_estimates(abstract)

    assert [item.measure for item in estimates] == ["hazard_ratio", "auc"]
    assert estimates[0].estimate == 2.1
    assert estimates[0].ci95 == (1.2, 3.4)
    assert estimates[1].ci95 == (0.75, 0.89)

    biomarker_linked = extract_effect_estimates(abstract, symbol="TP53")
    assert [item.measure for item in biomarker_linked] == ["hazard_ratio"]
    assert (
        extract_effect_estimates(
            "TP53 mutations were measured. Treatment improved survival (HR 0.70, 95% CI 0.60-0.82).",
            symbol="TP53",
        )
        == []
    )
    parenthesized_labels = extract_effect_estimates(
        "TP53 hazard ratio (HR), 1.80 (95% CI 1.20-2.70), and area under the curve (AUC) 0.81 (95% CI 0.74-0.88).",
        symbol="TP53",
    )
    assert [item.measure for item in parenthesized_labels] == ["hazard_ratio", "auc"]


def test_pubmed_search_pages_and_reports_flow(monkeypatch):
    calls = []

    def fake_get_json(url, params):
        assert params["retmax"] == 0
        assert params["usehistory"] == "y"
        return {"esearchresult": {"count": "5", "querykey": "1", "webenv": "test-history"}}

    def fake_get_text(url, params):
        calls.append(params)
        start = int(params["retstart"])
        if start == 0:
            return _pubmed_xml(
                [
                    (
                        "1",
                        "TP53 expression in breast cancer",
                        "TP53 was prognostic in breast cancer; HR 2.10 (95% CI 1.20-3.40).",
                    ),
                    (
                        "2",
                        "TP53 diagnostic biomarker",
                        "In breast cancer, TP53 expression had AUC 0.82 (95% CI 0.75-0.89).",
                    ),
                ]
            )
        return _pubmed_xml([("3", "TP53 expression in breast cancer", "")])

    monkeypatch.setattr("biomarker_agent.external.pubmed.get_json", fake_get_json)
    monkeypatch.setattr("biomarker_agent.external.pubmed.get_text", fake_get_text)
    monkeypatch.setattr("biomarker_agent.external.pubmed.sleep", lambda _: None)

    result = search_pubmed("TP53", "breast cancer", retmax=3, page_size=2)

    assert [call["retstart"] for call in calls] == [0, 2]
    assert [call["retmax"] for call in calls] == [2, 1]
    assert all(call["WebEnv"] == "test-history" for call in calls)
    assert result.summary.total_hits == 5
    assert result.summary.records_retrieved == 3
    assert result.summary.records_screened == 3
    assert result.summary.records_included == 3
    assert result.summary.abstracts_available == 2
    assert result.summary.records_with_effect_estimates == 2
    assert result.summary.effect_estimates_extracted == 2
    assert result.summary.pages_fetched == 2
    assert result.summary.truncated is True


def test_automated_screening_separates_included_excluded_and_uncertain():
    records = parse_pubmed_xml(
        _pubmed_xml(
            [
                ("1", "TP53 expression in breast cancer", "TP53 was a prognostic biomarker."),
                ("2", "Breast cancer outcome study", "Expression was prognostic, but no target was named."),
                ("3", "Breast cancer report", ""),
            ]
        ),
        "TP53",
        "breast cancer",
    )
    summary = summarize_literature_search(
        records,
        total_hits=3,
        retrieval_cap=3,
        page_size=3,
        pages_fetched=1,
        truncated=False,
    )

    assert [record.screening_decision for record in records] == ["include_candidate", "exclude", "uncertain"]
    assert summary.records_included == 1
    assert summary.records_excluded == 1
    assert summary.records_uncertain == 1


def test_retrieved_but_excluded_records_do_not_raise_literature_stage():
    records = parse_pubmed_xml(
        _pubmed_xml([("1", "Breast cancer outcome study", "Expression was prognostic, but no target was named.")]),
        "TP53",
        "breast cancer",
    )
    summary = summarize_literature_search(
        records,
        total_hits=1,
        retrieval_cap=1,
        page_size=1,
        pages_fetched=1,
        truncated=False,
    )

    domains, conclusion = build_external_framework(
        BiomarkerEntity(
            query="TP53",
            id_type="gene_symbol",
            hgnc_symbol="TP53",
            resolution_confidence="unique",
        ),
        ContextOfUse(category="unspecified", disease="breast cancer"),
        records,
        summary,
    )

    assert summary.records_excluded == 1
    assert domains["literature_retrieval"].status == "partial"
    assert conclusion.stage == "identity_confirmed"


def test_pubmed_search_preserves_completed_pages_after_page_failure(monkeypatch):
    monkeypatch.setattr(
        "biomarker_agent.external.pubmed.get_json",
        lambda url, params: {"esearchresult": {"count": "5", "querykey": "1", "webenv": "test-history"}},
    )

    def fake_get_text(url, params):
        if int(params["retstart"]) == 0:
            return _pubmed_xml(
                [
                    ("1", "TP53 expression in breast cancer", "TP53 was prognostic in breast cancer."),
                    ("2", "TP53 biomarker in breast cancer", "TP53 expression predicted outcome."),
                ]
            )
        raise ExternalSourceError("temporary upstream failure")

    monkeypatch.setattr("biomarker_agent.external.pubmed.get_text", fake_get_text)
    monkeypatch.setattr("biomarker_agent.external.pubmed.sleep", lambda _: None)

    result = search_pubmed("TP53", "breast cancer", retmax=3, page_size=2)

    assert result.summary.total_hits == 5
    assert result.summary.records_retrieved == 2
    assert result.summary.pages_fetched == 1
    assert result.summary.truncated is True
    assert "record 2 failed" in result.summary.retrieval_warnings[0]


def test_pubmed_search_preserves_completed_pages_after_malformed_xml(monkeypatch):
    monkeypatch.setattr(
        "biomarker_agent.external.pubmed.get_json",
        lambda url, params: {"esearchresult": {"count": "3", "querykey": "1", "webenv": "test-history"}},
    )

    def fake_get_text(url, params):
        if int(params["retstart"]) == 0:
            return _pubmed_xml(
                [
                    ("1", "TP53 expression in breast cancer", "TP53 was prognostic in breast cancer."),
                    ("2", "TP53 biomarker in breast cancer", "TP53 expression predicted outcome."),
                ]
            )
        return "<PubmedArticleSet><broken>"

    monkeypatch.setattr("biomarker_agent.external.pubmed.get_text", fake_get_text)
    monkeypatch.setattr("biomarker_agent.external.pubmed.sleep", lambda _: None)

    result = search_pubmed("TP53", "breast cancer", retmax=3, page_size=2)

    assert result.summary.records_retrieved == 2
    assert result.summary.pages_fetched == 1
    assert result.summary.truncated is True
    assert "Failed to parse PubMed EFetch XML" in result.summary.retrieval_warnings[0]


def test_zero_max_records_retrieves_all_available_pages(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "biomarker_agent.external.pubmed.get_json",
        lambda url, params: {"esearchresult": {"count": "3", "querykey": "1", "webenv": "test-history"}},
    )

    def fake_get_text(url, params):
        calls.append(int(params["retstart"]))
        if int(params["retstart"]) == 0:
            return _pubmed_xml(
                [
                    ("1", "TP53 expression in breast cancer", "TP53 was prognostic in breast cancer."),
                    ("2", "TP53 biomarker in breast cancer", "TP53 expression predicted outcome."),
                ]
            )
        return _pubmed_xml([("3", "TP53 prognosis in breast cancer", "TP53 was prognostic.")])

    monkeypatch.setattr("biomarker_agent.external.pubmed.get_text", fake_get_text)
    monkeypatch.setattr("biomarker_agent.external.pubmed.sleep", lambda _: None)

    result = search_pubmed("TP53", "breast cancer", retmax=0, page_size=2)

    assert calls == [0, 2]
    assert result.summary.retrieval_cap is None
    assert result.summary.records_retrieved == 3
    assert result.summary.truncated is False


def _pubmed_xml(records):
    articles = []
    for pmid, title, abstract in records:
        abstract_xml = f"<Abstract><AbstractText>{abstract}</AbstractText></Abstract>" if abstract else ""
        articles.append(
            "<PubmedArticle><MedlineCitation>"
            f"<PMID>{pmid}</PMID><Article><Journal><JournalIssue><PubDate><Year>2026</Year>"
            "</PubDate></JournalIssue><Title>Example Journal</Title></Journal>"
            f"<ArticleTitle>{title}</ArticleTitle>{abstract_xml}</Article>"
            "</MedlineCitation></PubmedArticle>"
        )
    return f"<PubmedArticleSet>{''.join(articles)}</PubmedArticleSet>"
