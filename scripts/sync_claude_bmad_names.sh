#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${ROOT_DIR}/.claude/commands"

if [[ ! -d "${SOURCE_DIR}" ]]; then
  echo "Missing commands directory: ${SOURCE_DIR}"
  exit 1
fi

count=0
while IFS= read -r -d '' file; do
  stem="$(basename "${file}" .md)"
  python3 - "${file}" "${stem}" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
command_name = sys.argv[2]
text = path.read_text(encoding="utf-8")
lines = text.splitlines()

if not lines or lines[0].strip() != "---":
    # Keep non-frontmatter commands intact (name is resolved from filename).
    sys.exit(0)

end = None
for idx in range(1, len(lines)):
    if lines[idx].strip() == "---":
        end = idx
        break

if end is None:
    sys.exit(0)

frontmatter = lines[1:end]
body = lines[end + 1 :]
updated = []
replaced = False

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

path.write_text(output, encoding="utf-8")
PY
  count=$((count + 1))
done < <(find "${SOURCE_DIR}" -maxdepth 1 -type f -name 'bmad*.md' -print0 | sort -z)

echo "Normalized ${count} Claude BMAD command names in ${SOURCE_DIR}"
