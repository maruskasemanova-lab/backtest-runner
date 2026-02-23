from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import HTTPException


@dataclass(frozen=True)
class BootstrapPhaseInputs:
    request: Any
    ticker: str
    comparable_mode: bool


@dataclass(frozen=True)
class BootstrapPhaseDeps:
    logger: Any
    reset_remote_orchestrator_state_scoped: Callable[..., Awaitable[Any]]
    load_remote_checkpoint: Callable[..., Awaitable[Any]]
    reset_remote_orchestrator_state: Callable[..., Awaitable[Any]]
    clear_remote_strategy_sessions: Callable[..., Awaitable[Any]]
    apply_strategy_overrides: Callable[..., Awaitable[Any]]
    apply_aos_optimizations: Callable[..., Awaitable[Dict[str, Any]]]
    normalize_momentum_diversification_payload: Callable[[Any], Any]
    apply_global_trailing: Callable[..., Awaitable[Any]]
    resolve_execution_config: Callable[..., Dict[str, Any]]
    normalize_reset_scope: Callable[[Any], str]


@dataclass(frozen=True)
class BootstrapPhaseResult:
    orchestrator_reset: Any
    checkpoint_loaded: Any
    effective_reset_scope: str
    strategy_overrides_applied: bool
    apply_aos_optimizations_on_start: bool
    aos_applied: Dict[str, Any]
    adaptive_profile_runtime: Dict[str, Any]
    effective_momentum_diversification: Optional[Dict[str, Any]]
    momentum_diversification_source: str
    momentum_diversification_json: Optional[str]
    execution_cfg: Dict[str, Any]


def _positive_or_zero(value: Any) -> float:
    try:
        parsed = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return parsed if parsed > 0 else 0.0


async def _run_orchestrator_reset(
    *,
    request: Any,
    comparable_mode: bool,
    deps: BootstrapPhaseDeps,
) -> tuple[Any, Any, str]:
    checkpoint_loaded = None
    use_checkpoint = bool(request.checkpoint_path) and not comparable_mode
    requested_reset_scope = deps.normalize_reset_scope(
        getattr(request, "orchestrator_reset_scope", None)
    )

    if use_checkpoint:
        effective_reset_scope = "session"
        orchestrator_reset = await deps.reset_remote_orchestrator_state_scoped(
            request.strategy_api_url,
            scope="session",
        )
        checkpoint_loaded = await deps.load_remote_checkpoint(
            request.strategy_api_url,
            request.checkpoint_path,
        )
        return orchestrator_reset, checkpoint_loaded, effective_reset_scope

    effective_reset_scope = "all" if comparable_mode else requested_reset_scope
    if effective_reset_scope == "all":
        orchestrator_reset = await deps.reset_remote_orchestrator_state(
            request.strategy_api_url
        )
    else:
        orchestrator_reset = await deps.reset_remote_orchestrator_state_scoped(
            request.strategy_api_url,
            scope=effective_reset_scope,
        )
    if comparable_mode and request.checkpoint_path:
        deps.logger.info(
            "Comparable mode ignores checkpoint_path and always starts from a cold state."
        )
    return orchestrator_reset, checkpoint_loaded, effective_reset_scope


def _extract_adaptive_profile_runtime(aos_applied: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(aos_applied.get("adaptive_profile"), dict):
        raw_runtime = aos_applied["adaptive_profile"].get("runtime_overrides")
        if isinstance(raw_runtime, dict):
            return dict(raw_runtime)
    return {}


def _resolve_momentum_diversification(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
    normalize_payload: Callable[[Any], Any],
) -> tuple[Optional[Dict[str, Any]], str, Optional[str]]:
    request_momentum_diversification = normalize_payload(
        request.momentum_diversification_override
    )
    profile_momentum_diversification = normalize_payload(
        adaptive_profile_runtime.get("momentum_diversification")
    )
    aos_adaptive_cfg = (
        aos_applied.get("adaptive", {})
        if isinstance(aos_applied.get("adaptive"), dict)
        else {}
    )
    aos_momentum_diversification = normalize_payload(
        aos_adaptive_cfg.get("momentum_diversification")
    )

    if request_momentum_diversification:
        effective = request_momentum_diversification
        source = "request"
    elif profile_momentum_diversification:
        effective = profile_momentum_diversification
        source = "adaptive_profile"
    elif aos_momentum_diversification:
        effective = aos_momentum_diversification
        source = "aos_config"
    else:
        effective = None
        source = "none"

    payload_json = json.dumps(effective, separators=(",", ":")) if effective else None
    return effective, source, payload_json


async def _apply_global_trailing_from_execution_cfg(
    *,
    request: Any,
    execution_cfg: Dict[str, Any],
    apply_global_trailing: Callable[..., Awaitable[Any]],
) -> None:
    await apply_global_trailing(
        request.strategy_api_url,
        _positive_or_zero(execution_cfg.get("effective_trailing_stop_pct")) or None,
        global_exit_rr_ratio=(
            _positive_or_zero(execution_cfg.get("effective_global_exit_rr_ratio"))
            or None
        ),
        global_risk_atr_stop_multiplier=(
            _positive_or_zero(
                execution_cfg.get("effective_global_risk_atr_stop_multiplier")
            )
            or None
        ),
        global_risk_volume_stop_pct=(
            _positive_or_zero(
                execution_cfg.get("effective_global_risk_volume_stop_pct")
            )
            or None
        ),
        global_risk_min_stop_loss_pct=(
            _positive_or_zero(
                execution_cfg.get("effective_global_risk_min_stop_loss_pct")
            )
            or None
        ),
    )


async def run_start_bootstrap_phase(
    *,
    inputs: BootstrapPhaseInputs,
    deps: BootstrapPhaseDeps,
    record_phase_ms: Callable[[str, float], None],
) -> BootstrapPhaseResult:
    request = inputs.request
    comparable_mode = bool(inputs.comparable_mode)

    phase_started = perf_counter()
    orchestrator_reset, checkpoint_loaded, effective_reset_scope = (
        await _run_orchestrator_reset(
            request=request,
            comparable_mode=comparable_mode,
            deps=deps,
        )
    )
    record_phase_ms("reset_orchestrator", phase_started)

    phase_started = perf_counter()
    await deps.clear_remote_strategy_sessions(
        request.strategy_api_url,
        request.run_id,
        inputs.ticker,
    )
    record_phase_ms("clear_remote_sessions", phase_started)

    strategy_overrides_applied = bool(request.apply_ticker_overrides_on_start)
    phase_started = perf_counter()
    if strategy_overrides_applied:
        await deps.apply_strategy_overrides(request.strategy_api_url, inputs.ticker)
    record_phase_ms("apply_strategy_overrides", phase_started)

    apply_aos_optimizations_on_start = bool(
        getattr(request, "apply_aos_optimizations_on_start", True)
    )
    phase_started = perf_counter()
    aos_applied = await deps.apply_aos_optimizations(
        request.strategy_api_url,
        inputs.ticker,
        remote_sync=apply_aos_optimizations_on_start,
        aos_config_path=request.aos_config_path,
    )
    record_phase_ms("apply_aos_optimizations", phase_started)

    adaptive_profile_runtime = _extract_adaptive_profile_runtime(aos_applied)
    (
        effective_momentum_diversification,
        momentum_diversification_source,
        momentum_diversification_json,
    ) = _resolve_momentum_diversification(
        request=request,
        aos_applied=aos_applied,
        adaptive_profile_runtime=adaptive_profile_runtime,
        normalize_payload=deps.normalize_momentum_diversification_payload,
    )

    phase_started = perf_counter()
    try:
        execution_cfg = deps.resolve_execution_config(
            request=request,
            aos_applied=aos_applied,
            adaptive_profile_runtime=adaptive_profile_runtime,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    record_phase_ms("resolve_execution_config", phase_started)
    if bool(execution_cfg.get("liquidity_sweep_l2_auto_enabled", False)):
        deps.logger.info(
            "Liquidity sweep guard auto-enabled L2 confirm for run_id=%s ticker=%s source=%s",
            request.run_id,
            inputs.ticker,
            execution_cfg.get(
                "liquidity_sweep_l2_auto_source", "liquidity_sweep_guard"
            ),
        )

    phase_started = perf_counter()
    await _apply_global_trailing_from_execution_cfg(
        request=request,
        execution_cfg=execution_cfg,
        apply_global_trailing=deps.apply_global_trailing,
    )
    record_phase_ms("apply_global_trailing", phase_started)

    return BootstrapPhaseResult(
        orchestrator_reset=orchestrator_reset,
        checkpoint_loaded=checkpoint_loaded,
        effective_reset_scope=effective_reset_scope,
        strategy_overrides_applied=strategy_overrides_applied,
        apply_aos_optimizations_on_start=apply_aos_optimizations_on_start,
        aos_applied=dict(aos_applied) if isinstance(aos_applied, dict) else {},
        adaptive_profile_runtime=adaptive_profile_runtime,
        effective_momentum_diversification=effective_momentum_diversification,
        momentum_diversification_source=momentum_diversification_source,
        momentum_diversification_json=momentum_diversification_json,
        execution_cfg=dict(execution_cfg),
    )
