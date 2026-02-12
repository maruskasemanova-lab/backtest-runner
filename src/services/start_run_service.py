from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

import pandas as pd
from fastapi import HTTPException

from src.models.run_requests import StartRunRequest


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
    configure_session: Callable[..., Awaitable[Any]]
    broadcast: Callable[[Dict[str, Any]], Awaitable[None]]
    run_config_cls: Any
    session_runner_cls: Any


async def start_run(request: StartRunRequest, deps: StartRunDeps):
    """Start a new backtest run."""
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
    if request.date_from and request.date_to:
        range_start = request.date_from
        range_end = request.date_to
    elif request.date:
        range_start = request.date
        range_end = request.date
    else:
        raise HTTPException(400, "Either date or date_from/date_to must be provided")

    run_date_label = (
        f"{range_start}_to_{range_end}"
        if range_start != range_end or request.date_from or request.date_to
        else range_start
    )

    run_key = f"{request.run_id}:{ticker}:{run_date_label}"
    
    if run_key in active_runners:
        raise HTTPException(400, f"Run already exists: {run_key}")

    # Orchestrator state reset: cold start (full) or warm start (session-only).
    checkpoint_loaded = None
    use_checkpoint = bool(request.checkpoint_path) and not comparable_mode
    if use_checkpoint:
        # Warm start: reset only per-session state, then load checkpoint
        orchestrator_reset = await _reset_remote_orchestrator_state_scoped(
            request.strategy_api_url, scope="session"
        )
        checkpoint_loaded = await _load_remote_checkpoint(
            request.strategy_api_url, request.checkpoint_path
        )
    else:
        # Cold start (default): full reset for deterministic backtests
        orchestrator_reset = await _reset_remote_orchestrator_state(request.strategy_api_url)
        if comparable_mode and request.checkpoint_path:
            logger.info(
                "Comparable mode ignores checkpoint_path and always starts from a cold state."
            )

    # Defensive cleanup in strategy API for reruns with the same run_id+ticker.
    await _clear_remote_strategy_sessions(request.strategy_api_url, request.run_id, ticker)

    strategy_overrides_applied = bool(request.apply_ticker_overrides_on_start)
    # Apply per-ticker strategy overrides (best-effort) only when explicitly enabled.
    # Frontend-driven runs may disable this so manual FE edits are not overwritten.
    if strategy_overrides_applied:
        await _apply_strategy_overrides(request.strategy_api_url, ticker)
    # Apply AOS optimizations (time filter, long_only, params)
    aos_applied = await _apply_aos_optimizations(
        request.strategy_api_url,
        ticker,
        aos_config_path=request.aos_config_path,
    )
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
    # Apply global trailing (best-effort, overrides per-ticker trailing)
    await _apply_global_trailing(request.strategy_api_url, request.trailing_stop_pct)

    # Load data
    data_file = request.data_file
    
    # Auto-discover data file(s) if not provided
    if not data_file:
        # Prefer centralized catalog (Data Manager + runner use the same inventory).
        databento_svc.scan_existing_files()
        data_files = databento_svc.get_files_for_range(
            ticker=ticker,
            start_date=range_start,
            end_date=range_end,
            schema_prefix="ohlcv-",
        )
        if not data_files:
            # Backward-compatible fallback only when centralized catalog has no
            # OHLCV entries for this ticker at all.
            catalog_rows = databento_svc.list_catalog(refresh=False, ticker=ticker)
            has_catalog_ohlcv = any(
                str(row.get("schema", "")).lower().startswith("ohlcv-")
                and row.get("status") == "ready"
                for row in catalog_rows
            )
            if not has_catalog_ohlcv:
                discovery = get_discovery()
                data_files = discovery.get_files_for_range(ticker, range_start, range_end)
    else:
        data_files = [data_file]

    if data_files:
        dfs = []
        skipped_files = []
        for file in data_files:
            try:
                if file.endswith('.parquet') or file.endswith('.parq'):
                    dfs.append(data_loader.load_parquet(file))
                else:
                    dfs.append(data_loader.load_csv(file))
            except FileNotFoundError as e:
                raise HTTPException(404, str(e))
            except Exception as e:
                logger.warning(f"Skipping invalid data file {file}: {e}")
                skipped_files.append(file)
                continue

        if not dfs:
            skipped_note = f" Skipped files: {', '.join(skipped_files)}" if skipped_files else ""
            raise HTTPException(400, f"No usable data files for the specified date/range.{skipped_note}")

        df = pd.concat(dfs, ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df = data_loader.filter_trading_range(df, range_start, range_end)
        if aos_applied.get("time_filter_enabled") and aos_applied.get("trading_hours"):
            df = data_loader.filter_trading_hours(df, aos_applied.get("trading_hours"))
    else:
        if not request.allow_mock_data:
            raise HTTPException(
                404,
                f"No data files found for {ticker} in range {range_start} to {range_end}. "
                "Backtest aborted to avoid mock-data contamination."
            )
        logger.warning(
            f"No data file found for {ticker} in range {range_start} to {range_end}, using mock data (allow_mock_data=True)"
        )
        df = data_loader.generate_mock_data(ticker=ticker, date=range_start)
    
    # Convert to list of bar dicts
    bars = list(data_loader.get_bars_iterator(df))
    
    if not bars:
        raise HTTPException(400, "No data available for the specified date/range")

    aos_l2_cfg = aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}

    def _pick_l2_float(request_value: Any, cfg_key: str, profile_key: str) -> float:
        try:
            profile_value = float(adaptive_profile_runtime.get(profile_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            profile_value = 0.0
        if abs(profile_value) > 1e-12:
            return profile_value
        try:
            req = float(request_value)
        except (TypeError, ValueError):
            req = 0.0
        if abs(req) > 1e-12:
            return req
        try:
            return float(aos_l2_cfg.get(cfg_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    requested_l2_only = bool(request.l2_only or bool(aos_l2_cfg.get("l2_only", False)))
    requested_l2_confirm = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    l2_min_delta = _pick_l2_float(request.l2_min_delta, "min_delta", "l2_min_delta")
    l2_min_imbalance = _pick_l2_float(request.l2_min_imbalance, "min_imbalance", "l2_min_imbalance")
    l2_min_iceberg_bias = _pick_l2_float(
        request.l2_min_iceberg_bias, "min_iceberg_bias", "l2_min_iceberg_bias"
    )
    l2_min_participation_ratio = _pick_l2_float(
        request.l2_min_participation_ratio, "min_participation_ratio", "l2_min_participation_ratio"
    )
    l2_min_directional_consistency = _pick_l2_float(
        request.l2_min_directional_consistency,
        "min_directional_consistency",
        "l2_min_directional_consistency",
    )
    l2_min_signed_aggression = _pick_l2_float(
        request.l2_min_signed_aggression, "min_signed_aggression", "l2_min_signed_aggression"
    )
    profile_strategy_selection_mode = str(
        adaptive_profile_runtime.get("strategy_selection_mode", "")
    ).strip().lower()
    if profile_strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
        profile_strategy_selection_mode = ""
    requested_strategy_selection_mode = str(request.strategy_selection_mode or "").strip().lower()
    if requested_strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
        requested_strategy_selection_mode = ""
    effective_strategy_selection_mode = (
        profile_strategy_selection_mode
        or requested_strategy_selection_mode
        or str(aos_applied.get("strategy_selection_mode", "adaptive_top_n")).strip().lower()
        or "adaptive_top_n"
    )
    try:
        profile_max_active_strategies = int(adaptive_profile_runtime.get("max_active_strategies", 0))
    except (TypeError, ValueError):
        profile_max_active_strategies = 0
    try:
        requested_max_active_strategies = (
            int(request.max_active_strategies) if request.max_active_strategies is not None else 0
        )
    except (TypeError, ValueError):
        requested_max_active_strategies = 0
    try:
        aos_max_active_strategies = int(aos_applied.get("max_active_strategies", 3))
    except (TypeError, ValueError):
        aos_max_active_strategies = 3
    effective_max_active_strategies = (
        profile_max_active_strategies
        or requested_max_active_strategies
        or aos_max_active_strategies
        or 3
    )
    effective_max_active_strategies = max(1, min(20, effective_max_active_strategies))

    positioning_cfg_requested = bool(request.apply_positioning_config_on_start)
    positioning_cfg = (
        dict(aos_applied.get("positioning", {}))
        if positioning_cfg_requested and isinstance(aos_applied.get("positioning"), dict)
        else {}
    )

    def _coerce_bool(value: Any, *, default: Optional[bool] = None) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "no", "n", "off"}:
                return False
        return default

    def _resolve_positioning_float(
        *,
        request_value: Any,
        request_default: float,
        positioning_key: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        runtime_key: Optional[str] = None,
        runtime_positive_only: bool = False,
    ) -> tuple[float, str]:
        source = "request"
        try:
            resolved = float(request_value)
        except (TypeError, ValueError):
            resolved = float(request_default)
            source = "default"

        if abs(resolved - float(request_default)) < 1e-12 and positioning_cfg:
            raw = positioning_cfg.get(positioning_key)
            if raw is not None:
                try:
                    resolved = float(raw)
                    source = "positioning_config"
                except (TypeError, ValueError):
                    pass

        if runtime_key:
            try:
                runtime_value = float(adaptive_profile_runtime.get(runtime_key, 0.0) or 0.0)
            except (TypeError, ValueError):
                runtime_value = 0.0
            runtime_valid = runtime_value > 0 if runtime_positive_only else abs(runtime_value) > 1e-12
            if runtime_valid:
                resolved = runtime_value
                source = "adaptive_profile"

        if min_value is not None:
            resolved = max(min_value, resolved)
        if max_value is not None:
            resolved = min(max_value, resolved)
        return resolved, source

    def _resolve_positioning_int(
        *,
        request_value: Any,
        request_default: int,
        positioning_key: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
        runtime_key: Optional[str] = None,
        runtime_positive_only: bool = False,
    ) -> tuple[int, str]:
        source = "request"
        try:
            resolved = int(request_value)
        except (TypeError, ValueError):
            resolved = int(request_default)
            source = "default"

        if resolved == int(request_default) and positioning_cfg:
            raw = positioning_cfg.get(positioning_key)
            if raw is not None:
                try:
                    resolved = int(raw)
                    source = "positioning_config"
                except (TypeError, ValueError):
                    pass

        if runtime_key:
            try:
                runtime_value = int(adaptive_profile_runtime.get(runtime_key, 0) or 0)
            except (TypeError, ValueError):
                runtime_value = 0
            runtime_valid = runtime_value > 0 if runtime_positive_only else runtime_value != 0
            if runtime_valid:
                resolved = runtime_value
                source = "adaptive_profile"

        if min_value is not None:
            resolved = max(min_value, resolved)
        if max_value is not None:
            resolved = min(max_value, resolved)
        return resolved, source

    def _resolve_positioning_bool(
        *,
        request_value: Any,
        request_default: bool,
        positioning_key: str,
        runtime_key: Optional[str] = None,
    ) -> tuple[bool, str]:
        source = "request"
        resolved = _coerce_bool(request_value, default=request_default)
        if resolved is None:
            resolved = request_default
            source = "default"
        if resolved == bool(request_default) and positioning_cfg and positioning_key in positioning_cfg:
            positioned = _coerce_bool(positioning_cfg.get(positioning_key), default=None)
            if positioned is not None:
                resolved = positioned
                source = "positioning_config"
        if runtime_key:
            runtime_bool = _coerce_bool(adaptive_profile_runtime.get(runtime_key), default=None)
            if runtime_bool is not None:
                resolved = runtime_bool
                source = "adaptive_profile"
        return bool(resolved), source

    def _resolve_stop_loss_mode(
        *,
        request_mode: Any,
        request_default: str = "strategy",
        positioning_key: str = "stop_loss_mode",
    ) -> tuple[str, str]:
        valid_modes = {"strategy", "fixed", "capped"}
        source = "request"
        normalized_default = str(request_default).strip().lower() or "strategy"
        mode = str(request_mode or normalized_default).strip().lower()
        if mode not in valid_modes:
            mode = normalized_default
            source = "default"
        if mode == normalized_default and positioning_cfg:
            positioned_mode = str(positioning_cfg.get(positioning_key, "")).strip().lower()
            if positioned_mode in valid_modes:
                mode = positioned_mode
                source = "positioning_config"
        return mode, source

    effective_risk_per_trade_pct, risk_per_trade_source = _resolve_positioning_float(
        request_value=request.risk_per_trade_pct,
        request_default=1.0,
        positioning_key="risk_per_trade_pct",
        min_value=0.1,
    )
    effective_max_position_notional_pct, max_position_notional_source = _resolve_positioning_float(
        request_value=request.max_position_notional_pct,
        request_default=100.0,
        positioning_key="max_position_notional_pct",
        min_value=1.0,
    )
    effective_max_fill_participation_rate, max_fill_participation_source = _resolve_positioning_float(
        request_value=request.max_fill_participation_rate,
        request_default=0.20,
        positioning_key="max_fill_participation_rate",
        min_value=0.01,
        max_value=1.0,
    )
    effective_min_fill_ratio, min_fill_ratio_source = _resolve_positioning_float(
        request_value=request.min_fill_ratio,
        request_default=0.35,
        positioning_key="min_fill_ratio",
        min_value=0.01,
        max_value=1.0,
    )
    effective_enable_partial_take_profit, partial_take_profit_enabled_source = _resolve_positioning_bool(
        request_value=request.enable_partial_take_profit,
        request_default=True,
        positioning_key="enable_partial_take_profit",
    )
    effective_partial_take_profit_rr, partial_take_profit_rr_source = _resolve_positioning_float(
        request_value=request.partial_take_profit_rr,
        request_default=1.0,
        positioning_key="partial_take_profit_rr",
        min_value=0.25,
    )
    effective_partial_take_profit_fraction, partial_take_profit_fraction_source = _resolve_positioning_float(
        request_value=request.partial_take_profit_fraction,
        request_default=0.5,
        positioning_key="partial_take_profit_fraction",
        min_value=0.05,
        max_value=0.95,
    )
    effective_trailing_activation_pct, trailing_activation_source = _resolve_positioning_float(
        request_value=request.trailing_activation_pct,
        request_default=0.15,
        positioning_key="trailing_activation_pct",
        min_value=0.0,
    )
    effective_break_even_buffer_pct, break_even_buffer_source = _resolve_positioning_float(
        request_value=request.break_even_buffer_pct,
        request_default=0.03,
        positioning_key="break_even_buffer_pct",
        min_value=0.0,
    )
    effective_break_even_min_hold_bars, break_even_min_hold_source = _resolve_positioning_int(
        request_value=request.break_even_min_hold_bars,
        request_default=2,
        positioning_key="break_even_min_hold_bars",
        min_value=1,
    )
    effective_trailing_enabled_in_choppy, trailing_enabled_in_choppy_source = _resolve_positioning_bool(
        request_value=request.trailing_enabled_in_choppy,
        request_default=False,
        positioning_key="trailing_enabled_in_choppy",
    )
    effective_time_exit_bars, time_exit_source = _resolve_positioning_int(
        request_value=request.time_exit_bars,
        request_default=40,
        positioning_key="time_exit_bars",
        min_value=1,
        runtime_key="time_exit_bars",
        runtime_positive_only=True,
    )
    effective_adverse_flow_exit_enabled, adverse_flow_exit_enabled_source = _resolve_positioning_bool(
        request_value=request.adverse_flow_exit_enabled,
        request_default=True,
        positioning_key="adverse_flow_exit_enabled",
    )
    effective_adverse_flow_threshold, adverse_flow_threshold_source = _resolve_positioning_float(
        request_value=request.adverse_flow_threshold,
        request_default=0.12,
        positioning_key="adverse_flow_threshold",
        min_value=0.02,
    )
    effective_adverse_flow_min_hold_bars, adverse_flow_min_hold_source = _resolve_positioning_int(
        request_value=request.adverse_flow_min_hold_bars,
        request_default=3,
        positioning_key="adverse_flow_min_hold_bars",
        min_value=1,
    )
    effective_stop_loss_mode, stop_loss_mode_source = _resolve_stop_loss_mode(
        request_mode=request.stop_loss_mode
    )
    effective_fixed_stop_loss_pct, fixed_stop_loss_source = _resolve_positioning_float(
        request_value=request.fixed_stop_loss_pct,
        request_default=0.0,
        positioning_key="fixed_stop_loss_pct",
        min_value=0.0,
    )

    def _resolve_adverse_flow_threshold(
        *,
        request_value: Any,
        request_default: float,
        positioning_key: str,
        aos_key: str,
        runtime_key: str,
    ) -> tuple[float, str]:
        source = "request"
        try:
            resolved = float(request_value)
        except (TypeError, ValueError):
            resolved = request_default
            source = "default"
        if abs(resolved - request_default) < 1e-12:
            if positioning_cfg and positioning_key in positioning_cfg:
                try:
                    resolved = float(positioning_cfg.get(positioning_key))
                    source = "positioning_config"
                except (TypeError, ValueError):
                    pass
            if source in {"request", "default"}:
                try:
                    resolved = float(aos_applied.get(aos_key, request_default))
                    source = "aos_config"
                except (TypeError, ValueError):
                    resolved = request_default
                    source = "default"
        try:
            runtime_value = float(adaptive_profile_runtime.get(runtime_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            runtime_value = 0.0
        if runtime_value > 0:
            resolved = runtime_value
            source = "adaptive_profile"
        return max(0.02, resolved), source

    effective_adverse_flow_consistency_threshold, adverse_flow_consistency_source = (
        _resolve_adverse_flow_threshold(
            request_value=request.adverse_flow_consistency_threshold,
            request_default=0.45,
            positioning_key="adverse_flow_consistency_threshold",
            aos_key="adverse_flow_consistency_threshold",
            runtime_key="adverse_flow_consistency_threshold",
        )
    )
    effective_adverse_book_pressure_threshold, adverse_book_pressure_source = (
        _resolve_adverse_flow_threshold(
            request_value=request.adverse_book_pressure_threshold,
            request_default=0.15,
            positioning_key="adverse_book_pressure_threshold",
            aos_key="adverse_book_pressure_threshold",
            runtime_key="adverse_book_pressure_threshold",
        )
    )

    # Keep request value unless left at default and AOS provides an override.
    if int(request.l2_lookback_bars) != 3:
        l2_lookback_bars = max(1, int(request.l2_lookback_bars))
    else:
        try:
            l2_lookback_bars = max(1, int(aos_l2_cfg.get("lookback_bars", request.l2_lookback_bars)))
        except (TypeError, ValueError):
            l2_lookback_bars = max(1, int(request.l2_lookback_bars))

    # Optional L2 feature enrichment and filtering.
    l2_stats: Dict[str, Any] = {
        "requested_l2_only": requested_l2_only,
        "requested_l2_confirm_enabled": requested_l2_confirm,
        "aos_l2_config_applied": bool(aos_l2_cfg),
        "has_l2": False,
        "footprint_bars": 0,
        "icebergs": 0,
        "covered_minutes": 0,
        "bars_with_l2": 0,
        "bars_total": len(bars),
        "bars_after_filter": len(bars),
    }
    use_l2 = bool(requested_l2_only or requested_l2_confirm)
    l2_sessionized_by_market_day = bool(
        comparable_mode and (range_start != range_end or bool(request.date_from and request.date_to))
    )
    if use_l2:
        # Expand slightly to include last bar bucket in inclusive range.
        first_ts_utc = _to_utc_datetime(bars[0]["timestamp"])
        last_ts_utc = _to_utc_datetime(bars[-1]["timestamp"]) + timedelta(minutes=1)
        feature_map, build_stats = _build_l2_feature_map(
            ticker=ticker,
            start_dt_utc=first_ts_utc,
            end_dt_utc=last_ts_utc,
        )
        if l2_sessionized_by_market_day:
            build_stats.update(
                _normalize_l2_feature_map_for_market_day_sessions(
                    feature_map=feature_map,
                    bars=bars,
                )
            )
        l2_stats.update(build_stats)
        bars, attach_stats = _attach_l2_features(bars, feature_map, l2_only=requested_l2_only)
        l2_stats.update(attach_stats)
        # Guard against false positives where files exist but requested range has zero overlap.
        l2_stats["has_l2"] = bool(l2_stats.get("bars_with_l2", 0) > 0)

        if requested_l2_only and not bars:
            raise HTTPException(
                400,
                f"L2-only mode requested but no L2-aligned bars found for {ticker} "
                f"in range {range_start} to {range_end}.",
            )
        if requested_l2_confirm and not l2_stats.get("has_l2"):
            logger.warning(
                f"L2 confirmation requested for {ticker}, but no L2 data was found. "
                "Falling back to non-L2 confirmation for this run."
            )
    
    # Configure session defaults after strategy/AOS updates and after
    # we know whether L2 confirmation is actually feasible for this run.
    effective_l2_confirm = bool(requested_l2_confirm and l2_stats.get("has_l2"))
    effective_intrabar_execution_recalc_1s = (
        bool(request.intrabar_execution_recalc_1s)
        if request.intrabar_execution_recalc_1s is not None
        else bool(use_l2 and l2_stats.get("has_l2"))
    )
    await _configure_session(
        request.strategy_api_url,
        request.run_id,
        ticker,
        range_start,
        request.regime_detection_minutes,
        request.regime_refresh_bars,
        request.account_size_usd,
        risk_per_trade_pct=effective_risk_per_trade_pct,
        max_position_notional_pct=effective_max_position_notional_pct,
        max_fill_participation_rate=effective_max_fill_participation_rate,
        min_fill_ratio=effective_min_fill_ratio,
        enable_partial_take_profit=effective_enable_partial_take_profit,
        partial_take_profit_rr=effective_partial_take_profit_rr,
        partial_take_profit_fraction=effective_partial_take_profit_fraction,
        trailing_activation_pct=effective_trailing_activation_pct,
        break_even_buffer_pct=effective_break_even_buffer_pct,
        break_even_min_hold_bars=effective_break_even_min_hold_bars,
        trailing_enabled_in_choppy=effective_trailing_enabled_in_choppy,
        time_exit_bars=effective_time_exit_bars,
        adverse_flow_exit_enabled=effective_adverse_flow_exit_enabled,
        adverse_flow_threshold=effective_adverse_flow_threshold,
        adverse_flow_min_hold_bars=effective_adverse_flow_min_hold_bars,
        adverse_flow_consistency_threshold=effective_adverse_flow_consistency_threshold,
        adverse_book_pressure_threshold=effective_adverse_book_pressure_threshold,
        stop_loss_mode=effective_stop_loss_mode,
        fixed_stop_loss_pct=effective_fixed_stop_loss_pct,
        l2_confirm_enabled=effective_l2_confirm,
        l2_min_delta=l2_min_delta,
        l2_min_imbalance=l2_min_imbalance,
        l2_min_iceberg_bias=l2_min_iceberg_bias,
        l2_lookback_bars=l2_lookback_bars,
        l2_min_participation_ratio=l2_min_participation_ratio,
        l2_min_directional_consistency=l2_min_directional_consistency,
        l2_min_signed_aggression=l2_min_signed_aggression,
        cold_start_each_day=effective_cold_start_each_day,
        strategy_selection_mode=effective_strategy_selection_mode,
        max_active_strategies=effective_max_active_strategies,
        momentum_diversification_json=momentum_diversification_json,
    )

    if not bars:
        raise HTTPException(400, "No data available for the specified date/range")

    # Load QQQ reference bars for cross-asset context (best-effort)
    ref_bars_map = {}
    if ticker.upper() != 'QQQ':
        try:
            databento_svc.scan_existing_files()
            qqq_files = databento_svc.get_files_for_range(
                ticker='QQQ', start_date=range_start, end_date=range_end,
                schema_prefix="ohlcv-",
            )
            if not qqq_files:
                discovery = get_discovery()
                qqq_files = discovery.get_files_for_range('QQQ', range_start, range_end)
            if qqq_files:
                qqq_dfs = []
                for f in qqq_files:
                    try:
                        if f.endswith('.parquet') or f.endswith('.parq'):
                            qqq_dfs.append(data_loader.load_parquet(f))
                        else:
                            qqq_dfs.append(data_loader.load_csv(f))
                    except Exception:
                        continue
                if qqq_dfs:
                    qqq_df = pd.concat(qqq_dfs, ignore_index=True)
                    qqq_df = data_loader.filter_trading_range(qqq_df, range_start, range_end)
                    for qqq_bar in data_loader.get_bars_iterator(qqq_df):
                        ts = qqq_bar.get('timestamp')
                        ts_key = (ts.isoformat() if hasattr(ts, 'isoformat')
                                  else str(ts))
                        qqq_bar['ticker'] = 'QQQ'
                        ref_bars_map[ts_key] = qqq_bar
                    logger.info(f"Loaded {len(ref_bars_map)} QQQ reference bars for cross-asset")
        except Exception as e:
            logger.debug(f"Could not load QQQ reference data: {e}")

    # Create runner
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
            "run_id": request.run_id,
            "ticker": ticker,
            "bar": bar
        })
    
    async def on_decision(marker):
        await broadcast({
            "type": "decision",
            "run_id": request.run_id,
            "ticker": ticker,
            "marker": marker
        })
    
    runner.on_bar(on_bar)
    runner.on_decision(on_decision)
    
    # Store checkpoint auto-save metadata on runner for use after run_all
    runner._checkpoint_auto_save = bool(request.auto_save_checkpoint and not comparable_mode)
    runner._checkpoint_strategy_url = request.strategy_api_url
    runner._checkpoint_loaded = checkpoint_loaded

    active_runners[run_key] = runner

    logger.info(f"Started run {run_key} with {len(bars)} bars")

    return {
        "success": True,
        "run_key": run_key,
        "ticker": ticker,
        "total_bars": len(bars),
        "strategy_state_reset": orchestrator_reset,
        "checkpoint_loaded": checkpoint_loaded,
        "strategy_overrides_applied": strategy_overrides_applied,
        "data_files": data_files,
        "aos_applied": aos_applied,
        "l2_applied": {
            **l2_stats,
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
        "execution_config": {
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
            "strategy_selection_mode": effective_strategy_selection_mode,
            "max_active_strategies": effective_max_active_strategies,
            "momentum_diversification_applied": bool(effective_momentum_diversification),
            "momentum_diversification_source": momentum_diversification_source,
            "momentum_diversification": effective_momentum_diversification or {},
        },
        "first_bar": bars[0] if bars else None,
        "last_bar": bars[-1] if bars else None
    }


