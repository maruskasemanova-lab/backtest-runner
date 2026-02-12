from fastapi import APIRouter, Depends

from src.models.run_requests import StartRunRequest
from src.routes.context import ApiServices, get_api_services

router = APIRouter()


@router.post("/api/run/start")
async def start_run_endpoint(
    request: StartRunRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Start a new backtest run."""
    return await services.start_run(request)
