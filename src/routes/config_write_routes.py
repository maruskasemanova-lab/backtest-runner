from fastapi import APIRouter, Depends

from src.models.config_requests import (
    AOSUpdateRequest,
    AdaptiveTunerProfileApplyRequest,
    PositioningUpdateRequest,
    StrategyComboApplyRequest,
    StrategyComboCaptureRequest,
)
from src.routes.context import ApiServices, get_api_services
from src.services.config_write_service import (
    apply_adaptive_tuner_profile,
    apply_strategy_combo,
    capture_strategy_combo,
    update_aos_config,
    update_positioning_config,
)

router = APIRouter()


@router.post("/api/strategy-combos/capture")
async def capture_strategy_combo_endpoint(
    request: StrategyComboCaptureRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Capture current strategy API settings into a saved ticker combo profile."""
    return await capture_strategy_combo(request, services.build_config_write_deps())


@router.post("/api/strategy-combos/apply")
async def apply_strategy_combo_endpoint(
    request: StrategyComboApplyRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Set active strategy combo profile and optionally apply it immediately."""
    return await apply_strategy_combo(request, services.build_config_write_deps())


@router.post("/api/aos-config/update")
async def update_aos_config_endpoint(
    request: AOSUpdateRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Update AOS config for a specific ticker."""
    return update_aos_config(request, services.build_config_write_deps())


@router.post("/api/positioning-config/update")
async def update_positioning_config_endpoint(
    request: PositioningUpdateRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Update positioning config for a specific ticker."""
    return update_positioning_config(request, services.build_config_write_deps())


@router.post("/api/adaptive-tuner/profiles/apply")
async def apply_adaptive_tuner_profile_endpoint(
    request: AdaptiveTunerProfileApplyRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Apply a saved adaptive-tuner profile into active ticker AOS settings."""
    return apply_adaptive_tuner_profile(request, services.build_config_write_deps())
