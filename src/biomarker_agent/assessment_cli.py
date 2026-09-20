from __future__ import annotations

import argparse
from pathlib import Path

from biomarker_agent.confidence_cli import run_guided_assessment
from biomarker_agent.external import assess_external_evidence
from biomarker_agent.external_cli import write_external_outputs
from biomarker_agent.pipeline import load_request, run_validation
from biomarker_agent.reporting import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="biomarker-assess",
        description="Assess biomarker evidence and validation readiness",
    )
    workflows = parser.add_subparsers(dest="workflow", required=True)

    external = workflows.add_parser(
        "external",
        help="Search public identity and literature metadata",
    )
    external.add_argument("biomarker_id")
    external.add_argument("--disease", default="LSCC")
    external.add_argument("--retmax", type=int, default=10)
    external.add_argument("--email", help="Optional email passed to NCBI E-utilities")
    external.add_argument("--out", type=Path, default=Path("reports/external"))

    cohort = workflows.add_parser(
        "cohort",
        help="Run a configured local cohort assessment",
    )
    cohort.add_argument("request", type=Path)
    cohort.add_argument("--out", type=Path, default=Path("reports/latest"))

    guided = workflows.add_parser(
        "guided",
        help="Answer questions and optionally supply cohort files",
    )
    guided.add_argument("--out", type=Path, default=Path("reports/confidence"))
    guided.add_argument(
        "--planning-only",
        action="store_true",
        help="Resolve the entity and report evidence gaps without cohort files",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.workflow == "external":
        external_result = assess_external_evidence(
            args.biomarker_id,
            args.disease,
            retmax=args.retmax,
            email=args.email,
        )
        write_external_outputs(external_result, args.out)
        print(f"Overall confidence: {external_result.overall_confidence}")
        for score in external_result.evidence_scores.values():
            print(f"{score.dimension}: {score.score}/5 - {score.justification}")
        print(f"Wrote {args.out / 'external_evidence.json'}")
        print(f"Wrote {args.out / 'external_report.md'}")
        print(f"Wrote {args.out / 'external_report.html'}")
        return

    if args.workflow == "cohort":
        cohort_result = run_validation(load_request(args.request))
        for path in write_outputs(cohort_result, args.out):
            print(f"Wrote {path}")
        return

    run_guided_assessment(args.out, args.planning_only)


if __name__ == "__main__":
    main()
