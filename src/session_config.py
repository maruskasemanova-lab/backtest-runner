"""
Session Config - Session configuration for backtest runs.

This module handles configuration of trading sessions including
risk parameters, exit rules, and L2 confirmation settings.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp


logger = logging.getLogger("SessionConfig")


async def configure_session(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
    date: str,
    regime_detection_minutes: int,
    regime_refresh_bars: int,
    account_size_usd: float,
    risk_per_trade_pct: float = 1.0,
    max_position_notional_pct: float = 100.0,
    max_fill_participation_rate: float = 0.20,
    min_fill_ratio: float = 0.35,
    enable_partial_take_profit: bool = True,
    partial_take_profit_rr: float = 1.0,
    partial_take_profit_fraction: float = 0.5,
    trailing_activation_pct: float = 0.15,
    break_even_buffer_pct: float = 0.03,
    break_even_min_hold_bars: int = 2,
    trailing_enabled_in_choppy: bool = False,
    time_exit_bars: int = 40,
    adverse_flow_exit_enabled: bool = True,
    adverse_flow_threshold: float = 0.12,
    adverse_flow_min_hold_bars: int = 3,
    adverse_flow_consistency_threshold: float = 0.45,
    adverse_book_pressure_threshold: float = 0.15,
    stop_loss_mode: str = "strategy",
    fixed_stop_loss_pct: float = 0.0,
    l2_confirm_enabled: bool = False,
    l2_min_delta: float = 0.0,
    l2_min_imbalance: float = 0.0,
    l2_min_iceberg_bias: float = 0.0,
    l2_lookback_bars: int = 3,
    l2_min_participation_ratio: float = 0.0,
    l2_min_directional_consistency: float = 0.0,
    l2_min_signed_aggression: float = 0.0,
    cold_start_each_day: bool = False,
    strategy_selection_mode: str = "adaptive_top_n",
    max_active_strategies: int = 3,
    momentum_diversification_json: Optional[str] = None,
) -> bool:
    """
    Configure a trading session on the strategy API.
    
    Args:
        strategy_api_url: URL of the strategy API
        run_id: Run identifier
        ticker: Ticker symbol
        date: Trading date
        regime_detection_minutes: Minutes for regime detection
        regime_refresh_bars: Bars between regime refresh
        account_size_usd: Account size in USD
        risk_per_trade_pct: Risk per trade as percentage
        ... (other parameters as documented in api_server.py)
        
    Returns:
        True if configuration was successful
    """
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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/session/config",
                params=params,
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        f"Session config failed (HTTP {resp.status}) for {run_id}:{ticker}:{date}"
                    )
                    return False
                return True
    except Exception as e:
        logger.warning(f"Session config error for {run_id}:{ticker}:{date}: {e}")
        return False


async def clear_remote_strategy_sessions(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
) -> bool:
    """
    Best-effort cleanup of strategy API session state.
    
    This prevents sticky per-run state (phase/cooldown/session caches) from
    affecting subsequent replays with the same run_id+ticker.
    
    Args:
        strategy_api_url: URL of the strategy API
        run_id: Run identifier
        ticker: Ticker symbol
        
    Returns:
        True if cleanup was successful
    """
    normalized_ticker = ticker.upper()
    
    async def _clear_v2(session: aiohttp.ClientSession) -> bool:
        async with session.delete(
            f"{strategy_api_url}/api/session/run",
            params={"run_id": run_id, "ticker": normalized_ticker},
        ) as resp:
            if resp.status == 200:
                return True
            # Endpoint might not exist on older strategy API builds.
            if resp.status in (404, 405):
                return False
            logger.warning(
                f"Session run-clear failed (HTTP {resp.status}) for {run_id}:{normalized_ticker}"
            )
            return False
    
    async def _clear_legacy(session: aiohttp.ClientSession) -> None:
        from typing import List
        
        try:
            async with session.get(f"{strategy_api_url}/api/sessions") as resp:
                if resp.status != 200:
                    logger.warning(
                        f"Session list failed (HTTP {resp.status}) for {run_id}:{normalized_ticker}"
                    )
                    return
                payload = await resp.json()
        except Exception as exc:
            logger.warning(f"Session list error for {run_id}:{normalized_ticker}: {exc}")
            return
        
        if not isinstance(payload, dict):
            return
        
        dates_to_clear: List[str] = []
        for session_state in payload.values():
            if not isinstance(session_state, dict):
                continue
            if session_state.get("run_id") != run_id:
                continue
            if str(session_state.get("ticker", "")).upper() != normalized_ticker:
                continue
            date_val = session_state.get("date")
            if isinstance(date_val, str) and date_val:
                dates_to_clear.append(date_val)
        
        for date_val in sorted(set(dates_to_clear)):
            try:
                async with session.delete(
                    f"{strategy_api_url}/api/session",
                    params={
                        "run_id": run_id,
                        "ticker": normalized_ticker,
                        "date": date_val,
                    },
                ) as resp:
                    if resp.status not in (200, 404):
                        logger.warning(
                            f"Legacy session clear failed (HTTP {resp.status}) "
                            f"for {run_id}:{normalized_ticker}:{date_val}"
                        )
            except Exception as exc:
                logger.warning(
                    f"Legacy session clear error for {run_id}:{normalized_ticker}:{date_val}: {exc}"
                )
    
    try:
        async with aiohttp.ClientSession() as session:
            used_v2 = await _clear_v2(session)
            if not used_v2:
                await _clear_legacy(session)
            return True
    except Exception as exc:
        logger.warning(f"Remote session cleanup error for {run_id}:{normalized_ticker}: {exc}")
        return False


async def reset_remote_orchestrator_state(
    strategy_api_url: str,
    scope: str = "all",
) -> bool:
    """
    Best-effort full reset of remote strategy/orchestrator state.
    
    Args:
        strategy_api_url: URL of the strategy API
        scope: Reset scope (all, session, learning)
        
    Returns:
        True when a reset endpoint acknowledged the request
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": scope, "clear_sessions": "true"},
            ) as resp:
                if resp.status == 200:
                    return True
                if resp.status in (404, 405):
                    # Older strategy API builds do not expose this endpoint.
                    return False
                logger.warning(
                    f"Remote orchestrator reset failed (HTTP {resp.status}) at {strategy_api_url}"
                )
                return False
    except Exception as exc:
        logger.warning(f"Remote orchestrator reset error at {strategy_api_url}: {exc}")
        return False


async def load_remote_checkpoint(
    strategy_api_url: str,
    checkpoint_path: str,
) -> Optional[Dict[str, Any]]:
    """
    Load a checkpoint on the remote strategy API.
    
    Args:
        strategy_api_url: URL of the strategy API
        checkpoint_path: Path to checkpoint file
        
    Returns:
        Checkpoint data or None if failed
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/load",
                params={"path": checkpoint_path},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(
                    f"Remote checkpoint load failed (HTTP {resp.status}): {checkpoint_path}"
                )
                return None
    except Exception as exc:
        logger.warning(f"Remote checkpoint load error: {exc}")
        return None


async def save_remote_checkpoint(
    strategy_api_url: str,
    run_id: str = "",
    ticker: str = "",
    date_from: str = "",
    date_to: str = "",
) -> Optional[str]:
    """
    Auto-save checkpoint after a successful backtest run.
    
    Args:
        strategy_api_url: URL of the strategy API
        run_id: Run identifier
        ticker: Ticker symbol
        date_from: Start date
        date_to: End date
        
    Returns:
        Path to saved checkpoint or None if failed
    """
    try:
        params = {
            k: v for k, v in {
                "run_id": run_id,
                "ticker": ticker,
                "date_from": date_from,
                "date_to": date_to,
            }.items() if v
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/save",
                params=params,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    path = result.get("path")
                    logger.info(f"Auto-saved checkpoint: {path}")
                    return path
                return None
    except Exception as exc:
        logger.warning(f"Checkpoint auto-save error: {exc}")
        return None
