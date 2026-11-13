from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from biomarker_agent.analyses import run_clinical_utility, run_diagnostic_analysis, run_prognostic_analysis
from biomarker_agent.datasets import load_cohort
from biomarker_agent.evidence import build_validation_framework, contexts_from_request, grade_evidence
from biomarker_agent.qc import run_qc
from biomarker_agent.resolver import OfflineResolver
from biomarker_agent.robustness import run_bootstrap_direction
from biomarker_agent.schemas import AnalysisBundle, ValidationRequest, ValidationResult


def load_request(path: Path) -> ValidationRequest:
    with path.open() as handle:
        payload = yaml.safe_load(handle)
    return ValidationRequest.model_validate(payload)


def _accepted_ids(entity) -> list[str]:
    return [
        value
        for value in [
            entity.hgnc_symbol,
            entity.ensembl_gene_id,
            entity.entrez_id,
            entity.uniprot_accession,
            *entity.aliases,
        ]
        if value
    ]


def _dataset_record(config) -> dict[str, Any]:
    return {
        "name": config.name,
        "role": config.role,
        "disease": config.disease,
        "source": config.source,
        "version": config.version,
        "expression_layer": config.expression_layer,
        "expression_path": str(config.expression_path),
        "metadata_path": str(config.metadata_path),
        "access_date": config.access_date,
        "independent_from_discovery": config.independent_from_discovery,
        "protocol_locked": config.protocol_locked,
        "sample_size_justification": config.sample_size_justification,
    }


def run_validation(request: ValidationRequest) -> ValidationResult:
    entity = OfflineResolver().resolve(request.biomarker_id)
    contexts_of_use = contexts_from_request(request)
    requested_categories = {context.category for context in contexts_of_use}
    run_diagnostic = "diagnostic" in requested_categories
    run_prognostic = any(
        context.category == "prognostic" and context.endpoint == "overall_survival" for context in contexts_of_use
    )
    cohorts = [request.datasets.discovery, *request.datasets.external]
    qc_results = []
    diagnostic_results = []
    prognostic_results = []
    robustness_results = {}
    clinical_utility = {}

    for config in cohorts:
        cohort = load_cohort(config)
        expression_values = cohort.biomarker_values(_accepted_ids(entity))
        qc = run_qc(
            cohort,
            expression_values,
            require_diagnostic=run_diagnostic,
            require_survival=run_prognostic,
        )
        qc_results.append(qc)
        if not qc.passed:
            continue
        if run_diagnostic:
            diagnostic_results.append(
                run_diagnostic_analysis(cohort, entity.hgnc_symbol or request.biomarker_id, expression_values)
            )
            robustness_results[config.name] = run_bootstrap_direction(cohort, expression_values)
        if run_prognostic:
            try:
                prognostic_results.append(
                    run_prognostic_analysis(
                        cohort, entity.hgnc_symbol or request.biomarker_id, expression_values, request.covariates
                    )
                )
            except ValueError as exc:
                qc.warnings.append(f"prognostic analysis was not evaluable: {exc}")
            clinical_utility[config.name] = run_clinical_utility(cohort, expression_values, request.covariates)

    result = ValidationResult(
        entity=entity,
        question={
            "disease": request.disease,
            "intended_uses": request.intended_uses,
            "molecular_layers": request.molecular_layers,
            "specimen": request.specimen,
            "endpoints": request.endpoints,
            "covariates": request.covariates,
            "assumptions": {
                "database_connections": "offline resolver only; no external biological databases queried",
                "expression_scale": "input matrices are analysis-ready and already normalised",
                "cutoff_policy": "continuous expression only; no cut-off selected",
                "model_validation": "models are refitted per cohort; no locked model validation is performed",
            },
        },
        datasets=[_dataset_record(config) for config in cohorts],
        qc=qc_results,
        analyses=AnalysisBundle(diagnostic=diagnostic_results, prognostic=prognostic_results),
        robustness=robustness_results,
        clinical_utility=clinical_utility,
        contexts_of_use=contexts_of_use,
        evidence_scores={},
        overall_grade="D",
        limitations=[
            "The current cohort workflow uses retrospective data only and cannot establish clinical validation.",
            "Cox modelling is a deterministic MVP implementation intended for small simulated datasets.",
            "No proportional-hazards test, spline non-linearity assessment, permutation test, or protein orthogonal validation is implemented yet.",
            "Reported baseline-versus-augmented C-index differences are apparent discrimination, not clinical utility.",
            "Structural CSV quality control does not establish assay analytical validity.",
        ],
        recommended_next_validation=[
            f"Add an independent {request.disease} cohort with locked preprocessing, model parameters, and covariates.",
            "Add protein-abundance data for RNA-protein concordance.",
            "Add calibration, decision-curve net benefit, missing-data sensitivity, and fit-for-purpose sample-size checks.",
        ],
        provenance=ValidationResult.now_provenance(),
    )
    domains, conclusion = build_validation_framework(result)
    result.evidence_domains = domains
    result.evidence_conclusion = conclusion
    scores, grade = grade_evidence(result)
    result.evidence_scores = scores
    result.overall_grade = grade
    return result
