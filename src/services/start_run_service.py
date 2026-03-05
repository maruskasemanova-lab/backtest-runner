from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import date, datetime
from time import perf_counter
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from fastapi import HTTPException

from src.models.run_requests import PrewarmRunRequest, StartRunRequest
from src.runtime_mode import (
    stateful_run_api_supported,
    stateful_run_api_unsupported_detail,
)
from src.services.start_run_data_service import (
    enrich_bars_with_l2,
    get_prewarm_result,
    get_start_run_data_cache_stats,
    load_reference_bars_map,
    load_run_bars,
    set_prewarm_result,
)
from src.services.start_run_execution_config_service import resolve_execution_config
from src.services.start_run_execution_payload_service import (
    ExecutionPayloadInputs,
    build_execution_payload,
)
from src.services.start_run_planning_utils import (
    add_days_iso as planning_add_days_iso,
    build_progressive_chunks as planning_build_progressive_chunks,
    format_iso_day as planning_format_iso_day,
    inclusive_day_span as planning_inclusive_day_span,
    parse_iso_day as planning_parse_iso_day,
    prewarm_l2_guard_reason as planning_prewarm_l2_guard_reason,
    resolve_progressive_plan as planning_resolve_progressive_plan,
    run_l2_guard_reason as planning_run_l2_guard_reason,
)
from src.services.start_run_report_utils import (
    build_data_availability_warnings as report_build_data_availability_warnings,
    build_report_metadata as report_build_report_metadata,
    build_run_request_config_snapshot as report_build_run_request_config_snapshot,
    extract_effective_profile_metadata as report_extract_effective_profile_metadata,
    first_profile_ref_token as report_first_profile_ref_token,
    normalize_profile_ref_token as report_normalize_profile_ref_token,
    summarize_days_preview as report_summarize_days_preview,
)
from src.services.start_run_time_filter_utils import (
    canonical_trading_hours as _canonical_trading_hours,
)
from src.services.start_run_prewarm_utils import (
    PrewarmInflightRegistry,
    PrewarmRequestState,
    raise_for_guard_reason as prewarm_raise_for_guard_reason,
    resolve_prewarm_request_state as prewarm_resolve_request_state,
)
from src.services.start_run_bootstrap_phase_service import (
    BootstrapPhaseDeps,
    BootstrapPhaseInputs,
    run_start_bootstrap_phase,
)
from src.services.start_run_load_phase_service import (
    LoadPhaseDeps,
    LoadPhaseInputs,
    run_start_load_phase,
)
from src.services.start_run_session_phase_service import (
    SessionPhaseDeps,
    SessionPhaseInputs,
    run_start_session_phase,
)
from src.services.run_config_snapshot_service import build_resolved_config_snapshot
from src.services.start_run_runner_setup_service import (
    RunnerSetupDeps,
    RunnerSetupInputs,
    setup_runner_with_progressive_loading,
)
from src.services.start_run_time_window_service import (
    filter_reference_map_for_requested_time_window,
)


def _parse_non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return max(0, int(default))
    try:
        return max(0, int(str(raw).strip()))
    except (TypeError, ValueError):
        return max(0, int(default))


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(default)


# Guardrail: ticker-scope prewarm plus full-range L2 is memory-heavy and can
# overwhelm local machines. Limit it by default, but allow explicit override.
PREWARM_TICKER_SCOPE_L2_MAX_DAYS = _parse_non_negative_int_env(
    "BACKTEST_PREWARM_TICKER_SCOPE_L2_MAX_DAYS",
    10,
)
PREWARM_TICKER_SCOPE_L2_FORCE = _parse_bool_env(
    "BACKTEST_PREWARM_TICKER_SCOPE_L2_FORCE",
    False,
)
RUN_L2_MAX_DAYS = _parse_non_negative_int_env("BACKTEST_RUN_L2_MAX_DAYS", 10)
RUN_L2_FORCE = _parse_bool_env("BACKTEST_RUN_L2_FORCE", False)
PROGRESSIVE_LOAD_ENABLED = _parse_bool_env("BACKTEST_PROGRESSIVE_LOAD_ENABLED", True)
PROGRESSIVE_LOAD_ALLOW_COMPARABLE_MODE = _parse_bool_env(
    "BACKTEST_PROGRESSIVE_LOAD_ALLOW_COMPARABLE_MODE",
    True,
)
PROGRESSIVE_LOAD_MIN_DAYS = _parse_non_negative_int_env(
    "BACKTEST_PROGRESSIVE_LOAD_MIN_DAYS",
    10,
)
PROGRESSIVE_LOAD_INITIAL_DAYS = _parse_non_negative_int_env(
    "BACKTEST_PROGRESSIVE_LOAD_INITIAL_DAYS",
    4,
)
PROGRESSIVE_LOAD_CHUNK_DAYS = _parse_non_negative_int_env(
    "BACKTEST_PROGRESSIVE_LOAD_CHUNK_DAYS",
    4,
)
PROGRESSIVE_LOAD_COMPARABLE_INITIAL_DAYS = _parse_non_negative_int_env(
    "BACKTEST_PROGRESSIVE_LOAD_COMPARABLE_INITIAL_DAYS",
    1,
)
PROGRESSIVE_LOAD_COMPARABLE_CHUNK_DAYS = _parse_non_negative_int_env(
    "BACKTEST_PROGRESSIVE_LOAD_COMPARABLE_CHUNK_DAYS",
    1,
)
_PREWARM_INFLIGHT_REGISTRY = PrewarmInflightRegistry()


def _strategy_reset_success(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("success"))
    return bool(value)


def _strategy_reset_detail(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {"success": bool(value), "legacy_bool_result": bool(value)}


def _to_json_compatible(value: Any) -> Any:
    """Recursively normalize payload values for FastAPI JSON encoding."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible(item) for item in value]

    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return _to_json_compatible(item_method())
        except Exception:
            pass
    tolist_method = getattr(value, "tolist", None)
    if callable(tolist_method):
        try:
            return _to_json_compatible(tolist_method())
        except Exception:
            pass

    import numpy as np
    import pandas as pd
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()

    return str(value)


@dataclass
class StartRunDeps:
    active_runners: Dict[str, Any]
    logger: Any
    data_loader: Any
    databento_svc: Any
    l2_manager: Any
    get_discovery: Callable[[], Any]
    reset_remote_orchestrator_state_scoped: Callable[..., Awaitable[Any]]
    load_remote_checkpoint: Callable[..., Awaitable[Any]]
    reset_remote_orchestrator_state: Callable[..., Awaitable[Any]]
    clear_remote_strategy_sessions: Callable[..., Awaitable[Any]]
    apply_strategy_overrides: Callable[..., Awaitable[Any]]
    apply_aos_optimizations: Callable[..., Awaitable[Dict[str, Any]]]
    apply_strategy_param_map: Callable[
        [str, Dict[str, Dict[str, Any]]], Awaitable[Dict[str, Any]]
    ]
    fetch_remote_strategies: Callable[[str], Awaitable[Dict[str, Any]]]
    normalize_momentum_diversification_payload: Callable[[Any], Any]
    apply_global_trailing: Callable[..., Awaitable[Any]]
    to_utc_datetime: Callable[[Any], Any]
    build_l2_feature_map: Callable[..., Any]
    normalize_l2_feature_map_for_market_day_sessions: Callable[..., Dict[str, Any]]
    attach_l2_features: Callable[..., Any]
    load_aos_config: Callable[..., Dict[str, Any]]
    get_ticker_positioning_config: Callable[[str], Dict[str, Any]]
    positioning_config_keys: Iterable[str]
    configure_session: Callable[..., Awaitable[Any]]
    broadcast: Callable[[Dict[str, Any]], Awaitable[None]]
    run_config_cls: Any
    session_runner_cls: Any


def _resolve_request_range(request: Any) -> tuple[str, str]:
    if request.date_from and request.date_to:
        return request.date_from, request.date_to
    if request.date:
        return request.date, request.date
    raise HTTPException(400, "Either date or date_from/date_to must be provided")


def _normalize_profile_ref_token(value: Any) -> Optional[str]:
    return report_normalize_profile_ref_token(value)


def _first_profile_ref_token(*values: Any) -> Optional[str]:
    return report_first_profile_ref_token(*values)


def _extract_effective_profile_metadata(
    *,
    aos_applied: Dict[str, Any],
    execution_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    return report_extract_effective_profile_metadata(
        aos_applied=aos_applied,
        execution_config=execution_config,
    )


def _summarize_days_preview(days: Any, limit: int = 3) -> str:
    return report_summarize_days_preview(days, limit)


def _build_data_availability_warnings(
    *,
    execution_config: Dict[str, Any],
    l2_applied: Dict[str, Any],
) -> List[str]:
    return report_build_data_availability_warnings(
        execution_config=execution_config,
        l2_applied=l2_applied,
    )


async def _force_enable_all_remote_strategies(
    *,
    strategy_api_url: str,
    fetch_remote_strategies: Callable[[str], Awaitable[Dict[str, Any]]],
    apply_strategy_param_map: Callable[
        [str, Dict[str, Dict[str, Any]]], Awaitable[Dict[str, Any]]
    ],
) -> Dict[str, Any]:
    remote = await fetch_remote_strategies(strategy_api_url)
    if not isinstance(remote, dict):
        return {
            "attempted": True,
            "applied": False,
            "reason": "remote_strategy_catalog_unavailable",
        }

    strategy_names = [str(name).strip() for name in remote.keys() if str(name).strip()]
    if not strategy_names:
        return {
            "attempted": True,
            "applied": False,
            "reason": "no_remote_strategies",
            "strategy_count": 0,
        }

    enable_map = {name: {"enabled": True} for name in strategy_names}
    sync_result = await apply_strategy_param_map(strategy_api_url, enable_map)
    result: Dict[str, Any] = {
        "attempted": True,
        "applied": True,
        "strategy_count": len(strategy_names),
    }
    if isinstance(sync_result, dict):
        result.update(sync_result)
    return result


def _build_report_metadata(
    *,
    run_key: str,
    run_date_label: str,
    aos_applied: Dict[str, Any],
    execution_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return report_build_report_metadata(
        run_key=run_key,
        run_date_label=run_date_label,
        aos_applied=aos_applied,
        execution_config=execution_config,
    )


def _build_run_request_config_snapshot(request: StartRunRequest) -> Dict[str, Any]:
    return report_build_run_request_config_snapshot(request)


def _resolve_prewarm_request_state(
    *,
    request: PrewarmRunRequest,
    deps: StartRunDeps,
) -> PrewarmRequestState:
    ticker = str(request.ticker or "").strip().upper()
    if not ticker:
        raise HTTPException(400, "Ticker is required")
    return prewarm_resolve_request_state(
        request=request,
        ticker=ticker,
        databento_svc=deps.databento_svc,
        get_discovery=deps.get_discovery,
        load_aos_config=deps.load_aos_config,
        get_ticker_positioning_config=deps.get_ticker_positioning_config,
        positioning_config_keys=getattr(deps, "positioning_config_keys", ()) or (),
        resolve_request_range=_resolve_request_range,
        build_l2_guard_reason=_prewarm_l2_guard_reason,
    )


def _inclusive_day_span(start_iso: str, end_iso: str) -> int:
    return planning_inclusive_day_span(start_iso, end_iso)


def _run_l2_guard_reason(
    *,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    range_start: str,
    range_end: str,
) -> Optional[str]:
    return planning_run_l2_guard_reason(
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        range_start=range_start,
        range_end=range_end,
        run_l2_force=RUN_L2_FORCE,
        run_l2_max_days=RUN_L2_MAX_DAYS,
    )


def _prewarm_l2_guard_reason(
    *,
    prewarm_scope: str,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    range_start: str,
    range_end: str,
) -> Optional[str]:
    return planning_prewarm_l2_guard_reason(
        prewarm_scope=prewarm_scope,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        range_start=range_start,
        range_end=range_end,
        prewarm_ticker_scope_l2_force=PREWARM_TICKER_SCOPE_L2_FORCE,
        prewarm_ticker_scope_l2_max_days=PREWARM_TICKER_SCOPE_L2_MAX_DAYS,
        run_l2_force=RUN_L2_FORCE,
        run_l2_max_days=RUN_L2_MAX_DAYS,
    )


def _parse_iso_day(value: Any) -> Optional[datetime]:
    return planning_parse_iso_day(value)


def _format_iso_day(value: datetime) -> str:
    return planning_format_iso_day(value)


def _add_days_iso(value: str, days: int) -> Optional[str]:
    return planning_add_days_iso(value, days)


def _build_progressive_chunks(
    *,
    range_start: str,
    range_end: str,
    initial_days: int,
    chunk_days: int,
) -> list[tuple[str, str]]:
    return planning_build_progressive_chunks(
        range_start=range_start,
        range_end=range_end,
        initial_days=initial_days,
        chunk_days=chunk_days,
    )


def _resolve_progressive_plan(
    *,
    range_start: str,
    range_end: str,
    comparable_mode: bool,
) -> Optional[Dict[str, Any]]:
    return planning_resolve_progressive_plan(
        range_start=range_start,
        range_end=range_end,
        comparable_mode=comparable_mode,
        progressive_load_enabled=PROGRESSIVE_LOAD_ENABLED,
        progressive_load_allow_comparable_mode=PROGRESSIVE_LOAD_ALLOW_COMPARABLE_MODE,
        progressive_load_min_days=PROGRESSIVE_LOAD_MIN_DAYS,
        progressive_load_initial_days=PROGRESSIVE_LOAD_INITIAL_DAYS,
        progressive_load_chunk_days=PROGRESSIVE_LOAD_CHUNK_DAYS,
        progressive_load_comparable_initial_days=PROGRESSIVE_LOAD_COMPARABLE_INITIAL_DAYS,
        progressive_load_comparable_chunk_days=PROGRESSIVE_LOAD_COMPARABLE_CHUNK_DAYS,
    )


def _normalize_reset_scope(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"session", "learning", "all"}:
        return normalized
    return "all"


@dataclass(frozen=True)
class StartRunIdentity:
    ticker: str
    comparable_mode: bool
    effective_cold_start_each_day: bool
    range_start: str
    range_end: str
    full_range_start: str
    full_range_end: str
    load_range_start: str
    load_range_end: str
    progressive_plan: Optional[Dict[str, Any]]
    progressive_pending_chunks: list[tuple[str, str]]
    run_date_label: str
    run_key: str


def _resolve_start_run_identity(
    *,
    request: StartRunRequest,
    active_runners: Dict[str, Any],
) -> StartRunIdentity:
    ticker = request.ticker.upper()
    comparable_mode = bool(request.comparable_mode)
    effective_cold_start_each_day = bool(request.cold_start_each_day or comparable_mode)

    range_start, range_end = _resolve_request_range(request)
    full_range_start = str(range_start)
    full_range_end = str(range_end)
    progressive_plan = _resolve_progressive_plan(
        range_start=full_range_start,
        range_end=full_range_end,
        comparable_mode=comparable_mode,
    )
    progressive_pending_chunks: list[tuple[str, str]] = []
    if progressive_plan:
        load_range_start = str(progressive_plan["initial_start"])
        load_range_end = str(progressive_plan["initial_end"])
        progressive_pending_chunks = list(progressive_plan.get("chunks", []))
    else:
        load_range_start = full_range_start
        load_range_end = full_range_end

    run_date_label = (
        f"{full_range_start}_to_{full_range_end}"
        if full_range_start != full_range_end or request.date_from or request.date_to
        else full_range_start
    )
    run_key = f"{request.run_id}:{ticker}:{run_date_label}"
    if run_key in active_runners:
        raise HTTPException(400, f"Run already exists: {run_key}")

    return StartRunIdentity(
        ticker=ticker,
        comparable_mode=comparable_mode,
        effective_cold_start_each_day=effective_cold_start_each_day,
        range_start=str(range_start),
        range_end=str(range_end),
        full_range_start=full_range_start,
        full_range_end=full_range_end,
        load_range_start=load_range_start,
        load_range_end=load_range_end,
        progressive_plan=progressive_plan,
        progressive_pending_chunks=progressive_pending_chunks,
        run_date_label=run_date_label,
        run_key=run_key,
    )


async def start_run(request: StartRunRequest, deps: StartRunDeps):
    """Start a new backtest run."""
    if not stateful_run_api_supported():
        raise HTTPException(503, stateful_run_api_unsupported_detail())

    start_wall_clock = perf_counter()
    start_timing: Dict[str, Any] = {"phases_ms": {}}

    def _record_phase_ms(phase_name: str, started_at: float) -> None:
        start_timing["phases_ms"][phase_name] = round(
            (perf_counter() - started_at) * 1000.0, 2
        )

    identity = _resolve_start_run_identity(
        request=request,
        active_runners=deps.active_runners,
    )

    bootstrap = await run_start_bootstrap_phase(
        inputs=BootstrapPhaseInputs(
            request=request,
            ticker=identity.ticker,
            comparable_mode=identity.comparable_mode,
        ),
        deps=BootstrapPhaseDeps(
            logger=deps.logger,
            reset_remote_orchestrator_state_scoped=deps.reset_remote_orchestrator_state_scoped,
            load_remote_checkpoint=deps.load_remote_checkpoint,
            reset_remote_orchestrator_state=deps.reset_remote_orchestrator_state,
            clear_remote_strategy_sessions=deps.clear_remote_strategy_sessions,
            apply_strategy_overrides=deps.apply_strategy_overrides,
            apply_aos_optimizations=deps.apply_aos_optimizations,
            normalize_momentum_diversification_payload=deps.normalize_momentum_diversification_payload,
            apply_global_trailing=deps.apply_global_trailing,
            resolve_execution_config=resolve_execution_config,
            normalize_reset_scope=_normalize_reset_scope,
        ),
        record_phase_ms=_record_phase_ms,
    )

    load_phase = await run_start_load_phase(
        inputs=LoadPhaseInputs(
            request=request,
            ticker=identity.ticker,
            run_key=identity.run_key,
            range_start=identity.range_start,
            range_end=identity.range_end,
            load_range_start=identity.load_range_start,
            load_range_end=identity.load_range_end,
            comparable_mode=identity.comparable_mode,
            aos_applied=bootstrap.aos_applied,
            execution_cfg=bootstrap.execution_cfg,
            progressive_plan=identity.progressive_plan,
            progressive_pending_chunks=identity.progressive_pending_chunks,
        ),
        deps=LoadPhaseDeps(
            logger=deps.logger,
            data_loader=deps.data_loader,
            databento_svc=deps.databento_svc,
            get_discovery=deps.get_discovery,
            load_run_bars=load_run_bars,
            enrich_bars_with_l2=enrich_bars_with_l2,
            to_utc_datetime=deps.to_utc_datetime,
            build_l2_feature_map=deps.build_l2_feature_map,
            normalize_l2_feature_map_for_market_day_sessions=deps.normalize_l2_feature_map_for_market_day_sessions,
            attach_l2_features=deps.attach_l2_features,
            run_l2_guard_reason=_run_l2_guard_reason,
        ),
        record_phase_ms=_record_phase_ms,
    )

    async def _force_enable_all_sync() -> Dict[str, Any]:
        return await _force_enable_all_remote_strategies(
            strategy_api_url=request.strategy_api_url,
            fetch_remote_strategies=deps.fetch_remote_strategies,
            apply_strategy_param_map=deps.apply_strategy_param_map,
        )

    session_phase = await run_start_session_phase(
        inputs=SessionPhaseInputs(
            request=request,
            run_key=identity.run_key,
            ticker=identity.ticker,
            range_start=identity.range_start,
            comparable_mode=identity.comparable_mode,
            execution_cfg=bootstrap.execution_cfg,
            l2_stats=load_phase.l2_stats,
            requested_l2_confirm=bool(load_phase.requested_l2_confirm),
            use_l2=bool(load_phase.use_l2),
            effective_cold_start_each_day=identity.effective_cold_start_each_day,
            momentum_diversification_json=bootstrap.momentum_diversification_json,
        ),
        deps=SessionPhaseDeps(
            logger=deps.logger,
            configure_session=deps.configure_session,
            force_enable_all_remote_strategies=_force_enable_all_sync,
        ),
        record_phase_ms=_record_phase_ms,
    )

    threshold_overrides = getattr(request, "threshold_overrides", None)
    if isinstance(threshold_overrides, dict) and threshold_overrides:
        from src.services.run_control_service import _strategy_api_session_deps
        from src.services.strategy_api_session_service import apply_orchestrator_config
        
        phase_started = perf_counter()
        integration_deps = _strategy_api_session_deps(deps.logger)
        await apply_orchestrator_config(
            strategy_api_url=request.strategy_api_url,
            config=threshold_overrides,
            deps=integration_deps,
        )
        _record_phase_ms("apply_threshold_overrides", phase_started)

    if not load_phase.bars:
        raise HTTPException(400, "No data available for the specified date/range")

    phase_started = perf_counter()
    ref_bars_map = load_reference_bars_map(
        ticker=identity.ticker,
        range_start=identity.load_range_start,
        range_end=str(load_phase.load_range_end),
        data_loader=deps.data_loader,
        databento_svc=deps.databento_svc,
        get_discovery=deps.get_discovery,
        logger=deps.logger,
    )
    ref_bars_map = filter_reference_map_for_requested_time_window(
        ref_bars_map=ref_bars_map,
        request=request,
        to_utc_datetime=deps.to_utc_datetime,
    )
    _record_phase_ms("load_reference_bars", phase_started)

    phase_started = perf_counter()
    runner, ref_bars_map = setup_runner_with_progressive_loading(
        inputs=RunnerSetupInputs(
            request=request,
            run_key=identity.run_key,
            run_date_label=identity.run_date_label,
            ticker=identity.ticker,
            range_start=identity.range_start,
            range_end=identity.range_end,
            load_range_start=identity.load_range_start,
            load_range_end=str(load_phase.load_range_end),
            full_range_start=identity.full_range_start,
            full_range_end=identity.full_range_end,
            comparable_mode=identity.comparable_mode,
            bars=list(load_phase.bars),
            ref_bars_map=ref_bars_map,
            session_config_snapshot=session_phase.session_config_snapshot,
            effective_intrabar_execution_recalc_1s=(
                session_phase.effective_intrabar_execution_recalc_1s
            ),
            effective_intrabar_eval_step_seconds=(
                session_phase.effective_intrabar_eval_step_seconds
            ),
            checkpoint_loaded=bootstrap.checkpoint_loaded,
            progressive_plan=load_phase.progressive_plan,
            aos_applied=bootstrap.aos_applied,
            requested_l2_only=bool(load_phase.requested_l2_only),
            requested_l2_confirm=bool(load_phase.requested_l2_confirm),
        ),
        deps=RunnerSetupDeps(
            active_runners=deps.active_runners,
            logger=deps.logger,
            data_loader=deps.data_loader,
            databento_svc=deps.databento_svc,
            l2_manager=deps.l2_manager,
            get_discovery=deps.get_discovery,
            broadcast=deps.broadcast,
            run_config_cls=deps.run_config_cls,
            session_runner_cls=deps.session_runner_cls,
            to_utc_datetime=deps.to_utc_datetime,
            build_l2_feature_map=deps.build_l2_feature_map,
            normalize_l2_feature_map_for_market_day_sessions=deps.normalize_l2_feature_map_for_market_day_sessions,
            attach_l2_features=deps.attach_l2_features,
            load_run_bars=load_run_bars,
            enrich_bars_with_l2=enrich_bars_with_l2,
            load_reference_bars_map=load_reference_bars_map,
        ),
    )
    _record_phase_ms("runner_setup", phase_started)

    bars = list(load_phase.bars)
    start_timing["total_ms"] = round((perf_counter() - start_wall_clock) * 1000.0, 2)
    phases_ms = start_timing.get("phases_ms", {})
    if phases_ms:
        slowest_phase, slowest_phase_ms = max(
            phases_ms.items(), key=lambda item: float(item[1])
        )
        start_timing["slowest_phase"] = str(slowest_phase)
        start_timing["slowest_phase_ms"] = float(slowest_phase_ms)
    start_timing["context"] = {
        "ticker": identity.ticker,
        "range_start": identity.full_range_start,
        "range_end": identity.full_range_end,
        "start_time": str(getattr(request, "start_time", "") or ""),
        "end_time": str(getattr(request, "end_time", "") or ""),
        "trade_start_time": str(getattr(request, "trade_start_time", "") or ""),
        "trade_end_time": str(getattr(request, "trade_end_time", "") or ""),
        "initial_loaded_range_start": identity.load_range_start,
        "initial_loaded_range_end": str(load_phase.load_range_end),
        "bars_loaded": len(bars),
        "reference_bars_loaded": len(ref_bars_map),
        "orchestrator_reset_scope": bootstrap.effective_reset_scope,
        "apply_aos_optimizations_on_start": bootstrap.apply_aos_optimizations_on_start,
        "use_l2": bool(load_phase.use_l2),
        "requested_l2_only": bool(load_phase.requested_l2_only),
        "requested_l2_confirm_enabled": bool(load_phase.requested_l2_confirm),
        "effective_l2_confirm_enabled": bool(session_phase.effective_l2_confirm),
        "effective_trade_eval_mode": session_phase.effective_trade_eval_mode,
        "effective_intrabar_eval_step_seconds": int(
            session_phase.effective_intrabar_eval_step_seconds
        ),
        "l2_has_data": bool(load_phase.l2_stats.get("has_l2")),
        "liquidity_sweep_detection_enabled": bool(
            bootstrap.execution_cfg.get(
                "effective_liquidity_sweep_detection_enabled", False
            )
        ),
        "liquidity_sweep_l2_auto_enabled": bool(
            bootstrap.execution_cfg.get("liquidity_sweep_l2_auto_enabled", False)
        ),
        "liquidity_sweep_l2_auto_source": str(
            bootstrap.execution_cfg.get("liquidity_sweep_l2_auto_source", "disabled")
        ),
        "all_enabled_remote_sync_attempted": bool(
            session_phase.all_enabled_remote_sync
        ),
        "progressive_loading_enabled": bool(load_phase.progressive_plan),
        "progressive_pending_chunks": (
            len(load_phase.progressive_plan.get("chunks", []))
            if isinstance(load_phase.progressive_plan, dict)
            else 0
        ),
    }

    execution_payload = build_execution_payload(
        inputs=ExecutionPayloadInputs(
            request=request,
            execution_cfg=bootstrap.execution_cfg,
            aos_applied=bootstrap.aos_applied,
            control_plane_snapshot=bootstrap.control_plane_snapshot,
            momentum_diversification_source=bootstrap.momentum_diversification_source,
            effective_momentum_diversification=bootstrap.effective_momentum_diversification,
            effective_intrabar_execution_recalc_1s=session_phase.effective_intrabar_execution_recalc_1s,
            effective_intrabar_eval_step_seconds=session_phase.effective_intrabar_eval_step_seconds,
            effective_cold_start_each_day=identity.effective_cold_start_each_day,
            comparable_mode=identity.comparable_mode,
            effective_reset_scope=bootstrap.effective_reset_scope,
            apply_aos_optimizations_on_start=bootstrap.apply_aos_optimizations_on_start,
            effective_strategy_selection_mode=session_phase.effective_strategy_selection_mode,
            effective_max_active_strategies=session_phase.effective_max_active_strategies,
            all_enabled_remote_sync=session_phase.all_enabled_remote_sync,
            l2_stats=load_phase.l2_stats,
            l2_sessionized_by_market_day=load_phase.l2_sessionized_by_market_day,
            requested_l2_only_raw=load_phase.requested_l2_only_raw,
            requested_l2_confirm_raw=load_phase.requested_l2_confirm_raw,
            l2_guard_reason=load_phase.l2_guard_reason,
            effective_l2_confirm=session_phase.effective_l2_confirm,
            l2_auto_enabled_by_sweep=bool(
                bootstrap.execution_cfg.get("liquidity_sweep_l2_auto_enabled", False)
            ),
            l2_auto_enabled_source=str(
                bootstrap.execution_cfg.get(
                    "liquidity_sweep_l2_auto_source", "disabled"
                )
            ),
        ),
        canonical_trading_hours=_canonical_trading_hours,
        extract_effective_profile_metadata=_extract_effective_profile_metadata,
    )
    execution_config_payload = dict(execution_payload.execution_config_payload)
    l2_applied_payload = dict(execution_payload.l2_applied_payload)
    runner._aos_applied = (
        dict(bootstrap.aos_applied) if isinstance(bootstrap.aos_applied, dict) else {}
    )
    runner._execution_config = dict(execution_config_payload)
    runner._control_plane_snapshot = (
        dict(bootstrap.control_plane_snapshot)
        if isinstance(bootstrap.control_plane_snapshot, dict)
        else {}
    )
    runner._l2_applied = dict(l2_applied_payload)
    runner._strategy_state_reset = _strategy_reset_success(bootstrap.orchestrator_reset)
    runner._strategy_state_reset_detail = _strategy_reset_detail(
        bootstrap.orchestrator_reset
    )
    runner._orchestrator_reset_scope = bootstrap.effective_reset_scope
    runner._checkpoint_loaded = (
        dict(bootstrap.checkpoint_loaded)
        if isinstance(bootstrap.checkpoint_loaded, dict)
        else bootstrap.checkpoint_loaded
    )
    runner._data_selection_warnings = _build_data_availability_warnings(
        execution_config=runner._execution_config,
        l2_applied=runner._l2_applied,
    )
    if runner._data_selection_warnings:
        runner.selection_warnings = list(runner._data_selection_warnings)
    runner._report_metadata = _build_report_metadata(
        run_key=identity.run_key,
        run_date_label=identity.run_date_label,
        aos_applied=runner._aos_applied,
        execution_config=runner._execution_config,
    )
    runner._run_request_config = _build_run_request_config_snapshot(request)
    runner._resolved_config_snapshot = build_resolved_config_snapshot(
        run_id=request.run_id,
        ticker=identity.ticker,
        date_label=identity.run_date_label,
        report_metadata=runner._report_metadata,
        control_plane_snapshot=runner._control_plane_snapshot,
        aos_applied=runner._aos_applied,
        execution_config=runner._execution_config,
        run_request_config=runner._run_request_config,
        l2_applied=runner._l2_applied,
        session_config_snapshot=session_phase.session_config_snapshot,
        to_json_safe=_to_json_compatible,
    )

    deps.logger.info(f"Started run {identity.run_key} with {len(bars)} bars")

    response = {
        "success": True,
        "run_key": identity.run_key,
        "ticker": identity.ticker,
        "total_bars": len(bars),
        "requested_range": {
            "date_from": identity.full_range_start,
            "date_to": identity.full_range_end,
        },
        "progressive_loading": {
            "enabled": bool(load_phase.progressive_plan),
            "initial_range_start": identity.load_range_start,
            "initial_range_end": str(load_phase.load_range_end),
            "loaded_until": getattr(
                runner,
                "_progressive_loading_loaded_until",
                str(load_phase.load_range_end),
            ),
            "target_end": identity.full_range_end,
            "pending_chunks": int(
                getattr(runner, "_progressive_loading_pending_chunks", 0)
            ),
            "complete": bool(getattr(runner, "_progressive_loading_complete", True)),
            "last_error": getattr(runner, "_progressive_loading_last_error", None),
        },
        "strategy_state_reset": _strategy_reset_success(bootstrap.orchestrator_reset),
        "strategy_state_reset_detail": _strategy_reset_detail(bootstrap.orchestrator_reset),
        "orchestrator_reset_scope": bootstrap.effective_reset_scope,
        "checkpoint_loaded": bootstrap.checkpoint_loaded,
        "strategy_overrides_applied": bootstrap.strategy_overrides_applied,
        "data_files": list(load_phase.data_files),
        "aos_applied": bootstrap.aos_applied,
        "control_plane_snapshot": bootstrap.control_plane_snapshot,
        "l2_applied": l2_applied_payload,
        "execution_config": execution_config_payload,
        "start_timing": start_timing,
        "first_bar": bars[0] if bars else None,
        "last_bar": bars[-1] if bars else None,
    }
    return _to_json_compatible(response)


async def prewarm_run_data(
    request: PrewarmRunRequest, deps: StartRunDeps
) -> Dict[str, Any]:
    logger = deps.logger
    state = _resolve_prewarm_request_state(request=request, deps=deps)
    prewarm_raise_for_guard_reason(state=state, logger=logger)

    cached_result = get_prewarm_result(state.prewarm_cache_key)
    if isinstance(cached_result, dict):
        logger.info(
            "Using prewarm result cache for %s %s..%s",
            state.ticker,
            state.range_start,
            state.range_end,
        )
        cached_payload = dict(cached_result)
        cached_payload["cache_hit"] = True
        cached_payload["cache_key"] = state.prewarm_cache_key
        cached_payload["cache_stats"] = get_start_run_data_cache_stats()
        return cached_payload
    shared_future, is_owner = _PREWARM_INFLIGHT_REGISTRY.acquire(state.prewarm_cache_key)
    if not is_owner:
        logger.info(
            "Joining in-flight prewarm for %s %s..%s",
            state.ticker,
            state.range_start,
            state.range_end,
        )
        joined_result = await asyncio.wrap_future(shared_future)
        joined_payload = dict(joined_result)
        joined_payload["cache_hit"] = True
        joined_payload["cache_key"] = state.prewarm_cache_key
        joined_payload["cache_stats"] = get_start_run_data_cache_stats()
        joined_payload["joined_inflight"] = True
        return joined_payload

    try:
        bars, data_files = load_run_bars(
            request=request,
            ticker=state.ticker,
            range_start=state.range_start,
            range_end=state.range_end,
            data_loader=deps.data_loader,
            databento_svc=deps.databento_svc,
            get_discovery=deps.get_discovery,
            aos_applied=state.aos_applied,
            logger=logger,
        )

        bars, l2_stats, l2_sessionized_by_market_day = enrich_bars_with_l2(
            bars=bars,
            ticker=state.ticker,
            range_start=state.range_start,
            range_end=state.range_end,
            requested_l2_only=state.requested_l2_only,
            requested_l2_confirm=state.requested_l2_confirm,
            comparable_mode=bool(request.comparable_mode),
            is_multi_day_request=state.is_multi_day_request,
            aos_l2_config_applied=bool(
                isinstance(state.aos_applied.get("l2"), dict)
                and state.aos_applied.get("l2")
            ),
            to_utc_datetime=deps.to_utc_datetime,
            build_l2_feature_map=deps.build_l2_feature_map,
            normalize_l2_feature_map_for_market_day_sessions=deps.normalize_l2_feature_map_for_market_day_sessions,
            attach_l2_features=deps.attach_l2_features,
            logger=logger,
        )

        ref_bars_map = load_reference_bars_map(
            ticker=state.ticker,
            range_start=state.range_start,
            range_end=state.range_end,
            data_loader=deps.data_loader,
            databento_svc=deps.databento_svc,
            get_discovery=deps.get_discovery,
            logger=logger,
        )

        result = {
            "success": True,
            "ticker": state.ticker,
            "prewarm_scope": state.prewarm_scope,
            "range_start": state.range_start,
            "range_end": state.range_end,
            "bars": len(bars),
            "data_files_count": len(data_files),
            "reference_bars": len(ref_bars_map),
            "l2_requested": bool(
                state.requested_l2_only_raw or state.requested_l2_confirm_raw
            ),
            "use_l2": bool(state.requested_l2_only or state.requested_l2_confirm),
            "l2_only": state.requested_l2_only,
            "l2_confirm_enabled": state.requested_l2_confirm,
            "l2_guard_reason": state.l2_guard_reason,
            "l2_sessionized_by_market_day": l2_sessionized_by_market_day,
            "l2": l2_stats,
            "cache_hit": False,
            "cache_key": state.prewarm_cache_key,
            "cache_stats": get_start_run_data_cache_stats(),
        }
        set_prewarm_result(state.prewarm_cache_key, result)
        if not shared_future.done():
            shared_future.set_result(dict(result))
        return result
    except Exception as exc:
        if not shared_future.done():
            shared_future.set_exception(exc)
        raise
    finally:
        _PREWARM_INFLIGHT_REGISTRY.release(state.prewarm_cache_key, shared_future)


async def get_prewarm_status(
    request: PrewarmRunRequest, deps: StartRunDeps
) -> Dict[str, Any]:
    """Check whether a prewarm request key is already ready/in-flight without loading data."""
    state = _resolve_prewarm_request_state(request=request, deps=deps)
    prewarm_raise_for_guard_reason(state=state, logger=deps.logger)
    cached_result = get_prewarm_result(state.prewarm_cache_key)
    in_progress = _PREWARM_INFLIGHT_REGISTRY.is_inflight(state.prewarm_cache_key)

    response = {
        "success": True,
        "ready": bool(isinstance(cached_result, dict)),
        "in_progress": bool(in_progress),
        "cache_key": state.prewarm_cache_key,
        "ticker": state.ticker,
        "prewarm_scope": state.prewarm_scope,
        "range_start": state.range_start,
        "range_end": state.range_end,
        "l2_requested": bool(
            state.requested_l2_only_raw or state.requested_l2_confirm_raw
        ),
        "use_l2": bool(state.requested_l2_only or state.requested_l2_confirm),
        "l2_only": state.requested_l2_only,
        "l2_confirm_enabled": state.requested_l2_confirm,
        "l2_guard_reason": state.l2_guard_reason,
        "cache_stats": get_start_run_data_cache_stats(),
    }
    if isinstance(cached_result, dict):
        response.update(
            {
                "bars": int(cached_result.get("bars", 0) or 0),
                "reference_bars": int(cached_result.get("reference_bars", 0) or 0),
                "l2_sessionized_by_market_day": bool(
                    cached_result.get("l2_sessionized_by_market_day", False)
                ),
                "l2": dict(cached_result.get("l2", {})),
            }
        )
    return response
