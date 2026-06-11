#!/usr/bin/env bash

set -euo pipefail

# Prefer project virtualenvs, then fallback to system python.
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
elif [[ -x "venv/bin/python" ]]; then
  PYTHON_BIN="venv/bin/python"
elif [[ -x "env/bin/python" ]]; then
  PYTHON_BIN="env/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi

exec "$PYTHON_BIN" -m pytest "$@"