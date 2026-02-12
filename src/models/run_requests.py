from typing import Any, Dict, Optional, Union

from pydantic import BaseModel


class StartRunRequest(BaseModel):
    run_id: str
    ticker: str
    date: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    data_file: Optional[str] = None  # If None, auto-discover from available data
    strategy_api_url: str = "http://localhost:8001"
    regime_detection_minutes: int = 15
    regime_refresh_bars: int = 12
    trailing_stop_pct: Optional[float] = None
    account_size_usd: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    max_position_notional_pct: float = 100.0
    max_fill_participation_rate: float = 0.20
    min_fill_ratio: float = 0.35
    enable_partial_take_profit: bool = True
    partial_take_profit_rr: float = 1.0
    partial_take_profit_fraction: float = 0.5
    trailing_activation_pct: float = 0.15
    break_even_buffer_pct: float = 0.03
    break_even_min_hold_bars: int = 2
    trailing_enabled_in_choppy: bool = False
    time_exit_bars: int = 40
    adverse_flow_exit_enabled: bool = True
    adverse_flow_threshold: float = 0.12
    adverse_flow_min_hold_bars: int = 3
    adverse_flow_consistency_threshold: float = 0.45
    adverse_book_pressure_threshold: float = 0.15
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
    strategy_selection_mode: Optional[str] = None
    max_active_strategies: Optional[int] = None
    momentum_diversification_override: Optional[Dict[str, Any]] = None
    intrabar_execution_recalc_1s: Optional[bool] = None
    cold_start_each_day: bool = False
    comparable_mode: bool = False
    apply_positioning_config_on_start: bool = True
    # Whether runner should re-apply ticker defaults from strategy_overrides.json
    # during run start. Keep enabled by default for backward compatibility.
    apply_ticker_overrides_on_start: bool = True
    # Checkpoint: warm-start from a previous backtest's learning state
    checkpoint_path: Optional[str] = None
    auto_save_checkpoint: bool = True
    # Internal override used by adaptive tuner parallel workers.
    aos_config_path: Optional[str] = None


class PlayRequest(BaseModel):
    # Accept strings like "max" / "10hz" as well as raw millisecond values.
    speed_ms: Optional[Union[int, str]] = 100
