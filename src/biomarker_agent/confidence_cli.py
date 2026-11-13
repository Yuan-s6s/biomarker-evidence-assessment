from __future__ import annotations

import argparse
import json
from pathlib import Path

from biomarker_agent.confidence import (
    build_request_from_answers,
    planning_confidence,
    run_confidence_tool,
    split_csv_answer,
    yes,
)


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or (default or "")


def ask_required(prompt: str) -> str:
    while not (answer := ask(prompt)):
        print(f"{prompt} is required.")
    return answer


def run_guided_assessment(out: Path, planning_only: bool = False) -> None:
    biomarker_id = ask_required("Biomarker ID")
    disease = ask_required("Disease (full name recommended)")
    intended_uses = split_csv_answer(
        ask("Intended use(s), comma-separated", "diagnostic,prognostic"), ["diagnostic", "prognostic"]
    )
    molecular_layers = split_csv_answer(ask("Molecular layer(s), comma-separated", "rna"), ["rna"])

    if planning_only or not yes(ask("Do you have discovery cohort CSV files?", "no")):
        summary = planning_confidence(biomarker_id, disease, intended_uses, molecular_layers)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "planning_confidence.json"
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        print(f"Wrote {path}")
        return

    discovery_expression = Path(ask("Discovery expression CSV path"))
    discovery_metadata = Path(ask("Discovery metadata CSV path"))
    endpoints = split_csv_answer(ask("Endpoint(s), comma-separated", "overall_survival"), ["overall_survival"])
    covariates = split_csv_answer(ask("Covariates, comma-separated", "age,stage"), ["age", "stage"])

    external_expression = None
    external_metadata = None
    if yes(ask("Do you have external validation CSV files?", "no")):
        external_expression = Path(ask("External expression CSV path"))
        external_metadata = Path(ask("External metadata CSV path"))

    request = build_request_from_answers(
        biomarker_id=biomarker_id,
        disease=disease,
        intended_uses=intended_uses,
        molecular_layers=molecular_layers,
        endpoints=endpoints,
        covariates=covariates,
        discovery_expression_path=discovery_expression,
        discovery_metadata_path=discovery_metadata,
        external_expression_path=external_expression,
        external_metadata_path=external_metadata,
    )
    result = run_confidence_tool(request, out)
    print(f"Evidence stage: {result.evidence_conclusion.stage}")
    print(f"Supported claim: {result.evidence_conclusion.supported_claim}")
    for assessment in result.evidence_domains.values():
        print(f"{assessment.dimension}: {assessment.status} - {assessment.justification}")
    print(f"Wrote {out / 'result.json'}")
    print(f"Wrote {out / 'report.md'}")
    print(f"Wrote {out / 'report.html'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask questions and assess biomarker evidence readiness")
    parser.add_argument("--out", type=Path, default=Path("reports/confidence"))
    parser.add_argument(
        "--planning-only",
        action="store_true",
        help="Resolve the entity and report evidence gaps without asking for data files",
    )
    args = parser.parse_args()
    run_guided_assessment(args.out, args.planning_only)


if __name__ == "__main__":
    main()
