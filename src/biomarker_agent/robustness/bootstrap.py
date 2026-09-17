from __future__ import annotations

import random

from biomarker_agent.datasets import CohortData
from biomarker_agent.schemas import RobustnessResult


def run_bootstrap_direction(cohort: CohortData, expression_values: dict[str, float | None], iterations: int = 200, seed: int = 202601) -> RobustnessResult:
    rng = random.Random(seed)
    tumor = []
    normal = []
    for row in cohort.metadata:
        value = expression_values.get(row["sample_id"])
        if value is None:
            continue
        if row.get("diagnosis", "").lower() == "tumor":
            tumor.append(value)
        elif row.get("diagnosis", "").lower() == "normal":
            normal.append(value)
    if not tumor or not normal:
        return RobustnessResult(cohort_name=cohort.config.name, bootstrap_iterations=iterations, diagnostic_direction_stability=None, sensitivity_notes=["diagnostic bootstrap was not evaluable"])
    observed_direction = 1 if (sum(tumor) / len(tumor)) >= (sum(normal) / len(normal)) else -1
    stable = 0
    for _ in range(iterations):
        tumor_sample = [rng.choice(tumor) for _ in tumor]
        normal_sample = [rng.choice(normal) for _ in normal]
        direction = 1 if (sum(tumor_sample) / len(tumor_sample)) >= (sum(normal_sample) / len(normal_sample)) else -1
        stable += direction == observed_direction
    return RobustnessResult(
        cohort_name=cohort.config.name,
        bootstrap_iterations=iterations,
        diagnostic_direction_stability=stable / iterations,
        sensitivity_notes=["fixed-seed nonparametric bootstrap of diagnostic direction"],
    )
