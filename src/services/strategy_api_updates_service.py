from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from fastapi import HTTPException

from src.services.strategy_api_types import StrategyApiIntegrationDeps


def _parse_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return max(1, int(default))
    try:
        return max(1, int(str(raw).strip()))
    except (TypeError, ValueError):
        return max(1, int(default))


def _parse_positive_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return max(0.1, float(default))
    try:
        return max(0.1, float(str(raw).strip()))
    except (TypeError, ValueError):
        return max(0.1, float(default))


_STRATEGY_UPDATE_MAX_CONCURRENCY = _parse_positive_int_env(
    "BACKTEST_STRATEGY_UPDATE_MAX_CONCURRENCY",
    8,
)
_STRATEGY_API_TIMEOUT_SECONDS = _parse_positive_float_env(
    "BACKTEST_STRATEGY_API_TIMEOUT_SECONDS",
    6.0,
)
_STRATEGY_API_CLIENT_TIMEOUT = aiohttp.ClientTimeout(
    total=_STRATEGY_API_TIMEOUT_SECONDS,
    connect=min(_STRATEGY_API_TIMEOUT_SECONDS, 3.0),
)


async def _post_strategy_update(
    session: aiohttp.ClientSession,
    *,
    strategy_api_url: str,
    strategy_name: str,
    params: Dict[str, Any],
) -> Tuple[str, int | None, str | None]:
    try:
        async with session.post(
            f"{strategy_api_url}/api/strategies/update",
            json={"strategy_name": strategy_name, "params": params},
        ) as resp:
            return strategy_name, int(resp.status), None
    except Exception as exc:
        return strategy_name, None, str(exc)


async def _run_strategy_updates(
    *,
    strategy_api_url: str,
    updates: List[Tuple[str, Dict[str, Any]]],
) -> List[Tuple[str, int | None, str | None]]:
    if not updates:
        return []
    semaphore = asyncio.Semaphore(_STRATEGY_UPDATE_MAX_CONCURRENCY)
    async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
        async def _bounded_update(
            strategy_name: str,
            params: Dict[str, Any],
        ) -> Tuple[str, int | None, str | None]:
            async with semaphore:
                return await _post_strategy_update(
                    session,
                    strategy_api_url=strategy_api_url,
                    strategy_name=strategy_name,
                    params=params,
                )

        tasks = [
            asyncio.create_task(_bounded_update(strategy_name, params))
            for strategy_name, params in updates
        ]
        return await asyncio.gather(*tasks)


async def apply_strategy_overrides(
    strategy_api_url: str,
    ticker: str,
    deps: StrategyApiIntegrationDeps,
) -> None:
    overrides = deps.load_strategy_overrides().get(ticker.upper())
    if not overrides:
        return
    updates = [
        (str(strat_name), dict(params or {}))
        for strat_name, params in overrides.items()
    ]
    results = await _run_strategy_updates(
        strategy_api_url=strategy_api_url,
        updates=updates,
    )
    for strat_name, status, error in results:
        if error:
            deps.logger.warning(f"Override error for {ticker}:{strat_name}: {error}")
            continue
        if status != 200:
            deps.logger.warning(
                f"Override failed for {ticker}:{strat_name} (HTTP {status})"
            )


async def fetch_remote_strategies(
    strategy_api_url: str,
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
        async with session.get(f"{strategy_api_url}/api/strategies") as resp:
            if resp.status != 200:
                raise HTTPException(
                    502,
                    f"Failed to fetch strategies from strategy API (HTTP {resp.status})",
                )
            payload = await resp.json()
    if not isinstance(payload, dict):
        raise HTTPException(502, "Strategy API /api/strategies returned invalid payload.")
    return payload


async def apply_strategy_param_map(
    strategy_api_url: str,
    strategy_params: Dict[str, Dict[str, Any]],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    applied: List[str] = []
    failed: List[Dict[str, Any]] = []
    updates: List[Tuple[str, Dict[str, Any]]] = []
    for strat_name, params in strategy_params.items():
        clean_params = deps.sanitize_strategy_params(params)
        if not clean_params:
            continue
        updates.append((str(strat_name), clean_params))

    results = await _run_strategy_updates(
        strategy_api_url=strategy_api_url,
        updates=updates,
    )
    for strat_name, status, error in results:
        if error:
            failed.append({"strategy": strat_name, "error": error})
        elif status == 200:
            applied.append(strat_name)
        else:
            failed.append({"strategy": strat_name, "status": status})
    return {
        "applied_strategies": applied,
        "failed_strategies": failed,
        "applied_count": len(applied),
        "failed_count": len(failed),
    }


async def apply_global_trailing(
    strategy_api_url: str,
    trailing_stop_pct: Optional[float],
    deps: StrategyApiIntegrationDeps,
) -> None:
    if trailing_stop_pct is None:
        return
    if trailing_stop_pct <= 0:
        deps.logger.warning("Global trailing_stop_pct ignored (must be > 0).")
        return
    try:
        async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
            async with session.get(f"{strategy_api_url}/api/strategies") as resp:
                if resp.status != 200:
                    deps.logger.warning(
                        f"Failed to fetch strategies for global trailing (HTTP {resp.status})"
                    )
                    return
                strategies = await resp.json()
        if not isinstance(strategies, dict):
            deps.logger.warning("Failed to parse strategies for global trailing (invalid payload).")
            return
        updates = [
            (str(name), {"trailing_stop_pct": trailing_stop_pct})
            for name in strategies.keys()
        ]
        results = await _run_strategy_updates(
            strategy_api_url=strategy_api_url,
            updates=updates,
        )
        for name, status, error in results:
            if error:
                deps.logger.warning(f"Global trailing update error for {name}: {error}")
            elif status != 200:
                deps.logger.warning(
                    f"Global trailing update failed for {name} (HTTP {status})"
                )
    except Exception as exc:
        deps.logger.warning(f"Global trailing update failed: {exc}")
