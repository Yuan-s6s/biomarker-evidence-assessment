from __future__ import annotations

from biomarker_agent.datasets import CohortData
from biomarker_agent.schemas import QCResult


def run_qc(
    cohort: CohortData,
    expression_values: dict[str, float | None],
    *,
    require_diagnostic: bool = True,
    require_survival: bool = False,
) -> QCResult:
    failures: list[str] = []
    warnings: list[str] = []

    sample_ids = [row.get("sample_id", "") for row in cohort.metadata]
    duplicate_samples = sorted({sample_id for sample_id in sample_ids if sample_ids.count(sample_id) > 1})
    if duplicate_samples:
        failures.append(f"duplicate metadata sample IDs: {', '.join(duplicate_samples)}")

    expression_samples = set(expression_values)
    metadata_samples = set(sample_ids)
    if missing_meta := sorted(expression_samples - metadata_samples):
        failures.append(f"expression samples missing metadata: {', '.join(missing_meta)}")
    if missing_expr := sorted(metadata_samples - expression_samples):
        failures.append(f"metadata samples missing expression: {', '.join(missing_expr)}")

    analyzable = [
        row
        for row in cohort.metadata
        if row.get("sample_id") in expression_values and expression_values[row["sample_id"]] is not None
    ]
    missing_expression_count = sum(1 for value in expression_values.values() if value is None)
    if missing_expression_count:
        warnings.append(f"{missing_expression_count} samples have missing biomarker expression")

    tumor_count = sum(1 for row in analyzable if row.get("diagnosis", "").lower() == "tumor")
    normal_count = sum(1 for row in analyzable if row.get("diagnosis", "").lower() == "normal")
    if require_diagnostic and (tumor_count < 2 or normal_count < 2):
        failures.append("diagnostic analysis requires at least two tumour and two normal samples")
    elif require_diagnostic and (tumor_count < 20 or normal_count < 20):
        warnings.append("fewer than 20 samples in at least one diagnostic group; estimates will be imprecise")

    event_count = 0
    survival_rows = 0
    for row in analyzable:
        time = row.get("survival_time")
        event = row.get("event")
        if time not in (None, "") or event not in (None, ""):
            survival_rows += 1
            if time in (None, "") or event in (None, ""):
                failures.append(f"missing survival field for sample {row.get('sample_id')}")
                continue
            try:
                time_value = float(str(time))
                event_value = int(float(str(event)))
            except (TypeError, ValueError):
                failures.append(f"invalid survival fields for sample {row.get('sample_id')}")
                continue
            if time_value <= 0:
                failures.append(f"non-positive survival time for sample {row.get('sample_id')}")
            if event_value not in {0, 1}:
                failures.append(f"event must be 0 or 1 for sample {row.get('sample_id')}")
            event_count += event_value == 1
    if require_survival and not survival_rows:
        failures.append("prognostic analysis requires survival_time and event data")
    elif require_survival and event_count < 2:
        failures.append("prognostic analysis requires at least two survival events")
    elif survival_rows and event_count < 10:
        warnings.append("fewer than ten survival events; prognostic estimates will be highly unstable")

    return QCResult(
        cohort_name=cohort.config.name,
        passed=not failures,
        blocking_failures=failures,
        warnings=warnings,
        sample_count=len(cohort.metadata),
        analyzable_sample_count=len(analyzable),
        tumor_count=tumor_count,
        normal_count=normal_count,
        event_count=int(event_count),
        missing_expression_count=missing_expression_count,
    )
