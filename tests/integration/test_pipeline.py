from pathlib import Path

from biomarker_agent.evidence import build_validation_framework
from biomarker_agent.pipeline import load_request, run_validation
from biomarker_agent.reporting import write_outputs

ROOT = Path(__file__).resolve().parents[2]


def test_pipeline_generates_result_and_reports(tmp_path):
    request = load_request(ROOT / "configs/example_request.yaml")
    result = run_validation(request)
    assert result.entity.hgnc_symbol == "RAB38"
    assert all(qc.passed for qc in result.qc)
    assert len(result.analyses.diagnostic) == 2
    assert result.analyses.diagnostic[0].direction == "higher_in_tumor"
    assert result.evidence_conclusion.stage == "retrospective_association"
    assert result.evidence_domains["independent_replication"].status == "partial"
    assert result.evidence_domains["locked_external_model_validation"].status == "not_evaluated"
    assert result.evidence_domains["analytical_validity"].status == "not_evaluated"
    assert result.overall_grade == "D"
    assert result.provenance["software_version"] == "0.3.0"
    assert result.provenance["phase"] == "phase_2_claim_bounded_assessment"
    assert result.provenance["runtime_versions"]["python"]
    assert all(item.random_seed == 202601 for item in result.robustness.values())
    json_path, markdown_path, html_path = write_outputs(result, tmp_path)
    assert json_path.exists()
    assert "Biomarker Evidence Assessment Report" in markdown_path.read_text()
    assert "<html" in html_path.read_text()


def test_pipeline_only_runs_requested_claim_analysis():
    request = load_request(ROOT / "configs/example_request.yaml")
    request.contexts_of_use = [context for context in request.contexts_of_use if context.category == "prognostic"]
    request.intended_uses = ["prognostic"]

    result = run_validation(request)

    assert result.analyses.diagnostic == []
    assert len(result.analyses.prognostic) == 2
    assert result.robustness == {}


def test_replication_stage_requires_all_documented_gates():
    result = run_validation(load_request(ROOT / "configs/example_request.yaml"))
    external = next(dataset for dataset in result.datasets if dataset["role"] == "external")
    external["sample_size_justification"] = "Precision target was prespecified and met."
    for qc in result.qc:
        qc.warnings = []

    domains, conclusion = build_validation_framework(result)

    assert domains["independent_replication"].status == "supported"
    assert conclusion.stage == "independent_association_replication"
