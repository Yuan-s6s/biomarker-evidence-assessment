from __future__ import annotations

from biomarker_agent.schemas import (
    BiomarkerCategory,
    BiomarkerEntity,
    ContextOfUse,
    EvidenceConclusion,
    EvidenceDomainAssessment,
    LiteratureRecord,
    LiteratureSearchSummary,
    ValidationRequest,
    ValidationResult,
)

CATEGORY_MAP: dict[str, BiomarkerCategory] = {
    "diagnostic": "diagnostic",
    "prognostic": "prognostic",
    "predictive": "predictive",
    "monitoring": "monitoring",
    "susceptibility_risk": "susceptibility_risk",
    "pharmacodynamic_response": "pharmacodynamic_response",
    "safety": "safety",
}


def missing_context_fields(context: ContextOfUse) -> list[str]:
    required = ["disease", "target_population", "clinical_setting", "specimen", "assay", "intended_action"]
    category_specific = {
        "diagnostic": ["reference_standard"],
        "prognostic": ["endpoint", "time_horizon", "baseline_comparator"],
        "predictive": ["endpoint", "time_horizon", "intervention", "baseline_comparator"],
        "monitoring": ["endpoint", "time_horizon"],
        "susceptibility_risk": ["endpoint", "time_horizon"],
        "pharmacodynamic_response": ["endpoint", "intervention"],
        "safety": ["endpoint", "intervention"],
        "unspecified": ["category"],
    }
    required.extend(category_specific[context.category])
    missing = []
    for field_name in required:
        value = context.category if field_name == "category" else getattr(context, field_name)
        if value in (None, "", "unspecified"):
            missing.append(field_name)
    return missing


def contexts_from_request(request: ValidationRequest) -> list[ContextOfUse]:
    if request.contexts_of_use:
        return request.contexts_of_use

    categories: list[BiomarkerCategory] = []
    for intended_use in request.intended_uses:
        category = CATEGORY_MAP.get(intended_use.strip().lower(), "unspecified")
        if category not in categories:
            categories.append(category)
    if not categories:
        categories.append("unspecified")

    contexts = []
    for category in categories:
        endpoint = (
            "disease_status"
            if category == "diagnostic"
            else request.endpoints[0]
            if len(request.endpoints) == 1
            else None
        )
        contexts.append(
            ContextOfUse(
                category=category,
                disease=request.disease,
                specimen=request.specimen,
                endpoint=endpoint,
            )
        )
    return contexts


def _context_domain(contexts: list[ContextOfUse]) -> EvidenceDomainAssessment:
    if not contexts:
        return EvidenceDomainAssessment(
            dimension="context_of_use",
            status="not_evaluated",
            justification="No context of use was supplied.",
        )
    missing_by_context = [
        (f"{context.category}[{index}]", fields)
        for index, context in enumerate(contexts, start=1)
        if (fields := missing_context_fields(context))
    ]
    if missing_by_context:
        details = "; ".join(f"{label}: {', '.join(fields)}" for label, fields in missing_by_context)
        return EvidenceDomainAssessment(
            dimension="context_of_use",
            status="partial",
            justification=f"The context of use is incomplete ({details}).",
        )
    return EvidenceDomainAssessment(
        dimension="context_of_use",
        status="supported",
        justification="All required context-of-use fields were supplied.",
    )


def build_external_framework(
    entity: BiomarkerEntity,
    context: ContextOfUse,
    literature_records: list[LiteratureRecord],
    literature_summary: LiteratureSearchSummary | None = None,
) -> tuple[dict[str, EvidenceDomainAssessment], EvidenceConclusion]:
    identity_supported = entity.resolution_confidence == "unique"
    summary = literature_summary or LiteratureSearchSummary(records_retrieved=len(literature_records))
    records_retrieved = bool(literature_records)
    literature_signal = summary.records_included > 0 or (
        records_retrieved and summary.records_screened == 0 and literature_summary is None
    )
    retrieval_failed = (summary.total_hits > 0 or bool(summary.retrieval_warnings)) and not records_retrieved
    if records_retrieved:
        retrieval_justification = (
            f"PubMed returned {summary.total_hits} hit(s); {summary.records_retrieved} were retrieved, "
            f"{summary.records_included} passed automated title/abstract screening, and "
            f"{summary.records_with_effect_estimates} contained rule-parsed same-sentence biomarker "
            "effect-and-95%-CI candidate(s). Full-text eligibility and extracted values were not verified."
        )
        if summary.retrieval_warnings:
            retrieval_justification += f" Pagination produced {len(summary.retrieval_warnings)} warning(s)."
    elif retrieval_failed:
        retrieval_justification = (
            f"PubMed retrieval failed or returned no usable records ({len(summary.retrieval_warnings)} warning(s))."
        )
    else:
        retrieval_justification = "No disease-related PubMed records were found."
    domains = {
        "identity": EvidenceDomainAssessment(
            dimension="identity",
            status="supported" if identity_supported else "concern",
            justification=(
                f"The submitted identifier resolved uniquely via {entity.mapping_source}."
                if identity_supported
                else f"Identifier resolution was {entity.resolution_confidence}."
            ),
        ),
        "context_of_use": _context_domain([context]),
        "literature_retrieval": EvidenceDomainAssessment(
            dimension="literature_retrieval",
            status="partial" if records_retrieved else "concern" if retrieval_failed else "not_evaluated",
            justification=retrieval_justification,
        ),
        "study_quality": EvidenceDomainAssessment(
            dimension="study_quality",
            status="not_evaluated",
            justification="No full-text eligibility assessment or risk-of-bias appraisal was performed.",
        ),
        "statistical_validation": EvidenceDomainAssessment(
            dimension="statistical_validation",
            status="not_evaluated",
            justification="No expression or outcome dataset was statistically reanalysed.",
        ),
        "analytical_validity": EvidenceDomainAssessment(
            dimension="analytical_validity",
            status="not_evaluated",
            justification="Assay precision, accuracy, specificity, and pre-analytical handling were not assessed.",
        ),
        "clinical_utility": EvidenceDomainAssessment(
            dimension="clinical_utility",
            status="not_evaluated",
            justification="No decision-impact or prospective utility evidence was assessed.",
        ),
    }

    if not identity_supported:
        conclusion = EvidenceConclusion(
            stage="not_assessed",
            supported_claim="No biomarker evidence claim is supported until the identifier is resolved.",
            unmet_requirements=["Resolve the biomarker to one biological entity."],
        )
    elif literature_signal:
        conclusion = EvidenceConclusion(
            stage="literature_signal",
            supported_claim=(
                "The biomarker identity was resolved and disease-related PubMed title/abstract records were found. "
                "Automated screening results, including any same-sentence abstract biomarker effect candidates, support a literature signal only, not a validated association."
            ),
            unmet_requirements=[
                "Verify study eligibility and every candidate effect estimate against full text and tables.",
                "Assess study-level risk of bias and duplicate cohorts.",
                "Reanalyse an independent, fit-for-purpose cohort.",
                "Document analytical validity of the measurement assay.",
            ],
        )
    else:
        conclusion = EvidenceConclusion(
            stage="identity_confirmed",
            supported_claim="The biomarker identity was resolved; no disease-specific evidence claim is supported.",
            unmet_requirements=[
                "Retrieve and appraise disease-specific studies.",
                "Provide a fit-for-purpose validation cohort.",
            ],
        )
    return domains, conclusion


def _prognostic_signal(result: ValidationResult, cohort_name: str) -> tuple[int, bool] | None:
    model = next((item for item in result.analyses.prognostic if item.cohort_name == cohort_name), None)
    if model is None:
        return None
    term = next((item for item in model.terms if item.term == "biomarker_expression"), None)
    if term is None or abs(term.coefficient) <= 1e-9:
        return None
    direction = 1 if term.coefficient > 0 else -1
    precise = term.ci95[0] > 1 or term.ci95[1] < 1
    return direction, precise


def _replication_domain(result: ValidationResult) -> tuple[EvidenceDomainAssessment, bool]:
    external = [dataset for dataset in result.datasets if dataset.get("role") == "external"]
    if not external:
        return (
            EvidenceDomainAssessment(
                dimension="independent_replication",
                status="not_evaluated",
                justification="No external cohort was supplied.",
            ),
            False,
        )

    target_disease = str(result.question.get("disease", "")).strip().casefold()
    qc_by_name = {item.cohort_name: item for item in result.qc}
    eligible = []
    missing_requirements: set[str] = set()
    for dataset in external:
        if dataset.get("independent_from_discovery") is not True:
            missing_requirements.add("cohort independence")
        if dataset.get("protocol_locked") is not True:
            missing_requirements.add("locked protocol")
        if not dataset.get("sample_size_justification"):
            missing_requirements.add("fit-for-purpose sample-size justification")
        dataset_disease = str(dataset.get("disease") or "").strip().casefold()
        if not dataset_disease or dataset_disease != target_disease:
            missing_requirements.add("disease-scope match")
        cohort_qc = qc_by_name.get(str(dataset.get("name")))
        has_precision_warning = bool(
            cohort_qc
            and any("imprecise" in warning.lower() or "unstable" in warning.lower() for warning in cohort_qc.warnings)
        )
        if has_precision_warning:
            missing_requirements.add("adequate observed precision")
        if (
            dataset.get("independent_from_discovery") is True
            and dataset.get("protocol_locked") is True
            and bool(dataset.get("sample_size_justification"))
            and dataset_disease == target_disease
            and not has_precision_warning
        ):
            eligible.append(dataset)
    if not eligible:
        missing = ", ".join(sorted(missing_requirements))
        return (
            EvidenceDomainAssessment(
                dimension="independent_replication",
                status="partial",
                justification=(
                    f"External association results were available, but replication gates were incomplete ({missing})."
                ),
            ),
            False,
        )

    discovery_name = next(
        (str(dataset.get("name")) for dataset in result.datasets if dataset.get("role") == "discovery"), ""
    )
    diagnostic_by_name = {item.cohort_name: item for item in result.analyses.diagnostic}
    discovery_diagnostic = diagnostic_by_name.get(discovery_name)
    discovery_prognostic = _prognostic_signal(result, discovery_name)
    comparisons: list[str] = []
    for dataset in eligible:
        name = str(dataset.get("name"))
        external_diagnostic = diagnostic_by_name.get(name)
        if discovery_diagnostic is not None and external_diagnostic is not None:
            if discovery_diagnostic.direction != external_diagnostic.direction:
                comparisons.append("conflicting")
            else:
                discovery_precise = discovery_diagnostic.ci95[0] > 0 or discovery_diagnostic.ci95[1] < 0
                external_precise = external_diagnostic.ci95[0] > 0 or external_diagnostic.ci95[1] < 0
                comparisons.append("supported" if discovery_precise and external_precise else "partial")
        external_prognostic = _prognostic_signal(result, name)
        if discovery_prognostic is not None and external_prognostic is not None:
            if discovery_prognostic[0] != external_prognostic[0]:
                comparisons.append("conflicting")
            else:
                comparisons.append("supported" if discovery_prognostic[1] and external_prognostic[1] else "partial")

    if not comparisons:
        return (
            EvidenceDomainAssessment(
                dimension="independent_replication",
                status="not_evaluated",
                justification="Eligible external cohorts were present, but no comparable association result was available.",
            ),
            False,
        )
    if "conflicting" in comparisons:
        return (
            EvidenceDomainAssessment(
                dimension="independent_replication",
                status="conflicting",
                justification="At least one eligible external association direction conflicted with discovery.",
            ),
            False,
        )
    if "supported" in comparisons:
        return (
            EvidenceDomainAssessment(
                dimension="independent_replication",
                status="supported",
                justification=(
                    "A concordant association with a confidence interval excluding the null was observed in an independent, disease-matched cohort with a locked protocol and documented sample-size justification."
                ),
            ),
            True,
        )
    return (
        EvidenceDomainAssessment(
            dimension="independent_replication",
            status="partial",
            justification="External association direction was concordant, but confidence intervals did not exclude the null.",
        ),
        False,
    )


def build_validation_framework(
    result: ValidationResult,
) -> tuple[dict[str, EvidenceDomainAssessment], EvidenceConclusion]:
    qc_passed = bool(result.qc) and all(item.passed for item in result.qc)
    qc_warnings = [warning for item in result.qc for warning in item.warnings]
    association_available = bool(result.analyses.diagnostic or result.analyses.prognostic)
    replication_domain, replication_supported = _replication_domain(result)
    domains = {
        "identity": EvidenceDomainAssessment(
            dimension="identity",
            status="supported" if result.entity.resolution_confidence == "unique" else "concern",
            justification=f"Identifier resolution was {result.entity.resolution_confidence}.",
        ),
        "context_of_use": _context_domain(result.contexts_of_use),
        "structural_data_quality": EvidenceDomainAssessment(
            dimension="structural_data_quality",
            status="partial" if qc_passed and qc_warnings else "supported" if qc_passed else "concern",
            justification=(
                f"Blocking checks passed with {len(qc_warnings)} warning(s)."
                if qc_passed and qc_warnings
                else "All blocking structural data checks passed."
                if qc_passed
                else "One or more structural data checks failed or were unavailable."
            ),
        ),
        "retrospective_association": EvidenceDomainAssessment(
            dimension="retrospective_association",
            status="supported" if association_available else "not_evaluated",
            justification=(
                "At least one retrospective diagnostic or prognostic association was estimated."
                if association_available
                else "No diagnostic or prognostic association was estimated."
            ),
        ),
        "independent_replication": replication_domain,
        "locked_external_model_validation": EvidenceDomainAssessment(
            dimension="locked_external_model_validation",
            status="not_evaluated",
            justification="Models were refitted per cohort; no locked discovery model was applied unchanged to external data.",
        ),
        "analytical_validity": EvidenceDomainAssessment(
            dimension="analytical_validity",
            status="not_evaluated",
            justification="CSV integrity checks do not establish assay analytical validity.",
        ),
        "clinical_utility": EvidenceDomainAssessment(
            dimension="clinical_utility",
            status="not_evaluated",
            justification="Apparent C-index differences do not establish decision impact or prospective clinical utility.",
        ),
    }

    if replication_supported:
        conclusion = EvidenceConclusion(
            stage="independent_association_replication",
            supported_claim=(
                "A retrospective association was observed with concordant direction in a documented independent cohort. "
                "No locked prediction model or clinical utility claim is supported."
            ),
            unmet_requirements=[
                "Apply a locked discovery model unchanged in a sufficiently sized external cohort.",
                "Evaluate calibration, discrimination, and decision-curve net benefit with confidence intervals.",
                "Document assay analytical validity.",
                "Perform prospective impact evaluation before clinical use.",
            ],
        )
    elif association_available:
        conclusion = EvidenceConclusion(
            stage="retrospective_association",
            supported_claim=(
                "A retrospective association was estimated in the supplied data. This does not establish external model validation or clinical utility."
            ),
            unmet_requirements=[
                "Confirm cohort independence and lock the validation protocol.",
                "Replicate effect estimates with confidence intervals in an external cohort.",
                "Document assay analytical validity.",
                "Evaluate a locked model and clinical net benefit.",
            ],
        )
    elif result.entity.resolution_confidence == "unique":
        conclusion = EvidenceConclusion(
            stage="identity_confirmed",
            supported_claim="The biomarker identity was resolved, but no association was evaluable.",
            unmet_requirements=["Provide a fit-for-purpose cohort that passes quality control."],
        )
    else:
        conclusion = EvidenceConclusion(
            stage="not_assessed",
            supported_claim="No evidence claim is supported.",
            unmet_requirements=["Resolve the biomarker identity and provide fit-for-purpose data."],
        )
    return domains, conclusion
