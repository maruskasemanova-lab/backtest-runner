from fastapi import APIRouter, Depends

from src.routes.context import ApiServices, get_api_services
from src.services.live_trader_service import (
    discover_live_trader_runs,
    live_trader_events_payload,
    live_trader_snapshot_payload,
)

router = APIRouter()


@router.get("/api/live-trader/runs")
async def list_live_trader_runs(
    limit: int = 20,
    active_only: bool = False,
    services: ApiServices = Depends(get_api_services),
):
    """List discovered ibkr-realtime-trader runs from JSONL artifacts."""
    artifacts_dir = services.get_live_trader_artifacts_dir()
    runs = discover_live_trader_runs(
        artifacts_dir,
        limit=limit,
        active_only=active_only,
        active_window_seconds=services.live_run_active_window_seconds,
        logger=services.logger,
    )
    return {
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
    return live_trader_events_payload(
        artifacts_dir,
        run_id,
        stream=stream,
        limit=limit,
        logger=services.logger,
    )


@router.get("/api/live-trader/snapshot/{run_id}")
async def get_live_trader_snapshot(
    run_id: str,
    tail_limit: int = 200,
    services: ApiServices = Depends(get_api_services),
):
    """Get latest records and counts from all live-trader streams for one run."""
    artifacts_dir = services.get_live_trader_artifacts_dir()
    return live_trader_snapshot_payload(
        artifacts_dir,
        run_id,
        tail_limit=tail_limit,
        active_window_seconds=services.live_run_active_window_seconds,
        logger=services.logger,
    )
