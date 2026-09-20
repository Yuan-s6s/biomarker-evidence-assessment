from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from biomarker_agent.analyses import run_clinical_utility, run_diagnostic_analysis, run_prognostic_analysis
from biomarker_agent.datasets import load_cohort
from biomarker_agent.evidence import grade_evidence
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
        "source": config.source,
        "version": config.version,
        "expression_layer": config.expression_layer,
        "expression_path": str(config.expression_path),
        "metadata_path": str(config.metadata_path),
        "access_date": config.access_date,
    }


def run_validation(request: ValidationRequest) -> ValidationResult:
    entity = OfflineResolver().resolve(request.biomarker_id)
    cohorts = [request.datasets.discovery, *request.datasets.external]
    qc_results = []
    diagnostic_results = []
    prognostic_results = []
    robustness_results = {}
    clinical_utility = {}

    for config in cohorts:
        cohort = load_cohort(config)
        expression_values = cohort.biomarker_values(_accepted_ids(entity))
        qc = run_qc(cohort, expression_values)
        qc_results.append(qc)
        if not qc.passed:
            continue
        diagnostic_results.append(
            run_diagnostic_analysis(cohort, entity.hgnc_symbol or request.biomarker_id, expression_values)
        )
        if "overall_survival" in request.endpoints:
            prognostic_results.append(
                run_prognostic_analysis(
                    cohort, entity.hgnc_symbol or request.biomarker_id, expression_values, request.covariates
                )
            )
            clinical_utility[config.name] = run_clinical_utility(cohort, expression_values, request.covariates)
        robustness_results[config.name] = run_bootstrap_direction(cohort, expression_values)

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
            },
        },
        datasets=[_dataset_record(config) for config in cohorts],
        qc=qc_results,
        analyses=AnalysisBundle(diagnostic=diagnostic_results, prognostic=prognostic_results),
        robustness=robustness_results,
        clinical_utility=clinical_utility,
        evidence_scores={},
        overall_grade="D",
        limitations=[
            "Phase 1 uses local retrospective cohorts only and cannot establish clinical validation.",
            "Cox modelling is a deterministic MVP implementation intended for small simulated datasets.",
            "No proportional-hazards test, spline non-linearity assessment, permutation test, or protein orthogonal validation is implemented yet.",
        ],
        recommended_next_validation=[
            "Add an independent public LSCC/HNSCC cohort with locked preprocessing and covariates.",
            "Add protein-abundance data for RNA-protein concordance.",
            "Extend robustness analyses to permutation and missing-data sensitivity.",
        ],
        provenance=ValidationResult.now_provenance(),
    )
    scores, grade = grade_evidence(result)
    result.evidence_scores = scores
    result.overall_grade = grade
    return result
