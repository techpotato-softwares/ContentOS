#!/usr/bin/env bash
# Build web for CloudFront /app and optionally set VITE_API_URL.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/apps/web"

export VITE_BASE="${VITE_BASE:-/app/}"
if [[ -n "${VITE_API_URL:-}" ]]; then
  echo "==> Building web with base=$VITE_BASE api=$VITE_API_URL"
else
  echo "==> Building web with base=$VITE_BASE (VITE_API_URL empty)"
fi

npm ci
npm run build
