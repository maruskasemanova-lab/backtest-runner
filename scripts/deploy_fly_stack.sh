#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FLY_RUNNER_APP_NAME="${FLY_RUNNER_APP_NAME:-backtest-runner-api}"
FLY_STRATEGY_APP_NAME="${FLY_STRATEGY_APP_NAME:-market-regime-strategy-api}"

if [[ -z "${BACKTEST_INTERNAL_STRATEGY_API_URL:-}" ]]; then
  export BACKTEST_INTERNAL_STRATEGY_API_URL="https://${FLY_STRATEGY_APP_NAME}.fly.dev"
fi
if [[ -z "${BACKTEST_STRATEGY_API_ALLOWLIST:-}" ]]; then
  export BACKTEST_STRATEGY_API_ALLOWLIST="${BACKTEST_INTERNAL_STRATEGY_API_URL}"
fi
if [[ -z "${STRATEGY_CORS_ALLOW_ORIGINS:-}" && -n "${BACKTEST_CORS_ALLOW_ORIGINS:-}" ]]; then
  export STRATEGY_CORS_ALLOW_ORIGINS="${BACKTEST_CORS_ALLOW_ORIGINS}"
fi

"${REPO_ROOT}/scripts/deploy_strategy_fly.sh"
"${REPO_ROOT}/scripts/deploy_backend_fly.sh"

runner_url="https://${FLY_RUNNER_APP_NAME}.fly.dev"
strategy_url="https://${FLY_STRATEGY_APP_NAME}.fly.dev"

echo
echo "Fly stack deployed."
echo "Runner URL:   ${runner_url}"
echo "Strategy URL: ${strategy_url}"
echo
echo "Netlify env values:"
echo "  VITE_API_BASE_URL=${runner_url}"
echo "  VITE_PLAYBACK_API_BASE_URL=${runner_url}"
echo "  VITE_STRATEGY_API_URL=${strategy_url}"
