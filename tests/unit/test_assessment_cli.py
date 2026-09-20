from pathlib import Path

from biomarker_agent.assessment_cli import build_parser


def test_external_workflow_arguments():
    args = build_parser().parse_args(["external", "TP53", "--disease", "breast cancer", "--retmax", "5"])
    assert args.workflow == "external"
    assert args.biomarker_id == "TP53"
    assert args.disease == "breast cancer"
    assert args.retmax == 5


def test_cohort_workflow_arguments():
    args = build_parser().parse_args(["cohort", "configs/example_request.yaml"])
    assert args.workflow == "cohort"
    assert args.request == Path("configs/example_request.yaml")


def test_guided_workflow_arguments():
    args = build_parser().parse_args(["guided", "--planning-only"])
    assert args.workflow == "guided"
    assert args.planning_only is True
