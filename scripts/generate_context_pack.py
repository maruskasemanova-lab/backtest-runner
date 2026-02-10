#!/usr/bin/env python3
"""
Generate BMAD context packs from bmad/context/component-map.json.

Outputs:
- bmad/context/generated/00-index.md
- bmad/context/generated/<domain>.md
- bmad/context/generated/00-machine-index.json
- bmad/context/generated/00-endpoint-map.md
"""
from __future__ import annotations

import ast
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "bmad" / "context" / "component-map.json"
OUT_DIR = ROOT / "bmad" / "context" / "generated"
ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "websocket"}


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


def _decorator_route_info(decorator: ast.AST) -> Optional[Tuple[str, str]]:
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr.lower() not in ROUTE_DECORATORS:
        return None

    value = func.value
    if not isinstance(value, ast.Name) or value.id not in {"app", "router"}:
        return None

    path = ""
    if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
        path = decorator.args[0].value
    for kw in decorator.keywords:
        if kw.arg == "path" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            path = kw.value.value
    return func.attr.upper(), path


def extract_python_metadata(path: Path) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"symbols": [], "routes": [], "parse_error": None}
    if not path.exists() or path.suffix != ".py":
        return payload

    source = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        payload["parse_error"] = f"{exc.msg} @ line {exc.lineno}"
        return payload

    symbols: List[Dict[str, Any]] = []
    routes: List[Dict[str, Any]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            symbols.append({"kind": "class", "name": node.name, "line": node.lineno})
        elif isinstance(node, ast.AsyncFunctionDef):
            symbols.append({"kind": "async_function", "name": node.name, "line": node.lineno})
        elif isinstance(node, ast.FunctionDef):
            symbols.append({"kind": "function", "name": node.name, "line": node.lineno})

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                route_info = _decorator_route_info(decorator)
                if route_info is None:
                    continue
                method, route_path = route_info
                routes.append(
                    {
                        "method": method,
                        "path": route_path,
                        "handler": node.name,
                        "line": node.lineno,
                    }
                )

    payload["symbols"] = symbols
    payload["routes"] = routes
    return payload


def build_file_record(raw_path: str) -> Dict[str, Any]:
    path = resolve_path(raw_path)
    exists = path.exists()
    record: Dict[str, Any] = {
        "path": raw_path,
        "absolute_path": str(path),
        "exists": exists,
        "lines": line_count(path),
        "last_commit": git_last_touch(path),
        "symbols": [],
        "routes": [],
        "parse_error": None,
    }

    if exists and path.suffix == ".py":
        py_meta = extract_python_metadata(path)
        record["symbols"] = py_meta["symbols"]
        record["routes"] = py_meta["routes"]
        record["parse_error"] = py_meta.get("parse_error")

    return record


def build_machine_index(config: Dict[str, Any]) -> Dict[str, Any]:
    domains_out: List[Dict[str, Any]] = []
    route_catalog: List[Dict[str, Any]] = []

    for domain in config.get("domains", []):
        files = [build_file_record(raw) for raw in domain.get("files", [])]

        for file_record in files:
            for route in file_record.get("routes", []):
                route_catalog.append(
                    {
                        "domain": domain.get("id"),
                        "file": file_record.get("path"),
                        "method": route.get("method"),
                        "path": route.get("path"),
                        "handler": route.get("handler"),
                        "line": route.get("line"),
                    }
                )

        domains_out.append(
            {
                "id": domain.get("id"),
                "title": domain.get("title"),
                "mission": domain.get("mission"),
                "depends_on": domain.get("depends_on", []),
                "entrypoints": domain.get("entrypoints", []),
                "change_checks": domain.get("change_checks", []),
                "critical_invariants": domain.get("critical_invariants", []),
                "tests": domain.get("tests", []),
                "files": files,
            }
        )

    route_catalog.sort(key=lambda r: (str(r.get("domain")), str(r.get("method")), str(r.get("path")), str(r.get("handler"))))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": config.get("project", {}),
        "map_version": config.get("version", 1),
        "domains": domains_out,
        "route_catalog": route_catalog,
    }


def build_domain_markdown(domain: Dict[str, Any], file_records: List[Dict[str, Any]]) -> str:
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
    for rec in file_records:
        exists = "yes" if rec.get("exists") else "no"
        lines.append(
            f"| `{rec.get('path')}` | {exists} | {rec.get('lines', 0)} | `{rec.get('last_commit', '-')}` |"
        )
    lines.append("")

    lines.append("## Change Checks")
    lines.append("")
    for check in domain.get("change_checks", []):
        lines.append(f"- {check}")
    lines.append("")

    lines.append("## Critical Invariants")
    lines.append("")
    invariants = domain.get("critical_invariants", [])
    if invariants:
        for inv in invariants:
            lines.append(f"- {inv}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Test Targets")
    lines.append("")
    tests = domain.get("tests", [])
    if tests:
        for test in tests:
            lines.append(f"- `{test}`")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Key Symbols")
    lines.append("")
    symbols_written = False
    for rec in file_records:
        symbols = rec.get("symbols") or []
        if not symbols:
            continue
        symbols_written = True
        lines.append(f"### `{rec.get('path')}`")
        for symbol in symbols[:12]:
            lines.append(
                f"- `{symbol.get('kind')}` `{symbol.get('name')}` (line {symbol.get('line')})"
            )
        if len(symbols) > 12:
            lines.append(f"- ... {len(symbols) - 12} more symbols")
        lines.append("")
    if not symbols_written:
        lines.append("- (no Python symbols discovered in mapped files)")
        lines.append("")

    lines.append("## Endpoint Summary")
    lines.append("")
    lines.append("| Method | Path | Handler | File |")
    lines.append("|---|---|---|---|")
    route_count = 0
    for rec in file_records:
        for route in rec.get("routes", []):
            route_count += 1
            lines.append(
                f"| `{route.get('method')}` | `{route.get('path')}` | `{route.get('handler')}` | `{rec.get('path')}` |"
            )
    if route_count == 0:
        lines.append("| `-` | `-` | `-` | `-` |")
    lines.append("")

    lines.append("## Prompt Primer")
    lines.append("")
    lines.append(
        "Load this domain pack with `bmad/context/generated/00-index.md` and "
        "`bmad/context/generated/00-machine-index.json`, then keep edits scoped "
        "to mapped files unless interface changes are explicit."
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

    lines.append("## Generated Assets")
    lines.append("")
    lines.append("- `bmad/context/generated/00-machine-index.json` (symbols + routes)")
    lines.append("- `bmad/context/generated/00-endpoint-map.md` (global endpoint catalog)")
    lines.append("")

    lines.append("## How To Use")
    lines.append("")
    lines.append("- Pick one primary domain for the task.")
    lines.append("- Load the primary domain pack plus `00-machine-index.json`.")
    lines.append("- Keep changes local first; list contract deltas when crossing domains.")
    lines.append("")
    return "\n".join(lines)


def build_endpoint_map_markdown(machine_index: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Endpoint Map")
    lines.append("")
    lines.append("Generated from mapped Python files in `component-map.json`.")
    lines.append("")
    lines.append("| Domain | Method | Path | Handler | File | Line |")
    lines.append("|---|---|---|---|---|---:|")

    routes = machine_index.get("route_catalog", [])
    if not routes:
        lines.append("| `-` | `-` | `-` | `-` | `-` | 0 |")
        lines.append("")
        return "\n".join(lines)

    for route in routes:
        lines.append(
            "| `{domain}` | `{method}` | `{path}` | `{handler}` | `{file}` | {line} |".format(
                domain=route.get("domain", "-"),
                method=route.get("method", "-"),
                path=route.get("path", "-"),
                handler=route.get("handler", "-"),
                file=route.get("file", "-"),
                line=route.get("line", 0),
            )
        )

    lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    config = read_map()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    machine_index = build_machine_index(config)

    index_md = build_index_markdown(config)
    (OUT_DIR / "00-index.md").write_text(index_md, encoding="utf-8")
    write_json(OUT_DIR / "00-machine-index.json", machine_index)

    endpoint_map_md = build_endpoint_map_markdown(machine_index)
    (OUT_DIR / "00-endpoint-map.md").write_text(endpoint_map_md, encoding="utf-8")

    domain_records = {d.get("id"): d for d in machine_index.get("domains", [])}
    for domain in config.get("domains", []):
        rec = domain_records.get(domain.get("id"), {})
        content = build_domain_markdown(domain, rec.get("files", []))
        (OUT_DIR / f"{domain['id']}.md").write_text(content, encoding="utf-8")

    print(
        f"Generated {len(config.get('domains', [])) + 3} context files in {OUT_DIR} "
        f"(including machine index + endpoint map)"
    )


if __name__ == "__main__":
    main()
