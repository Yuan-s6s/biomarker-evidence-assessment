from pathlib import Path

from biomarker_agent.external_cli import render_markdown
from biomarker_agent.pipeline import load_request, run_validation
from biomarker_agent.reporting.html import render_external_html, render_validation_html
from biomarker_agent.reporting.summary import build_external_report_summary
from biomarker_agent.schemas import (
    BiomarkerEntity,
    EffectEstimateCandidate,
    EvidenceConclusion,
    EvidenceDomainAssessment,
    EvidenceScore,
    ExternalEvidenceResult,
    LiteratureRecord,
    LiteratureSearchSummary,
)

ROOT = Path(__file__).resolve().parents[2]


def test_validation_html_contains_detailed_sections_and_escapes_content():
    result = run_validation(load_request(ROOT / "configs/example_request.yaml"))
    result.entity.query = '<script>alert("unsafe")</script>'
    result.entity.mapping_source = '<img src=x onerror=alert("unsafe")>'

    html = render_validation_html(result)

    assert '<meta name="viewport"' in html
    assert 'id="evidence"' in html
    assert "Cohorts and quality control" in html
    assert "Mean difference" in html
    assert "Hazard ratio" in html
    assert "Apparent incremental discrimination" in html
    assert "Highest supported stage" in html
    assert "Retrospective Association" in html
    assert "Supported claim" in html
    assert "Context of use" in html
    assert "Reference standard" in html
    assert "Random seed" in html
    assert "Legacy heuristic indicators" in html
    assert "Run provenance" in html
    assert 'role="meter"' in html
    assert '<script>alert("unsafe")</script>' not in html
    assert "&lt;script&gt;alert(&quot;unsafe&quot;)&lt;/script&gt;" in html
    assert '<img src=x onerror=alert("unsafe")>' not in html
    assert "&lt;img src=x onerror=alert(&quot;unsafe&quot;)&gt;" in html


def test_external_html_contains_source_details_and_rejects_unsafe_links():
    result = ExternalEvidenceResult(
        entity=BiomarkerEntity(
            query="FAKE<1>",
            id_type="gene_symbol_or_alias",
            hgnc_symbol="FAKE1",
            ensembl_gene_id="ENSG00000000001",
            entrez_id="1",
            uniprot_accession="P00001",
            aliases=["ALIAS1"],
            mapping_source="test",
            resolution_confidence="unique",
        ),
        disease="Example disease",
        literature_query='FAKE1 AND "Example disease"',
        literature_records=[
            LiteratureRecord(
                pmid="123",
                title="FAKE1 <expression> study",
                journal="Example Journal",
                publication_date="2026",
                url="javascript:alert(1)",
                evidence_class="direct",
                matched_terms=["Example disease"],
                abstract_available=True,
                screening_decision="include_candidate",
                screening_reasons=["test inclusion"],
                effect_estimates=[
                    EffectEstimateCandidate(
                        measure="hazard_ratio",
                        estimate=2.1,
                        ci95=(1.2, 3.4),
                    )
                ],
            )
        ],
        literature_summary=LiteratureSearchSummary(
            total_hits=12,
            retrieval_cap=1,
            page_size=1,
            pages_fetched=1,
            records_retrieved=1,
            records_screened=1,
            records_included=1,
            abstracts_available=1,
            records_with_effect_estimates=1,
            effect_estimates_extracted=1,
            truncated=True,
        ),
        database_records=[
            {
                "source": "MyGene.info",
                "symbol": "FAKE1",
                "name": "Example gene",
                "entrezgene": "1",
                "ensembl": {"gene": "ENSG00000000001"},
                "uniprot": {"Swiss-Prot": "P00001"},
                "score": 42.0,
            }
        ],
        evidence_domains={
            "context_of_use": EvidenceDomainAssessment(
                dimension="context_of_use",
                status="partial",
                justification="Test context is incomplete.",
            )
        },
        evidence_conclusion=EvidenceConclusion(
            stage="literature_signal",
            supported_claim="A literature signal is supported for testing only.",
            unmet_requirements=["Verify candidate records against full text."],
        ),
        evidence_scores={
            "id_certainty": EvidenceScore(
                dimension="id_certainty",
                score=5,
                justification="Unique test mapping.",
            )
        },
        overall_confidence="low",
        limitations=["Metadata-level test evidence only."],
        provenance={"generated_at": "2026-09-20T00:00:00+00:00", "sources": ["Test source"]},
    )

    html = render_external_html(result)
    markdown = render_markdown(result)
    summary = build_external_report_summary(result)

    assert 'id="summary"' in html
    assert "Assessment summary" in html
    assert "Bottom line" in html
    assert "PubMed reported 12 query hits; 1 unique record was retrieved" in html
    assert "Retrieval was truncated after 1 of 12 hits" in html
    assert "1 article contained at least one rule-parsed" in html
    assert "Priority next steps" in html
    assert "External database records" in html
    assert "MyGene.info" in html
    assert "Disease-specific literature" in html
    assert "Literature flow" in html
    assert "PubMed total hits" in html
    assert "Records with effect candidates" in html
    assert "Hazard Ratio 2.1" in html
    assert "Retrieval truncated" in html
    assert "PMID" in html
    assert "FAKE1 &lt;expression&gt; study" in html
    assert 'href="#"' in html
    assert "javascript:alert(1)" not in html
    assert "FAKE&lt;1&gt;" in html
    assert "2026-09-20 00:00 UTC" in html
    assert "2026-09-20T00:00:00+00:00" in html
    assert "## Assessment Summary" in markdown
    assert "**Bottom line:** Assessment of FAKE1 in Example disease" in markdown
    assert "**Interpretation boundary:**" in markdown
    assert "### Priority Next Steps" in markdown
    assert summary.priority_next_steps == ["Verify candidate records against full text."]


def test_external_summary_distinguishes_retrieval_failure_from_zero_hits():
    result = ExternalEvidenceResult(
        entity=BiomarkerEntity(
            query="FAKE1",
            id_type="gene_symbol",
            hgnc_symbol="FAKE1",
            resolution_confidence="unique",
        ),
        disease="Example disease",
        literature_query="",
        literature_summary=LiteratureSearchSummary(retrieval_warnings=["PubMed unavailable"]),
        evidence_scores={},
        overall_confidence="insufficient",
        limitations=["PubMed unavailable"],
        provenance={},
    )

    summary = build_external_report_summary(result)

    assert "PubMed retrieval did not complete" in summary.key_findings[1]
    assert "reported 0 query hit" not in summary.key_findings[1]
    assert "No retrieved article contained" in summary.key_findings[3]
