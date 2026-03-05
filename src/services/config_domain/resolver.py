from __future__ import annotations

from typing import Any, Dict

from .repository import TickerConfigAggregate


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_ticker_display_payload(aggregate: TickerConfigAggregate) -> Dict[str, Any]:
    payload = dict(aggregate.ticker_config)
    if aggregate.positioning:
        payload["positioning"] = dict(aggregate.positioning)
    return payload


def resolve_local_aos_applied_snapshot(
    aggregate: TickerConfigAggregate,
) -> Dict[str, Any]:
    ticker_cfg = aggregate.ticker_config
    applied: Dict[str, Any] = {
        "trading_hours": ticker_cfg.get("trading_hours"),
        "time_filter_enabled": bool(
            ticker_cfg.get("time_filter_enabled", bool(ticker_cfg.get("trading_hours")))
        ),
        "strategy_selection_mode": (
            str(ticker_cfg.get("strategy_selection_mode", "adaptive_top_n"))
            .strip()
            .lower()
            or "adaptive_top_n"
        ),
    }

    raw_max_active = _coerce_int(ticker_cfg.get("max_active_strategies", 3), 3)
    applied["max_active_strategies"] = max(1, min(20, raw_max_active))

    if isinstance(ticker_cfg.get("l2"), dict):
        applied["l2"] = dict(ticker_cfg.get("l2", {}))
    if isinstance(ticker_cfg.get("adaptive"), dict):
        applied["adaptive"] = dict(ticker_cfg.get("adaptive", {}))

    applied["adverse_flow_consistency_threshold"] = _coerce_float(
        ticker_cfg.get("adverse_flow_consistency_threshold", 0.45),
        0.45,
    )
    applied["adverse_book_pressure_threshold"] = _coerce_float(
        ticker_cfg.get("adverse_book_pressure_threshold", 0.15),
        0.15,
    )

    if aggregate.positioning:
        applied["positioning"] = dict(aggregate.positioning)

    return applied
