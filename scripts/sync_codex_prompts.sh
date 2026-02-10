#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${ROOT_DIR}/.claude/commands"
PROJECT_TARGET_DIR="${ROOT_DIR}/.codex/prompts"
GLOBAL_TARGET_DIR="${HOME}/.codex/prompts"

MODE="project"
case "${1:-}" in
  --global)
    MODE="global"
    ;;
  --both)
    MODE="both"
    ;;
  ""|--project)
    MODE="project"
    ;;
  *)
    echo "Usage: $0 [--project|--global|--both]"
    exit 1
    ;;
esac

if [[ ! -d "${SOURCE_DIR}" ]]; then
  echo "Missing source commands directory: ${SOURCE_DIR}"
  exit 1
fi

sync_target() {
  local target_dir="$1"
  mkdir -p "${target_dir}"
  find "${target_dir}" -maxdepth 1 -type f -name 'bmad*.md' -delete

  local count=0
  while IFS= read -r -d '' file; do
    stem="$(basename "${file}" .md)"
    target="${target_dir}/$(basename "${file}")"
    python3 - "${file}" "${target}" "${stem}" <<'PY'
from pathlib import Path
import re
import sys

source_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
command_name = sys.argv[3]
text = source_path.read_text(encoding="utf-8")
lines = text.splitlines()

if lines and lines[0].strip() == "---":
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end = idx
            break

    if end is not None:
        frontmatter = lines[1:end]
        body = lines[end + 1 :]
        replaced = False
        updated = []

        for line in frontmatter:
            if re.match(r"^\s*name\s*:\s*", line):
                updated.append(f"name: '{command_name}'")
                replaced = True
            else:
                updated.append(line)

        if not replaced:
            updated.insert(0, f"name: '{command_name}'")

        output = "---\n" + "\n".join(updated) + "\n---\n"
        if body:
            output += "\n".join(body)
            if text.endswith("\n"):
                output += "\n"
        target_path.write_text(output, encoding="utf-8")
        sys.exit(0)

target_path.write_text(text, encoding="utf-8")
PY
    count=$((count + 1))
  done < <(find "${SOURCE_DIR}" -maxdepth 1 -type f -name 'bmad*.md' -print0 | sort -z)
  echo "Synced ${count} BMAD prompt files to ${target_dir}"
}

if [[ "${MODE}" == "project" || "${MODE}" == "both" ]]; then
  sync_target "${PROJECT_TARGET_DIR}"
fi

if [[ "${MODE}" == "global" || "${MODE}" == "both" ]]; then
  sync_target "${GLOBAL_TARGET_DIR}"
fi
