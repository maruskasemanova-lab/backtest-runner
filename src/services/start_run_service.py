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


def _resolve_local_aos_applied(
    *,
    ticker: str,
    load_aos_config: Callable[..., Dict[str, Any]],
    get_ticker_positioning_config: Callable[[str], Dict[str, Any]],
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        aos_config = load_aos_config(aos_config_path) if aos_config_path else load_aos_config()
    except TypeError:
        aos_config = load_aos_config()
    except Exception:
        aos_config = {}

    tickers = aos_config.get("tickers", {}) if isinstance(aos_config, dict) else {}
    ticker_cfg = tickers.get(ticker.upper(), {}) if isinstance(tickers, dict) else {}
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    applied: Dict[str, Any] = {
        "trading_hours": ticker_cfg.get("trading_hours"),
        "time_filter_enabled": bool(
            ticker_cfg.get("time_filter_enabled", bool(ticker_cfg.get("trading_hours")))
        ),
        "strategy_selection_mode": (
            str(ticker_cfg.get("strategy_selection_mode", "adaptive_top_n")).strip().lower()
            or "adaptive_top_n"
        ),
    }

    try:
        raw_max_active = int(ticker_cfg.get("max_active_strategies", 3))
    except (TypeError, ValueError):
        raw_max_active = 3
    applied["max_active_strategies"] = max(1, min(20, raw_max_active))

    if isinstance(ticker_cfg.get("l2"), dict):
        applied["l2"] = dict(ticker_cfg.get("l2", {}))
    if isinstance(ticker_cfg.get("adaptive"), dict):
        applied["adaptive"] = dict(ticker_cfg.get("adaptive", {}))
    try:
        applied["adverse_flow_consistency_threshold"] = float(
            ticker_cfg.get("adverse_flow_consistency_threshold", 0.45)
        )
    except (TypeError, ValueError):
        applied["adverse_flow_consistency_threshold"] = 0.45
    try:
        applied["adverse_book_pressure_threshold"] = float(
            ticker_cfg.get("adverse_book_pressure_threshold", 0.15)
        )
    except (TypeError, ValueError):
        applied["adverse_book_pressure_threshold"] = 0.15

    try:
        positioning_cfg = get_ticker_positioning_config(ticker)
    except Exception:
        positioning_cfg = {}
    if isinstance(positioning_cfg, dict) and positioning_cfg:
        applied["positioning"] = dict(positioning_cfg)
    return applied


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
            None if getattr(request, "include_extended_hours", None) is None else bool(request.include_extended_hours)
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
    requested_scope = str(getattr(request, "prewarm_scope", "range") or "range").strip().lower()
    prewarm_scope = requested_scope if requested_scope in {"range", "ticker"} else "range"
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
    if not PROGRESSIVE_LOAD_ENABLED or comparable_mode:
        return None

    day_span = _inclusive_day_span(range_start, range_end)
    min_days = max(1, int(PROGRESSIVE_LOAD_MIN_DAYS))
    if day_span <= min_days:
        return None

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


async def start_run(request: StartRunRequest, deps: StartRunDeps):
    """Start a new backtest run."""
    if not stateful_run_api_supported():
        raise HTTPException(503, stateful_run_api_unsupported_detail())

    start_wall_clock = perf_counter()
    start_timing: Dict[str, Any] = {"phases_ms": {}}

    def _record_phase_ms(phase_name: str, started_at: float) -> None:
        start_timing["phases_ms"][phase_name] = round((perf_counter() - started_at) * 1000.0, 2)

    active_runners = deps.active_runners
    logger = deps.logger
    data_loader = deps.data_loader
    databento_svc = deps.databento_svc
    l2_manager = deps.l2_manager
    get_discovery = deps.get_discovery
    _reset_remote_orchestrator_state_scoped = deps.reset_remote_orchestrator_state_scoped
    _load_remote_checkpoint = deps.load_remote_checkpoint
    _reset_remote_orchestrator_state = deps.reset_remote_orchestrator_state
    _clear_remote_strategy_sessions = deps.clear_remote_strategy_sessions
    _apply_strategy_overrides = deps.apply_strategy_overrides
    _apply_aos_optimizations = deps.apply_aos_optimizations
    _normalize_momentum_diversification_payload = deps.normalize_momentum_diversification_payload
    _apply_global_trailing = deps.apply_global_trailing
    _to_utc_datetime = deps.to_utc_datetime
    _build_l2_feature_map = deps.build_l2_feature_map
    _normalize_l2_feature_map_for_market_day_sessions = deps.normalize_l2_feature_map_for_market_day_sessions
    _attach_l2_features = deps.attach_l2_features
    _configure_session = deps.configure_session
    broadcast = deps.broadcast
    RunConfig = deps.run_config_cls
    SessionRunner = deps.session_runner_cls

    ticker = request.ticker.upper()
    comparable_mode = bool(request.comparable_mode)
    effective_cold_start_each_day = bool(request.cold_start_each_day or comparable_mode)

    # Resolve date range
    range_start, range_end = _resolve_request_range(request)
    full_range_start = str(range_start)
    full_range_end = str(range_end)
    progressive_plan = _resolve_progressive_plan(
        range_start=full_range_start,
        range_end=full_range_end,
        comparable_mode=comparable_mode,
    )
    if progressive_plan:
        load_range_start = str(progressive_plan["initial_start"])
        load_range_end = str(progressive_plan["initial_end"])
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

    # Orchestrator state reset: cold start (full) or warm start (session-only).
    checkpoint_loaded = None
    use_checkpoint = bool(request.checkpoint_path) and not comparable_mode
    requested_reset_scope = _normalize_reset_scope(getattr(request, "orchestrator_reset_scope", None))
    effective_reset_scope = "all"
    phase_started = perf_counter()
    if use_checkpoint:
        # Warm start: reset only per-session state, then load checkpoint
        effective_reset_scope = "session"
        orchestrator_reset = await _reset_remote_orchestrator_state_scoped(
            request.strategy_api_url, scope="session"
        )
        checkpoint_loaded = await _load_remote_checkpoint(
            request.strategy_api_url, request.checkpoint_path
        )
    else:
        # Cold start (default): full reset for deterministic backtests.
        # Optional request override can relax scope for interactive fast starts.
        effective_reset_scope = "all" if comparable_mode else requested_reset_scope
        if effective_reset_scope == "all":
            orchestrator_reset = await _reset_remote_orchestrator_state(request.strategy_api_url)
        else:
            orchestrator_reset = await _reset_remote_orchestrator_state_scoped(
                request.strategy_api_url,
                scope=effective_reset_scope,
            )
        if comparable_mode and request.checkpoint_path:
            logger.info(
                "Comparable mode ignores checkpoint_path and always starts from a cold state."
            )
    _record_phase_ms("reset_orchestrator", phase_started)

    # Defensive cleanup in strategy API for reruns with the same run_id+ticker.
    phase_started = perf_counter()
    await _clear_remote_strategy_sessions(request.strategy_api_url, request.run_id, ticker)
    _record_phase_ms("clear_remote_sessions", phase_started)

    strategy_overrides_applied = bool(request.apply_ticker_overrides_on_start)
    # Apply per-ticker strategy overrides (best-effort) only when explicitly enabled.
    # Frontend-driven runs may disable this so manual FE edits are not overwritten.
    phase_started = perf_counter()
    if strategy_overrides_applied:
        await _apply_strategy_overrides(request.strategy_api_url, ticker)
    _record_phase_ms("apply_strategy_overrides", phase_started)
    # Apply AOS optimizations (time filter, long_only, params)
    # Optional fast-start path: skip remote strategy sync when FE already
    # applied strategy/API config directly.
    apply_aos_optimizations_on_start = bool(
        getattr(request, "apply_aos_optimizations_on_start", True)
    )
    phase_started = perf_counter()
    aos_applied = await _apply_aos_optimizations(
        request.strategy_api_url,
        ticker,
        remote_sync=apply_aos_optimizations_on_start,
        aos_config_path=request.aos_config_path,
    )
    _record_phase_ms("apply_aos_optimizations", phase_started)
    adaptive_profile_runtime = {}
    if isinstance(aos_applied.get("adaptive_profile"), dict):
        raw_runtime = aos_applied["adaptive_profile"].get("runtime_overrides")
        if isinstance(raw_runtime, dict):
            adaptive_profile_runtime = dict(raw_runtime)

    request_momentum_diversification = _normalize_momentum_diversification_payload(
        request.momentum_diversification_override
    )
    profile_momentum_diversification = _normalize_momentum_diversification_payload(
        adaptive_profile_runtime.get("momentum_diversification")
    )
    aos_adaptive_cfg = aos_applied.get("adaptive", {}) if isinstance(aos_applied.get("adaptive"), dict) else {}
    aos_momentum_diversification = _normalize_momentum_diversification_payload(
        aos_adaptive_cfg.get("momentum_diversification")
    )
    if request_momentum_diversification:
        effective_momentum_diversification = request_momentum_diversification
        momentum_diversification_source = "request"
    elif profile_momentum_diversification:
        effective_momentum_diversification = profile_momentum_diversification
        momentum_diversification_source = "adaptive_profile"
    elif aos_momentum_diversification:
        effective_momentum_diversification = aos_momentum_diversification
        momentum_diversification_source = "aos_config"
    else:
        effective_momentum_diversification = None
        momentum_diversification_source = "none"
    momentum_diversification_json = (
        json.dumps(effective_momentum_diversification, separators=(",", ":"))
        if effective_momentum_diversification
        else None
    )
    phase_started = perf_counter()
    execution_cfg = resolve_execution_config(
        request=request,
        aos_applied=aos_applied,
        adaptive_profile_runtime=adaptive_profile_runtime,
    )
    _record_phase_ms("resolve_execution_config", phase_started)
    effective_global_trailing_stop_pct = float(execution_cfg.get("effective_trailing_stop_pct", 0.0) or 0.0)
    if effective_global_trailing_stop_pct <= 0:
        effective_global_trailing_stop_pct = 0.0
    effective_global_exit_rr_ratio = float(
        execution_cfg.get("effective_global_exit_rr_ratio", 0.0) or 0.0
    )
    if effective_global_exit_rr_ratio <= 0:
        effective_global_exit_rr_ratio = 0.0
    effective_global_risk_atr_stop_multiplier = float(
        execution_cfg.get("effective_global_risk_atr_stop_multiplier", 0.0) or 0.0
    )
    if effective_global_risk_atr_stop_multiplier <= 0:
        effective_global_risk_atr_stop_multiplier = 0.0
    effective_global_risk_volume_stop_pct = float(
        execution_cfg.get("effective_global_risk_volume_stop_pct", 0.0) or 0.0
    )
    if effective_global_risk_volume_stop_pct <= 0:
        effective_global_risk_volume_stop_pct = 0.0
    effective_global_risk_min_stop_loss_pct = float(
        execution_cfg.get("effective_global_risk_min_stop_loss_pct", 0.0) or 0.0
    )
    if effective_global_risk_min_stop_loss_pct <= 0:
        effective_global_risk_min_stop_loss_pct = 0.0

    # Apply global trailing baseline (best-effort). Strategies in `global`
    # mode will consume it; `custom` strategies keep their own values.
    phase_started = perf_counter()
    await _apply_global_trailing(
        request.strategy_api_url,
        effective_global_trailing_stop_pct if effective_global_trailing_stop_pct > 0 else None,
        global_exit_rr_ratio=(
            effective_global_exit_rr_ratio if effective_global_exit_rr_ratio > 0 else None
        ),
        global_risk_atr_stop_multiplier=(
            effective_global_risk_atr_stop_multiplier
            if effective_global_risk_atr_stop_multiplier > 0
            else None
        ),
        global_risk_volume_stop_pct=(
            effective_global_risk_volume_stop_pct if effective_global_risk_volume_stop_pct > 0 else None
        ),
        global_risk_min_stop_loss_pct=(
            effective_global_risk_min_stop_loss_pct if effective_global_risk_min_stop_loss_pct > 0 else None
        ),
    )
    _record_phase_ms("apply_global_trailing", phase_started)

    phase_started = perf_counter()
    bars, data_files = load_run_bars(
        request=request,
        ticker=ticker,
        range_start=load_range_start,
        range_end=load_range_end,
        data_loader=data_loader,
        databento_svc=databento_svc,
        get_discovery=get_discovery,
        aos_applied=aos_applied,
        logger=logger,
    )
    _record_phase_ms("load_run_bars", phase_started)

    requested_l2_only_raw = bool(execution_cfg["requested_l2_only"])
    requested_l2_confirm_raw = bool(execution_cfg["requested_l2_confirm"])
    requested_l2_only = requested_l2_only_raw
    requested_l2_confirm = requested_l2_confirm_raw
    l2_guard_reason = None
    if not RUN_L2_FORCE and bool(requested_l2_only or requested_l2_confirm):
        day_span = _inclusive_day_span(range_start, range_end)
        if RUN_L2_MAX_DAYS > 0 and day_span > RUN_L2_MAX_DAYS:
            requested_l2_only = False
            requested_l2_confirm = False
            l2_guard_reason = (
                "L2 disabled for this run because requested range "
                f"covers {day_span} days (> {RUN_L2_MAX_DAYS})."
            )
            logger.warning(
                "%s run_id=%s ticker=%s range=%s..%s",
                l2_guard_reason,
                request.run_id,
                ticker,
                range_start,
                range_end,
            )
    use_l2 = bool(requested_l2_only or requested_l2_confirm)

    phase_started = perf_counter()
    bars, l2_stats, l2_sessionized_by_market_day = enrich_bars_with_l2(
        bars=bars,
        ticker=ticker,
        range_start=load_range_start,
        range_end=load_range_end,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        comparable_mode=comparable_mode,
        is_multi_day_request=bool(
            load_range_start != load_range_end or bool(request.date_from and request.date_to)
        ),
        aos_l2_config_applied=bool(isinstance(aos_applied.get("l2"), dict) and aos_applied.get("l2")),
        to_utc_datetime=_to_utc_datetime,
        build_l2_feature_map=_build_l2_feature_map,
        normalize_l2_feature_map_for_market_day_sessions=_normalize_l2_feature_map_for_market_day_sessions,
        attach_l2_features=_attach_l2_features,
        logger=logger,
    )
    _record_phase_ms("enrich_bars_with_l2", phase_started)

    l2_min_delta = float(execution_cfg["l2_min_delta"])
    l2_min_imbalance = float(execution_cfg["l2_min_imbalance"])
    l2_min_iceberg_bias = float(execution_cfg["l2_min_iceberg_bias"])
    l2_lookback_bars = int(execution_cfg["l2_lookback_bars"])
    l2_min_participation_ratio = float(execution_cfg["l2_min_participation_ratio"])
    l2_min_directional_consistency = float(execution_cfg["l2_min_directional_consistency"])
    l2_min_signed_aggression = float(execution_cfg["l2_min_signed_aggression"])
    effective_strategy_selection_mode = str(execution_cfg["effective_strategy_selection_mode"])
    effective_max_active_strategies = int(execution_cfg["effective_max_active_strategies"])
    positioning_cfg_requested = bool(execution_cfg["positioning_cfg_requested"])
    positioning_cfg = dict(execution_cfg["positioning_cfg"])
    effective_risk_per_trade_pct = float(execution_cfg["effective_risk_per_trade_pct"])
    risk_per_trade_source = str(execution_cfg["risk_per_trade_source"])
    effective_max_position_notional_pct = float(execution_cfg["effective_max_position_notional_pct"])
    max_position_notional_source = str(execution_cfg["max_position_notional_source"])
    effective_max_fill_participation_rate = float(execution_cfg["effective_max_fill_participation_rate"])
    max_fill_participation_source = str(execution_cfg["max_fill_participation_source"])
    effective_min_fill_ratio = float(execution_cfg["effective_min_fill_ratio"])
    min_fill_ratio_source = str(execution_cfg["min_fill_ratio_source"])
    effective_enable_partial_take_profit = bool(execution_cfg["effective_enable_partial_take_profit"])
    partial_take_profit_enabled_source = str(execution_cfg["partial_take_profit_enabled_source"])
    effective_partial_take_profit_rr = float(execution_cfg["effective_partial_take_profit_rr"])
    partial_take_profit_rr_source = str(execution_cfg["partial_take_profit_rr_source"])
    effective_partial_take_profit_fraction = float(execution_cfg["effective_partial_take_profit_fraction"])
    partial_take_profit_fraction_source = str(execution_cfg["partial_take_profit_fraction_source"])
    effective_global_trailing_stop_pct = float(execution_cfg["effective_trailing_stop_pct"])
    trailing_stop_pct_source = str(execution_cfg["trailing_stop_pct_source"])
    effective_global_exit_rr_ratio = float(execution_cfg["effective_global_exit_rr_ratio"])
    global_exit_rr_ratio_source = str(execution_cfg["global_exit_rr_ratio_source"])
    effective_global_risk_atr_stop_multiplier = float(
        execution_cfg["effective_global_risk_atr_stop_multiplier"]
    )
    global_risk_atr_stop_multiplier_source = str(
        execution_cfg["global_risk_atr_stop_multiplier_source"]
    )
    effective_global_risk_volume_stop_pct = float(
        execution_cfg["effective_global_risk_volume_stop_pct"]
    )
    global_risk_volume_stop_pct_source = str(execution_cfg["global_risk_volume_stop_pct_source"])
    effective_global_risk_min_stop_loss_pct = float(
        execution_cfg["effective_global_risk_min_stop_loss_pct"]
    )
    global_risk_min_stop_loss_pct_source = str(
        execution_cfg["global_risk_min_stop_loss_pct_source"]
    )
    effective_trailing_activation_pct = float(execution_cfg["effective_trailing_activation_pct"])
    trailing_activation_source = str(execution_cfg["trailing_activation_source"])
    effective_break_even_buffer_pct = float(execution_cfg["effective_break_even_buffer_pct"])
    break_even_buffer_source = str(execution_cfg["break_even_buffer_source"])
    effective_break_even_min_hold_bars = int(execution_cfg["effective_break_even_min_hold_bars"])
    break_even_min_hold_source = str(execution_cfg["break_even_min_hold_source"])
    effective_trailing_enabled_in_choppy = bool(execution_cfg["effective_trailing_enabled_in_choppy"])
    trailing_enabled_in_choppy_source = str(execution_cfg["trailing_enabled_in_choppy_source"])
    effective_time_exit_bars = int(execution_cfg["effective_time_exit_bars"])
    time_exit_source = str(execution_cfg["time_exit_source"])
    effective_adverse_flow_exit_enabled = bool(execution_cfg["effective_adverse_flow_exit_enabled"])
    adverse_flow_exit_enabled_source = str(execution_cfg["adverse_flow_exit_enabled_source"])
    effective_adverse_flow_threshold = float(execution_cfg["effective_adverse_flow_threshold"])
    adverse_flow_threshold_source = str(execution_cfg["adverse_flow_threshold_source"])
    effective_adverse_flow_min_hold_bars = int(execution_cfg["effective_adverse_flow_min_hold_bars"])
    adverse_flow_min_hold_source = str(execution_cfg["adverse_flow_min_hold_source"])
    effective_stop_loss_mode = str(execution_cfg["effective_stop_loss_mode"])
    stop_loss_mode_source = str(execution_cfg["stop_loss_mode_source"])
    effective_fixed_stop_loss_pct = float(execution_cfg["effective_fixed_stop_loss_pct"])
    fixed_stop_loss_source = str(execution_cfg["fixed_stop_loss_source"])
    effective_adverse_flow_consistency_threshold = float(
        execution_cfg["effective_adverse_flow_consistency_threshold"]
    )
    adverse_flow_consistency_source = str(execution_cfg["adverse_flow_consistency_source"])
    effective_adverse_book_pressure_threshold = float(
        execution_cfg["effective_adverse_book_pressure_threshold"]
    )
    adverse_book_pressure_source = str(execution_cfg["adverse_book_pressure_source"])
    effective_max_daily_trades = execution_cfg.get("effective_max_daily_trades")
    max_daily_trades_source = str(execution_cfg.get("max_daily_trades_source", "ticker_config"))
    effective_mu_choppy_hard_block_enabled = execution_cfg.get(
        "effective_mu_choppy_hard_block_enabled"
    )
    mu_choppy_hard_block_enabled_source = str(
        execution_cfg.get("mu_choppy_hard_block_enabled_source", "ticker_config")
    )
    
    # Configure session defaults after strategy/AOS updates and after
    # we know whether L2 confirmation is actually feasible for this run.
    effective_l2_confirm = bool(requested_l2_confirm and l2_stats.get("has_l2"))
    effective_intrabar_execution_recalc_1s = (
        bool(request.intrabar_execution_recalc_1s)
        if request.intrabar_execution_recalc_1s is not None
        else bool(use_l2 and l2_stats.get("has_l2"))
    )
    session_config_snapshot = dict(execution_cfg.get("trading_config", {}))
    session_config_snapshot["l2_confirm_enabled"] = effective_l2_confirm
    session_config_snapshot["cold_start_each_day"] = effective_cold_start_each_day
    session_config_snapshot["strategy_selection_mode"] = effective_strategy_selection_mode
    session_config_snapshot["max_active_strategies"] = effective_max_active_strategies
    session_config_snapshot["momentum_diversification_json"] = momentum_diversification_json

    phase_started = perf_counter()
    await _configure_session(
        request.strategy_api_url,
        request.run_id,
        ticker,
        range_start,
        **session_config_snapshot,
    )
    _record_phase_ms("configure_session", phase_started)

    if not bars:
        raise HTTPException(400, "No data available for the specified date/range")

    phase_started = perf_counter()
    ref_bars_map = load_reference_bars_map(
        ticker=ticker,
        range_start=load_range_start,
        range_end=load_range_end,
        data_loader=data_loader,
        databento_svc=databento_svc,
        get_discovery=get_discovery,
        logger=logger,
    )
    _record_phase_ms("load_reference_bars", phase_started)

    # Create runner
    phase_started = perf_counter()
    config = RunConfig(
        run_id=request.run_id,
        ticker=ticker,
        date=run_date_label,
        date_from=range_start,
        date_to=range_end,
        strategy_api_url=request.strategy_api_url,
        account_size_usd=request.account_size_usd,
        regime_detection_minutes=request.regime_detection_minutes,
        intrabar_execution_recalc_1s=effective_intrabar_execution_recalc_1s,
    )

    runner = SessionRunner(config)
    runner.ref_bars_map = ref_bars_map
    if effective_intrabar_execution_recalc_1s:
        runner.l2_manager = l2_manager
    runner.load_bars(bars)
    
    # Register callbacks for broadcasting
    async def on_bar(bar):
        await broadcast({
            "type": "bar",
            "run_key": run_key,
            "run_id": request.run_id,
            "ticker": ticker,
            "date": run_date_label,
            "bar": bar
        })
    
    async def on_decision(marker):
        await broadcast({
            "type": "decision",
            "run_key": run_key,
            "run_id": request.run_id,
            "ticker": ticker,
            "date": run_date_label,
            "marker": marker
        })
    
    runner.on_bar(on_bar)
    runner.on_decision(on_decision)
    
    # Store checkpoint auto-save metadata on runner for use after run_all
    runner._checkpoint_auto_save = bool(request.auto_save_checkpoint and not comparable_mode)
    runner._checkpoint_strategy_url = request.strategy_api_url
    runner._checkpoint_loaded = checkpoint_loaded
    runner._restart_session_date = range_start
    runner._restart_session_config = dict(session_config_snapshot)
    runner._progressive_loading_enabled = bool(progressive_plan)
    runner._progressive_loading_complete = not bool(progressive_plan)
    runner._progressive_loading_loaded_until = load_range_end if bars else None
    runner._progressive_loading_target_end = full_range_end
    runner._progressive_loading_pending_chunks = (
        len(progressive_plan.get("chunks", [])) if isinstance(progressive_plan, dict) else 0
    )
    runner._progressive_loading_last_error = None
    runner._progressive_loading_task = None
    runner._progressive_wait_timeout_seconds = 90
    runner._progressive_wait_started_at = None

    active_runners[run_key] = runner

    if isinstance(progressive_plan, dict):
        pending_chunks = list(progressive_plan.get("chunks", []))

        def _load_chunk_payload(chunk_start: str, chunk_end: str):
            chunk_bars, _chunk_data_files = load_run_bars(
                request=request,
                ticker=ticker,
                range_start=chunk_start,
                range_end=chunk_end,
                data_loader=data_loader,
                databento_svc=databento_svc,
                get_discovery=get_discovery,
                aos_applied=aos_applied,
                logger=logger,
            )
            chunk_bars, _chunk_l2_stats, _chunk_l2_sessionized = enrich_bars_with_l2(
                bars=chunk_bars,
                ticker=ticker,
                range_start=chunk_start,
                range_end=chunk_end,
                requested_l2_only=requested_l2_only,
                requested_l2_confirm=requested_l2_confirm,
                comparable_mode=comparable_mode,
                is_multi_day_request=bool(chunk_start != chunk_end),
                aos_l2_config_applied=bool(
                    isinstance(aos_applied.get("l2"), dict) and aos_applied.get("l2")
                ),
                to_utc_datetime=_to_utc_datetime,
                build_l2_feature_map=_build_l2_feature_map,
                normalize_l2_feature_map_for_market_day_sessions=_normalize_l2_feature_map_for_market_day_sessions,
                attach_l2_features=_attach_l2_features,
                logger=logger,
            )
            chunk_ref_map = load_reference_bars_map(
                ticker=ticker,
                range_start=chunk_start,
                range_end=chunk_end,
                data_loader=data_loader,
                databento_svc=databento_svc,
                get_discovery=get_discovery,
                logger=logger,
            )
            return chunk_bars, chunk_ref_map

        async def _append_remaining_chunks() -> None:
            logger.info(
                "Progressive loading enabled for %s: initial=%s..%s, pending_chunks=%d, target=%s..%s",
                run_key,
                load_range_start,
                load_range_end,
                len(pending_chunks),
                full_range_start,
                full_range_end,
            )
            try:
                for idx, (chunk_start, chunk_end) in enumerate(pending_chunks, start=1):
                    if active_runners.get(run_key) is not runner:
                        logger.info(
                            "Progressive loading aborted for %s (runner no longer active).",
                            run_key,
                        )
                        break

                    chunk_bars, chunk_ref_map = await asyncio.to_thread(
                        _load_chunk_payload,
                        chunk_start,
                        chunk_end,
                    )

                    last_loaded_ts = None
                    if runner.bars:
                        try:
                            last_loaded_ts = _to_utc_datetime(runner.bars[-1].get("timestamp"))
                        except Exception:
                            last_loaded_ts = None

                    appended_bars = []
                    for bar_item in chunk_bars:
                        if last_loaded_ts is not None:
                            try:
                                bar_ts = _to_utc_datetime(bar_item.get("timestamp"))
                                if bar_ts <= last_loaded_ts:
                                    continue
                            except Exception:
                                pass
                        appended_bars.append(bar_item)

                    if appended_bars:
                        runner.bars.extend(appended_bars)
                    if isinstance(chunk_ref_map, dict) and chunk_ref_map:
                        runner.ref_bars_map.update(chunk_ref_map)

                    runner._progressive_loading_loaded_until = chunk_end
                    runner._progressive_loading_pending_chunks = max(
                        0, len(pending_chunks) - idx
                    )

                    logger.info(
                        "Progressive chunk loaded for %s: %s..%s (+%d bars, total=%d, pending=%d)",
                        run_key,
                        chunk_start,
                        chunk_end,
                        len(appended_bars),
                        len(runner.bars),
                        int(runner._progressive_loading_pending_chunks),
                    )
                    await broadcast(
                        {
                            "type": "run_data_extended",
                            "run_key": run_key,
                            "run_id": request.run_id,
                            "ticker": ticker,
                            "date": run_date_label,
                            "chunk_start": chunk_start,
                            "chunk_end": chunk_end,
                            "added_bars": len(appended_bars),
                            "total_bars": len(runner.bars),
                            "pending_chunks": int(runner._progressive_loading_pending_chunks),
                        }
                    )
            except Exception as exc:
                runner._progressive_loading_last_error = str(exc)
                logger.exception("Progressive loading failed for %s", run_key)
            finally:
                runner._progressive_loading_complete = True
                runner._progressive_loading_pending_chunks = 0
                if not runner._progressive_loading_last_error:
                    runner._progressive_loading_loaded_until = full_range_end
                logger.info(
                    "Progressive loading finished for %s (error=%s)",
                    run_key,
                    runner._progressive_loading_last_error,
                )

        runner._progressive_loading_task = asyncio.create_task(_append_remaining_chunks())

    _record_phase_ms("runner_setup", phase_started)

    start_timing["total_ms"] = round((perf_counter() - start_wall_clock) * 1000.0, 2)
    phases_ms = start_timing.get("phases_ms", {})
    if phases_ms:
        slowest_phase, slowest_phase_ms = max(phases_ms.items(), key=lambda item: float(item[1]))
        start_timing["slowest_phase"] = str(slowest_phase)
        start_timing["slowest_phase_ms"] = float(slowest_phase_ms)
    start_timing["context"] = {
        "ticker": ticker,
        "range_start": full_range_start,
        "range_end": full_range_end,
        "initial_loaded_range_start": load_range_start,
        "initial_loaded_range_end": load_range_end,
        "bars_loaded": len(bars),
        "reference_bars_loaded": len(ref_bars_map),
        "orchestrator_reset_scope": effective_reset_scope,
        "apply_aos_optimizations_on_start": apply_aos_optimizations_on_start,
        "use_l2": bool(use_l2),
        "l2_has_data": bool(l2_stats.get("has_l2")),
        "progressive_loading_enabled": bool(progressive_plan),
        "progressive_pending_chunks": (
            len(progressive_plan.get("chunks", [])) if isinstance(progressive_plan, dict) else 0
        ),
    }

    execution_config_payload = {
        "account_size_usd": request.account_size_usd,
        "positioning_config_enabled": positioning_cfg_requested,
        "positioning_config_applied": bool(positioning_cfg),
        "risk_per_trade_pct": effective_risk_per_trade_pct,
        "risk_per_trade_pct_source": risk_per_trade_source,
        "max_position_notional_pct": effective_max_position_notional_pct,
        "max_position_notional_pct_source": max_position_notional_source,
        "max_fill_participation_rate": effective_max_fill_participation_rate,
        "max_fill_participation_rate_source": max_fill_participation_source,
        "min_fill_ratio": effective_min_fill_ratio,
        "min_fill_ratio_source": min_fill_ratio_source,
        "enable_partial_take_profit": effective_enable_partial_take_profit,
        "enable_partial_take_profit_source": partial_take_profit_enabled_source,
        "partial_take_profit_rr": effective_partial_take_profit_rr,
        "partial_take_profit_rr_source": partial_take_profit_rr_source,
        "partial_take_profit_fraction": effective_partial_take_profit_fraction,
        "partial_take_profit_fraction_source": partial_take_profit_fraction_source,
        "trailing_stop_pct": effective_global_trailing_stop_pct,
        "trailing_stop_pct_source": trailing_stop_pct_source,
        "global_exit_rr_ratio": effective_global_exit_rr_ratio,
        "global_exit_rr_ratio_source": global_exit_rr_ratio_source,
        "global_risk_atr_stop_multiplier": effective_global_risk_atr_stop_multiplier,
        "global_risk_atr_stop_multiplier_source": global_risk_atr_stop_multiplier_source,
        "global_risk_volume_stop_pct": effective_global_risk_volume_stop_pct,
        "global_risk_volume_stop_pct_source": global_risk_volume_stop_pct_source,
        "global_risk_min_stop_loss_pct": effective_global_risk_min_stop_loss_pct,
        "global_risk_min_stop_loss_pct_source": global_risk_min_stop_loss_pct_source,
        "trailing_activation_pct": effective_trailing_activation_pct,
        "trailing_activation_pct_source": trailing_activation_source,
        "break_even_buffer_pct": effective_break_even_buffer_pct,
        "break_even_buffer_pct_source": break_even_buffer_source,
        "break_even_min_hold_bars": effective_break_even_min_hold_bars,
        "break_even_min_hold_bars_source": break_even_min_hold_source,
        "trailing_enabled_in_choppy": effective_trailing_enabled_in_choppy,
        "trailing_enabled_in_choppy_source": trailing_enabled_in_choppy_source,
        "time_exit_bars": effective_time_exit_bars,
        "time_exit_bars_source": time_exit_source,
        "adverse_flow_exit_enabled": effective_adverse_flow_exit_enabled,
        "adverse_flow_exit_enabled_source": adverse_flow_exit_enabled_source,
        "adverse_flow_threshold": effective_adverse_flow_threshold,
        "adverse_flow_threshold_source": adverse_flow_threshold_source,
        "adverse_flow_min_hold_bars": effective_adverse_flow_min_hold_bars,
        "adverse_flow_min_hold_bars_source": adverse_flow_min_hold_source,
        "adverse_flow_consistency_threshold": effective_adverse_flow_consistency_threshold,
        "adverse_flow_consistency_threshold_source": adverse_flow_consistency_source,
        "adverse_book_pressure_threshold": effective_adverse_book_pressure_threshold,
        "adverse_book_pressure_threshold_source": adverse_book_pressure_source,
        "stop_loss_mode": effective_stop_loss_mode,
        "stop_loss_mode_source": stop_loss_mode_source,
        "fixed_stop_loss_pct": effective_fixed_stop_loss_pct,
        "fixed_stop_loss_pct_source": fixed_stop_loss_source,
        "intrabar_execution_recalc_1s": effective_intrabar_execution_recalc_1s,
        "cold_start_each_day": effective_cold_start_each_day,
        "comparable_mode": comparable_mode,
        "orchestrator_reset_scope": effective_reset_scope,
        "apply_aos_optimizations_on_start": apply_aos_optimizations_on_start,
        "strategy_selection_mode": effective_strategy_selection_mode,
        "max_active_strategies": effective_max_active_strategies,
        "include_extended_hours": (
            bool(request.include_extended_hours)
            if request.include_extended_hours is not None
            else not bool(
                aos_applied.get("time_filter_enabled")
                and _canonical_trading_hours(aos_applied.get("trading_hours"))
            )
        ),
        "momentum_diversification_applied": bool(effective_momentum_diversification),
        "momentum_diversification_source": momentum_diversification_source,
        "momentum_diversification": effective_momentum_diversification or {},
    }
    if effective_max_daily_trades is not None:
        execution_config_payload["max_daily_trades"] = int(effective_max_daily_trades)
        execution_config_payload["max_daily_trades_source"] = max_daily_trades_source
    if effective_mu_choppy_hard_block_enabled is not None:
        execution_config_payload["mu_choppy_hard_block_enabled"] = bool(
            effective_mu_choppy_hard_block_enabled
        )
        execution_config_payload["mu_choppy_hard_block_enabled_source"] = (
            mu_choppy_hard_block_enabled_source
        )
    effective_profile_meta = _extract_effective_profile_metadata(
        aos_applied=aos_applied,
        execution_config=execution_config_payload,
    )
    unified_profile_id = effective_profile_meta.get("unified_profile_id")
    adaptive_profile_id = effective_profile_meta.get("adaptive_profile_id")
    strategy_combo_profile_id = effective_profile_meta.get("strategy_combo_profile_id")
    if unified_profile_id:
        execution_config_payload["unified_profile_id"] = unified_profile_id
        execution_config_payload["active_unified_profile_id"] = unified_profile_id
    unified_profile_name = effective_profile_meta.get("unified_profile_name")
    if unified_profile_name:
        execution_config_payload["unified_profile_name"] = unified_profile_name
    if adaptive_profile_id:
        execution_config_payload["adaptive_profile_id"] = adaptive_profile_id
        execution_config_payload["active_adaptive_tuner_profile_id"] = adaptive_profile_id
    adaptive_profile_name = effective_profile_meta.get("adaptive_profile_name")
    if adaptive_profile_name:
        execution_config_payload["adaptive_profile_name"] = adaptive_profile_name
    if strategy_combo_profile_id:
        execution_config_payload["strategy_combo_profile_id"] = strategy_combo_profile_id
        execution_config_payload["active_strategy_combo_profile_id"] = strategy_combo_profile_id
    strategy_combo_profile_name = effective_profile_meta.get("strategy_combo_profile_name")
    if strategy_combo_profile_name:
        execution_config_payload["strategy_combo_profile_name"] = strategy_combo_profile_name
    runner._aos_applied = dict(aos_applied) if isinstance(aos_applied, dict) else {}
    runner._execution_config = dict(execution_config_payload)
    runner._report_metadata = _build_report_metadata(
        run_key=run_key,
        run_date_label=run_date_label,
        aos_applied=runner._aos_applied,
        execution_config=runner._execution_config,
    )

    logger.info(f"Started run {run_key} with {len(bars)} bars")

    return {
        "success": True,
        "run_key": run_key,
        "ticker": ticker,
        "total_bars": len(bars),
        "requested_range": {
            "date_from": full_range_start,
            "date_to": full_range_end,
        },
        "progressive_loading": {
            "enabled": bool(progressive_plan),
            "initial_range_start": load_range_start,
            "initial_range_end": load_range_end,
            "loaded_until": getattr(runner, "_progressive_loading_loaded_until", load_range_end),
            "target_end": full_range_end,
            "pending_chunks": int(getattr(runner, "_progressive_loading_pending_chunks", 0)),
            "complete": bool(getattr(runner, "_progressive_loading_complete", True)),
            "last_error": getattr(runner, "_progressive_loading_last_error", None),
        },
        "strategy_state_reset": orchestrator_reset,
        "orchestrator_reset_scope": effective_reset_scope,
        "checkpoint_loaded": checkpoint_loaded,
        "strategy_overrides_applied": strategy_overrides_applied,
        "data_files": data_files,
        "aos_applied": aos_applied,
        "l2_applied": {
            **l2_stats,
            "l2_requested": bool(requested_l2_only_raw or requested_l2_confirm_raw),
            "l2_guard_reason": l2_guard_reason,
            "effective_l2_confirm_enabled": effective_l2_confirm,
            "l2_min_delta": l2_min_delta,
            "l2_min_imbalance": l2_min_imbalance,
            "l2_min_iceberg_bias": l2_min_iceberg_bias,
            "l2_lookback_bars": l2_lookback_bars,
            "l2_min_participation_ratio": l2_min_participation_ratio,
            "l2_min_directional_consistency": l2_min_directional_consistency,
            "l2_min_signed_aggression": l2_min_signed_aggression,
            "sessionized_by_market_day": l2_sessionized_by_market_day,
        },
        "execution_config": execution_config_payload,
        "start_timing": start_timing,
        "first_bar": bars[0] if bars else None,
        "last_bar": bars[-1] if bars else None
    }


async def prewarm_run_data(request: PrewarmRunRequest, deps: StartRunDeps) -> Dict[str, Any]:
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

    aos_applied = _resolve_local_aos_applied(
        ticker=ticker,
        load_aos_config=deps.load_aos_config,
        get_ticker_positioning_config=deps.get_ticker_positioning_config,
        aos_config_path=getattr(request, "aos_config_path", None),
    )

    aos_l2_cfg = aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}
    requested_l2_only_raw = bool(request.l2_only or bool(aos_l2_cfg.get("l2_only", False)))
    requested_l2_confirm_raw = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    requested_l2_only = requested_l2_only_raw
    requested_l2_confirm = requested_l2_confirm_raw
    l2_guard_reason = None
    if bool(requested_l2_only or requested_l2_confirm):
        day_span = _inclusive_day_span(range_start, range_end)
        if prewarm_scope == "ticker":
            if (
                not PREWARM_TICKER_SCOPE_L2_FORCE
                and PREWARM_TICKER_SCOPE_L2_MAX_DAYS > 0
                and day_span > PREWARM_TICKER_SCOPE_L2_MAX_DAYS
            ):
                requested_l2_only = False
                requested_l2_confirm = False
                l2_guard_reason = (
                    "L2 prewarm skipped for ticker scope because requested range "
                    f"covers {day_span} days (> {PREWARM_TICKER_SCOPE_L2_MAX_DAYS})."
                )
        else:
            # Keep range-scope prewarm aligned with run-start L2 guard to avoid
            # large memory spikes when FE selects long date ranges with L2 enabled.
            if (
                not RUN_L2_FORCE
                and RUN_L2_MAX_DAYS > 0
                and day_span > RUN_L2_MAX_DAYS
            ):
                requested_l2_only = False
                requested_l2_confirm = False
                l2_guard_reason = (
                    "L2 prewarm skipped for range scope because requested range "
                    f"covers {day_span} days (> {RUN_L2_MAX_DAYS})."
                )
        if l2_guard_reason:
            logger.warning(
                "%s ticker=%s range=%s..%s",
                l2_guard_reason,
                ticker,
                range_start,
                range_end,
            )

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
            aos_l2_config_applied=bool(isinstance(aos_applied.get("l2"), dict) and aos_applied.get("l2")),
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


async def get_prewarm_status(request: PrewarmRunRequest, deps: StartRunDeps) -> Dict[str, Any]:
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
    aos_applied = _resolve_local_aos_applied(
        ticker=ticker,
        load_aos_config=deps.load_aos_config,
        get_ticker_positioning_config=deps.get_ticker_positioning_config,
        aos_config_path=getattr(request, "aos_config_path", None),
    )
    aos_l2_cfg = aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}
    requested_l2_only_raw = bool(request.l2_only or bool(aos_l2_cfg.get("l2_only", False)))
    requested_l2_confirm_raw = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    requested_l2_only = requested_l2_only_raw
    requested_l2_confirm = requested_l2_confirm_raw
    l2_guard_reason = None
    if bool(requested_l2_only or requested_l2_confirm):
        day_span = _inclusive_day_span(range_start, range_end)
        if prewarm_scope == "ticker":
            if (
                not PREWARM_TICKER_SCOPE_L2_FORCE
                and PREWARM_TICKER_SCOPE_L2_MAX_DAYS > 0
                and day_span > PREWARM_TICKER_SCOPE_L2_MAX_DAYS
            ):
                requested_l2_only = False
                requested_l2_confirm = False
                l2_guard_reason = (
                    "L2 prewarm skipped for ticker scope because requested range "
                    f"covers {day_span} days (> {PREWARM_TICKER_SCOPE_L2_MAX_DAYS})."
                )
        else:
            if (
                not RUN_L2_FORCE
                and RUN_L2_MAX_DAYS > 0
                and day_span > RUN_L2_MAX_DAYS
            ):
                requested_l2_only = False
                requested_l2_confirm = False
                l2_guard_reason = (
                    "L2 prewarm skipped for range scope because requested range "
                    f"covers {day_span} days (> {RUN_L2_MAX_DAYS})."
                )
        if l2_guard_reason:
            logger.warning(
                "%s ticker=%s range=%s..%s",
                l2_guard_reason,
                ticker,
                range_start,
                range_end,
            )

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
