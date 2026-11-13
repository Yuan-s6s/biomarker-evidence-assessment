from __future__ import annotations

from typing import Literal

from biomarker_agent.schemas import EvidenceScore, ValidationResult


def grade_evidence(result: ValidationResult) -> tuple[dict[str, EvidenceScore], Literal["C", "D"]]:
    scores: dict[str, EvidenceScore] = {}
    scores["id_certainty"] = EvidenceScore(
        dimension="id_certainty",
        score=5 if result.entity.resolution_confidence == "unique" else 0,
        justification=f"Resolver confidence was {result.entity.resolution_confidence}.",
    )
    any_qc_fail = any(not qc.passed for qc in result.qc)
    scores["structural_data_quality"] = EvidenceScore(
        dimension="structural_data_quality",
        score=0 if any_qc_fail else 2 if any(qc.warnings for qc in result.qc) else 3,
        justification=(
            "Blocking structural data failures were present."
            if any_qc_fail
            else "Structural CSV checks passed; assay analytical validity was not assessed."
        ),
    )
    replication = result.evidence_domains.get("independent_replication")
    replication_score = (
        3
        if replication and replication.status == "supported"
        else 1
        if replication and replication.status == "partial"
        else 0
    )
    replication_justification = (
        replication.justification if replication else "Independent replication was not assessed."
    )
    scores["independent_replication"] = EvidenceScore(
        dimension="independent_replication", score=replication_score, justification=replication_justification
    )

    stabilities = [
        item.diagnostic_direction_stability
        for item in result.robustness.values()
        if item.diagnostic_direction_stability is not None
    ]
    min_stability = min(stabilities) if stabilities else 0.0
    scores["statistical_robustness"] = EvidenceScore(
        dimension="statistical_robustness",
        score=2 if min_stability >= 0.9 else 1 if min_stability >= 0.7 else 0,
        justification=(
            f"Minimum diagnostic sign-bootstrap stability was {min_stability:.2f}; this does not quantify model optimism."
        ),
    )
    deltas = [item.delta_c_index for item in result.clinical_utility.values() if item.delta_c_index is not None]
    best_delta = max(deltas) if deltas else 0.0
    scores["apparent_incremental_discrimination"] = EvidenceScore(
        dimension="apparent_incremental_discrimination",
        score=1 if best_delta > 0 else 0,
        justification=f"Best apparent delta C-index was {best_delta:.3f}; no clinical utility claim is supported.",
    )
    scores["analytical_validity"] = EvidenceScore(
        dimension="analytical_validity", score=0, justification="Assay analytical validity was not assessed."
    )
    scores["locked_external_model_validation"] = EvidenceScore(
        dimension="locked_external_model_validation",
        score=0,
        justification="No locked discovery model was applied unchanged to external data.",
    )
    scores["clinical_utility"] = EvidenceScore(
        dimension="clinical_utility",
        score=0,
        justification="Decision impact and prospective clinical utility were not assessed.",
    )

    grade: Literal["C", "D"] = "C" if result.evidence_conclusion.stage == "independent_association_replication" else "D"
    return scores, grade
