from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "biomarker-validation-agent/0.1"


class ExternalSourceError(RuntimeError):
    pass


def get_json(base_url: str, params: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    url = f"{base_url}?{urlencode(params, doseq=True)}"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - exercised by integration/smoke against live network
        raise ExternalSourceError(f"Failed to retrieve {base_url}: {exc}") from exc
