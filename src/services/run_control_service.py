from __future__ import annotations

import asyncio
import base64
import gzip
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Dict, Optional, Union

import aiohttp
from fastapi import HTTPException, Request

from src.services.session_runner_strategy_client import StrategyApiClient
from src.services.strategy_api_auth_headers import build_strategy_api_headers
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


async def _read_raw_request_payload(
    raw_request: Optional[Request],
) -> Optional[Dict[str, Any]]:
    if raw_request is None:
        return None
    try:
        parsed_payload = await raw_request.json()
    except Exception:
        return None
    return parsed_payload if isinstance(parsed_payload, dict) else None


def _set_runner_trade_eval_mode(
    runner: Any, deps: RunControlDeps, normalized_mode: str
) -> None:
    _, intrabar_enabled, step_seconds = resolve_trade_eval_settings(
        requested_mode=normalized_mode,
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
    # runtime (the runner may have been created without it).
    if intrabar_enabled and getattr(runner, "l2_manager", None) is None:
        if deps.l2_manager is not None:
            runner.l2_manager = deps.l2_manager


def _effective_runner_trade_eval_mode(runner: Any) -> str:
    return resolve_trade_eval_mode_from_settings(
        intrabar_enabled=bool(
            getattr(runner.config, "intrabar_execution_recalc_1s", False)
        ),
        intrabar_eval_step_seconds=getattr(
            runner.config, "intrabar_eval_step_seconds", 1
        ),
    )


def _resolve_requested_trade_eval_mode(
    *, request: Optional[Any], payload: Optional[Dict[str, Any]]
) -> Optional[str]:
    raw_trade_mode = (
        getattr(request, "trade_eval_mode", None) if request is not None else None
    )
    if raw_trade_mode is None and payload is not None:
        raw_trade_mode = payload.get("trade_eval_mode")
    return normalize_trade_eval_mode(raw_trade_mode)


def _env_flag(name: str, default: bool) -> bool:
    token = str(os.getenv(name, "")).strip().lower()
    if not token:
        return bool(default)
    return token in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return max(minimum, int(default))
    try:
        parsed = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return max(minimum, int(default))
    return max(minimum, parsed)


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

    return str(value)


def _safe_runner_processed_bars(runner: Any) -> list[Dict[str, Any]]:
    getter = getattr(runner, "get_processed_bars", None)
    if not callable(getter):
        return []
    try:
        bars = getter()
    except Exception:
        return []
    return [item for item in bars if isinstance(item, dict)] if isinstance(bars, list) else []


def _safe_runner_markers(runner: Any) -> list[Dict[str, Any]]:
    getter = getattr(runner, "get_markers", None)
    if not callable(getter):
        return []
    try:
        markers = getter()
    except Exception:
        return []
    return (
        [item for item in markers if isinstance(item, dict)]
        if isinstance(markers, list)
        else []
    )


def _build_playback_snapshot_metadata(
    *,
    runner: Any,
    run_key: str,
) -> Optional[Dict[str, Any]]:
    if not _env_flag("BACKTEST_RUN_REPORT_SNAPSHOT_ENABLED", True):
        return None

    bars = _safe_runner_processed_bars(runner)
    if not bars:
        return None
    markers = _safe_runner_markers(runner)

    snapshot_payload: Dict[str, Any] = {
        "schema_version": 1,
        "run_key": str(run_key),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "bars": bars,
        "markers": markers,
    }

    try:
        serialized = json.dumps(snapshot_payload, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return None

    max_uncompressed_bytes = _env_int(
        "BACKTEST_RUN_REPORT_SNAPSHOT_MAX_UNCOMPRESSED_BYTES",
        120_000_000,
        minimum=1_000_000,
    )
    uncompressed_bytes = len(serialized.encode("utf-8"))
    if uncompressed_bytes > max_uncompressed_bytes:
        return {
            "schema_version": 1,
            "encoding": None,
            "bars_count": len(bars),
            "markers_count": len(markers),
            "payload_b64": None,
            "uncompressed_bytes": uncompressed_bytes,
            "compressed_bytes": None,
            "skip_reason": "snapshot_too_large_uncompressed",
        }

    compressed = gzip.compress(serialized.encode("utf-8"), compresslevel=6)
    max_compressed_bytes = _env_int(
        "BACKTEST_RUN_REPORT_SNAPSHOT_MAX_COMPRESSED_BYTES",
        25_000_000,
        minimum=250_000,
    )
    compressed_bytes = len(compressed)
    if compressed_bytes > max_compressed_bytes:
        return {
            "schema_version": 1,
            "encoding": None,
            "bars_count": len(bars),
            "markers_count": len(markers),
            "payload_b64": None,
            "uncompressed_bytes": uncompressed_bytes,
            "compressed_bytes": compressed_bytes,
            "skip_reason": "snapshot_too_large_compressed",
        }

    payload_b64 = base64.b64encode(compressed).decode("ascii")
    return {
        "schema_version": 1,
        "encoding": "gzip+base64",
        "bars_count": len(bars),
        "markers_count": len(markers),
        "payload_b64": payload_b64,
        "uncompressed_bytes": uncompressed_bytes,
        "compressed_bytes": compressed_bytes,
        "skip_reason": None,
    }


async def _persist_runner_summary_to_store(runner: Any, deps: RunControlDeps) -> bool:
    report_store = getattr(deps, "run_reports_store", None)
    upsert = getattr(report_store, "upsert_run_summary", None)
    if not callable(upsert):
        return False

    run_key = _runner_run_key(runner)
    if not run_key:
        return False
    summary_payload = runner.get_summary()
    payload = dict(summary_payload) if isinstance(summary_payload, dict) else {}
    playback_snapshot = _build_playback_snapshot_metadata(
        runner=runner,
        run_key=run_key,
    )
    if isinstance(playback_snapshot, dict):
        payload["playback_snapshot"] = playback_snapshot
    await asyncio.to_thread(
        upsert,
        run_key=run_key,
        summary=payload,
    )
    return True


def get_run_state(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    return runner.get_state()


async def step_run(
    run_id: str,
    ticker: str,
    date: str,
    deps: RunControlDeps,
    *,
    request: Optional[Any] = None,
    raw_request: Optional[Request] = None,
):
    _, runner = deps.run_registry.require(run_id, ticker, date)

    payload = await _read_raw_request_payload(raw_request)
    normalized_trade_mode = _resolve_requested_trade_eval_mode(
        request=request,
        payload=payload,
    )
    if normalized_trade_mode is not None:
        _set_runner_trade_eval_mode(runner, deps, normalized_trade_mode)

    result = await runner.step()
    if isinstance(result, dict):
        out = dict(result)
        out["trade_eval_mode"] = _effective_runner_trade_eval_mode(runner)
        return out
    return {
        "success": bool(result),
        "trade_eval_mode": _effective_runner_trade_eval_mode(runner),
    }


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
    payload = await _read_raw_request_payload(raw_request)

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

    normalized_trade_mode = _resolve_requested_trade_eval_mode(
        request=request,
        payload=payload,
    )

    if normalized_trade_mode is not None:
        _set_runner_trade_eval_mode(runner, deps, normalized_trade_mode)

    effective_trade_mode = _effective_runner_trade_eval_mode(runner)

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
    bars = _safe_runner_processed_bars(runner)
    return {
        "bars": _to_json_compatible(bars),
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


async def evaluate_intrabar_slice(
    run_id: str,
    ticker: str,
    date: str,
    payload: Dict[str, Any],
    deps: RunControlDeps,
):
    _, runner = deps.run_registry.require(run_id, ticker, date)

    body = payload if isinstance(payload, dict) else {}
    required_fields = ("timestamp", "open", "high", "low", "close", "volume")
    missing_fields = [field for field in required_fields if body.get(field) is None]
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Missing intrabar payload fields: {', '.join(missing_fields)}",
        )

    strategy_api_url = str(
        getattr(getattr(runner, "config", None), "strategy_api_url", "") or ""
    ).strip()
    if not strategy_api_url:
        raise HTTPException(
            status_code=500, detail="Run has no strategy_api_url configured."
        )

    proxy_payload = dict(body)
    proxy_payload["run_id"] = str(getattr(runner.config, "run_id", run_id) or run_id)
    proxy_payload["ticker"] = str(getattr(runner.config, "ticker", ticker) or ticker)

    strategy_client = getattr(runner, "_strategy_api_client", None)
    if strategy_client is not None:
        response = await strategy_client.post_json(
            "/api/session/intrabar_eval",
            json=proxy_payload,
        )
        status_code = StrategyApiClient.response_status_code(response)
        if status_code != 200:
            error_text = await StrategyApiClient.response_text(response)
            detail = (
                error_text
                or f"Strategy intrabar eval failed (HTTP {status_code})"
            )
            raise HTTPException(status_code=status_code, detail=detail)
        try:
            return await StrategyApiClient.response_json(response)
        except Exception as exc:  # pragma: no cover - defensive path
            raise HTTPException(
                status_code=502,
                detail=f"Invalid strategy intrabar response: {str(exc)}",
            ) from exc

    headers = build_strategy_api_headers(strategy_api_url)
    session: Any = None
    owns_session = False

    try:
        get_runner_session = getattr(runner, "_get_strategy_http_session", None)
        if callable(get_runner_session):
            maybe_session = get_runner_session()
            session = (
                await maybe_session
                if asyncio.iscoroutine(maybe_session)
                else maybe_session
            )
        if session is None:
            timeout = aiohttp.ClientTimeout(
                total=8.0, connect=2.0, sock_connect=2.0, sock_read=6.0
            )
            session = aiohttp.ClientSession(timeout=timeout)
            owns_session = True

        post_kwargs: Dict[str, Any] = {"json": proxy_payload}
        if headers:
            post_kwargs["headers"] = headers

        async with session.post(
            f"{strategy_api_url}/api/session/intrabar_eval", **post_kwargs
        ) as resp:
            if resp.status != 200:
                error_text = str(await resp.text() or "").strip()
                detail = error_text or f"Strategy intrabar eval failed (HTTP {resp.status})"
                raise HTTPException(status_code=resp.status, detail=detail)
            try:
                return await resp.json()
            except Exception as exc:  # pragma: no cover - defensive path
                raise HTTPException(
                    status_code=502,
                    detail=f"Invalid strategy intrabar response: {str(exc)}",
                ) from exc
    except aiohttp.ClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Strategy intrabar eval request failed: {str(exc)}",
        ) from exc
    finally:
        if owns_session and session is not None and not session.closed:
            await session.close()


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
