from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from biomarker_agent.evidence import missing_context_fields
from biomarker_agent.pipeline import run_validation
from biomarker_agent.reporting import write_outputs
from biomarker_agent.resolver import AmbiguousIdentifierError, OfflineResolver, UnresolvedIdentifierError
from biomarker_agent.schemas import (
    BiomarkerCategory,
    CohortConfig,
    ContextOfUse,
    DatasetConfig,
    EvidenceConclusion,
    EvidenceDomainAssessment,
    EvidenceScore,
    ValidationRequest,
)


def split_csv_answer(value: str, default: Iterable[str]) -> list[str]:
    cleaned = [item.strip() for item in value.split(",") if item.strip()]
    return cleaned or list(default)


def yes(value: str) -> bool:
    return value.strip().lower() in {"y", "yes", "true", "1"}


def _planning_contexts(disease: str, intended_uses: list[str]) -> list[ContextOfUse]:
    category_map: dict[str, BiomarkerCategory] = {
        "diagnostic": "diagnostic",
        "prognostic": "prognostic",
        "predictive": "predictive",
        "monitoring": "monitoring",
        "safety": "safety",
    }
    contexts = []
    for intended_use in intended_uses:
        category = category_map.get(intended_use.strip().lower(), "unspecified")
        contexts.append(
            ContextOfUse(
                category=category,
                disease=disease,
                endpoint="disease_status" if category == "diagnostic" else None,
            )
        )
    return contexts or [ContextOfUse(category="unspecified", disease=disease)]


def _planning_framework(
    contexts: list[ContextOfUse], *, identity_status: Literal["supported", "concern"], identity_justification: str
) -> tuple[dict, dict]:
    missing = sorted({field for context in contexts for field in missing_context_fields(context)})
    domains = {
        "identity": EvidenceDomainAssessment(
            dimension="identity",
            status=identity_status,
            justification=identity_justification,
        ),
        "context_of_use": EvidenceDomainAssessment(
            dimension="context_of_use",
            status="partial" if missing else "supported",
            justification=(
                f"Missing context fields: {', '.join(missing)}."
                if missing
                else "All required context-of-use fields were supplied."
            ),
        ),
        "statistical_validation": EvidenceDomainAssessment(
            dimension="statistical_validation",
            status="not_evaluated",
            justification="No cohort data were supplied.",
        ),
        "analytical_validity": EvidenceDomainAssessment(
            dimension="analytical_validity",
            status="not_evaluated",
            justification="No assay validation evidence was supplied.",
        ),
        "clinical_utility": EvidenceDomainAssessment(
            dimension="clinical_utility",
            status="not_evaluated",
            justification="No clinical decision-impact evidence was supplied.",
        ),
    }
    identity_supported = identity_status == "supported"
    conclusion = EvidenceConclusion(
        stage="identity_confirmed" if identity_supported else "not_assessed",
        supported_claim=(
            "The biomarker identity was resolved; no disease association or clinical claim was evaluated."
            if identity_supported
            else "No biomarker evidence claim is supported until the identifier is resolved."
        ),
        unmet_requirements=(
            [
                "Complete the context of use.",
                "Provide fit-for-purpose discovery and independent validation data.",
                "Document assay analytical validity.",
            ]
            if identity_supported
            else ["Resolve the biomarker to one biological entity."]
        ),
    )
    return (
        {key: value.model_dump(mode="json") for key, value in domains.items()},
        conclusion.model_dump(mode="json"),
    )


def build_request_from_answers(
    biomarker_id: str,
    disease: str,
    intended_uses: list[str],
    molecular_layers: list[str],
    endpoints: list[str],
    covariates: list[str],
    discovery_expression_path: Path,
    discovery_metadata_path: Path,
    external_expression_path: Path | None = None,
    external_metadata_path: Path | None = None,
) -> ValidationRequest:
    external = []
    if external_expression_path and external_metadata_path:
        external.append(
            CohortConfig(
                name="external",
                role="external",
                expression_path=external_expression_path,
                metadata_path=external_metadata_path,
                expression_layer="rna",
            )
        )
    return ValidationRequest(
        biomarker_id=biomarker_id,
        disease=disease,
        intended_uses=intended_uses,
        molecular_layers=molecular_layers,  # type: ignore[arg-type]
        specimen="tumor_tissue",
        endpoints=endpoints,
        covariates=covariates,
        analysis_mode="full_validation",
        datasets=DatasetConfig(
            discovery=CohortConfig(
                name="discovery",
                role="discovery",
                expression_path=discovery_expression_path,
                metadata_path=discovery_metadata_path,
                expression_layer="rna",
            ),
            external=external,
        ),
    )


def planning_confidence(biomarker_id: str, disease: str, intended_uses: list[str], molecular_layers: list[str]) -> dict:
    contexts = _planning_contexts(disease, intended_uses)
    try:
        entity = OfflineResolver().resolve(biomarker_id)
    except AmbiguousIdentifierError as exc:
        domains, conclusion = _planning_framework(
            contexts,
            identity_status="concern",
            identity_justification="The submitted identifier matched multiple offline candidates.",
        )
        return {
            "status": "needs_confirmation",
            "entity": exc.entity.model_dump(mode="json"),
            "contexts_of_use": [context.model_dump(mode="json") for context in contexts],
            "evidence_domains": domains,
            "evidence_conclusion": conclusion,
            "confidence": {
                "id_certainty": EvidenceScore(
                    dimension="id_certainty",
                    score=0,
                    justification="The submitted identifier matched multiple offline candidates.",
                ).model_dump(mode="json"),
                "data_availability": EvidenceScore(
                    dimension="data_availability", score=0, justification="No cohort data were supplied."
                ).model_dump(mode="json"),
            },
            "overall": "Cannot judge biomarker evidence until the identifier is confirmed and validation data are supplied.",
        }
    except UnresolvedIdentifierError as exc:
        domains, conclusion = _planning_framework(
            contexts,
            identity_status="concern",
            identity_justification="The offline resolver could not map the submitted identifier.",
        )
        return {
            "status": "unresolved",
            "entity": exc.entity.model_dump(mode="json"),
            "contexts_of_use": [context.model_dump(mode="json") for context in contexts],
            "evidence_domains": domains,
            "evidence_conclusion": conclusion,
            "confidence": {
                "id_certainty": EvidenceScore(
                    dimension="id_certainty",
                    score=0,
                    justification="The offline resolver could not map the submitted identifier.",
                ).model_dump(mode="json"),
                "data_availability": EvidenceScore(
                    dimension="data_availability", score=0, justification="No cohort data were supplied."
                ).model_dump(mode="json"),
            },
            "overall": "Cannot judge biomarker evidence until the identifier is resolved.",
        }

    layers = ", ".join(molecular_layers)
    domains, conclusion = _planning_framework(
        contexts,
        identity_status="supported",
        identity_justification="The offline resolver found a unique entity mapping.",
    )
    return {
        "status": "planning_only",
        "entity": entity.model_dump(mode="json"),
        "contexts_of_use": [context.model_dump(mode="json") for context in contexts],
        "evidence_domains": domains,
        "evidence_conclusion": conclusion,
        "question": {
            "disease": disease,
            "intended_uses": intended_uses,
            "molecular_layers": molecular_layers,
        },
        "confidence": {
            "id_certainty": EvidenceScore(
                dimension="id_certainty", score=5, justification="The offline resolver found a unique entity mapping."
            ).model_dump(mode="json"),
            "data_availability": EvidenceScore(
                dimension="data_availability",
                score=0,
                justification="No expression/survival cohort data were supplied, so no statistical validation was run.",
            ).model_dump(mode="json"),
            "direct_evidence": EvidenceScore(
                dimension="direct_evidence",
                score=0,
                justification=f"No local {layers} evidence was analysed for {disease or 'an unspecified disease'}.",
            ).model_dump(mode="json"),
            "clinical_utility": EvidenceScore(
                dimension="clinical_utility",
                score=0,
                justification="No baseline-vs-biomarker model comparison was possible without cohort data.",
            ).model_dump(mode="json"),
        },
        "overall": "ID confidence is high, but biomarker evidence confidence is insufficient because no validation data were supplied.",
        "next_questions": [
            "Do you have discovery expression and metadata CSV files?",
            "Is the intended claim diagnostic, prognostic, or both?",
            "Which endpoint and covariates should be prespecified before analysis?",
        ],
    }


def run_confidence_tool(request: ValidationRequest, out_dir: Path):
    result = run_validation(request)
    write_outputs(result, out_dir)
    return result
