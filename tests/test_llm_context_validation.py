from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path


def _load_validator_module():
    root = Path(__file__).resolve().parents[1]
    module_path = root / "scripts" / "validate_llm_context.py"
    spec = importlib.util.spec_from_file_location("validate_llm_context", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_minimal_repo(root: Path) -> None:
    _write(root / "scripts/generate_context_pack.py", "print('ok')\n")
    _write(root / "mapped.py", "def ok():\n    return True\n")

    map_payload = {
        "version": 2,
        "project": {"name": "mini"},
        "domains": [
            {
                "id": "orchestration",
                "title": "x",
                "files": ["mapped.py"],
                "critical_invariants": ["no lookahead"],
                "tests": ["tests/test_x.py"],
            }
        ],
    }
    _write(root / "bmad/context/component-map.json", json.dumps(map_payload, indent=2))

    _write(root / "AGENTS.md", "x")
    _write(root / "CLAUDE.md", "x")
    _write(root / "docs/llm/README.md", "x")
    _write(root / "docs/llm/functionality-map.md", "x")
    _write(root / "docs/llm/api-contracts.md", "x")
    _write(root / "docs/llm/invariants-and-validation.md", "x")
    _write(root / ".claude/settings.json", "{}")

    command_names = [
        "bmad-system-map.md",
        "bmad-next.md",
        "bmad-plan.md",
        "bmad-story.md",
        "bmad-implement.md",
        "bmad-review.md",
    ]
    for name in command_names:
        _write(
            root / ".claude/commands" / name,
            """
---
description: test command
---

use bmad/context/generated/00-machine-index.json
use bmad/context/generated/orchestration.md
```yaml
key: value
```
""".strip(),
        )

    _write(root / "bmad/context/generated/00-index.md", "x")
    _write(
        root / "bmad/context/generated/00-machine-index.json",
        json.dumps({"domains": [], "route_catalog": []}),
    )
    _write(root / "bmad/context/generated/00-endpoint-map.md", "x")
    _write(root / "bmad/context/generated/orchestration.md", "x")


def _patch_validator_paths(module, root: Path) -> None:
    module.ROOT = root
    module.MAP_PATH = root / "bmad/context/component-map.json"
    module.GEN_DIR = root / "bmad/context/generated"
    module.REQUIRED_DOCS = [
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / "docs/llm/README.md",
        root / "docs/llm/functionality-map.md",
        root / "docs/llm/api-contracts.md",
        root / "docs/llm/invariants-and-validation.md",
    ]
    module.REQUIRED_CLAUDE_CONFIG = [
        root / ".claude/settings.json",
    ]
    module.REQUIRED_COMMANDS = [
        root / ".claude/commands/bmad-system-map.md",
        root / ".claude/commands/bmad-next.md",
        root / ".claude/commands/bmad-plan.md",
        root / ".claude/commands/bmad-story.md",
        root / ".claude/commands/bmad-implement.md",
        root / ".claude/commands/bmad-review.md",
    ]


def test_run_checks_passes_on_valid_layout(tmp_path: Path) -> None:
    module = _load_validator_module()
    _build_minimal_repo(tmp_path)
    _patch_validator_paths(module, tmp_path)

    errors, warnings = module.run_checks(strict=False)
    assert errors == []
    assert warnings == []


def test_run_checks_fails_on_missing_generated_file(tmp_path: Path) -> None:
    module = _load_validator_module()
    _build_minimal_repo(tmp_path)
    _patch_validator_paths(module, tmp_path)

    os.remove(tmp_path / "bmad/context/generated/00-endpoint-map.md")

    errors, _ = module.run_checks(strict=False)
    assert any("00-endpoint-map.md" in err for err in errors)


def test_run_checks_fails_on_stale_generated_file(tmp_path: Path) -> None:
    module = _load_validator_module()
    _build_minimal_repo(tmp_path)
    _patch_validator_paths(module, tmp_path)

    generated = tmp_path / "bmad/context/generated/00-index.md"
    map_file = tmp_path / "bmad/context/component-map.json"

    os.utime(generated, (1, 1))
    os.utime(map_file, None)

    errors, _ = module.run_checks(strict=False)
    assert any("Stale generated file" in err for err in errors)


def test_run_checks_fails_on_missing_command_frontmatter(tmp_path: Path) -> None:
    module = _load_validator_module()
    _build_minimal_repo(tmp_path)
    _patch_validator_paths(module, tmp_path)

    command_path = tmp_path / ".claude/commands/bmad-implement.md"
    command_path.write_text(
        """
use bmad/context/generated/00-machine-index.json
use bmad/context/generated/orchestration.md
```yaml
key: value
```
""".strip(),
        encoding="utf-8",
    )

    errors, _ = module.run_checks(strict=False)
    assert any("frontmatter" in err for err in errors)
