from __future__ import annotations

import os
from typing import Any, Dict

from src.services.config_domain import (
    EffectiveAosState,
    extract_profile_runtime_overrides,
    normalize_profile_ref_token,
    resolve_active_adaptive_tuner_candidate,
)
from src.services.strategy_api_auth_headers import build_strategy_api_headers
from src.services.strategy_api_transport import (
    normalize_strategy_api_base_url,
    open_strategy_api_session,
)
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


def normalize_strategy_key(name: Any) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    return text.replace("-", "_").replace(" ", "_")


def _strategy_api_headers(strategy_api_url: str) -> Dict[str, str]:
    return build_strategy_api_headers(strategy_api_url)


async def publish_active_strategy_combo(
    strategy_api_url: str,
    ticker: str,
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    profiles = deps.normalize_strategy_combo_profiles(
        ticker_config.get("strategy_combo_profiles", [])
    )
    active_profile_id = normalize_profile_ref_token(
        ticker_config.get("active_strategy_combo_profile_id")
    )
    if not active_profile_id:
        return {}
    target_profile = next(
        (
            profile
            for profile in profiles
            if normalize_profile_ref_token(profile.get("profile_id")) == active_profile_id
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
    apply_result = await deps.apply_strategy_param_map(
        strategy_api_url, strategy_params
    )
    return {
        "active_profile_id": active_profile_id,
        "profile_name": target_profile.get("profile_name"),
        **apply_result,
    }


async def publish_active_adaptive_tuner_profile(
    strategy_api_url: str,
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    active_profile_id = normalize_profile_ref_token(
        ticker_config.get("active_adaptive_tuner_profile_id")
    )
    active_profile_name = None
    if active_profile_id:
        profiles = deps.normalize_tuner_profiles(
            ticker_config.get("adaptive_tuner_profiles", [])
        )
        target_profile = next(
            (
                profile
                for profile in profiles
                if normalize_profile_ref_token(profile.get("profile_id"))
                == active_profile_id
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
    for key in (
        "min_confidence",
        "atr_stop_multiplier",
        "rr_ratio",
        "trailing_stop_pct",
    ):
        raw = candidate.get(key)
        if raw is None:
            continue
        try:
            v2_params[key] = float(raw)
        except (TypeError, ValueError):
            continue
    if v2_params:
        override_combo_params = bool(
            candidate.get("override_combo_strategy_params", False)
        )
        combo_param_strategies: set[str] = set()
        active_combo_profile_id = normalize_profile_ref_token(
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
                    if normalize_profile_ref_token(profile.get("profile_id"))
                    == active_combo_profile_id
                ),
                None,
            )
            if isinstance(combo_profile, dict):
                strategy_params = combo_profile.get("strategy_params")
                if isinstance(strategy_params, dict):
                    for strategy_name, strategy_cfg in strategy_params.items():
                        if isinstance(strategy_cfg, dict) and strategy_cfg:
                            combo_param_strategies.add(
                                normalize_strategy_key(strategy_name)
                            )

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
            param_apply = await deps.apply_strategy_param_map(
                strategy_api_url, param_map
            )
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

    orchestrator_payload: Dict[str, Any] = {}
    if candidate.get("base_threshold") is not None:
        try:
            orchestrator_payload["base_threshold"] = float(
                candidate.get("base_threshold")
            )
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


async def _publish_base_strategy_params(
    *,
    strategy_api_url: str,
    ticker: str,
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
    applied: Dict[str, Any],
) -> None:
    strategy_name = ticker_config.get("strategy")
    params = dict(ticker_config.get("params", {}))
    if "long_only" in ticker_config and "long_only" not in params:
        params["long_only"] = bool(ticker_config["long_only"])
    try:
        base_url = normalize_strategy_api_base_url(strategy_api_url)
        async with open_strategy_api_session(
            strategy_api_url=strategy_api_url,
            timeout_seconds=_STRATEGY_API_TIMEOUT_SECONDS,
            connect_timeout_seconds=3.0,
        ) as session:
            if strategy_name and params:
                async with session.post(
                    f"{base_url}/api/strategies/update",
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


async def publish_effective_aos_state(
    *,
    strategy_api_url: str,
    ticker: str,
    state: EffectiveAosState,
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    applied = dict(state.applied)
    if state.unified_profile:
        strategy_profile = state.unified_profile.get("strategy_profile")
        if not isinstance(strategy_profile, dict):
            strategy_profile = {}
        strategy_params = strategy_profile.get("strategy_params")
        if isinstance(strategy_params, dict) and strategy_params:
            strategy_sync = await deps.apply_strategy_param_map(
                strategy_api_url, strategy_params
            )
            applied["unified_profile"]["strategy_sync"] = strategy_sync
        return applied

    combo_applied = await deps.apply_active_strategy_combo(
        strategy_api_url=strategy_api_url,
        ticker=ticker,
        ticker_config=state.ticker_config,
    )
    if combo_applied:
        applied["strategy_combo"] = combo_applied

    await _publish_base_strategy_params(
        strategy_api_url=strategy_api_url,
        ticker=ticker,
        ticker_config=state.ticker_config,
        deps=deps,
        applied=applied,
    )

    adaptive_profile_applied = await deps.apply_active_adaptive_tuner_profile(
        strategy_api_url=strategy_api_url,
        ticker_config=state.ticker_config,
    )
    if adaptive_profile_applied:
        if state.active_adaptive_runtime and not isinstance(
            adaptive_profile_applied.get("runtime_overrides"),
            dict,
        ):
            adaptive_profile_applied = dict(adaptive_profile_applied)
            adaptive_profile_applied["runtime_overrides"] = state.active_adaptive_runtime
        applied["adaptive_profile"] = adaptive_profile_applied
    elif state.active_adaptive_runtime:
        applied["adaptive_profile"] = {
            "active_profile_id": normalize_profile_ref_token(
                state.ticker_config.get("active_adaptive_tuner_profile_id")
            )
            or None,
            "runtime_overrides": state.active_adaptive_runtime,
            "candidate_applied": False,
        }
    return applied
