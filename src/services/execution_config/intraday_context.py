from __future__ import annotations

from typing import Any, Dict

from src.services.execution_config.helpers import coerce_bool


def _int_min(value: Any, *, default: int, min_value: int) -> int:
    try:
        return max(min_value, int(value))
    except (TypeError, ValueError):
        return default


def _int_clamp(value: Any, *, default: int, min_value: int, max_value: int) -> int:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        resolved = default
    return max(min_value, min(max_value, resolved))


def _float_clamp(
    value: Any,
    *,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        resolved = default
    if min_value is not None:
        resolved = max(min_value, resolved)
    if max_value is not None:
        resolved = min(max_value, resolved)
    return resolved


def _bool_default(value: Any, *, default: bool) -> bool:
    resolved = coerce_bool(value, default=default)
    if resolved is None:
        return default
    return bool(resolved)


def resolve_intraday_levels_config(request: Any) -> Dict[str, Any]:
    return {
        "intraday_levels_enabled": _bool_default(
            getattr(request, "intraday_levels_enabled", True),
            default=True,
        ),
        "intraday_levels_swing_left_bars": _int_min(
            getattr(request, "intraday_levels_swing_left_bars", 2),
            default=2,
            min_value=1,
        ),
        "intraday_levels_swing_right_bars": _int_min(
            getattr(request, "intraday_levels_swing_right_bars", 2),
            default=2,
            min_value=1,
        ),
        "intraday_levels_test_tolerance_pct": _float_clamp(
            getattr(request, "intraday_levels_test_tolerance_pct", 0.08),
            default=0.08,
            min_value=0.0,
        ),
        "intraday_levels_break_tolerance_pct": _float_clamp(
            getattr(request, "intraday_levels_break_tolerance_pct", 0.05),
            default=0.05,
            min_value=0.0,
        ),
        "intraday_levels_breakout_volume_lookback": _int_min(
            getattr(request, "intraday_levels_breakout_volume_lookback", 20),
            default=20,
            min_value=2,
        ),
        "intraday_levels_breakout_volume_multiplier": _float_clamp(
            getattr(request, "intraday_levels_breakout_volume_multiplier", 1.2),
            default=1.2,
            min_value=1.0,
        ),
        "intraday_levels_volume_profile_bin_size_pct": _float_clamp(
            getattr(request, "intraday_levels_volume_profile_bin_size_pct", 0.05),
            default=0.05,
            min_value=0.01,
        ),
        "intraday_levels_value_area_pct": _float_clamp(
            getattr(request, "intraday_levels_value_area_pct", 0.70),
            default=0.70,
            min_value=0.5,
            max_value=0.95,
        ),
        "intraday_levels_entry_quality_enabled": _bool_default(
            getattr(request, "intraday_levels_entry_quality_enabled", True),
            default=True,
        ),
        "intraday_levels_min_levels_for_context": _int_min(
            getattr(request, "intraday_levels_min_levels_for_context", 1),
            default=1,
            min_value=1,
        ),
        "intraday_levels_entry_tolerance_pct": _float_clamp(
            getattr(request, "intraday_levels_entry_tolerance_pct", 0.10),
            default=0.10,
            min_value=0.01,
        ),
        "intraday_levels_break_cooldown_bars": _int_min(
            getattr(request, "intraday_levels_break_cooldown_bars", 3),
            default=3,
            min_value=1,
        ),
        "intraday_levels_rotation_max_tests": _int_min(
            getattr(request, "intraday_levels_rotation_max_tests", 2),
            default=2,
            min_value=1,
        ),
        "intraday_levels_rotation_volume_max_ratio": _float_clamp(
            getattr(request, "intraday_levels_rotation_volume_max_ratio", 0.95),
            default=0.95,
            min_value=0.1,
            max_value=2.0,
        ),
        "intraday_levels_recent_bounce_lookback_bars": _int_min(
            getattr(request, "intraday_levels_recent_bounce_lookback_bars", 6),
            default=6,
            min_value=1,
        ),
        "intraday_levels_require_recent_bounce_for_mean_reversion": _bool_default(
            getattr(
                request,
                "intraday_levels_require_recent_bounce_for_mean_reversion",
                True,
            ),
            default=True,
        ),
        "intraday_levels_momentum_break_max_age_bars": _int_min(
            getattr(request, "intraday_levels_momentum_break_max_age_bars", 3),
            default=3,
            min_value=1,
        ),
        "intraday_levels_momentum_min_room_pct": _float_clamp(
            getattr(request, "intraday_levels_momentum_min_room_pct", 0.15),
            default=0.15,
            min_value=0.01,
        ),
        "intraday_levels_momentum_min_broken_ratio": _float_clamp(
            getattr(request, "intraday_levels_momentum_min_broken_ratio", 0.30),
            default=0.30,
            min_value=0.0,
            max_value=1.0,
        ),
        "intraday_levels_min_confluence_score": _int_min(
            getattr(request, "intraday_levels_min_confluence_score", 1),
            default=1,
            min_value=1,
        ),
        "intraday_levels_memory_enabled": _bool_default(
            getattr(request, "intraday_levels_memory_enabled", True),
            default=True,
        ),
        "intraday_levels_memory_min_tests": _int_min(
            getattr(request, "intraday_levels_memory_min_tests", 2),
            default=2,
            min_value=1,
        ),
        "intraday_levels_memory_max_age_days": _int_min(
            getattr(request, "intraday_levels_memory_max_age_days", 5),
            default=5,
            min_value=1,
        ),
        "intraday_levels_memory_decay_after_days": _int_min(
            getattr(request, "intraday_levels_memory_decay_after_days", 2),
            default=2,
            min_value=1,
        ),
        "intraday_levels_memory_decay_weight": _float_clamp(
            getattr(request, "intraday_levels_memory_decay_weight", 0.50),
            default=0.50,
            min_value=0.1,
            max_value=1.0,
        ),
        "intraday_levels_memory_max_levels": _int_min(
            getattr(request, "intraday_levels_memory_max_levels", 12),
            default=12,
            min_value=1,
        ),
        "intraday_levels_opening_range_enabled": _bool_default(
            getattr(request, "intraday_levels_opening_range_enabled", True),
            default=True,
        ),
        "intraday_levels_opening_range_minutes": _int_min(
            getattr(request, "intraday_levels_opening_range_minutes", 30),
            default=30,
            min_value=5,
        ),
        "intraday_levels_opening_range_break_tolerance_pct": _float_clamp(
            getattr(request, "intraday_levels_opening_range_break_tolerance_pct", 0.05),
            default=0.05,
            min_value=0.01,
        ),
        "intraday_levels_poc_migration_enabled": _bool_default(
            getattr(request, "intraday_levels_poc_migration_enabled", True),
            default=True,
        ),
        "intraday_levels_poc_migration_interval_bars": _int_min(
            getattr(request, "intraday_levels_poc_migration_interval_bars", 30),
            default=30,
            min_value=1,
        ),
        "intraday_levels_poc_migration_trend_threshold_pct": _float_clamp(
            getattr(request, "intraday_levels_poc_migration_trend_threshold_pct", 0.20),
            default=0.20,
            min_value=0.01,
        ),
        "intraday_levels_poc_migration_range_threshold_pct": _float_clamp(
            getattr(request, "intraday_levels_poc_migration_range_threshold_pct", 0.10),
            default=0.10,
            min_value=0.01,
        ),
        "intraday_levels_composite_profile_enabled": _bool_default(
            getattr(request, "intraday_levels_composite_profile_enabled", True),
            default=True,
        ),
        "intraday_levels_composite_profile_days": _int_min(
            getattr(request, "intraday_levels_composite_profile_days", 3),
            default=3,
            min_value=1,
        ),
        "intraday_levels_composite_profile_current_day_weight": _float_clamp(
            getattr(
                request, "intraday_levels_composite_profile_current_day_weight", 1.0
            ),
            default=1.0,
            min_value=0.1,
        ),
        "intraday_levels_spike_detection_enabled": _bool_default(
            getattr(request, "intraday_levels_spike_detection_enabled", True),
            default=True,
        ),
        "intraday_levels_spike_min_wick_ratio": _float_clamp(
            getattr(request, "intraday_levels_spike_min_wick_ratio", 0.60),
            default=0.60,
            min_value=0.4,
            max_value=0.95,
        ),
        "intraday_levels_prior_day_anchors_enabled": _bool_default(
            getattr(request, "intraday_levels_prior_day_anchors_enabled", True),
            default=True,
        ),
        "intraday_levels_gap_analysis_enabled": _bool_default(
            getattr(request, "intraday_levels_gap_analysis_enabled", True),
            default=True,
        ),
        "intraday_levels_gap_min_pct": _float_clamp(
            getattr(request, "intraday_levels_gap_min_pct", 0.30),
            default=0.30,
            min_value=0.0,
        ),
        "intraday_levels_gap_momentum_threshold_pct": _float_clamp(
            getattr(request, "intraday_levels_gap_momentum_threshold_pct", 2.0),
            default=2.0,
            min_value=0.1,
        ),
        "intraday_levels_rvol_filter_enabled": _bool_default(
            getattr(request, "intraday_levels_rvol_filter_enabled", True),
            default=True,
        ),
        "intraday_levels_rvol_lookback_bars": _int_min(
            getattr(request, "intraday_levels_rvol_lookback_bars", 20),
            default=20,
            min_value=5,
        ),
        "intraday_levels_rvol_min_threshold": _float_clamp(
            getattr(request, "intraday_levels_rvol_min_threshold", 0.80),
            default=0.80,
            min_value=0.0,
        ),
        "intraday_levels_rvol_strong_threshold": _float_clamp(
            getattr(request, "intraday_levels_rvol_strong_threshold", 1.50),
            default=1.50,
            min_value=0.1,
        ),
        "intraday_levels_adaptive_window_enabled": _bool_default(
            getattr(request, "intraday_levels_adaptive_window_enabled", True),
            default=True,
        ),
        "intraday_levels_adaptive_window_min_bars": _int_min(
            getattr(request, "intraday_levels_adaptive_window_min_bars", 6),
            default=6,
            min_value=1,
        ),
        "intraday_levels_adaptive_window_rvol_threshold": _float_clamp(
            getattr(request, "intraday_levels_adaptive_window_rvol_threshold", 0.5),
            default=0.5,
            min_value=0.0,
        ),
        "intraday_levels_adaptive_window_atr_ratio_max": _float_clamp(
            getattr(request, "intraday_levels_adaptive_window_atr_ratio_max", 1.5),
            default=1.5,
            min_value=0.1,
        ),
        "intraday_levels_micro_confirmation_enabled": _bool_default(
            getattr(request, "intraday_levels_micro_confirmation_enabled", False),
            default=False,
        ),
        "intraday_levels_micro_confirmation_bars": _int_min(
            getattr(request, "intraday_levels_micro_confirmation_bars", 2),
            default=2,
            min_value=1,
        ),
        "intraday_levels_micro_confirmation_disable_for_sweep": _bool_default(
            getattr(
                request,
                "intraday_levels_micro_confirmation_disable_for_sweep",
                False,
            ),
            default=False,
        ),
        "intraday_levels_micro_confirmation_sweep_bars": _int_min(
            getattr(request, "intraday_levels_micro_confirmation_sweep_bars", 0),
            default=0,
            min_value=0,
        ),
        "intraday_levels_micro_confirmation_require_intrabar": _bool_default(
            getattr(
                request,
                "intraday_levels_micro_confirmation_require_intrabar",
                False,
            ),
            default=False,
        ),
        "intraday_levels_micro_confirmation_intrabar_window_seconds": _int_clamp(
            getattr(
                request,
                "intraday_levels_micro_confirmation_intrabar_window_seconds",
                5,
            ),
            default=5,
            min_value=1,
            max_value=60,
        ),
        "intraday_levels_micro_confirmation_intrabar_min_coverage_points": _int_min(
            getattr(
                request,
                "intraday_levels_micro_confirmation_intrabar_min_coverage_points",
                3,
            ),
            default=3,
            min_value=0,
        ),
        "intraday_levels_micro_confirmation_intrabar_min_move_pct": _float_clamp(
            getattr(
                request,
                "intraday_levels_micro_confirmation_intrabar_min_move_pct",
                0.02,
            ),
            default=0.02,
            min_value=0.0,
        ),
        "intraday_levels_micro_confirmation_intrabar_min_push_ratio": _float_clamp(
            getattr(
                request,
                "intraday_levels_micro_confirmation_intrabar_min_push_ratio",
                0.10,
            ),
            default=0.10,
            min_value=0.0,
            max_value=1.0,
        ),
        "intraday_levels_micro_confirmation_intrabar_max_spread_bps": _float_clamp(
            getattr(
                request,
                "intraday_levels_micro_confirmation_intrabar_max_spread_bps",
                12.0,
            ),
            default=12.0,
            min_value=0.0,
        ),
        "intraday_levels_confluence_sizing_enabled": _bool_default(
            getattr(request, "intraday_levels_confluence_sizing_enabled", False),
            default=False,
        ),
        "liquidity_sweep_detection_enabled": _bool_default(
            getattr(request, "liquidity_sweep_detection_enabled", False),
            default=False,
        ),
        "sweep_min_aggression_z": _float_clamp(
            getattr(request, "sweep_min_aggression_z", -2.0),
            default=-2.0,
        ),
        "sweep_min_book_pressure_z": _float_clamp(
            getattr(request, "sweep_min_book_pressure_z", 1.5),
            default=1.5,
        ),
        "sweep_max_price_change_pct": _float_clamp(
            getattr(request, "sweep_max_price_change_pct", 0.05),
            default=0.05,
            min_value=0.0,
        ),
    }


def resolve_context_risk_config(request: Any) -> Dict[str, Any]:
    context_risk_min_level_tests_for_sl = 1
    try:
        context_risk_min_level_tests_for_sl = max(
            0, int(getattr(request, "context_risk_min_level_tests_for_sl", 2))
        )
    except (TypeError, ValueError):
        context_risk_min_level_tests_for_sl = 1

    return {
        "context_aware_risk_enabled": _bool_default(
            getattr(request, "context_aware_risk_enabled", False),
            default=False,
        ),
        "context_risk_sl_buffer_pct": _float_clamp(
            getattr(request, "context_risk_sl_buffer_pct", 0.10),
            default=0.10,
            min_value=0.0,
        ),
        "context_risk_min_sl_pct": _float_clamp(
            getattr(request, "context_risk_min_sl_pct", 0.30),
            default=0.30,
            min_value=0.0,
        ),
        "context_risk_min_room_pct": _float_clamp(
            getattr(request, "context_risk_min_room_pct", 0.08),
            default=0.08,
            min_value=0.0,
        ),
        "context_risk_min_effective_rr": _float_clamp(
            getattr(request, "context_risk_min_effective_rr", 1.0),
            default=1.0,
            min_value=0.0,
        ),
        "context_risk_trailing_tighten_zone": _float_clamp(
            getattr(request, "context_risk_trailing_tighten_zone", 0.2),
            default=0.2,
            min_value=0.0,
            max_value=1.0,
        ),
        "context_risk_trailing_tighten_factor": _float_clamp(
            getattr(request, "context_risk_trailing_tighten_factor", 0.5),
            default=0.5,
            min_value=0.0,
            max_value=1.0,
        ),
        "context_risk_level_trail_enabled": _bool_default(
            getattr(request, "context_risk_level_trail_enabled", True),
            default=True,
        ),
        "context_risk_max_anchor_search_pct": _float_clamp(
            getattr(request, "context_risk_max_anchor_search_pct", 0.8),
            default=0.8,
            min_value=0.1,
        ),
        "context_risk_min_level_tests_for_sl": context_risk_min_level_tests_for_sl,
        "sweep_atr_buffer_multiplier": _float_clamp(
            getattr(request, "sweep_atr_buffer_multiplier", 0.5),
            default=0.5,
            min_value=0.0,
        ),
    }
