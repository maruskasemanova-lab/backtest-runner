#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

require_axon() {
  if ! command -v axon >/dev/null 2>&1; then
    echo "Axon CLI not found (axon). Install with: uv tool install axoniq --python 3.11"
    exit 1
  fi
}

usage() {
  cat <<'EOF'
Usage: ./scripts/axon-flow.sh <command> [args]

Commands:
  doctor                     Check Axon install, MCP config, and local index presence
  index                      Build/update Axon index for this repo (axon analyze .)
  watch                      Watch + live reindex (axon watch)
  mcp                        Start MCP server with watch (axon serve --watch)
  q|query <text>             Hybrid search
  ctx|context <symbol>       Symbol context (callers/callees/type refs)
  impact <symbol> [depth]    Blast radius (default depth=3)
  dead                       Dead-code report
  diff <base..head>          Structural branch diff (example: main..feature)
  refresh-context            Regenerate/validate BMAD context pack
  help                       Show this help

Examples:
  ./scripts/axon-flow.sh doctor
  ./scripts/axon-flow.sh index
  ./scripts/axon-flow.sh q "start run prewarm cache"
  ./scripts/axon-flow.sh ctx service_start_run
  ./scripts/axon-flow.sh impact StartRunRequest 2
  ./scripts/axon-flow.sh dead
EOF
}

run_repo() {
  (
    cd "${ROOT_DIR}"
    "$@"
  )
}

main() {
  local cmd="${1:-help}"
  if [[ $# -gt 0 ]]; then
    shift
  fi

  case "${cmd}" in
    help|-h|--help)
      usage
      ;;
    doctor)
      require_axon
      echo "Repo: ${ROOT_DIR}"
      echo "Axon: $(command -v axon)"
      run_repo axon --version
      if [[ -f "${ROOT_DIR}/.mcp.json" ]]; then
        echo "Project MCP config: ${ROOT_DIR}/.mcp.json (present)"
      else
        echo "Project MCP config: ${ROOT_DIR}/.mcp.json (missing)"
      fi
      if [[ -e "${ROOT_DIR}/.axon/kuzu" ]]; then
        echo "Index: ${ROOT_DIR}/.axon/kuzu (present)"
      else
        echo "Index: ${ROOT_DIR}/.axon/kuzu (missing; run './scripts/axon-flow.sh index')"
      fi
      ;;
    index)
      require_axon
      run_repo axon analyze .
      ;;
    watch)
      require_axon
      run_repo axon watch
      ;;
    mcp)
      require_axon
      run_repo axon serve --watch
      ;;
    q|query)
      require_axon
      if [[ $# -lt 1 ]]; then
        echo "Missing query text."
        usage
        exit 1
      fi
      run_repo axon query "$*"
      ;;
    ctx|context)
      require_axon
      if [[ $# -ne 1 ]]; then
        echo "Usage: ./scripts/axon-flow.sh context <symbol>"
        exit 1
      fi
      run_repo axon context "$1"
      ;;
    impact)
      require_axon
      if [[ $# -lt 1 || $# -gt 2 ]]; then
        echo "Usage: ./scripts/axon-flow.sh impact <symbol> [depth]"
        exit 1
      fi
      local depth="${2:-3}"
      run_repo axon impact "$1" --depth "${depth}"
      ;;
    dead)
      require_axon
      run_repo axon dead-code
      ;;
    diff)
      require_axon
      if [[ $# -ne 1 ]]; then
        echo "Usage: ./scripts/axon-flow.sh diff <base..head>"
        exit 1
      fi
      run_repo axon diff "$1"
      ;;
    refresh-context)
      run_repo python3 scripts/generate_context_pack.py
      run_repo python3 scripts/validate_llm_context.py
      ;;
    *)
      echo "Unknown command: ${cmd}"
      usage
      exit 1
      ;;
  esac
}

main "$@"
