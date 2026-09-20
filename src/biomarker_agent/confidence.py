from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from biomarker_agent.pipeline import run_validation
from biomarker_agent.reporting import write_outputs
from biomarker_agent.resolver import AmbiguousIdentifierError, OfflineResolver, UnresolvedIdentifierError
from biomarker_agent.schemas import CohortConfig, DatasetConfig, EvidenceScore, ValidationRequest


def split_csv_answer(value: str, default: Iterable[str]) -> list[str]:
    cleaned = [item.strip() for item in value.split(",") if item.strip()]
    return cleaned or list(default)


def yes(value: str) -> bool:
    return value.strip().lower() in {"y", "yes", "true", "1"}


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
        disease=disease or "LSCC",
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
    try:
        entity = OfflineResolver().resolve(biomarker_id)
    except AmbiguousIdentifierError as exc:
        return {
            "status": "needs_confirmation",
            "entity": exc.entity.model_dump(mode="json"),
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
        return {
            "status": "unresolved",
            "entity": exc.entity.model_dump(mode="json"),
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
    return {
        "status": "planning_only",
        "entity": entity.model_dump(mode="json"),
        "question": {
            "disease": disease or "LSCC",
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
                justification=f"No local {layers} evidence was analysed for {disease or 'LSCC'}.",
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
