from pathlib import Path

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
    assert result.overall_grade in {"C", "D"}
    json_path, markdown_path, html_path = write_outputs(result, tmp_path)
    assert json_path.exists()
    assert "Biomarker Evidence Assessment Report" in markdown_path.read_text()
    assert "<html" in html_path.read_text()
