from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.routes.context import ApiServices, get_api_services
from src.services.file_store_migration_service import sync_live_trader_artifacts_to_store
from src.services.live_trader_service import (
    infer_live_run_status,
    sanitize_live_run_id,
)

router = APIRouter()


def _supports_db_live_trader(store: Any) -> bool:
    return bool(
        callable(getattr(store, "list_live_trader_runs", None))
        and callable(getattr(store, "list_live_trader_events", None))
        and callable(getattr(store, "get_live_trader_stream_stats", None))
    )


@router.get("/api/live-trader/runs")
async def list_live_trader_runs(
    limit: int = 20,
    active_only: bool = False,
    services: ApiServices = Depends(get_api_services),
):
    """List discovered ibkr-realtime-trader runs from DB-backed event store."""
    artifacts_dir = services.get_live_trader_artifacts_dir()
    store = getattr(services, "state_store", None)
    if not _supports_db_live_trader(store):
        raise HTTPException(
            503,
            "Live trader DB store is not configured (missing live_trader_events backend).",
        )
    sync_live_trader_artifacts_to_store(
        artifacts_dir=artifacts_dir,
        store=store,
        logger=services.logger,
    )
    runs = store.list_live_trader_runs(
        limit=limit,
        active_only=active_only,
        active_window_seconds=services.live_run_active_window_seconds,
    )
    return {
        "source_mode": "sqlite_live_trader_events",
        "artifacts_dir": str(artifacts_dir),
        "count": len(runs),
        "active_only": bool(active_only),
        "runs": runs,
    }


@router.get("/api/live-trader/events/{run_id}")
async def get_live_trader_events(
    run_id: str,
    stream: str = "decisions",
    limit: int = 200,
    services: ApiServices = Depends(get_api_services),
):
    """Get tail events for one stream (runtime/decisions/signals/orders)."""
    artifacts_dir = services.get_live_trader_artifacts_dir()
    store = getattr(services, "state_store", None)
    if not _supports_db_live_trader(store):
        raise HTTPException(
            503,
            "Live trader DB store is not configured (missing live_trader_events backend).",
        )
    run_id_safe = sanitize_live_run_id(run_id)
    stream_key = str(stream or "decisions").strip().lower()
    if stream_key not in {"runtime", "decisions", "signals", "orders"}:
        raise HTTPException(
            400, "stream must be one of: runtime, decisions, signals, orders"
        )
    sync_live_trader_artifacts_to_store(
        artifacts_dir=artifacts_dir,
        store=store,
        logger=services.logger,
    )
    events = store.list_live_trader_events(
        run_id=run_id_safe,
        stream=stream_key,
        limit=limit,
    )
    if not events:
        raise HTTPException(
            404,
            f"Live stream data not found in DB for run_id={run_id_safe} stream={stream_key}",
        )
    return {
        "run_id": run_id_safe,
        "stream": stream_key,
        "count": len(events),
        "events": events,
    }


@router.get("/api/live-trader/snapshot/{run_id}")
async def get_live_trader_snapshot(
    run_id: str,
    tail_limit: int = 200,
    services: ApiServices = Depends(get_api_services),
):
    """Get latest records and counts from all live-trader streams for one run."""
    artifacts_dir = services.get_live_trader_artifacts_dir()
    store = getattr(services, "state_store", None)
    if not _supports_db_live_trader(store):
        raise HTTPException(
            503,
            "Live trader DB store is not configured (missing live_trader_events backend).",
        )
    run_id_safe = sanitize_live_run_id(run_id)
    sync_live_trader_artifacts_to_store(
        artifacts_dir=artifacts_dir,
        store=store,
        logger=services.logger,
    )
    streams = {}
    total_count = 0
    updated_at = None
    for stream_key in ("runtime", "decisions", "signals", "orders"):
        stats = store.get_live_trader_stream_stats(
            run_id=run_id_safe,
            stream=stream_key,
        )
        count = int(stats.get("count") or 0) if isinstance(stats, dict) else 0
        stream_updated = (
            str(stats.get("updated_at") or "").strip()
            if isinstance(stats, dict)
            else ""
        )
        latest = stats.get("latest") if isinstance(stats, dict) else None
        streams[stream_key] = {
            "exists": count > 0,
            "count": count,
            "latest": latest if isinstance(latest, dict) else None,
            "updated_at": stream_updated or None,
        }
        total_count += count
        if stream_updated and (updated_at is None or stream_updated > updated_at):
            updated_at = stream_updated
    if total_count <= 0:
        raise HTTPException(
            404,
            f"No live-trader events found in DB for run_id={run_id_safe}",
        )
    runtime_latest = streams.get("runtime", {}).get("latest")
    runtime_summary = runtime_latest if isinstance(runtime_latest, dict) else None
    status = infer_live_run_status(
        updated_at,
        runtime_summary,
        active_window_seconds=services.live_run_active_window_seconds,
    )
    return {
        "run_id": run_id_safe,
        "tail_limit": max(1, min(2000, int(tail_limit))),
        "total_count": total_count,
        "updated_at": updated_at,
        "status": status,
        "runtime": runtime_summary,
        "streams": streams,
    }
