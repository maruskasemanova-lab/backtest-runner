#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${RENDER_DEPLOY_HOOK_URL:-}" ]]; then
  echo "Missing RENDER_DEPLOY_HOOK_URL env var."
  echo "Create a Deploy Hook in Render and export it before running this script."
  exit 1
fi

curl -fsS -X POST "$RENDER_DEPLOY_HOOK_URL" >/dev/null
echo "Render deploy triggered."
