from pathlib import Path

from biomarker_agent.analyses import run_diagnostic_analysis
from biomarker_agent.datasets import load_cohort
from biomarker_agent.qc import run_qc
from biomarker_agent.schemas import CohortConfig

ROOT = Path(__file__).resolve().parents[1]


def _cohort():
    return load_cohort(
        CohortConfig(
            name="discovery",
            role="discovery",
            expression_path=ROOT / "fixtures/discovery_expression.csv",
            metadata_path=ROOT / "fixtures/discovery_metadata.csv",
        )
    )


def test_qc_passes_simulated_fixture():
    cohort = _cohort()
    values = cohort.biomarker_values(["RAB38"])
    qc = run_qc(cohort, values)
    assert qc.passed
    assert qc.tumor_count == 6
    assert qc.normal_count == 4


def test_diagnostic_detects_higher_tumor_expression():
    cohort = _cohort()
    result = run_diagnostic_analysis(cohort, "RAB38", cohort.biomarker_values(["RAB38"]))
    assert result.direction == "higher_in_tumor"
    assert result.mean_difference > 4
    assert result.auc == 1.0
