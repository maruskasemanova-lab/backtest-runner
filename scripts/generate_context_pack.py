#!/usr/bin/env python3
"""
Generate BMAD context packs from bmad/context/component-map.json.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "bmad" / "context" / "component-map.json"
OUT_DIR = ROOT / "bmad" / "context" / "generated"


def read_map() -> Dict[str, Any]:
    if not MAP_PATH.exists():
        raise FileNotFoundError(f"Missing map file: {MAP_PATH}")
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def resolve_path(raw_path: str) -> Path:
    p = Path(raw_path)
    if p.is_absolute():
        return p
    return (ROOT / p).resolve()


def find_git_root(path: Path) -> Optional[Path]:
    current = path.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *list(current.parents)]:
        if (candidate / ".git").exists():
            return candidate
    return None


def git_last_touch(path: Path) -> str:
    if not path.exists():
        return "-"
    git_root = find_git_root(path)
    if git_root is None:
        return "-"
    try:
        rel = path.resolve().relative_to(git_root)
    except ValueError:
        return "-"
    cmd = ["git", "-C", str(git_root), "log", "-n", "1", "--pretty=format:%h %cs", "--", str(rel)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    out = proc.stdout.strip()
    return out if out else "-"


def line_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)


def build_domain_markdown(domain: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Domain: {domain['title']}")
    lines.append("")
    lines.append(f"**ID:** `{domain['id']}`")
    lines.append("")
    lines.append("## Mission")
    lines.append("")
    lines.append(domain.get("mission", ""))
    lines.append("")
    lines.append("## Depends On")
    lines.append("")
    depends_on = domain.get("depends_on", [])
    if depends_on:
        for dep in depends_on:
            lines.append(f"- `{dep}`")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Entrypoints")
    lines.append("")
    for ep in domain.get("entrypoints", []):
        lines.append(f"- `{ep}`")
    lines.append("")
    lines.append("## File Inventory")
    lines.append("")
    lines.append("| File | Exists | Lines | Last Commit |")
    lines.append("|---|---:|---:|---|")
    for raw in domain.get("files", []):
        path = resolve_path(raw)
        exists = "yes" if path.exists() else "no"
        lines_count = line_count(path)
        touched = git_last_touch(path)
        lines.append(f"| `{raw}` | {exists} | {lines_count} | `{touched}` |")
    lines.append("")
    lines.append("## Change Checks")
    lines.append("")
    for check in domain.get("change_checks", []):
        lines.append(f"- {check}")
    lines.append("")
    lines.append("## Prompt Primer")
    lines.append("")
    lines.append(
        "Load this file plus `bmad/context/generated/00-index.md`, then keep edits scoped to "
        "the file inventory unless interface changes are explicitly required."
    )
    lines.append("")
    return "\n".join(lines)


def build_index_markdown(config: Dict[str, Any]) -> str:
    project = config.get("project", {})
    domains = config.get("domains", [])
    lines: List[str] = []
    lines.append("# BMAD Context Index")
    lines.append("")
    lines.append(f"**Project:** {project.get('name', '')}")
    lines.append("")
    lines.append(project.get("summary", ""))
    lines.append("")
    lines.append("## Services")
    lines.append("")
    lines.append("| Service | Port | Responsibility |")
    lines.append("|---|---:|---|")
    for service in project.get("services", []):
        lines.append(
            f"| `{service.get('name', '')}` | {service.get('port', '')} | {service.get('responsibility', '')} |"
        )
    lines.append("")
    lines.append("## Data Flow")
    lines.append("")
    lines.append(project.get("data_flow", ""))
    lines.append("")
    lines.append("## Domains")
    lines.append("")
    lines.append("| Domain ID | Title | Pack |")
    lines.append("|---|---|---|")
    for domain in domains:
        lines.append(
            f"| `{domain.get('id', '')}` | {domain.get('title', '')} | `bmad/context/generated/{domain.get('id', '')}.md` |"
        )
    lines.append("")
    lines.append("## How To Use")
    lines.append("")
    lines.append("- Pick one primary domain for the task.")
    lines.append("- Load that domain pack and keep changes local first.")
    lines.append("- If cross-domain edits are needed, list impacted contracts explicitly.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    config = read_map()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    domains = config.get("domains", [])
    index_md = build_index_markdown(config)
    (OUT_DIR / "00-index.md").write_text(index_md, encoding="utf-8")

    for domain in domains:
        content = build_domain_markdown(domain)
        file_name = f"{domain['id']}.md"
        (OUT_DIR / file_name).write_text(content, encoding="utf-8")

    print(f"Generated {len(domains) + 1} context files in {OUT_DIR}")


if __name__ == "__main__":
    main()

