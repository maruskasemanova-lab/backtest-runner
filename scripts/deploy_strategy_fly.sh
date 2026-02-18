#!/usr/bin/env bash
set -euo pipefail

if ! command -v flyctl >/dev/null 2>&1; then
  echo "flyctl is required. Install from https://fly.io/docs/flyctl/install/."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

STRATEGY_REPO_DIR="${STRATEGY_REPO_DIR:-${REPO_ROOT}/../market_regime_detection}"
FLY_STRATEGY_APP_NAME="${FLY_STRATEGY_APP_NAME:-market-regime-strategy-api}"
FLY_PRIMARY_REGION="${FLY_PRIMARY_REGION:-iad}"

if [[ ! -f "${STRATEGY_REPO_DIR}/api_server.py" || ! -f "${STRATEGY_REPO_DIR}/requirements.txt" ]]; then
  echo "Strategy repo not found at '${STRATEGY_REPO_DIR}'."
  exit 1
fi

dockerfile_path="${STRATEGY_REPO_DIR}/.fly.Dockerfile"
config_path="${STRATEGY_REPO_DIR}/.fly.toml"
trap 'rm -f "${dockerfile_path}" "${config_path}"' EXIT

cp "${REPO_ROOT}/config/fly/strategy.Dockerfile" "${dockerfile_path}"
cp "${REPO_ROOT}/config/fly/strategy.fly.toml" "${config_path}"

if ! flyctl apps show "${FLY_STRATEGY_APP_NAME}" >/dev/null 2>&1; then
  flyctl apps create "${FLY_STRATEGY_APP_NAME}"
fi

SECRET_PAIRS=()
for key in STRATEGY_INTERNAL_API_TOKEN STRATEGY_CORS_ALLOW_ORIGINS STRATEGY_CORS_ALLOW_ORIGIN_REGEX
do
  value="${!key:-}"
  if [[ -n "${value}" ]]; then
    SECRET_PAIRS+=("${key}=${value}")
  fi
done

if (( ${#SECRET_PAIRS[@]} > 0 )); then
  flyctl secrets set --app "${FLY_STRATEGY_APP_NAME}" "${SECRET_PAIRS[@]}"
fi

flyctl deploy "${STRATEGY_REPO_DIR}" \
  --config "${config_path}" \
  --dockerfile "${dockerfile_path}" \
  --app "${FLY_STRATEGY_APP_NAME}" \
  --primary-region "${FLY_PRIMARY_REGION}" \
  --remote-only

flyctl scale count 1 --yes --app "${FLY_STRATEGY_APP_NAME}"

echo "Strategy API deployed: https://${FLY_STRATEGY_APP_NAME}.fly.dev"
