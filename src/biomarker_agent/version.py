from __future__ import annotations

import platform
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version

__version__ = "0.2.0"


def runtime_versions() -> dict[str, str]:
    """Return the runtime versions needed to reproduce an assessment."""
    versions = {"python": platform.python_version()}
    for label, distribution in {
        "numpy": "numpy",
        "pydantic": "pydantic",
        "pyyaml": "PyYAML",
    }.items():
        try:
            versions[label] = distribution_version(distribution)
        except PackageNotFoundError:
            versions[label] = "not-installed"
    return versions
