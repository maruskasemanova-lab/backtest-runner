from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict

from src.services.session_runner_models import Result
from src.services.session_runner_payload_validator import ValidateStrategyBarPayload


class StrategyBarPayloadInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    ticker: str
    bar: "StrategyBarInput"
    timestamp: datetime | str
    warmup_only: Optional[bool] = None
    intrabar_quotes_1s: Optional[List["StrategyIntrabarQuoteInput"]] = None
    current_bar_index: int = 0
    include_pending_entry: bool = False


class StrategyBarInput(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

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


class StrategyIntrabarQuoteInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    s: int
    bid: float
    ask: float


class StrategyReferenceBarInput(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    ticker: str = "QQQ"
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None


StrategyReferenceBarLike = StrategyReferenceBarInput | Dict[str, Any]
StrategyIntrabarQuoteLike = StrategyIntrabarQuoteInput | Dict[str, float]


@dataclass(frozen=True)
class StrategyBarPayloadBuildContext:
    ref_bars_map: Mapping[str, StrategyReferenceBarLike]
    should_attach_intrabar_quotes: bool = False
    intrabar_recalc_enabled: bool = False
    l2_manager_name: Optional[str] = None
    intrabar_quotes_1s: Optional[List[StrategyIntrabarQuoteLike]] = None


def stringify_bar_timestamp(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _dump_intrabar_quotes(
    quotes: Optional[List[StrategyIntrabarQuoteInput]],
) -> Optional[List[Dict[str, float]]]:
    if not quotes:
        return None
    return [quote.model_dump(mode="python") for quote in quotes]


def _resolve_reference_bar_input(
    ref_bar: StrategyReferenceBarLike,
) -> StrategyReferenceBarInput:
    if isinstance(ref_bar, StrategyReferenceBarInput):
        return ref_bar
    return StrategyReferenceBarInput.model_validate(ref_bar)


def build_strategy_bar_payload(
    *,
    payload_input: StrategyBarPayloadInput,
    l2_payload_keys: Sequence[str],
    tcbbo_payload_keys: Sequence[str],
    ref_bars_map: Mapping[str, StrategyReferenceBarLike],
) -> Dict[str, Any]:
    resolved_timestamp = stringify_bar_timestamp(payload_input.timestamp)
    bar = payload_input.bar.model_dump(mode="python")
    payload: Dict[str, Any] = {
        "run_id": payload_input.run_id,
        "ticker": payload_input.ticker,
        "timestamp": resolved_timestamp,
        "open": bar["open"],
        "high": bar["high"],
        "low": bar["low"],
        "close": bar["close"],
        "volume": bar["volume"],
        "vwap": bar.get("vwap"),
    }
    if payload_input.warmup_only is not None:
        payload["warmup_only"] = bool(payload_input.warmup_only)
    intrabar_quotes = _dump_intrabar_quotes(payload_input.intrabar_quotes_1s)
    if intrabar_quotes:
        payload["intrabar_quotes_1s"] = intrabar_quotes

    for key in l2_payload_keys:
        if key in bar:
            payload[key] = bar.get(key)
    for key in tcbbo_payload_keys:
        if key in bar:
            payload[key] = bar.get(key)

    ref_bar = ref_bars_map.get(resolved_timestamp)
    if ref_bar:
        typed_ref_bar = _resolve_reference_bar_input(ref_bar)
        payload["ref_ticker"] = typed_ref_bar.ticker
        payload["ref_open"] = typed_ref_bar.open
        payload["ref_high"] = typed_ref_bar.high
        payload["ref_low"] = typed_ref_bar.low
        payload["ref_close"] = typed_ref_bar.close
        payload["ref_volume"] = typed_ref_bar.volume
    return payload


def build_validated_strategy_bar_payload(
    *,
    validate_strategy_bar_payload: ValidateStrategyBarPayload,
    payload_input: StrategyBarPayloadInput,
    l2_payload_keys: Sequence[str],
    tcbbo_payload_keys: Sequence[str],
    ref_bars_map: Mapping[str, Dict[str, Any]],
) -> Result[Dict[str, Any], str]:
    payload = build_strategy_bar_payload(
        payload_input=payload_input,
        l2_payload_keys=l2_payload_keys,
        tcbbo_payload_keys=tcbbo_payload_keys,
        ref_bars_map=ref_bars_map,
    )
    return validate_strategy_bar_payload(payload)


class StrategyBarPayloadBuilder:
    def __init__(
        self,
        *,
        l2_payload_keys: Sequence[str],
        tcbbo_payload_keys: Sequence[str],
        validate_strategy_bar_payload: ValidateStrategyBarPayload,
        logger: logging.Logger,
    ):
        self._l2_payload_keys = tuple(l2_payload_keys)
        self._tcbbo_payload_keys = tuple(tcbbo_payload_keys)
        self._validate_strategy_bar_payload = validate_strategy_bar_payload
        self._logger = logger

    def build_live_payload(
        self,
        *,
        payload_input: StrategyBarPayloadInput,
        build_context: StrategyBarPayloadBuildContext,
    ) -> Dict[str, Any]:
        payload = build_strategy_bar_payload(
            payload_input=payload_input,
            l2_payload_keys=self._l2_payload_keys,
            tcbbo_payload_keys=self._tcbbo_payload_keys,
            ref_bars_map=build_context.ref_bars_map,
        )

        if payload.get("tcbbo_has_data"):
            self._logger.info(
                "[TCBBO-PAYLOAD-DEBUG] bar=%d Sending TCBBO data: %s",
                payload_input.current_bar_index,
                {key: payload.get(key) for key in self._tcbbo_payload_keys},
            )

        if (
            not build_context.should_attach_intrabar_quotes
            and payload_input.current_bar_index <= 3
        ):
            self._logger.debug(
                "[INTRABAR-DEBUG] bar=%s should_attach=False intrabar_recalc=%s l2_manager=%s",
                payload_input.current_bar_index,
                build_context.intrabar_recalc_enabled,
                build_context.l2_manager_name,
            )
        if build_context.should_attach_intrabar_quotes:
            intrabar_quotes = build_context.intrabar_quotes_1s
            typed_intrabar_quotes = (
                [
                    StrategyIntrabarQuoteInput.model_validate(quote)
                    for quote in intrabar_quotes
                ]
                if intrabar_quotes
                else None
            )
            dumped_intrabar_quotes = _dump_intrabar_quotes(typed_intrabar_quotes)
            if dumped_intrabar_quotes:
                payload["intrabar_quotes_1s"] = dumped_intrabar_quotes
            elif payload_input.current_bar_index <= 3:
                self._logger.debug(
                    "[INTRABAR-DEBUG] bar=%s quotes=None for %s",
                    payload_input.current_bar_index,
                    payload_input.timestamp,
                )
        return payload

    def build_validated_live_payload(
        self,
        *,
        payload_input: StrategyBarPayloadInput,
        build_context: StrategyBarPayloadBuildContext,
    ) -> Result[Dict[str, Any], str]:
        payload = self.build_live_payload(
            payload_input=payload_input,
            build_context=build_context,
        )
        return self._validate_strategy_bar_payload(payload)
