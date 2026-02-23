from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from src.services.start_run_time_window_service import (
    filter_bars_for_requested_time_window,
    filter_reference_map_for_requested_time_window,
)


@dataclass(frozen=True)
class RunnerSetupInputs:
    request: Any
    run_key: str
    run_date_label: str
    ticker: str
    range_start: str
    range_end: str
    load_range_start: str
    load_range_end: str
    full_range_start: str
    full_range_end: str
    comparable_mode: bool
    bars: list[Any]
    ref_bars_map: Dict[str, Any]
    session_config_snapshot: Dict[str, Any]
    effective_intrabar_execution_recalc_1s: bool
    effective_intrabar_eval_step_seconds: int
    checkpoint_loaded: Any
    progressive_plan: Optional[Dict[str, Any]]
    aos_applied: Dict[str, Any]
    requested_l2_only: bool
    requested_l2_confirm: bool


@dataclass(frozen=True)
class RunnerSetupDeps:
    active_runners: Dict[str, Any]
    logger: Any
    data_loader: Any
    databento_svc: Any
    l2_manager: Any
    get_discovery: Callable[[], Any]
    broadcast: Callable[[Dict[str, Any]], Awaitable[None]]
    run_config_cls: Any
    session_runner_cls: Any
    to_utc_datetime: Callable[[Any], Any]
    build_l2_feature_map: Callable[..., Any]
    normalize_l2_feature_map_for_market_day_sessions: Callable[..., Dict[str, Any]]
    attach_l2_features: Callable[..., Any]
    load_run_bars: Callable[..., Any]
    enrich_bars_with_l2: Callable[..., Any]
    load_reference_bars_map: Callable[..., Dict[str, Any]]


def _register_runner_callbacks(
    *,
    runner: Any,
    deps: RunnerSetupDeps,
    request: Any,
    run_key: str,
    ticker: str,
    run_date_label: str,
) -> None:
    async def on_bar(bar):
        await deps.broadcast(
            {
                "type": "bar",
                "run_key": run_key,
                "run_id": request.run_id,
                "ticker": ticker,
                "date": run_date_label,
                "bar": bar,
            }
        )

    async def on_decision(marker):
        await deps.broadcast(
            {
                "type": "decision",
                "run_key": run_key,
                "run_id": request.run_id,
                "ticker": ticker,
                "date": run_date_label,
                "marker": marker,
            }
        )

    runner.on_bar(on_bar)
    runner.on_decision(on_decision)


def _apply_runner_runtime_metadata(
    *,
    runner: Any,
    inputs: RunnerSetupInputs,
    deps: RunnerSetupDeps,
) -> None:
    trade_start_raw = str(getattr(inputs.request, "trade_start_time", "") or "").strip()
    trade_end_raw = str(getattr(inputs.request, "trade_end_time", "") or "").strip()
    try:
        runner._trade_start_time = (
            deps.to_utc_datetime(trade_start_raw) if trade_start_raw else None
        )
    except Exception:
        runner._trade_start_time = None
    try:
        runner._trade_end_time = (
            deps.to_utc_datetime(trade_end_raw) if trade_end_raw else None
        )
    except Exception:
        runner._trade_end_time = None
    runner._checkpoint_auto_save = bool(
        inputs.request.auto_save_checkpoint and not inputs.comparable_mode
    )
    runner._checkpoint_strategy_url = inputs.request.strategy_api_url
    runner._checkpoint_loaded = inputs.checkpoint_loaded
    runner._restart_session_date = inputs.range_start
    runner._restart_session_config = dict(inputs.session_config_snapshot)
    runner._progressive_loading_enabled = bool(inputs.progressive_plan)
    runner._progressive_loading_complete = not bool(inputs.progressive_plan)
    runner._progressive_loading_loaded_until = (
        inputs.load_range_end if inputs.bars else None
    )
    runner._progressive_loading_target_end = inputs.full_range_end
    runner._progressive_loading_pending_chunks = (
        len(inputs.progressive_plan.get("chunks", []))
        if isinstance(inputs.progressive_plan, dict)
        else 0
    )
    runner._progressive_loading_last_error = None
    runner._progressive_loading_task = None
    runner._progressive_wait_timeout_seconds = 90
    runner._progressive_wait_started_at = None


def _load_chunk_payload(
    *,
    chunk_start: str,
    chunk_end: str,
    inputs: RunnerSetupInputs,
    deps: RunnerSetupDeps,
) -> tuple[list[Any], Dict[str, Any]]:
    chunk_bars, _chunk_data_files = deps.load_run_bars(
        request=inputs.request,
        ticker=inputs.ticker,
        range_start=chunk_start,
        range_end=chunk_end,
        data_loader=deps.data_loader,
        databento_svc=deps.databento_svc,
        get_discovery=deps.get_discovery,
        aos_applied=inputs.aos_applied,
        logger=deps.logger,
    )
    chunk_bars, _chunk_l2_stats, _chunk_l2_sessionized = deps.enrich_bars_with_l2(
        bars=chunk_bars,
        ticker=inputs.ticker,
        range_start=chunk_start,
        range_end=chunk_end,
        requested_l2_only=inputs.requested_l2_only,
        requested_l2_confirm=inputs.requested_l2_confirm,
        comparable_mode=inputs.comparable_mode,
        is_multi_day_request=bool(chunk_start != chunk_end),
        aos_l2_config_applied=bool(
            isinstance(inputs.aos_applied.get("l2"), dict)
            and inputs.aos_applied.get("l2")
        ),
        to_utc_datetime=deps.to_utc_datetime,
        build_l2_feature_map=deps.build_l2_feature_map,
        normalize_l2_feature_map_for_market_day_sessions=(
            deps.normalize_l2_feature_map_for_market_day_sessions
        ),
        attach_l2_features=deps.attach_l2_features,
        logger=deps.logger,
    )
    chunk_ref_map = deps.load_reference_bars_map(
        ticker=inputs.ticker,
        range_start=chunk_start,
        range_end=chunk_end,
        data_loader=deps.data_loader,
        databento_svc=deps.databento_svc,
        get_discovery=deps.get_discovery,
        logger=deps.logger,
    )
    chunk_bars = filter_bars_for_requested_time_window(
        bars=chunk_bars,
        request=inputs.request,
        to_utc_datetime=deps.to_utc_datetime,
    )
    chunk_ref_map = filter_reference_map_for_requested_time_window(
        ref_bars_map=chunk_ref_map,
        request=inputs.request,
        to_utc_datetime=deps.to_utc_datetime,
    )
    return list(chunk_bars), (
        dict(chunk_ref_map) if isinstance(chunk_ref_map, dict) else {}
    )


def _append_deduped_chunk_bars(
    *,
    runner: Any,
    chunk_bars: list[Any],
    to_utc_datetime: Callable[[Any], Any],
) -> list[Any]:
    last_loaded_ts = None
    if runner.bars:
        try:
            last_loaded_ts = to_utc_datetime(runner.bars[-1].get("timestamp"))
        except Exception:
            last_loaded_ts = None

    appended_bars: list[Any] = []
    for bar_item in chunk_bars:
        if last_loaded_ts is not None:
            try:
                bar_ts = to_utc_datetime(bar_item.get("timestamp"))
                if bar_ts <= last_loaded_ts:
                    continue
            except Exception:
                pass
        appended_bars.append(bar_item)

    if appended_bars:
        runner.bars.extend(appended_bars)
    return appended_bars


async def _append_remaining_chunks(
    *,
    runner: Any,
    inputs: RunnerSetupInputs,
    deps: RunnerSetupDeps,
    pending_chunks: list[tuple[str, str]],
) -> None:
    deps.logger.info(
        "Progressive loading enabled for %s: initial=%s..%s, pending_chunks=%d, target=%s..%s",
        inputs.run_key,
        inputs.load_range_start,
        inputs.load_range_end,
        len(pending_chunks),
        inputs.full_range_start,
        inputs.full_range_end,
    )
    try:
        for idx, (chunk_start, chunk_end) in enumerate(pending_chunks, start=1):
            if deps.active_runners.get(inputs.run_key) is not runner:
                deps.logger.info(
                    "Progressive loading aborted for %s (runner no longer active).",
                    inputs.run_key,
                )
                break

            chunk_bars, chunk_ref_map = await asyncio.to_thread(
                _load_chunk_payload,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                inputs=inputs,
                deps=deps,
            )
            appended_bars = _append_deduped_chunk_bars(
                runner=runner,
                chunk_bars=chunk_bars,
                to_utc_datetime=deps.to_utc_datetime,
            )
            if chunk_ref_map:
                runner.ref_bars_map.update(chunk_ref_map)

            runner._progressive_loading_loaded_until = chunk_end
            runner._progressive_loading_pending_chunks = max(
                0, len(pending_chunks) - idx
            )

            deps.logger.info(
                "Progressive chunk loaded for %s: %s..%s (+%d bars, total=%d, pending=%d)",
                inputs.run_key,
                chunk_start,
                chunk_end,
                len(appended_bars),
                len(runner.bars),
                int(runner._progressive_loading_pending_chunks),
            )
            await deps.broadcast(
                {
                    "type": "run_data_extended",
                    "run_key": inputs.run_key,
                    "run_id": inputs.request.run_id,
                    "ticker": inputs.ticker,
                    "date": inputs.run_date_label,
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "added_bars": len(appended_bars),
                    "total_bars": len(runner.bars),
                    "pending_chunks": int(runner._progressive_loading_pending_chunks),
                }
            )
    except Exception as exc:
        runner._progressive_loading_last_error = str(exc)
        deps.logger.exception("Progressive loading failed for %s", inputs.run_key)
    finally:
        runner._progressive_loading_complete = True
        runner._progressive_loading_pending_chunks = 0
        if not runner._progressive_loading_last_error:
            runner._progressive_loading_loaded_until = inputs.full_range_end
        deps.logger.info(
            "Progressive loading finished for %s (error=%s)",
            inputs.run_key,
            runner._progressive_loading_last_error,
        )


def setup_runner_with_progressive_loading(
    *,
    inputs: RunnerSetupInputs,
    deps: RunnerSetupDeps,
) -> tuple[Any, Dict[str, Any]]:
    ref_bars_map = (
        dict(inputs.ref_bars_map) if isinstance(inputs.ref_bars_map, dict) else {}
    )

    config = deps.run_config_cls(
        run_id=inputs.request.run_id,
        ticker=inputs.ticker,
        date=inputs.run_date_label,
        date_from=inputs.range_start,
        date_to=inputs.range_end,
        strategy_api_url=inputs.request.strategy_api_url,
        account_size_usd=inputs.request.account_size_usd,
        regime_detection_minutes=inputs.request.regime_detection_minutes,
        intrabar_execution_recalc_1s=inputs.effective_intrabar_execution_recalc_1s,
        intrabar_eval_step_seconds=inputs.effective_intrabar_eval_step_seconds,
    )

    runner = deps.session_runner_cls(config)
    runner.ref_bars_map = ref_bars_map
    if inputs.effective_intrabar_execution_recalc_1s:
        runner.l2_manager = deps.l2_manager
    runner.load_bars(inputs.bars)

    _register_runner_callbacks(
        runner=runner,
        deps=deps,
        request=inputs.request,
        run_key=inputs.run_key,
        ticker=inputs.ticker,
        run_date_label=inputs.run_date_label,
    )
    _apply_runner_runtime_metadata(runner=runner, inputs=inputs, deps=deps)

    deps.active_runners[inputs.run_key] = runner

    if isinstance(inputs.progressive_plan, dict):
        pending_chunks = list(inputs.progressive_plan.get("chunks", []))
        runner._progressive_loading_task = asyncio.create_task(
            _append_remaining_chunks(
                runner=runner,
                inputs=inputs,
                deps=deps,
                pending_chunks=pending_chunks,
            )
        )

    return runner, ref_bars_map
