#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found. Install it first, then run this script again."
  exit 1
fi

export CODEX_HOME="${ROOT_DIR}/.codex"
mkdir -p "${CODEX_HOME}"

"${ROOT_DIR}/scripts/sync_codex_prompts.sh"

echo "Starting Codex with CODEX_HOME=${CODEX_HOME}"
exec codex "$@"
