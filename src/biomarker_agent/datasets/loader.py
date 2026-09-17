from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from biomarker_agent.schemas import CohortConfig


@dataclass
class CohortData:
    config: CohortConfig
    metadata: list[dict[str, Any]]
    expression: dict[str, dict[str, float | None]]

    def biomarker_values(self, accepted_ids: list[str]) -> dict[str, float | None]:
        for entity_id in accepted_ids:
            if entity_id in self.expression:
                return self.expression[entity_id]
        available = ", ".join(sorted(self.expression))
        raise KeyError(f"No expression column found for any of {accepted_ids}; available: {available}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _to_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_cohort(config: CohortConfig) -> CohortData:
    metadata = _read_csv(config.metadata_path)
    rows = _read_csv(config.expression_path)
    if not rows:
        return CohortData(config=config, metadata=metadata, expression={})

    expression: dict[str, dict[str, float | None]] = {}
    columns = [column for column in rows[0] if column != "sample_id"]
    for column in columns:
        expression[column] = {}
    for row in rows:
        sample_id = row["sample_id"]
        for column in columns:
            expression[column][sample_id] = _to_float(row.get(column))
    return CohortData(config=config, metadata=metadata, expression=expression)
