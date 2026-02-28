import { defaultStrategyApiUrl } from "../../utils";
import {
  MU_TICKER,
  START_MODE_FAST_RESTART,
  TRADE_EVAL_MODE_STANDARD,
  MU_DEFAULT_MOMENTUM_APPLY_TO_STRATEGIES,
  MU_INTRADAY_NON_OVERFIT_BASELINE,
} from "./runConfigCore";

export const buildDefaultRunId = () => {
  const nonce = Math.random().toString(36).slice(2, 7);
  return `backtest-${Date.now()}-${nonce}`;
};

export const applyMuMomentumDefaults = (draft, ticker, previousTicker) => {
  const upperTicker = String(ticker || "").trim().toUpperCase();
  const priorTicker = String(previousTicker || "").trim().toUpperCase();
  if (upperTicker !== MU_TICKER || priorTicker === MU_TICKER) {
    return draft;
  }
  return {
    ...draft,
    // Favor fast first-start defaults; reproducibility presets remain available.
    momentum_diversification_override_enabled: false,
    momentum_apply_to_strategies: MU_DEFAULT_MOMENTUM_APPLY_TO_STRATEGIES,
    include_extended_hours: false,
    l2_confirm_enabled: true,
    tcbbo_gate_enabled: true,
    apply_aos_optimizations_on_start: false,
    start_mode: START_MODE_FAST_RESTART,
    ...MU_INTRADAY_NON_OVERFIT_BASELINE,
  };
};

export const buildDefaultRunConfig = () => ({
  run_id: buildDefaultRunId(),
  ticker: "",
  date: "",
  date_from: "",
  date_to: "",
  trade_eval_mode: TRADE_EVAL_MODE_STANDARD,
  include_extended_hours: false,
  data_file: null,
  strategy_api_url: defaultStrategyApiUrl,
  risk_per_trade_pct: 1.0,
  max_position_notional_pct: 100.0,
  max_fill_participation_rate: 0.2,
  min_fill_ratio: 0.35,
  trailing_stop_pct: 0.8,
  global_exit_rr_ratio: 2.0,
  global_risk_atr_stop_multiplier: 1.0,
  global_risk_volume_stop_pct: 1.0,
  global_risk_min_stop_loss_pct: 0.15,
  trailing_activation_pct: 0.20,
  break_even_buffer_pct: 0.03,
  break_even_min_hold_bars: 3,
  break_even_activation_min_mfe_pct: 0.45,
  break_even_activation_min_r: 1.5,
  break_even_activation_min_r_trending_5m: 1.8,
  break_even_activation_min_r_choppy_5m: 1.2,
  break_even_activation_use_levels: true,
  break_even_activation_use_l2: true,
  enable_partial_take_profit: true,
  partial_take_profit_rr: 2.0,
  partial_take_profit_fraction: 0.4,
  partial_flow_deterioration_min_r: 0.5,
  partial_flow_deterioration_skip_be: true,
  trailing_enabled_in_choppy: false,
  time_exit_bars: 40,
  adverse_flow_exit_enabled: true,
  adverse_flow_threshold: 0.12,
  adverse_flow_min_hold_bars: 3,
  stop_loss_mode: "strategy",
  fixed_stop_loss_pct: 0.0,
  l2_only: false,
  l2_confirm_enabled: true,
  l2_min_imbalance: 0.0,
  l2_min_directional_consistency: 0.0,
  l2_min_signed_aggression: 0.0,
  l2_lookback_bars: 3,
  tcbbo_gate_enabled: true,
  tcbbo_min_net_premium: 0.0,
  tcbbo_sweep_boost: 5.0,
  tcbbo_lookback_bars: 5,
  intraday_levels_enabled: true,
  intraday_levels_swing_left_bars: 2,
  intraday_levels_swing_right_bars: 2,
  intraday_levels_test_tolerance_pct: 0.08,
  intraday_levels_break_tolerance_pct: 0.05,
  intraday_levels_breakout_volume_lookback: 20,
  intraday_levels_breakout_volume_multiplier: 1.2,
  intraday_levels_volume_profile_bin_size_pct: 0.05,
  intraday_levels_value_area_pct: 0.7,
  intraday_levels_entry_quality_enabled: true,
  intraday_levels_min_levels_for_context: 1,
  intraday_levels_entry_tolerance_pct: 0.1,
  intraday_levels_break_cooldown_bars: 3,
  intraday_levels_rotation_max_tests: 2,
  intraday_levels_rotation_volume_max_ratio: 0.95,
  intraday_levels_recent_bounce_lookback_bars: 6,
  intraday_levels_require_recent_bounce_for_mean_reversion: true,
  intraday_levels_momentum_break_max_age_bars: 3,
  intraday_levels_momentum_min_room_pct: 0.15,
  intraday_levels_momentum_min_broken_ratio: 0.3,
  intraday_levels_min_confluence_score: 1,
  intraday_levels_memory_enabled: true,
  intraday_levels_memory_min_tests: 2,
  intraday_levels_memory_max_age_days: 5,
  intraday_levels_memory_decay_after_days: 2,
  intraday_levels_memory_decay_weight: 0.5,
  intraday_levels_memory_max_levels: 12,
  intraday_levels_opening_range_enabled: true,
  intraday_levels_opening_range_minutes: 30,
  intraday_levels_opening_range_break_tolerance_pct: 0.05,
  intraday_levels_poc_migration_enabled: true,
  intraday_levels_poc_migration_interval_bars: 30,
  intraday_levels_poc_migration_trend_threshold_pct: 0.2,
  intraday_levels_poc_migration_range_threshold_pct: 0.1,
  intraday_levels_composite_profile_enabled: true,
  intraday_levels_composite_profile_days: 3,
  intraday_levels_composite_profile_current_day_weight: 1.0,
  intraday_levels_spike_detection_enabled: true,
  intraday_levels_spike_min_wick_ratio: 0.6,
  intraday_levels_prior_day_anchors_enabled: true,
  intraday_levels_gap_analysis_enabled: true,
  intraday_levels_gap_min_pct: 0.3,
  intraday_levels_gap_momentum_threshold_pct: 2.0,
  intraday_levels_rvol_filter_enabled: true,
  intraday_levels_rvol_lookback_bars: 20,
  intraday_levels_rvol_min_threshold: 0.8,
  intraday_levels_rvol_strong_threshold: 1.5,
  intraday_levels_adaptive_window_enabled: true,
  intraday_levels_adaptive_window_min_bars: 6,
  intraday_levels_adaptive_window_rvol_threshold: 0.5,
  intraday_levels_adaptive_window_atr_ratio_max: 1.5,
  intraday_levels_micro_confirmation_enabled: false,
  intraday_levels_micro_confirmation_bars: 2,
  intraday_levels_confluence_sizing_enabled: false,
  liquidity_sweep_detection_enabled: true,
  sweep_min_aggression_z: -2.0,
  sweep_min_book_pressure_z: 1.5,
  sweep_max_price_change_pct: 0.05,
  sweep_atr_buffer_multiplier: 0.5,
  context_aware_risk_enabled: false,
  context_risk_sl_buffer_pct: 0.10,
  context_risk_min_sl_pct: 0.50,
  context_risk_min_room_pct: 0.08,
  context_risk_min_effective_rr: 0.5,
  context_risk_trailing_tighten_zone: 0.2,
  context_risk_trailing_tighten_factor: 0.5,
  context_risk_level_trail_enabled: true,
  context_risk_max_anchor_search_pct: 2.5,
  context_risk_min_level_tests_for_sl: 1,
  account_size_usd: 10000,
  regime_detection_minutes: 15,
  strategy_selection_mode: "all_enabled",
  max_active_strategies: 20,
  momentum_diversification_override_enabled: false,
  momentum_diversification_enabled: true,
  momentum_require_l2_coverage: true,
  momentum_route_enabled: true,
  momentum_route_require_l2_coverage: true,
  momentum_min_flow_score: 58,
  momentum_min_directional_consistency: 0.45,
  momentum_min_signed_aggression: 0.04,
  momentum_min_imbalance: 0.02,
  momentum_min_cvd: 0,
  momentum_min_directional_price_change_pct: 0,
  momentum_min_price_trend_efficiency: 0,
  momentum_min_last_bar_body_ratio: 0,
  momentum_min_last_bar_close_location: 0,
  momentum_min_delta_acceleration: 0,
  momentum_min_delta_price_divergence: 0,
  momentum_route_flow_score_impulse: 64,
  momentum_fail_fast_exit_enabled: true,
  momentum_fail_fast_max_bars: 3,
  momentum_fail_fast_signed_aggression_max: -0.08,
  momentum_fail_fast_book_pressure_max: -0.1,
  momentum_fail_fast_directional_consistency_max: 0.2,
  momentum_apply_to_strategies: "momentum_flow",
  momentum_allowed_micro_regimes: "",
  momentum_blocked_micro_regimes: "",
  momentum_sleeves: [],
  checkpoint_path: null,
  auto_save_checkpoint: true,
  start_mode: START_MODE_FAST_RESTART,
  apply_aos_optimizations_on_start: false,
});

export const buildNormalizedIntradayLevels = (config) => {
  const intradayLevelsEnabled = !!config.intraday_levels_enabled;
  const ticker = String(config.ticker || "").trim().toUpperCase();
  const forceMuEntryQualityGate = intradayLevelsEnabled && ticker === MU_TICKER;
  return {
    intraday_levels_enabled: intradayLevelsEnabled,
    intraday_levels_swing_left_bars: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_swing_left_bars || 2)),
    ),
    intraday_levels_swing_right_bars: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_swing_right_bars || 2)),
    ),
    intraday_levels_test_tolerance_pct: Math.max(
      0,
      Number(config.intraday_levels_test_tolerance_pct || 0),
    ),
    intraday_levels_break_tolerance_pct: Math.max(
      0,
      Number(config.intraday_levels_break_tolerance_pct || 0),
    ),
    intraday_levels_breakout_volume_lookback: Math.max(
      2,
      Math.trunc(Number(config.intraday_levels_breakout_volume_lookback || 20)),
    ),
    intraday_levels_breakout_volume_multiplier: Math.max(
      1,
      Number(config.intraday_levels_breakout_volume_multiplier || 1),
    ),
    intraday_levels_volume_profile_bin_size_pct: Math.max(
      0.01,
      Number(config.intraday_levels_volume_profile_bin_size_pct || 0.01),
    ),
    intraday_levels_value_area_pct: Math.min(
      0.95,
      Math.max(0.5, Number(config.intraday_levels_value_area_pct || 0.7)),
    ),
    intraday_levels_entry_quality_enabled: forceMuEntryQualityGate
      ? true
      : !!config.intraday_levels_entry_quality_enabled,
    intraday_levels_min_levels_for_context: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_min_levels_for_context || 2)),
    ),
    intraday_levels_entry_tolerance_pct: Math.max(
      0.01,
      Number(config.intraday_levels_entry_tolerance_pct || 0.1),
    ),
    intraday_levels_break_cooldown_bars: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_break_cooldown_bars || 6)),
    ),
    intraday_levels_rotation_max_tests: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_rotation_max_tests || 2)),
    ),
    intraday_levels_rotation_volume_max_ratio: Math.min(
      2.0,
      Math.max(0.1, Number(config.intraday_levels_rotation_volume_max_ratio || 0.95)),
    ),
    intraday_levels_recent_bounce_lookback_bars: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_recent_bounce_lookback_bars || 6)),
    ),
    intraday_levels_require_recent_bounce_for_mean_reversion:
      !!config.intraday_levels_require_recent_bounce_for_mean_reversion,
    intraday_levels_momentum_break_max_age_bars: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_momentum_break_max_age_bars || 3)),
    ),
    intraday_levels_momentum_min_room_pct: Math.max(
      0.01,
      Number(config.intraday_levels_momentum_min_room_pct || 0.3),
    ),
    intraday_levels_momentum_min_broken_ratio: Math.min(
      1.0,
      Math.max(0.0, Number(config.intraday_levels_momentum_min_broken_ratio || 0.3)),
    ),
    intraday_levels_min_confluence_score: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_min_confluence_score || 2)),
    ),
    intraday_levels_memory_enabled: !!config.intraday_levels_memory_enabled,
    intraday_levels_memory_min_tests: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_memory_min_tests || 2)),
    ),
    intraday_levels_memory_max_age_days: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_memory_max_age_days || 5)),
    ),
    intraday_levels_memory_decay_after_days: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_memory_decay_after_days || 2)),
    ),
    intraday_levels_memory_decay_weight: Math.min(
      1.0,
      Math.max(0.1, Number(config.intraday_levels_memory_decay_weight || 0.5)),
    ),
    intraday_levels_memory_max_levels: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_memory_max_levels || 12)),
    ),
    intraday_levels_opening_range_enabled: !!config.intraday_levels_opening_range_enabled,
    intraday_levels_opening_range_minutes: Math.max(
      5,
      Math.trunc(Number(config.intraday_levels_opening_range_minutes || 30)),
    ),
    intraday_levels_opening_range_break_tolerance_pct: Math.max(
      0.01,
      Number(config.intraday_levels_opening_range_break_tolerance_pct || 0.05),
    ),
    intraday_levels_poc_migration_enabled: !!config.intraday_levels_poc_migration_enabled,
    intraday_levels_poc_migration_interval_bars: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_poc_migration_interval_bars || 30)),
    ),
    intraday_levels_poc_migration_trend_threshold_pct: Math.max(
      0.01,
      Number(config.intraday_levels_poc_migration_trend_threshold_pct || 0.2),
    ),
    intraday_levels_poc_migration_range_threshold_pct: Math.max(
      0.01,
      Number(config.intraday_levels_poc_migration_range_threshold_pct || 0.1),
    ),
    intraday_levels_composite_profile_enabled: !!config.intraday_levels_composite_profile_enabled,
    intraday_levels_composite_profile_days: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_composite_profile_days || 3)),
    ),
    intraday_levels_composite_profile_current_day_weight: Math.max(
      0.1,
      Number(config.intraday_levels_composite_profile_current_day_weight || 1.0),
    ),
    intraday_levels_spike_detection_enabled: !!config.intraday_levels_spike_detection_enabled,
    intraday_levels_spike_min_wick_ratio: Math.min(
      0.95,
      Math.max(0.4, Number(config.intraday_levels_spike_min_wick_ratio || 0.6)),
    ),
    intraday_levels_prior_day_anchors_enabled: !!config.intraday_levels_prior_day_anchors_enabled,
    intraday_levels_gap_analysis_enabled: !!config.intraday_levels_gap_analysis_enabled,
    intraday_levels_gap_min_pct: Math.max(0, Number(config.intraday_levels_gap_min_pct || 0.3)),
    intraday_levels_gap_momentum_threshold_pct: Math.max(
      0.1,
      Number(config.intraday_levels_gap_momentum_threshold_pct || 2.0),
    ),
    intraday_levels_rvol_filter_enabled: !!config.intraday_levels_rvol_filter_enabled,
    intraday_levels_rvol_lookback_bars: Math.max(
      5,
      Math.trunc(Number(config.intraday_levels_rvol_lookback_bars || 20)),
    ),
    intraday_levels_rvol_min_threshold: Math.max(
      0,
      Number(config.intraday_levels_rvol_min_threshold || 0.8),
    ),
    intraday_levels_rvol_strong_threshold: Math.max(
      0.1,
      Number(config.intraday_levels_rvol_strong_threshold || 1.5),
    ),
    intraday_levels_adaptive_window_enabled: !!config.intraday_levels_adaptive_window_enabled,
    intraday_levels_adaptive_window_min_bars: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_adaptive_window_min_bars || 6)),
    ),
    intraday_levels_adaptive_window_rvol_threshold: Math.max(
      0,
      Number(config.intraday_levels_adaptive_window_rvol_threshold || 1.0),
    ),
    intraday_levels_adaptive_window_atr_ratio_max: Math.max(
      0.1,
      Number(config.intraday_levels_adaptive_window_atr_ratio_max || 1.5),
    ),
    intraday_levels_micro_confirmation_enabled: !!config.intraday_levels_micro_confirmation_enabled,
    intraday_levels_micro_confirmation_bars: Math.max(
      1,
      Math.trunc(Number(config.intraday_levels_micro_confirmation_bars || 2)),
    ),
    intraday_levels_confluence_sizing_enabled: !!config.intraday_levels_confluence_sizing_enabled,
    liquidity_sweep_detection_enabled: !!config.liquidity_sweep_detection_enabled,
    sweep_min_aggression_z: Number(config.sweep_min_aggression_z ?? -2.0),
    sweep_min_book_pressure_z: Number(config.sweep_min_book_pressure_z ?? 1.5),
    sweep_max_price_change_pct: Math.max(
      0,
      Number(config.sweep_max_price_change_pct ?? 0.05),
    ),
  };
};

export const buildNormalizedContextRisk = (config) => ({
  context_aware_risk_enabled: !!config.context_aware_risk_enabled,
  context_risk_sl_buffer_pct: Math.max(0, Number(config.context_risk_sl_buffer_pct || 0.05)),
  context_risk_min_sl_pct: Math.max(0, Number(config.context_risk_min_sl_pct || 0.50)),
  context_risk_min_room_pct: Math.max(0, Number(config.context_risk_min_room_pct || 0.08)),
  context_risk_min_effective_rr: Math.max(0, Number(config.context_risk_min_effective_rr || 0.5)),
  context_risk_trailing_tighten_zone: Math.max(
    0,
    Math.min(1, Number(config.context_risk_trailing_tighten_zone || 0.2)),
  ),
  context_risk_trailing_tighten_factor: Math.max(
    0,
    Math.min(1, Number(config.context_risk_trailing_tighten_factor || 0.5)),
  ),
  context_risk_level_trail_enabled: !!config.context_risk_level_trail_enabled,
  context_risk_max_anchor_search_pct: Math.max(
    0.1,
    Number(config.context_risk_max_anchor_search_pct || 1.5),
  ),
  context_risk_min_level_tests_for_sl: Math.max(
    0,
    Math.trunc(Number(config.context_risk_min_level_tests_for_sl || 1)),
  ),
  sweep_atr_buffer_multiplier: Math.max(
    0,
    Number(config.sweep_atr_buffer_multiplier ?? 0.5),
  ),
});
