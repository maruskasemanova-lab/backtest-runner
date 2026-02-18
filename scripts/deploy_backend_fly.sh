#!/usr/bin/env bash
set -euo pipefail

if ! command -v flyctl >/dev/null 2>&1; then
  echo "flyctl is required. Install from https://fly.io/docs/flyctl/install/."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FLY_RUNNER_APP_NAME="${FLY_RUNNER_APP_NAME:-backtest-runner-api}"
FLY_PRIMARY_REGION="${FLY_PRIMARY_REGION:-iad}"
FLY_RUNNER_VOLUME_NAME="${FLY_RUNNER_VOLUME_NAME:-backtest_data}"
FLY_RUNNER_VOLUME_SIZE_GB="${FLY_RUNNER_VOLUME_SIZE_GB:-3}"

echo "Deploying runner app '${FLY_RUNNER_APP_NAME}' in region '${FLY_PRIMARY_REGION}'."

if ! flyctl apps show "${FLY_RUNNER_APP_NAME}" >/dev/null 2>&1; then
  flyctl apps create "${FLY_RUNNER_APP_NAME}"
fi

if ! flyctl volumes list --app "${FLY_RUNNER_APP_NAME}" 2>/dev/null | grep -Eq "(^|[[:space:]])${FLY_RUNNER_VOLUME_NAME}([[:space:]]|$)"; then
  flyctl volumes create "${FLY_RUNNER_VOLUME_NAME}" \
    --yes \
    --size "${FLY_RUNNER_VOLUME_SIZE_GB}" \
    --region "${FLY_PRIMARY_REGION}" \
    --app "${FLY_RUNNER_APP_NAME}"
fi

SECRET_PAIRS=()
for key in \
  BACKTEST_INTERNAL_STRATEGY_API_URL \
  BACKTEST_STRATEGY_API_ALLOWLIST \
  BACKTEST_CORS_ALLOW_ORIGINS \
  BACKTEST_CORS_ALLOW_ORIGIN_REGEX \
  BACKTEST_JWT_SECRET \
  SUPABASE_JWT_SECRET \
  DATABENTO_API_KEY \
  STRIPE_SECRET_KEY \
  STRIPE_WEBHOOK_SECRET \
  STRIPE_PREMIUM_PRICE_ID \
  BACKTEST_SUPABASE_USER_SETTINGS_ENABLED \
  BACKTEST_SUPABASE_URL \
  BACKTEST_SUPABASE_SERVICE_ROLE_KEY \
  BACKTEST_SUPABASE_PUBLISHABLE_KEY \
  BACKTEST_REMOTE_MANIFEST_URL \
  BACKTEST_AVAILABLE_DATA_REMOTE_ONLY \
  BACKTEST_REMOTE_MANIFEST_REQUIRED \
  BACKTEST_REMOTE_SYNC_MIN_INTERVAL_SEC \
  BACKTEST_L2_INCLUDE_ICEBERGS_IN_FEATURE_MAP \
  BACKTEST_DATA_CATALOG_PATH \
  BACKTEST_REMOTE_S3_ENDPOINT \
  BACKTEST_REMOTE_S3_ACCOUNT_ID \
  BACKTEST_REMOTE_S3_ACCESS_KEY_ID \
  BACKTEST_REMOTE_S3_SECRET_ACCESS_KEY \
  BACKTEST_REMOTE_S3_REGION \
  BACKTEST_STRATEGY_INTERNAL_API_TOKEN \
  STRATEGY_INTERNAL_API_TOKEN \
  BACKTEST_ALLOW_UNVERIFIED_JWT \
  BACKTEST_V2_WORKER_CONCURRENCY \
  BACKTEST_V2_MAX_QUEUE_BACKLOG \
  BACKTEST_V2_JOB_MAX_ATTEMPTS \
  BACKTEST_MAX_WS_CLIENTS
do
  value="${!key:-}"
  if [[ -n "${value}" ]]; then
    SECRET_PAIRS+=("${key}=${value}")
  fi
done

if (( ${#SECRET_PAIRS[@]} > 0 )); then
  flyctl secrets set --app "${FLY_RUNNER_APP_NAME}" "${SECRET_PAIRS[@]}"
fi

flyctl deploy "${REPO_ROOT}" \
  --config "${REPO_ROOT}/fly.toml" \
  --app "${FLY_RUNNER_APP_NAME}" \
  --primary-region "${FLY_PRIMARY_REGION}" \
  --remote-only

flyctl scale count 1 --yes --app "${FLY_RUNNER_APP_NAME}"

echo "Runner deployed: https://${FLY_RUNNER_APP_NAME}.fly.dev"
