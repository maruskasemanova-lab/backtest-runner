from typing import Optional, Union

from fastapi import APIRouter, Body, Depends, Request

from src.models.run_requests import PlayRequest
from src.routes.context import ApiServices, get_api_services
from src.services.run_control_service import (
    delete_run,
    get_bar_details,
    get_chart_annotations,
    get_markers,
    get_processed_bars,
    get_run_state,
    get_run_summary,
    list_runs,
    pause_run,
    play_run,
    restart_run,
    resume_run,
    step_run,
    stop_run,
)

router = APIRouter()


@router.get("/api/run/{run_id}/{ticker}/{date}/state")
async def get_run_state_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Get current state of a run."""
    return get_run_state(run_id, ticker, date, services.build_run_control_deps())


@router.post("/api/run/{run_id}/{ticker}/{date}/step")
async def step_run_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Advance the run by one bar."""
    return await step_run(run_id, ticker, date, services.build_run_control_deps())


@router.post("/api/run/{run_id}/{ticker}/{date}/play")
async def play_run_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    request: Optional[PlayRequest] = Body(default=None),
    speed_ms: Optional[Union[int, str]] = None,
    raw_request: Request = None,
    services: ApiServices = Depends(get_api_services),
):
    """Start or resume auto-advancing through bars."""
    return await play_run(
        run_id,
        ticker,
        date,
        services.build_run_control_deps(),
        request=request,
        speed_ms=speed_ms,
        raw_request=raw_request,
    )


@router.post("/api/run/{run_id}/{ticker}/{date}/pause")
async def pause_run_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Pause a running backtest."""
    return pause_run(run_id, ticker, date, services.build_run_control_deps())


@router.post("/api/run/{run_id}/{ticker}/{date}/resume")
async def resume_run_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Resume a paused backtest."""
    return resume_run(run_id, ticker, date, services.build_run_control_deps())


@router.post("/api/run/{run_id}/{ticker}/{date}/stop")
async def stop_run_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Stop a running backtest."""
    return stop_run(run_id, ticker, date, services.build_run_control_deps())


@router.post("/api/run/{run_id}/{ticker}/{date}/restart")
async def restart_run_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Restart an existing run from bar zero using already loaded bars."""
    return await restart_run(run_id, ticker, date, services.build_run_control_deps())


@router.get("/api/run/{run_id}/{ticker}/{date}/bars")
async def get_processed_bars_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Get all processed bars so far."""
    return get_processed_bars(run_id, ticker, date, services.build_run_control_deps())


@router.get("/api/run/{run_id}/{ticker}/{date}/bar-details/{minute_key}")
async def get_bar_details_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    minute_key: int,
    services: ApiServices = Depends(get_api_services),
):
    """Get 1-second intrabar frames for a specific minute bar."""
    return get_bar_details(
        run_id, ticker, date, minute_key, services.build_run_control_deps()
    )


@router.get("/api/run/{run_id}/{ticker}/{date}/markers")
async def get_markers_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    marker_type: Optional[str] = None,
    services: ApiServices = Depends(get_api_services),
):
    """Get all decision markers."""
    return get_markers(
        run_id, ticker, date, marker_type, services.build_run_control_deps()
    )


@router.get("/api/run/{run_id}/{ticker}/{date}/chart-annotations")
async def get_chart_annotations_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Get markers formatted for chart display."""
    return get_chart_annotations(
        run_id, ticker, date, services.build_run_control_deps()
    )


@router.get("/api/run/{run_id}/{ticker}/{date}/summary")
async def get_run_summary_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Get session summary."""
    return get_run_summary(run_id, ticker, date, services.build_run_control_deps())


@router.delete("/api/run/{run_id}/{ticker}/{date}")
async def delete_run_endpoint(
    run_id: str,
    ticker: str,
    date: str,
    services: ApiServices = Depends(get_api_services),
):
    """Delete a run from memory."""
    return await delete_run(run_id, ticker, date, services.build_run_control_deps())


@router.get("/api/runs")
async def list_runs_endpoint(services: ApiServices = Depends(get_api_services)):
    """List all active runs."""
    return list_runs(services.build_run_control_deps())
