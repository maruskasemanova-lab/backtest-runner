from typing import Any, Dict

from fastapi import APIRouter, Depends

from src.routes.context import ApiServices, get_api_services

router = APIRouter()


@router.get("/api/strategy-overrides")
async def get_strategy_overrides(services: ApiServices = Depends(get_api_services)):
    """Get optimized strategy parameters per ticker."""
    return services.load_strategy_overrides()


@router.get("/api/strategy-overrides/{ticker}")
async def get_ticker_overrides(ticker: str, services: ApiServices = Depends(get_api_services)):
    """Get optimized strategy parameters for a specific ticker."""
    overrides = services.load_strategy_overrides()
    return overrides.get(ticker.upper(), {})


@router.get("/api/strategy-combos/{ticker}")
async def get_strategy_combos(ticker: str, services: ApiServices = Depends(get_api_services)):
    """Get saved strategy-parameter combo profiles for a ticker."""
    return services.build_strategy_combo_options_payload(ticker)


@router.get("/api/aos-config")
async def get_aos_config(services: ApiServices = Depends(get_api_services)):
    """Get full AOS optimization config."""
    aos_config = services.load_aos_config()
    positioning_config = services.load_positioning_config()
    return services.merge_positioning_into_aos_snapshot(aos_config, positioning_config)


@router.get("/api/aos-config/{ticker}")
async def get_ticker_aos_config(ticker: str, services: ApiServices = Depends(get_api_services)):
    """Get AOS config for a specific ticker."""
    config = services.load_aos_config()
    ticker_config = config.get("tickers", {}).get(ticker.upper(), {})
    if not isinstance(ticker_config, dict):
        ticker_config = {}

    positioning_cfg = services.get_ticker_positioning_config(ticker)
    legacy_positioning: Dict[str, Any] = {}
    for key in services.positioning_config_keys:
        if key in ticker_config:
            legacy_positioning[key] = ticker_config.get(key)

    if legacy_positioning:
        merged_positioning = dict(legacy_positioning)
        merged_positioning.update(positioning_cfg)
        positioning_cfg = merged_positioning

    if positioning_cfg:
        payload = dict(ticker_config)
        payload["positioning"] = positioning_cfg
        return payload
    return ticker_config


@router.get("/api/positioning-config")
async def get_positioning_config(services: ApiServices = Depends(get_api_services)):
    """Get full positioning config file."""
    return services.load_positioning_config()


@router.get("/api/positioning-config/{ticker}")
async def get_ticker_positioning_config(ticker: str, services: ApiServices = Depends(get_api_services)):
    """Get positioning config for one ticker."""
    return services.get_ticker_positioning_config(ticker)


@router.get("/api/adaptive-tuner/options/{ticker}")
async def get_adaptive_tuner_options(ticker: str, services: ApiServices = Depends(get_api_services)):
    """Get real coverage ranges and saved tuner profiles for a ticker."""
    return services.build_adaptive_tuner_options_payload(ticker)
