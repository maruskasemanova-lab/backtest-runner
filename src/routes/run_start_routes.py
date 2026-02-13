from fastapi import APIRouter, Depends, Query

from src.models.run_requests import PrewarmRunRequest, StartRunRequest
from src.routes.context import ApiServices, get_api_services
from src.services.start_run_data_service import flush_start_run_data_cache

router = APIRouter()


@router.post("/api/run/start")
async def start_run_endpoint(
    request: StartRunRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Start a new backtest run."""
    return await services.start_run(request)


@router.post("/api/run/prewarm")
async def prewarm_run_endpoint(
    request: PrewarmRunRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Prewarm bars/L2/reference caches for the requested range."""
    return await services.prewarm_run(request)


@router.post("/api/run/prewarm/status")
async def prewarm_status_endpoint(
    request: PrewarmRunRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Check prewarm readiness/in-flight state without triggering heavy loads."""
    return await services.prewarm_status(request)


@router.post("/api/run/cache/flush")
async def flush_run_cache_endpoint(
    include_disk: bool = Query(default=False),
):
    """Flush cached run-start data (memory, optional disk)."""
    return flush_start_run_data_cache(include_disk=bool(include_disk))
