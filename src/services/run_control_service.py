from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Dict, Optional, Union

from fastapi import HTTPException, Request

from src.services.trade_eval_mode_service import (
    normalize_trade_eval_mode,
    resolve_trade_eval_mode_from_settings,
    resolve_trade_eval_settings,
)


@dataclass
class RunControlDeps:
    run_registry: Any
    active_runners: Dict[str, Any]
    marker_type_enum: Any
    logger: Any
    reports_dir: Path
    save_remote_checkpoint: Any
    clear_remote_strategy_sessions: Any
    configure_session: Any
    run_reports_store: Optional[Any] = None
    l2_manager: Optional[Any] = None


def _runner_date_label(runner: Any) -> str:
    config = getattr(runner, "config", None)
    if config is None:
        return ""
    date_from = str(getattr(config, "date_from", "") or "").strip()
    date_to = str(getattr(config, "date_to", "") or "").strip()
    if date_from and date_to:
        return f"{date_from}_to_{date_to}"
    return str(date_from or date_to or getattr(config, "date", "") or "").strip()


def _runner_run_key(runner: Any) -> Optional[str]:
    config = getattr(runner, "config", None)
    if config is None:
        return None
    run_id = str(getattr(config, "run_id", "") or "").strip()
    ticker = str(getattr(config, "ticker", "") or "").strip()
    date_label = _runner_date_label(runner)
    if not run_id or not ticker or not date_label:
        return None
    return f"{run_id}:{ticker}:{date_label}"


async def _persist_runner_summary_to_store(runner: Any, deps: RunControlDeps) -> bool:
    report_store = getattr(deps, "run_reports_store", None)
    upsert = getattr(report_store, "upsert_run_summary", None)
    if not callable(upsert):
        return False

    run_key = _runner_run_key(runner)
    if not run_key:
        return False
    summary_payload = runner.get_summary()
    payload = summary_payload if isinstance(summary_payload, dict) else {}
    await asyncio.to_thread(
        upsert,
        run_key=run_key,
        summary=payload,
    )
    return True


def get_run_state(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    return runner.get_state()


async def step_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    return await runner.step()


async def play_run(
    run_id: str,
    ticker: str,
    date: str,
    deps: RunControlDeps,
    *,
    request: Optional[Any] = None,
    speed_ms: Optional[Union[int, str]] = None,
    raw_request: Optional[Request] = None,
):
    _, runner = deps.run_registry.require(run_id, ticker, date)

    def _set_trade_eval_mode(mode: str) -> None:
        _, intrabar_enabled, step_seconds = resolve_trade_eval_settings(
            requested_mode=mode,
            fallback_intrabar_enabled=bool(
                getattr(runner.config, "intrabar_execution_recalc_1s", False)
            ),
            fallback_intrabar_eval_step_seconds=getattr(
                runner.config, "intrabar_eval_step_seconds", 1
            ),
        )
        runner.config.intrabar_execution_recalc_1s = intrabar_enabled
        runner.config.intrabar_eval_step_seconds = step_seconds
        # Ensure L2 manager is attached when switching to intrabar mode at
        # play-time (the runner may have been created without it if the
        # original start request did not request intrabar evaluation).
        if intrabar_enabled and getattr(runner, "l2_manager", None) is None:
            if deps.l2_manager is not None:
                runner.l2_manager = deps.l2_manager

    def _effective_trade_eval_mode() -> str:
        return resolve_trade_eval_mode_from_settings(
            intrabar_enabled=bool(
                getattr(runner.config, "intrabar_execution_recalc_1s", False)
            ),
            intrabar_eval_step_seconds=getattr(
                runner.config, "intrabar_eval_step_seconds", 1
            ),
        )

    payload: Optional[Dict[str, Any]] = None
    if raw_request is not None:
        try:
            parsed_payload = await raw_request.json()
            if isinstance(parsed_payload, dict):
                payload = parsed_payload
        except Exception:
            payload = None

    raw_speed = None
    request_speed = getattr(request, "speed_ms", None) if request is not None else None
    if request_speed is not None:
        raw_speed = request_speed
    elif speed_ms is not None:
        raw_speed = speed_ms
    elif payload is not None:
        raw_speed = payload.get("speed_ms")
    if raw_speed is None:
        raw_speed = "max"

    raw_trade_mode = (
        getattr(request, "trade_eval_mode", None) if request is not None else None
    )
    if raw_trade_mode is None and payload is not None:
        raw_trade_mode = payload.get("trade_eval_mode")

    normalized_trade_mode = normalize_trade_eval_mode(raw_trade_mode)

    if normalized_trade_mode is not None:
        _set_trade_eval_mode(normalized_trade_mode)

    effective_trade_mode = _effective_trade_eval_mode()

    if runner.is_running and runner.is_paused:
        runner.resume()
        return {
            "success": True,
            "resumed": True,
            "speed_ms": (
                runner.last_run_speed
                if hasattr(runner, "last_run_speed")
                else "unknown"
            ),
            "trade_eval_mode": effective_trade_mode,
        }

    if runner.is_running:
        return {"success": False, "error": "Run already in progress"}

    if isinstance(raw_speed, str):
        normalized = raw_speed.strip().lower()
        if normalized in {"instant", "max", "fast"}:
            raw_speed = "max"
        elif normalized.endswith("hz") and normalized[:-2].isdigit():
            raw_speed = f"{int(normalized[:-2])}hz"
        elif normalized in {"", "null", "none"}:
            raw_speed = "max"

    runner.last_run_speed = raw_speed

    async def _run_and_maybe_save():
        await runner.run_all(speed_ms=raw_speed)

        try:
            deps.reports_dir.mkdir(parents=True, exist_ok=True)
            run_date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_run_id = str(runner.config.run_id).replace(":", "_")
            out_dir = (
                deps.reports_dir
                / f"{run_date_str}_{runner.config.ticker}_{safe_run_id}"
            )
            runner.save_reports(str(out_dir))
        except Exception as exc:
            deps.logger.error("Failed to auto-save reports: %s", exc)

        try:
            await _persist_runner_summary_to_store(runner, deps)
        except Exception as exc:
            deps.logger.error(
                "Failed to persist run summary to external report store: %s", exc
            )

        if getattr(runner, "_checkpoint_auto_save", False):
            url = getattr(runner, "_checkpoint_strategy_url", "")
            if url:
                await deps.save_remote_checkpoint(
                    url,
                    run_id=runner.config.run_id,
                    ticker=runner.config.ticker,
                    date_from=runner.config.date_from or runner.config.date,
                    date_to=runner.config.date_to or runner.config.date,
                )

    asyncio.create_task(_run_and_maybe_save())
    return {
        "success": True,
        "speed_ms": raw_speed,
        "trade_eval_mode": effective_trade_mode,
    }


def pause_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    runner.pause()
    return {"success": True, "is_paused": True}


def resume_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    runner.resume()
    return {"success": True, "is_paused": False}


def stop_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    runner.stop()
    return {"success": True, "stopped": True}


async def restart_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)

    if getattr(runner, "is_running", False):
        raise HTTPException(
            409, "Cannot restart while run is active. Pause/stop first."
        )

    restart_config = getattr(runner, "_restart_session_config", None)
    if not isinstance(restart_config, dict):
        raise HTTPException(
            409, "Run cannot be restarted (missing session config snapshot)."
        )

    await deps.clear_remote_strategy_sessions(
        runner.config.strategy_api_url,
        runner.config.run_id,
        runner.config.ticker,
    )

    restart_date = str(
        getattr(runner, "_restart_session_date", None)
        or runner.config.date_from
        or runner.config.date
    )

    await deps.configure_session(
        runner.config.strategy_api_url,
        runner.config.run_id,
        runner.config.ticker,
        restart_date,
        **restart_config,
    )

    if hasattr(runner, "reset_for_replay"):
        if hasattr(runner, "close_http_session"):
            await runner.close_http_session()
        runner.reset_for_replay()
    else:
        # Safety fallback for older runner objects.
        runner.current_bar_index = 0
        runner.is_running = False
        runner.is_paused = False
        runner.phase = "INITIALIZED"
        runner.last_response = None
        runner.session_summary = None

    return {"success": True, "restarted": True, "state": runner.get_state()}


def get_processed_bars(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    return {
        "bars": runner.get_processed_bars(),
        "current_index": runner.current_bar_index,
        "total_bars": len(runner.bars),
    }


def get_bar_details(
    run_id: str, ticker: str, date: str, minute_key: int, deps: RunControlDeps
):
    from src.intrabar_frame_builder import IntrabarFrameBuilder
    from src.l2_data_manager import L2DataManager

    deps.run_registry.require(run_id, ticker, date)

    minute_start = datetime.fromtimestamp(minute_key, tz=timezone.utc)
    minute_end = minute_start.replace(second=59, microsecond=999999)

    manager = L2DataManager()
    builder = IntrabarFrameBuilder(manager=manager)

    try:
        frames = builder.build_frames(ticker, minute_start, minute_end)
        if frames.empty:
            return {
                "minute_key": minute_key,
                "ticker": ticker,
                "frames": [],
                "stats": {"has_data": False, "seconds": 0},
            }

        frames["ts_sec"] = frames["ts_sec"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        records = frames.to_dict(orient="records")
        return {
            "minute_key": minute_key,
            "ticker": ticker,
            "frames": records,
            "stats": {
                "has_data": True,
                "seconds": len(records),
                "coverage_ratio": (
                    float(frames["coverage_ratio"].iloc[0])
                    if "coverage_ratio" in frames.columns
                    else 0.0
                ),
                "total_trade_ticks": (
                    int(frames["trade_ticks_sec"].sum())
                    if "trade_ticks_sec" in frames.columns
                    else 0
                ),
                "total_book_updates": (
                    int(frames["book_updates_sec"].sum())
                    if "book_updates_sec" in frames.columns
                    else 0
                ),
            },
        }
    except Exception as exc:
        raise HTTPException(500, f"Failed to load bar details: {str(exc)}")


def get_markers(
    run_id: str,
    ticker: str,
    date: str,
    marker_type: Optional[str],
    deps: RunControlDeps,
):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    if marker_type:
        try:
            mt = deps.marker_type_enum(marker_type)
            return runner.tracker.get_markers(mt)
        except ValueError:
            raise HTTPException(400, f"Invalid marker type: {marker_type}")
    return runner.get_markers()


def get_chart_annotations(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    return runner.get_chart_annotations()


def get_run_summary(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    return runner.get_summary()


async def delete_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    run_key, runner = deps.run_registry.require(run_id, ticker, date)
    runner.stop()
    try:
        await _persist_runner_summary_to_store(runner, deps)
    except Exception as exc:
        deps.logger.error("Failed to persist run summary during delete_run: %s", exc)
    if hasattr(runner, "close_http_session"):
        await runner.close_http_session()
    await deps.clear_remote_strategy_sessions(
        runner.config.strategy_api_url,
        runner.config.run_id,
        runner.config.ticker,
    )
    del deps.active_runners[run_key]
    return {"success": True, "deleted": run_key}


def list_runs(deps: RunControlDeps):
    return [runner.get_state() for runner in deps.active_runners.values()]
