from __future__ import annotations

import os
from typing import Any, Dict, Optional

import aiohttp

from src.services.strategy_api_types import StrategyApiIntegrationDeps


def _parse_positive_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return max(0.1, float(default))
    try:
        return max(0.1, float(str(raw).strip()))
    except (TypeError, ValueError):
        return max(0.1, float(default))


_STRATEGY_API_TIMEOUT_SECONDS = _parse_positive_float_env(
    "BACKTEST_STRATEGY_API_TIMEOUT_SECONDS",
    6.0,
)
_STRATEGY_API_CLIENT_TIMEOUT = aiohttp.ClientTimeout(
    total=_STRATEGY_API_TIMEOUT_SECONDS,
    connect=min(_STRATEGY_API_TIMEOUT_SECONDS, 3.0),
)


async def configure_session(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
    date: str,
    regime_detection_minutes: int,
    regime_refresh_bars: int,
    account_size_usd: float,
    risk_per_trade_pct: float,
    max_position_notional_pct: float,
    max_fill_participation_rate: float,
    min_fill_ratio: float,
    enable_partial_take_profit: bool,
    partial_take_profit_rr: float,
    partial_take_profit_fraction: float,
    trailing_activation_pct: float,
    break_even_buffer_pct: float,
    break_even_min_hold_bars: int,
    trailing_enabled_in_choppy: bool,
    time_exit_bars: int,
    adverse_flow_exit_enabled: bool,
    adverse_flow_threshold: float,
    adverse_flow_min_hold_bars: int,
    adverse_flow_consistency_threshold: float,
    adverse_book_pressure_threshold: float,
    stop_loss_mode: str,
    fixed_stop_loss_pct: float,
    l2_confirm_enabled: bool,
    l2_min_delta: float,
    l2_min_imbalance: float,
    l2_min_iceberg_bias: float,
    l2_lookback_bars: int,
    l2_min_participation_ratio: float,
    l2_min_directional_consistency: float,
    l2_min_signed_aggression: float,
    cold_start_each_day: bool,
    strategy_selection_mode: str,
    max_active_strategies: int,
    momentum_diversification_json: Optional[str],
    deps: StrategyApiIntegrationDeps,
) -> None:
    params = {
        "run_id": run_id,
        "ticker": ticker,
        "date": date,
        "regime_detection_minutes": int(regime_detection_minutes),
        "regime_refresh_bars": int(regime_refresh_bars),
        "account_size_usd": float(account_size_usd),
        "risk_per_trade_pct": float(risk_per_trade_pct),
        "max_position_notional_pct": float(max_position_notional_pct),
        "max_fill_participation_rate": float(max_fill_participation_rate),
        "min_fill_ratio": float(min_fill_ratio),
        "enable_partial_take_profit": int(bool(enable_partial_take_profit)),
        "partial_take_profit_rr": float(partial_take_profit_rr),
        "partial_take_profit_fraction": float(partial_take_profit_fraction),
        "trailing_activation_pct": float(trailing_activation_pct),
        "break_even_buffer_pct": float(break_even_buffer_pct),
        "break_even_min_hold_bars": int(break_even_min_hold_bars),
        "trailing_enabled_in_choppy": int(bool(trailing_enabled_in_choppy)),
        "time_exit_bars": int(time_exit_bars),
        "adverse_flow_exit_enabled": int(bool(adverse_flow_exit_enabled)),
        "adverse_flow_threshold": float(adverse_flow_threshold),
        "adverse_flow_min_hold_bars": int(adverse_flow_min_hold_bars),
        "adverse_flow_consistency_threshold": float(adverse_flow_consistency_threshold),
        "adverse_book_pressure_threshold": float(adverse_book_pressure_threshold),
        "stop_loss_mode": str(stop_loss_mode),
        "fixed_stop_loss_pct": float(fixed_stop_loss_pct),
        "l2_confirm_enabled": int(bool(l2_confirm_enabled)),
        "l2_min_delta": float(l2_min_delta),
        "l2_min_imbalance": float(l2_min_imbalance),
        "l2_min_iceberg_bias": float(l2_min_iceberg_bias),
        "l2_lookback_bars": int(l2_lookback_bars),
        "l2_min_participation_ratio": float(l2_min_participation_ratio),
        "l2_min_directional_consistency": float(l2_min_directional_consistency),
        "l2_min_signed_aggression": float(l2_min_signed_aggression),
        "cold_start_each_day": int(bool(cold_start_each_day)),
        "strategy_selection_mode": str(strategy_selection_mode),
        "max_active_strategies": int(max_active_strategies),
    }
    if momentum_diversification_json:
        params["momentum_diversification_json"] = str(momentum_diversification_json)
    try:
        async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
            async with session.post(
                f"{strategy_api_url}/api/session/config",
                params=params,
            ) as resp:
                if resp.status != 200:
                    deps.logger.warning(
                        f"Session config failed (HTTP {resp.status}) for {run_id}:{ticker}:{date}"
                    )
    except Exception as exc:
        deps.logger.warning(f"Session config error for {run_id}:{ticker}:{date}: {exc}")


async def clear_remote_strategy_sessions(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
    deps: StrategyApiIntegrationDeps,
) -> None:
    normalized_ticker = ticker.upper()

    async def _clear_v2(session: aiohttp.ClientSession) -> None:
        async with session.delete(
            f"{strategy_api_url}/api/session/run",
            params={"run_id": run_id, "ticker": normalized_ticker},
        ) as resp:
            if resp.status != 200:
                deps.logger.warning(
                    f"Session run-clear failed (HTTP {resp.status}) for {run_id}:{normalized_ticker}"
                )

    try:
        async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
            await _clear_v2(session)
    except Exception as exc:
        deps.logger.warning(f"Remote session cleanup error for {run_id}:{normalized_ticker}: {exc}")


async def reset_remote_orchestrator_state(
    strategy_api_url: str,
    deps: StrategyApiIntegrationDeps,
) -> bool:
    try:
        async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": "all", "clear_sessions": "true"},
            ) as resp:
                if resp.status == 200:
                    return True
                if resp.status in (404, 405):
                    return False
                deps.logger.warning(
                    f"Remote orchestrator reset failed (HTTP {resp.status}) at {strategy_api_url}"
                )
                return False
    except Exception as exc:
        deps.logger.warning(f"Remote orchestrator reset error at {strategy_api_url}: {exc}")
        return False


async def reset_remote_orchestrator_state_scoped(
    strategy_api_url: str,
    scope: str,
    deps: StrategyApiIntegrationDeps,
) -> bool:
    try:
        async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": scope, "clear_sessions": "true"},
            ) as resp:
                return resp.status == 200
    except Exception as exc:
        deps.logger.warning(f"Remote orchestrator scoped reset error: {exc}")
        return False


async def load_remote_checkpoint(
    strategy_api_url: str,
    checkpoint_path: str,
    deps: StrategyApiIntegrationDeps,
) -> Optional[Dict]:
    try:
        async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/load",
                params={"path": checkpoint_path},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                deps.logger.warning(
                    f"Remote checkpoint load failed (HTTP {resp.status}): {checkpoint_path}"
                )
                return None
    except Exception as exc:
        deps.logger.warning(f"Remote checkpoint load error: {exc}")
        return None


async def save_remote_checkpoint(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
    date_from: str,
    date_to: str,
    deps: StrategyApiIntegrationDeps,
) -> Optional[str]:
    try:
        params = {
            key: value
            for key, value in {
                "run_id": run_id,
                "ticker": ticker,
                "date_from": date_from,
                "date_to": date_to,
            }.items()
            if value
        }
        async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/save",
                params=params,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    path = result.get("path")
                    deps.logger.info(f"Auto-saved checkpoint: {path}")
                    return path
                return None
    except Exception as exc:
        deps.logger.warning(f"Checkpoint auto-save error: {exc}")
        return None
