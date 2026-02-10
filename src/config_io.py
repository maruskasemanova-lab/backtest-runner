"""
Configuration and JSON utility helpers for backtest-runner.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_json_file(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    """Load JSON file with safe fallback."""
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text())
    except Exception:
        return dict(default)


def save_json_file(path: Path, payload: Dict[str, Any]) -> bool:
    """Persist JSON file with stable formatting."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))
        return True
    except Exception:
        return False
