from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from src.services.trade_eval_mode_service import resolve_trade_eval_mode_from_settings


@dataclass(frozen=True)
class ExecutionPayloadInputs:
    request: Any
    execution_cfg: Dict[str, Any]
    aos_applied: Dict[str, Any]
    momentum_diversification_source: str
    effective_momentum_diversification: Optional[Dict[str, Any]]
    effective_intrabar_execution_recalc_1s: bool
    effective_intrabar_eval_step_seconds: int
    effective_cold_start_each_day: bool
    comparable_mode: bool
    effective_reset_scope: str
    apply_aos_optimizations_on_start: bool
    effective_strategy_selection_mode: str
    effective_max_active_strategies: int
    all_enabled_remote_sync: Optional[Dict[str, Any]]
    l2_stats: Dict[str, Any]
    l2_sessionized_by_market_day: bool
    requested_l2_only_raw: bool
    requested_l2_confirm_raw: bool
    l2_guard_reason: Optional[str]
    effective_l2_confirm: bool
    l2_auto_enabled_by_sweep: bool
    l2_auto_enabled_source: str


@dataclass(frozen=True)
class ExecutionPayloadResult:
    execution_config_payload: Dict[str, Any]
    l2_applied_payload: Dict[str, Any]


def _build_l2_thresholds(execution_cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "l2_min_delta": float(execution_cfg["l2_min_delta"]),
        "l2_min_imbalance": float(execution_cfg["l2_min_imbalance"]),
        "l2_min_iceberg_bias": float(execution_cfg["l2_min_iceberg_bias"]),
        "l2_lookback_bars": int(execution_cfg["l2_lookback_bars"]),
        "l2_min_participation_ratio": float(
            execution_cfg["l2_min_participation_ratio"]
        ),
        "l2_min_directional_consistency": float(
            execution_cfg["l2_min_directional_consistency"]
        ),
        "l2_min_signed_aggression": float(execution_cfg["l2_min_signed_aggression"]),
    }


def _is_options_flow_alpha_enabled(aos_applied: Dict[str, Any]) -> bool:
    if not isinstance(aos_applied, dict):
        return False
    positioning = aos_applied.get("positioning")
    if isinstance(positioning, dict):
        return bool(positioning.get("options_flow_alpha_enabled", False))
    return bool(aos_applied.get("options_flow_alpha_enabled", False))


def _build_core_execution_payload(execution_cfg: Dict[str, Any]) -> Dict[str, Any]:
    positioning_cfg = dict(execution_cfg["positioning_cfg"])
    return {
        "positioning_config_enabled": bool(execution_cfg["positioning_cfg_requested"]),
        "positioning_config_applied": bool(positioning_cfg),
        "risk_per_trade_pct": float(execution_cfg["effective_risk_per_trade_pct"]),
        "risk_per_trade_pct_source": str(execution_cfg["risk_per_trade_source"]),
        "max_position_notional_pct": float(
            execution_cfg["effective_max_position_notional_pct"]
        ),
        "max_position_notional_pct_source": str(
            execution_cfg["max_position_notional_source"]
        ),
        "max_fill_participation_rate": float(
            execution_cfg["effective_max_fill_participation_rate"]
        ),
        "max_fill_participation_rate_source": str(
            execution_cfg["max_fill_participation_source"]
        ),
        "min_fill_ratio": float(execution_cfg["effective_min_fill_ratio"]),
        "min_fill_ratio_source": str(execution_cfg["min_fill_ratio_source"]),
        "enable_partial_take_profit": bool(
            execution_cfg["effective_enable_partial_take_profit"]
        ),
        "enable_partial_take_profit_source": str(
            execution_cfg["partial_take_profit_enabled_source"]
        ),
        "partial_take_profit_rr": float(
            execution_cfg["effective_partial_take_profit_rr"]
        ),
        "partial_take_profit_rr_source": str(
            execution_cfg["partial_take_profit_rr_source"]
        ),
        "partial_take_profit_fraction": float(
            execution_cfg["effective_partial_take_profit_fraction"]
        ),
        "partial_take_profit_fraction_source": str(
            execution_cfg["partial_take_profit_fraction_source"]
        ),
        "partial_protect_min_mfe_r": float(
            execution_cfg["effective_partial_protect_min_mfe_r"]
        ),
        "partial_protect_min_mfe_r_source": str(
            execution_cfg["partial_protect_min_mfe_r_source"]
        ),
        "trailing_stop_pct": float(execution_cfg["effective_trailing_stop_pct"]),
        "trailing_stop_pct_source": str(execution_cfg["trailing_stop_pct_source"]),
        "global_exit_rr_ratio": float(execution_cfg["effective_global_exit_rr_ratio"]),
        "global_exit_rr_ratio_source": str(
            execution_cfg["global_exit_rr_ratio_source"]
        ),
        "global_risk_atr_stop_multiplier": float(
            execution_cfg["effective_global_risk_atr_stop_multiplier"]
        ),
        "global_risk_atr_stop_multiplier_source": str(
            execution_cfg["global_risk_atr_stop_multiplier_source"]
        ),
        "global_risk_volume_stop_pct": float(
            execution_cfg["effective_global_risk_volume_stop_pct"]
        ),
        "global_risk_volume_stop_pct_source": str(
            execution_cfg["global_risk_volume_stop_pct_source"]
        ),
        "global_risk_min_stop_loss_pct": float(
            execution_cfg["effective_global_risk_min_stop_loss_pct"]
        ),
        "global_risk_min_stop_loss_pct_source": str(
            execution_cfg["global_risk_min_stop_loss_pct_source"]
        ),
        "trailing_activation_pct": float(
            execution_cfg["effective_trailing_activation_pct"]
        ),
        "trailing_activation_pct_source": str(
            execution_cfg["trailing_activation_source"]
        ),
        "break_even_buffer_pct": float(
            execution_cfg["effective_break_even_buffer_pct"]
        ),
        "break_even_buffer_pct_source": str(execution_cfg["break_even_buffer_source"]),
        "break_even_min_hold_bars": int(
            execution_cfg["effective_break_even_min_hold_bars"]
        ),
        "break_even_min_hold_bars_source": str(
            execution_cfg["break_even_min_hold_source"]
        ),
        "break_even_activation_min_mfe_pct": float(
            execution_cfg["effective_break_even_activation_min_mfe_pct"]
        ),
        "break_even_activation_min_mfe_pct_source": str(
            execution_cfg["break_even_activation_min_mfe_source"]
        ),
        "break_even_activation_min_r": float(
            execution_cfg["effective_break_even_activation_min_r"]
        ),
        "break_even_activation_min_r_source": str(
            execution_cfg["break_even_activation_min_r_source"]
        ),
        "break_even_activation_min_r_trending_5m": float(
            execution_cfg["effective_break_even_activation_min_r_trending_5m"]
        ),
        "break_even_activation_min_r_trending_5m_source": str(
            execution_cfg["break_even_activation_min_r_trending_source"]
        ),
        "break_even_activation_min_r_choppy_5m": float(
            execution_cfg["effective_break_even_activation_min_r_choppy_5m"]
        ),
        "break_even_activation_min_r_choppy_5m_source": str(
            execution_cfg["break_even_activation_min_r_choppy_source"]
        ),
        "break_even_activation_use_levels": bool(
            execution_cfg["effective_break_even_activation_use_levels"]
        ),
        "break_even_activation_use_levels_source": str(
            execution_cfg["break_even_activation_use_levels_source"]
        ),
        "break_even_activation_use_l2": bool(
            execution_cfg["effective_break_even_activation_use_l2"]
        ),
        "break_even_activation_use_l2_source": str(
            execution_cfg["break_even_activation_use_l2_source"]
        ),
        "break_even_level_buffer_pct": float(
            execution_cfg["effective_break_even_level_buffer_pct"]
        ),
        "break_even_level_buffer_pct_source": str(
            execution_cfg["break_even_level_buffer_source"]
        ),
        "break_even_level_max_distance_pct": float(
            execution_cfg["effective_break_even_level_max_distance_pct"]
        ),
        "break_even_level_max_distance_pct_source": str(
            execution_cfg["break_even_level_max_distance_source"]
        ),
        "break_even_level_min_confluence": int(
            execution_cfg["effective_break_even_level_min_confluence"]
        ),
        "break_even_level_min_confluence_source": str(
            execution_cfg["break_even_level_min_confluence_source"]
        ),
        "break_even_level_min_tests": int(
            execution_cfg["effective_break_even_level_min_tests"]
        ),
        "break_even_level_min_tests_source": str(
            execution_cfg["break_even_level_min_tests_source"]
        ),
        "break_even_l2_signed_aggression_min": float(
            execution_cfg["effective_break_even_l2_signed_aggression_min"]
        ),
        "break_even_l2_signed_aggression_min_source": str(
            execution_cfg["break_even_l2_signed_source"]
        ),
        "break_even_l2_imbalance_min": float(
            execution_cfg["effective_break_even_l2_imbalance_min"]
        ),
        "break_even_l2_imbalance_min_source": str(
            execution_cfg["break_even_l2_imbalance_source"]
        ),
        "break_even_l2_book_pressure_min": float(
            execution_cfg["effective_break_even_l2_book_pressure_min"]
        ),
        "break_even_l2_book_pressure_min_source": str(
            execution_cfg["break_even_l2_book_source"]
        ),
        "break_even_l2_spread_bps_max": float(
            execution_cfg["effective_break_even_l2_spread_bps_max"]
        ),
        "break_even_l2_spread_bps_max_source": str(
            execution_cfg["break_even_l2_spread_source"]
        ),
        "break_even_costs_pct": float(execution_cfg["effective_break_even_costs_pct"]),
        "break_even_costs_pct_source": str(execution_cfg["break_even_costs_source"]),
        "break_even_min_buffer_pct": float(
            execution_cfg["effective_break_even_min_buffer_pct"]
        ),
        "break_even_min_buffer_pct_source": str(
            execution_cfg["break_even_min_buffer_source"]
        ),
        "break_even_atr_buffer_k": float(
            execution_cfg["effective_break_even_atr_buffer_k"]
        ),
        "break_even_atr_buffer_k_source": str(
            execution_cfg["break_even_atr_buffer_source"]
        ),
        "break_even_5m_atr_buffer_k": float(
            execution_cfg["effective_break_even_5m_atr_buffer_k"]
        ),
        "break_even_5m_atr_buffer_k_source": str(
            execution_cfg["break_even_5m_atr_buffer_source"]
        ),
        "break_even_tick_size": float(execution_cfg["effective_break_even_tick_size"]),
        "break_even_tick_size_source": str(
            execution_cfg["break_even_tick_size_source"]
        ),
        "break_even_min_tick_buffer": int(
            execution_cfg["effective_break_even_min_tick_buffer"]
        ),
        "break_even_min_tick_buffer_source": str(
            execution_cfg["break_even_min_tick_buffer_source"]
        ),
        "break_even_anti_spike_bars": int(
            execution_cfg["effective_break_even_anti_spike_bars"]
        ),
        "break_even_anti_spike_bars_source": str(
            execution_cfg["break_even_anti_spike_bars_source"]
        ),
        "break_even_anti_spike_hits_required": int(
            execution_cfg["effective_break_even_anti_spike_hits_required"]
        ),
        "break_even_anti_spike_hits_required_source": str(
            execution_cfg["break_even_anti_spike_hits_source"]
        ),
        "break_even_anti_spike_require_close_beyond": bool(
            execution_cfg["effective_break_even_anti_spike_require_close_beyond"]
        ),
        "break_even_anti_spike_require_close_beyond_source": str(
            execution_cfg["break_even_anti_spike_close_source"]
        ),
        "break_even_5m_no_go_proximity_pct": float(
            execution_cfg["effective_break_even_5m_no_go_proximity_pct"]
        ),
        "break_even_5m_no_go_proximity_pct_source": str(
            execution_cfg["break_even_5m_no_go_source"]
        ),
        "break_even_5m_mfe_atr_factor": float(
            execution_cfg["effective_break_even_5m_mfe_atr_factor"]
        ),
        "break_even_5m_mfe_atr_factor_source": str(
            execution_cfg["break_even_5m_mfe_atr_source"]
        ),
        "break_even_5m_l2_bias_threshold": float(
            execution_cfg["effective_break_even_5m_l2_bias_threshold"]
        ),
        "break_even_5m_l2_bias_threshold_source": str(
            execution_cfg["break_even_5m_l2_bias_source"]
        ),
        "break_even_5m_l2_bias_tighten_factor": float(
            execution_cfg["effective_break_even_5m_l2_bias_tighten_factor"]
        ),
        "break_even_5m_l2_bias_tighten_factor_source": str(
            execution_cfg["break_even_5m_l2_tighten_source"]
        ),
        "break_even_movement_formula_enabled": bool(
            execution_cfg["effective_break_even_movement_formula_enabled"]
        ),
        "break_even_movement_formula_enabled_source": str(
            execution_cfg["break_even_movement_formula_enabled_source"]
        ),
        "break_even_movement_formula": str(
            execution_cfg["effective_break_even_movement_formula"]
        ),
        "break_even_movement_formula_source": str(
            execution_cfg["break_even_movement_formula_source"]
        ),
        "break_even_proof_formula_enabled": bool(
            execution_cfg["effective_break_even_proof_formula_enabled"]
        ),
        "break_even_proof_formula_enabled_source": str(
            execution_cfg["break_even_proof_formula_enabled_source"]
        ),
        "break_even_proof_formula": str(
            execution_cfg["effective_break_even_proof_formula"]
        ),
        "break_even_proof_formula_source": str(
            execution_cfg["break_even_proof_formula_source"]
        ),
        "break_even_activation_formula_enabled": bool(
            execution_cfg["effective_break_even_activation_formula_enabled"]
        ),
        "break_even_activation_formula_enabled_source": str(
            execution_cfg["break_even_activation_formula_enabled_source"]
        ),
        "break_even_activation_formula": str(
            execution_cfg["effective_break_even_activation_formula"]
        ),
        "break_even_activation_formula_source": str(
            execution_cfg["break_even_activation_formula_source"]
        ),
        "break_even_trailing_handoff_formula_enabled": bool(
            execution_cfg["effective_break_even_trailing_handoff_formula_enabled"]
        ),
        "break_even_trailing_handoff_formula_enabled_source": str(
            execution_cfg["break_even_trailing_handoff_formula_enabled_source"]
        ),
        "break_even_trailing_handoff_formula": str(
            execution_cfg["effective_break_even_trailing_handoff_formula"]
        ),
        "break_even_trailing_handoff_formula_source": str(
            execution_cfg["break_even_trailing_handoff_formula_source"]
        ),
        "trailing_enabled_in_choppy": bool(
            execution_cfg["effective_trailing_enabled_in_choppy"]
        ),
        "trailing_enabled_in_choppy_source": str(
            execution_cfg["trailing_enabled_in_choppy_source"]
        ),
        "time_exit_bars": int(execution_cfg["effective_time_exit_bars"]),
        "time_exit_bars_source": str(execution_cfg["time_exit_source"]),
        "time_exit_formula_enabled": bool(
            execution_cfg["effective_time_exit_formula_enabled"]
        ),
        "time_exit_formula_enabled_source": str(
            execution_cfg["time_exit_formula_enabled_source"]
        ),
        "time_exit_formula": str(execution_cfg["effective_time_exit_formula"]),
        "time_exit_formula_source": str(execution_cfg["time_exit_formula_source"]),
        "adverse_flow_exit_enabled": bool(
            execution_cfg["effective_adverse_flow_exit_enabled"]
        ),
        "adverse_flow_exit_enabled_source": str(
            execution_cfg["adverse_flow_exit_enabled_source"]
        ),
        "adverse_flow_threshold": float(
            execution_cfg["effective_adverse_flow_threshold"]
        ),
        "adverse_flow_threshold_source": str(
            execution_cfg["adverse_flow_threshold_source"]
        ),
        "adverse_flow_min_hold_bars": int(
            execution_cfg["effective_adverse_flow_min_hold_bars"]
        ),
        "adverse_flow_min_hold_bars_source": str(
            execution_cfg["adverse_flow_min_hold_source"]
        ),
        "adverse_flow_consistency_threshold": float(
            execution_cfg["effective_adverse_flow_consistency_threshold"]
        ),
        "adverse_flow_consistency_threshold_source": str(
            execution_cfg["adverse_flow_consistency_source"]
        ),
        "adverse_book_pressure_threshold": float(
            execution_cfg["effective_adverse_book_pressure_threshold"]
        ),
        "adverse_book_pressure_threshold_source": str(
            execution_cfg["adverse_book_pressure_source"]
        ),
        "adverse_flow_exit_formula_enabled": bool(
            execution_cfg["effective_adverse_flow_exit_formula_enabled"]
        ),
        "adverse_flow_exit_formula_enabled_source": str(
            execution_cfg["adverse_flow_exit_formula_enabled_source"]
        ),
        "adverse_flow_exit_formula": str(
            execution_cfg["effective_adverse_flow_exit_formula"]
        ),
        "adverse_flow_exit_formula_source": str(
            execution_cfg["adverse_flow_exit_formula_source"]
        ),
        "stop_loss_mode": str(execution_cfg["effective_stop_loss_mode"]),
        "stop_loss_mode_source": str(execution_cfg["stop_loss_mode_source"]),
        "fixed_stop_loss_pct": float(execution_cfg["effective_fixed_stop_loss_pct"]),
        "fixed_stop_loss_pct_source": str(execution_cfg["fixed_stop_loss_source"]),
    }


def _build_runtime_execution_payload(inputs: ExecutionPayloadInputs) -> Dict[str, Any]:
    return {
        "regime_detection_minutes": int(
            inputs.execution_cfg.get(
                "effective_regime_detection_minutes",
                getattr(inputs.request, "regime_detection_minutes", 15),
            )
        ),
        "regime_detection_minutes_source": str(
            inputs.execution_cfg.get("regime_detection_minutes_source", "default")
        ),
        "regime_refresh_bars": int(
            inputs.execution_cfg.get(
                "effective_regime_refresh_bars",
                getattr(inputs.request, "regime_refresh_bars", 12),
            )
        ),
        "regime_refresh_bars_source": str(
            inputs.execution_cfg.get("regime_refresh_bars_source", "default")
        ),
        "intrabar_execution_recalc_1s": inputs.effective_intrabar_execution_recalc_1s,
        "intrabar_eval_step_seconds": int(inputs.effective_intrabar_eval_step_seconds),
        "trade_eval_mode": resolve_trade_eval_mode_from_settings(
            intrabar_enabled=inputs.effective_intrabar_execution_recalc_1s,
            intrabar_eval_step_seconds=inputs.effective_intrabar_eval_step_seconds,
        ),
        "cold_start_each_day": inputs.effective_cold_start_each_day,
        "comparable_mode": inputs.comparable_mode,
        "orchestrator_reset_scope": inputs.effective_reset_scope,
        "apply_aos_optimizations_on_start": inputs.apply_aos_optimizations_on_start,
        "strategy_selection_mode": inputs.effective_strategy_selection_mode,
        "max_active_strategies": inputs.effective_max_active_strategies,
        "all_enabled_remote_sync": inputs.all_enabled_remote_sync,
        "l2_requested": bool(
            inputs.requested_l2_only_raw or inputs.requested_l2_confirm_raw
        ),
        "requested_l2_only": bool(inputs.requested_l2_only_raw),
        "requested_l2_confirm_enabled": bool(inputs.requested_l2_confirm_raw),
        "effective_l2_confirm_enabled": bool(inputs.effective_l2_confirm),
        "liquidity_sweep_l2_auto_enabled": bool(inputs.l2_auto_enabled_by_sweep),
        "liquidity_sweep_l2_auto_source": str(inputs.l2_auto_enabled_source),
    }


def _build_intraday_levels_payload(execution_cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intraday_levels_enabled": bool(
            execution_cfg.get("effective_intraday_levels_enabled", True)
        ),
        "intraday_levels_swing_left_bars": int(
            execution_cfg.get("effective_intraday_levels_swing_left_bars", 2)
        ),
        "intraday_levels_swing_right_bars": int(
            execution_cfg.get("effective_intraday_levels_swing_right_bars", 2)
        ),
        "intraday_levels_test_tolerance_pct": float(
            execution_cfg.get("effective_intraday_levels_test_tolerance_pct", 0.08)
        ),
        "intraday_levels_break_tolerance_pct": float(
            execution_cfg.get("effective_intraday_levels_break_tolerance_pct", 0.05)
        ),
        "intraday_levels_breakout_volume_lookback": int(
            execution_cfg.get("effective_intraday_levels_breakout_volume_lookback", 20)
        ),
        "intraday_levels_breakout_volume_multiplier": float(
            execution_cfg.get(
                "effective_intraday_levels_breakout_volume_multiplier", 1.2
            )
        ),
        "intraday_levels_volume_profile_bin_size_pct": float(
            execution_cfg.get(
                "effective_intraday_levels_volume_profile_bin_size_pct", 0.05
            )
        ),
        "intraday_levels_value_area_pct": float(
            execution_cfg.get("effective_intraday_levels_value_area_pct", 0.70)
        ),
        "intraday_levels_entry_quality_enabled": bool(
            execution_cfg.get("effective_intraday_levels_entry_quality_enabled", True)
        ),
        "intraday_levels_min_levels_for_context": int(
            execution_cfg.get("effective_intraday_levels_min_levels_for_context", 1)
        ),
        "intraday_levels_entry_tolerance_pct": float(
            execution_cfg.get("effective_intraday_levels_entry_tolerance_pct", 0.10)
        ),
        "intraday_levels_break_cooldown_bars": int(
            execution_cfg.get("effective_intraday_levels_break_cooldown_bars", 3)
        ),
        "intraday_levels_rotation_max_tests": int(
            execution_cfg.get("effective_intraday_levels_rotation_max_tests", 2)
        ),
        "intraday_levels_rotation_volume_max_ratio": float(
            execution_cfg.get(
                "effective_intraday_levels_rotation_volume_max_ratio", 0.95
            )
        ),
        "intraday_levels_recent_bounce_lookback_bars": int(
            execution_cfg.get(
                "effective_intraday_levels_recent_bounce_lookback_bars", 6
            )
        ),
        "intraday_levels_require_recent_bounce_for_mean_reversion": bool(
            execution_cfg.get(
                "effective_intraday_levels_require_recent_bounce_for_mean_reversion",
                True,
            )
        ),
        "intraday_levels_momentum_break_max_age_bars": int(
            execution_cfg.get(
                "effective_intraday_levels_momentum_break_max_age_bars", 3
            )
        ),
        "intraday_levels_momentum_min_room_pct": float(
            execution_cfg.get("effective_intraday_levels_momentum_min_room_pct", 0.15)
        ),
        "intraday_levels_momentum_min_broken_ratio": float(
            execution_cfg.get(
                "effective_intraday_levels_momentum_min_broken_ratio", 0.30
            )
        ),
        "intraday_levels_min_confluence_score": int(
            execution_cfg.get("effective_intraday_levels_min_confluence_score", 1)
        ),
        "intraday_levels_memory_enabled": bool(
            execution_cfg.get("effective_intraday_levels_memory_enabled", True)
        ),
        "intraday_levels_memory_min_tests": int(
            execution_cfg.get("effective_intraday_levels_memory_min_tests", 2)
        ),
        "intraday_levels_memory_max_age_days": int(
            execution_cfg.get("effective_intraday_levels_memory_max_age_days", 5)
        ),
        "intraday_levels_memory_decay_after_days": int(
            execution_cfg.get("effective_intraday_levels_memory_decay_after_days", 2)
        ),
        "intraday_levels_memory_decay_weight": float(
            execution_cfg.get("effective_intraday_levels_memory_decay_weight", 0.50)
        ),
        "intraday_levels_memory_max_levels": int(
            execution_cfg.get("effective_intraday_levels_memory_max_levels", 12)
        ),
        "intraday_levels_opening_range_enabled": bool(
            execution_cfg.get("effective_intraday_levels_opening_range_enabled", True)
        ),
        "intraday_levels_opening_range_minutes": int(
            execution_cfg.get("effective_intraday_levels_opening_range_minutes", 30)
        ),
        "intraday_levels_opening_range_break_tolerance_pct": float(
            execution_cfg.get(
                "effective_intraday_levels_opening_range_break_tolerance_pct",
                0.05,
            )
        ),
        "intraday_levels_poc_migration_enabled": bool(
            execution_cfg.get("effective_intraday_levels_poc_migration_enabled", True)
        ),
        "intraday_levels_poc_migration_interval_bars": int(
            execution_cfg.get(
                "effective_intraday_levels_poc_migration_interval_bars", 30
            )
        ),
        "intraday_levels_poc_migration_trend_threshold_pct": float(
            execution_cfg.get(
                "effective_intraday_levels_poc_migration_trend_threshold_pct",
                0.20,
            )
        ),
        "intraday_levels_poc_migration_range_threshold_pct": float(
            execution_cfg.get(
                "effective_intraday_levels_poc_migration_range_threshold_pct",
                0.10,
            )
        ),
        "intraday_levels_composite_profile_enabled": bool(
            execution_cfg.get(
                "effective_intraday_levels_composite_profile_enabled", True
            )
        ),
        "intraday_levels_composite_profile_days": int(
            execution_cfg.get("effective_intraday_levels_composite_profile_days", 3)
        ),
        "intraday_levels_composite_profile_current_day_weight": float(
            execution_cfg.get(
                "effective_intraday_levels_composite_profile_current_day_weight",
                1.0,
            )
        ),
        "intraday_levels_spike_detection_enabled": bool(
            execution_cfg.get("effective_intraday_levels_spike_detection_enabled", True)
        ),
        "intraday_levels_spike_min_wick_ratio": float(
            execution_cfg.get("effective_intraday_levels_spike_min_wick_ratio", 0.60)
        ),
        "intraday_levels_prior_day_anchors_enabled": bool(
            execution_cfg.get(
                "effective_intraday_levels_prior_day_anchors_enabled", True
            )
        ),
        "intraday_levels_gap_analysis_enabled": bool(
            execution_cfg.get("effective_intraday_levels_gap_analysis_enabled", True)
        ),
        "intraday_levels_gap_min_pct": float(
            execution_cfg.get("effective_intraday_levels_gap_min_pct", 0.30)
        ),
        "intraday_levels_gap_momentum_threshold_pct": float(
            execution_cfg.get(
                "effective_intraday_levels_gap_momentum_threshold_pct", 2.0
            )
        ),
        "intraday_levels_rvol_filter_enabled": bool(
            execution_cfg.get("effective_intraday_levels_rvol_filter_enabled", True)
        ),
        "intraday_levels_rvol_lookback_bars": int(
            execution_cfg.get("effective_intraday_levels_rvol_lookback_bars", 20)
        ),
        "intraday_levels_rvol_min_threshold": float(
            execution_cfg.get("effective_intraday_levels_rvol_min_threshold", 0.80)
        ),
        "intraday_levels_rvol_strong_threshold": float(
            execution_cfg.get("effective_intraday_levels_rvol_strong_threshold", 1.50)
        ),
        "intraday_levels_adaptive_window_enabled": bool(
            execution_cfg.get("effective_intraday_levels_adaptive_window_enabled", True)
        ),
        "intraday_levels_adaptive_window_min_bars": int(
            execution_cfg.get("effective_intraday_levels_adaptive_window_min_bars", 6)
        ),
        "intraday_levels_adaptive_window_rvol_threshold": float(
            execution_cfg.get(
                "effective_intraday_levels_adaptive_window_rvol_threshold", 0.5
            )
        ),
        "intraday_levels_adaptive_window_atr_ratio_max": float(
            execution_cfg.get(
                "effective_intraday_levels_adaptive_window_atr_ratio_max", 1.5
            )
        ),
        "intraday_levels_micro_confirmation_enabled": bool(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_enabled", False
            )
        ),
        "intraday_levels_micro_confirmation_bars": int(
            execution_cfg.get("effective_intraday_levels_micro_confirmation_bars", 2)
        ),
        "intraday_levels_micro_confirmation_disable_for_sweep": bool(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_disable_for_sweep",
                False,
            )
        ),
        "intraday_levels_micro_confirmation_sweep_bars": int(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_sweep_bars", 0
            )
        ),
        "intraday_levels_micro_confirmation_require_intrabar": bool(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_require_intrabar",
                False,
            )
        ),
        "intraday_levels_micro_confirmation_intrabar_window_seconds": int(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_intrabar_window_seconds",
                5,
            )
        ),
        "intraday_levels_micro_confirmation_intrabar_min_coverage_points": int(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_intrabar_min_coverage_points",
                3,
            )
        ),
        "intraday_levels_micro_confirmation_intrabar_min_move_pct": float(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_intrabar_min_move_pct",
                0.02,
            )
        ),
        "intraday_levels_micro_confirmation_intrabar_min_push_ratio": float(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_intrabar_min_push_ratio",
                0.10,
            )
        ),
        "intraday_levels_micro_confirmation_intrabar_max_spread_bps": float(
            execution_cfg.get(
                "effective_intraday_levels_micro_confirmation_intrabar_max_spread_bps",
                12.0,
            )
        ),
        "intraday_levels_confluence_sizing_enabled": bool(
            execution_cfg.get(
                "effective_intraday_levels_confluence_sizing_enabled", False
            )
        ),
        "liquidity_sweep_detection_enabled": bool(
            execution_cfg.get("effective_liquidity_sweep_detection_enabled", False)
        ),
        "sweep_min_aggression_z": float(
            execution_cfg.get("effective_sweep_min_aggression_z", -2.0)
        ),
        "sweep_min_book_pressure_z": float(
            execution_cfg.get("effective_sweep_min_book_pressure_z", 1.5)
        ),
        "sweep_max_price_change_pct": float(
            execution_cfg.get("effective_sweep_max_price_change_pct", 0.05)
        ),
        "tcbbo_gate_enabled": bool(
            execution_cfg.get("effective_tcbbo_gate_enabled", False)
        ),
        "tcbbo_min_net_premium": float(
            execution_cfg.get("effective_tcbbo_min_net_premium", 0.0)
        ),
        "tcbbo_sweep_boost": float(
            execution_cfg.get("effective_tcbbo_sweep_boost", 5.0)
        ),
        "tcbbo_lookback_bars": int(
            execution_cfg.get("effective_tcbbo_lookback_bars", 5)
        ),
    }


def _build_context_risk_payload(execution_cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "context_aware_risk_enabled": bool(
            execution_cfg.get("context_aware_risk_enabled", False)
        ),
        "context_risk_sl_buffer_pct": float(
            execution_cfg.get("context_risk_sl_buffer_pct", 0.10)
        ),
        "context_risk_min_sl_pct": float(
            execution_cfg.get("context_risk_min_sl_pct", 0.30)
        ),
        "context_risk_min_room_pct": float(
            execution_cfg.get("context_risk_min_room_pct", 0.08)
        ),
        "context_risk_min_effective_rr": float(
            execution_cfg.get("context_risk_min_effective_rr", 0.5)
        ),
        "context_risk_trailing_tighten_zone": float(
            execution_cfg.get("context_risk_trailing_tighten_zone", 0.2)
        ),
        "context_risk_trailing_tighten_factor": float(
            execution_cfg.get("context_risk_trailing_tighten_factor", 0.5)
        ),
        "context_risk_level_trail_enabled": bool(
            execution_cfg.get("context_risk_level_trail_enabled", True)
        ),
        "context_risk_max_anchor_search_pct": float(
            execution_cfg.get("context_risk_max_anchor_search_pct", 2.5)
        ),
        "context_risk_min_level_tests_for_sl": int(
            execution_cfg.get("context_risk_min_level_tests_for_sl", 1)
        ),
        "sweep_atr_buffer_multiplier": float(
            execution_cfg.get("sweep_atr_buffer_multiplier", 0.5)
        ),
    }


def _resolve_include_extended_hours(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
    canonical_trading_hours: Callable[[Any], tuple[int, ...]],
) -> bool:
    if request.include_extended_hours is not None:
        return bool(request.include_extended_hours)
    return not bool(
        aos_applied.get("time_filter_enabled")
        and canonical_trading_hours(aos_applied.get("trading_hours"))
    )


def _apply_optional_execution_limits(
    *,
    execution_config_payload: Dict[str, Any],
    execution_cfg: Dict[str, Any],
) -> None:
    effective_max_daily_trades = execution_cfg.get("effective_max_daily_trades")
    max_daily_trades_source = str(
        execution_cfg.get("max_daily_trades_source", "ticker_config")
    )
    if effective_max_daily_trades is not None:
        execution_config_payload["max_daily_trades"] = int(effective_max_daily_trades)
        execution_config_payload["max_daily_trades_source"] = max_daily_trades_source

    effective_mu_choppy_hard_block_enabled = execution_cfg.get(
        "effective_mu_choppy_hard_block_enabled"
    )
    mu_choppy_hard_block_enabled_source = str(
        execution_cfg.get("mu_choppy_hard_block_enabled_source", "ticker_config")
    )
    if effective_mu_choppy_hard_block_enabled is not None:
        execution_config_payload["mu_choppy_hard_block_enabled"] = bool(
            effective_mu_choppy_hard_block_enabled
        )
        execution_config_payload["mu_choppy_hard_block_enabled_source"] = (
            mu_choppy_hard_block_enabled_source
        )


def _apply_effective_profile_metadata(
    *,
    execution_config_payload: Dict[str, Any],
    aos_applied: Dict[str, Any],
    extract_effective_profile_metadata: Callable[..., Dict[str, Optional[str]]],
) -> None:
    effective_profile_meta = extract_effective_profile_metadata(
        aos_applied=aos_applied,
        execution_config=execution_config_payload,
    )
    unified_profile_id = effective_profile_meta.get("unified_profile_id")
    if unified_profile_id:
        execution_config_payload["unified_profile_id"] = unified_profile_id
        execution_config_payload["active_unified_profile_id"] = unified_profile_id

    unified_profile_name = effective_profile_meta.get("unified_profile_name")
    if unified_profile_name:
        execution_config_payload["unified_profile_name"] = unified_profile_name

    adaptive_profile_id = effective_profile_meta.get("adaptive_profile_id")
    if adaptive_profile_id:
        execution_config_payload["adaptive_profile_id"] = adaptive_profile_id
        execution_config_payload["active_adaptive_tuner_profile_id"] = (
            adaptive_profile_id
        )

    adaptive_profile_name = effective_profile_meta.get("adaptive_profile_name")
    if adaptive_profile_name:
        execution_config_payload["adaptive_profile_name"] = adaptive_profile_name

    strategy_combo_profile_id = effective_profile_meta.get("strategy_combo_profile_id")
    if strategy_combo_profile_id:
        execution_config_payload["strategy_combo_profile_id"] = (
            strategy_combo_profile_id
        )
        execution_config_payload["active_strategy_combo_profile_id"] = (
            strategy_combo_profile_id
        )

    strategy_combo_profile_name = effective_profile_meta.get(
        "strategy_combo_profile_name"
    )
    if strategy_combo_profile_name:
        execution_config_payload["strategy_combo_profile_name"] = (
            strategy_combo_profile_name
        )


def _build_l2_applied_payload(
    *,
    inputs: ExecutionPayloadInputs,
    l2_thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    tcbbo_gate_enabled = bool(inputs.execution_cfg.get("effective_tcbbo_gate_enabled", False))
    options_flow_alpha_enabled = _is_options_flow_alpha_enabled(inputs.aos_applied)
    tcbbo_feature_required_by: list[str] = []
    if tcbbo_gate_enabled:
        tcbbo_feature_required_by.append("tcbbo_gate")
    if options_flow_alpha_enabled:
        tcbbo_feature_required_by.append("options_flow_alpha")

    return {
        **inputs.l2_stats,
        "l2_requested": bool(
            inputs.requested_l2_only_raw or inputs.requested_l2_confirm_raw
        ),
        "l2_guard_reason": inputs.l2_guard_reason,
        "effective_l2_confirm_enabled": inputs.effective_l2_confirm,
        "tcbbo_gate_enabled": tcbbo_gate_enabled,
        "tcbbo_min_net_premium": float(
            inputs.execution_cfg.get("effective_tcbbo_min_net_premium", 0.0)
        ),
        "tcbbo_sweep_boost": float(
            inputs.execution_cfg.get("effective_tcbbo_sweep_boost", 5.0)
        ),
        "tcbbo_lookback_bars": int(
            inputs.execution_cfg.get("effective_tcbbo_lookback_bars", 5)
        ),
        "options_flow_alpha_enabled": options_flow_alpha_enabled,
        "tcbbo_feature_required": bool(tcbbo_feature_required_by),
        "tcbbo_feature_required_by": list(tcbbo_feature_required_by),
        "liquidity_sweep_l2_auto_enabled": bool(inputs.l2_auto_enabled_by_sweep),
        "liquidity_sweep_l2_auto_source": str(inputs.l2_auto_enabled_source),
        **l2_thresholds,
        "sessionized_by_market_day": inputs.l2_sessionized_by_market_day,
    }


def build_execution_payload(
    *,
    inputs: ExecutionPayloadInputs,
    canonical_trading_hours: Callable[[Any], tuple[int, ...]],
    extract_effective_profile_metadata: Callable[..., Dict[str, Optional[str]]],
) -> ExecutionPayloadResult:
    request = inputs.request
    execution_cfg = inputs.execution_cfg
    aos_applied = (
        dict(inputs.aos_applied) if isinstance(inputs.aos_applied, dict) else {}
    )

    execution_config_payload = {
        "account_size_usd": request.account_size_usd,
        **_build_core_execution_payload(execution_cfg),
        **_build_runtime_execution_payload(inputs),
        **_build_intraday_levels_payload(execution_cfg),
        **_build_context_risk_payload(execution_cfg),
        "include_extended_hours": _resolve_include_extended_hours(
            request=request,
            aos_applied=aos_applied,
            canonical_trading_hours=canonical_trading_hours,
        ),
        "momentum_diversification_applied": bool(
            inputs.effective_momentum_diversification
        ),
        "momentum_diversification_source": inputs.momentum_diversification_source,
        "momentum_diversification": inputs.effective_momentum_diversification or {},
    }
    _apply_optional_execution_limits(
        execution_config_payload=execution_config_payload,
        execution_cfg=execution_cfg,
    )
    _apply_effective_profile_metadata(
        execution_config_payload=execution_config_payload,
        aos_applied=aos_applied,
        extract_effective_profile_metadata=extract_effective_profile_metadata,
    )

    l2_applied_payload = _build_l2_applied_payload(
        inputs=inputs,
        l2_thresholds=_build_l2_thresholds(execution_cfg),
    )

    return ExecutionPayloadResult(
        execution_config_payload=execution_config_payload,
        l2_applied_payload=l2_applied_payload,
    )
