from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from src.services.session_runner_models import (
    StrategyBarResponse,
    StrategySignalMetadataPayload,
    StrategySignalPayload,
    dump_payload,
    dump_payload_or_none,
)


SafeFloat = Callable[[Any], Optional[float]]


@dataclass(frozen=True)
class StrategySelectionOptions:
    active_strategies: List[str]
    alternative_strategies: List[str]


@dataclass(frozen=True)
class SignalMarkerSnapshot:
    price: Any
    signal_type: str
    strategy: str
    confidence: Any
    reasoning: str
    stop_loss: Any
    take_profit: Any


def resolve_intraday_levels_payload(
    response: Any,
) -> Optional[Dict[str, Any]]:
    if isinstance(response, StrategyBarResponse):
        return dump_payload_or_none(response.intraday_levels)

    payload = dump_payload(response).get("intraday_levels")
    return dict(payload) if isinstance(payload, dict) else None


def resolve_strategy_selection_options(
    strategy: str,
    strategies_payload: Any,
) -> StrategySelectionOptions:
    active_strategies = [
        str(name).strip()
        for name in (strategies_payload if isinstance(strategies_payload, list) else [])
        if str(name).strip()
    ]
    strategy_token = str(strategy).strip()
    if strategy_token.lower() == "adaptive":
        alternative_strategies = list(active_strategies)
    else:
        alternative_strategies = [
            name for name in active_strategies if name != strategy_token
        ]
    return StrategySelectionOptions(
        active_strategies=active_strategies,
        alternative_strategies=alternative_strategies,
    )


def apply_intraday_levels_details(
    details: Dict[str, Any],
    intraday_levels_payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    enriched = dict(details)
    if intraday_levels_payload is not None:
        enriched["intraday_levels"] = dict(intraday_levels_payload)
    return enriched


def enrich_signal_marker_details(
    details: Dict[str, Any],
    *,
    signal: Any,
    response_tcbbo_confirmation: Any,
    intraday_levels_payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    enriched = apply_intraday_levels_details(details, intraday_levels_payload)
    if isinstance(signal, StrategySignalPayload):
        signal_metadata = dump_payload_or_none(signal.metadata)
        level_context = (
            dump_payload_or_none(signal.metadata.level_context)
            if isinstance(signal.metadata, StrategySignalMetadataPayload)
            else None
        )
        flow_snapshot = (
            dump_payload_or_none(signal.metadata.order_flow)
            if isinstance(signal.metadata, StrategySignalMetadataPayload)
            else None
        )
        tcbbo_confirmation = (
            dump_payload_or_none(signal.metadata.tcbbo_confirmation)
            if isinstance(signal.metadata, StrategySignalMetadataPayload)
            else None
        )
    else:
        signal_payload = dump_payload(signal)
        signal_metadata = signal_payload.get("metadata")
        level_context = (
            signal_metadata.get("level_context")
            if isinstance(signal_metadata, dict)
            else None
        )
        flow_snapshot = (
            signal_metadata.get("order_flow")
            if isinstance(signal_metadata, dict)
            else None
        )
        tcbbo_confirmation = (
            signal_metadata.get("tcbbo_confirmation")
            if isinstance(signal_metadata, dict)
            else None
        )
    if isinstance(signal_metadata, dict):
        enriched["signal_metadata"] = dict(signal_metadata)
        if isinstance(level_context, dict):
            enriched["level_context"] = dict(level_context)
        if isinstance(flow_snapshot, dict):
            enriched["flow_snapshot"] = dict(flow_snapshot)
            enriched["signed_aggression"] = flow_snapshot.get("signed_aggression")
        if isinstance(tcbbo_confirmation, dict):
            enriched["tcbbo_confirmation"] = dict(tcbbo_confirmation)
    response_tcbbo_payload = dump_payload_or_none(response_tcbbo_confirmation)
    if "tcbbo_confirmation" not in enriched and response_tcbbo_payload:
        enriched["tcbbo_confirmation"] = dict(response_tcbbo_payload)
    return enriched


def resolve_signal_marker_snapshot(
    signal: Any,
    *,
    default_price: Any,
) -> SignalMarkerSnapshot:
    if isinstance(signal, StrategySignalPayload):
        return SignalMarkerSnapshot(
            price=signal.price if signal.price is not None else default_price,
            signal_type=signal.signal or "BUY",
            strategy=signal.strategy or signal.strategy_name or "unknown",
            confidence=signal.confidence if signal.confidence is not None else 50,
            reasoning=signal.reasoning or "",
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
        )

    signal_payload = dump_payload(signal)
    return SignalMarkerSnapshot(
        price=signal_payload.get("price", default_price),
        signal_type=signal_payload.get("signal", "BUY"),
        strategy=signal_payload.get("strategy")
        or signal_payload.get("strategy_name")
        or "unknown",
        confidence=signal_payload.get("confidence", 50),
        reasoning=signal_payload.get("reasoning", ""),
        stop_loss=signal_payload.get("stop_loss"),
        take_profit=signal_payload.get("take_profit"),
    )


def resolve_execution_status_marker_price(
    bar: Dict[str, Any],
    *,
    safe_float: SafeFloat,
) -> float:
    marker_price = safe_float(bar.get("open"))
    if marker_price is None:
        marker_price = safe_float(bar.get("close"))
    if marker_price is None:
        return 0.0
    return float(marker_price)
