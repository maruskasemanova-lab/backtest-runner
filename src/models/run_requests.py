from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


class StartRunRequest(BaseModel):
    run_id: str
    book_pressure_block_z_threshold: float = 1.65
    break_even_l2_proof_book_pressure_threshold: float = 0.06
    break_even_l2_proof_imbalance_threshold: float = 0.1
    break_even_l2_proof_signed_threshold: float = 0.07
    break_even_proof_logic: str = "OR"
    ev_relaxation_enabled: bool = True
    ev_relaxation_factor: float = 0.5
    ev_relaxation_threshold: float = 10.0
    hard_l2_block_enabled: bool = True
    intraday_levels_bounce_conflict_buffer_bars: int = 2
    micro_confirmation_mode: str = "volume_delta"
    micro_confirmation_volume_delta_min_pct: float = 0.6
    signed_aggression_block_z_threshold: float = 1.65
    strategy_time_windows: Optional[Dict[str, Any]] = None
    time_of_day_filter_enabled: bool = True
    volume_profile_poc_mode: str = "favor_bounce_mean_reversion"
    weak_l2_aggression_threshold: float = 0.05
    weak_l2_break_even_min_hold_bars: int = 1
    weak_l2_fast_break_even_enabled: bool = False
    ticker: str
    date: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    # Optional intraday playback slice (ISO datetime). When provided, runner bars
    # are filtered to this window after the day/date range is loaded.
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    # Optional trading-only intraday slice (ISO datetime). Bars outside this window
    # can still be loaded as warmup but are sent to the strategy engine with
    # warmup_only semantics (no trading entries/exits).
    trade_start_time: Optional[str] = None
    trade_end_time: Optional[str] = None
    # Run-level session scope override:
    # - True  => include pre/post-market bars
    # - False => regular session bars only
    # - None  => use AOS time-filter settings
    include_extended_hours: Optional[bool] = None
    data_file: Optional[str] = None  # If None, auto-discover from available data
    strategy_api_url: str = "http://localhost:8001"
    regime_detection_minutes: int = 15
    regime_refresh_bars: int = 12
    trailing_stop_pct: Optional[float] = None
    global_exit_rr_ratio: Optional[float] = None
    global_risk_atr_stop_multiplier: Optional[float] = None
    global_risk_volume_stop_pct: Optional[float] = None
    global_risk_min_stop_loss_pct: Optional[float] = None
    account_size_usd: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    max_position_notional_pct: float = 100.0
    max_fill_participation_rate: float = 0.20
    min_fill_ratio: float = 0.35
    enable_partial_take_profit: bool = True
    partial_take_profit_rr: float = 1.0
    partial_take_profit_fraction: float = 0.5
    trailing_activation_pct: float = 0.20
    break_even_buffer_pct: float = 0.03
    break_even_min_hold_bars: int = 3
    break_even_activation_min_mfe_pct: Optional[float] = None
    break_even_activation_min_r: Optional[float] = None
    break_even_activation_min_r_trending_5m: Optional[float] = None
    break_even_activation_min_r_choppy_5m: Optional[float] = None
    break_even_activation_use_levels: bool = True
    break_even_activation_use_l2: bool = True
    break_even_level_buffer_pct: float = 0.02
    break_even_level_max_distance_pct: float = 0.60
    break_even_level_min_confluence: int = 2
    break_even_level_min_tests: int = 1
    break_even_l2_signed_aggression_min: float = 0.12
    break_even_l2_imbalance_min: float = 0.15
    break_even_l2_book_pressure_min: float = 0.10
    break_even_l2_spread_bps_max: float = 12.0
    break_even_costs_pct: float = 0.03
    break_even_min_buffer_pct: float = 0.05
    break_even_atr_buffer_k: float = 0.10
    break_even_5m_atr_buffer_k: float = 0.10
    break_even_tick_size: float = 0.01
    break_even_min_tick_buffer: int = 1
    break_even_anti_spike_bars: int = 1
    break_even_anti_spike_hits_required: int = 2
    break_even_anti_spike_require_close_beyond: bool = True
    break_even_5m_no_go_proximity_pct: float = 0.10
    break_even_5m_mfe_atr_factor: float = 0.15
    break_even_5m_l2_bias_threshold: float = 0.10
    break_even_5m_l2_bias_tighten_factor: float = 0.85
    break_even_movement_formula_enabled: bool = False
    break_even_movement_formula: str = ""
    break_even_proof_formula_enabled: bool = False
    break_even_proof_formula: str = ""
    break_even_activation_formula_enabled: bool = False
    break_even_activation_formula: str = ""
    break_even_trailing_handoff_formula_enabled: bool = False
    break_even_trailing_handoff_formula: str = ""
    trailing_enabled_in_choppy: bool = False
    time_exit_bars: int = 40
    time_exit_formula_enabled: bool = False
    time_exit_formula: str = ""
    adverse_flow_exit_enabled: bool = True
    adverse_flow_threshold: float = 0.12
    adverse_flow_min_hold_bars: int = 3
    adverse_flow_consistency_threshold: float = 0.45
    adverse_book_pressure_threshold: float = 0.15
    adverse_flow_exit_formula_enabled: bool = False
    adverse_flow_exit_formula: str = ""
    stop_loss_mode: str = "strategy"
    fixed_stop_loss_pct: float = 0.0
    allow_mock_data: bool = False
    l2_only: bool = False
    l2_confirm_enabled: bool = False
    l2_min_delta: float = 0.0
    l2_min_imbalance: float = 0.0
    l2_min_iceberg_bias: float = 0.0
    l2_lookback_bars: int = 3
    l2_min_participation_ratio: float = 0.0
    l2_min_directional_consistency: float = 0.0
    l2_min_signed_aggression: float = 0.0
    intraday_levels_enabled: bool = True
    intraday_levels_swing_left_bars: int = 2
    intraday_levels_swing_right_bars: int = 2
    intraday_levels_test_tolerance_pct: float = 0.08
    intraday_levels_break_tolerance_pct: float = 0.05
    intraday_levels_breakout_volume_lookback: int = 20
    intraday_levels_breakout_volume_multiplier: float = 1.2
    intraday_levels_volume_profile_bin_size_pct: float = 0.05
    intraday_levels_value_area_pct: float = 0.70
    intraday_levels_entry_quality_enabled: bool = True
    intraday_levels_min_levels_for_context: int = 1
    intraday_levels_entry_tolerance_pct: float = 0.10
    intraday_levels_break_cooldown_bars: int = 3
    intraday_levels_rotation_max_tests: int = 2
    intraday_levels_rotation_volume_max_ratio: float = 0.95
    intraday_levels_recent_bounce_lookback_bars: int = 6
    intraday_levels_require_recent_bounce_for_mean_reversion: bool = True
    intraday_levels_momentum_break_max_age_bars: int = 3
    intraday_levels_momentum_min_room_pct: float = 0.15
    intraday_levels_momentum_min_broken_ratio: float = 0.30
    intraday_levels_min_confluence_score: int = 1
    intraday_levels_memory_enabled: bool = True
    intraday_levels_memory_min_tests: int = 2
    intraday_levels_memory_max_age_days: int = 5
    intraday_levels_memory_decay_after_days: int = 2
    intraday_levels_memory_decay_weight: float = 0.50
    intraday_levels_memory_max_levels: int = 12
    intraday_levels_opening_range_enabled: bool = True
    intraday_levels_opening_range_minutes: int = 30
    intraday_levels_opening_range_break_tolerance_pct: float = 0.05
    intraday_levels_poc_migration_enabled: bool = True
    intraday_levels_poc_migration_interval_bars: int = 30
    intraday_levels_poc_migration_trend_threshold_pct: float = 0.20
    intraday_levels_poc_migration_range_threshold_pct: float = 0.10
    intraday_levels_composite_profile_enabled: bool = True
    intraday_levels_composite_profile_days: int = 3
    intraday_levels_composite_profile_current_day_weight: float = 1.0
    intraday_levels_spike_detection_enabled: bool = True
    intraday_levels_spike_min_wick_ratio: float = 0.60
    intraday_levels_prior_day_anchors_enabled: bool = True
    intraday_levels_gap_analysis_enabled: bool = True
    intraday_levels_gap_min_pct: float = 0.30
    intraday_levels_gap_momentum_threshold_pct: float = 2.0
    intraday_levels_rvol_filter_enabled: bool = True
    intraday_levels_rvol_lookback_bars: int = 20
    intraday_levels_rvol_min_threshold: float = 0.80
    intraday_levels_rvol_strong_threshold: float = 1.50
    intraday_levels_adaptive_window_enabled: bool = True
    intraday_levels_adaptive_window_min_bars: int = 6
    intraday_levels_adaptive_window_rvol_threshold: float = 0.5
    intraday_levels_adaptive_window_atr_ratio_max: float = 1.5
    intraday_levels_micro_confirmation_enabled: bool = False
    intraday_levels_micro_confirmation_bars: int = 2
    intraday_levels_micro_confirmation_disable_for_sweep: bool = False
    intraday_levels_micro_confirmation_sweep_bars: int = 0
    intraday_levels_micro_confirmation_require_intrabar: bool = False
    intraday_levels_micro_confirmation_intrabar_window_seconds: int = 5
    intraday_levels_micro_confirmation_intrabar_min_coverage_points: int = 3
    intraday_levels_micro_confirmation_intrabar_min_move_pct: float = 0.02
    intraday_levels_micro_confirmation_intrabar_min_push_ratio: float = 0.10
    intraday_levels_micro_confirmation_intrabar_max_spread_bps: float = 12.0
    intraday_levels_confluence_sizing_enabled: bool = False
    liquidity_sweep_detection_enabled: bool = False
    sweep_min_aggression_z: float = -2.0
    sweep_min_book_pressure_z: float = 1.5
    sweep_max_price_change_pct: float = 0.05
    sweep_atr_buffer_multiplier: float = 0.5
    # TCBBO options flow gate
    tcbbo_gate_enabled: bool = False
    tcbbo_min_net_premium: float = 0.0
    tcbbo_sweep_boost: float = 5.0
    tcbbo_lookback_bars: int = 5
    # Context-aware risk: dynamically adjust SL/TP based on intraday levels
    context_aware_risk_enabled: bool = False
    context_risk_sl_buffer_pct: float = 0.10
    context_risk_min_sl_pct: float = 0.30
    context_risk_min_room_pct: float = 0.08
    context_risk_min_effective_rr: float = 0.5
    context_risk_trailing_tighten_zone: float = 0.2
    context_risk_trailing_tighten_factor: float = 0.5
    context_risk_level_trail_enabled: bool = True
    context_risk_max_anchor_search_pct: float = 2.5
    context_risk_min_level_tests_for_sl: int = 1
    strategy_selection_mode: Optional[str] = None
    max_active_strategies: Optional[int] = None
    momentum_diversification_override: Optional[Dict[str, Any]] = None
    # Optional start-time playback evaluation path:
    # - "standard" => minute bars only
    # - "intrabar_1s" => intrabar quotes at 1-second checkpoints
    # - "intrabar_5s" => intrabar quotes at 5-second checkpoints
    trade_eval_mode: Optional[str] = None
    intrabar_execution_recalc_1s: Optional[bool] = None
    cold_start_each_day: bool = False
    comparable_mode: bool = False
    apply_positioning_config_on_start: bool = True
    partial_protect_min_mfe_r: Optional[float] = None
    # Whether runner should re-apply ticker defaults from strategy_overrides.json
    # during run start. Keep enabled by default for backward compatibility.
    apply_ticker_overrides_on_start: bool = True
    # Whether runner should sync AOS/adaptive strategy params to Strategy API
    # during run start. Disable for faster starts when FE already synced params.
    apply_aos_optimizations_on_start: bool = True
    # Optional orchestrator reset scope override for faster starts:
    # - "all" (default deterministic cold reset)
    # - "session" (faster, preserves learned state)
    # - "learning"
    orchestrator_reset_scope: Optional[str] = None
    # Checkpoint: warm-start from a previous backtest's learning state
    checkpoint_path: Optional[str] = None
    auto_save_checkpoint: bool = True
    # Internal override used by adaptive tuner parallel workers.
    aos_config_path: Optional[str] = None
    # Optional regime filter override: list of allowed regimes (e.g. ["TRENDING", "CHOPPY"]).
    # Empty list = allow all regimes. None = use ticker-specific default from aos_config.json.
    regime_filter: Optional[List[str]] = None


class PrewarmRunRequest(BaseModel):
    ticker: str
    # "range" uses date/date_from/date_to, "ticker" resolves full available ticker coverage.
    prewarm_scope: str = "range"
    date: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    # Optional prewarm session-scope override (same semantics as StartRunRequest).
    include_extended_hours: Optional[bool] = None
    data_file: Optional[str] = None
    allow_mock_data: bool = False
    l2_only: bool = False
    l2_confirm_enabled: bool = False
    l2_min_delta: float = 0.0
    l2_min_imbalance: float = 0.0
    l2_min_iceberg_bias: float = 0.0
    l2_lookback_bars: int = 3
    l2_min_participation_ratio: float = 0.0
    l2_min_directional_consistency: float = 0.0
    l2_min_signed_aggression: float = 0.0
    strategy_selection_mode: Optional[str] = None
    max_active_strategies: Optional[int] = None
    apply_positioning_config_on_start: bool = True
    comparable_mode: bool = False
    aos_config_path: Optional[str] = None


class PlayRequest(BaseModel):
    # Accept strings like "max" / "10hz" as well as raw millisecond values.
    speed_ms: Optional[Union[int, str]] = 100
    # Optional playback override for in-trade evaluation path:
    # - "standard" => minute bars only (faster)
    # - "intrabar_1s" => include 1-second intrabar quotes for each processed minute bar
    # - "intrabar_5s" => intrabar evaluation with 5-second quote checkpoints (faster than 1s)
    trade_eval_mode: Optional[str] = None
