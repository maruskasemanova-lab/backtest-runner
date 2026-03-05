from __future__ import annotations

from typing import Any, Dict

from src.services.config_fingerprint_utils import compute_config_fingerprint
from src.services.start_run_report_utils import extract_effective_profile_metadata


def _canonical_trading_hours(value: Any) -> list[int]:
    if not isinstance(value, (list, tuple)):
        return []
    normalized: set[int] = set()
    for raw_hour in value:
        try:
            hour = int(raw_hour)
        except (TypeError, ValueError):
            continue
        if 0 <= hour <= 23:
            normalized.add(hour)
    return sorted(normalized)


def _optional_token(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def build_control_plane_snapshot(
    *,
    aos_applied: Dict[str, Any],
    execution_config: Dict[str, Any],
    apply_aos_optimizations_on_start: bool,
    effective_reset_scope: str,
    comparable_mode: bool,
) -> Dict[str, Any]:
    aos_payload = dict(aos_applied) if isinstance(aos_applied, dict) else {}
    execution_payload = (
        dict(execution_config) if isinstance(execution_config, dict) else {}
    )
    profile_meta = extract_effective_profile_metadata(
        aos_applied=aos_payload,
        execution_config=execution_payload,
    )

    execution_config_fingerprint = _optional_token(
        execution_payload.get("config_fingerprint")
    ) or compute_config_fingerprint(execution_payload)
    aos_applied_fingerprint = compute_config_fingerprint({"aos_applied": aos_payload})

    max_active_strategies: int | None
    try:
        max_active_strategies = int(
            aos_payload.get(
                "max_active_strategies",
                execution_payload.get("effective_max_active_strategies"),
            )
        )
    except (TypeError, ValueError):
        max_active_strategies = None

    return {
        "schema_version": 1,
        "config_fingerprint": execution_config_fingerprint,
        "execution_config_fingerprint": execution_config_fingerprint,
        "aos_applied_fingerprint": aos_applied_fingerprint,
        "apply_aos_optimizations_on_start": bool(apply_aos_optimizations_on_start),
        "effective_reset_scope": str(effective_reset_scope or "").strip() or "session",
        "comparable_mode": bool(comparable_mode),
        "trading_hours": _canonical_trading_hours(aos_payload.get("trading_hours")),
        "time_filter_enabled": bool(aos_payload.get("time_filter_enabled", False)),
        "strategy_selection_mode": (
            str(
                aos_payload.get(
                    "strategy_selection_mode",
                    execution_payload.get("effective_strategy_selection_mode", ""),
                )
            )
            .strip()
            .lower()
            or None
        ),
        "max_active_strategies": max_active_strategies,
        **profile_meta,
    }
