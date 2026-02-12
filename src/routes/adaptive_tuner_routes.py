from fastapi import APIRouter, Depends

from src.models.tuner_requests import AdaptiveTunerRequest
from src.routes.context import ApiServices, get_api_services
from src.services.adaptive_tuner_orchestration_service import (
    get_adaptive_tuner_job,
    list_adaptive_tuner_jobs,
    run_adaptive_tuner,
)

router = APIRouter()


@router.post("/api/adaptive-tuner/run")
async def run_adaptive_tuner_endpoint(
    request: AdaptiveTunerRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Start an adaptive-tuner job (v1 or v2) and return a job id for polling."""
    return await run_adaptive_tuner(request, services.build_adaptive_tuner_deps())


@router.get("/api/adaptive-tuner/{job_id}")
async def get_adaptive_tuner_job_endpoint(
    job_id: str,
    services: ApiServices = Depends(get_api_services),
):
    """Get current status and results of an adaptive tuner job."""
    return get_adaptive_tuner_job(job_id, services.build_adaptive_tuner_deps())


@router.get("/api/adaptive-tuner")
async def list_adaptive_tuner_jobs_endpoint(
    limit: int = 20,
    services: ApiServices = Depends(get_api_services),
):
    """List recent adaptive tuner jobs."""
    return list_adaptive_tuner_jobs(services.build_adaptive_tuner_deps(), limit)
