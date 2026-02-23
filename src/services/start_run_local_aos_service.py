from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def _load_aos_config_safe(
    *,
    load_aos_config: Callable[..., Dict[str, Any]],
    aos_config_path: Optional[str],
) -> Dict[str, Any]:
    try:
        config = (
            load_aos_config(aos_config_path) if aos_config_path else load_aos_config()
        )
    except TypeError:
        config = load_aos_config()
    except Exception:
        return {}
    return config if isinstance(config, dict) else {}


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


def resolve_local_aos_applied(
    *,
    ticker: str,
    load_aos_config: Callable[..., Dict[str, Any]],
    get_ticker_positioning_config: Callable[[str], Dict[str, Any]],
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    aos_config = _load_aos_config_safe(
        load_aos_config=load_aos_config,
        aos_config_path=aos_config_path,
    )

    tickers = aos_config.get("tickers", {}) if isinstance(aos_config, dict) else {}
    ticker_cfg = tickers.get(ticker.upper(), {}) if isinstance(tickers, dict) else {}
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

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

    try:
        positioning_cfg = get_ticker_positioning_config(ticker)
    except Exception:
        positioning_cfg = {}
    if isinstance(positioning_cfg, dict) and positioning_cfg:
        applied["positioning"] = dict(positioning_cfg)

    return applied
