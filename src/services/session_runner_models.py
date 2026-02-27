from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E


Result = Union[Ok[T], Err[E]]
PayloadLike = Union[BaseModel, Dict[str, Any], None]


class ExecutionLifecycle(str, Enum):
    INITIALIZED = "INITIALIZED"
    FLAT = "FLAT"
    PENDING_ENTRY = "PENDING_ENTRY"
    IN_POSITION = "IN_POSITION"
    END_OF_DAY = "END_OF_DAY"


class StrategyBarIntrabarQuotePayload(BaseModel):
    s: int
    bid: float
    ask: float


class StrategyBarPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    ticker: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None
    l2_schema_version: Optional[str] = None
    l2_delta: Optional[float] = None
    l2_buy_volume: Optional[float] = None
    l2_sell_volume: Optional[float] = None
    l2_volume: Optional[float] = None
    l2_imbalance: Optional[float] = None
    l2_bid_depth_total: Optional[float] = None
    l2_ask_depth_total: Optional[float] = None
    l2_book_pressure: Optional[float] = None
    l2_book_pressure_change: Optional[float] = None
    l2_iceberg_buy_count: Optional[int] = None
    l2_iceberg_sell_count: Optional[int] = None
    l2_iceberg_bias: Optional[float] = None
    l2_quality_coverage_ratio: Optional[float] = None
    l2_quality_trade_ticks: Optional[int] = None
    l2_quality_book_updates: Optional[int] = None
    l2_quality_flags: Optional[List[str]] = None
    l2_quality: Optional[Dict[str, Any]] = None
    l2_cumulative_delta: Optional[float] = None
    l2_signed_aggression: Optional[float] = None
    l2_absorption_rate: Optional[float] = None
    l2_delta_price_divergence: Optional[float] = None
    l2_delta_acceleration: Optional[float] = None
    tcbbo_net_premium: Optional[float] = None
    tcbbo_cumulative_net_premium: Optional[float] = None
    tcbbo_call_buy_premium: Optional[float] = None
    tcbbo_put_buy_premium: Optional[float] = None
    tcbbo_call_sell_premium: Optional[float] = None
    tcbbo_put_sell_premium: Optional[float] = None
    tcbbo_sweep_count: Optional[int] = None
    tcbbo_sweep_premium: Optional[float] = None
    tcbbo_trade_count: Optional[int] = None
    tcbbo_has_data: Optional[bool] = None
    warmup_only: bool = False
    intrabar_quotes_1s: Optional[List[StrategyBarIntrabarQuotePayload]] = None
    ref_ticker: Optional[str] = None
    ref_open: Optional[float] = None
    ref_high: Optional[float] = None
    ref_low: Optional[float] = None
    ref_close: Optional[float] = None
    ref_volume: Optional[float] = None


class StrategyResponsePayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class StrategyBreakEvenPayload(StrategyResponsePayload):
    armed: Optional[bool] = None
    trigger_rr: Optional[float] = None
    stop_price: Optional[float] = None


class StrategyIndicatorsPayload(StrategyResponsePayload):
    trend_efficiency: Optional[float] = None
    volatility: Optional[float] = None
    adx: Optional[float] = None
    atr: Optional[float] = None


class StrategyL2QualityPayload(StrategyResponsePayload):
    has_l2: Optional[bool] = None
    quality_score: Optional[float] = None
    coverage_ratio: Optional[float] = None
    trade_ticks: Optional[int] = None
    book_updates: Optional[int] = None
    flags: List[str] = Field(default_factory=list)


class StrategyContextRiskPayload(StrategyResponsePayload):
    risk_pct: Optional[float] = None
    effective_rr: Optional[float] = None
    sl_reason: Optional[str] = None
    tp_reason: Optional[str] = None
    skip: Optional[bool] = None
    skip_reason: Optional[str] = None
    original_sl: Optional[float] = None
    adjusted_sl: Optional[float] = None
    original_tp: Optional[float] = None
    adjusted_tp: Optional[float] = None


class StrategySessionSummaryPayload(StrategyResponsePayload):
    run_id: Optional[str] = None
    ticker: Optional[str] = None
    date: Optional[str] = None
    regime: Optional[str] = None
    micro_regime: Optional[str] = None
    strategy: Optional[str] = None
    total_trades: Optional[int] = None
    winning_trades: Optional[int] = None
    losing_trades: Optional[int] = None
    win_rate: Optional[float] = None
    total_pnl_pct: Optional[float] = None
    total_pnl_dollars: Optional[float] = None
    bars_processed: Optional[int] = None
    success: Optional[bool] = None
    selection_warnings: List[str] = Field(default_factory=list)


class StrategyIntradayLevelsPayload(StrategyResponsePayload):
    intraday_levels_enabled: Optional[bool] = None
    intraday_levels_entry_quality_enabled: Optional[bool] = None
    intraday_levels_min_levels_for_context: Optional[int] = None
    intraday_levels_min_confluence_score: Optional[int] = None
    gate: Optional[str] = None
    score: Optional[float] = None
    level_count: Optional[int] = None


class StrategyLayerScoresPayload(StrategyResponsePayload):
    engine: Optional[str] = None


class StrategySignalRejectedPayload(StrategyResponsePayload):
    gate: Optional[str] = None
    reason: Optional[str] = None


class StrategyGoldenSetupPayload(StrategyResponsePayload):
    passed: Optional[bool] = None
    reason: Optional[str] = None
    score: Optional[float] = None


class StrategyIntrabarEvalCheckpointPayload(StrategyResponsePayload):
    s: Optional[int] = None
    layer_scores: Optional[StrategyLayerScoresPayload] = None
    signal_rejected: Optional[StrategySignalRejectedPayload] = None
    candidate_diagnostics: Optional["StrategyCandidateDiagnosticsPayload"] = None


class StrategyIntrabarEvalTracePayload(StrategyResponsePayload):
    checkpoints: List[StrategyIntrabarEvalCheckpointPayload] = Field(
        default_factory=list
    )


class StrategyTcbboConfirmationPayload(StrategyResponsePayload):
    confidence_boost: Optional[float] = None
    sweep_aligned: Optional[bool] = None
    net_premium: Optional[float] = None
    cumulative_net_premium: Optional[float] = None
    sweep_count: Optional[int] = None
    sweep_premium: Optional[float] = None
    trade_count: Optional[int] = None
    has_data: Optional[bool] = None


class StrategyCandidateDiagnosticsPayload(StrategyResponsePayload):
    score: Optional[float] = None


class StrategyOrderFlowPayload(StrategyResponsePayload):
    signed_aggression: Optional[float] = None
    book_pressure_avg: Optional[float] = None
    book_pressure_trend: Optional[float] = None
    book_pressure_confirmed: Optional[bool] = None


class StrategyLevelContextPayload(StrategyResponsePayload):
    gate: Optional[str] = None
    passed: Optional[bool] = None
    reason: Optional[str] = None
    score: Optional[float] = None


class StrategyLiquiditySweepPayload(StrategyResponsePayload):
    detected: Optional[bool] = None
    atr: Optional[float] = None


class StrategyRiskControlsPayload(StrategyResponsePayload):
    stop_loss_mode: Optional[str] = None
    fixed_stop_loss_pct: Optional[float] = None
    effective_stop_loss: Optional[float] = None
    strategy_stop_loss: Optional[float] = None


class StrategyTradeCostsPayload(StrategyResponsePayload):
    total: Optional[float] = None


class StrategyEntryQualityDiagnosticsPayload(StrategyResponsePayload):
    is_first_bar_stop_loss: Optional[bool] = None
    near_confluence_score: Optional[float] = None


class StrategySwitchGuardPayload(StrategyResponsePayload):
    cooldown_bars: Optional[int] = None
    min_active_bars_before_switch: Optional[int] = None


class StrategyMicroConfirmationPayload(StrategyResponsePayload):
    ready: Optional[bool] = None
    passed: Optional[bool] = None
    required_bars: Optional[int] = None
    confirm_bars: Optional[int] = None
    reason: Optional[str] = None


class StrategyIntrabarConfirmationPayload(StrategyResponsePayload):
    ready: Optional[bool] = None
    passed: Optional[bool] = None
    reason: Optional[str] = None
    window_seconds: Optional[int] = None
    min_coverage_points: Optional[int] = None
    min_move_pct: Optional[float] = None
    min_push_ratio: Optional[float] = None
    max_spread_bps: Optional[float] = None


class StrategySignalMetadataPayload(StrategyResponsePayload):
    candidate_diagnostics: Optional[StrategyCandidateDiagnosticsPayload] = None
    order_flow: Optional[StrategyOrderFlowPayload] = None
    level_context: Optional[StrategyLevelContextPayload] = None
    tcbbo_confirmation: Optional[StrategyTcbboConfirmationPayload] = None
    break_even: Optional[StrategyBreakEvenPayload] = None
    context_risk: Optional[StrategyContextRiskPayload] = None
    liquidity_sweep: Optional[StrategyLiquiditySweepPayload] = None
    risk_controls: Optional[StrategyRiskControlsPayload] = None
    sweep_triggered: Optional[bool] = None


class StrategySignalPayload(StrategyResponsePayload):
    price: Optional[float] = None
    signal: Optional[str] = None
    strategy: Optional[str] = None
    strategy_name: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Optional[StrategySignalMetadataPayload] = None


class StrategyRegimeUpdatePayload(StrategyResponsePayload):
    regime: Optional[str] = None
    strategy: Optional[str] = None
    strategies: List[str] = Field(default_factory=list)
    indicators: StrategyIndicatorsPayload = Field(
        default_factory=StrategyIndicatorsPayload
    )
    switch_guard: Optional[StrategySwitchGuardPayload] = None
    selection_warnings: List[str] = Field(default_factory=list)


class StrategyPositionOpenedPayload(StrategyResponsePayload):
    entry_price: Optional[float] = None
    side: Optional[str] = None
    strategy: Optional[str] = None
    size: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[StrategySignalMetadataPayload] = None


class StrategyPositionClosedPayload(StrategyResponsePayload):
    exit_price: Optional[float] = None
    side: Optional[str] = None
    exit_reason: Optional[str] = None
    pnl_pct: Optional[float] = None
    pnl_dollars: Optional[float] = None
    entry_price: Optional[float] = None
    entry_time: Optional[str] = None
    bars_held: Optional[int] = None
    size: Optional[float] = None
    strategy: Optional[str] = None
    costs: Optional[StrategyTradeCostsPayload] = None
    gross_pnl_pct: Optional[float] = None
    gross_pnl_dollars: Optional[float] = None
    cost_usd: Optional[float] = None
    cost_pct: Optional[float] = None
    pnl_usd: Optional[float] = None
    position_notional_usd: Optional[float] = None
    schema_version: Optional[int] = None
    level_context: Optional[StrategyLevelContextPayload] = None
    flow_snapshot: Optional[StrategyOrderFlowPayload] = None
    signal_metadata: Optional[StrategySignalMetadataPayload] = None
    break_even: Optional[StrategyBreakEvenPayload] = None
    entry_quality_diagnostics: Optional[StrategyEntryQualityDiagnosticsPayload] = None
    flow_strategy: Optional[bool] = None
    book_pressure_confirmed: Optional[bool] = None
    book_pressure_avg: Optional[float] = None
    book_pressure_trend: Optional[float] = None
    signed_aggression: Optional[float] = None
    regime: Optional[str] = None


class StrategyBarResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    phase: Optional[str] = None
    action: Optional[str] = None
    regime: Optional[str] = None
    micro_regime: Optional[str] = None
    strategy: Optional[str] = None
    selected_strategy: Optional[str] = None
    strategies: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    indicators: StrategyIndicatorsPayload = Field(
        default_factory=StrategyIndicatorsPayload
    )
    selection_warnings: List[str] = Field(default_factory=list)
    signals: List[StrategySignalPayload] = Field(default_factory=list)
    signal: Optional[StrategySignalPayload] = None
    regime_update: Optional[StrategyRegimeUpdatePayload] = None
    position_opened: Optional[StrategyPositionOpenedPayload] = None
    position_closed: Optional[StrategyPositionClosedPayload] = None
    break_even: Optional[StrategyBreakEvenPayload] = None
    session_summary: Optional[StrategySessionSummaryPayload] = None
    intraday_levels: Optional[StrategyIntradayLevelsPayload] = None
    context_risk: Optional[StrategyContextRiskPayload] = None
    l2_quality: Optional[StrategyL2QualityPayload] = None
    tcbbo_confirmation: Optional[StrategyTcbboConfirmationPayload] = None
    micro_confirmation: Optional[StrategyMicroConfirmationPayload] = None
    intrabar_confirmation: Optional[StrategyIntrabarConfirmationPayload] = None
    layer_scores: Optional[StrategyLayerScoresPayload] = None
    signal_rejected: Optional[StrategySignalRejectedPayload] = None
    golden_setup: Optional[StrategyGoldenSetupPayload] = None
    intrabar_eval_trace: Optional[StrategyIntrabarEvalTracePayload] = None
    queued_for_next_bar: bool = False
    stale_pending_signal_dropped: bool = False
    stale_pending_signal_age_bars: Optional[int] = None
    pending_signal_ttl_bars: Optional[int] = None
    warmup_only: bool = False


def dump_payload(
    payload: PayloadLike,
    *,
    exclude_none: bool = True,
    exclude_unset: bool = True,
) -> Dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, BaseModel):
        return payload.model_dump(
            mode="python",
            exclude_none=exclude_none,
            exclude_unset=exclude_unset,
        )
    if isinstance(payload, dict):
        return dict(payload)
    return {}


def dump_payload_or_none(
    payload: PayloadLike,
    *,
    exclude_none: bool = True,
    exclude_unset: bool = True,
) -> Optional[Dict[str, Any]]:
    dumped = dump_payload(
        payload,
        exclude_none=exclude_none,
        exclude_unset=exclude_unset,
    )
    return dumped or None
