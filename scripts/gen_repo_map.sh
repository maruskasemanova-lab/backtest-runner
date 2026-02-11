#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_FILE="$ROOT_DIR/docs/REPO_MAP.md"
GENERATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

IGNORES=".git|node_modules|dist|build|__pycache__|.pytest_cache|reports|walk_forward_results|aos_walk_forward_results|_bmad-output|*.log|*.json|*.csv|*.parquet|*.parq|*.tar.gz"

{
  echo "# Repo Map"
  echo
  echo "Generated at: \`$GENERATED_AT\`"
  echo
  echo "## Tree (depth 2)"
  echo
  echo "\`\`\`text"
  if command -v tree >/dev/null 2>&1; then
    (
      cd "$ROOT_DIR"
      tree -L 2 -I "$IGNORES"
    )
  else
    (
      cd "$ROOT_DIR"
      find . -maxdepth 2 \
        -not -path "./.git/*" \
        -not -path "./node_modules/*" \
        -not -path "./dist/*" \
        -not -path "./build/*" \
        -not -path "./__pycache__/*" \
        -not -name "*.log" \
        -not -name "*.json" \
        -not -name "*.csv" \
        -not -name "*.parquet" \
        -not -name "*.parq" \
        -not -name "*.tar.gz" \
        | sort
    )
  fi
  echo "\`\`\`"
  echo
  echo "## Entrypoints / Key Files"
  echo
  echo "- \`api_server.py\` (runner API orchestration, adaptive tuner, AOS config endpoints)"
  echo "- \`session_runner.py\` (bar playback engine, marker lifecycle)"
  echo "- \`data_loader.py\` (OHLCV loading/filtering)"
  echo "- \`src/l2_feature_service.py\` (L2 feature attachment to bars)"
  echo "- \`src/l2_data_manager.py\` (L2 file loading and raw L2 access)"
  echo "- \`frontend/src/App.jsx\` (frontend orchestration shell)"
  echo "- \`frontend/src/components/RunConfig.jsx\` (run payload + pre-run AOS/profile apply)"
  echo "- \`frontend/src/components/AdaptiveTuner.jsx\` (tuner UI + polling)"
  echo "- \`frontend/src/components/AdaptiveStrategyStudio.jsx\` (adaptive config editor)"
  echo
  echo "## Adaptive Tuning Hot Spots"
  echo
  echo "- \`POST /api/adaptive-tuner/run\` in \`api_server.py\`"
  echo "- \`_run_adaptive_tuner_job\` (v1 worker) in \`api_server.py\`"
  echo "- \`_run_v2_adaptive_tuner_job\` (v2 worker) in \`api_server.py\`"
  echo "- \`_evaluate_adaptive_tuner_candidate\` / \`_evaluate_v2_candidate\` in \`api_server.py\`"
  echo "- \`tests/test_adaptive_tuner_api.py\`"
  echo
  echo "## AOS Config Persistence Surface"
  echo
  echo "- Source file: \`aos_optimization/aos_config.json\`"
  echo "- Read helpers: \`_load_aos_config\`"
  echo "- Write helper: \`_save_aos_config\`"
  echo "- Write endpoints: \`/api/aos-config/update\`, \`/api/strategy-combos/*\`, \`/api/adaptive-tuner/profiles/apply\`, tuner workers"
  echo "- \`/api/run/start\` reads/apply runtime config but does not directly persist \`aos_config.json\`"
  echo
  echo "## LLM Context Files"
  echo
  echo "- \`CLAUDE.md\` (persistent agent instructions)"
  echo "- \`AGENTS.md\` (deterministic protocol for coding agents)"
  echo "- \`docs/llm/*.md\` (manual behavior/contract docs)"
  echo "- \`bmad/context/generated/*\` (generated machine/context index)"
} > "$OUT_FILE"

echo "Wrote $OUT_FILE"
