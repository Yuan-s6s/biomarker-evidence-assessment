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
        "## Evidence Conclusion",
        f"- Highest supported stage: **{result.evidence_conclusion.stage}**",
        f"- Supported claim: {result.evidence_conclusion.supported_claim}",
        "",
        "### Unmet Requirements",
    ]
    for requirement in result.evidence_conclusion.unmet_requirements:
        lines.append(f"- {requirement}")
    lines.extend(
        [
            "",
            "## Evidence Domains",
        ]
    )
    for assessment in result.evidence_domains.values():
        lines.append(f"- {assessment.dimension}: {assessment.status}. {assessment.justification}")
    lines.extend(
        [
            "",
            "## Context of Use",
        ]
    )
    for context in result.contexts_of_use:
        lines.append(
            f"- {context.category}: disease={context.disease}; population={context.target_population}; "
            f"setting={context.clinical_setting}; specimen={context.specimen}; assay={context.assay}; "
            f"endpoint={context.endpoint}; horizon={context.time_horizon}; "
            f"reference_standard={context.reference_standard}; intervention={context.intervention}; "
            f"baseline_comparator={context.baseline_comparator}; action={context.intended_action}"
        )
    lines.extend(
        [
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
    )
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
    lines.extend(["", "## Apparent Incremental Discrimination"])
    for utility in result.clinical_utility.values():
        lines.append(
            f"- {utility.cohort_name}: baseline C={utility.baseline_c_index}, augmented C={utility.augmented_c_index}, delta={utility.delta_c_index}; {utility.interpretation}"
        )
    lines.extend(["", "## Robustness"])
    for robustness in result.robustness.values():
        lines.append(
            f"- {robustness.cohort_name}: bootstrap iterations={robustness.bootstrap_iterations}; "
            f"random seed={robustness.random_seed}; direction stability={robustness.diagnostic_direction_stability}; "
            f"notes={robustness.sensitivity_notes}"
        )
    lines.extend(["", "## Legacy Heuristic Indicators"])
    for score in result.evidence_scores.values():
        lines.append(f"- {score.dimension}: {score.score}/5. {score.justification}")
    lines.extend(["", f"Legacy grade: **{result.overall_grade}**", "", "## Limitations"])
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
