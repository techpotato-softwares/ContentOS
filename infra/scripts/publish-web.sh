#!/usr/bin/env bash
# After CDK deploy: rebuild SPA with API URL and sync to s3://bucket/app/
set -euo pipefail

ENV="${1:?env required (qa|prod|dev)}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STACK="ApiStack-$ENV"
REGION="${AWS_REGION:-${CDK_DEFAULT_REGION:-ap-south-1}}"

cfn_out() {
  local export_name="$1"
  aws cloudformation describe-stacks \
    --stack-name "$STACK" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?ExportName=='${export_name}'].OutputValue" \
    --output text
}

API_URL="$(cfn_out "ContentOSApiUrl-$ENV")"
BUCKET="$(cfn_out "ContentOS-UI-BucketName-$ENV")"
DIST_ID="$(cfn_out "ContentOS-UI-DistributionId-$ENV")"
APP_URL="$(cfn_out "ContentOS-App-URL-$ENV")"
SITE_URL="$(cfn_out "ContentOS-UI-URL-$ENV")"

if [[ -z "$API_URL" || "$API_URL" == "None" ]]; then
  echo "ERROR: Could not resolve ContentOSApiUrl-$ENV from stack $STACK"
  exit 1
fi

echo "==> API: $API_URL"
echo "==> App: $APP_URL"
echo "==> Marketing: $SITE_URL"
echo "==> Bucket: $BUCKET  Distribution: $DIST_ID"

export VITE_BASE=/app/
export VITE_API_URL="$API_URL"
"$ROOT/infra/scripts/build-web.sh"

aws s3 sync "$ROOT/apps/web/dist" "s3://${BUCKET}/app/" --delete --region "$REGION"
aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/app/*" \
  --region "$REGION" >/dev/null

echo "==> Synced /app and invalidated CloudFront"
echo "Marketing: $SITE_URL"
echo "Application: $APP_URL"
