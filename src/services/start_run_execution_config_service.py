from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def resolve_execution_config(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
) -> Dict[str, Any]:
    aos_l2_cfg = aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}

    def _pick_l2_float(request_value: Any, cfg_key: str, profile_key: str) -> float:
        try:
            profile_value = float(adaptive_profile_runtime.get(profile_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            profile_value = 0.0
        if abs(profile_value) > 1e-12:
            return profile_value
        try:
            req = float(request_value)
        except (TypeError, ValueError):
            req = 0.0
        if abs(req) > 1e-12:
            return req
        try:
            return float(aos_l2_cfg.get(cfg_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    requested_l2_only = bool(request.l2_only or bool(aos_l2_cfg.get("l2_only", False)))
    requested_l2_confirm = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    l2_min_delta = _pick_l2_float(request.l2_min_delta, "min_delta", "l2_min_delta")
    l2_min_imbalance = _pick_l2_float(request.l2_min_imbalance, "min_imbalance", "l2_min_imbalance")
    l2_min_iceberg_bias = _pick_l2_float(
        request.l2_min_iceberg_bias, "min_iceberg_bias", "l2_min_iceberg_bias"
    )
    l2_min_participation_ratio = _pick_l2_float(
        request.l2_min_participation_ratio, "min_participation_ratio", "l2_min_participation_ratio"
    )
    l2_min_directional_consistency = _pick_l2_float(
        request.l2_min_directional_consistency,
        "min_directional_consistency",
        "l2_min_directional_consistency",
    )
    l2_min_signed_aggression = _pick_l2_float(
        request.l2_min_signed_aggression, "min_signed_aggression", "l2_min_signed_aggression"
    )
    profile_strategy_selection_mode = str(
        adaptive_profile_runtime.get("strategy_selection_mode", "")
    ).strip().lower()
    if profile_strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
        profile_strategy_selection_mode = ""
    requested_strategy_selection_mode = str(request.strategy_selection_mode or "").strip().lower()
    if requested_strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
        requested_strategy_selection_mode = ""
    effective_strategy_selection_mode = (
        profile_strategy_selection_mode
        or requested_strategy_selection_mode
        or str(aos_applied.get("strategy_selection_mode", "adaptive_top_n")).strip().lower()
        or "adaptive_top_n"
    )
    try:
        profile_max_active_strategies = int(adaptive_profile_runtime.get("max_active_strategies", 0))
    except (TypeError, ValueError):
        profile_max_active_strategies = 0
    try:
        requested_max_active_strategies = (
            int(request.max_active_strategies) if request.max_active_strategies is not None else 0
        )
    except (TypeError, ValueError):
        requested_max_active_strategies = 0
    try:
        aos_max_active_strategies = int(aos_applied.get("max_active_strategies", 3))
    except (TypeError, ValueError):
        aos_max_active_strategies = 3
    effective_max_active_strategies = (
        profile_max_active_strategies
        or requested_max_active_strategies
        or aos_max_active_strategies
        or 3
    )
    effective_max_active_strategies = max(1, min(20, effective_max_active_strategies))

    positioning_cfg_requested = bool(request.apply_positioning_config_on_start)
    positioning_cfg = (
        dict(aos_applied.get("positioning", {}))
        if positioning_cfg_requested and isinstance(aos_applied.get("positioning"), dict)
        else {}
    )

    def _coerce_bool(value: Any, *, default: Optional[bool] = None) -> Optional[bool]:
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

    def _resolve_positioning_float(
        *,
        request_value: Any,
        request_default: float,
        positioning_key: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        runtime_key: Optional[str] = None,
        runtime_positive_only: bool = False,
    ) -> Tuple[float, str]:
        source = "request"
        try:
            resolved = float(request_value)
        except (TypeError, ValueError):
            resolved = float(request_default)
            source = "default"

        if abs(resolved - float(request_default)) < 1e-12 and positioning_cfg:
            raw = positioning_cfg.get(positioning_key)
            if raw is not None:
                try:
                    resolved = float(raw)
                    source = "positioning_config"
                except (TypeError, ValueError):
                    pass

        if runtime_key:
            try:
                runtime_value = float(adaptive_profile_runtime.get(runtime_key, 0.0) or 0.0)
            except (TypeError, ValueError):
                runtime_value = 0.0
            runtime_valid = runtime_value > 0 if runtime_positive_only else abs(runtime_value) > 1e-12
            if runtime_valid:
                resolved = runtime_value
                source = "adaptive_profile"

        if min_value is not None:
            resolved = max(min_value, resolved)
        if max_value is not None:
            resolved = min(max_value, resolved)
        return resolved, source

    def _resolve_positioning_int(
        *,
        request_value: Any,
        request_default: int,
        positioning_key: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        runtime_key: Optional[str] = None,
        runtime_positive_only: bool = False,
    ) -> Tuple[int, str]:
        source = "request"
        try:
            resolved = int(request_value)
        except (TypeError, ValueError):
            resolved = int(request_default)
            source = "default"

        if resolved == int(request_default) and positioning_cfg:
            raw = positioning_cfg.get(positioning_key)
            if raw is not None:
                try:
                    resolved = int(raw)
                    source = "positioning_config"
                except (TypeError, ValueError):
                    pass

        if runtime_key:
            try:
                runtime_value = int(adaptive_profile_runtime.get(runtime_key, 0) or 0)
            except (TypeError, ValueError):
                runtime_value = 0
            runtime_valid = runtime_value > 0 if runtime_positive_only else runtime_value != 0
            if runtime_valid:
                resolved = runtime_value
                source = "adaptive_profile"

        if min_value is not None:
            resolved = max(min_value, resolved)
        if max_value is not None:
            resolved = min(max_value, resolved)
        return resolved, source

    def _resolve_positioning_bool(
        *,
        request_value: Any,
        request_default: bool,
        positioning_key: str,
        runtime_key: Optional[str] = None,
    ) -> Tuple[bool, str]:
        source = "request"
        resolved = _coerce_bool(request_value, default=request_default)
        if resolved is None:
            resolved = request_default
            source = "default"
        if resolved == bool(request_default) and positioning_cfg and positioning_key in positioning_cfg:
            positioned = _coerce_bool(positioning_cfg.get(positioning_key), default=None)
            if positioned is not None:
                resolved = positioned
                source = "positioning_config"
        if runtime_key:
            runtime_bool = _coerce_bool(adaptive_profile_runtime.get(runtime_key), default=None)
            if runtime_bool is not None:
                resolved = runtime_bool
                source = "adaptive_profile"
        return bool(resolved), source

    def _resolve_stop_loss_mode(
        *,
        request_mode: Any,
        request_default: str = "strategy",
        positioning_key: str = "stop_loss_mode",
    ) -> Tuple[str, str]:
        valid_modes = {"strategy", "fixed", "capped"}
        source = "request"
        normalized_default = str(request_default).strip().lower() or "strategy"
        mode = str(request_mode or normalized_default).strip().lower()
        if mode not in valid_modes:
            mode = normalized_default
            source = "default"
        if mode == normalized_default and positioning_cfg:
            positioned_mode = str(positioning_cfg.get(positioning_key, "")).strip().lower()
            if positioned_mode in valid_modes:
                mode = positioned_mode
                source = "positioning_config"
        return mode, source

    effective_risk_per_trade_pct, risk_per_trade_source = _resolve_positioning_float(
        request_value=request.risk_per_trade_pct,
        request_default=1.0,
        positioning_key="risk_per_trade_pct",
        min_value=0.1,
    )
    effective_max_position_notional_pct, max_position_notional_source = _resolve_positioning_float(
        request_value=request.max_position_notional_pct,
        request_default=100.0,
        positioning_key="max_position_notional_pct",
        min_value=1.0,
    )
    effective_max_fill_participation_rate, max_fill_participation_source = _resolve_positioning_float(
        request_value=request.max_fill_participation_rate,
        request_default=0.20,
        positioning_key="max_fill_participation_rate",
        min_value=0.01,
        max_value=1.0,
    )
    effective_min_fill_ratio, min_fill_ratio_source = _resolve_positioning_float(
        request_value=request.min_fill_ratio,
        request_default=0.35,
        positioning_key="min_fill_ratio",
        min_value=0.01,
        max_value=1.0,
    )
    effective_enable_partial_take_profit, partial_take_profit_enabled_source = _resolve_positioning_bool(
        request_value=request.enable_partial_take_profit,
        request_default=True,
        positioning_key="enable_partial_take_profit",
    )
    effective_partial_take_profit_rr, partial_take_profit_rr_source = _resolve_positioning_float(
        request_value=request.partial_take_profit_rr,
        request_default=1.0,
        positioning_key="partial_take_profit_rr",
        min_value=0.25,
    )
    effective_partial_take_profit_fraction, partial_take_profit_fraction_source = _resolve_positioning_float(
        request_value=request.partial_take_profit_fraction,
        request_default=0.5,
        positioning_key="partial_take_profit_fraction",
        min_value=0.05,
        max_value=0.95,
    )
    effective_trailing_activation_pct, trailing_activation_source = _resolve_positioning_float(
        request_value=request.trailing_activation_pct,
        request_default=0.15,
        positioning_key="trailing_activation_pct",
        min_value=0.0,
    )
    effective_break_even_buffer_pct, break_even_buffer_source = _resolve_positioning_float(
        request_value=request.break_even_buffer_pct,
        request_default=0.03,
        positioning_key="break_even_buffer_pct",
        min_value=0.0,
    )
    effective_break_even_min_hold_bars, break_even_min_hold_source = _resolve_positioning_int(
        request_value=request.break_even_min_hold_bars,
        request_default=2,
        positioning_key="break_even_min_hold_bars",
        min_value=1,
    )
    effective_trailing_enabled_in_choppy, trailing_enabled_in_choppy_source = _resolve_positioning_bool(
        request_value=request.trailing_enabled_in_choppy,
        request_default=False,
        positioning_key="trailing_enabled_in_choppy",
    )
    effective_time_exit_bars, time_exit_source = _resolve_positioning_int(
        request_value=request.time_exit_bars,
        request_default=40,
        positioning_key="time_exit_bars",
        min_value=1,
        runtime_key="time_exit_bars",
        runtime_positive_only=True,
    )
    effective_adverse_flow_exit_enabled, adverse_flow_exit_enabled_source = _resolve_positioning_bool(
        request_value=request.adverse_flow_exit_enabled,
        request_default=True,
        positioning_key="adverse_flow_exit_enabled",
    )
    effective_adverse_flow_threshold, adverse_flow_threshold_source = _resolve_positioning_float(
        request_value=request.adverse_flow_threshold,
        request_default=0.12,
        positioning_key="adverse_flow_threshold",
        min_value=0.02,
    )
    effective_adverse_flow_min_hold_bars, adverse_flow_min_hold_source = _resolve_positioning_int(
        request_value=request.adverse_flow_min_hold_bars,
        request_default=3,
        positioning_key="adverse_flow_min_hold_bars",
        min_value=1,
    )
    effective_stop_loss_mode, stop_loss_mode_source = _resolve_stop_loss_mode(
        request_mode=request.stop_loss_mode
    )
    effective_fixed_stop_loss_pct, fixed_stop_loss_source = _resolve_positioning_float(
        request_value=request.fixed_stop_loss_pct,
        request_default=0.0,
        positioning_key="fixed_stop_loss_pct",
        min_value=0.0,
    )

    def _resolve_adverse_flow_threshold(
        *,
        request_value: Any,
        request_default: float,
        positioning_key: str,
        aos_key: str,
        runtime_key: str,
    ) -> Tuple[float, str]:
        source = "request"
        try:
            resolved = float(request_value)
        except (TypeError, ValueError):
            resolved = request_default
            source = "default"
        if abs(resolved - request_default) < 1e-12:
            if positioning_cfg and positioning_key in positioning_cfg:
                try:
                    resolved = float(positioning_cfg.get(positioning_key))
                    source = "positioning_config"
                except (TypeError, ValueError):
                    pass
            if source in {"request", "default"}:
                try:
                    resolved = float(aos_applied.get(aos_key, request_default))
                    source = "aos_config"
                except (TypeError, ValueError):
                    resolved = request_default
                    source = "default"
        try:
            runtime_value = float(adaptive_profile_runtime.get(runtime_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            runtime_value = 0.0
        if runtime_value > 0:
            resolved = runtime_value
            source = "adaptive_profile"
        return max(0.02, resolved), source

    effective_adverse_flow_consistency_threshold, adverse_flow_consistency_source = (
        _resolve_adverse_flow_threshold(
            request_value=request.adverse_flow_consistency_threshold,
            request_default=0.45,
            positioning_key="adverse_flow_consistency_threshold",
            aos_key="adverse_flow_consistency_threshold",
            runtime_key="adverse_flow_consistency_threshold",
        )
    )
    effective_adverse_book_pressure_threshold, adverse_book_pressure_source = (
        _resolve_adverse_flow_threshold(
            request_value=request.adverse_book_pressure_threshold,
            request_default=0.15,
            positioning_key="adverse_book_pressure_threshold",
            aos_key="adverse_book_pressure_threshold",
            runtime_key="adverse_book_pressure_threshold",
        )
    )

    if int(request.l2_lookback_bars) != 3:
        l2_lookback_bars = max(1, int(request.l2_lookback_bars))
    else:
        try:
            l2_lookback_bars = max(1, int(aos_l2_cfg.get("lookback_bars", request.l2_lookback_bars)))
        except (TypeError, ValueError):
            l2_lookback_bars = max(1, int(request.l2_lookback_bars))

    return {
        "requested_l2_only": requested_l2_only,
        "requested_l2_confirm": requested_l2_confirm,
        "l2_min_delta": l2_min_delta,
        "l2_min_imbalance": l2_min_imbalance,
        "l2_min_iceberg_bias": l2_min_iceberg_bias,
        "l2_lookback_bars": l2_lookback_bars,
        "l2_min_participation_ratio": l2_min_participation_ratio,
        "l2_min_directional_consistency": l2_min_directional_consistency,
        "l2_min_signed_aggression": l2_min_signed_aggression,
        "effective_strategy_selection_mode": effective_strategy_selection_mode,
        "effective_max_active_strategies": effective_max_active_strategies,
        "positioning_cfg_requested": positioning_cfg_requested,
        "positioning_cfg": positioning_cfg,
        "effective_risk_per_trade_pct": effective_risk_per_trade_pct,
        "risk_per_trade_source": risk_per_trade_source,
        "effective_max_position_notional_pct": effective_max_position_notional_pct,
        "max_position_notional_source": max_position_notional_source,
        "effective_max_fill_participation_rate": effective_max_fill_participation_rate,
        "max_fill_participation_source": max_fill_participation_source,
        "effective_min_fill_ratio": effective_min_fill_ratio,
        "min_fill_ratio_source": min_fill_ratio_source,
        "effective_enable_partial_take_profit": effective_enable_partial_take_profit,
        "partial_take_profit_enabled_source": partial_take_profit_enabled_source,
        "effective_partial_take_profit_rr": effective_partial_take_profit_rr,
        "partial_take_profit_rr_source": partial_take_profit_rr_source,
        "effective_partial_take_profit_fraction": effective_partial_take_profit_fraction,
        "partial_take_profit_fraction_source": partial_take_profit_fraction_source,
        "effective_trailing_activation_pct": effective_trailing_activation_pct,
        "trailing_activation_source": trailing_activation_source,
        "effective_break_even_buffer_pct": effective_break_even_buffer_pct,
        "break_even_buffer_source": break_even_buffer_source,
        "effective_break_even_min_hold_bars": effective_break_even_min_hold_bars,
        "break_even_min_hold_source": break_even_min_hold_source,
        "effective_trailing_enabled_in_choppy": effective_trailing_enabled_in_choppy,
        "trailing_enabled_in_choppy_source": trailing_enabled_in_choppy_source,
        "effective_time_exit_bars": effective_time_exit_bars,
        "time_exit_source": time_exit_source,
        "effective_adverse_flow_exit_enabled": effective_adverse_flow_exit_enabled,
        "adverse_flow_exit_enabled_source": adverse_flow_exit_enabled_source,
        "effective_adverse_flow_threshold": effective_adverse_flow_threshold,
        "adverse_flow_threshold_source": adverse_flow_threshold_source,
        "effective_adverse_flow_min_hold_bars": effective_adverse_flow_min_hold_bars,
        "adverse_flow_min_hold_source": adverse_flow_min_hold_source,
        "effective_stop_loss_mode": effective_stop_loss_mode,
        "stop_loss_mode_source": stop_loss_mode_source,
        "effective_fixed_stop_loss_pct": effective_fixed_stop_loss_pct,
        "fixed_stop_loss_source": fixed_stop_loss_source,
        "effective_adverse_flow_consistency_threshold": effective_adverse_flow_consistency_threshold,
        "adverse_flow_consistency_source": adverse_flow_consistency_source,
        "effective_adverse_book_pressure_threshold": effective_adverse_book_pressure_threshold,
        "adverse_book_pressure_source": adverse_book_pressure_source,
    }
