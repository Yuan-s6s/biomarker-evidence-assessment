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
    scores["technical_reliability"] = EvidenceScore(
        dimension="technical_reliability",
        score=0 if any_qc_fail else 3 if any(qc.warnings for qc in result.qc) else 5,
        justification="Blocking QC failures were present." if any_qc_fail else "All blocking QC checks passed.",
    )
    diagnostic = result.analyses.diagnostic
    if len(diagnostic) >= 2:
        discovery_direction = diagnostic[0].direction
        concordant = all(item.direction == discovery_direction for item in diagnostic[1:])
        replication_score = 5 if concordant else 0
        replication_justification = (
            "External diagnostic direction was concordant with discovery."
            if concordant
            else "External diagnostic direction conflicted with discovery."
        )
    else:
        replication_score = 0
        replication_justification = "No external diagnostic analysis was available."
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
        score=5 if min_stability >= 0.9 else 3 if min_stability >= 0.7 else 0,
        justification=f"Minimum diagnostic bootstrap direction stability was {min_stability:.2f}.",
    )
    deltas = [item.delta_c_index for item in result.clinical_utility.values() if item.delta_c_index is not None]
    best_delta = max(deltas) if deltas else 0.0
    scores["incremental_clinical_value"] = EvidenceScore(
        dimension="incremental_clinical_value",
        score=5 if best_delta >= 0.05 else 3 if best_delta > 0 else 0,
        justification=f"Best apparent delta C-index was {best_delta:.3f}.",
    )
    scores["orthogonal_support"] = EvidenceScore(
        dimension="orthogonal_support", score=0, justification="No protein or orthogonal data were analysed in Phase 1."
    )
    scores["transportability"] = EvidenceScore(
        dimension="transportability",
        score=3 if len(result.datasets) > 1 else 0,
        justification="External local cohort was present."
        if len(result.datasets) > 1
        else "Only one cohort was present.",
    )

    if any(
        score.score == 0 for key, score in scores.items() if key in {"technical_reliability", "independent_replication"}
    ):
        grade: Literal["C", "D"] = "D"
    elif scores["statistical_robustness"].score >= 3 and scores["incremental_clinical_value"].score >= 3:
        grade = "C"
    else:
        grade = "D"
    return scores, grade
