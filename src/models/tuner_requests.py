from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AdaptiveTunerRequest(BaseModel):
    ticker: str
    date_from: str
    date_to: str
    strategy_api_url: str = "http://localhost:8001"
    method: str = "grid"  # grid | random | optuna
    n_trials: int = 16
    score_metric: str = "pnl_pct"  # pnl_pct | pnl_dollars | win_rate | trade_adjusted | robust
    seed: int = 42
    adaptive_version: int = 1  # 1 = flat search, 2 = multi-dimensional vector discovery
    persist_best: bool = False
    allow_mock_data: bool = False
    comparable_mode: bool = True
    l2_required: bool = False
    l2_confirm_enabled: bool = True
    l2_only: bool = False
    # Quick approximate mode: tune on sampled days and expand trial budget.
    quick_mode: bool = False
    quick_max_days: int = 2
    quick_trial_boost: int = 3
    # --- V1 search dimensions ---
    selection_modes: Optional[List[str]] = None
    max_active_options: Optional[List[int]] = None
    min_active_bars_options: Optional[List[int]] = None
    switch_cooldown_bars_options: Optional[List[int]] = None
    flow_bias_options: Optional[List[bool]] = None
    ohlcv_fallback_options: Optional[List[bool]] = None
    # --- V2 multi-dimensional vector search dimensions ---
    # Strategy dimension: sets of strategies to evaluate
    strategy_sets: Optional[List[List[str]]] = None
    # L2 threshold dimension
    l2_min_delta_options: Optional[List[float]] = None
    l2_min_imbalance_options: Optional[List[float]] = None
    l2_min_signed_aggression_options: Optional[List[float]] = None
    l2_min_directional_consistency_options: Optional[List[float]] = None
    l2_min_participation_ratio_options: Optional[List[float]] = None
    l2_lookback_bars_options: Optional[List[int]] = None
    # Regime dimension: sets of allowed regimes
    regime_filter_sets: Optional[List[List[str]]] = None
    # Evidence engine dimension
    base_threshold_options: Optional[List[float]] = None
    min_confirming_sources_options: Optional[List[int]] = None
    # Per-strategy parameter tuning dimension
    min_confidence_options: Optional[List[float]] = None
    atr_stop_multiplier_options: Optional[List[float]] = None
    rr_ratio_options: Optional[List[float]] = None
    # Time-of-day dimension: sets of allowed trading hours (list of lists of ints, e.g. [[9,10],[9,10,11,12,13,14,15]])
    time_window_sets: Optional[List[List[int]]] = None
    # Flow-informed exit thresholds (v2)
    adverse_flow_consistency_options: Optional[List[float]] = None
    adverse_book_pressure_options: Optional[List[float]] = None
    # Exit parameter dims (v2)
    time_exit_bars_options: Optional[List[int]] = None
    trailing_stop_pct_options: Optional[List[float]] = None
    # Momentum diversification dims (v2)
    momentum_diversification_enabled_options: Optional[List[bool]] = None
    momentum_route_enabled_options: Optional[List[bool]] = None
    momentum_min_flow_score_options: Optional[List[float]] = None
    momentum_min_directional_consistency_options: Optional[List[float]] = None
    momentum_min_signed_aggression_options: Optional[List[float]] = None
    momentum_min_imbalance_options: Optional[List[float]] = None
    momentum_min_cvd_options: Optional[List[float]] = None
    momentum_min_directional_price_change_pct_options: Optional[List[float]] = None
    momentum_min_price_trend_efficiency_options: Optional[List[float]] = None
    momentum_min_last_bar_body_ratio_options: Optional[List[float]] = None
    momentum_min_last_bar_close_location_options: Optional[List[float]] = None
    momentum_min_delta_acceleration_options: Optional[List[float]] = None
    momentum_min_delta_price_divergence_options: Optional[List[float]] = None
    momentum_route_flow_score_impulse_options: Optional[List[float]] = None
    momentum_fail_fast_exit_enabled_options: Optional[List[bool]] = None
    momentum_fail_fast_max_bars_options: Optional[List[int]] = None
    # Context-aware exit response dims (v2) – Phase 3
    context_regime_flip_tighten_stop_pct_options: Optional[List[float]] = None
    context_regime_flip_shorten_time_pct_options: Optional[List[float]] = None
    context_regime_flip_exit_when_losing_options: Optional[List[bool]] = None
    context_regime_flip_exit_loss_threshold_pct_options: Optional[List[float]] = None
    context_flow_reversal_move_to_breakeven_options: Optional[List[bool]] = None
    context_flow_reversal_exit_when_losing_options: Optional[List[bool]] = None
    context_momentum_stall_time_multiplier_options: Optional[List[float]] = None
    context_volatility_spike_tighten_pct_options: Optional[List[float]] = None
    context_response_grace_bars_options: Optional[List[int]] = None
    # Regime-conditional strategy maps: each map assigns strategies per macro regime
    regime_strategy_map_sets: Optional[List[Optional[Dict[str, List[str]]]]] = None
    # Neighborhood search: half candidates are baseline perturbations
    neighborhood_search: bool = False
    # V2 analysis options
    include_vector_analysis: bool = True
    min_trades_per_vector: int = 3
