#!/usr/bin/env bash
# Build layer + synth/deploy ApiStack-{env}
set -euo pipefail
ENV="${1:-dev}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="$(cd "$ROOT/../api" && pwd)"

echo "==> Building Python Lambda layer"
python3 "$API/layers/shared/python/scripts/build_layer.py"

cd "$ROOT"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

ACTION="${2:-deploy}"
case "$ACTION" in
  synth) cdk synth "ApiStack-$ENV" ;;
  deploy) cdk deploy "ApiStack-$ENV" --require-approval never ;;
  diff) cdk diff "ApiStack-$ENV" ;;
  destroy) cdk destroy "ApiStack-$ENV" ;;
  *) echo "Usage: $0 [dev|qa|prod] [synth|deploy|diff|destroy]"; exit 1 ;;
esac
