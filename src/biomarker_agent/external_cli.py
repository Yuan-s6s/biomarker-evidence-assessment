from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from biomarker_agent.external import assess_external_evidence
from biomarker_agent.external.pubmed import DEFAULT_MAX_RECORDS, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from biomarker_agent.reporting.html import render_external_html
from biomarker_agent.reporting.summary import build_external_report_summary
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


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def _page_size(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= MAX_PAGE_SIZE:
        raise argparse.ArgumentTypeError(f"must be between 1 and {MAX_PAGE_SIZE}")
    return parsed


def add_literature_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-records",
        "--retmax",
        dest="retmax",
        type=_nonnegative_int,
        default=DEFAULT_MAX_RECORDS,
        metavar="N",
        help=(
            f"Maximum PubMed records to retrieve (default: {DEFAULT_MAX_RECORDS}); "
            "use 0 for all available records up to the 10,000-record ESearch limit"
        ),
    )
    parser.add_argument(
        "--page-size",
        type=_page_size,
        default=DEFAULT_PAGE_SIZE,
        metavar="N",
        help=f"PubMed EFetch page size (default: {DEFAULT_PAGE_SIZE}; range: 1-{MAX_PAGE_SIZE})",
    )
    parser.add_argument("--email", help="Optional email passed to NCBI E-utilities")


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
    flow = result.literature_summary
    summary = build_external_report_summary(result)
    lines = [
        f"# External Biomarker Evidence: {result.entity.hgnc_symbol or result.entity.query}",
        "",
        f"Disease: {result.disease}",
        f"Evidence stage: **{result.evidence_conclusion.stage}**",
        "",
        "## Assessment Summary",
        f"**Bottom line:** {summary.headline}",
        "",
        "### Key Findings",
        *[f"- {finding}" for finding in summary.key_findings],
        "",
        f"**Supported claim:** {summary.supported_claim}",
        "",
        f"**Interpretation boundary:** {summary.interpretation_boundary}",
    ]
    if summary.priority_next_steps:
        lines.extend(
            [
                "",
                "### Priority Next Steps",
                *[f"- {step}" for step in summary.priority_next_steps],
            ]
        )
    lines.extend(
        [
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
            "## Literature Flow",
            f"- Total PubMed hits: {flow.total_hits}",
            f"- Configured retrieval cap: {flow.retrieval_cap if flow.retrieval_cap is not None else 'all up to 10,000'}",
            f"- Page size: {flow.page_size}",
            f"- Pages fetched: {flow.pages_fetched}",
            f"- Records retrieved: {flow.records_retrieved}",
            f"- Records screened: {flow.records_screened}",
            f"- Automated title/abstract candidates included: {flow.records_included}",
            f"- Automated exclusions: {flow.records_excluded}",
            f"- Uncertain records: {flow.records_uncertain}",
            f"- Abstracts available: {flow.abstracts_available}",
            f"- Records with same-sentence biomarker effect-and-95%-CI candidates: {flow.records_with_effect_estimates}",
            f"- Effect candidates extracted: {flow.effect_estimates_extracted}",
            f"- Retrieval truncated: {flow.truncated}",
            f"- Retrieval warnings: {flow.retrieval_warnings or 'none'}",
            "",
            "## Evidence Domains",
        ]
    )
    for assessment in result.evidence_domains.values():
        lines.append(f"- {assessment.dimension}: {assessment.status}. {assessment.justification}")
    lines.extend(["", "## Unmet Requirements"])
    for requirement in result.evidence_conclusion.unmet_requirements:
        lines.append(f"- {requirement}")
    lines.extend(["", "## Literature", f"Query: `{result.literature_query}`"])
    for record in result.literature_records:
        estimates = ", ".join(
            f"{item.measure}={item.estimate} (95% CI {item.ci95[0]}-{item.ci95[1]})" for item in record.effect_estimates
        )
        screening_reasons = "; ".join(record.screening_reasons) or "none recorded"
        lines.append(
            f"- PMID {record.pmid}: {record.title} ({record.publication_date}; {record.evidence_class}; "
            f"screen={record.screening_decision}; screen basis={screening_reasons}; abstract={record.abstract_available}; "
            f"effect candidates={estimates or 'none'}) {record.url}"
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
    add_literature_arguments(parser)
    parser.add_argument("--out", type=Path, default=Path("reports/external"))
    add_context_arguments(parser)
    args = parser.parse_args()

    result = assess_external_evidence(
        args.biomarker_id,
        args.disease,
        retmax=args.retmax,
        email=args.email,
        context_of_use=context_from_args(args),
        page_size=args.page_size,
        api_key=os.environ.get("NCBI_API_KEY"),
    )
    write_external_outputs(result, args.out)
    print(f"Evidence stage: {result.evidence_conclusion.stage}")
    print(f"Supported claim: {result.evidence_conclusion.supported_claim}")
    for assessment in result.evidence_domains.values():
        print(f"{assessment.dimension}: {assessment.status} - {assessment.justification}")
    flow = result.literature_summary
    print(
        "Literature flow: "
        f"{flow.total_hits} total hits; {flow.records_retrieved} retrieved; "
        f"{flow.records_included} automated-screen candidates; "
        f"{flow.records_with_effect_estimates} with same-sentence biomarker effect-and-95%-CI candidates"
    )
    print(f"Wrote {args.out / 'external_evidence.json'}")
    print(f"Wrote {args.out / 'external_report.md'}")
    print(f"Wrote {args.out / 'external_report.html'}")


if __name__ == "__main__":
    main()
