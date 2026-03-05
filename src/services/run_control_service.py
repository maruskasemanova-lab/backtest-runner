from __future__ import annotations

import asyncio
import base64
import gzip
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any, Awaitable, Dict, Optional, Union

import aiohttp
from fastapi import HTTPException, Request

from decision_tracker import DecisionMarker
from src.services.run_config_snapshot_service import (
    attach_resolved_config_snapshot_to_summary,
    resolve_session_config_snapshot,
)
from src.services.session_runner_models import ExecutionLifecycle
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
    run_config_cls: Optional[Any] = None
    session_runner_cls: Optional[Any] = None


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


def _runner_completed_successfully(runner: Any) -> bool:
    bars = getattr(runner, "bars", None)
    try:
        total_bars = len(bars) if bars is not None else 0
    except Exception:
        total_bars = 0
    if total_bars <= 0:
        return False

    try:
        current_bar_index = int(getattr(runner, "current_bar_index", 0) or 0)
    except Exception:
        current_bar_index = 0
    if current_bar_index < total_bars:
        return False

    if bool(getattr(runner, "is_running", False)):
        return False

    phase = str(getattr(runner, "phase", "") or "").strip().upper()
    if phase == "ERROR":
        return False

    progressive_error = str(
        getattr(runner, "_progressive_loading_last_error", "") or ""
    ).strip()
    if progressive_error:
        return False

    return True


def _snapshot_backed_runner(runner: Any) -> bool:
    return bool(getattr(runner, "_snapshot_restored", False))


def _guard_snapshot_runner_mutation(runner: Any, *, action: str) -> None:
    if not _snapshot_backed_runner(runner):
        return
    raise HTTPException(
        409,
        (
            f"Snapshot-backed run is read-only and cannot {action}. "
            "Restore or start a live run to execute bars again."
        ),
    )


def _runner_state_payload(runner: Any) -> Dict[str, Any]:
    getter = getattr(runner, "get_state", None)
    state = getter() if callable(getter) else {}
    payload = dict(state) if isinstance(state, dict) else {}
    if not _snapshot_backed_runner(runner):
        return payload
    payload["is_snapshot"] = True
    payload["snapshot_backed"] = True
    payload["snapshot_restored"] = True
    payload["snapshot_source_mode"] = str(
        getattr(runner, "_snapshot_source_mode", "") or "persisted_playback"
    )
    report_saved_at = str(getattr(runner, "_snapshot_report_saved_at", "") or "").strip()
    if report_saved_at:
        payload["report_saved_at"] = report_saved_at
    return payload


async def _flush_runner_from_memory(
    *,
    run_key: str,
    runner: Any,
    deps: RunControlDeps,
) -> None:
    if hasattr(runner, "close_http_session"):
        try:
            await runner.close_http_session()
        except Exception as exc:
            deps.logger.error(
                "Failed to close HTTP session while flushing run %s: %s", run_key, exc
            )

    try:
        await deps.clear_remote_strategy_sessions(
            runner.config.strategy_api_url,
            runner.config.run_id,
            runner.config.ticker,
        )
    except Exception as exc:
        deps.logger.error(
            "Failed to clear remote strategy sessions while flushing run %s: %s",
            run_key,
            exc,
        )

    active_runner = deps.active_runners.get(run_key)
    if active_runner is runner:
        deps.active_runners.pop(run_key, None)


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


def _coerce_optional_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return None


def _strategy_api_session_deps(logger: Any) -> Any:
    """Session-service helpers currently only require a logger dependency."""
    return SimpleNamespace(logger=logger)


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
    upsert_snapshot = getattr(report_store, "upsert_run_config_snapshot", None)
    resolved_config_snapshot = (
        payload.get("resolved_config_snapshot", {})
        if isinstance(payload.get("resolved_config_snapshot"), dict)
        else {}
    )
    if callable(upsert_snapshot) and resolved_config_snapshot:
        try:
            snapshot_row = await asyncio.to_thread(
                upsert_snapshot,
                run_key=run_key,
                snapshot=resolved_config_snapshot,
            )
        except Exception as exc:
            deps.logger.error(
                "Failed to persist run config snapshot for %s: %s",
                run_key,
                exc,
            )
        else:
            snapshot_id = (
                snapshot_row.get("snapshot_id")
                if isinstance(snapshot_row, dict)
                else None
            )
            payload = attach_resolved_config_snapshot_to_summary(
                payload,
                snapshot_id=snapshot_id,
            )
            payload.pop("resolved_config_snapshot", None)
    await asyncio.to_thread(
        upsert,
        run_key=run_key,
        summary=payload,
    )
    return True


def _hydrate_persisted_run_summary(
    *,
    summary: Dict[str, Any],
    run_key: str,
    report_store: Any,
    logger: Any,
) -> Dict[str, Any]:
    payload = dict(summary) if isinstance(summary, dict) else {}
    embedded_snapshot = (
        payload.get("resolved_config_snapshot", {})
        if isinstance(payload.get("resolved_config_snapshot"), dict)
        else {}
    )
    if embedded_snapshot:
        return payload
    get_snapshot = getattr(report_store, "get_run_config_snapshot", None)
    if not callable(get_snapshot):
        return payload
    snapshot_id = str(payload.get("resolved_config_snapshot_id") or "").strip() or None
    try:
        snapshot_row = get_snapshot(snapshot_id=snapshot_id, run_key=run_key)
    except Exception as exc:
        logger.error(
            "Failed to read run config snapshot from DB for %s: %s",
            run_key,
            exc,
        )
        return payload
    if not isinstance(snapshot_row, dict):
        return payload
    snapshot_payload = (
        snapshot_row.get("payload")
        if isinstance(snapshot_row.get("payload"), dict)
        else {}
    )
    resolved_snapshot_id = str(
        snapshot_row.get("snapshot_id") or snapshot_id or ""
    ).strip()
    return attach_resolved_config_snapshot_to_summary(
        payload,
        snapshot_id=resolved_snapshot_id,
        snapshot_payload=snapshot_payload,
    )


def _load_persisted_run_summary_by_run_key(
    *,
    run_key: str,
    deps: RunControlDeps,
) -> tuple[Dict[str, Any], Optional[str]]:
    report_store = getattr(deps, "run_reports_store", None)
    get_summary = getattr(report_store, "get_run_summary", None)
    if not callable(get_summary):
        return {}, None

    try:
        row = get_summary(run_key=run_key)
    except Exception as exc:
        deps.logger.error(
            "Failed to read persisted run summary for %s: %s",
            run_key,
            exc,
        )
        return {}, None

    if not isinstance(row, dict):
        return {}, None

    summary = row.get("summary", {})
    if not isinstance(summary, dict):
        return {}, row.get("updated_at")

    hydrated = _hydrate_persisted_run_summary(
        summary=summary,
        run_key=run_key,
        report_store=report_store,
        logger=deps.logger,
    )
    updated_at = str(row.get("updated_at") or "").strip() or None
    return hydrated, updated_at


def _load_runner_persisted_summary(
    *,
    runner: Any,
    deps: RunControlDeps,
) -> Dict[str, Any]:
    run_key = _runner_run_key(runner)
    if not run_key:
        return {}
    summary, _updated_at = _load_persisted_run_summary_by_run_key(
        run_key=run_key,
        deps=deps,
    )
    return summary


def _resolve_restart_session_config(
    *,
    runner: Any,
    deps: RunControlDeps,
) -> Dict[str, Any]:
    direct_snapshot = resolve_session_config_snapshot(
        getattr(runner, "_restart_session_config", None)
    )
    if direct_snapshot:
        return direct_snapshot

    resolved_snapshot = resolve_session_config_snapshot(
        resolved_config_snapshot=getattr(runner, "_resolved_config_snapshot", None)
    )
    if resolved_snapshot:
        return resolved_snapshot

    persisted_summary = _load_runner_persisted_summary(runner=runner, deps=deps)
    if persisted_summary:
        return resolve_session_config_snapshot(summary_payload=persisted_summary)

    return {}


def _resolved_config_snapshot_payload(summary_payload: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = summary_payload.get("resolved_config_snapshot", {})
    return snapshot if isinstance(snapshot, dict) else {}


def _has_modern_persisted_summary(
    summary_payload: Dict[str, Any],
    *,
    require_playback: bool = False,
) -> bool:
    resolved_snapshot = _resolved_config_snapshot_payload(summary_payload)
    if not resolved_snapshot and not str(
        summary_payload.get("resolved_config_snapshot_id") or ""
    ).strip():
        return False
    if not resolve_session_config_snapshot(summary_payload=summary_payload):
        return False
    if require_playback:
        playback_snapshot = (
            summary_payload.get("playback_snapshot", {})
            if isinstance(summary_payload.get("playback_snapshot"), dict)
            else {}
        )
        if str(playback_snapshot.get("encoding") or "").strip().lower() != "gzip+base64":
            return False
        if not str(playback_snapshot.get("payload_b64") or "").strip():
            return False
    return True


def _resolve_summary_config_payload(
    summary_payload: Dict[str, Any],
    *,
    key: str,
) -> Dict[str, Any]:
    direct = summary_payload.get(key, {})
    direct_payload = direct if isinstance(direct, dict) else {}
    snapshot = _resolved_config_snapshot_payload(summary_payload)
    nested = snapshot.get(key, {})
    nested_payload = nested if isinstance(nested, dict) else {}
    if direct_payload and nested_payload:
        return {**nested_payload, **direct_payload}
    return direct_payload or nested_payload


def _parse_snapshot_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _decode_playback_snapshot(summary_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    snapshot_meta = (
        summary_payload.get("playback_snapshot", {})
        if isinstance(summary_payload.get("playback_snapshot"), dict)
        else {}
    )
    if not snapshot_meta:
        return None
    if str(snapshot_meta.get("encoding") or "").strip().lower() != "gzip+base64":
        return None
    encoded = str(snapshot_meta.get("payload_b64") or "").strip()
    if not encoded:
        return None
    try:
        compressed = base64.b64decode(encoded)
        decompressed = gzip.decompress(compressed)
        payload = json.loads(decompressed.decode("utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _restore_decision_markers(
    *,
    marker_rows: Any,
    run_id: str,
    ticker: str,
    date_label: str,
    marker_type_enum: Any,
) -> list[DecisionMarker]:
    if not isinstance(marker_rows, list):
        return []
    restored: list[DecisionMarker] = []
    for index, row in enumerate(marker_rows, start=1):
        if not isinstance(row, dict):
            continue
        marker_type_token = str(row.get("marker_type") or "").strip()
        if not marker_type_token:
            continue
        try:
            marker_type = marker_type_enum(marker_type_token)
        except Exception:
            continue
        timestamp = _parse_snapshot_datetime(row.get("timestamp")) or datetime.now(
            timezone.utc
        )
        try:
            bar_index = int(row.get("bar_index", index - 1) or 0)
        except Exception:
            bar_index = index - 1
        try:
            price = float(row.get("price") or 0.0)
        except Exception:
            price = 0.0
        confidence = row.get("confidence")
        if confidence is not None:
            try:
                confidence = float(confidence)
            except Exception:
                confidence = None
        restored.append(
            DecisionMarker(
                id=str(row.get("id") or f"{run_id}:{ticker}:{date_label}:{index}"),
                timestamp=timestamp,
                bar_index=max(0, bar_index),
                marker_type=marker_type,
                title=str(row.get("title") or marker_type_token),
                description=str(row.get("description") or ""),
                price=price,
                side=(
                    str(row.get("side")).strip()
                    if row.get("side") is not None
                    else None
                ),
                strategy=(
                    str(row.get("strategy")).strip()
                    if row.get("strategy") is not None
                    else None
                ),
                regime=(
                    str(row.get("regime")).strip()
                    if row.get("regime") is not None
                    else None
                ),
                confidence=confidence,
                details=(
                    dict(row.get("details"))
                    if isinstance(row.get("details"), dict)
                    else {}
                ),
            )
        )
    return restored


def restore_run_snapshot(
    run_id: str,
    ticker: str,
    date: str,
    deps: RunControlDeps,
):
    run_key = deps.run_registry.build_key(run_id, ticker, date)
    existing_runner = deps.active_runners.get(run_key)
    if existing_runner is not None:
        return {
            "success": True,
            "restored": False,
            "already_active": True,
            "run_key": run_key,
            "state": _runner_state_payload(existing_runner),
        }

    run_config_cls = getattr(deps, "run_config_cls", None)
    session_runner_cls = getattr(deps, "session_runner_cls", None)
    if run_config_cls is None or session_runner_cls is None:
        raise HTTPException(
            503,
            "Snapshot restore is unavailable in this runtime (runner classes missing).",
        )

    summary_payload, report_saved_at = _load_persisted_run_summary_by_run_key(
        run_key=run_key,
        deps=deps,
    )
    if not summary_payload:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "RUN_NOT_FOUND",
                "message": f"Run snapshot not found for {run_key}",
                "hint": "Ensure the run completed and flushed to the run-report store.",
            },
        )

    decoded_snapshot = _decode_playback_snapshot(summary_payload)
    if not _has_modern_persisted_summary(summary_payload, require_playback=True):
        raise HTTPException(
            status_code=404,
            detail=(
                "Legacy run artifacts are no longer supported. "
                "Start a new run to persist modern playback and config snapshots."
            ),
        )
    bars_payload = (
        decoded_snapshot.get("bars", [])
        if isinstance(decoded_snapshot, dict)
        and isinstance(decoded_snapshot.get("bars"), list)
        else []
    )
    marker_rows = (
        decoded_snapshot.get("markers", [])
        if isinstance(decoded_snapshot, dict)
        and isinstance(decoded_snapshot.get("markers"), list)
        else (
            summary_payload.get("markers", [])
            if isinstance(summary_payload.get("markers"), list)
            else []
        )
    )
    if not bars_payload:
        raise HTTPException(
            404,
            (
                "Playback snapshot is not available for this run. "
                "Run it again once with snapshot persistence enabled."
            ),
        )

    request_config = _resolve_summary_config_payload(
        summary_payload,
        key="run_request_config",
    )
    execution_config = _resolve_summary_config_payload(
        summary_payload,
        key="execution_config",
    )
    report_metadata = _resolve_summary_config_payload(
        summary_payload,
        key="report_metadata",
    )
    control_plane_snapshot = _resolve_summary_config_payload(
        summary_payload,
        key="control_plane_snapshot",
    )
    aos_applied = _resolve_summary_config_payload(summary_payload, key="aos_applied")
    l2_applied = _resolve_summary_config_payload(summary_payload, key="l2_applied")
    resolved_config_snapshot = _resolved_config_snapshot_payload(summary_payload)
    session_config_snapshot = resolve_session_config_snapshot(summary_payload=summary_payload)

    run_date_label = str(summary_payload.get("date") or date or "").strip() or date
    date_from = str(request_config.get("date_from") or "").strip()
    date_to = str(request_config.get("date_to") or "").strip()
    if not date_from:
        if "_to_" in run_date_label:
            date_from = run_date_label.split("_to_", 1)[0]
        else:
            date_from = run_date_label
    if not date_to:
        if "_to_" in run_date_label:
            date_to = run_date_label.split("_to_", 1)[1]
        else:
            date_to = run_date_label

    trade_eval_mode = str(
        execution_config.get("trade_eval_mode")
        or request_config.get("trade_eval_mode")
        or ""
    ).strip()
    intrabar_enabled = bool(
        request_config.get("intrabar_execution_recalc_1s")
        or trade_eval_mode.startswith("intrabar")
    )
    try:
        intrabar_step_seconds = int(
            execution_config.get("intrabar_eval_step_seconds")
            or request_config.get("intrabar_eval_step_seconds")
            or 1
        )
    except Exception:
        intrabar_step_seconds = 1

    try:
        account_size_usd = float(
            request_config.get("account_size_usd")
            or execution_config.get("account_size_usd")
            or 10_000.0
        )
    except Exception:
        account_size_usd = 10_000.0
    try:
        regime_detection_minutes = int(
            session_config_snapshot.get("regime_detection_minutes")
            or request_config.get("regime_detection_minutes")
            or 15
        )
    except Exception:
        regime_detection_minutes = 15

    config = run_config_cls(
        run_id=str(summary_payload.get("run_id") or run_id),
        ticker=str(summary_payload.get("ticker") or ticker).strip().upper(),
        date=run_date_label,
        date_from=date_from,
        date_to=date_to,
        strategy_api_url=str(
            request_config.get("strategy_api_url") or "http://localhost:8001"
        ),
        account_size_usd=account_size_usd,
        regime_detection_minutes=regime_detection_minutes,
        intrabar_execution_recalc_1s=intrabar_enabled,
        intrabar_eval_step_seconds=max(1, intrabar_step_seconds),
    )
    runner = session_runner_cls(config)
    normalized_bars = [dict(item) for item in bars_payload if isinstance(item, dict)]
    runner.load_bars(normalized_bars)
    if intrabar_enabled and getattr(deps, "l2_manager", None) is not None:
        runner.l2_manager = deps.l2_manager

    total_bars = len(normalized_bars)
    try:
        processed_bars = int(summary_payload.get("processed_bars") or total_bars)
    except Exception:
        processed_bars = total_bars
    runner.current_bar_index = max(0, min(processed_bars, total_bars))
    runner.phase = str(summary_payload.get("phase") or "COMPLETED")
    runner.is_running = False
    runner.is_paused = False
    runner.last_response = None
    runner.session_summary = (
        dict(summary_payload.get("session_summary"))
        if isinstance(summary_payload.get("session_summary"), dict)
        else None
    )
    selection_warnings = (
        [str(item).strip() for item in summary_payload.get("selection_warnings", [])]
        if isinstance(summary_payload.get("selection_warnings"), list)
        else []
    )
    runner.selection_warnings = [item for item in selection_warnings if item]
    runner._data_selection_warnings = list(runner.selection_warnings)
    runner._report_metadata = dict(report_metadata)
    runner._control_plane_snapshot = dict(control_plane_snapshot)
    runner._aos_applied = dict(aos_applied)
    runner._execution_config = dict(execution_config)
    runner._run_request_config = dict(request_config)
    runner._l2_applied = dict(l2_applied)
    runner._resolved_config_snapshot = dict(resolved_config_snapshot)
    runner._restart_session_config = dict(session_config_snapshot)
    runner._restart_session_date = date_from
    runner._checkpoint_loaded = summary_payload.get("checkpoint_loaded")
    runner._keep_in_memory_after_completion = True
    runner._progressive_loading_enabled = False
    runner._progressive_loading_complete = True
    runner._progressive_loading_loaded_until = date_to
    runner._progressive_loading_target_end = date_to
    runner._progressive_loading_pending_chunks = 0
    runner._progressive_loading_last_error = None
    runner._snapshot_restored = True
    runner._snapshot_source_mode = "persisted_playback"
    runner._snapshot_report_saved_at = report_saved_at
    runner._execution_state_manager.lifecycle = ExecutionLifecycle.END_OF_DAY
    runner._execution_state_manager.position_active = False
    runner._execution_state_manager.pending_entry = False

    restored_markers = _restore_decision_markers(
        marker_rows=marker_rows,
        run_id=config.run_id,
        ticker=config.ticker,
        date_label=config.date,
        marker_type_enum=deps.marker_type_enum,
    )
    if restored_markers:
        runner.decision_tracker.markers = restored_markers
        runner.decision_tracker._marker_counter = len(restored_markers)

    deps.active_runners[run_key] = runner
    return {
        "success": True,
        "restored": True,
        "already_active": False,
        "run_key": run_key,
        "bars_count": total_bars,
        "markers_count": len(restored_markers),
        "state": _runner_state_payload(runner),
    }


def get_run_state(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    return _runner_state_payload(runner)


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
    _guard_snapshot_runner_mutation(runner, action="step")

    payload = await _read_raw_request_payload(raw_request)
    normalized_trade_mode = _resolve_requested_trade_eval_mode(
        request=request,
        payload=payload,
    )
    if normalized_trade_mode is not None:
        _set_runner_trade_eval_mode(runner, deps, normalized_trade_mode)

    # Apply threshold overrides atomically before stepping
    threshold_overrides = (payload or {}).get("threshold_overrides")
    if isinstance(threshold_overrides, dict) and threshold_overrides:
        strategy_api_url = str(
            getattr(getattr(runner, "config", None), "strategy_api_url", "") or ""
        ).strip()
        if strategy_api_url:
            from src.services.strategy_api_session_service import apply_orchestrator_config
            integration_deps = _strategy_api_session_deps(deps.logger)
            await apply_orchestrator_config(strategy_api_url, threshold_overrides, integration_deps)

    # Seek to scrubbed position if requested
    seek_to = (payload or {}).get("seek_to_bar_index")
    if seek_to is not None:
        try:
            seek_idx = int(seek_to)
            total = len(getattr(runner, "bars", []) or [])
            if 0 <= seek_idx < total:
                runner.current_bar_index = seek_idx
                runner.is_running = False
                runner.is_paused = False
                runner.phase = "PAUSED"
        except (TypeError, ValueError):
            pass

    result = await runner.step()
    if isinstance(result, dict):
        out = dict(result)
        out["trade_eval_mode"] = _effective_runner_trade_eval_mode(runner)
        out["intrabar_eval_step_seconds"] = int(
            getattr(runner.config, "intrabar_eval_step_seconds", 1) or 1
        )
        return _to_json_compatible(out)
    return _to_json_compatible({
        "success": bool(result),
        "trade_eval_mode": _effective_runner_trade_eval_mode(runner),
        "intrabar_eval_step_seconds": int(
            getattr(runner.config, "intrabar_eval_step_seconds", 1) or 1
        ),
    })


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
    run_key, runner = deps.run_registry.require(run_id, ticker, date)
    _guard_snapshot_runner_mutation(runner, action="play")
    payload = await _read_raw_request_payload(raw_request)
    requested_keep_in_memory = _coerce_optional_bool(
        (payload or {}).get("keep_in_memory_after_completion")
    )
    if requested_keep_in_memory is not None:
        setattr(runner, "_keep_in_memory_after_completion", requested_keep_in_memory)

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

    # Apply threshold overrides atomically before playing
    threshold_overrides = (payload or {}).get("threshold_overrides")
    if isinstance(threshold_overrides, dict) and threshold_overrides:
        strategy_api_url = str(
            getattr(getattr(runner, "config", None), "strategy_api_url", "") or ""
        ).strip()
        if strategy_api_url:
            from src.services.strategy_api_session_service import apply_orchestrator_config
            integration_deps = _strategy_api_session_deps(deps.logger)
            await apply_orchestrator_config(strategy_api_url, threshold_overrides, integration_deps)

    # Seek to scrubbed position if requested
    seek_to = (payload or {}).get("seek_to_bar_index")
    if seek_to is not None:
        try:
            seek_idx = int(seek_to)
            total = len(getattr(runner, "bars", []) or [])
            if 0 <= seek_idx < total:
                runner.current_bar_index = seek_idx
                runner.is_running = False
                runner.is_paused = False
                runner.phase = "PAUSED"
        except (TypeError, ValueError):
            pass

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
            "intrabar_eval_step_seconds": int(
                getattr(runner.config, "intrabar_eval_step_seconds", 1) or 1
            ),
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
        try:
            await runner.run_all(speed_ms=raw_speed)
        except Exception as exc:
            deps.logger.error("run_all failed for %s: %s", run_key, exc)
            return

        try:
            await _persist_runner_summary_to_store(runner, deps)
        except Exception as exc:
            deps.logger.error(
                "Failed to persist run summary to external report store: %s", exc
            )

        if getattr(runner, "_checkpoint_auto_save", False):
            url = getattr(runner, "_checkpoint_strategy_url", "")
            if url:
                try:
                    await deps.save_remote_checkpoint(
                        url,
                        run_id=runner.config.run_id,
                        ticker=runner.config.ticker,
                        date_from=runner.config.date_from or runner.config.date,
                        date_to=runner.config.date_to or runner.config.date,
                    )
                except Exception as exc:
                    deps.logger.error(
                        "Failed to auto-save checkpoint for %s: %s", run_key, exc
                    )

        if _runner_completed_successfully(runner):
            should_flush_completed_runs = _env_flag(
                "BACKTEST_AUTO_FLUSH_COMPLETED_RUNS",
                True,
            )
            keep_in_memory = bool(
                getattr(runner, "_keep_in_memory_after_completion", False)
            )
            if should_flush_completed_runs and not keep_in_memory:
                await _flush_runner_from_memory(
                    run_key=run_key,
                    runner=runner,
                    deps=deps,
                )

    asyncio.create_task(_run_and_maybe_save())
    return {
        "success": True,
        "speed_ms": raw_speed,
        "trade_eval_mode": effective_trade_mode,
        "intrabar_eval_step_seconds": int(
            getattr(runner.config, "intrabar_eval_step_seconds", 1) or 1
        ),
    }


def pause_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    runner.pause()
    return {"success": True, "is_paused": True}


def resume_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    _guard_snapshot_runner_mutation(runner, action="resume")
    runner.resume()
    return {"success": True, "is_paused": False}


def stop_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    runner.stop()
    return {"success": True, "stopped": True}


async def restart_run(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    _guard_snapshot_runner_mutation(runner, action="restart")

    if getattr(runner, "is_running", False):
        raise HTTPException(
            409, "Cannot restart while run is active. Pause/stop first."
        )

    restart_config = _resolve_restart_session_config(runner=runner, deps=deps)
    if not restart_config:
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

    return {"success": True, "restarted": True, "state": _runner_state_payload(runner)}


def get_processed_bars(
    run_id: str,
    ticker: str,
    date: str,
    deps: RunControlDeps,
    since_index: Optional[int] = None,
):
    _, runner = deps.run_registry.require(run_id, ticker, date)
    _guard_snapshot_runner_mutation(runner, action="evaluate intrabar slices")
    bars = _safe_runner_processed_bars(runner)
    total_bars = len(getattr(runner, "bars", []) or [])
    current_index = int(getattr(runner, "current_bar_index", 0) or 0)
    payload_mode = "full"
    normalized_since: Optional[int] = None

    if since_index is not None:
        payload_mode = "delta"
        normalized_since = max(0, int(since_index))
        if normalized_since <= len(bars):
            bars = bars[normalized_since:]
        else:
            # Defensive fallback: client requested an index beyond current
            # progress; return empty delta instead of forcing full resend.
            bars = []

    return {
        "bars": _to_json_compatible(bars),
        "current_index": current_index,
        "total_bars": total_bars,
        "mode": payload_mode,
        "since_index": normalized_since,
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


def get_run_summary_db(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    run_key = deps.run_registry.build_key(run_id, ticker, date)

    # Check RAM first
    runner = deps.active_runners.get(run_key)
    if runner is not None:
        return runner.get_summary()

    # Fallback to DB
    store = getattr(deps, "run_reports_store", None)
    if store is not None and hasattr(store, "get_run_summary"):
        try:
            db_result = store.get_run_summary(run_key=run_key)
            if db_result and "summary" in db_result:
                summary = (
                    db_result["summary"]
                    if isinstance(db_result.get("summary"), dict)
                    else {}
                )
                hydrated = _hydrate_persisted_run_summary(
                    summary=summary,
                    run_key=run_key,
                    report_store=store,
                    logger=deps.logger,
                )
                if not _has_modern_persisted_summary(hydrated):
                    raise HTTPException(
                        status_code=404,
                        detail={
                            "error_code": "RUN_NOT_FOUND",
                            "message": (
                                "Legacy run summary is no longer supported. "
                                f"Start a new run for {run_key}."
                            ),
                            "hint": "Only modern snapshot-backed persisted runs are readable.",
                        },
                    )
                return hydrated
        except HTTPException:
            raise
        except Exception as exc:
            deps.logger.error("Failed to read run summary from DB for %s: %s", run_key, exc)

    raise HTTPException(
        status_code=404,
        detail={
            "error_code": "RUN_NOT_FOUND",
            "message": f"Run summary not found in RAM or DB: {run_key}",
            "hint": "Ensure the run actually completed and flushed correctly."
        }
    )


def get_run_status(run_id: str, ticker: str, date: str, deps: RunControlDeps):
    run_key = deps.run_registry.build_key(run_id, ticker, date)
    
    # Check RAM first
    runner = deps.active_runners.get(run_key)
    if runner is not None:
        state = runner.get_state()
        return {
            "run_key": run_key,
            "state": (
                "snapshot_restored_in_ram"
                if _snapshot_backed_runner(runner)
                else ("running" if state.get("is_running") else "active_in_ram")
            ),
            "phase": state.get("phase"),
            "persisted": bool(_snapshot_backed_runner(runner)),
            "snapshot_backed": bool(_snapshot_backed_runner(runner)),
        }

    # Check DB
    store = getattr(deps, "run_reports_store", None)
    if store is not None and hasattr(store, "get_run_summary"):
        try:
            db_result = store.get_run_summary(run_key=run_key)
            if db_result and "summary" in db_result:
                return {
                    "run_key": run_key,
                    "state": "flushed_to_db",
                    "phase": db_result["summary"].get("phase", "completed"),
                    "persisted": True
                }
        except Exception:
            pass

    raise HTTPException(
        status_code=404,
        detail={
            "error_code": "RUN_NOT_FOUND",
            "message": f"Run not found anywhere: {run_key}"
        }
    )


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


async def update_orchestrator_config(
    run_id: str,
    ticker: str,
    date: str,
    config: Dict[str, Any],
    deps: RunControlDeps,
) -> Dict[str, Any]:
    """Proxy orchestrator config update to the strategy API for an active run."""
    _, runner = deps.run_registry.require(run_id, ticker, date)
    strategy_api_url = str(
        getattr(getattr(runner, "config", None), "strategy_api_url", "") or ""
    ).strip()
    if not strategy_api_url:
        raise HTTPException(500, "Run has no strategy_api_url configured.")

    from src.services.strategy_api_session_service import apply_orchestrator_config
    integration_deps = _strategy_api_session_deps(deps.logger)
    result = await apply_orchestrator_config(strategy_api_url, config, integration_deps)
    return result if isinstance(result, dict) else {}
