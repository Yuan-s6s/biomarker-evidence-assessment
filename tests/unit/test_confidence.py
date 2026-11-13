from pathlib import Path

import pytest

from biomarker_agent.confidence import build_request_from_answers, planning_confidence, split_csv_answer, yes
from biomarker_agent.schemas import CohortConfig, ContextOfUse, DatasetConfig, ValidationRequest


def test_planning_confidence_resolves_unique_id_without_statistics():
    summary = planning_confidence("RAB38", "lung squamous cell carcinoma", ["diagnostic"], ["rna"])
    assert summary["status"] == "planning_only"
    assert summary["confidence"]["id_certainty"]["score"] == 5
    assert summary["confidence"]["direct_evidence"]["score"] == 0
    assert summary["evidence_conclusion"]["stage"] == "identity_confirmed"
    assert summary["evidence_domains"]["context_of_use"]["status"] == "partial"
    assert summary["evidence_domains"]["clinical_utility"]["status"] == "not_evaluated"


def test_planning_confidence_blocks_ambiguous_id():
    summary = planning_confidence("RAB", "lung squamous cell carcinoma", ["diagnostic"], ["rna"])
    assert summary["status"] == "needs_confirmation"
    assert summary["confidence"]["id_certainty"]["score"] == 0
    assert summary["evidence_conclusion"]["stage"] == "not_assessed"


def test_answer_helpers():
    assert split_csv_answer("diagnostic, prognostic", []) == ["diagnostic", "prognostic"]
    assert split_csv_answer("", ["diagnostic"]) == ["diagnostic"]
    assert yes("yes")
    assert not yes("no")


def test_build_request_from_answers():
    request = build_request_from_answers(
        biomarker_id="RAB38",
        disease="lung squamous cell carcinoma",
        intended_uses=["diagnostic"],
        molecular_layers=["rna"],
        endpoints=["overall_survival"],
        covariates=["age"],
        discovery_expression_path=Path("expr.csv"),
        discovery_metadata_path=Path("meta.csv"),
    )
    assert request.biomarker_id == "RAB38"
    assert request.datasets.discovery.expression_path == Path("expr.csv")


def test_dataset_roles_and_files_are_kept_separate():
    discovery = CohortConfig(
        name="discovery",
        role="discovery",
        expression_path=Path("discovery_expr.csv"),
        metadata_path=Path("discovery_meta.csv"),
    )
    reused_external = CohortConfig(
        name="external",
        role="external",
        expression_path=Path("discovery_expr.csv"),
        metadata_path=Path("external_meta.csv"),
    )

    with pytest.raises(ValueError, match="must not reuse"):
        DatasetConfig(discovery=discovery, external=[reused_external])


def test_context_disease_must_match_request_scope():
    datasets = DatasetConfig(
        discovery=CohortConfig(
            name="discovery",
            role="discovery",
            expression_path=Path("discovery_expr.csv"),
            metadata_path=Path("discovery_meta.csv"),
        )
    )

    with pytest.raises(ValueError, match="must match"):
        ValidationRequest(
            biomarker_id="RAB38",
            disease="lung squamous cell carcinoma",
            contexts_of_use=[ContextOfUse(category="diagnostic", disease="breast cancer")],
            datasets=datasets,
        )
