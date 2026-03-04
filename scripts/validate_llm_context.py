#!/usr/bin/env python3
"""
Validate BMAD + LLM context assets.

Usage:
  python3 scripts/validate_llm_context.py
  python3 scripts/validate_llm_context.py --check
  python3 scripts/validate_llm_context.py --strict
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "bmad" / "context" / "component-map.json"
GEN_DIR = ROOT / "bmad" / "context" / "generated"

REQUIRED_DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "CLAUDE.md",
    ROOT / "docs" / "llm" / "README.md",
    ROOT / "docs" / "llm" / "functionality-map.md",
    ROOT / "docs" / "llm" / "api-contracts.md",
    ROOT / "docs" / "llm" / "invariants-and-validation.md",
]

REQUIRED_CLAUDE_CONFIG = [
    ROOT / ".claude" / "settings.json",
]

REQUIRED_COMMANDS = [
    ROOT / ".claude" / "commands" / "bmad-system-map.md",
    ROOT / ".claude" / "commands" / "bmad-next.md",
    ROOT / ".claude" / "commands" / "bmad-plan.md",
    ROOT / ".claude" / "commands" / "bmad-story.md",
    ROOT / ".claude" / "commands" / "bmad-implement.md",
    ROOT / ".claude" / "commands" / "bmad-review.md",
]

REQUIRED_GENERATED = [
    "00-index.md",
    "00-machine-index.json",
    "00-endpoint-map.md",
]


def resolve_path(raw_path: str) -> Path:
    p = Path(raw_path)
    if p.is_absolute():
        return p
    return (ROOT / p).resolve()


def _parse_simple_frontmatter(content: str) -> Dict[str, str] | None:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return None

    result: Dict[str, str] = {}
    for line in lines[1:end_idx]:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip().strip("\"'")
        if key.strip():
            result[key.strip()] = value
    return result


def _load_map() -> Dict[str, Any]:
    if not MAP_PATH.exists():
        raise FileNotFoundError(f"Missing map file: {MAP_PATH}")
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _check_file_exists(path: Path, errors: List[str]) -> None:
    if not path.exists():
        errors.append(f"Missing required file: {path}")


def _check_command_content(
    path: Path, errors: List[str], warnings: List[str], strict: bool
) -> None:
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8", errors="ignore")
    frontmatter = _parse_simple_frontmatter(content)
    if frontmatter is None:
        errors.append(
            f"Command {path.name} must include YAML frontmatter with at least description"
        )
    elif not frontmatter.get("description"):
        errors.append(f"Command {path.name} frontmatter must include description")

    checks = [
        ("00-machine-index.json", "must reference machine index"),
        ("bmad/context/generated/", "must reference generated domain packs"),
        ("```yaml", "must include schema-first YAML output block"),
    ]

    for needle, msg in checks:
        if needle in content:
            continue
        line = f"Command {path.name} {msg}"
        if strict or needle != "```yaml":
            errors.append(line)
        else:
            warnings.append(line)


def _check_generated_assets(config: Dict[str, Any], errors: List[str]) -> None:
    if not GEN_DIR.exists():
        errors.append(f"Missing generated directory: {GEN_DIR}")
        return

    expected = list(REQUIRED_GENERATED)
    expected.extend(f"{d['id']}.md" for d in config.get("domains", []))
    for filename in expected:
        file_path = GEN_DIR / filename
        if not file_path.exists():
            errors.append(f"Missing generated file: {file_path}")

    newest_input = max(
        MAP_PATH.stat().st_mtime,
        (ROOT / "scripts" / "generate_context_pack.py").stat().st_mtime,
    )
    for filename in expected:
        file_path = GEN_DIR / filename
        if not file_path.exists():
            continue
        if file_path.stat().st_mtime < newest_input:
            errors.append(
                f"Stale generated file: {file_path} (run python3 scripts/generate_context_pack.py)"
            )


def _check_machine_index(errors: List[str]) -> None:
    machine_path = GEN_DIR / "00-machine-index.json"
    if not machine_path.exists():
        return

    try:
        payload = json.loads(machine_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Invalid JSON in {machine_path}: {exc}")
        return

    if not isinstance(payload.get("domains"), list):
        errors.append("Machine index is missing 'domains' list")
    if not isinstance(payload.get("route_catalog"), list):
        errors.append("Machine index is missing 'route_catalog' list")


def _check_mapped_files(
    config: Dict[str, Any], errors: List[str], warnings: List[str], strict: bool
) -> None:
    for domain in config.get("domains", []):
        domain_id = domain.get("id", "unknown")
        for raw in domain.get("files", []):
            path = resolve_path(raw)
            if not path.exists():
                errors.append(
                    f"Mapped file does not exist ({domain_id}): {raw} -> {path}"
                )

        if not domain.get("critical_invariants"):
            msg = f"Domain '{domain_id}' has no critical_invariants"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)

        if not domain.get("tests"):
            msg = f"Domain '{domain_id}' has no tests"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)


def run_checks(strict: bool = False) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    try:
        config = _load_map()
    except Exception as exc:
        return [str(exc)], warnings

    _check_mapped_files(config, errors, warnings, strict)

    for path in REQUIRED_DOCS:
        _check_file_exists(path, errors)

    for path in REQUIRED_CLAUDE_CONFIG:
        _check_file_exists(path, errors)

    for path in REQUIRED_COMMANDS:
        _check_file_exists(path, errors)
        _check_command_content(path, errors, warnings, strict)

    _check_generated_assets(config, errors)
    _check_machine_index(errors)

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate BMAD/LLM context artifacts")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run validation checks only (default behavior).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Promote warnings to errors for stricter local/CI gating.",
    )
    args = parser.parse_args()

    errors, warnings = run_checks(strict=args.strict)

    if errors:
        print("LLM context validation: FAILED")
        for item in errors:
            print(f"- ERROR: {item}")
    else:
        print("LLM context validation: PASSED")

    for item in warnings:
        print(f"- WARN: {item}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
