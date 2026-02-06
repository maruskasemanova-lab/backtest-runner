#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if ! command -v npx >/dev/null 2>&1; then
  echo "npx not found. Install Node.js 18+ first."
  exit 1
fi

echo "Running BMAD interactive installer..."
npx bmad-method install

echo
echo "Refreshing project-specific context packs..."
python3 scripts/generate_context_pack.py

echo
echo "Done. Start with: BMAD_QUICKSTART.md"
