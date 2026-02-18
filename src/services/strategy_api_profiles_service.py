from __future__ import annotations

import os
from typing import Any, Dict

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

_PROFILE_PLACEHOLDER_TOKENS = {"none", "null", "n/a", "na", "undefined", "-"}


def _normalize_profile_ref_token(value: Any) -> str:
    token = str(value).strip() if value is not None else ""
    if not token:
        return ""
    if token.lower() in _PROFILE_PLACEHOLDER_TOKENS:
        return ""
    return token


def _strategy_api_headers(strategy_api_url: str) -> Dict[str, str]:
    return build_strategy_api_headers(strategy_api_url)


def normalize_strategy_key(name: Any) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    return text.replace("-", "_").replace(" ", "_")


def resolve_active_adaptive_tuner_candidate(
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    active_profile_id = _normalize_profile_ref_token(
        ticker_config.get("active_adaptive_tuner_profile_id")
    )
    if not active_profile_id:
        return {}
    profiles = deps.normalize_tuner_profiles(ticker_config.get("adaptive_tuner_profiles", []))
    target_profile = next(
        (
            profile
            for profile in profiles
            if _normalize_profile_ref_token(profile.get("profile_id")) == active_profile_id
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


def resolve_active_unified_profile(
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    active_profile_id = _normalize_profile_ref_token(ticker_config.get("active_unified_profile_id"))
    if not active_profile_id:
        return {}
    profiles = deps.normalize_unified_profiles(ticker_config.get("unified_profiles", []))
    target_profile = next(
        (
            profile
            for profile in profiles
            if _normalize_profile_ref_token(profile.get("profile_id")) == active_profile_id
        ),
        None,
    )
    if isinstance(target_profile, dict):
        return target_profile
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
    trading_hours = candidate.get("trading_hours")
    if isinstance(trading_hours, (list, tuple)):
        normalized_hours = []
        for raw_hour in trading_hours:
            try:
                hour = int(raw_hour)
            except (TypeError, ValueError):
                continue
            if 0 <= hour <= 23:
                normalized_hours.append(hour)
        if normalized_hours:
            runtime["trading_hours"] = sorted(set(normalized_hours))
            runtime["time_filter_enabled"] = bool(
                candidate.get("time_filter_enabled", True)
            )
    if "long_only" in candidate:
        runtime["long_only"] = bool(candidate.get("long_only"))

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


def _extract_unified_runtime_overrides(
    strategy_profile: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    runtime: Dict[str, Any] = {}
    if not isinstance(strategy_profile, dict):
        return runtime

    raw_runtime = strategy_profile.get("runtime_overrides")
    if isinstance(raw_runtime, dict):
        runtime.update(raw_runtime)

    adaptive_candidate = strategy_profile.get("adaptive_candidate")
    if isinstance(adaptive_candidate, dict):
        runtime.update(extract_profile_runtime_overrides(adaptive_candidate, deps))

    if "strategy_selection_mode" in strategy_profile:
        runtime["strategy_selection_mode"] = deps.normalize_strategy_selection_mode(
            strategy_profile.get("strategy_selection_mode")
        )
    if "max_active_strategies" in strategy_profile:
        runtime["max_active_strategies"] = deps.normalize_clamped_int(
            strategy_profile.get("max_active_strategies"),
            default=3,
            min_value=1,
            max_value=20,
        )
    if "trading_hours" in strategy_profile and isinstance(strategy_profile.get("trading_hours"), list):
        normalized_hours = []
        seen_hours = set()
        for raw_hour in strategy_profile.get("trading_hours", []):
            try:
                hour = int(raw_hour)
            except (TypeError, ValueError):
                continue
            if hour < 0 or hour > 23 or hour in seen_hours:
                continue
            seen_hours.add(hour)
            normalized_hours.append(hour)
        if normalized_hours:
            runtime["trading_hours"] = sorted(normalized_hours)
            runtime["time_filter_enabled"] = bool(strategy_profile.get("time_filter_enabled", True))

    if "long_only" in strategy_profile:
        runtime["long_only"] = bool(strategy_profile.get("long_only"))

    for key in (
        "l2_min_delta",
        "l2_min_imbalance",
        "l2_min_signed_aggression",
        "l2_min_directional_consistency",
        "l2_min_participation_ratio",
        "l2_min_iceberg_bias",
        "time_exit_bars",
        "global_exit_rr_ratio",
        "global_risk_atr_stop_multiplier",
        "global_risk_volume_stop_pct",
        "global_risk_min_stop_loss_pct",
        "trailing_stop_pct",
        "adverse_flow_consistency_threshold",
        "adverse_book_pressure_threshold",
    ):
        if key not in strategy_profile:
            continue
        value = strategy_profile.get(key)
        if value is None:
            continue
        runtime[key] = value

    momentum_runtime = deps.normalize_momentum_diversification_payload(
        strategy_profile.get("momentum_diversification")
    )
    if momentum_runtime:
        runtime["momentum_diversification"] = momentum_runtime
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
    active_profile_id = _normalize_profile_ref_token(
        ticker_config.get("active_strategy_combo_profile_id")
    )
    if not active_profile_id:
        return {}
    target_profile = next(
        (
            profile
            for profile in profiles
            if _normalize_profile_ref_token(profile.get("profile_id")) == active_profile_id
        ),
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
    active_profile_id = _normalize_profile_ref_token(
        ticker_config.get("active_adaptive_tuner_profile_id")
    )
    active_profile_name = None
    if active_profile_id:
        profiles = deps.normalize_tuner_profiles(ticker_config.get("adaptive_tuner_profiles", []))
        target_profile = next(
            (
                profile
                for profile in profiles
                if _normalize_profile_ref_token(profile.get("profile_id")) == active_profile_id
            ),
            None,
        )
        if isinstance(target_profile, dict):
            active_profile_name = (
                str(target_profile.get("profile_name") or "").strip() or None
            )

    candidate = resolve_active_adaptive_tuner_candidate(ticker_config, deps)
    if not candidate:
        return {}

    enabled_raw = candidate.get("enabled_strategies", [])
    enabled_strategies = [str(s).strip() for s in enabled_raw if str(s).strip()]
    if not enabled_strategies:
        return {
            "active_profile_id": active_profile_id or None,
            "profile_name": active_profile_name,
            "candidate_applied": False,
            "reason": "candidate has no enabled_strategies",
        }

    enabled_norm = {normalize_strategy_key(s) for s in enabled_strategies}
    result: Dict[str, Any] = {
        "active_profile_id": active_profile_id or None,
        "profile_name": active_profile_name,
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
        # Respect active strategy-combo profile as the more specific source.
        # Adaptive v2 params are treated as fallback for enabled strategies
        # that are not explicitly configured in the active combo.
        override_combo_params = bool(candidate.get("override_combo_strategy_params", False))
        combo_param_strategies: set[str] = set()
        active_combo_profile_id = _normalize_profile_ref_token(
            ticker_config.get("active_strategy_combo_profile_id")
        )
        if active_combo_profile_id:
            combo_profiles = deps.normalize_strategy_combo_profiles(
                ticker_config.get("strategy_combo_profiles", [])
            )
            combo_profile = next(
                (
                    profile
                    for profile in combo_profiles
                    if _normalize_profile_ref_token(profile.get("profile_id")) == active_combo_profile_id
                ),
                None,
            )
            if isinstance(combo_profile, dict):
                strategy_params = combo_profile.get("strategy_params")
                if isinstance(strategy_params, dict):
                    for strategy_name, strategy_cfg in strategy_params.items():
                        if isinstance(strategy_cfg, dict) and strategy_cfg:
                            combo_param_strategies.add(normalize_strategy_key(strategy_name))

        if override_combo_params:
            v2_targets = list(enabled_strategies)
        else:
            v2_targets = [
                name
                for name in enabled_strategies
                if normalize_strategy_key(name) not in combo_param_strategies
            ]
        if v2_targets:
            param_map = {name: dict(v2_params) for name in v2_targets}
            param_apply = await deps.apply_strategy_param_map(strategy_api_url, param_map)
            result["v2_param_sync"] = param_apply
            if override_combo_params:
                result["v2_param_sync_override_combo"] = True
            skipped = sorted(
                set(enabled_strategies) - set(v2_targets),
                key=lambda item: normalize_strategy_key(item),
            )
            if skipped:
                result["v2_param_sync_skipped_combo_strategies"] = skipped
        else:
            result["v2_param_sync_skipped_combo_strategies"] = list(enabled_strategies)

    # Sync orchestrator-level gates from adaptive candidate.
    orchestrator_payload: Dict[str, Any] = {}
    if candidate.get("base_threshold") is not None:
        try:
            orchestrator_payload["base_threshold"] = float(candidate.get("base_threshold"))
        except (TypeError, ValueError):
            pass
    if candidate.get("min_confirming_sources") is not None:
        try:
            orchestrator_payload["min_confirming_sources"] = int(
                candidate.get("min_confirming_sources")
            )
        except (TypeError, ValueError):
            pass
    if candidate.get("min_margin_over_threshold") is not None:
        try:
            orchestrator_payload["min_margin_over_threshold"] = float(
                candidate.get("min_margin_over_threshold")
            )
        except (TypeError, ValueError):
            pass
    if candidate.get("single_source_min_margin") is not None:
        try:
            orchestrator_payload["single_source_min_margin"] = float(
                candidate.get("single_source_min_margin")
            )
        except (TypeError, ValueError):
            pass
    if orchestrator_payload:
        result["orchestrator_sync"] = await deps.apply_orchestrator_config(
            strategy_api_url,
            orchestrator_payload,
        )

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

    unified_profile = resolve_active_unified_profile(ticker_config, deps)
    if unified_profile:
        unified_profile_id = _normalize_profile_ref_token(unified_profile.get("profile_id")) or None
        unified_profile_name = str(unified_profile.get("profile_name") or "").strip() or None
        strategy_profile = unified_profile.get("strategy_profile")
        if not isinstance(strategy_profile, dict):
            strategy_profile = {}
        execution_profile = unified_profile.get("execution_profile")
        if not isinstance(execution_profile, dict):
            execution_profile = {}

        strategy_params = strategy_profile.get("strategy_params")
        if not isinstance(strategy_params, dict):
            strategy_params = {}

        applied: Dict[str, Any] = {
            "unified_profile": {
                "active_profile_id": unified_profile_id,
                "profile_name": unified_profile_name,
            }
        }
        if remote_sync:
            if strategy_params:
                strategy_sync = await deps.apply_strategy_param_map(strategy_api_url, strategy_params)
                applied["unified_profile"]["strategy_sync"] = strategy_sync
        else:
            applied["remote_sync_skipped"] = True
            if strategy_params:
                applied["unified_profile"]["strategy_sync_skipped"] = True

        runtime_overrides = _extract_unified_runtime_overrides(strategy_profile, deps)
        applied["adaptive_profile"] = {
            "active_profile_id": unified_profile_id,
            "profile_name": unified_profile_name,
            "runtime_overrides": runtime_overrides,
            "candidate_applied": bool(strategy_params),
            "unified_profile": True,
        }

        profile_hours = runtime_overrides.get("trading_hours")
        if isinstance(profile_hours, list) and profile_hours:
            applied["trading_hours"] = list(profile_hours)
            applied["time_filter_enabled"] = bool(
                runtime_overrides.get("time_filter_enabled", True)
            )
            applied["trading_hours_source"] = "unified_profile"
        else:
            raw_hours = strategy_profile.get("trading_hours", ticker_config.get("trading_hours"))
            if isinstance(raw_hours, list) and raw_hours:
                applied["trading_hours"] = list(raw_hours)
            else:
                applied["trading_hours"] = ticker_config.get("trading_hours")
            applied["time_filter_enabled"] = bool(
                strategy_profile.get(
                    "time_filter_enabled",
                    ticker_config.get("time_filter_enabled", bool(applied.get("trading_hours"))),
                )
            )
            applied["trading_hours_source"] = "ticker_config"

        if "long_only" in runtime_overrides:
            applied["long_only"] = bool(runtime_overrides.get("long_only"))
            applied["long_only_source"] = "unified_profile"
        elif "long_only" in strategy_profile:
            applied["long_only"] = bool(strategy_profile.get("long_only"))
            applied["long_only_source"] = "unified_profile"
        else:
            params = dict(ticker_config.get("params", {}))
            applied["long_only"] = bool(ticker_config.get("long_only", params.get("long_only", False)))
            applied["long_only_source"] = "ticker_config"

        strategy_selection_mode = str(
            runtime_overrides.get(
                "strategy_selection_mode",
                strategy_profile.get("strategy_selection_mode", ticker_config.get("strategy_selection_mode", "adaptive_top_n")),
            )
        ).strip().lower()
        if strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
            strategy_selection_mode = "adaptive_top_n"
        applied["strategy_selection_mode"] = strategy_selection_mode
        try:
            raw_max_active = int(
                runtime_overrides.get(
                    "max_active_strategies",
                    strategy_profile.get("max_active_strategies", ticker_config.get("max_active_strategies", 3)),
                )
            )
        except (TypeError, ValueError):
            raw_max_active = 3
        applied["max_active_strategies"] = max(1, min(20, raw_max_active))

        try:
            applied["adverse_flow_consistency_threshold"] = float(
                runtime_overrides.get(
                    "adverse_flow_consistency_threshold",
                    strategy_profile.get(
                        "adverse_flow_consistency_threshold",
                        ticker_config.get("adverse_flow_consistency_threshold", 0.45),
                    ),
                )
            )
        except (TypeError, ValueError):
            applied["adverse_flow_consistency_threshold"] = 0.45
        try:
            applied["adverse_book_pressure_threshold"] = float(
                runtime_overrides.get(
                    "adverse_book_pressure_threshold",
                    strategy_profile.get(
                        "adverse_book_pressure_threshold",
                        ticker_config.get("adverse_book_pressure_threshold", 0.15),
                    ),
                )
            )
        except (TypeError, ValueError):
            applied["adverse_book_pressure_threshold"] = 0.15

        if isinstance(strategy_profile.get("l2"), dict):
            applied["l2"] = strategy_profile.get("l2", {})
        elif isinstance(ticker_config.get("l2"), dict):
            applied["l2"] = ticker_config.get("l2", {})
        if isinstance(strategy_profile.get("adaptive"), dict):
            applied["adaptive"] = strategy_profile.get("adaptive", {})
        elif isinstance(ticker_config.get("adaptive"), dict):
            applied["adaptive"] = ticker_config.get("adaptive", {})

        inline_positioning = execution_profile.get("positioning")
        if isinstance(inline_positioning, dict) and inline_positioning:
            merged_positioning = dict(positioning_ticker_config)
            merged_positioning.update(inline_positioning)
            positioning_ticker_config = merged_positioning
        if positioning_ticker_config:
            applied["positioning"] = positioning_ticker_config
        return applied

    applied: Dict[str, Any] = {}
    strategy_name = ticker_config.get("strategy")
    params = dict(ticker_config.get("params", {}))
    if "long_only" in ticker_config and "long_only" not in params:
        params["long_only"] = bool(ticker_config["long_only"])

    active_candidate = resolve_active_adaptive_tuner_candidate(ticker_config, deps)
    active_profile_runtime = extract_profile_runtime_overrides(active_candidate, deps)
    active_profile_id = _normalize_profile_ref_token(
        ticker_config.get("active_adaptive_tuner_profile_id")
    )
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
                        headers=_strategy_api_headers(strategy_api_url),
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

    profile_hours = active_profile_runtime.get("trading_hours")
    if isinstance(profile_hours, list) and profile_hours:
        applied["trading_hours"] = list(profile_hours)
        applied["time_filter_enabled"] = bool(
            active_profile_runtime.get("time_filter_enabled", True)
        )
        applied["trading_hours_source"] = "adaptive_profile"
    else:
        applied["trading_hours"] = ticker_config.get("trading_hours")
        applied["time_filter_enabled"] = bool(
            ticker_config.get("time_filter_enabled", bool(ticker_config.get("trading_hours")))
        )
        applied["trading_hours_source"] = "ticker_config"
    if "long_only" in active_profile_runtime:
        applied["long_only"] = bool(active_profile_runtime.get("long_only"))
        applied["long_only_source"] = "adaptive_profile"
    else:
        applied["long_only"] = bool(ticker_config.get("long_only", params.get("long_only", False)))
        applied["long_only_source"] = "ticker_config"
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
