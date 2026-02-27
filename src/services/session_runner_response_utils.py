from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.services.session_runner_models import (
    StrategyBarResponse,
    StrategySignalMetadataPayload,
    StrategyPositionOpenedPayload,
    StrategySignalPayload,
    dump_payload,
    dump_payload_or_none,
)


SafeFloat = Callable[[Any], Optional[float]]


class PendingExecutionStatusMarker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    signal_type: str
    strategy: str
    confidence: float
    details: Dict[str, Any] = Field(default_factory=dict)


def extract_candidate_diagnostics(
    api_response: Any,
) -> Optional[Dict[str, Any]]:
    if isinstance(api_response, StrategyBarResponse):
        position = api_response.position_opened
        if (
            position is not None
            and isinstance(position.metadata, StrategySignalMetadataPayload)
            and position.metadata.candidate_diagnostics is not None
        ):
            return dump_payload_or_none(position.metadata.candidate_diagnostics)
        for signal in api_response.signals:
            if (
                isinstance(signal.metadata, StrategySignalMetadataPayload)
                and signal.metadata.candidate_diagnostics is not None
            ):
                return dump_payload_or_none(signal.metadata.candidate_diagnostics)
        return None

    response_payload = dump_payload(api_response)
    if not response_payload:
        return None
    position = response_payload.get("position_opened")
    if isinstance(position, dict):
        metadata = position.get("metadata")
        if isinstance(metadata, dict) and isinstance(
            metadata.get("candidate_diagnostics"), dict
        ):
            return dict(metadata.get("candidate_diagnostics") or {})
    for signal in response_payload.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        signal_metadata = signal.get("metadata")
        if isinstance(signal_metadata, dict) and isinstance(
            signal_metadata.get("candidate_diagnostics"), dict
        ):
            return dict(signal_metadata.get("candidate_diagnostics") or {})
    return None


def extract_strategy_label(response: Any) -> Optional[str]:
    if isinstance(response, StrategyBarResponse):
        return response.strategy or response.selected_strategy or (
            response.strategies[0] if response.strategies else None
        )

    response_payload = dump_payload(response)
    return (
        response_payload.get("strategy")
        or response_payload.get("selected_strategy")
        or (response_payload.get("strategies") or [None])[0]
    )


def generate_regime_explanation(response: Any) -> str:
    if isinstance(response, StrategyBarResponse):
        regime = response.regime or "UNKNOWN"
        micro_regime = response.micro_regime
        indicators = dump_payload(response.indicators)
    else:
        response_payload = dump_payload(response)
        regime = response_payload.get("regime", "UNKNOWN")
        micro_regime = response_payload.get("micro_regime")
        indicators = response_payload.get("indicators", {})

    def _as_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    trend_eff = _as_float(indicators.get("trend_efficiency"))
    volatility = _as_float(indicators.get("volatility"))
    adx = _as_float(indicators.get("adx"))

    if regime == "TRENDING":
        if trend_eff is None:
            base = "Market showing directional movement (trend context unavailable)"
        elif trend_eff >= 0.45:
            base = "Market showing directional movement with elevated trend efficiency"
        elif trend_eff < 0.15:
            base = "Market tagged TRENDING, but measured trend efficiency is low (transition/noise risk)"
        else:
            base = "Market showing directional bias with moderate trend efficiency"
    elif regime == "CHOPPY":
        base = "Market showing sideways/noisy movement with low directional efficiency"
    elif regime == "MIXED":
        base = "Market showing mixed directional and mean-reverting behavior"
    else:
        base = f"Detected {regime} regime"

    if micro_regime and micro_regime != regime:
        base += f" (micro: {micro_regime})"

    match (regime, micro_regime):
        case ("TRENDING", "CHOPPY" | "MIXED" | "TRANSITION"):
            base += " [macro/micro divergence]"
        case ("CHOPPY", "TRENDING_UP" | "TRENDING_DOWN" | "BREAKOUT"):
            base += " [macro/micro divergence]"
        case (_, "TRANSITION"):
            base += " [transition/noisy trend]"

    if indicators:
        details = []
        if trend_eff is not None:
            details.append(f"Trend Efficiency: {trend_eff:.2f}")
        if volatility is not None:
            details.append(f"Volatility: {volatility:.2f}%")
        if adx is not None:
            details.append(f"ADX: {adx:.1f}")
        else:
            details.append("ADX: N/A")
        atr = _as_float(indicators.get("atr"))
        if atr is not None:
            details.append(f"ATR: {atr:.2f}")
        if details:
            base += f" ({', '.join(details)})"

    return base


def build_pending_execution_status_marker(
    response: Any,
    *,
    safe_float: SafeFloat,
) -> Optional[PendingExecutionStatusMarker]:
    if isinstance(response, StrategyBarResponse):
        action = str(response.action or "").strip()
        reason = str(response.reason or "").strip()
        signal_payload = response.signal
        opened_payload = response.position_opened
        micro_confirmation = response.micro_confirmation
        intrabar_confirmation = response.intrabar_confirmation
        context_risk = response.context_risk
        stale_pending_signal_dropped = bool(response.stale_pending_signal_dropped)
        stale_age = response.stale_pending_signal_age_bars
        stale_ttl = response.pending_signal_ttl_bars
    else:
        response_payload = dump_payload(response)
        if not response_payload:
            return None
        action = str(response_payload.get("action") or "").strip()
        reason = str(response_payload.get("reason") or "").strip()
        signal_payload = response_payload.get("signal")
        opened_payload = response_payload.get("position_opened")
        micro_confirmation = response_payload.get("micro_confirmation")
        intrabar_confirmation = response_payload.get("intrabar_confirmation")
        context_risk = response_payload.get("context_risk")
        stale_pending_signal_dropped = bool(
            response_payload.get("stale_pending_signal_dropped")
        )
        stale_age = response_payload.get("stale_pending_signal_age_bars")
        stale_ttl = response_payload.get("pending_signal_ttl_bars")

    details: Dict[str, Any] = {}

    template: Optional[Dict[str, str]]
    match action:
        case "pending_micro_confirmation":
            template = {
                "status": "pending",
                "signal_type": "PENDING",
                "title": "Signal Pending Confirmation",
                "default_reason": "Awaiting consecutive close confirmation.",
            }
        case "pending_intrabar_confirmation":
            template = {
                "status": "pending",
                "signal_type": "PENDING",
                "title": "Signal Pending Intrabar Confirmation",
                "default_reason": "Awaiting intrabar flow confirmation.",
            }
        case "micro_confirmation_failed":
            template = {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Micro Confirmation)",
                "default_reason": "Consecutive close confirmation failed.",
            }
        case "intrabar_confirmation_failed":
            template = {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Intrabar Confirmation)",
                "default_reason": "Intrabar flow confirmation failed.",
            }
        case "consecutive_loss_cooldown":
            template = {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Cooldown)",
                "default_reason": "Consecutive-loss cooldown blocked entry.",
            }
        case "regime_warmup":
            template = {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Regime Warmup)",
                "default_reason": "Regime warmup incomplete; pending signal discarded.",
            }
        case "context_risk_skip":
            template = {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Context Risk)",
                "default_reason": "Context-aware risk guard skipped the pending signal.",
            }
        case "insufficient_fill":
            template = {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Insufficient Fill)",
                "default_reason": "Position size after risk/fill constraints is zero.",
            }
        case _:
            template = None

    if template is None and stale_pending_signal_dropped:
        action = action or "stale_pending_signal_dropped"
        template = {
            "status": "no_fill",
            "signal_type": "NO_FILL",
            "title": "Signal Dropped (Stale)",
            "default_reason": "Pending signal expired before execution.",
        }
        if stale_age is not None:
            details["stale_pending_signal_age_bars"] = stale_age
        if stale_ttl is not None:
            details["pending_signal_ttl_bars"] = stale_ttl
        if not reason and stale_age is not None and stale_ttl is not None:
            reason = (
                f"Pending signal expired after {stale_age} bars (ttl {stale_ttl} bars)."
            )

    if template is None:
        return None

    if not reason:
        reason = template["default_reason"]

    strategy = "pending_signal"
    confidence = 0.0

    if isinstance(signal_payload, StrategySignalPayload):
        strategy = (
            str(signal_payload.strategy or signal_payload.strategy_name or strategy).strip()
            or strategy
        )
        parsed_confidence = safe_float(signal_payload.confidence)
        if parsed_confidence is not None:
            confidence = parsed_confidence
    elif isinstance(signal_payload, dict):
        strategy = (
            str(
                signal_payload.get("strategy")
                or signal_payload.get("strategy_name")
                or strategy
            ).strip()
            or strategy
        )
        parsed_confidence = safe_float(signal_payload.get("confidence"))
        if parsed_confidence is not None:
            confidence = parsed_confidence

    if isinstance(opened_payload, StrategyPositionOpenedPayload):
        strategy = str(opened_payload.strategy or strategy).strip() or strategy
        parsed_confidence = safe_float(opened_payload.confidence)
        if parsed_confidence is not None:
            confidence = parsed_confidence
    elif isinstance(opened_payload, dict):
        strategy = str(opened_payload.get("strategy") or strategy).strip() or strategy
        parsed_confidence = safe_float(opened_payload.get("confidence"))
        if parsed_confidence is not None:
            confidence = parsed_confidence

    micro_confirmation_payload = dump_payload_or_none(micro_confirmation)
    if micro_confirmation_payload is not None:
        details["micro_confirmation"] = micro_confirmation_payload

    intrabar_confirmation_payload = dump_payload_or_none(intrabar_confirmation)
    if intrabar_confirmation_payload is not None:
        details["intrabar_confirmation"] = intrabar_confirmation_payload

    context_risk_payload = dump_payload_or_none(context_risk)
    if context_risk_payload is not None:
        details["context_risk"] = context_risk_payload

    details["execution_status"] = template["status"]
    details["execution_action"] = action or "pending_signal_update"
    details["reason"] = reason

    return PendingExecutionStatusMarker(
        title=template["title"],
        description=reason,
        signal_type=template["signal_type"],
        strategy=strategy,
        confidence=confidence,
        details=details,
    )
