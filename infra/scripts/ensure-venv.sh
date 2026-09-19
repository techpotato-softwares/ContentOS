#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Syncing infra dependencies with uv"
uv sync

echo "==> infra venv ready"
