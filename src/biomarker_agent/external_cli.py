from __future__ import annotations

import argparse
import json
from pathlib import Path

from biomarker_agent.external import assess_external_evidence
from biomarker_agent.reporting.html import render_external_html
from biomarker_agent.schemas import ContextOfUse, ExternalEvidenceResult

BIOMARKER_CATEGORIES = [
    "diagnostic",
    "prognostic",
    "predictive",
    "monitoring",
    "susceptibility_risk",
    "pharmacodynamic_response",
    "safety",
    "unspecified",
]


def add_context_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--category", choices=BIOMARKER_CATEGORIES, default="unspecified")
    parser.add_argument("--population", help="Target population for the intended use")
    parser.add_argument("--setting", help="Clinical setting or point in the care pathway")
    parser.add_argument("--specimen", help="Specimen type, such as plasma or tumor tissue")
    parser.add_argument("--assay", help="Measurement assay or platform")
    parser.add_argument("--endpoint", help="Clinical endpoint or target condition")
    parser.add_argument("--time-horizon", help="Prediction or monitoring time horizon")
    parser.add_argument("--reference-standard", help="Reference standard for diagnostic claims")
    parser.add_argument("--intended-action", help="Decision or action informed by the biomarker")
    parser.add_argument("--intervention", help="Intervention for predictive or response claims")
    parser.add_argument("--baseline-comparator", help="Existing clinical test, model, or standard of care")


def context_from_args(args: argparse.Namespace) -> ContextOfUse:
    return ContextOfUse(
        category=args.category,
        disease=args.disease,
        target_population=args.population,
        clinical_setting=args.setting,
        specimen=args.specimen,
        assay=args.assay,
        endpoint=args.endpoint,
        time_horizon=args.time_horizon,
        reference_standard=args.reference_standard,
        intended_action=args.intended_action,
        intervention=args.intervention,
        baseline_comparator=args.baseline_comparator,
    )


def render_markdown(result: ExternalEvidenceResult) -> str:
    lines = [
        f"# External Biomarker Evidence: {result.entity.hgnc_symbol or result.entity.query}",
        "",
        f"Disease: {result.disease}",
        f"Evidence stage: **{result.evidence_conclusion.stage}**",
        f"Supported claim: {result.evidence_conclusion.supported_claim}",
        "",
        "## Context of Use",
        f"- Category: {result.context_of_use.category if result.context_of_use else 'not supplied'}",
        f"- Target population: {result.context_of_use.target_population if result.context_of_use else None}",
        f"- Clinical setting: {result.context_of_use.clinical_setting if result.context_of_use else None}",
        f"- Specimen: {result.context_of_use.specimen if result.context_of_use else None}",
        f"- Assay: {result.context_of_use.assay if result.context_of_use else None}",
        f"- Endpoint: {result.context_of_use.endpoint if result.context_of_use else None}",
        f"- Time horizon: {result.context_of_use.time_horizon if result.context_of_use else None}",
        f"- Reference standard: {result.context_of_use.reference_standard if result.context_of_use else None}",
        f"- Intervention: {result.context_of_use.intervention if result.context_of_use else None}",
        f"- Baseline comparator: {result.context_of_use.baseline_comparator if result.context_of_use else None}",
        f"- Intended action: {result.context_of_use.intended_action if result.context_of_use else None}",
        "",
        "## Entity",
        f"- Query: `{result.entity.query}`",
        f"- Symbol: {result.entity.hgnc_symbol}",
        f"- Ensembl: {result.entity.ensembl_gene_id}",
        f"- Entrez: {result.entity.entrez_id}",
        f"- UniProt: {result.entity.uniprot_accession}",
        f"- Resolution: {result.entity.resolution_confidence} ({result.entity.mapping_source})",
        "",
        "## Evidence Domains",
    ]
    for assessment in result.evidence_domains.values():
        lines.append(f"- {assessment.dimension}: {assessment.status}. {assessment.justification}")
    lines.extend(["", "## Unmet Requirements"])
    for requirement in result.evidence_conclusion.unmet_requirements:
        lines.append(f"- {requirement}")
    lines.extend(["", "## Literature", f"Query: `{result.literature_query}`"])
    for record in result.literature_records:
        lines.append(
            f"- PMID {record.pmid}: {record.title} ({record.publication_date}; {record.evidence_class}) {record.url}"
        )
    lines.extend(["", "## Limitations"])
    for limitation in result.limitations:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"


def write_external_outputs(result: ExternalEvidenceResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = result.model_dump(mode="json")
    markdown = render_markdown(result)
    (out_dir / "external_evidence.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "external_report.md").write_text(markdown, encoding="utf-8")
    (out_dir / "external_report.html").write_text(render_external_html(result), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assess biomarker evidence using external literature and public identity databases"
    )
    parser.add_argument("biomarker_id")
    parser.add_argument("--disease", required=True)
    parser.add_argument("--retmax", type=int, default=10)
    parser.add_argument("--email", help="Optional email passed to NCBI E-utilities")
    parser.add_argument("--out", type=Path, default=Path("reports/external"))
    add_context_arguments(parser)
    args = parser.parse_args()

    result = assess_external_evidence(
        args.biomarker_id,
        args.disease,
        retmax=args.retmax,
        email=args.email,
        context_of_use=context_from_args(args),
    )
    write_external_outputs(result, args.out)
    print(f"Evidence stage: {result.evidence_conclusion.stage}")
    print(f"Supported claim: {result.evidence_conclusion.supported_claim}")
    for assessment in result.evidence_domains.values():
        print(f"{assessment.dimension}: {assessment.status} - {assessment.justification}")
    print(f"Wrote {args.out / 'external_evidence.json'}")
    print(f"Wrote {args.out / 'external_report.md'}")
    print(f"Wrote {args.out / 'external_report.html'}")


if __name__ == "__main__":
    main()
