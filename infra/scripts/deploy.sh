#!/usr/bin/env bash
# Synth/deploy ApiStack-{env}. Expects layer + web already built for deploy.
set -euo pipefail

ENV="${1:-dev}"
ACTION="${2:-deploy}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$ROOT/.." && pwd)"

cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ ! -d .venv ]]; then
  echo "==> Creating infra venv with $PYTHON_BIN"
  "$PYTHON_BIN" -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -U pip
  pip install -r requirements.txt
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

CDK_BIN=(npx --yes aws-cdk)
if command -v cdk >/dev/null 2>&1; then
  CDK_BIN=(cdk)
fi

export CDK_DEFAULT_ACCOUNT="${CDK_DEFAULT_ACCOUNT:-${AWS_ACCOUNT_ID:-}}"
export CDK_DEFAULT_REGION="${CDK_DEFAULT_REGION:-${AWS_REGION:-ap-south-1}}"

case "$ACTION" in
  synth) "${CDK_BIN[@]}" synth "ApiStack-$ENV" ;;
  deploy) "${CDK_BIN[@]}" deploy "ApiStack-$ENV" --require-approval never ;;
  diff) "${CDK_BIN[@]}" diff "ApiStack-$ENV" ;;
  destroy) "${CDK_BIN[@]}" destroy "ApiStack-$ENV" --force ;;
  bootstrap) "${CDK_BIN[@]}" bootstrap "aws://${CDK_DEFAULT_ACCOUNT}/${CDK_DEFAULT_REGION}" ;;
  *)
    echo "Usage: $0 [dev|qa|prod] [synth|deploy|diff|destroy|bootstrap]"
    exit 1
    ;;
esac
