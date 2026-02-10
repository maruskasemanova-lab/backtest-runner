#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found. Install Node.js 18+ first."
  exit 1
fi

TEMP_BMAD_DIR=".bmad_legacy_tmp"
TEMP_COMMAND_BACKUP=".claude/commands/.legacy-bmad-cmd-backup"
INSTALL_ACTION="install"
BMAD_USER_NAME="${BMAD_USER_NAME:-${USER:-hotovo}}"
BMAD_COMM_LANG="${BMAD_COMM_LANG:-English}"
BMAD_DOC_LANG="${BMAD_DOC_LANG:-English}"
LEGACY_COMMANDS=(
  "bmad-implement.md"
  "bmad-next.md"
  "bmad-plan.md"
  "bmad-review.md"
  "bmad-story.md"
  "bmad-system-map.md"
)

restore_on_exit() {
  if [[ -d "${TEMP_BMAD_DIR}" && ! -d "bmad" ]]; then
    mv "${TEMP_BMAD_DIR}" "bmad"
  fi
  if [[ -d "${TEMP_COMMAND_BACKUP}" ]]; then
    for file in "${LEGACY_COMMANDS[@]}"; do
      if [[ -f "${TEMP_COMMAND_BACKUP}/${file}" ]]; then
        cp "${TEMP_COMMAND_BACKUP}/${file}" ".claude/commands/${file}"
      fi
    done
  fi
}
trap restore_on_exit EXIT

mkdir -p "${TEMP_COMMAND_BACKUP}"
for file in "${LEGACY_COMMANDS[@]}"; do
  if [[ -f ".claude/commands/${file}" ]]; then
    cp ".claude/commands/${file}" "${TEMP_COMMAND_BACKUP}/${file}"
  fi
done

if [[ -d "bmad" ]]; then
  mv "bmad" "${TEMP_BMAD_DIR}"
fi

if [[ -d "_bmad" ]]; then
  INSTALL_ACTION="quick-update"
fi

echo "Installing full BMAD-METHOD (bmm + bmb) for Claude Code (action: ${INSTALL_ACTION})..."
npx bmad-method@beta install \
  --directory "${ROOT_DIR}" \
  --modules bmm,bmb \
  --tools claude-code \
  --action "${INSTALL_ACTION}" \
  --user-name "${BMAD_USER_NAME}" \
  --communication-language "${BMAD_COMM_LANG}" \
  --document-output-language "${BMAD_DOC_LANG}" \
  --output-folder _bmad-output \
  --yes

if [[ -d "${TEMP_BMAD_DIR}" ]]; then
  mv "${TEMP_BMAD_DIR}" "bmad"
fi

for file in "${LEGACY_COMMANDS[@]}"; do
  if [[ -f "${TEMP_COMMAND_BACKUP}/${file}" ]]; then
    cp "${TEMP_COMMAND_BACKUP}/${file}" ".claude/commands/${file}"
  fi
done

rm -rf "${TEMP_COMMAND_BACKUP}"
trap - EXIT

echo
echo "Refreshing project-specific context packs..."
python3 scripts/generate_context_pack.py

echo
echo "Normalizing BMAD command names for Claude (/bmad-*)..."
./scripts/sync_claude_bmad_names.sh

echo
echo "Syncing BMAD prompts for project-local Codex usage..."
./scripts/sync_codex_prompts.sh

echo
echo "Done. Use /bmad-help for official BMAD flow or keep project custom commands (/bmad-plan, /bmad-implement, ...)."
