#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN=python3
for candidate in python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done

ver="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
major="${ver%%.*}"
minor="${ver#*.}"
if [[ "$major" -lt 3 || ( "$major" -eq 3 && "$minor" -lt 10 ) ]]; then
  echo "ERROR: aws-cdk-lib needs Python >= 3.10 (found $PYTHON_BIN $ver)."
  echo "Install with: brew install python@3.12"
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "==> Creating infra/.venv with $PYTHON_BIN ($ver)"
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
echo "==> infra venv ready ($PYTHON_BIN)"
