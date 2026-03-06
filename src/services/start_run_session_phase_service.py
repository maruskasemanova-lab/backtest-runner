from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Awaitable, Callable, Dict, Optional

from src.services.trade_eval_mode_service import resolve_trade_eval_settings


@dataclass(frozen=True)
class SessionPhaseInputs:
    request: Any
    run_key: str
    ticker: str
    range_start: str
    bars: list[Any]
    comparable_mode: bool
    execution_cfg: Dict[str, Any]
    l2_stats: Dict[str, Any]
    requested_l2_confirm: bool
    use_l2: bool
    effective_cold_start_each_day: bool
    momentum_diversification_json: Optional[str]


@dataclass(frozen=True)
class SessionPhaseDeps:
    logger: Any
    configure_session: Callable[..., Awaitable[Any]]
    force_enable_all_remote_strategies: Callable[[], Awaitable[Dict[str, Any]]]
    build_heatmap_memory_catalog: Callable[..., Optional[Dict[str, Any]]]


@dataclass(frozen=True)
class SessionPhaseResult:
    effective_strategy_selection_mode: str
    effective_max_active_strategies: int
    all_enabled_remote_sync: Optional[Dict[str, Any]]
    effective_l2_confirm: bool
    effective_trade_eval_mode: str
    effective_intrabar_execution_recalc_1s: bool
    effective_intrabar_eval_step_seconds: int
    session_config_snapshot: Dict[str, Any]


async def run_start_session_phase(
    *,
    inputs: SessionPhaseInputs,
    deps: SessionPhaseDeps,
    record_phase_ms: Callable[[str, float], None],
) -> SessionPhaseResult:
    effective_strategy_selection_mode = str(
        inputs.execution_cfg["effective_strategy_selection_mode"]
    )
    effective_max_active_strategies = int(
        inputs.execution_cfg["effective_max_active_strategies"]
    )

    all_enabled_remote_sync: Optional[Dict[str, Any]] = None
    if effective_strategy_selection_mode == "all_enabled":
        phase_started = perf_counter()
        try:
            all_enabled_remote_sync = await deps.force_enable_all_remote_strategies()
        except Exception as exc:
            deps.logger.warning(
                "Failed to force-enable all strategies for %s: %s",
                inputs.run_key,
                exc,
            )
            all_enabled_remote_sync = {
                "attempted": True,
                "applied": False,
                "error": str(exc),
            }
        record_phase_ms("force_enable_all_strategies", phase_started)

    effective_l2_confirm = bool(
        inputs.requested_l2_confirm and inputs.l2_stats.get("has_l2")
    )
    fallback_intrabar_execution = (
        bool(inputs.request.intrabar_execution_recalc_1s)
        if inputs.request.intrabar_execution_recalc_1s is not None
        else bool(inputs.use_l2 and inputs.l2_stats.get("has_l2"))
    )
    (
        effective_trade_eval_mode,
        effective_intrabar_execution_recalc_1s,
        effective_intrabar_eval_step_seconds,
    ) = resolve_trade_eval_settings(
        requested_mode=getattr(inputs.request, "trade_eval_mode", None),
        fallback_intrabar_enabled=fallback_intrabar_execution,
        fallback_intrabar_eval_step_seconds=1,
    )

    session_config_snapshot = dict(inputs.execution_cfg.get("trading_config", {}))
    session_config_snapshot["l2_confirm_enabled"] = effective_l2_confirm
    session_config_snapshot["cold_start_each_day"] = (
        inputs.effective_cold_start_each_day
    )
    session_config_snapshot["strategy_selection_mode"] = (
        effective_strategy_selection_mode
    )
    session_config_snapshot["max_active_strategies"] = effective_max_active_strategies
    session_config_snapshot["momentum_diversification_json"] = (
        inputs.momentum_diversification_json
    )
    if inputs.request.regime_filter is not None:
        session_config_snapshot["regime_filter"] = [
            str(r).strip().upper()
            for r in inputs.request.regime_filter
            if str(r).strip()
        ]
    heatmap_memory_catalog = deps.build_heatmap_memory_catalog(
        ticker=inputs.ticker,
        bars=inputs.bars,
    )
    if isinstance(heatmap_memory_catalog, dict):
        summary = heatmap_memory_catalog.get("summary")
        if isinstance(summary, dict):
            session_config_snapshot["heatmap_memory_summary"] = dict(summary)

    phase_started = perf_counter()
    await deps.configure_session(
        inputs.request.strategy_api_url,
        inputs.request.run_id,
        inputs.ticker,
        inputs.range_start,
        heatmap_memory_catalog=heatmap_memory_catalog,
        **session_config_snapshot,
    )
    record_phase_ms("configure_session", phase_started)

    return SessionPhaseResult(
        effective_strategy_selection_mode=effective_strategy_selection_mode,
        effective_max_active_strategies=effective_max_active_strategies,
        all_enabled_remote_sync=all_enabled_remote_sync,
        effective_l2_confirm=effective_l2_confirm,
        effective_trade_eval_mode=effective_trade_eval_mode,
        effective_intrabar_execution_recalc_1s=effective_intrabar_execution_recalc_1s,
        effective_intrabar_eval_step_seconds=effective_intrabar_eval_step_seconds,
        session_config_snapshot=session_config_snapshot,
    )
