from pathlib import Path

from biomarker_agent.analyses import run_clinical_utility, run_prognostic_analysis
from biomarker_agent.datasets import load_cohort
from biomarker_agent.schemas import CohortConfig

ROOT = Path(__file__).resolve().parents[1]


def test_cox_model_returns_biomarker_term():
    cohort = load_cohort(
        CohortConfig(
            name="discovery",
            role="discovery",
            expression_path=ROOT / "fixtures/discovery_expression.csv",
            metadata_path=ROOT / "fixtures/discovery_metadata.csv",
        )
    )
    result = run_prognostic_analysis(cohort, "RAB38", cohort.biomarker_values(["RAB38"]), ["age", "stage"])
    terms = {term.term: term for term in result.terms}
    assert "biomarker_expression" in terms
    assert terms["biomarker_expression"].hazard_ratio > 1.0
    assert result.concordance_index >= 0.5


def test_clinical_utility_compares_baseline_and_augmented():
    cohort = load_cohort(
        CohortConfig(
            name="discovery",
            role="discovery",
            expression_path=ROOT / "fixtures/discovery_expression.csv",
            metadata_path=ROOT / "fixtures/discovery_metadata.csv",
        )
    )
    utility = run_clinical_utility(cohort, cohort.biomarker_values(["RAB38"]), ["age", "stage"])
    assert utility.augmented_c_index is not None
    assert utility.delta_c_index is not None
