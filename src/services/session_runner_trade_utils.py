from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.services.session_runner_marker_utils import apply_intraday_levels_details
from src.services.session_runner_models import (
    StrategyBarResponse,
    StrategySignalMetadataPayload,
    StrategyPositionClosedPayload,
    StrategyPositionOpenedPayload,
    StrategySignalPayload,
    dump_payload,
    dump_payload_or_none,
)


@dataclass(frozen=True)
class EntryMarkerContext:
    reasoning: str
    confidence: Any
    metadata: Dict[str, Any]
    context_risk_payload: Optional[Dict[str, Any]]
    break_even_payload: Optional[Dict[str, Any]]
    liquidity_sweep_payload: Optional[Dict[str, Any]]
    sweep_triggered: bool


@dataclass(frozen=True)
class EntryPositionSnapshot:
    entry_price: Any
    side: str
    strategy: str
    size: Any
    stop_loss: Any
    take_profit: Any


def resolve_entry_marker_context(
    response: Any,
    position_payload: Any,
) -> EntryMarkerContext:
    if isinstance(response, StrategyBarResponse) and isinstance(
        position_payload, StrategyPositionOpenedPayload
    ):
        signal_data = (
            response.signal if isinstance(response.signal, StrategySignalPayload) else None
        )
        metadata_payload = position_payload.metadata or (
            signal_data.metadata if signal_data is not None else None
        )
        metadata = dump_payload(metadata_payload)
        resolved_context_risk_payload = dump_payload_or_none(response.context_risk)
        if (
            resolved_context_risk_payload is None
            and isinstance(metadata_payload, StrategySignalMetadataPayload)
        ):
            resolved_context_risk_payload = dump_payload_or_none(
                metadata_payload.context_risk
            )
        break_even_payload = (
            dump_payload_or_none(metadata_payload.break_even)
            if isinstance(metadata_payload, StrategySignalMetadataPayload)
            else None
        )
        liquidity_sweep_payload = (
            dump_payload_or_none(metadata_payload.liquidity_sweep)
            if isinstance(metadata_payload, StrategySignalMetadataPayload)
            else None
        )
        sweep_triggered = bool(
            metadata_payload.sweep_triggered
            if isinstance(metadata_payload, StrategySignalMetadataPayload)
            else False
        )
        return EntryMarkerContext(
            reasoning=str(
                position_payload.reasoning
                or (signal_data.reasoning if signal_data is not None else "")
                or ""
            ),
            confidence=(
                position_payload.confidence
                if position_payload.confidence is not None
                else (
                    signal_data.confidence
                    if signal_data is not None and signal_data.confidence is not None
                    else 50
                )
            ),
            metadata=dict(metadata),
            context_risk_payload=resolved_context_risk_payload,
            break_even_payload=break_even_payload,
            liquidity_sweep_payload=liquidity_sweep_payload,
            sweep_triggered=sweep_triggered,
        )

    response_payload = dump_payload(response)
    position_data = dump_payload(position_payload)
    signal_data = response_payload.get("signal")
    if not isinstance(signal_data, dict):
        signal_data = {}

    metadata = position_data.get("metadata", signal_data.get("metadata", {}))
    if not isinstance(metadata, dict):
        metadata = {}

    context_risk_payload = response_payload.get("context_risk")
    if isinstance(context_risk_payload, dict):
        resolved_context_risk_payload = dict(context_risk_payload)
    else:
        context_from_metadata = metadata.get("context_risk")
        resolved_context_risk_payload = (
            dict(context_from_metadata)
            if isinstance(context_from_metadata, dict)
            else None
        )
    break_even_payload = (
        dict(metadata.get("break_even"))
        if isinstance(metadata.get("break_even"), dict)
        else None
    )
    liquidity_sweep_payload = (
        dict(metadata.get("liquidity_sweep"))
        if isinstance(metadata.get("liquidity_sweep"), dict)
        else None
    )

    return EntryMarkerContext(
        reasoning=str(position_data.get("reasoning", signal_data.get("reasoning", ""))),
        confidence=position_data.get("confidence", signal_data.get("confidence", 50)),
        metadata=dict(metadata),
        context_risk_payload=resolved_context_risk_payload,
        break_even_payload=break_even_payload,
        liquidity_sweep_payload=liquidity_sweep_payload,
        sweep_triggered=bool(metadata.get("sweep_triggered", False)),
    )


def resolve_entry_position_snapshot(
    position_payload: Any,
    *,
    default_entry_price: Any,
) -> EntryPositionSnapshot:
    if isinstance(position_payload, StrategyPositionOpenedPayload):
        return EntryPositionSnapshot(
            entry_price=(
                position_payload.entry_price
                if position_payload.entry_price is not None
                else default_entry_price
            ),
            side=position_payload.side or "long",
            strategy=position_payload.strategy or "unknown",
            size=position_payload.size if position_payload.size is not None else 1.0,
            stop_loss=position_payload.stop_loss if position_payload.stop_loss is not None else 0,
            take_profit=(
                position_payload.take_profit
                if position_payload.take_profit is not None
                else 0
            ),
        )

    position_data = dump_payload(position_payload)
    return EntryPositionSnapshot(
        entry_price=position_data.get("entry_price", default_entry_price),
        side=position_data.get("side", "long"),
        strategy=position_data.get("strategy", "unknown"),
        size=position_data.get("size", 1.0),
        stop_loss=position_data.get("stop_loss", 0),
        take_profit=position_data.get("take_profit", 0),
    )


def apply_entry_marker_details(
    details: Dict[str, Any],
    *,
    intraday_levels_payload: Optional[Dict[str, Any]],
    entry_context: EntryMarkerContext,
    response_break_even: Any,
    risk_adjustment: Any,
) -> Dict[str, Any]:
    enriched = apply_intraday_levels_details(details, intraday_levels_payload)
    if entry_context.context_risk_payload is not None:
        enriched["context_risk"] = dict(entry_context.context_risk_payload)
    elif risk_adjustment is not None:
        enriched["context_risk"] = risk_adjustment.to_dict()

    if entry_context.break_even_payload is not None:
        enriched["break_even"] = dict(entry_context.break_even_payload)
    else:
        response_break_even_payload = dump_payload_or_none(response_break_even)
        if response_break_even_payload is not None:
            enriched["break_even"] = response_break_even_payload
    return enriched


def resolve_position_closed_gross_pnl_dollars(position_payload: Any) -> Any:
    if isinstance(position_payload, StrategyPositionClosedPayload):
        if position_payload.gross_pnl_dollars is not None:
            return position_payload.gross_pnl_dollars
        if position_payload.gross_pnl_pct is None:
            return None
        return (
            position_payload.gross_pnl_pct
            * (position_payload.entry_price or 0)
            * (position_payload.size or 1)
            / 100
        )

    position_data = dump_payload(position_payload)
    gross_pnl_dollars = position_data.get("gross_pnl_dollars")
    if gross_pnl_dollars is not None:
        return gross_pnl_dollars

    gross_pnl_pct = position_data.get("gross_pnl_pct")
    if gross_pnl_pct is None:
        return None
    return gross_pnl_pct * position_data.get("entry_price", 0) * position_data.get(
        "size", 1
    ) / 100


def build_exit_marker_details(
    details: Dict[str, Any],
    *,
    position_payload: Any,
    intraday_levels_payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if isinstance(position_payload, StrategyPositionClosedPayload):
        enriched = apply_intraday_levels_details(details, intraday_levels_payload)
        level_context = dump_payload_or_none(position_payload.level_context)
        if level_context is not None:
            enriched["level_context"] = level_context
        flow_snapshot = dump_payload_or_none(position_payload.flow_snapshot)
        if flow_snapshot is not None:
            enriched["flow_snapshot"] = flow_snapshot
        signal_metadata = dump_payload_or_none(position_payload.signal_metadata)
        if signal_metadata is not None:
            enriched["signal_metadata"] = signal_metadata
            if isinstance(position_payload.signal_metadata, StrategySignalMetadataPayload):
                signal_break_even = dump_payload_or_none(
                    position_payload.signal_metadata.break_even
                )
                if signal_break_even is not None:
                    enriched["break_even"] = signal_break_even
        position_break_even = dump_payload_or_none(position_payload.break_even)
        if position_break_even is not None:
            enriched["break_even"] = position_break_even
        entry_quality_diagnostics = dump_payload_or_none(
            position_payload.entry_quality_diagnostics
        )
        if entry_quality_diagnostics is not None:
            enriched["entry_quality_diagnostics"] = entry_quality_diagnostics
        if position_payload.flow_strategy is not None:
            enriched["flow_strategy"] = bool(position_payload.flow_strategy)
        if position_payload.book_pressure_confirmed is not None:
            enriched["book_pressure_confirmed"] = position_payload.book_pressure_confirmed
        if position_payload.book_pressure_avg is not None:
            enriched["book_pressure_avg"] = position_payload.book_pressure_avg
        if position_payload.book_pressure_trend is not None:
            enriched["book_pressure_trend"] = position_payload.book_pressure_trend
        if position_payload.signed_aggression is not None:
            enriched["signed_aggression"] = position_payload.signed_aggression
        return enriched

    position_data = dump_payload(position_payload)
    enriched = apply_intraday_levels_details(details, intraday_levels_payload)
    if isinstance(position_data.get("level_context"), dict):
        enriched["level_context"] = dict(position_data.get("level_context") or {})
    if isinstance(position_data.get("flow_snapshot"), dict):
        enriched["flow_snapshot"] = dict(position_data.get("flow_snapshot") or {})
    if isinstance(position_data.get("signal_metadata"), dict):
        signal_metadata = dict(position_data.get("signal_metadata") or {})
        enriched["signal_metadata"] = signal_metadata
        signal_break_even = signal_metadata.get("break_even")
        if isinstance(signal_break_even, dict):
            enriched["break_even"] = dict(signal_break_even)
    position_break_even = dump_payload_or_none(position_data.get("break_even"))
    if position_break_even is not None:
        enriched["break_even"] = position_break_even
    if isinstance(position_data.get("entry_quality_diagnostics"), dict):
        enriched["entry_quality_diagnostics"] = dict(
            position_data.get("entry_quality_diagnostics") or {}
        )
    if "flow_strategy" in position_data:
        enriched["flow_strategy"] = bool(position_data.get("flow_strategy"))
    if "book_pressure_confirmed" in position_data:
        enriched["book_pressure_confirmed"] = position_data.get(
            "book_pressure_confirmed"
        )
    if "book_pressure_avg" in position_data:
        enriched["book_pressure_avg"] = position_data.get("book_pressure_avg")
    if "book_pressure_trend" in position_data:
        enriched["book_pressure_trend"] = position_data.get("book_pressure_trend")
    if "signed_aggression" in position_data:
        enriched["signed_aggression"] = position_data.get("signed_aggression")
    return enriched


def resolve_closed_trade_cost_usd(position_payload: Any) -> float:
    if isinstance(position_payload, StrategyPositionClosedPayload):
        cost_usd = position_payload.cost_usd or 0.0
        costs_payload = dump_payload_or_none(position_payload.costs)
        if cost_usd == 0.0 and isinstance(costs_payload, dict):
            cost_usd = costs_payload.get("total", 0.0) or 0.0
        return float(cost_usd)

    position_data = dump_payload(position_payload)
    cost_usd = position_data.get("cost_usd", 0.0) or 0.0
    if cost_usd == 0.0 and "costs" in position_data:
        costs_payload = position_data.get("costs")
        if isinstance(costs_payload, dict):
            cost_usd = costs_payload.get("total", 0.0) or 0.0
    return float(cost_usd)


def resolve_closed_trade_regime(
    position_payload: Any,
    response: Any,
) -> str:
    if isinstance(response, StrategyBarResponse) and isinstance(
        position_payload, StrategyPositionClosedPayload
    ):
        return str(
            position_payload.regime
            or response.regime
            or (
                response.regime_update.regime
                if response.regime_update is not None
                else None
            )
            or "unknown"
        )

    position_data = dump_payload(position_payload)
    response_payload = dump_payload(response)
    regime_update = response_payload.get("regime_update")
    return str(
        position_data.get("regime")
        or response_payload.get("regime")
        or (regime_update.get("regime") if isinstance(regime_update, dict) else None)
        or "unknown"
    )


def extract_level_fade_setup_type(
    signal_metadata: Any,
    *,
    strategy: Optional[str] = None,
) -> Optional[str]:
    strategy_key = str(strategy or "").strip().lower()
    if strategy_key and strategy_key != "level_fade":
        return None
    if not isinstance(signal_metadata, dict):
        return None

    level_fade_payload = signal_metadata.get("level_fade")
    if isinstance(level_fade_payload, dict):
        setup_type = str(
            level_fade_payload.get("setup_type_guess")
            or level_fade_payload.get("setup_type")
            or ""
        ).strip().lower()
        if setup_type:
            return setup_type

    setup_type = str(
        signal_metadata.get("setup_type_guess") or signal_metadata.get("setup_type") or ""
    ).strip().lower()
    if setup_type:
        return setup_type

    if bool(signal_metadata.get("sweep_triggered", False)):
        return "sweep_reclaim"
    return None


def build_closed_trade_record_kwargs(
    position_payload: Any,
    response: Any,
    *,
    ticker: str,
    date: str,
    exit_time: str,
    default_exit_price: Any,
) -> Dict[str, Any]:
    if isinstance(position_payload, StrategyPositionClosedPayload):
        signal_metadata = dump_payload_or_none(position_payload.signal_metadata)
        position_data = dump_payload(position_payload)
        return {
            "strategy": position_payload.strategy or "unknown",
            "regime": resolve_closed_trade_regime(position_payload, response),
            "ticker": ticker,
            "date": date,
            "side": position_payload.side or "long",
            "entry_price": position_payload.entry_price or 0.0,
            "exit_price": (
                position_payload.exit_price
                if position_payload.exit_price is not None
                else default_exit_price
            ),
            "entry_time": position_payload.entry_time or "",
            "exit_time": exit_time,
            "pnl_pct": position_payload.pnl_pct or 0.0,
            "pnl_dollars": position_payload.pnl_dollars or 0.0,
            "gross_pnl_pct": position_payload.gross_pnl_pct or 0.0,
            "total_costs": resolve_closed_trade_cost_usd(position_payload),
            "exit_reason": position_payload.exit_reason or "unknown",
            "size": position_payload.size,
            "position_notional_usd": position_payload.position_notional_usd,
            "gross_pnl_dollars": position_payload.gross_pnl_dollars,
            "cost_usd": position_payload.cost_usd,
            "cost_pct": position_payload.cost_pct,
            "take_profit": position_data.get("take_profit"),
            "signal_bar_index": position_data.get("signal_bar_index"),
            "entry_bar_index": position_data.get("entry_bar_index"),
            "signal_timestamp": position_data.get("signal_timestamp"),
            "signal_price": position_data.get("signal_price"),
            "bars_held": position_payload.bars_held or 0,
            "flow_strategy": bool(position_payload.flow_strategy),
            "book_pressure_confirmed": position_payload.book_pressure_confirmed,
            "book_pressure_avg": position_payload.book_pressure_avg,
            "book_pressure_trend": position_payload.book_pressure_trend,
            "signed_aggression": position_payload.signed_aggression,
            "setup_type": (
                position_data.get("setup_type")
                or extract_level_fade_setup_type(
                    signal_metadata,
                    strategy=position_payload.strategy,
                )
            ),
            "setup_reason": position_data.get("setup_reason"),
            "level_context": dump_payload_or_none(position_payload.level_context),
            "flow_snapshot": dump_payload_or_none(position_payload.flow_snapshot),
            "signal_metadata": signal_metadata,
            "break_even": dump_payload_or_none(position_payload.break_even),
            "entry_quality_diagnostics": dump_payload_or_none(
                position_payload.entry_quality_diagnostics
            ),
            "trade_audit": (
                dict(position_data.get("trade_audit", {}))
                if isinstance(position_data.get("trade_audit"), dict)
                else None
            ),
        }

    position_data = dump_payload(position_payload)
    signal_metadata = (
        dict(position_data.get("signal_metadata") or {})
        if isinstance(position_data.get("signal_metadata"), dict)
        else None
    )
    return {
        "strategy": position_data.get("strategy", "unknown"),
        "regime": resolve_closed_trade_regime(position_payload, response),
        "ticker": ticker,
        "date": date,
        "side": position_data.get("side", "long"),
        "entry_price": position_data.get("entry_price", 0.0),
        "exit_price": position_data.get("exit_price", default_exit_price),
        "entry_time": position_data.get("entry_time", ""),
        "exit_time": exit_time,
        "pnl_pct": position_data.get("pnl_pct", 0.0),
        "pnl_dollars": position_data.get("pnl_dollars", 0.0),
        "gross_pnl_pct": position_data.get("gross_pnl_pct", 0.0),
        "total_costs": resolve_closed_trade_cost_usd(position_payload),
        "exit_reason": position_data.get("exit_reason", "unknown"),
        "size": position_data.get("size"),
        "position_notional_usd": position_data.get("position_notional_usd"),
        "gross_pnl_dollars": position_data.get("gross_pnl_dollars"),
        "cost_usd": position_data.get("cost_usd"),
        "cost_pct": position_data.get("cost_pct"),
        "take_profit": position_data.get("take_profit"),
        "signal_bar_index": position_data.get("signal_bar_index"),
        "entry_bar_index": position_data.get("entry_bar_index"),
        "signal_timestamp": position_data.get("signal_timestamp"),
        "signal_price": position_data.get("signal_price"),
        "bars_held": position_data.get("bars_held", 0),
        "flow_strategy": position_data.get("flow_strategy", False),
        "book_pressure_confirmed": position_data.get("book_pressure_confirmed"),
        "book_pressure_avg": position_data.get("book_pressure_avg"),
        "book_pressure_trend": position_data.get("book_pressure_trend"),
        "signed_aggression": position_data.get("signed_aggression"),
        "setup_type": extract_level_fade_setup_type(
            signal_metadata,
            strategy=position_data.get("strategy"),
        ) if not position_data.get("setup_type") else position_data.get("setup_type"),
        "setup_reason": position_data.get("setup_reason"),
        "level_context": (
            dict(position_data.get("level_context", {}))
            if isinstance(position_data.get("level_context"), dict)
            else None
        ),
        "flow_snapshot": (
            dict(position_data.get("flow_snapshot", {}))
            if isinstance(position_data.get("flow_snapshot"), dict)
            else None
        ),
        "signal_metadata": signal_metadata,
        "break_even": (
            dict(position_data.get("break_even", {}))
            if isinstance(position_data.get("break_even"), dict)
            else None
        ),
        "entry_quality_diagnostics": (
            dict(position_data.get("entry_quality_diagnostics", {}))
            if isinstance(position_data.get("entry_quality_diagnostics"), dict)
            else None
        ),
        "trade_audit": (
            dict(position_data.get("trade_audit", {}))
            if isinstance(position_data.get("trade_audit"), dict)
            else None
        ),
    }


def build_exit_marker_kwargs(
    position_payload: Any,
    *,
    default_exit_price: Any,
) -> Dict[str, Any]:
    if isinstance(position_payload, StrategyPositionClosedPayload):
        return {
            "price": (
                position_payload.exit_price
                if position_payload.exit_price is not None
                else default_exit_price
            ),
            "side": position_payload.side or "long",
            "reason": position_payload.exit_reason or "unknown",
            "pnl_pct": position_payload.pnl_pct or 0,
            "pnl_dollars": position_payload.pnl_dollars or 0,
            "entry_price": position_payload.entry_price,
            "entry_time": position_payload.entry_time,
            "bars_held": position_payload.bars_held,
            "size": position_payload.size,
            "costs": dump_payload_or_none(position_payload.costs),
            "gross_pnl_pct": position_payload.gross_pnl_pct,
            "gross_pnl_dollars": resolve_position_closed_gross_pnl_dollars(
                position_payload
            ),
            "cost_usd": resolve_closed_trade_cost_usd(position_payload),
            "cost_pct": position_payload.cost_pct,
            "pnl_usd": position_payload.pnl_usd,
            "position_notional_usd": position_payload.position_notional_usd,
            "schema_version": (
                position_payload.schema_version
                if position_payload.schema_version is not None
                else 1
            ),
        }

    position_data = dump_payload(position_payload)
    return {
        "price": position_data.get("exit_price", default_exit_price),
        "side": position_data.get("side", "long"),
        "reason": position_data.get("exit_reason", "unknown"),
        "pnl_pct": position_data.get("pnl_pct", 0),
        "pnl_dollars": position_data.get("pnl_dollars", 0),
        "entry_price": position_data.get("entry_price"),
        "entry_time": position_data.get("entry_time"),
        "bars_held": position_data.get("bars_held"),
        "size": position_data.get("size"),
        "costs": position_data.get("costs"),
        "gross_pnl_pct": position_data.get("gross_pnl_pct"),
        "gross_pnl_dollars": resolve_position_closed_gross_pnl_dollars(position_payload),
        "cost_usd": resolve_closed_trade_cost_usd(position_payload),
        "cost_pct": position_data.get("cost_pct"),
        "pnl_usd": position_data.get("pnl_usd"),
        "position_notional_usd": position_data.get("position_notional_usd"),
        "schema_version": position_data.get("schema_version", 1),
    }
