#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${BIOMARKER_VENV:-${ROOT_DIR}/.venv}"
READY_FILE="${VENV_DIR}/.biomarker-assessment-ready"

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

find_python() {
  local candidate
  local candidates=(python3.12 python3.11 python3)

  if [[ -n "${BIOMARKER_PYTHON:-}" ]]; then
    candidates=("${BIOMARKER_PYTHON}")
  fi

  for candidate in "${candidates[@]}"; do
    if command -v "${candidate}" >/dev/null 2>&1 && \
      "${candidate}" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
      printf '%s' "${candidate}"
      return 0
    fi
  done

  return 1
}

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  PYTHON_BIN="$(find_python)" || \
    fail "Python 3.11 or newer was not found. Set BIOMARKER_PYTHON to its executable path."

  printf 'Creating local Python environment with %s at %s\n' "${PYTHON_BIN}" "${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' || \
  fail "The existing virtual environment uses Python older than 3.11. Remove .venv and run again."

if [[ ! -f "${READY_FILE}" || "${ROOT_DIR}/pyproject.toml" -nt "${READY_FILE}" ]] || \
  ! "${VENV_DIR}/bin/python" -c 'from biomarker_agent.assessment_cli import main' >/dev/null 2>&1; then
  printf 'Installing Biomarker Evidence Assessment Toolkit (first run only)\n'
  "${VENV_DIR}/bin/python" -m pip install -e "${ROOT_DIR}"
  touch "${READY_FILE}"
fi

cd "${ROOT_DIR}"

if [[ $# -eq 0 ]]; then
  printf 'Starting the guided assessment. Press Ctrl+C to exit.\n'
  set -- guided --out reports/confidence
elif [[ "$1" == "demo" ]]; then
  shift
  printf 'Running the bundled cohort example.\n'
  set -- cohort configs/example_request.yaml --out reports/example "$@"
fi

exec "${VENV_DIR}/bin/python" -m biomarker_agent.assessment_cli "$@"
