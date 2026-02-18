#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${NETLIFY_SITE_ID:-}" || -z "${NETLIFY_AUTH_TOKEN:-}" ]]; then
  echo "NETLIFY_SITE_ID and NETLIFY_AUTH_TOKEN are required."
  exit 1
fi

FLY_RUNNER_APP_NAME="${FLY_RUNNER_APP_NAME:-backtest-runner-api}"
FLY_STRATEGY_APP_NAME="${FLY_STRATEGY_APP_NAME:-market-regime-strategy-api}"

runner_url="https://${FLY_RUNNER_APP_NAME}.fly.dev"
strategy_url="https://${FLY_STRATEGY_APP_NAME}.fly.dev"

npx netlify env:set VITE_API_BASE_URL "${runner_url}" \
  --site "${NETLIFY_SITE_ID}" \
  --auth "${NETLIFY_AUTH_TOKEN}"

npx netlify env:set VITE_PLAYBACK_API_BASE_URL "${runner_url}" \
  --site "${NETLIFY_SITE_ID}" \
  --auth "${NETLIFY_AUTH_TOKEN}"

npx netlify env:set VITE_STRATEGY_API_URL "${strategy_url}" \
  --site "${NETLIFY_SITE_ID}" \
  --auth "${NETLIFY_AUTH_TOKEN}"

npx netlify env:set VITE_WS_BASE_URL "wss://${FLY_RUNNER_APP_NAME}.fly.dev" \
  --site "${NETLIFY_SITE_ID}" \
  --auth "${NETLIFY_AUTH_TOKEN}"

echo "Netlify environment updated for Fly stack."
