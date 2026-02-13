from __future__ import annotations

import os
from typing import Any, Dict

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


def normalize_strategy_key(name: Any) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    return text.replace("-", "_").replace(" ", "_")


def resolve_active_adaptive_tuner_candidate(
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    active_profile_id = str(ticker_config.get("active_adaptive_tuner_profile_id", "")).strip()
    if not active_profile_id:
        return {}
    profiles = deps.normalize_tuner_profiles(ticker_config.get("adaptive_tuner_profiles", []))
    target_profile = next(
        (
            profile
            for profile in profiles
            if str(profile.get("profile_id", "")).strip() == active_profile_id
        ),
        None,
    )
    if not isinstance(target_profile, dict):
        return {}
    candidate = target_profile.get("candidate")
    if isinstance(candidate, dict):
        return candidate
    best_trial = target_profile.get("best_trial")
    if isinstance(best_trial, dict) and isinstance(best_trial.get("candidate"), dict):
        return best_trial.get("candidate", {})
    return {}


def extract_profile_runtime_overrides(
    candidate: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    if not isinstance(candidate, dict):
        return {}
    runtime: Dict[str, Any] = {}
    runtime["strategy_selection_mode"] = deps.normalize_strategy_selection_mode(
        candidate.get("strategy_selection_mode")
    )
    runtime["max_active_strategies"] = deps.normalize_clamped_int(
        candidate.get("max_active_strategies"), default=3, min_value=1, max_value=20
    )
    try:
        time_exit_bars = int(candidate.get("time_exit_bars"))
        if time_exit_bars > 0:
            runtime["time_exit_bars"] = time_exit_bars
    except (TypeError, ValueError):
        pass
    threshold_overrides = (
        ("adverse_flow_consistency", "adverse_flow_consistency_threshold"),
        ("adverse_book_pressure", "adverse_book_pressure_threshold"),
    )
    for candidate_key, runtime_key in threshold_overrides:
        raw = candidate.get(candidate_key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            runtime[runtime_key] = value
    for key in (
        "l2_min_delta",
        "l2_min_imbalance",
        "l2_min_signed_aggression",
        "l2_min_directional_consistency",
        "l2_min_participation_ratio",
        "l2_min_iceberg_bias",
    ):
        raw = candidate.get(key)
        if raw is None:
            continue
        try:
            runtime[key] = float(raw)
        except (TypeError, ValueError):
            continue

    momentum_runtime = deps.normalize_momentum_diversification_payload(
        candidate.get("momentum_diversification")
    )
    if not momentum_runtime:
        raw_momentum: Dict[str, Any] = {}
        momentum_keys = (
            "momentum_diversification_enabled",
            "momentum_route_enabled",
            "momentum_min_flow_score",
            "momentum_min_directional_consistency",
            "momentum_min_signed_aggression",
            "momentum_min_imbalance",
            "momentum_min_cvd",
            "momentum_min_directional_price_change_pct",
            "momentum_min_price_trend_efficiency",
            "momentum_min_last_bar_body_ratio",
            "momentum_min_last_bar_close_location",
            "momentum_min_delta_acceleration",
            "momentum_min_delta_price_divergence",
            "momentum_route_flow_score_impulse",
            "momentum_fail_fast_exit_enabled",
            "momentum_fail_fast_max_bars",
        )
        key_map = {
            "momentum_diversification_enabled": "enabled",
            "momentum_route_enabled": "route_enabled",
            "momentum_min_flow_score": "min_flow_score",
            "momentum_min_directional_consistency": "min_directional_consistency",
            "momentum_min_signed_aggression": "min_signed_aggression",
            "momentum_min_imbalance": "min_imbalance",
            "momentum_min_cvd": "min_cvd",
            "momentum_min_directional_price_change_pct": "min_directional_price_change_pct",
            "momentum_min_price_trend_efficiency": "min_price_trend_efficiency",
            "momentum_min_last_bar_body_ratio": "min_last_bar_body_ratio",
            "momentum_min_last_bar_close_location": "min_last_bar_close_location",
            "momentum_min_delta_acceleration": "min_delta_acceleration",
            "momentum_min_delta_price_divergence": "min_delta_price_divergence",
            "momentum_route_flow_score_impulse": "route_flow_score_impulse",
            "momentum_fail_fast_exit_enabled": "fail_fast_exit_enabled",
            "momentum_fail_fast_max_bars": "fail_fast_max_bars",
        }
        for key in momentum_keys:
            if key not in candidate:
                continue
            raw_momentum[key_map[key]] = candidate.get(key)
        momentum_runtime = deps.normalize_momentum_diversification_payload(raw_momentum)
    if momentum_runtime:
        runtime["momentum_diversification"] = momentum_runtime

    # Context-aware exit response parameters
    context_exit = candidate.get("adaptive", {}).get("context_exit_response")
    if isinstance(context_exit, dict) and context_exit:
        runtime["context_exit_response"] = context_exit

    return runtime


async def apply_active_strategy_combo(
    strategy_api_url: str,
    ticker: str,
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    profiles = deps.normalize_strategy_combo_profiles(
        ticker_config.get("strategy_combo_profiles", [])
    )
    active_profile_id = str(ticker_config.get("active_strategy_combo_profile_id", "")).strip()
    if not active_profile_id:
        return {}
    target_profile = next(
        (profile for profile in profiles if str(profile.get("profile_id")) == active_profile_id),
        None,
    )
    if not isinstance(target_profile, dict):
        deps.logger.warning(
            "Active strategy combo profile not found for %s: %s",
            ticker,
            active_profile_id,
        )
        return {
            "active_profile_id": active_profile_id,
            "applied_count": 0,
            "failed_count": 0,
            "missing_profile": True,
        }
    strategy_params = target_profile.get("strategy_params", {})
    if not isinstance(strategy_params, dict):
        return {
            "active_profile_id": active_profile_id,
            "profile_name": target_profile.get("profile_name"),
            "applied_count": 0,
            "failed_count": 0,
        }
    apply_result = await deps.apply_strategy_param_map(strategy_api_url, strategy_params)
    return {
        "active_profile_id": active_profile_id,
        "profile_name": target_profile.get("profile_name"),
        **apply_result,
    }


async def apply_active_adaptive_tuner_profile(
    strategy_api_url: str,
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    candidate = resolve_active_adaptive_tuner_candidate(ticker_config, deps)
    if not candidate:
        return {}

    enabled_raw = candidate.get("enabled_strategies", [])
    enabled_strategies = [str(s).strip() for s in enabled_raw if str(s).strip()]
    if not enabled_strategies:
        return {"candidate_applied": False, "reason": "candidate has no enabled_strategies"}

    enabled_norm = {normalize_strategy_key(s) for s in enabled_strategies}
    result: Dict[str, Any] = {
        "candidate_applied": True,
        "enabled_strategies": enabled_strategies,
        "runtime_overrides": extract_profile_runtime_overrides(candidate, deps),
    }

    try:
        remote = await deps.fetch_remote_strategies(strategy_api_url)
    except Exception as exc:
        return {
            **result,
            "candidate_applied": False,
            "error": f"failed to fetch remote strategies: {exc}",
        }

    enable_map: Dict[str, Dict[str, Any]] = {}
    for strategy_name in remote.keys():
        normalized = normalize_strategy_key(strategy_name)
        enable_map[str(strategy_name)] = {"enabled": normalized in enabled_norm}
    enable_apply = await deps.apply_strategy_param_map(strategy_api_url, enable_map)
    result["enabled_sync"] = enable_apply

    v2_params: Dict[str, Any] = {}
    for key in ("min_confidence", "atr_stop_multiplier", "rr_ratio", "trailing_stop_pct"):
        raw = candidate.get(key)
        if raw is None:
            continue
        try:
            v2_params[key] = float(raw)
        except (TypeError, ValueError):
            continue
    if v2_params:
        param_map = {name: dict(v2_params) for name in enabled_strategies}
        param_apply = await deps.apply_strategy_param_map(strategy_api_url, param_map)
        result["v2_param_sync"] = param_apply

    return result


async def apply_aos_optimizations(
    strategy_api_url: str,
    ticker: str,
    deps: StrategyApiIntegrationDeps,
    *,
    remote_sync: bool = True,
    aos_config_path: str | None = None,
) -> Dict[str, Any]:
    aos_config = deps.load_aos_config(aos_config_path)
    ticker_config = aos_config.get("tickers", {}).get(ticker.upper(), {})
    positioning_ticker_config = deps.get_ticker_positioning_config(ticker)
    if isinstance(ticker_config, dict):
        legacy_positioning = {}
        for key in deps.positioning_config_keys:
            if key in ticker_config:
                legacy_positioning[key] = ticker_config.get(key)
        if legacy_positioning:
            merged_positioning = dict(legacy_positioning)
            merged_positioning.update(positioning_ticker_config)
            positioning_ticker_config = merged_positioning

    if not ticker_config:
        return {"positioning": positioning_ticker_config} if positioning_ticker_config else {}

    applied: Dict[str, Any] = {}
    strategy_name = ticker_config.get("strategy")
    params = dict(ticker_config.get("params", {}))
    if "long_only" in ticker_config and "long_only" not in params:
        params["long_only"] = bool(ticker_config["long_only"])

    active_candidate = resolve_active_adaptive_tuner_candidate(ticker_config, deps)
    active_profile_runtime = extract_profile_runtime_overrides(active_candidate, deps)
    active_profile_id = str(ticker_config.get("active_adaptive_tuner_profile_id", "")).strip()
    if remote_sync:
        combo_applied = await deps.apply_active_strategy_combo(
            strategy_api_url=strategy_api_url,
            ticker=ticker,
            ticker_config=ticker_config,
        )
        if combo_applied:
            applied["strategy_combo"] = combo_applied

        try:
            async with aiohttp.ClientSession(timeout=_STRATEGY_API_CLIENT_TIMEOUT) as session:
                if strategy_name and params:
                    async with session.post(
                        f"{strategy_api_url}/api/strategies/update",
                        json={"strategy_name": strategy_name, "params": params},
                    ) as resp:
                        if resp.status == 200:
                            applied["strategy"] = strategy_name
                            applied["params"] = params
                            deps.logger.info(f"Applied AOS params for {ticker}: {params}")
                        else:
                            deps.logger.warning(
                                f"AOS update failed for {ticker}:{strategy_name} (HTTP {resp.status})"
                            )
        except Exception as exc:
            deps.logger.warning(f"AOS update error for {ticker}: {exc}")

        adaptive_profile_applied = await deps.apply_active_adaptive_tuner_profile(
            strategy_api_url=strategy_api_url,
            ticker_config=ticker_config,
        )
        if adaptive_profile_applied:
            if active_profile_runtime and not isinstance(
                adaptive_profile_applied.get("runtime_overrides"),
                dict,
            ):
                adaptive_profile_applied = dict(adaptive_profile_applied)
                adaptive_profile_applied["runtime_overrides"] = active_profile_runtime
            applied["adaptive_profile"] = adaptive_profile_applied
        elif active_profile_runtime:
            applied["adaptive_profile"] = {
                "active_profile_id": active_profile_id or None,
                "runtime_overrides": active_profile_runtime,
                "candidate_applied": False,
            }
    else:
        applied["remote_sync_skipped"] = True
        if active_profile_id or active_profile_runtime:
            enabled_raw = active_candidate.get("enabled_strategies", []) if isinstance(active_candidate, dict) else []
            enabled_strategies = [
                str(item).strip()
                for item in enabled_raw
                if str(item).strip()
            ]
            applied["adaptive_profile"] = {
                "active_profile_id": active_profile_id or None,
                "runtime_overrides": active_profile_runtime,
                "enabled_strategies": enabled_strategies,
                "candidate_applied": bool(enabled_strategies),
                "remote_sync_skipped": True,
            }

    applied["trading_hours"] = ticker_config.get("trading_hours")
    applied["long_only"] = bool(ticker_config.get("long_only", params.get("long_only", False)))
    applied["time_filter_enabled"] = bool(
        ticker_config.get("time_filter_enabled", bool(ticker_config.get("trading_hours")))
    )
    applied["strategy_selection_mode"] = (
        str(ticker_config.get("strategy_selection_mode", "adaptive_top_n")).strip().lower()
        or "adaptive_top_n"
    )
    try:
        raw_max_active = int(ticker_config.get("max_active_strategies", 3))
    except (TypeError, ValueError):
        raw_max_active = 3
    applied["max_active_strategies"] = max(1, min(20, raw_max_active))
    try:
        applied["adverse_flow_consistency_threshold"] = float(
            ticker_config.get("adverse_flow_consistency_threshold", 0.45)
        )
    except (TypeError, ValueError):
        applied["adverse_flow_consistency_threshold"] = 0.45
    try:
        applied["adverse_book_pressure_threshold"] = float(
            ticker_config.get("adverse_book_pressure_threshold", 0.15)
        )
    except (TypeError, ValueError):
        applied["adverse_book_pressure_threshold"] = 0.15
    if isinstance(ticker_config.get("l2"), dict):
        applied["l2"] = ticker_config.get("l2", {})
    if isinstance(ticker_config.get("adaptive"), dict):
        applied["adaptive"] = ticker_config.get("adaptive", {})
    if positioning_ticker_config:
        applied["positioning"] = positioning_ticker_config
    return applied
