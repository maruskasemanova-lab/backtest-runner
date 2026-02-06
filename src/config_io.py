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


def coerce_bool(value: Any, default: bool = False) -> bool:
    """Coerce common bool-like values to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def extract_multilayer_payload(ticker_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ticker-specific multi-layer/candlestick settings from AOS config."""
    allowed_core = {"pattern_weight", "strategy_weight", "threshold", "require_pattern"}
    allowed_detector = {
        "body_doji_pct",
        "wick_ratio_hammer",
        "engulfing_min_body_pct",
        "volume_confirm_ratio",
        "vwap_proximity_pct",
    }

    raw: Dict[str, Any] = {}
    for key in ("multilayer", "multi_layer"):
        block = ticker_config.get(key)
        if isinstance(block, dict):
            raw.update(block)

    candlestick = ticker_config.get("candlestick")
    if isinstance(candlestick, dict):
        nested_ml = candlestick.get("multilayer")
        if isinstance(nested_ml, dict):
            raw.update(nested_ml)
        detector = candlestick.get("detector")
        if isinstance(detector, dict):
            raw.update(detector)
        for key in allowed_core.union(allowed_detector):
            if key in candlestick:
                raw[key] = candlestick[key]

    for key in allowed_core.union(allowed_detector):
        if key in ticker_config and key not in raw:
            raw[key] = ticker_config[key]

    detector_block = raw.get("detector")
    if isinstance(detector_block, dict):
        for key in allowed_detector:
            if key in detector_block and key not in raw:
                raw[key] = detector_block[key]

    payload: Dict[str, Any] = {}
    for key in ("pattern_weight", "strategy_weight", "threshold"):
        if key not in raw:
            continue
        try:
            payload[key] = float(raw[key])
        except (TypeError, ValueError):
            continue

    if "require_pattern" in raw:
        payload["require_pattern"] = coerce_bool(raw["require_pattern"], default=True)

    for key in allowed_detector:
        if key not in raw:
            continue
        try:
            payload[key] = float(raw[key])
        except (TypeError, ValueError):
            continue

    return payload

