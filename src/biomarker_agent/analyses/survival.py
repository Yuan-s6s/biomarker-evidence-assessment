from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Any

import numpy as np

from biomarker_agent.datasets import CohortData
from biomarker_agent.schemas import ClinicalUtilityResult, CoxTerm, PrognosticResult

MAX_LOG_HR = 50.0


@dataclass
class CoxFit:
    terms: list[str]
    coefficients: np.ndarray
    standard_errors: np.ndarray
    log_likelihood: float
    risk_scores: np.ndarray
    warnings: list[str]


def _encode_rows(
    cohort: CohortData, expression_values: dict[str, float | None], covariates: list[str], include_biomarker: bool
) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
    rows: list[dict[str, Any]] = []
    for row in cohort.metadata:
        sample_id = row["sample_id"]
        expr = expression_values.get(sample_id)
        if expr is None or row.get("survival_time") in (None, "") or row.get("event") in (None, ""):
            continue
        clean = dict(row)
        clean["biomarker_expression"] = expr
        rows.append(clean)

    encoded_columns: dict[str, list[float]] = {}
    if include_biomarker:
        encoded_columns["biomarker_expression"] = [float(row["biomarker_expression"]) for row in rows]
    for covariate in covariates:
        values = [row.get(covariate, "") for row in rows]
        numeric = True
        numeric_values: list[float] = []
        for value in values:
            try:
                numeric_values.append(float(value))
            except (TypeError, ValueError):
                numeric = False
                break
        if numeric:
            encoded_columns[covariate] = numeric_values
        else:
            levels = sorted({str(value) for value in values if value != ""})
            for level in levels[1:]:
                encoded_columns[f"{covariate}={level}"] = [
                    1.0 if str(row.get(covariate, "")) == level else 0.0 for row in rows
                ]

    terms = list(encoded_columns)
    x = np.asarray([encoded_columns[term] for term in terms], dtype=float).T
    times = np.asarray([float(row["survival_time"]) for row in rows], dtype=float)
    events = np.asarray([int(float(row["event"])) for row in rows], dtype=int)
    return terms, x, times, events


def _standardize(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if x.size == 0:
        return x, np.asarray([]), np.asarray([])
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    scales[scales == 0] = 1.0
    return (x - means) / scales, means, scales


def _loglik_gradient_hessian(
    beta: np.ndarray, x: np.ndarray, times: np.ndarray, events: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray]:
    p = len(beta)
    loglik = 0.0
    gradient = np.zeros(p)
    hessian = np.zeros((p, p))
    scores = x @ beta
    for idx in np.where(events == 1)[0]:
        risk = times >= times[idx]
        risk_scores = np.exp(scores[risk] - np.max(scores[risk]))
        risk_x = x[risk]
        denom = risk_scores.sum()
        weighted_mean = (risk_scores[:, None] * risk_x).sum(axis=0) / denom
        centered = risk_x - weighted_mean
        weighted_cov = (risk_scores[:, None, None] * np.einsum("ij,ik->ijk", centered, centered)).sum(axis=0) / denom
        loglik += scores[idx] - (log(denom) + np.max(scores[risk]))
        gradient += x[idx] - weighted_mean
        hessian -= weighted_cov
    return loglik, gradient, hessian


def fit_cox_model(
    cohort: CohortData, expression_values: dict[str, float | None], covariates: list[str], include_biomarker: bool
) -> CoxFit:
    terms, x, times, events = _encode_rows(cohort, expression_values, covariates, include_biomarker)
    warnings: list[str] = []
    if len(times) < 4 or int(events.sum()) < 2 or not terms:
        raise ValueError("Cox model requires at least four samples, two events, and one predictor")
    x_std, _, scales = _standardize(x)
    beta = np.zeros(x_std.shape[1])
    ridge = 1e-6
    loglik = float("nan")
    for _ in range(50):
        loglik, gradient, hessian = _loglik_gradient_hessian(beta, x_std, times, events)
        penalized_hessian = hessian - np.eye(len(beta)) * ridge
        try:
            step = np.linalg.solve(penalized_hessian, gradient)
        except np.linalg.LinAlgError:
            warnings.append("Cox Hessian was singular; used pseudo-inverse")
            step = np.linalg.pinv(penalized_hessian) @ gradient
        beta_next = beta - step
        if np.max(np.abs(beta_next - beta)) < 1e-7:
            beta = beta_next
            break
        beta = beta_next

    _, _, hessian = _loglik_gradient_hessian(beta, x_std, times, events)
    try:
        covariance = np.linalg.inv(-hessian + np.eye(len(beta)) * ridge)
    except np.linalg.LinAlgError:
        covariance = np.linalg.pinv(-hessian + np.eye(len(beta)) * ridge)
        warnings.append("Cox covariance used pseudo-inverse")
    beta_original = beta / scales
    se_original = np.sqrt(np.diag(covariance)) / scales
    if np.any(np.abs(beta_original) > MAX_LOG_HR):
        warnings.append("Cox coefficient exceeded reporting bounds, consistent with sparse data or separation")
    return CoxFit(
        terms=terms,
        coefficients=beta_original,
        standard_errors=se_original,
        log_likelihood=loglik,
        risk_scores=x @ beta_original,
        warnings=warnings,
    )


def _safe_exp(value: float) -> float:
    return float(exp(max(min(value, MAX_LOG_HR), -MAX_LOG_HR)))


def concordance_index(times: np.ndarray, events: np.ndarray, risk_scores: np.ndarray) -> float:
    concordant = 0.0
    comparable = 0.0
    for i in range(len(times)):
        for j in range(i + 1, len(times)):
            if times[i] == times[j]:
                continue
            if times[i] < times[j] and events[i] == 1:
                comparable += 1
                concordant += (
                    1.0 if risk_scores[i] > risk_scores[j] else 0.5 if risk_scores[i] == risk_scores[j] else 0.0
                )
            elif times[j] < times[i] and events[j] == 1:
                comparable += 1
                concordant += (
                    1.0 if risk_scores[j] > risk_scores[i] else 0.5 if risk_scores[i] == risk_scores[j] else 0.0
                )
    return concordant / comparable if comparable else float("nan")


def run_prognostic_analysis(
    cohort: CohortData, biomarker: str, expression_values: dict[str, float | None], covariates: list[str]
) -> PrognosticResult:
    fit = fit_cox_model(cohort, expression_values, covariates, include_biomarker=True)
    _, _, times, events = _encode_rows(cohort, expression_values, covariates, include_biomarker=True)
    terms = []
    for term, coef, se in zip(fit.terms, fit.coefficients, fit.standard_errors):
        terms.append(
            CoxTerm(
                term=term,
                coefficient=float(coef),
                hazard_ratio=_safe_exp(float(coef)),
                standard_error=float(se),
                ci95=(_safe_exp(float(coef - 1.96 * se)), _safe_exp(float(coef + 1.96 * se))),
            )
        )
    return PrognosticResult(
        cohort_name=cohort.config.name,
        biomarker=biomarker,
        n=len(times),
        event_count=int(events.sum()),
        terms=terms,
        log_likelihood=float(fit.log_likelihood),
        concordance_index=float(concordance_index(times, events, fit.risk_scores)),
        warnings=fit.warnings,
    )


def run_clinical_utility(
    cohort: CohortData, expression_values: dict[str, float | None], covariates: list[str]
) -> ClinicalUtilityResult:
    try:
        _, _, times, events = _encode_rows(cohort, expression_values, covariates, include_biomarker=True)
        augmented = fit_cox_model(cohort, expression_values, covariates, include_biomarker=True)
        augmented_c = float(concordance_index(times, events, augmented.risk_scores))
        if covariates:
            baseline = fit_cox_model(cohort, expression_values, covariates, include_biomarker=False)
            baseline_c = float(concordance_index(times, events, baseline.risk_scores))
        else:
            baseline_c = None
        delta = None if baseline_c is None else augmented_c - baseline_c
        interpretation = (
            "baseline unavailable; no prespecified covariates"
            if baseline_c is None
            else "biomarker improved apparent concordance"
            if delta and delta > 0
            else "no apparent concordance improvement"
        )
        return ClinicalUtilityResult(
            cohort_name=cohort.config.name,
            baseline_c_index=baseline_c,
            augmented_c_index=augmented_c,
            delta_c_index=delta,
            interpretation=interpretation,
        )
    except ValueError as exc:
        return ClinicalUtilityResult(
            cohort_name=cohort.config.name,
            baseline_c_index=None,
            augmented_c_index=None,
            delta_c_index=None,
            interpretation=str(exc),
        )
