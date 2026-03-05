from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.routes.context import ApiServices, get_api_services
from src.routes.unified_profile_user_store import (
    build_user_unified_profile_options_payload,
)
from src.services.config_domain import (
    TickerConfigRepositoryDeps,
    build_ticker_display_payload,
    load_ticker_config_aggregate,
)

router = APIRouter()


def _build_ticker_config_repository_deps(
    services: ApiServices,
) -> TickerConfigRepositoryDeps:
    config_write_deps = services.build_config_write_deps()
    return TickerConfigRepositoryDeps(
        load_aos_config=services.load_aos_config,
        get_ticker_positioning_config=services.get_ticker_positioning_config,
        normalize_strategy_combo_profiles=(
            config_write_deps.normalize_strategy_combo_profiles
        ),
        normalize_unified_profiles=config_write_deps.normalize_unified_profiles,
        normalize_tuner_profiles=config_write_deps.normalize_tuner_profiles,
        positioning_config_keys=services.positioning_config_keys,
    )


@router.get("/api/strategy-overrides")
async def get_strategy_overrides(services: ApiServices = Depends(get_api_services)):
    """Get optimized strategy parameters per ticker."""
    return services.load_strategy_overrides()


@router.get("/api/strategy-overrides/{ticker}")
async def get_ticker_overrides(
    ticker: str, services: ApiServices = Depends(get_api_services)
):
    """Get optimized strategy parameters for a specific ticker."""
    overrides = services.load_strategy_overrides()
    return overrides.get(ticker.upper(), {})


@router.get("/api/strategy-combos/{ticker}")
async def get_strategy_combos(
    ticker: str, services: ApiServices = Depends(get_api_services)
):
    """Get saved strategy-parameter combo profiles for a ticker."""
    return services.build_strategy_combo_options_payload(ticker)


@router.get("/api/aos-config")
async def get_aos_config(services: ApiServices = Depends(get_api_services)):
    """Get full AOS optimization config."""
    aos_config = services.load_aos_config()
    positioning_config = services.load_positioning_config()
    return services.merge_positioning_into_aos_snapshot(aos_config, positioning_config)


@router.get("/api/aos-config/{ticker}")
async def get_ticker_aos_config(
    ticker: str, services: ApiServices = Depends(get_api_services)
):
    """Get AOS config for a specific ticker."""
    aggregate = load_ticker_config_aggregate(
        ticker=ticker,
        deps=_build_ticker_config_repository_deps(services),
    )
    return build_ticker_display_payload(aggregate)


@router.get("/api/positioning-config")
async def get_positioning_config(services: ApiServices = Depends(get_api_services)):
    """Get full positioning config file."""
    return services.load_positioning_config()


@router.get("/api/positioning-config/{ticker}")
async def get_ticker_positioning_config(
    ticker: str, services: ApiServices = Depends(get_api_services)
):
    """Get positioning config for one ticker."""
    return services.get_ticker_positioning_config(ticker)


@router.get("/api/adaptive-tuner/options/{ticker}")
async def get_adaptive_tuner_options(
    ticker: str, services: ApiServices = Depends(get_api_services)
):
    """Get real coverage ranges and saved tuner profiles for a ticker."""
    return services.build_adaptive_tuner_options_payload(ticker)


@router.get("/api/profiles/{ticker}")
async def get_unified_profiles(
    ticker: str,
    request: Request,
    services: ApiServices = Depends(get_api_services),
):
    """Get saved unified strategy+execution profiles for a ticker."""
    base_payload = services.build_unified_profile_options_payload(ticker)
    config_write_deps = services.build_config_write_deps()
    return build_user_unified_profile_options_payload(
        request=request,
        ticker=ticker,
        base_payload=base_payload,
        load_aos_config=services.load_aos_config,
        normalize_unified_profiles=config_write_deps.normalize_unified_profiles,
    )


@router.get("/api/aos-history/{ticker}")
async def get_aos_history(
    ticker: str,
    limit: int = Query(default=1000, ge=1, le=5000),
    services: ApiServices = Depends(get_api_services),
):
    """Get historical AOS changes for a specific ticker from DB-backed store."""
    ticker_upper = str(ticker or "").strip().upper()
    if not ticker_upper:
        raise HTTPException(status_code=400, detail="ticker is required")

    store = getattr(services, "state_store", None)
    list_fn = getattr(store, "list_aos_history_entries", None)
    if not callable(list_fn):
        return []

    try:
        rows = list_fn(ticker=ticker_upper, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read AOS history from store: {exc}",
        ) from exc
    return rows if isinstance(rows, list) else []
