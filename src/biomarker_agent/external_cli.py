from __future__ import annotations

import argparse
import json
from pathlib import Path

from biomarker_agent.external import assess_external_evidence
from biomarker_agent.reporting.html import render_external_html
from biomarker_agent.schemas import ExternalEvidenceResult


def render_markdown(result: ExternalEvidenceResult) -> str:
    lines = [
        f"# External Biomarker Evidence: {result.entity.hgnc_symbol or result.entity.query}",
        "",
        f"Disease: {result.disease}",
        f"Overall confidence: **{result.overall_confidence}**",
        "",
        "## Entity",
        f"- Query: `{result.entity.query}`",
        f"- Symbol: {result.entity.hgnc_symbol}",
        f"- Ensembl: {result.entity.ensembl_gene_id}",
        f"- Entrez: {result.entity.entrez_id}",
        f"- UniProt: {result.entity.uniprot_accession}",
        f"- Resolution: {result.entity.resolution_confidence} ({result.entity.mapping_source})",
        "",
        "## Scores",
    ]
    for score in result.evidence_scores.values():
        lines.append(f"- {score.dimension}: {score.score}/5. {score.justification}")
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
    parser.add_argument("--disease", default="LSCC")
    parser.add_argument("--retmax", type=int, default=10)
    parser.add_argument("--email", help="Optional email passed to NCBI E-utilities")
    parser.add_argument("--out", type=Path, default=Path("reports/external"))
    args = parser.parse_args()

    result = assess_external_evidence(args.biomarker_id, args.disease, retmax=args.retmax, email=args.email)
    write_external_outputs(result, args.out)
    print(f"Overall confidence: {result.overall_confidence}")
    for score in result.evidence_scores.values():
        print(f"{score.dimension}: {score.score}/5 - {score.justification}")
    print(f"Wrote {args.out / 'external_evidence.json'}")
    print(f"Wrote {args.out / 'external_report.md'}")
    print(f"Wrote {args.out / 'external_report.html'}")


if __name__ == "__main__":
    main()
