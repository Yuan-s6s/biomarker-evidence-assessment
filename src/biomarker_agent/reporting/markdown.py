from __future__ import annotations

import json
from pathlib import Path

from biomarker_agent.reporting.html import render_validation_html
from biomarker_agent.schemas import ValidationResult


def _dump_model(result: ValidationResult) -> dict:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return result.dict()


def render_markdown_report(result: ValidationResult) -> str:
    lines = [
        f"# Biomarker Evidence Assessment Report: {result.entity.hgnc_symbol or result.entity.query}",
        "",
        "## Entity Resolution",
        f"- Query: `{result.entity.query}`",
        f"- Resolution: {result.entity.resolution_confidence}",
        f"- HGNC symbol: {result.entity.hgnc_symbol}",
        f"- Ensembl gene ID: {result.entity.ensembl_gene_id}",
        f"- UniProt accession: {result.entity.uniprot_accession}",
        "",
        "## Assumptions",
    ]
    for key, value in result.question.get("assumptions", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## QC"])
    for qc in result.qc:
        status = "passed" if qc.passed else "blocked"
        lines.append(
            f"- {qc.cohort_name}: {status}; analyzable n={qc.analyzable_sample_count}; failures={qc.blocking_failures or 'none'}; warnings={qc.warnings or 'none'}"
        )
    lines.extend(["", "## Diagnostic Expression"])
    for diagnostic in result.analyses.diagnostic:
        lines.append(
            f"- {diagnostic.cohort_name}: mean difference={diagnostic.mean_difference:.3f} (95% CI {diagnostic.ci95[0]:.3f} to {diagnostic.ci95[1]:.3f}), AUC={diagnostic.auc:.3f}, direction={diagnostic.direction}"
        )
    lines.extend(["", "## Prognostic Association"])
    for prognostic in result.analyses.prognostic:
        biomarker_terms = [term for term in prognostic.terms if term.term == "biomarker_expression"]
        if biomarker_terms:
            term = biomarker_terms[0]
            lines.append(
                f"- {prognostic.cohort_name}: biomarker HR={term.hazard_ratio:.3f} (95% CI {term.ci95[0]:.3f} to {term.ci95[1]:.3f}), C-index={prognostic.concordance_index:.3f}"
            )
    lines.extend(["", "## Clinical Utility"])
    for utility in result.clinical_utility.values():
        lines.append(
            f"- {utility.cohort_name}: baseline C={utility.baseline_c_index}, augmented C={utility.augmented_c_index}, delta={utility.delta_c_index}; {utility.interpretation}"
        )
    lines.extend(["", "## Evidence Grades"])
    for score in result.evidence_scores.values():
        lines.append(f"- {score.dimension}: {score.score}/5. {score.justification}")
    lines.extend(["", f"Overall grade: **{result.overall_grade}**", "", "## Limitations"])
    for limitation in result.limitations:
        lines.append(f"- {limitation}")
    lines.extend(["", "## Recommended Next Validation"])
    for recommendation in result.recommended_next_validation:
        lines.append(f"- {recommendation}")
    return "\n".join(lines) + "\n"


def render_html_report(result: ValidationResult) -> str:
    return render_validation_html(result)


def write_outputs(result: ValidationResult, out_dir: Path) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "result.json"
    markdown_path = out_dir / "report.md"
    html_path = out_dir / "report.html"
    json_path.write_text(json.dumps(_dump_model(result), indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown_report(result), encoding="utf-8")
    html_path.write_text(render_html_report(result), encoding="utf-8")
    return json_path, markdown_path, html_path
