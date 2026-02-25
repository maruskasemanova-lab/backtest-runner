from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict

from src.services.execution_config.helpers import (
    pick_l2_float,
    resolve_adverse_flow_threshold as helper_resolve_adverse_flow_threshold,
    resolve_optional_runtime_bool as helper_resolve_optional_runtime_bool,
    resolve_optional_runtime_non_negative_int as helper_resolve_optional_runtime_non_negative_int,
    resolve_positioning_bool as helper_resolve_positioning_bool,
    resolve_positioning_float as helper_resolve_positioning_float,
    resolve_positioning_int as helper_resolve_positioning_int,
    resolve_positioning_str as helper_resolve_positioning_str,
    resolve_stop_loss_mode as helper_resolve_stop_loss_mode,
)
from src.services.execution_config.intraday_context import (
    resolve_context_risk_config,
    resolve_intraday_levels_config,
)


@dataclass(frozen=True)
class FloatPositioningSpec:
    effective_key: str
    source_key: str
    request_attr: str
    request_default: float
    positioning_key: str
    min_value: float | None = None
    max_value: float | None = None
    runtime_key: str | None = None
    runtime_positive_only: bool = False


@dataclass(frozen=True)
class IntPositioningSpec:
    effective_key: str
    source_key: str
    request_attr: str
    request_default: int
    positioning_key: str
    min_value: int | None = None
    max_value: int | None = None
    runtime_key: str | None = None
    runtime_positive_only: bool = False


@dataclass(frozen=True)
class BoolPositioningSpec:
    effective_key: str
    source_key: str
    request_attr: str
    request_default: bool
    positioning_key: str
    runtime_key: str | None = None


@dataclass(frozen=True)
class StringPositioningSpec:
    effective_key: str
    source_key: str
    request_attr: str
    request_default: str
    positioning_key: str
    runtime_key: str | None = None
    strip: bool = True


_FLOAT_POSITIONING_SPECS: tuple[FloatPositioningSpec, ...] = (
    FloatPositioningSpec(
        effective_key="effective_book_pressure_block_z_threshold",
        source_key="book_pressure_block_z_threshold_source",
        request_attr="book_pressure_block_z_threshold",
        request_default=1.65,
        positioning_key="book_pressure_block_z_threshold",
        min_value=-10.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_proof_book_pressure_threshold",
        source_key="break_even_l2_proof_book_pressure_threshold_source",
        request_attr="break_even_l2_proof_book_pressure_threshold",
        request_default=0.06,
        positioning_key="break_even_l2_proof_book_pressure_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_proof_imbalance_threshold",
        source_key="break_even_l2_proof_imbalance_threshold_source",
        request_attr="break_even_l2_proof_imbalance_threshold",
        request_default=0.1,
        positioning_key="break_even_l2_proof_imbalance_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_proof_signed_threshold",
        source_key="break_even_l2_proof_signed_threshold_source",
        request_attr="break_even_l2_proof_signed_threshold",
        request_default=0.07,
        positioning_key="break_even_l2_proof_signed_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_ev_relaxation_factor",
        source_key="ev_relaxation_factor_source",
        request_attr="ev_relaxation_factor",
        request_default=0.5,
        positioning_key="ev_relaxation_factor",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_ev_relaxation_threshold",
        source_key="ev_relaxation_threshold_source",
        request_attr="ev_relaxation_threshold",
        request_default=10.0,
        positioning_key="ev_relaxation_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_micro_confirmation_volume_delta_min_pct",
        source_key="micro_confirmation_volume_delta_min_pct_source",
        request_attr="micro_confirmation_volume_delta_min_pct",
        request_default=0.6,
        positioning_key="micro_confirmation_volume_delta_min_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_signed_aggression_block_z_threshold",
        source_key="signed_aggression_block_z_threshold_source",
        request_attr="signed_aggression_block_z_threshold",
        request_default=1.65,
        positioning_key="signed_aggression_block_z_threshold",
        min_value=-10.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_weak_l2_aggression_threshold",
        source_key="weak_l2_aggression_threshold_source",
        request_attr="weak_l2_aggression_threshold",
        request_default=0.05,
        positioning_key="weak_l2_aggression_threshold",
        min_value=0.0,
    ),    FloatPositioningSpec(
        effective_key="effective_risk_per_trade_pct",
        source_key="risk_per_trade_source",
        request_attr="risk_per_trade_pct",
        request_default=1.0,
        positioning_key="risk_per_trade_pct",
        min_value=0.1,
    ),
    FloatPositioningSpec(
        effective_key="effective_max_position_notional_pct",
        source_key="max_position_notional_source",
        request_attr="max_position_notional_pct",
        request_default=100.0,
        positioning_key="max_position_notional_pct",
        min_value=1.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_max_fill_participation_rate",
        source_key="max_fill_participation_source",
        request_attr="max_fill_participation_rate",
        request_default=0.20,
        positioning_key="max_fill_participation_rate",
        min_value=0.01,
        max_value=1.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_min_fill_ratio",
        source_key="min_fill_ratio_source",
        request_attr="min_fill_ratio",
        request_default=0.35,
        positioning_key="min_fill_ratio",
        min_value=0.01,
        max_value=1.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_partial_take_profit_rr",
        source_key="partial_take_profit_rr_source",
        request_attr="partial_take_profit_rr",
        request_default=1.0,
        positioning_key="partial_take_profit_rr",
        min_value=0.25,
    ),
    FloatPositioningSpec(
        effective_key="effective_partial_take_profit_fraction",
        source_key="partial_take_profit_fraction_source",
        request_attr="partial_take_profit_fraction",
        request_default=0.5,
        positioning_key="partial_take_profit_fraction",
        min_value=0.05,
        max_value=0.95,
    ),
    FloatPositioningSpec(
        effective_key="effective_partial_flow_deterioration_min_r",
        source_key="partial_flow_deterioration_min_r_source",
        request_attr="partial_flow_deterioration_min_r",
        request_default=0.5,
        positioning_key="partial_flow_deterioration_min_r",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_partial_protect_min_mfe_r",
        source_key="partial_protect_min_mfe_r_source",
        request_attr="partial_protect_min_mfe_r",
        request_default=0.0,
        positioning_key="partial_protect_min_mfe_r",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_trailing_stop_pct",
        source_key="trailing_stop_pct_source",
        request_attr="trailing_stop_pct",
        request_default=0.0,
        positioning_key="trailing_stop_pct",
        min_value=0.0,
        runtime_key="trailing_stop_pct",
        runtime_positive_only=True,
    ),
    FloatPositioningSpec(
        effective_key="effective_global_exit_rr_ratio",
        source_key="global_exit_rr_ratio_source",
        request_attr="global_exit_rr_ratio",
        request_default=0.0,
        positioning_key="global_exit_rr_ratio",
        min_value=0.0,
        runtime_key="global_exit_rr_ratio",
        runtime_positive_only=True,
    ),
    FloatPositioningSpec(
        effective_key="effective_global_risk_atr_stop_multiplier",
        source_key="global_risk_atr_stop_multiplier_source",
        request_attr="global_risk_atr_stop_multiplier",
        request_default=0.0,
        positioning_key="global_risk_atr_stop_multiplier",
        min_value=0.0,
        runtime_key="global_risk_atr_stop_multiplier",
        runtime_positive_only=True,
    ),
    FloatPositioningSpec(
        effective_key="effective_global_risk_volume_stop_pct",
        source_key="global_risk_volume_stop_pct_source",
        request_attr="global_risk_volume_stop_pct",
        request_default=0.0,
        positioning_key="global_risk_volume_stop_pct",
        min_value=0.0,
        runtime_key="global_risk_volume_stop_pct",
        runtime_positive_only=True,
    ),
    FloatPositioningSpec(
        effective_key="effective_global_risk_min_stop_loss_pct",
        source_key="global_risk_min_stop_loss_pct_source",
        request_attr="global_risk_min_stop_loss_pct",
        request_default=0.0,
        positioning_key="global_risk_min_stop_loss_pct",
        min_value=0.0,
        runtime_key="global_risk_min_stop_loss_pct",
        runtime_positive_only=True,
    ),
    FloatPositioningSpec(
        effective_key="effective_trailing_activation_pct",
        source_key="trailing_activation_source",
        request_attr="trailing_activation_pct",
        request_default=0.15,
        positioning_key="trailing_activation_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_buffer_pct",
        source_key="break_even_buffer_source",
        request_attr="break_even_buffer_pct",
        request_default=0.03,
        positioning_key="break_even_buffer_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_activation_min_mfe_pct",
        source_key="break_even_activation_min_mfe_source",
        request_attr="break_even_activation_min_mfe_pct",
        request_default=0.0,
        positioning_key="break_even_activation_min_mfe_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_activation_min_r",
        source_key="break_even_activation_min_r_source",
        request_attr="break_even_activation_min_r",
        request_default=0.0,
        positioning_key="break_even_activation_min_r",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_activation_min_r_trending_5m",
        source_key="break_even_activation_min_r_trending_source",
        request_attr="break_even_activation_min_r_trending_5m",
        request_default=0.0,
        positioning_key="break_even_activation_min_r_trending_5m",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_activation_min_r_choppy_5m",
        source_key="break_even_activation_min_r_choppy_source",
        request_attr="break_even_activation_min_r_choppy_5m",
        request_default=0.0,
        positioning_key="break_even_activation_min_r_choppy_5m",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_level_buffer_pct",
        source_key="break_even_level_buffer_source",
        request_attr="break_even_level_buffer_pct",
        request_default=0.02,
        positioning_key="break_even_level_buffer_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_level_max_distance_pct",
        source_key="break_even_level_max_distance_source",
        request_attr="break_even_level_max_distance_pct",
        request_default=0.60,
        positioning_key="break_even_level_max_distance_pct",
        min_value=0.01,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_signed_aggression_min",
        source_key="break_even_l2_signed_source",
        request_attr="break_even_l2_signed_aggression_min",
        request_default=0.12,
        positioning_key="break_even_l2_signed_aggression_min",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_imbalance_min",
        source_key="break_even_l2_imbalance_source",
        request_attr="break_even_l2_imbalance_min",
        request_default=0.15,
        positioning_key="break_even_l2_imbalance_min",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_book_pressure_min",
        source_key="break_even_l2_book_source",
        request_attr="break_even_l2_book_pressure_min",
        request_default=0.10,
        positioning_key="break_even_l2_book_pressure_min",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_l2_spread_bps_max",
        source_key="break_even_l2_spread_source",
        request_attr="break_even_l2_spread_bps_max",
        request_default=12.0,
        positioning_key="break_even_l2_spread_bps_max",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_costs_pct",
        source_key="break_even_costs_source",
        request_attr="break_even_costs_pct",
        request_default=0.03,
        positioning_key="break_even_costs_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_min_buffer_pct",
        source_key="break_even_min_buffer_source",
        request_attr="break_even_min_buffer_pct",
        request_default=0.05,
        positioning_key="break_even_min_buffer_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_atr_buffer_k",
        source_key="break_even_atr_buffer_source",
        request_attr="break_even_atr_buffer_k",
        request_default=0.10,
        positioning_key="break_even_atr_buffer_k",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_5m_atr_buffer_k",
        source_key="break_even_5m_atr_buffer_source",
        request_attr="break_even_5m_atr_buffer_k",
        request_default=0.10,
        positioning_key="break_even_5m_atr_buffer_k",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_tick_size",
        source_key="break_even_tick_size_source",
        request_attr="break_even_tick_size",
        request_default=0.01,
        positioning_key="break_even_tick_size",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_5m_no_go_proximity_pct",
        source_key="break_even_5m_no_go_source",
        request_attr="break_even_5m_no_go_proximity_pct",
        request_default=0.10,
        positioning_key="break_even_5m_no_go_proximity_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_5m_mfe_atr_factor",
        source_key="break_even_5m_mfe_atr_source",
        request_attr="break_even_5m_mfe_atr_factor",
        request_default=0.15,
        positioning_key="break_even_5m_mfe_atr_factor",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_5m_l2_bias_threshold",
        source_key="break_even_5m_l2_bias_source",
        request_attr="break_even_5m_l2_bias_threshold",
        request_default=0.10,
        positioning_key="break_even_5m_l2_bias_threshold",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_break_even_5m_l2_bias_tighten_factor",
        source_key="break_even_5m_l2_tighten_source",
        request_attr="break_even_5m_l2_bias_tighten_factor",
        request_default=0.85,
        positioning_key="break_even_5m_l2_bias_tighten_factor",
        min_value=0.1,
        max_value=2.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_adverse_flow_threshold",
        source_key="adverse_flow_threshold_source",
        request_attr="adverse_flow_threshold",
        request_default=0.12,
        positioning_key="adverse_flow_threshold",
        min_value=0.02,
    ),
    FloatPositioningSpec(
        effective_key="effective_fixed_stop_loss_pct",
        source_key="fixed_stop_loss_source",
        request_attr="fixed_stop_loss_pct",
        request_default=0.0,
        positioning_key="fixed_stop_loss_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_tcbbo_min_net_premium",
        source_key="tcbbo_min_net_premium_source",
        request_attr="tcbbo_min_net_premium",
        request_default=0.0,
        positioning_key="tcbbo_min_net_premium",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_tcbbo_sweep_boost",
        source_key="tcbbo_sweep_boost_source",
        request_attr="tcbbo_sweep_boost",
        request_default=5.0,
        positioning_key="tcbbo_sweep_boost",
        min_value=0.0,
        max_value=20.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_intrabar_min_move_pct",
        source_key="intraday_levels_micro_confirmation_intrabar_min_move_pct_source",
        request_attr="intraday_levels_micro_confirmation_intrabar_min_move_pct",
        request_default=0.02,
        positioning_key="intraday_levels_micro_confirmation_intrabar_min_move_pct",
        min_value=0.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_intrabar_min_push_ratio",
        source_key="intraday_levels_micro_confirmation_intrabar_min_push_ratio_source",
        request_attr="intraday_levels_micro_confirmation_intrabar_min_push_ratio",
        request_default=0.10,
        positioning_key="intraday_levels_micro_confirmation_intrabar_min_push_ratio",
        min_value=0.0,
        max_value=1.0,
    ),
    FloatPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_intrabar_max_spread_bps",
        source_key="intraday_levels_micro_confirmation_intrabar_max_spread_bps_source",
        request_attr="intraday_levels_micro_confirmation_intrabar_max_spread_bps",
        request_default=12.0,
        positioning_key="intraday_levels_micro_confirmation_intrabar_max_spread_bps",
        min_value=0.0,
    ),
)


_INT_POSITIONING_SPECS: tuple[IntPositioningSpec, ...] = (
    IntPositioningSpec(
        effective_key="effective_intraday_levels_bounce_conflict_buffer_bars",
        source_key="intraday_levels_bounce_conflict_buffer_bars_source",
        request_attr="intraday_levels_bounce_conflict_buffer_bars",
        request_default=2,
        positioning_key="intraday_levels_bounce_conflict_buffer_bars",
        min_value=0,
    ),
    IntPositioningSpec(
        effective_key="effective_weak_l2_break_even_min_hold_bars",
        source_key="weak_l2_break_even_min_hold_bars_source",
        request_attr="weak_l2_break_even_min_hold_bars",
        request_default=1,
        positioning_key="weak_l2_break_even_min_hold_bars",
        min_value=0,
    ),    IntPositioningSpec(
        effective_key="effective_break_even_min_hold_bars",
        source_key="break_even_min_hold_source",
        request_attr="break_even_min_hold_bars",
        request_default=5,
        positioning_key="break_even_min_hold_bars",
        min_value=1,
    ),
    IntPositioningSpec(
        effective_key="effective_break_even_level_min_confluence",
        source_key="break_even_level_min_confluence_source",
        request_attr="break_even_level_min_confluence",
        request_default=2,
        positioning_key="break_even_level_min_confluence",
        min_value=0,
    ),
    IntPositioningSpec(
        effective_key="effective_break_even_level_min_tests",
        source_key="break_even_level_min_tests_source",
        request_attr="break_even_level_min_tests",
        request_default=1,
        positioning_key="break_even_level_min_tests",
        min_value=0,
    ),
    IntPositioningSpec(
        effective_key="effective_break_even_min_tick_buffer",
        source_key="break_even_min_tick_buffer_source",
        request_attr="break_even_min_tick_buffer",
        request_default=1,
        positioning_key="break_even_min_tick_buffer",
        min_value=0,
    ),
    IntPositioningSpec(
        effective_key="effective_break_even_anti_spike_bars",
        source_key="break_even_anti_spike_bars_source",
        request_attr="break_even_anti_spike_bars",
        request_default=1,
        positioning_key="break_even_anti_spike_bars",
        min_value=0,
    ),
    IntPositioningSpec(
        effective_key="effective_break_even_anti_spike_hits_required",
        source_key="break_even_anti_spike_hits_source",
        request_attr="break_even_anti_spike_hits_required",
        request_default=2,
        positioning_key="break_even_anti_spike_hits_required",
        min_value=1,
    ),
    IntPositioningSpec(
        effective_key="effective_time_exit_bars",
        source_key="time_exit_source",
        request_attr="time_exit_bars",
        request_default=40,
        positioning_key="time_exit_bars",
        min_value=1,
        runtime_key="time_exit_bars",
        runtime_positive_only=True,
    ),
    IntPositioningSpec(
        effective_key="effective_adverse_flow_min_hold_bars",
        source_key="adverse_flow_min_hold_source",
        request_attr="adverse_flow_min_hold_bars",
        request_default=3,
        positioning_key="adverse_flow_min_hold_bars",
        min_value=1,
    ),
    IntPositioningSpec(
        effective_key="effective_tcbbo_lookback_bars",
        source_key="tcbbo_lookback_bars_source",
        request_attr="tcbbo_lookback_bars",
        request_default=5,
        positioning_key="tcbbo_lookback_bars",
        min_value=1,
    ),
    IntPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_bars",
        source_key="intraday_levels_micro_confirmation_bars_source",
        request_attr="intraday_levels_micro_confirmation_bars",
        request_default=2,
        positioning_key="intraday_levels_micro_confirmation_bars",
        min_value=1,
    ),
    IntPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_sweep_bars",
        source_key="intraday_levels_micro_confirmation_sweep_bars_source",
        request_attr="intraday_levels_micro_confirmation_sweep_bars",
        request_default=0,
        positioning_key="intraday_levels_micro_confirmation_sweep_bars",
        min_value=0,
    ),
    IntPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_intrabar_window_seconds",
        source_key="intraday_levels_micro_confirmation_intrabar_window_seconds_source",
        request_attr="intraday_levels_micro_confirmation_intrabar_window_seconds",
        request_default=5,
        positioning_key="intraday_levels_micro_confirmation_intrabar_window_seconds",
        min_value=1,
        max_value=60,
    ),
    IntPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_intrabar_min_coverage_points",
        source_key="intraday_levels_micro_confirmation_intrabar_min_coverage_points_source",
        request_attr="intraday_levels_micro_confirmation_intrabar_min_coverage_points",
        request_default=3,
        positioning_key="intraday_levels_micro_confirmation_intrabar_min_coverage_points",
        min_value=0,
    ),
)


_BOOL_POSITIONING_SPECS: tuple[BoolPositioningSpec, ...] = (
    BoolPositioningSpec(
        effective_key="effective_ev_relaxation_enabled",
        source_key="ev_relaxation_enabled_source",
        request_attr="ev_relaxation_enabled",
        request_default=True,
        positioning_key="ev_relaxation_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_hard_l2_block_enabled",
        source_key="hard_l2_block_enabled_source",
        request_attr="hard_l2_block_enabled",
        request_default=True,
        positioning_key="hard_l2_block_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_time_of_day_filter_enabled",
        source_key="time_of_day_filter_enabled_source",
        request_attr="time_of_day_filter_enabled",
        request_default=True,
        positioning_key="time_of_day_filter_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_weak_l2_fast_break_even_enabled",
        source_key="weak_l2_fast_break_even_enabled_source",
        request_attr="weak_l2_fast_break_even_enabled",
        request_default=False,
        positioning_key="weak_l2_fast_break_even_enabled",
    ),    BoolPositioningSpec(
        effective_key="effective_enable_partial_take_profit",
        source_key="partial_take_profit_enabled_source",
        request_attr="enable_partial_take_profit",
        request_default=True,
        positioning_key="enable_partial_take_profit",
    ),
    BoolPositioningSpec(
        effective_key="effective_partial_flow_deterioration_skip_be",
        source_key="partial_flow_deterioration_skip_be_source",
        request_attr="partial_flow_deterioration_skip_be",
        request_default=True,
        positioning_key="partial_flow_deterioration_skip_be",
    ),
    BoolPositioningSpec(
        effective_key="effective_break_even_activation_use_levels",
        source_key="break_even_activation_use_levels_source",
        request_attr="break_even_activation_use_levels",
        request_default=True,
        positioning_key="break_even_activation_use_levels",
    ),
    BoolPositioningSpec(
        effective_key="effective_break_even_activation_use_l2",
        source_key="break_even_activation_use_l2_source",
        request_attr="break_even_activation_use_l2",
        request_default=True,
        positioning_key="break_even_activation_use_l2",
    ),
    BoolPositioningSpec(
        effective_key="effective_break_even_movement_formula_enabled",
        source_key="break_even_movement_formula_enabled_source",
        request_attr="break_even_movement_formula_enabled",
        request_default=False,
        positioning_key="break_even_movement_formula_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_break_even_proof_formula_enabled",
        source_key="break_even_proof_formula_enabled_source",
        request_attr="break_even_proof_formula_enabled",
        request_default=False,
        positioning_key="break_even_proof_formula_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_break_even_activation_formula_enabled",
        source_key="break_even_activation_formula_enabled_source",
        request_attr="break_even_activation_formula_enabled",
        request_default=False,
        positioning_key="break_even_activation_formula_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_break_even_trailing_handoff_formula_enabled",
        source_key="break_even_trailing_handoff_formula_enabled_source",
        request_attr="break_even_trailing_handoff_formula_enabled",
        request_default=False,
        positioning_key="break_even_trailing_handoff_formula_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_break_even_anti_spike_require_close_beyond",
        source_key="break_even_anti_spike_close_source",
        request_attr="break_even_anti_spike_require_close_beyond",
        request_default=True,
        positioning_key="break_even_anti_spike_require_close_beyond",
    ),
    BoolPositioningSpec(
        effective_key="effective_trailing_enabled_in_choppy",
        source_key="trailing_enabled_in_choppy_source",
        request_attr="trailing_enabled_in_choppy",
        request_default=False,
        positioning_key="trailing_enabled_in_choppy",
    ),
    BoolPositioningSpec(
        effective_key="effective_adverse_flow_exit_enabled",
        source_key="adverse_flow_exit_enabled_source",
        request_attr="adverse_flow_exit_enabled",
        request_default=True,
        positioning_key="adverse_flow_exit_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_time_exit_formula_enabled",
        source_key="time_exit_formula_enabled_source",
        request_attr="time_exit_formula_enabled",
        request_default=False,
        positioning_key="time_exit_formula_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_adverse_flow_exit_formula_enabled",
        source_key="adverse_flow_exit_formula_enabled_source",
        request_attr="adverse_flow_exit_formula_enabled",
        request_default=False,
        positioning_key="adverse_flow_exit_formula_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_tcbbo_gate_enabled",
        source_key="tcbbo_gate_enabled_source",
        request_attr="tcbbo_gate_enabled",
        request_default=False,
        positioning_key="tcbbo_gate_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_enabled",
        source_key="intraday_levels_micro_confirmation_enabled_source",
        request_attr="intraday_levels_micro_confirmation_enabled",
        request_default=False,
        positioning_key="intraday_levels_micro_confirmation_enabled",
    ),
    BoolPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_disable_for_sweep",
        source_key="intraday_levels_micro_confirmation_disable_for_sweep_source",
        request_attr="intraday_levels_micro_confirmation_disable_for_sweep",
        request_default=False,
        positioning_key="intraday_levels_micro_confirmation_disable_for_sweep",
    ),
    BoolPositioningSpec(
        effective_key="effective_intraday_levels_micro_confirmation_require_intrabar",
        source_key="intraday_levels_micro_confirmation_require_intrabar_source",
        request_attr="intraday_levels_micro_confirmation_require_intrabar",
        request_default=False,
        positioning_key="intraday_levels_micro_confirmation_require_intrabar",
    ),
)


_STRING_POSITIONING_SPECS: tuple[StringPositioningSpec, ...] = (
    StringPositioningSpec(
        effective_key="effective_break_even_proof_logic",
        source_key="break_even_proof_logic_source",
        request_attr="break_even_proof_logic",
        request_default="OR",
        positioning_key="break_even_proof_logic",
    ),
    StringPositioningSpec(
        effective_key="effective_micro_confirmation_mode",
        source_key="micro_confirmation_mode_source",
        request_attr="micro_confirmation_mode",
        request_default="volume_delta",
        positioning_key="micro_confirmation_mode",
    ),
    StringPositioningSpec(
        effective_key="effective_volume_profile_poc_mode",
        source_key="volume_profile_poc_mode_source",
        request_attr="volume_profile_poc_mode",
        request_default="favor_bounce_mean_reversion",
        positioning_key="volume_profile_poc_mode",
    ),    StringPositioningSpec(
        effective_key="effective_break_even_movement_formula",
        source_key="break_even_movement_formula_source",
        request_attr="break_even_movement_formula",
        request_default="",
        positioning_key="break_even_movement_formula",
    ),
    StringPositioningSpec(
        effective_key="effective_break_even_proof_formula",
        source_key="break_even_proof_formula_source",
        request_attr="break_even_proof_formula",
        request_default="",
        positioning_key="break_even_proof_formula",
    ),
    StringPositioningSpec(
        effective_key="effective_break_even_activation_formula",
        source_key="break_even_activation_formula_source",
        request_attr="break_even_activation_formula",
        request_default="",
        positioning_key="break_even_activation_formula",
    ),
    StringPositioningSpec(
        effective_key="effective_break_even_trailing_handoff_formula",
        source_key="break_even_trailing_handoff_formula_source",
        request_attr="break_even_trailing_handoff_formula",
        request_default="",
        positioning_key="break_even_trailing_handoff_formula",
    ),
    StringPositioningSpec(
        effective_key="effective_time_exit_formula",
        source_key="time_exit_formula_source",
        request_attr="time_exit_formula",
        request_default="",
        positioning_key="time_exit_formula",
    ),
    StringPositioningSpec(
        effective_key="effective_adverse_flow_exit_formula",
        source_key="adverse_flow_exit_formula_source",
        request_attr="adverse_flow_exit_formula",
        request_default="",
        positioning_key="adverse_flow_exit_formula",
    ),
)


def _resolve_strategy_selection(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
) -> Dict[str, Any]:
    profile_strategy_selection_mode = (
        str(adaptive_profile_runtime.get("strategy_selection_mode", "")).strip().lower()
    )
    if profile_strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
        profile_strategy_selection_mode = ""
    requested_strategy_selection_mode = (
        str(request.strategy_selection_mode or "").strip().lower()
    )
    if requested_strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
        requested_strategy_selection_mode = ""
    effective_strategy_selection_mode = (
        requested_strategy_selection_mode
        or profile_strategy_selection_mode
        or str(aos_applied.get("strategy_selection_mode", "adaptive_top_n"))
        .strip()
        .lower()
        or "adaptive_top_n"
    )

    try:
        profile_max_active_strategies = int(
            adaptive_profile_runtime.get("max_active_strategies", 0)
        )
    except (TypeError, ValueError):
        profile_max_active_strategies = 0
    try:
        requested_max_active_strategies = (
            int(request.max_active_strategies)
            if request.max_active_strategies is not None
            else 0
        )
    except (TypeError, ValueError):
        requested_max_active_strategies = 0
    try:
        aos_max_active_strategies = int(aos_applied.get("max_active_strategies", 3))
    except (TypeError, ValueError):
        aos_max_active_strategies = 3

    effective_max_active_strategies = (
        requested_max_active_strategies
        or profile_max_active_strategies
        or aos_max_active_strategies
        or 3
    )
    effective_max_active_strategies = max(1, min(20, effective_max_active_strategies))
    return {
        "effective_strategy_selection_mode": effective_strategy_selection_mode,
        "effective_max_active_strategies": effective_max_active_strategies,
    }


def _resolve_positioning_config(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
) -> Dict[str, Any]:
    positioning_cfg_requested = bool(request.apply_positioning_config_on_start)
    positioning_cfg = (
        dict(aos_applied.get("positioning", {}))
        if positioning_cfg_requested
        and isinstance(aos_applied.get("positioning"), dict)
        else {}
    )
    return {
        "positioning_cfg_requested": positioning_cfg_requested,
        "positioning_cfg": positioning_cfg,
    }


def _resolve_l2_lookback_bars(*, request: Any, aos_l2_cfg: Dict[str, Any]) -> int:
    if int(request.l2_lookback_bars) != 3:
        return max(1, int(request.l2_lookback_bars))
    try:
        return max(1, int(aos_l2_cfg.get("lookback_bars", request.l2_lookback_bars)))
    except (TypeError, ValueError):
        return max(1, int(request.l2_lookback_bars))


def _resolve_l2_config(
    *,
    request: Any,
    aos_l2_cfg: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
    liquidity_sweep_detection_enabled: bool,
) -> Dict[str, Any]:
    requested_l2_only = bool(request.l2_only or bool(aos_l2_cfg.get("l2_only", False)))
    requested_l2_confirm = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    l2_auto_enabled_by_sweep = False
    l2_auto_enabled_source = "disabled"
    if bool(liquidity_sweep_detection_enabled):
        if not bool(requested_l2_only or requested_l2_confirm):
            requested_l2_confirm = True
            l2_auto_enabled_by_sweep = True
            l2_auto_enabled_source = "liquidity_sweep_guard"
        else:
            l2_auto_enabled_source = "already_enabled"

    return {
        "requested_l2_only": requested_l2_only,
        "requested_l2_confirm": requested_l2_confirm,
        "l2_auto_enabled_by_sweep": l2_auto_enabled_by_sweep,
        "l2_auto_enabled_source": l2_auto_enabled_source,
        "l2_min_delta": pick_l2_float(
            request_value=request.l2_min_delta,
            cfg_key="min_delta",
            profile_key="l2_min_delta",
            aos_l2_cfg=aos_l2_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
        ),
        "l2_min_imbalance": pick_l2_float(
            request_value=request.l2_min_imbalance,
            cfg_key="min_imbalance",
            profile_key="l2_min_imbalance",
            aos_l2_cfg=aos_l2_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
        ),
        "l2_min_iceberg_bias": pick_l2_float(
            request_value=request.l2_min_iceberg_bias,
            cfg_key="min_iceberg_bias",
            profile_key="l2_min_iceberg_bias",
            aos_l2_cfg=aos_l2_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
        ),
        "l2_lookback_bars": _resolve_l2_lookback_bars(
            request=request, aos_l2_cfg=aos_l2_cfg
        ),
        "l2_min_participation_ratio": pick_l2_float(
            request_value=request.l2_min_participation_ratio,
            cfg_key="min_participation_ratio",
            profile_key="l2_min_participation_ratio",
            aos_l2_cfg=aos_l2_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
        ),
        "l2_min_directional_consistency": pick_l2_float(
            request_value=request.l2_min_directional_consistency,
            cfg_key="min_directional_consistency",
            profile_key="l2_min_directional_consistency",
            aos_l2_cfg=aos_l2_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
        ),
        "l2_min_signed_aggression": pick_l2_float(
            request_value=request.l2_min_signed_aggression,
            cfg_key="min_signed_aggression",
            profile_key="l2_min_signed_aggression",
            aos_l2_cfg=aos_l2_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
        ),
    }


def _resolve_positioning_fields(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
    positioning_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    resolved: Dict[str, Any] = {}
    for spec in _FLOAT_POSITIONING_SPECS:
        value, source = helper_resolve_positioning_float(
            request_value=getattr(request, spec.request_attr, spec.request_default),
            request_default=spec.request_default,
            positioning_key=spec.positioning_key,
            positioning_cfg=positioning_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
            min_value=spec.min_value,
            max_value=spec.max_value,
            runtime_key=spec.runtime_key,
            runtime_positive_only=spec.runtime_positive_only,
        )
        resolved[spec.effective_key] = value
        resolved[spec.source_key] = source

    for spec in _INT_POSITIONING_SPECS:
        value, source = helper_resolve_positioning_int(
            request_value=getattr(request, spec.request_attr, spec.request_default),
            request_default=spec.request_default,
            positioning_key=spec.positioning_key,
            positioning_cfg=positioning_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
            min_value=spec.min_value,
            max_value=spec.max_value,
            runtime_key=spec.runtime_key,
            runtime_positive_only=spec.runtime_positive_only,
        )
        resolved[spec.effective_key] = value
        resolved[spec.source_key] = source

    for spec in _BOOL_POSITIONING_SPECS:
        value, source = helper_resolve_positioning_bool(
            request_value=getattr(request, spec.request_attr, spec.request_default),
            request_default=spec.request_default,
            positioning_key=spec.positioning_key,
            positioning_cfg=positioning_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
            runtime_key=spec.runtime_key,
        )
        resolved[spec.effective_key] = value
        resolved[spec.source_key] = source

    for spec in _STRING_POSITIONING_SPECS:
        value, source = helper_resolve_positioning_str(
            request_value=getattr(request, spec.request_attr, spec.request_default),
            request_default=spec.request_default,
            positioning_key=spec.positioning_key,
            positioning_cfg=positioning_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
            runtime_key=spec.runtime_key,
            strip=spec.strip,
        )
        resolved[spec.effective_key] = value
        resolved[spec.source_key] = source

    stop_loss_mode, stop_loss_mode_source = helper_resolve_stop_loss_mode(
        request_mode=getattr(request, "stop_loss_mode", None),
        positioning_cfg=positioning_cfg,
    )
    resolved["effective_stop_loss_mode"] = stop_loss_mode
    resolved["stop_loss_mode_source"] = stop_loss_mode_source

    adverse_flow_consistency, adverse_flow_consistency_source = (
        helper_resolve_adverse_flow_threshold(
            request_value=getattr(request, "adverse_flow_consistency_threshold", 0.45),
            request_default=0.45,
            positioning_key="adverse_flow_consistency_threshold",
            aos_key="adverse_flow_consistency_threshold",
            runtime_key="adverse_flow_consistency_threshold",
            positioning_cfg=positioning_cfg,
            aos_applied=aos_applied,
            adaptive_profile_runtime=adaptive_profile_runtime,
        )
    )
    adverse_book_pressure, adverse_book_pressure_source = (
        helper_resolve_adverse_flow_threshold(
            request_value=getattr(request, "adverse_book_pressure_threshold", 0.15),
            request_default=0.15,
            positioning_key="adverse_book_pressure_threshold",
            aos_key="adverse_book_pressure_threshold",
            runtime_key="adverse_book_pressure_threshold",
            positioning_cfg=positioning_cfg,
            aos_applied=aos_applied,
            adaptive_profile_runtime=adaptive_profile_runtime,
        )
    )
    resolved["effective_adverse_flow_consistency_threshold"] = adverse_flow_consistency
    resolved["adverse_flow_consistency_source"] = adverse_flow_consistency_source
    resolved["effective_adverse_book_pressure_threshold"] = adverse_book_pressure
    resolved["adverse_book_pressure_source"] = adverse_book_pressure_source

    effective_max_daily_trades = helper_resolve_optional_runtime_non_negative_int(
        "max_daily_trades", adaptive_profile_runtime
    )
    resolved["effective_max_daily_trades"] = effective_max_daily_trades
    resolved["max_daily_trades_source"] = (
        "adaptive_profile"
        if effective_max_daily_trades is not None
        else "ticker_config"
    )

    effective_mu_choppy_hard_block_enabled = helper_resolve_optional_runtime_bool(
        "mu_choppy_hard_block_enabled", adaptive_profile_runtime
    )
    resolved["effective_mu_choppy_hard_block_enabled"] = (
        effective_mu_choppy_hard_block_enabled
    )
    resolved["mu_choppy_hard_block_enabled_source"] = (
        "adaptive_profile"
        if effective_mu_choppy_hard_block_enabled is not None
        else "ticker_config"
    )
    return resolved


def _apply_intraday_profile_overrides(
    *,
    request: Any,
    intraday_levels_cfg: Dict[str, Any],
    positioning_values: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
) -> Dict[str, Any]:
    resolved = dict(intraday_levels_cfg)
    override_map = {
        "intraday_levels_micro_confirmation_enabled": (
            "effective_intraday_levels_micro_confirmation_enabled"
        ),
        "intraday_levels_micro_confirmation_bars": "effective_intraday_levels_micro_confirmation_bars",
        "intraday_levels_micro_confirmation_disable_for_sweep": (
            "effective_intraday_levels_micro_confirmation_disable_for_sweep"
        ),
        "intraday_levels_micro_confirmation_sweep_bars": (
            "effective_intraday_levels_micro_confirmation_sweep_bars"
        ),
        "intraday_levels_micro_confirmation_require_intrabar": (
            "effective_intraday_levels_micro_confirmation_require_intrabar"
        ),
        "intraday_levels_micro_confirmation_intrabar_window_seconds": (
            "effective_intraday_levels_micro_confirmation_intrabar_window_seconds"
        ),
        "intraday_levels_micro_confirmation_intrabar_min_coverage_points": (
            "effective_intraday_levels_micro_confirmation_intrabar_min_coverage_points"
        ),
        "intraday_levels_micro_confirmation_intrabar_min_move_pct": (
            "effective_intraday_levels_micro_confirmation_intrabar_min_move_pct"
        ),
        "intraday_levels_micro_confirmation_intrabar_min_push_ratio": (
            "effective_intraday_levels_micro_confirmation_intrabar_min_push_ratio"
        ),
        "intraday_levels_micro_confirmation_intrabar_max_spread_bps": (
            "effective_intraday_levels_micro_confirmation_intrabar_max_spread_bps"
        ),
    }
    for cfg_key, effective_key in override_map.items():
        if effective_key in positioning_values:
            resolved[cfg_key] = positioning_values[effective_key]

    # Unified profile strategy runtime can override intraday-level controls
    # when the same field was not explicitly provided at run start.
    request_fields = _request_fields_set(request)
    profile_intraday_keys = (
        "intraday_levels_entry_tolerance_pct",
        "intraday_levels_memory_enabled",
        "intraday_levels_memory_min_tests",
        "intraday_levels_memory_max_age_days",
        "intraday_levels_memory_decay_after_days",
        "intraday_levels_memory_decay_weight",
        "intraday_levels_memory_max_levels",
        "intraday_levels_poc_migration_enabled",
        "intraday_levels_poc_migration_interval_bars",
        "intraday_levels_poc_migration_trend_threshold_pct",
        "intraday_levels_poc_migration_range_threshold_pct",
        "intraday_levels_micro_confirmation_enabled",
        "intraday_levels_micro_confirmation_bars",
        "intraday_levels_micro_confirmation_disable_for_sweep",
        "intraday_levels_micro_confirmation_sweep_bars",
        "intraday_levels_micro_confirmation_require_intrabar",
        "intraday_levels_micro_confirmation_intrabar_window_seconds",
        "intraday_levels_micro_confirmation_intrabar_min_coverage_points",
        "intraday_levels_micro_confirmation_intrabar_min_move_pct",
        "intraday_levels_micro_confirmation_intrabar_min_push_ratio",
        "intraday_levels_micro_confirmation_intrabar_max_spread_bps",
    )
    if isinstance(adaptive_profile_runtime, dict) and adaptive_profile_runtime:
        for key in profile_intraday_keys:
            if key in request_fields:
                continue
            if key not in adaptive_profile_runtime:
                continue
            resolved[key] = adaptive_profile_runtime.get(key)

        # Re-normalize all intraday-level fields after profile overlays.
        normalized_proxy = type("IntradayProfileProxy", (), {})()
        for key, value in resolved.items():
            setattr(normalized_proxy, key, value)
        resolved = resolve_intraday_levels_config(normalized_proxy)
    return resolved


def _apply_context_risk_profile_overrides(
    *,
    request: Any,
    context_risk_cfg: Dict[str, Any],
    positioning_cfg: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
) -> Dict[str, Any]:
    resolved = dict(context_risk_cfg)

    for key, request_default in (
        ("context_aware_risk_enabled", False),
        ("context_risk_level_trail_enabled", True),
    ):
        value, _ = helper_resolve_positioning_bool(
            request_value=getattr(request, key, request_default),
            request_default=request_default,
            positioning_key=key,
            positioning_cfg=positioning_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
            runtime_key=key,
        )
        resolved[key] = bool(value)

    for key, request_default, min_value, max_value in (
        ("context_risk_sl_buffer_pct", 0.10, 0.0, None),
        ("context_risk_min_sl_pct", 0.30, 0.0, None),
        ("context_risk_min_room_pct", 0.08, 0.0, None),
        ("context_risk_min_effective_rr", 0.50, 0.0, None),
        ("context_risk_trailing_tighten_zone", 0.20, 0.0, 1.0),
        ("context_risk_trailing_tighten_factor", 0.50, 0.0, 1.0),
        ("context_risk_max_anchor_search_pct", 2.5, 0.1, None),
    ):
        value, _ = helper_resolve_positioning_float(
            request_value=getattr(request, key, request_default),
            request_default=request_default,
            positioning_key=key,
            positioning_cfg=positioning_cfg,
            adaptive_profile_runtime=adaptive_profile_runtime,
            min_value=min_value,
            max_value=max_value,
            runtime_key=key,
        )
        resolved[key] = float(value)

    value, _ = helper_resolve_positioning_int(
        request_value=getattr(request, "context_risk_min_level_tests_for_sl", 1),
        request_default=1,
        positioning_key="context_risk_min_level_tests_for_sl",
        positioning_cfg=positioning_cfg,
        adaptive_profile_runtime=adaptive_profile_runtime,
        min_value=0,
        runtime_key="context_risk_min_level_tests_for_sl",
    )
    resolved["context_risk_min_level_tests_for_sl"] = int(value)
    return resolved


def _parse_clamped_int(value: Any, *, min_value: int) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(min_value, parsed)


def _request_fields_set(request: Any) -> set[str]:
    fields = getattr(request, "model_fields_set", None)
    if isinstance(fields, set):
        return {str(item) for item in fields}
    legacy_fields = getattr(request, "__fields_set__", None)
    if isinstance(legacy_fields, set):
        return {str(item) for item in legacy_fields}
    return set()


def _resolve_regime_runtime_value(
    *,
    field_name: str,
    min_value: int,
    default_value: int,
    request: Any,
    aos_applied: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
) -> tuple[int, str]:
    profile_value = _parse_clamped_int(
        adaptive_profile_runtime.get(field_name),
        min_value=min_value,
    )
    if profile_value is not None:
        return profile_value, "adaptive_profile"

    aos_value = _parse_clamped_int(aos_applied.get(field_name), min_value=min_value)
    if aos_value is not None:
        return aos_value, "aos_applied"

    request_value = _parse_clamped_int(
        getattr(request, field_name, None), min_value=min_value
    )
    if request_value is not None:
        request_source = (
            "request" if field_name in _request_fields_set(request) else "default"
        )
        return request_value, request_source
    return default_value, "default"


def _resolve_runtime_basics(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
) -> Dict[str, Any]:
    regime_detection_minutes, regime_detection_minutes_source = (
        _resolve_regime_runtime_value(
            field_name="regime_detection_minutes",
            min_value=1,
            default_value=15,
            request=request,
            aos_applied=aos_applied,
            adaptive_profile_runtime=adaptive_profile_runtime,
        )
    )
    regime_refresh_bars, regime_refresh_bars_source = _resolve_regime_runtime_value(
        field_name="regime_refresh_bars",
        min_value=3,
        default_value=12,
        request=request,
        aos_applied=aos_applied,
        adaptive_profile_runtime=adaptive_profile_runtime,
    )
    try:
        account_size_usd = max(0.0, float(request.account_size_usd))
    except (TypeError, ValueError):
        account_size_usd = 10_000.0
    return {
        "regime_detection_minutes": regime_detection_minutes,
        "regime_detection_minutes_source": regime_detection_minutes_source,
        "regime_refresh_bars": regime_refresh_bars,
        "regime_refresh_bars_source": regime_refresh_bars_source,
        "account_size_usd": account_size_usd,
    }


def _resolve_runtime_stop_loss(
    *,
    context_aware_risk_enabled: bool,
    positioning_values: Dict[str, Any],
) -> Dict[str, Any]:
    effective_stop_loss_mode_runtime = str(
        positioning_values["effective_stop_loss_mode"]
    )
    effective_stop_loss_mode_source_runtime = str(
        positioning_values["stop_loss_mode_source"]
    )
    if (
        bool(context_aware_risk_enabled)
        and effective_stop_loss_mode_runtime == "capped"
    ):
        # Context-aware risk owns final SL placement; avoid pre-tightening via capped mode.
        effective_stop_loss_mode_runtime = "strategy"
        effective_stop_loss_mode_source_runtime = "context_risk_override"

    try:
        effective_fixed_stop_loss_pct = float(
            positioning_values["effective_fixed_stop_loss_pct"]
        )
    except (TypeError, ValueError):
        effective_fixed_stop_loss_pct = 0.0
    if effective_stop_loss_mode_runtime in {"fixed", "capped"} and (
        not math.isfinite(effective_fixed_stop_loss_pct)
        or effective_fixed_stop_loss_pct <= 0.0
    ):
        raise ValueError(
            "Fixed stop-loss % must be > 0 when stop mode is fixed or capped."
        )
    return {
        "effective_stop_loss_mode_runtime": effective_stop_loss_mode_runtime,
        "effective_stop_loss_mode_source_runtime": effective_stop_loss_mode_source_runtime,
        "effective_fixed_stop_loss_pct_runtime": effective_fixed_stop_loss_pct,
    }


def _build_trading_config_payload(
    *,
    request: Any,
    l2_cfg: Dict[str, Any],
    intraday_levels_cfg: Dict[str, Any],
    context_risk_cfg: Dict[str, Any],
    strategy_cfg: Dict[str, Any],
    positioning_values: Dict[str, Any],
    runtime_basics: Dict[str, Any],
    stop_loss_runtime: Dict[str, Any],
) -> Dict[str, Any]:
    payload = {
        "regime_detection_minutes": runtime_basics["regime_detection_minutes"],
        "regime_refresh_bars": runtime_basics["regime_refresh_bars"],
        "account_size_usd": runtime_basics["account_size_usd"],
        "risk_per_trade_pct": positioning_values["effective_risk_per_trade_pct"],
        "max_position_notional_pct": positioning_values[
            "effective_max_position_notional_pct"
        ],
        "max_fill_participation_rate": positioning_values[
            "effective_max_fill_participation_rate"
        ],
        "min_fill_ratio": positioning_values["effective_min_fill_ratio"],
        "enable_partial_take_profit": positioning_values[
            "effective_enable_partial_take_profit"
        ],
        "partial_take_profit_rr": positioning_values[
            "effective_partial_take_profit_rr"
        ],
        "partial_take_profit_fraction": positioning_values[
            "effective_partial_take_profit_fraction"
        ],
        "partial_flow_deterioration_min_r": positioning_values[
            "effective_partial_flow_deterioration_min_r"
        ],
        "partial_protect_min_mfe_r": positioning_values[
            "effective_partial_protect_min_mfe_r"
        ],
        "partial_flow_deterioration_skip_be": bool(
            positioning_values["effective_partial_flow_deterioration_skip_be"]
        ),
        "trailing_activation_pct": positioning_values[
            "effective_trailing_activation_pct"
        ],
        "break_even_buffer_pct": positioning_values["effective_break_even_buffer_pct"],
        "break_even_min_hold_bars": positioning_values[
            "effective_break_even_min_hold_bars"
        ],
        "break_even_activation_min_mfe_pct": positioning_values[
            "effective_break_even_activation_min_mfe_pct"
        ],
        "break_even_activation_min_r": positioning_values[
            "effective_break_even_activation_min_r"
        ],
        "break_even_activation_min_r_trending_5m": positioning_values[
            "effective_break_even_activation_min_r_trending_5m"
        ],
        "break_even_activation_min_r_choppy_5m": positioning_values[
            "effective_break_even_activation_min_r_choppy_5m"
        ],
        "break_even_activation_use_levels": bool(
            positioning_values["effective_break_even_activation_use_levels"]
        ),
        "break_even_activation_use_l2": bool(
            positioning_values["effective_break_even_activation_use_l2"]
        ),
        "break_even_level_buffer_pct": positioning_values[
            "effective_break_even_level_buffer_pct"
        ],
        "break_even_level_max_distance_pct": positioning_values[
            "effective_break_even_level_max_distance_pct"
        ],
        "break_even_level_min_confluence": positioning_values[
            "effective_break_even_level_min_confluence"
        ],
        "break_even_level_min_tests": positioning_values[
            "effective_break_even_level_min_tests"
        ],
        "break_even_l2_signed_aggression_min": positioning_values[
            "effective_break_even_l2_signed_aggression_min"
        ],
        "break_even_l2_imbalance_min": positioning_values[
            "effective_break_even_l2_imbalance_min"
        ],
        "break_even_l2_book_pressure_min": positioning_values[
            "effective_break_even_l2_book_pressure_min"
        ],
        "break_even_l2_spread_bps_max": positioning_values[
            "effective_break_even_l2_spread_bps_max"
        ],
        "break_even_costs_pct": positioning_values["effective_break_even_costs_pct"],
        "break_even_min_buffer_pct": positioning_values[
            "effective_break_even_min_buffer_pct"
        ],
        "break_even_atr_buffer_k": positioning_values[
            "effective_break_even_atr_buffer_k"
        ],
        "break_even_5m_atr_buffer_k": positioning_values[
            "effective_break_even_5m_atr_buffer_k"
        ],
        "break_even_tick_size": positioning_values["effective_break_even_tick_size"],
        "break_even_min_tick_buffer": positioning_values[
            "effective_break_even_min_tick_buffer"
        ],
        "break_even_anti_spike_bars": positioning_values[
            "effective_break_even_anti_spike_bars"
        ],
        "break_even_anti_spike_hits_required": positioning_values[
            "effective_break_even_anti_spike_hits_required"
        ],
        "break_even_anti_spike_require_close_beyond": bool(
            positioning_values["effective_break_even_anti_spike_require_close_beyond"]
        ),
        "break_even_5m_no_go_proximity_pct": positioning_values[
            "effective_break_even_5m_no_go_proximity_pct"
        ],
        "break_even_5m_mfe_atr_factor": positioning_values[
            "effective_break_even_5m_mfe_atr_factor"
        ],
        "break_even_5m_l2_bias_threshold": positioning_values[
            "effective_break_even_5m_l2_bias_threshold"
        ],
        "break_even_5m_l2_bias_tighten_factor": positioning_values[
            "effective_break_even_5m_l2_bias_tighten_factor"
        ],
        "break_even_movement_formula_enabled": positioning_values[
            "effective_break_even_movement_formula_enabled"
        ],
        "break_even_movement_formula": positioning_values[
            "effective_break_even_movement_formula"
        ],
        "break_even_proof_formula_enabled": positioning_values[
            "effective_break_even_proof_formula_enabled"
        ],
        "break_even_proof_formula": positioning_values[
            "effective_break_even_proof_formula"
        ],
        "break_even_activation_formula_enabled": positioning_values[
            "effective_break_even_activation_formula_enabled"
        ],
        "break_even_activation_formula": positioning_values[
            "effective_break_even_activation_formula"
        ],
        "break_even_trailing_handoff_formula_enabled": positioning_values[
            "effective_break_even_trailing_handoff_formula_enabled"
        ],
        "break_even_trailing_handoff_formula": positioning_values[
            "effective_break_even_trailing_handoff_formula"
        ],
        "trailing_enabled_in_choppy": positioning_values[
            "effective_trailing_enabled_in_choppy"
        ],
        "time_exit_bars": positioning_values["effective_time_exit_bars"],
        "time_exit_formula_enabled": positioning_values[
            "effective_time_exit_formula_enabled"
        ],
        "time_exit_formula": positioning_values["effective_time_exit_formula"],
        "adverse_flow_exit_enabled": positioning_values[
            "effective_adverse_flow_exit_enabled"
        ],
        "adverse_flow_threshold": positioning_values[
            "effective_adverse_flow_threshold"
        ],
        "adverse_flow_min_hold_bars": positioning_values[
            "effective_adverse_flow_min_hold_bars"
        ],
        "adverse_flow_consistency_threshold": positioning_values[
            "effective_adverse_flow_consistency_threshold"
        ],
        "adverse_book_pressure_threshold": positioning_values[
            "effective_adverse_book_pressure_threshold"
        ],
        "adverse_flow_exit_formula_enabled": positioning_values[
            "effective_adverse_flow_exit_formula_enabled"
        ],
        "adverse_flow_exit_formula": positioning_values[
            "effective_adverse_flow_exit_formula"
        ],
        "stop_loss_mode": stop_loss_runtime["effective_stop_loss_mode_runtime"],
        "fixed_stop_loss_pct": stop_loss_runtime[
            "effective_fixed_stop_loss_pct_runtime"
        ],
        "l2_confirm_enabled": l2_cfg["requested_l2_confirm"],
        "l2_min_delta": l2_cfg["l2_min_delta"],
        "l2_min_imbalance": l2_cfg["l2_min_imbalance"],
        "l2_min_iceberg_bias": l2_cfg["l2_min_iceberg_bias"],
        "l2_lookback_bars": l2_cfg["l2_lookback_bars"],
        "l2_min_participation_ratio": l2_cfg["l2_min_participation_ratio"],
        "l2_min_directional_consistency": l2_cfg["l2_min_directional_consistency"],
        "l2_min_signed_aggression": l2_cfg["l2_min_signed_aggression"],
        "tcbbo_gate_enabled": positioning_values["effective_tcbbo_gate_enabled"],
        "tcbbo_min_net_premium": positioning_values["effective_tcbbo_min_net_premium"],
        "tcbbo_sweep_boost": positioning_values["effective_tcbbo_sweep_boost"],
        "tcbbo_lookback_bars": positioning_values["effective_tcbbo_lookback_bars"],
        **intraday_levels_cfg,
        **context_risk_cfg,
        "cold_start_each_day": bool(request.cold_start_each_day),
        "strategy_selection_mode": strategy_cfg["effective_strategy_selection_mode"],
        "max_active_strategies": strategy_cfg["effective_max_active_strategies"],
    }
    if positioning_values["effective_max_daily_trades"] is not None:
        payload["max_daily_trades"] = positioning_values["effective_max_daily_trades"]
    if positioning_values["effective_mu_choppy_hard_block_enabled"] is not None:
        payload["mu_choppy_hard_block_enabled"] = positioning_values[
            "effective_mu_choppy_hard_block_enabled"
        ]
    return payload


def resolve_execution_config(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
) -> Dict[str, Any]:
    aos_l2_cfg = (
        aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}
    )
    strategy_cfg = _resolve_strategy_selection(
        request=request,
        aos_applied=aos_applied,
        adaptive_profile_runtime=adaptive_profile_runtime,
    )
    positioning_cfg_state = _resolve_positioning_config(
        request=request,
        aos_applied=aos_applied,
    )
    positioning_values = _resolve_positioning_fields(
        request=request,
        aos_applied=aos_applied,
        adaptive_profile_runtime=adaptive_profile_runtime,
        positioning_cfg=positioning_cfg_state["positioning_cfg"],
    )
    intraday_levels_cfg = _apply_intraday_profile_overrides(
        request=request,
        intraday_levels_cfg=resolve_intraday_levels_config(request),
        positioning_values=positioning_values,
        adaptive_profile_runtime=adaptive_profile_runtime,
    )
    l2_cfg = _resolve_l2_config(
        request=request,
        aos_l2_cfg=aos_l2_cfg,
        adaptive_profile_runtime=adaptive_profile_runtime,
        liquidity_sweep_detection_enabled=bool(
            intraday_levels_cfg.get("liquidity_sweep_detection_enabled", False)
        ),
    )
    context_risk_cfg = _apply_context_risk_profile_overrides(
        request=request,
        context_risk_cfg=resolve_context_risk_config(request),
        positioning_cfg=positioning_cfg_state["positioning_cfg"],
        adaptive_profile_runtime=adaptive_profile_runtime,
    )
    stop_loss_runtime = _resolve_runtime_stop_loss(
        context_aware_risk_enabled=bool(context_risk_cfg["context_aware_risk_enabled"]),
        positioning_values=positioning_values,
    )
    runtime_basics = _resolve_runtime_basics(
        request=request,
        aos_applied=aos_applied,
        adaptive_profile_runtime=adaptive_profile_runtime,
    )

    result_positioning_values = dict(positioning_values)
    result_positioning_values["effective_stop_loss_mode"] = stop_loss_runtime[
        "effective_stop_loss_mode_runtime"
    ]
    result_positioning_values["stop_loss_mode_source"] = stop_loss_runtime[
        "effective_stop_loss_mode_source_runtime"
    ]
    result_positioning_values["effective_fixed_stop_loss_pct"] = stop_loss_runtime[
        "effective_fixed_stop_loss_pct_runtime"
    ]

    trading_config_payload = _build_trading_config_payload(
        request=request,
        l2_cfg=l2_cfg,
        intraday_levels_cfg=intraday_levels_cfg,
        context_risk_cfg=context_risk_cfg,
        strategy_cfg=strategy_cfg,
        positioning_values=result_positioning_values,
        runtime_basics=runtime_basics,
        stop_loss_runtime=stop_loss_runtime,
    )

    return {
        "requested_l2_only": l2_cfg["requested_l2_only"],
        "requested_l2_confirm": l2_cfg["requested_l2_confirm"],
        "l2_min_delta": l2_cfg["l2_min_delta"],
        "l2_min_imbalance": l2_cfg["l2_min_imbalance"],
        "l2_min_iceberg_bias": l2_cfg["l2_min_iceberg_bias"],
        "l2_lookback_bars": l2_cfg["l2_lookback_bars"],
        "l2_min_participation_ratio": l2_cfg["l2_min_participation_ratio"],
        "l2_min_directional_consistency": l2_cfg["l2_min_directional_consistency"],
        "l2_min_signed_aggression": l2_cfg["l2_min_signed_aggression"],
        "liquidity_sweep_l2_auto_enabled": bool(l2_cfg["l2_auto_enabled_by_sweep"]),
        "liquidity_sweep_l2_auto_source": str(l2_cfg["l2_auto_enabled_source"]),
        "effective_regime_detection_minutes": runtime_basics[
            "regime_detection_minutes"
        ],
        "regime_detection_minutes_source": runtime_basics[
            "regime_detection_minutes_source"
        ],
        "effective_regime_refresh_bars": runtime_basics["regime_refresh_bars"],
        "regime_refresh_bars_source": runtime_basics["regime_refresh_bars_source"],
        **{f"effective_{key}": value for key, value in intraday_levels_cfg.items()},
        "effective_strategy_selection_mode": strategy_cfg[
            "effective_strategy_selection_mode"
        ],
        "effective_max_active_strategies": strategy_cfg[
            "effective_max_active_strategies"
        ],
        "positioning_cfg_requested": positioning_cfg_state["positioning_cfg_requested"],
        "positioning_cfg": positioning_cfg_state["positioning_cfg"],
        **result_positioning_values,
        **context_risk_cfg,
        "trading_config": trading_config_payload,
    }
