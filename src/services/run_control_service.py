from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Dict, Optional, Union

from fastapi import HTTPException, Request


@dataclass
class RunControlDeps:
    run_registry: Any
    active_runners: Dict[str, Any]
    marker_type_enum: Any
    logger: Any
    reports_dir: Path
    save_remote_checkpoint: Any
    clear_remote_strategy_sessions: Any


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

    if runner.is_running and runner.is_paused:
        runner.resume()
        return {
            "success": True,
            "resumed": True,
            "speed_ms": runner.last_run_speed if hasattr(runner, "last_run_speed") else "unknown",
        }

    if runner.is_running:
        return {"success": False, "error": "Run already in progress"}

    raw_speed = None
    request_speed = getattr(request, "speed_ms", None) if request is not None else None
    if request_speed is not None:
        raw_speed = request_speed
    elif speed_ms is not None:
        raw_speed = speed_ms
    else:
        try:
            if raw_request is not None:
                payload = await raw_request.json()
                raw_speed = payload.get("speed_ms") if isinstance(payload, dict) else None
        except Exception:
            raw_speed = None
    if raw_speed is None:
        raw_speed = "max"

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
            out_dir = deps.reports_dir / f"{run_date_str}_{runner.config.ticker}_{safe_run_id}"
            runner.save_reports(str(out_dir))
        except Exception as exc:
            deps.logger.error("Failed to auto-save reports: %s", exc)

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
    return {"success": True, "speed_ms": raw_speed}


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


def get_processed_bars(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    return {
        "bars": runner.get_processed_bars(),
        "current_index": runner.current_bar_index,
        "total_bars": len(runner.bars),
    }


def get_bar_details(run_id: str, ticker: str, date: str, minute_key: int, deps: RunControlDeps):
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
                    float(frames["coverage_ratio"].iloc[0]) if "coverage_ratio" in frames.columns else 0.0
                ),
                "total_trade_ticks": (
                    int(frames["trade_ticks_sec"].sum()) if "trade_ticks_sec" in frames.columns else 0
                ),
                "total_book_updates": (
                    int(frames["book_updates_sec"].sum()) if "book_updates_sec" in frames.columns else 0
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
    await deps.clear_remote_strategy_sessions(
        runner.config.strategy_api_url,
        runner.config.run_id,
        runner.config.ticker,
    )
    del deps.active_runners[run_key]
    return {"success": True, "deleted": run_key}


def list_runs(deps: RunControlDeps):
    return [runner.get_state() for runner in deps.active_runners.values()]
