from pathlib import Path

from biomarker_agent.confidence import build_request_from_answers, planning_confidence, split_csv_answer, yes


def test_planning_confidence_resolves_unique_id_without_statistics():
    summary = planning_confidence("RAB38", "LSCC", ["diagnostic"], ["rna"])
    assert summary["status"] == "planning_only"
    assert summary["confidence"]["id_certainty"]["score"] == 5
    assert summary["confidence"]["direct_evidence"]["score"] == 0


def test_planning_confidence_blocks_ambiguous_id():
    summary = planning_confidence("RAB", "LSCC", ["diagnostic"], ["rna"])
    assert summary["status"] == "needs_confirmation"
    assert summary["confidence"]["id_certainty"]["score"] == 0


def test_answer_helpers():
    assert split_csv_answer("diagnostic, prognostic", []) == ["diagnostic", "prognostic"]
    assert split_csv_answer("", ["diagnostic"]) == ["diagnostic"]
    assert yes("yes")
    assert not yes("no")


def test_build_request_from_answers():
    request = build_request_from_answers(
        biomarker_id="RAB38",
        disease="LSCC",
        intended_uses=["diagnostic"],
        molecular_layers=["rna"],
        endpoints=["overall_survival"],
        covariates=["age"],
        discovery_expression_path=Path("expr.csv"),
        discovery_metadata_path=Path("meta.csv"),
    )
    assert request.biomarker_id == "RAB38"
    assert request.datasets.discovery.expression_path == Path("expr.csv")
