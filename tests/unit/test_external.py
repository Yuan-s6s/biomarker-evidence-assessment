from biomarker_agent.external.evidence import assess_external_evidence
from biomarker_agent.external.pubmed import build_pubmed_query


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

    def fake_search_pubmed(symbol, disease, retmax=10, email=None):
        from biomarker_agent.schemas import LiteratureRecord

        return (
            "FAKE1 AND LSCC",
            [
                LiteratureRecord(
                    pmid="1",
                    title="FAKE1 expression in lung squamous cell carcinoma",
                    journal="Example",
                    publication_date="2026",
                    url="https://pubmed.ncbi.nlm.nih.gov/1/",
                    evidence_class="direct",
                    matched_terms=["lung squamous cell carcinoma"],
                )
            ],
            {},
        )

    monkeypatch.setattr("biomarker_agent.external.evidence.query_mygene", fake_query_mygene)
    monkeypatch.setattr("biomarker_agent.external.evidence.search_pubmed", fake_search_pubmed)
    result = assess_external_evidence("FAKE1", "LSCC")
    assert result.entity.hgnc_symbol == "FAKE1"
    assert result.evidence_scores["direct_literature_support"].score == 1
    assert result.overall_confidence == "low"
    assert result.evidence_conclusion.stage == "literature_signal"
    assert result.evidence_domains["study_quality"].status == "not_evaluated"
    assert result.provenance["software_version"] == "0.2.0"
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

    def fake_search_pubmed(symbol, disease, retmax=10, email=None):
        from biomarker_agent.schemas import LiteratureRecord

        records = [
            LiteratureRecord(
                pmid=str(index),
                title=f"FAKE1 expression in Example disease study {index}",
                url=f"https://pubmed.ncbi.nlm.nih.gov/{index}/",
                evidence_class="direct",
                matched_terms=["Example disease"],
            )
            for index in range(1, 21)
        ]
        return "FAKE1 AND Example disease", records, {}

    monkeypatch.setattr("biomarker_agent.external.evidence.query_mygene", fake_query_mygene)
    monkeypatch.setattr("biomarker_agent.external.evidence.search_pubmed", fake_search_pubmed)

    result = assess_external_evidence("FAKE1", "Example disease", retmax=20)

    assert len(result.literature_records) == 20
    assert result.evidence_scores["direct_literature_support"].score == 1
    assert result.evidence_conclusion.stage == "literature_signal"
    assert result.overall_confidence == "low"
