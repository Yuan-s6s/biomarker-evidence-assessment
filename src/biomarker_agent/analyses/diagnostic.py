from __future__ import annotations

from math import erf, sqrt

from biomarker_agent.datasets import CohortData
from biomarker_agent.schemas import DiagnosticResult


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _sample_var(values: list[float]) -> float:
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def _normal_two_sided_p(z: float) -> float:
    cdf = 0.5 * (1.0 + erf(abs(z) / sqrt(2.0)))
    return max(0.0, min(1.0, 2.0 * (1.0 - cdf)))


def _auc(tumor: list[float], normal: list[float]) -> float:
    wins = 0.0
    total = len(tumor) * len(normal)
    for t_value in tumor:
        for n_value in normal:
            if t_value > n_value:
                wins += 1.0
            elif t_value == n_value:
                wins += 0.5
    return wins / total


def run_diagnostic_analysis(cohort: CohortData, biomarker: str, expression_values: dict[str, float | None]) -> DiagnosticResult:
    tumor: list[float] = []
    normal: list[float] = []
    for row in cohort.metadata:
        sample_id = row["sample_id"]
        value = expression_values.get(sample_id)
        if value is None:
            continue
        if row.get("diagnosis", "").lower() == "tumor":
            tumor.append(value)
        elif row.get("diagnosis", "").lower() == "normal":
            normal.append(value)

    tumor_mean = _mean(tumor)
    normal_mean = _mean(normal)
    difference = tumor_mean - normal_mean
    se = sqrt(_sample_var(tumor) / len(tumor) + _sample_var(normal) / len(normal))
    statistic = difference / se if se else 0.0
    ci = (difference - 1.96 * se, difference + 1.96 * se)
    if difference > 1e-9:
        direction = "higher_in_tumor"
    elif difference < -1e-9:
        direction = "lower_in_tumor"
    else:
        direction = "no_difference"
    return DiagnosticResult(
        cohort_name=cohort.config.name,
        biomarker=biomarker,
        tumor_n=len(tumor),
        normal_n=len(normal),
        tumor_mean=tumor_mean,
        normal_mean=normal_mean,
        mean_difference=difference,
        ci95=ci,
        test_statistic=statistic,
        p_value=_normal_two_sided_p(statistic),
        auc=_auc(tumor, normal),
        direction=direction,
    )
