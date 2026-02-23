"""
Strategy API Client - Communication with strategy API service.

This module handles all HTTP communication with the strategy API including:
- Fetching remote strategies
- Applying strategy parameters
- Applying overrides and trailing stops
- Managing strategy combos and tuner profiles
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

import aiohttp


logger = logging.getLogger("StrategyApiClient")


async def fetch_remote_strategies(strategy_api_url: str) -> Dict[str, Any]:
    """
    Fetch current strategies from strategy API.

    Args:
        strategy_api_url: URL of the strategy API

    Returns:
        Dictionary of strategy configurations
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{strategy_api_url}/api/strategies") as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"Failed to fetch strategies: HTTP {resp.status}")
                return {}
    except Exception as e:
        logger.warning(f"Error fetching strategies: {e}")
        return {}


async def apply_strategy_param_map(
    strategy_api_url: str,
    strategy_params: Dict[str, Dict[str, Any]],
    sanitize_strategy_params_func: Optional[
        Callable[[Dict[str, Any]], Dict[str, Any]]
    ] = None,
) -> Dict[str, Any]:
    """
    Apply strategy parameter map to strategy API.

    Args:
        strategy_api_url: URL of the strategy API
        strategy_params: Map of strategy name to parameters
        sanitize_strategy_params_func: Optional function to sanitize params

    Returns:
        Result dictionary with applied/failed counts
    """
    applied_strategies: List[str] = []
    failed_strategies: List[str] = []

    for strategy_name, params in strategy_params.items():
        if not isinstance(params, dict):
            continue

        # Sanitize if function provided
        clean_params = params
        if sanitize_strategy_params_func:
            clean_params = sanitize_strategy_params_func(params)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{strategy_api_url}/api/strategies/update",
                    json={"strategy_name": strategy_name, "params": clean_params},
                ) as resp:
                    if resp.status == 200:
                        applied_strategies.append(strategy_name)
                    else:
                        failed_strategies.append(strategy_name)
                        logger.warning(
                            f"Strategy update failed for {strategy_name}: HTTP {resp.status}"
                        )
        except Exception as e:
            failed_strategies.append(strategy_name)
            logger.warning(f"Strategy update error for {strategy_name}: {e}")

    return {
        "applied_strategies": applied_strategies,
        "failed_strategies": failed_strategies,
        "applied_count": len(applied_strategies),
        "failed_count": len(failed_strategies),
    }


async def apply_strategy_overrides(
    strategy_api_url: str,
    ticker: str,
    overrides: Optional[Dict[str, Any]],
) -> None:
    """
    Apply strategy overrides for a ticker.

    Args:
        strategy_api_url: URL of the strategy API
        ticker: Ticker symbol
        overrides: Override configuration
    """
    if not overrides or not isinstance(overrides, dict):
        return

    strategy_name = overrides.get("strategy")
    params = overrides.get("params", {})

    if not strategy_name:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/strategies/update",
                json={"strategy_name": strategy_name, "params": params},
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Applied overrides for {ticker}: {strategy_name}")
                else:
                    logger.warning(f"Override failed for {ticker}: HTTP {resp.status}")
    except Exception as e:
        logger.warning(f"Override error for {ticker}: {e}")


async def apply_global_trailing(
    strategy_api_url: str,
    trailing_stop_pct: Optional[float],
) -> None:
    """
    Apply global trailing stop to all strategies.

    Args:
        strategy_api_url: URL of the strategy API
        trailing_stop_pct: Trailing stop percentage
    """
    if trailing_stop_pct is None:
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/strategies/trailing",
                json={"trailing_stop_pct": trailing_stop_pct},
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Applied global trailing: {trailing_stop_pct}%")
                else:
                    logger.warning(f"Global trailing failed: HTTP {resp.status}")
    except Exception as e:
        logger.warning(f"Global trailing error: {e}")
