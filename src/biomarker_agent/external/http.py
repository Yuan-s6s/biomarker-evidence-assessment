from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from biomarker_agent.version import __version__

USER_AGENT = f"biomarker-evidence-assessment/{__version__}"


class ExternalSourceError(RuntimeError):
    pass


def get_text(base_url: str, params: dict[str, Any], timeout: float = 30.0) -> str:
    url = f"{base_url}?{urlencode(params, doseq=True)}"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except Exception as exc:  # pragma: no cover - exercised by integration/smoke against live network
        raise ExternalSourceError(f"Failed to retrieve {base_url}: {exc}") from exc


def get_json(base_url: str, params: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    try:
        return json.loads(get_text(base_url, params, timeout=timeout))
    except (TypeError, ValueError) as exc:  # pragma: no cover - malformed upstream response
        raise ExternalSourceError(f"Failed to parse JSON from {base_url}: {exc}") from exc
