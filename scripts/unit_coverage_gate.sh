#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "${ROOT_DIR}/.venv/bin/python3" ]]; then
  PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python3" ]]; then
  PYTHON_BIN="${VIRTUAL_ENV}/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  echo "ERROR: could not find a usable python3 interpreter."
  exit 2
fi

cd "${ROOT_DIR}"

echo "Running unit tests with 100% coverage requirement..."
"${PYTHON_BIN}" -m pytest tests/unit \
  --cov=sim \
  --cov=safety \
  --cov=algorithms \
  --cov=persistence \
  --cov=api \
  --cov=specs \
  --cov-report=term-missing \
  --cov-fail-under=100
