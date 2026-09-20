from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

from biomarker_agent.external import assess_external_evidence


def render_markdown(result) -> str:
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


def render_html(markdown: str) -> str:
    body = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            body.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            body.append(f"<li>{escape(line[2:])}</li>")
        elif line:
            body.append(f"<p>{escape(line)}</p>")
    return '<!doctype html>\n<html lang="en"><meta charset="utf-8"><body>\n' + "\n".join(body) + "\n</body></html>\n"


def write_external_outputs(result, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = result.model_dump(mode="json")
    markdown = render_markdown(result)
    (out_dir / "external_evidence.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "external_report.md").write_text(markdown, encoding="utf-8")
    (out_dir / "external_report.html").write_text(render_html(markdown), encoding="utf-8")


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
