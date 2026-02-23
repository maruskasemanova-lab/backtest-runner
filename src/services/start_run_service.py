from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any, Awaitable, Callable, Dict, Optional

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
from src.services.start_run_local_aos_service import resolve_local_aos_applied
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
_PREWARM_INFLIGHT: Dict[str, concurrent.futures.Future] = {}
_PREWARM_INFLIGHT_LOCK = threading.Lock()
_PROFILE_PLACEHOLDER_TOKENS = {"none", "null", "n/a", "na", "undefined", "-"}


def _acquire_prewarm_inflight(key: str) -> tuple[concurrent.futures.Future, bool]:
    with _PREWARM_INFLIGHT_LOCK:
        existing = _PREWARM_INFLIGHT.get(key)
        if isinstance(existing, concurrent.futures.Future):
            if existing.done():
                _PREWARM_INFLIGHT.pop(key, None)
            else:
                return existing, False
        future: concurrent.futures.Future = concurrent.futures.Future()
        _PREWARM_INFLIGHT[key] = future
        return future, True


def _release_prewarm_inflight(key: str, future: concurrent.futures.Future) -> None:
    with _PREWARM_INFLIGHT_LOCK:
        current = _PREWARM_INFLIGHT.get(key)
        if current is future:
            _PREWARM_INFLIGHT.pop(key, None)


def _is_prewarm_inflight(key: str) -> bool:
    with _PREWARM_INFLIGHT_LOCK:
        current = _PREWARM_INFLIGHT.get(key)
        if not isinstance(current, concurrent.futures.Future):
            return False
        if current.done():
            _PREWARM_INFLIGHT.pop(key, None)
            return False
        return True


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
    token = str(value).strip() if value is not None else ""
    if not token:
        return None
    if token.lower() in _PROFILE_PLACEHOLDER_TOKENS:
        return None
    return token


def _first_profile_ref_token(*values: Any) -> Optional[str]:
    for value in values:
        token = _normalize_profile_ref_token(value)
        if token:
            return token
    return None


def _extract_effective_profile_metadata(
    *,
    aos_applied: Dict[str, Any],
    execution_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    execution_payload = execution_config if isinstance(execution_config, dict) else {}
    unified_meta = (
        aos_applied.get("unified_profile", {})
        if isinstance(aos_applied.get("unified_profile"), dict)
        else {}
    )
    adaptive_meta = (
        aos_applied.get("adaptive_profile", {})
        if isinstance(aos_applied.get("adaptive_profile"), dict)
        else {}
    )
    strategy_combo_meta = (
        aos_applied.get("strategy_combo", {})
        if isinstance(aos_applied.get("strategy_combo"), dict)
        else {}
    )
    return {
        "unified_profile_id": _first_profile_ref_token(
            execution_payload.get("unified_profile_id"),
            execution_payload.get("active_unified_profile_id"),
            unified_meta.get("active_profile_id"),
            unified_meta.get("profile_id"),
        ),
        "unified_profile_name": _first_profile_ref_token(
            execution_payload.get("unified_profile_name"),
            unified_meta.get("profile_name"),
        ),
        "adaptive_profile_id": _first_profile_ref_token(
            execution_payload.get("adaptive_profile_id"),
            execution_payload.get("active_adaptive_tuner_profile_id"),
            adaptive_meta.get("active_profile_id"),
            adaptive_meta.get("profile_id"),
        ),
        "adaptive_profile_name": _first_profile_ref_token(
            execution_payload.get("adaptive_profile_name"),
            adaptive_meta.get("profile_name"),
        ),
        "strategy_combo_profile_id": _first_profile_ref_token(
            execution_payload.get("strategy_combo_profile_id"),
            execution_payload.get("active_strategy_combo_profile_id"),
            strategy_combo_meta.get("active_profile_id"),
            strategy_combo_meta.get("profile_id"),
        ),
        "strategy_combo_profile_name": _first_profile_ref_token(
            execution_payload.get("strategy_combo_profile_name"),
            strategy_combo_meta.get("profile_name"),
        ),
    }


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
    profile_meta = _extract_effective_profile_metadata(
        aos_applied=aos_applied,
        execution_config=execution_config,
    )
    return {
        "run_key": str(run_key),
        "run_date_label": str(run_date_label),
        "unified_profile_id": profile_meta.get("unified_profile_id"),
        "unified_profile_name": profile_meta.get("unified_profile_name"),
        "adaptive_profile_id": profile_meta.get("adaptive_profile_id"),
        "adaptive_profile_name": profile_meta.get("adaptive_profile_name"),
        "strategy_combo_profile_id": profile_meta.get("strategy_combo_profile_id"),
        "strategy_combo_profile_name": profile_meta.get("strategy_combo_profile_name"),
    }


def _canonical_trading_hours(raw_hours: Any) -> tuple[int, ...]:
    if not isinstance(raw_hours, list):
        return tuple()
    normalized = []
    seen = set()
    for item in raw_hours:
        try:
            hour = int(item)
        except (TypeError, ValueError):
            continue
        if hour < 0 or hour > 23 or hour in seen:
            continue
        seen.add(hour)
        normalized.append(hour)
    return tuple(sorted(normalized))


def _build_prewarm_cache_key(
    *,
    request: PrewarmRunRequest,
    prewarm_scope: str,
    ticker: str,
    range_start: str,
    range_end: str,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    aos_applied: Dict[str, Any],
) -> str:
    key_payload = {
        "ticker": ticker,
        "prewarm_scope": str(prewarm_scope or "range").strip().lower(),
        "range_start": str(range_start),
        "range_end": str(range_end),
        "data_file": str(request.data_file or ""),
        "allow_mock_data": bool(request.allow_mock_data),
        "comparable_mode": bool(request.comparable_mode),
        "requested_l2_only": bool(requested_l2_only),
        "requested_l2_confirm": bool(requested_l2_confirm),
        "include_extended_hours": (
            None
            if getattr(request, "include_extended_hours", None) is None
            else bool(request.include_extended_hours)
        ),
        "time_filter_enabled": bool(aos_applied.get("time_filter_enabled", False)),
        "trading_hours": _canonical_trading_hours(aos_applied.get("trading_hours")),
        "aos_config_path": str(getattr(request, "aos_config_path", "") or ""),
    }
    return json.dumps(key_payload, sort_keys=True, separators=(",", ":"))


def _resolve_prewarm_scope_range(
    *,
    request: PrewarmRunRequest,
    ticker: str,
    databento_svc: Any,
    get_discovery: Callable[[], Any],
) -> tuple[str, str, str]:
    requested_scope = (
        str(getattr(request, "prewarm_scope", "range") or "range").strip().lower()
    )
    prewarm_scope = (
        requested_scope if requested_scope in {"range", "ticker"} else "range"
    )
    if prewarm_scope == "range":
        range_start, range_end = _resolve_request_range(request)
        return prewarm_scope, range_start, range_end

    # Ticker-level prewarm resolves to full locally available OHLCV coverage.
    try:
        databento_svc.scan_existing_files()
    except Exception:
        pass

    try:
        summary = databento_svc.get_available_data_summary(refresh=True)
    except Exception:
        summary = {}
    date_ranges = summary.get("date_ranges", {}) if isinstance(summary, dict) else {}
    ticker_range = date_ranges.get(ticker, {}) if isinstance(date_ranges, dict) else {}
    range_start = str(ticker_range.get("start") or "").strip()
    range_end = str(ticker_range.get("end") or "").strip()

    if not range_start or not range_end:
        try:
            discovery = get_discovery()
            fallback = discovery.get_date_range(ticker)
        except Exception:
            fallback = {}
        if isinstance(fallback, dict):
            range_start = str(fallback.get("start") or range_start).strip()
            range_end = str(fallback.get("end") or range_end).strip()

    if not range_start or not range_end:
        raise HTTPException(
            404,
            f"No available OHLCV coverage found for ticker {ticker} for ticker-level prewarm.",
        )
    return prewarm_scope, range_start, range_end


def _inclusive_day_span(start_iso: str, end_iso: str) -> int:
    try:
        start_dt = datetime.strptime(str(start_iso), "%Y-%m-%d")
        end_dt = datetime.strptime(str(end_iso), "%Y-%m-%d")
    except Exception:
        return 0
    delta_days = (end_dt - start_dt).days
    return max(0, delta_days + 1)


def _run_l2_guard_reason(
    *,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    range_start: str,
    range_end: str,
) -> Optional[str]:
    if not bool(requested_l2_only or requested_l2_confirm):
        return None
    day_span = _inclusive_day_span(range_start, range_end)
    if RUN_L2_FORCE or RUN_L2_MAX_DAYS <= 0 or day_span <= RUN_L2_MAX_DAYS:
        return None
    return (
        "L2 request rejected: requested range "
        f"{range_start}..{range_end} covers {day_span} day(s), which exceeds "
        f"BACKTEST_RUN_L2_MAX_DAYS={RUN_L2_MAX_DAYS}. "
        "Set BACKTEST_RUN_L2_FORCE=1 or increase BACKTEST_RUN_L2_MAX_DAYS "
        "to allow full-range L2."
    )


def _prewarm_l2_guard_reason(
    *,
    prewarm_scope: str,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    range_start: str,
    range_end: str,
) -> Optional[str]:
    if not bool(requested_l2_only or requested_l2_confirm):
        return None
    day_span = _inclusive_day_span(range_start, range_end)
    scope = str(prewarm_scope or "range").strip().lower()
    if scope == "ticker":
        if (
            PREWARM_TICKER_SCOPE_L2_FORCE
            or PREWARM_TICKER_SCOPE_L2_MAX_DAYS <= 0
            or day_span <= PREWARM_TICKER_SCOPE_L2_MAX_DAYS
        ):
            return None
        return (
            "L2 prewarm rejected for ticker scope: requested range "
            f"{range_start}..{range_end} covers {day_span} day(s), which exceeds "
            "BACKTEST_PREWARM_TICKER_SCOPE_L2_MAX_DAYS="
            f"{PREWARM_TICKER_SCOPE_L2_MAX_DAYS}. "
            "Set BACKTEST_PREWARM_TICKER_SCOPE_L2_FORCE=1 or increase "
            "BACKTEST_PREWARM_TICKER_SCOPE_L2_MAX_DAYS to allow full-range L2 prewarm."
        )

    if RUN_L2_FORCE or RUN_L2_MAX_DAYS <= 0 or day_span <= RUN_L2_MAX_DAYS:
        return None
    return (
        "L2 prewarm rejected for range scope: requested range "
        f"{range_start}..{range_end} covers {day_span} day(s), which exceeds "
        f"BACKTEST_RUN_L2_MAX_DAYS={RUN_L2_MAX_DAYS}. "
        "Set BACKTEST_RUN_L2_FORCE=1 or increase BACKTEST_RUN_L2_MAX_DAYS "
        "to allow full-range L2 prewarm."
    )


def _parse_iso_day(value: Any) -> Optional[datetime]:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except Exception:
        return None


def _format_iso_day(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def _add_days_iso(value: str, days: int) -> Optional[str]:
    base = _parse_iso_day(value)
    if base is None:
        return None
    return _format_iso_day(base + timedelta(days=int(days)))


def _build_progressive_chunks(
    *,
    range_start: str,
    range_end: str,
    initial_days: int,
    chunk_days: int,
) -> list[tuple[str, str]]:
    start_dt = _parse_iso_day(range_start)
    end_dt = _parse_iso_day(range_end)
    if start_dt is None or end_dt is None or start_dt > end_dt:
        return []

    initial_span = max(1, int(initial_days))
    chunk_span = max(1, int(chunk_days))
    initial_end_dt = min(end_dt, start_dt + timedelta(days=initial_span - 1))
    next_start_dt = initial_end_dt + timedelta(days=1)

    chunks: list[tuple[str, str]] = []
    while next_start_dt <= end_dt:
        chunk_end_dt = min(end_dt, next_start_dt + timedelta(days=chunk_span - 1))
        chunks.append((_format_iso_day(next_start_dt), _format_iso_day(chunk_end_dt)))
        next_start_dt = chunk_end_dt + timedelta(days=1)
    return chunks


def _resolve_progressive_plan(
    *,
    range_start: str,
    range_end: str,
    comparable_mode: bool,
) -> Optional[Dict[str, Any]]:
    if not PROGRESSIVE_LOAD_ENABLED:
        return None
    if comparable_mode and not PROGRESSIVE_LOAD_ALLOW_COMPARABLE_MODE:
        return None

    day_span = _inclusive_day_span(range_start, range_end)
    min_days = max(1, int(PROGRESSIVE_LOAD_MIN_DAYS))
    if day_span <= min_days:
        return None

    if comparable_mode:
        initial_days = max(1, int(PROGRESSIVE_LOAD_COMPARABLE_INITIAL_DAYS))
        chunk_days = max(1, int(PROGRESSIVE_LOAD_COMPARABLE_CHUNK_DAYS))
    else:
        initial_days = max(1, int(PROGRESSIVE_LOAD_INITIAL_DAYS))
        chunk_days = max(1, int(PROGRESSIVE_LOAD_CHUNK_DAYS))

    initial_end = _add_days_iso(range_start, initial_days - 1) or range_end
    if initial_end > range_end:
        initial_end = range_end

    chunks = _build_progressive_chunks(
        range_start=range_start,
        range_end=range_end,
        initial_days=initial_days,
        chunk_days=chunk_days,
    )
    if not chunks:
        return None

    return {
        "initial_start": range_start,
        "initial_end": initial_end,
        "target_end": range_end,
        "chunks": chunks,
        "day_span": day_span,
        "initial_days": initial_days,
        "chunk_days": chunk_days,
    }


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
            momentum_diversification_source=bootstrap.momentum_diversification_source,
            effective_momentum_diversification=bootstrap.effective_momentum_diversification,
            effective_intrabar_execution_recalc_1s=session_phase.effective_intrabar_execution_recalc_1s,
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
    runner._report_metadata = _build_report_metadata(
        run_key=identity.run_key,
        run_date_label=identity.run_date_label,
        aos_applied=runner._aos_applied,
        execution_config=runner._execution_config,
    )

    deps.logger.info(f"Started run {identity.run_key} with {len(bars)} bars")

    return {
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
        "strategy_state_reset": bootstrap.orchestrator_reset,
        "orchestrator_reset_scope": bootstrap.effective_reset_scope,
        "checkpoint_loaded": bootstrap.checkpoint_loaded,
        "strategy_overrides_applied": bootstrap.strategy_overrides_applied,
        "data_files": list(load_phase.data_files),
        "aos_applied": bootstrap.aos_applied,
        "l2_applied": l2_applied_payload,
        "execution_config": execution_config_payload,
        "start_timing": start_timing,
        "first_bar": bars[0] if bars else None,
        "last_bar": bars[-1] if bars else None,
    }


async def prewarm_run_data(
    request: PrewarmRunRequest, deps: StartRunDeps
) -> Dict[str, Any]:
    logger = deps.logger
    ticker = str(request.ticker or "").strip().upper()
    if not ticker:
        raise HTTPException(400, "Ticker is required")

    prewarm_scope, range_start, range_end = _resolve_prewarm_scope_range(
        request=request,
        ticker=ticker,
        databento_svc=deps.databento_svc,
        get_discovery=deps.get_discovery,
    )
    is_multi_day_request = bool(
        range_start != range_end or bool(request.date_from and request.date_to)
    )

    aos_applied = resolve_local_aos_applied(
        ticker=ticker,
        load_aos_config=deps.load_aos_config,
        get_ticker_positioning_config=deps.get_ticker_positioning_config,
        aos_config_path=getattr(request, "aos_config_path", None),
    )

    aos_l2_cfg = (
        aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}
    )
    requested_l2_only_raw = bool(
        request.l2_only or bool(aos_l2_cfg.get("l2_only", False))
    )
    requested_l2_confirm_raw = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    requested_l2_only = requested_l2_only_raw
    requested_l2_confirm = requested_l2_confirm_raw
    l2_guard_reason = _prewarm_l2_guard_reason(
        prewarm_scope=prewarm_scope,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        range_start=range_start,
        range_end=range_end,
    )
    if l2_guard_reason:
        logger.warning(
            "%s ticker=%s range=%s..%s",
            l2_guard_reason,
            ticker,
            range_start,
            range_end,
        )
        raise HTTPException(400, l2_guard_reason)

    prewarm_cache_key = _build_prewarm_cache_key(
        request=request,
        prewarm_scope=prewarm_scope,
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        aos_applied=aos_applied,
    )
    cached_result = get_prewarm_result(prewarm_cache_key)
    if isinstance(cached_result, dict):
        logger.info(
            "Using prewarm result cache for %s %s..%s",
            ticker,
            range_start,
            range_end,
        )
        cached_payload = dict(cached_result)
        cached_payload["cache_hit"] = True
        cached_payload["cache_key"] = prewarm_cache_key
        cached_payload["cache_stats"] = get_start_run_data_cache_stats()
        return cached_payload
    shared_future, is_owner = _acquire_prewarm_inflight(prewarm_cache_key)
    if not is_owner:
        logger.info(
            "Joining in-flight prewarm for %s %s..%s",
            ticker,
            range_start,
            range_end,
        )
        joined_result = await asyncio.wrap_future(shared_future)
        joined_payload = dict(joined_result)
        joined_payload["cache_hit"] = True
        joined_payload["cache_key"] = prewarm_cache_key
        joined_payload["cache_stats"] = get_start_run_data_cache_stats()
        joined_payload["joined_inflight"] = True
        return joined_payload

    try:
        bars, data_files = load_run_bars(
            request=request,
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            data_loader=deps.data_loader,
            databento_svc=deps.databento_svc,
            get_discovery=deps.get_discovery,
            aos_applied=aos_applied,
            logger=logger,
        )

        bars, l2_stats, l2_sessionized_by_market_day = enrich_bars_with_l2(
            bars=bars,
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            requested_l2_only=requested_l2_only,
            requested_l2_confirm=requested_l2_confirm,
            comparable_mode=bool(request.comparable_mode),
            is_multi_day_request=is_multi_day_request,
            aos_l2_config_applied=bool(
                isinstance(aos_applied.get("l2"), dict) and aos_applied.get("l2")
            ),
            to_utc_datetime=deps.to_utc_datetime,
            build_l2_feature_map=deps.build_l2_feature_map,
            normalize_l2_feature_map_for_market_day_sessions=deps.normalize_l2_feature_map_for_market_day_sessions,
            attach_l2_features=deps.attach_l2_features,
            logger=logger,
        )

        ref_bars_map = load_reference_bars_map(
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            data_loader=deps.data_loader,
            databento_svc=deps.databento_svc,
            get_discovery=deps.get_discovery,
            logger=logger,
        )

        result = {
            "success": True,
            "ticker": ticker,
            "prewarm_scope": prewarm_scope,
            "range_start": range_start,
            "range_end": range_end,
            "bars": len(bars),
            "data_files_count": len(data_files),
            "reference_bars": len(ref_bars_map),
            "l2_requested": bool(requested_l2_only_raw or requested_l2_confirm_raw),
            "use_l2": bool(requested_l2_only or requested_l2_confirm),
            "l2_only": requested_l2_only,
            "l2_confirm_enabled": requested_l2_confirm,
            "l2_guard_reason": l2_guard_reason,
            "l2_sessionized_by_market_day": l2_sessionized_by_market_day,
            "l2": l2_stats,
            "cache_hit": False,
            "cache_key": prewarm_cache_key,
            "cache_stats": get_start_run_data_cache_stats(),
        }
        set_prewarm_result(prewarm_cache_key, result)
        if not shared_future.done():
            shared_future.set_result(dict(result))
        return result
    except Exception as exc:
        if not shared_future.done():
            shared_future.set_exception(exc)
        raise
    finally:
        _release_prewarm_inflight(prewarm_cache_key, shared_future)


async def get_prewarm_status(
    request: PrewarmRunRequest, deps: StartRunDeps
) -> Dict[str, Any]:
    """Check whether a prewarm request key is already ready/in-flight without loading data."""
    logger = deps.logger
    ticker = str(request.ticker or "").strip().upper()
    if not ticker:
        raise HTTPException(400, "Ticker is required")

    prewarm_scope, range_start, range_end = _resolve_prewarm_scope_range(
        request=request,
        ticker=ticker,
        databento_svc=deps.databento_svc,
        get_discovery=deps.get_discovery,
    )
    aos_applied = resolve_local_aos_applied(
        ticker=ticker,
        load_aos_config=deps.load_aos_config,
        get_ticker_positioning_config=deps.get_ticker_positioning_config,
        aos_config_path=getattr(request, "aos_config_path", None),
    )
    aos_l2_cfg = (
        aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}
    )
    requested_l2_only_raw = bool(
        request.l2_only or bool(aos_l2_cfg.get("l2_only", False))
    )
    requested_l2_confirm_raw = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    requested_l2_only = requested_l2_only_raw
    requested_l2_confirm = requested_l2_confirm_raw
    l2_guard_reason = _prewarm_l2_guard_reason(
        prewarm_scope=prewarm_scope,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        range_start=range_start,
        range_end=range_end,
    )
    if l2_guard_reason:
        logger.warning(
            "%s ticker=%s range=%s..%s",
            l2_guard_reason,
            ticker,
            range_start,
            range_end,
        )
        raise HTTPException(400, l2_guard_reason)

    prewarm_cache_key = _build_prewarm_cache_key(
        request=request,
        prewarm_scope=prewarm_scope,
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        aos_applied=aos_applied,
    )
    cached_result = get_prewarm_result(prewarm_cache_key)
    in_progress = _is_prewarm_inflight(prewarm_cache_key)

    response = {
        "success": True,
        "ready": bool(isinstance(cached_result, dict)),
        "in_progress": bool(in_progress),
        "cache_key": prewarm_cache_key,
        "ticker": ticker,
        "prewarm_scope": prewarm_scope,
        "range_start": range_start,
        "range_end": range_end,
        "l2_requested": bool(requested_l2_only_raw or requested_l2_confirm_raw),
        "use_l2": bool(requested_l2_only or requested_l2_confirm),
        "l2_only": requested_l2_only,
        "l2_confirm_enabled": requested_l2_confirm,
        "l2_guard_reason": l2_guard_reason,
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
