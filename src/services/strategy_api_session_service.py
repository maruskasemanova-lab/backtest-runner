from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import aiohttp

from src.services.strategy_api_auth_headers import build_strategy_api_headers
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


def _strategy_api_headers(strategy_api_url: Optional[str] = None) -> Dict[str, str]:
    return build_strategy_api_headers(strategy_api_url)


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
    intraday_levels_enabled: bool,
    intraday_levels_swing_left_bars: int,
    intraday_levels_swing_right_bars: int,
    intraday_levels_test_tolerance_pct: float,
    intraday_levels_break_tolerance_pct: float,
    intraday_levels_breakout_volume_lookback: int,
    intraday_levels_breakout_volume_multiplier: float,
    intraday_levels_volume_profile_bin_size_pct: float,
    intraday_levels_value_area_pct: float,
    intraday_levels_entry_quality_enabled: bool,
    intraday_levels_min_levels_for_context: int,
    intraday_levels_entry_tolerance_pct: float,
    intraday_levels_break_cooldown_bars: int,
    intraday_levels_rotation_max_tests: int,
    intraday_levels_rotation_volume_max_ratio: float,
    intraday_levels_recent_bounce_lookback_bars: int,
    intraday_levels_require_recent_bounce_for_mean_reversion: bool,
    intraday_levels_momentum_break_max_age_bars: int,
    intraday_levels_momentum_min_room_pct: float,
    intraday_levels_momentum_min_broken_ratio: float,
    intraday_levels_min_confluence_score: int,
    intraday_levels_memory_enabled: bool,
    intraday_levels_memory_min_tests: int,
    intraday_levels_memory_max_age_days: int,
    intraday_levels_memory_decay_after_days: int,
    intraday_levels_memory_decay_weight: float,
    intraday_levels_memory_max_levels: int,
    intraday_levels_opening_range_enabled: bool,
    intraday_levels_opening_range_minutes: int,
    intraday_levels_opening_range_break_tolerance_pct: float,
    intraday_levels_poc_migration_enabled: bool,
    intraday_levels_poc_migration_interval_bars: int,
    intraday_levels_poc_migration_trend_threshold_pct: float,
    intraday_levels_poc_migration_range_threshold_pct: float,
    intraday_levels_composite_profile_enabled: bool,
    intraday_levels_composite_profile_days: int,
    intraday_levels_composite_profile_current_day_weight: float,
    cold_start_each_day: bool,
    strategy_selection_mode: str,
    max_active_strategies: int,
    momentum_diversification_json: Optional[str],
    deps: StrategyApiIntegrationDeps,
    max_daily_trades: Optional[int] = None,
    mu_choppy_hard_block_enabled: Optional[bool] = None,
    regime_filter: Optional[List[str]] = None,
    **extra_params: Any,
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
        "intraday_levels_enabled": int(bool(intraday_levels_enabled)),
        "intraday_levels_swing_left_bars": int(intraday_levels_swing_left_bars),
        "intraday_levels_swing_right_bars": int(intraday_levels_swing_right_bars),
        "intraday_levels_test_tolerance_pct": float(intraday_levels_test_tolerance_pct),
        "intraday_levels_break_tolerance_pct": float(
            intraday_levels_break_tolerance_pct
        ),
        "intraday_levels_breakout_volume_lookback": int(
            intraday_levels_breakout_volume_lookback
        ),
        "intraday_levels_breakout_volume_multiplier": float(
            intraday_levels_breakout_volume_multiplier
        ),
        "intraday_levels_volume_profile_bin_size_pct": float(
            intraday_levels_volume_profile_bin_size_pct
        ),
        "intraday_levels_value_area_pct": float(intraday_levels_value_area_pct),
        "intraday_levels_entry_quality_enabled": int(
            bool(intraday_levels_entry_quality_enabled)
        ),
        "intraday_levels_min_levels_for_context": int(
            intraday_levels_min_levels_for_context
        ),
        "intraday_levels_entry_tolerance_pct": float(
            intraday_levels_entry_tolerance_pct
        ),
        "intraday_levels_break_cooldown_bars": int(intraday_levels_break_cooldown_bars),
        "intraday_levels_rotation_max_tests": int(intraday_levels_rotation_max_tests),
        "intraday_levels_rotation_volume_max_ratio": float(
            intraday_levels_rotation_volume_max_ratio
        ),
        "intraday_levels_recent_bounce_lookback_bars": int(
            intraday_levels_recent_bounce_lookback_bars
        ),
        "intraday_levels_require_recent_bounce_for_mean_reversion": int(
            bool(intraday_levels_require_recent_bounce_for_mean_reversion)
        ),
        "intraday_levels_momentum_break_max_age_bars": int(
            intraday_levels_momentum_break_max_age_bars
        ),
        "intraday_levels_momentum_min_room_pct": float(
            intraday_levels_momentum_min_room_pct
        ),
        "intraday_levels_momentum_min_broken_ratio": float(
            intraday_levels_momentum_min_broken_ratio
        ),
        "intraday_levels_min_confluence_score": int(
            intraday_levels_min_confluence_score
        ),
        "intraday_levels_memory_enabled": int(bool(intraday_levels_memory_enabled)),
        "intraday_levels_memory_min_tests": int(intraday_levels_memory_min_tests),
        "intraday_levels_memory_max_age_days": int(intraday_levels_memory_max_age_days),
        "intraday_levels_memory_decay_after_days": int(
            intraday_levels_memory_decay_after_days
        ),
        "intraday_levels_memory_decay_weight": float(
            intraday_levels_memory_decay_weight
        ),
        "intraday_levels_memory_max_levels": int(intraday_levels_memory_max_levels),
        "intraday_levels_opening_range_enabled": int(
            bool(intraday_levels_opening_range_enabled)
        ),
        "intraday_levels_opening_range_minutes": int(
            intraday_levels_opening_range_minutes
        ),
        "intraday_levels_opening_range_break_tolerance_pct": float(
            intraday_levels_opening_range_break_tolerance_pct
        ),
        "intraday_levels_poc_migration_enabled": int(
            bool(intraday_levels_poc_migration_enabled)
        ),
        "intraday_levels_poc_migration_interval_bars": int(
            intraday_levels_poc_migration_interval_bars
        ),
        "intraday_levels_poc_migration_trend_threshold_pct": float(
            intraday_levels_poc_migration_trend_threshold_pct
        ),
        "intraday_levels_poc_migration_range_threshold_pct": float(
            intraday_levels_poc_migration_range_threshold_pct
        ),
        "intraday_levels_composite_profile_enabled": int(
            bool(intraday_levels_composite_profile_enabled)
        ),
        "intraday_levels_composite_profile_days": int(
            intraday_levels_composite_profile_days
        ),
        "intraday_levels_composite_profile_current_day_weight": float(
            intraday_levels_composite_profile_current_day_weight
        ),
        "cold_start_each_day": int(bool(cold_start_each_day)),
        "strategy_selection_mode": str(strategy_selection_mode),
        "max_active_strategies": int(max_active_strategies),
    }
    if momentum_diversification_json:
        params["momentum_diversification_json"] = str(momentum_diversification_json)
    if max_daily_trades is not None:
        params["max_daily_trades"] = int(max_daily_trades)
    if mu_choppy_hard_block_enabled is not None:
        params["mu_choppy_hard_block_enabled"] = int(bool(mu_choppy_hard_block_enabled))
    if regime_filter is not None:
        params["regime_filter_json"] = json.dumps(regime_filter)
    if extra_params:
        for key, value in extra_params.items():
            if value is None:
                continue
            if isinstance(value, bool):
                params[str(key)] = int(value)
            elif isinstance(value, (int, float, str)):
                params[str(key)] = value
            elif isinstance(value, (dict, list)):
                params[str(key)] = json.dumps(value, separators=(",", ":"))
            else:
                params[str(key)] = str(value)
    try:
        async with aiohttp.ClientSession(
            timeout=_STRATEGY_API_CLIENT_TIMEOUT
        ) as session:
            async with session.post(
                f"{strategy_api_url}/api/session/config",
                params=params,
                headers=_strategy_api_headers(strategy_api_url),
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
            headers=_strategy_api_headers(strategy_api_url),
        ) as resp:
            if resp.status != 200:
                deps.logger.warning(
                    f"Session run-clear failed (HTTP {resp.status}) for {run_id}:{normalized_ticker}"
                )

    try:
        async with aiohttp.ClientSession(
            timeout=_STRATEGY_API_CLIENT_TIMEOUT
        ) as session:
            await _clear_v2(session)
    except Exception as exc:
        deps.logger.warning(
            f"Remote session cleanup error for {run_id}:{normalized_ticker}: {exc}"
        )


async def reset_remote_orchestrator_state(
    strategy_api_url: str,
    deps: StrategyApiIntegrationDeps,
) -> bool:
    try:
        async with aiohttp.ClientSession(
            timeout=_STRATEGY_API_CLIENT_TIMEOUT
        ) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": "all", "clear_sessions": "true"},
                headers=_strategy_api_headers(strategy_api_url),
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
        deps.logger.warning(
            f"Remote orchestrator reset error at {strategy_api_url}: {exc}"
        )
        return False


async def reset_remote_orchestrator_state_scoped(
    strategy_api_url: str,
    scope: str,
    deps: StrategyApiIntegrationDeps,
) -> bool:
    try:
        async with aiohttp.ClientSession(
            timeout=_STRATEGY_API_CLIENT_TIMEOUT
        ) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": scope, "clear_sessions": "true"},
                headers=_strategy_api_headers(strategy_api_url),
            ) as resp:
                return resp.status == 200
    except Exception as exc:
        deps.logger.warning(f"Remote orchestrator scoped reset error: {exc}")
        return False


async def apply_orchestrator_config(
    strategy_api_url: str,
    config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    """Best-effort update of remote orchestrator runtime config."""
    if not isinstance(config, dict) or not config:
        return {}
    try:
        async with aiohttp.ClientSession(
            timeout=_STRATEGY_API_CLIENT_TIMEOUT
        ) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/config",
                json=config,
                headers=_strategy_api_headers(strategy_api_url),
            ) as resp:
                if resp.status == 200:
                    payload = await resp.json()
                    return payload if isinstance(payload, dict) else {}
                deps.logger.warning(
                    "Remote orchestrator config update failed (HTTP %s) at %s",
                    resp.status,
                    strategy_api_url,
                )
                return {}
    except Exception as exc:
        deps.logger.warning(f"Remote orchestrator config update error: {exc}")
        return {}


async def load_remote_checkpoint(
    strategy_api_url: str,
    checkpoint_path: str,
    deps: StrategyApiIntegrationDeps,
) -> Optional[Dict]:
    try:
        async with aiohttp.ClientSession(
            timeout=_STRATEGY_API_CLIENT_TIMEOUT
        ) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/load",
                params={"path": checkpoint_path},
                headers=_strategy_api_headers(strategy_api_url),
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
        async with aiohttp.ClientSession(
            timeout=_STRATEGY_API_CLIENT_TIMEOUT
        ) as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/save",
                params=params,
                headers=_strategy_api_headers(strategy_api_url),
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
