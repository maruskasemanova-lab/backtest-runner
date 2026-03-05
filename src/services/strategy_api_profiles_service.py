from __future__ import annotations

from typing import Any, Dict

from src.services.config_domain import (
    TickerConfigRepositoryDeps,
    extract_profile_runtime_overrides as _extract_profile_runtime_overrides_shared,
    extract_unified_runtime_overrides as _extract_unified_runtime_overrides_shared,
    load_ticker_config_aggregate,
    resolve_active_adaptive_tuner_candidate as _resolve_active_adaptive_tuner_candidate_shared,
    resolve_active_unified_profile as _resolve_active_unified_profile_shared,
    resolve_effective_aos_state,
)
from src.services.config_publisher_service import (
    normalize_strategy_key as _normalize_strategy_key_shared,
    publish_active_adaptive_tuner_profile as _publish_active_adaptive_tuner_profile_shared,
    publish_active_strategy_combo as _publish_active_strategy_combo_shared,
    publish_effective_aos_state,
)
from src.services.strategy_api_types import StrategyApiIntegrationDeps


def normalize_strategy_key(name: Any) -> str:
    return _normalize_strategy_key_shared(name)


def resolve_active_adaptive_tuner_candidate(
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    return _resolve_active_adaptive_tuner_candidate_shared(ticker_config, deps)


def resolve_active_unified_profile(
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    return _resolve_active_unified_profile_shared(ticker_config, deps)


def extract_profile_runtime_overrides(
    candidate: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    return _extract_profile_runtime_overrides_shared(candidate, deps)


def _extract_unified_runtime_overrides(
    strategy_profile: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    return _extract_unified_runtime_overrides_shared(strategy_profile, deps)


async def apply_active_strategy_combo(
    strategy_api_url: str,
    ticker: str,
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    return await _publish_active_strategy_combo_shared(
        strategy_api_url=strategy_api_url,
        ticker=ticker,
        ticker_config=ticker_config,
        deps=deps,
    )


async def apply_active_adaptive_tuner_profile(
    strategy_api_url: str,
    ticker_config: Dict[str, Any],
    deps: StrategyApiIntegrationDeps,
) -> Dict[str, Any]:
    return await _publish_active_adaptive_tuner_profile_shared(
        strategy_api_url=strategy_api_url,
        ticker_config=ticker_config,
        deps=deps,
    )


async def apply_aos_optimizations(
    strategy_api_url: str,
    ticker: str,
    deps: StrategyApiIntegrationDeps,
    *,
    remote_sync: bool = True,
    aos_config_path: str | None = None,
) -> Dict[str, Any]:
    aggregate = load_ticker_config_aggregate(
        ticker=ticker,
        deps=TickerConfigRepositoryDeps(
            load_aos_config=deps.load_aos_config,
            get_ticker_positioning_config=deps.get_ticker_positioning_config,
            normalize_strategy_combo_profiles=deps.normalize_strategy_combo_profiles,
            normalize_unified_profiles=deps.normalize_unified_profiles,
            normalize_tuner_profiles=deps.normalize_tuner_profiles,
            positioning_config_keys=deps.positioning_config_keys,
        ),
        aos_config_path=aos_config_path,
    )
    state = resolve_effective_aos_state(aggregate, deps)

    if not state.ticker_config:
        return (
            {"positioning": dict(aggregate.positioning)}
            if aggregate.positioning
            else {}
        )

    if remote_sync:
        return await publish_effective_aos_state(
            strategy_api_url=strategy_api_url,
            ticker=ticker,
            state=state,
            deps=deps,
        )

    applied = dict(state.applied)
    applied["remote_sync_skipped"] = True
    if state.unified_profile:
        strategy_profile = state.unified_profile.get("strategy_profile")
        if not isinstance(strategy_profile, dict):
            strategy_profile = {}
        strategy_params = strategy_profile.get("strategy_params")
        if isinstance(strategy_params, dict) and strategy_params:
            unified_profile = applied.get("unified_profile")
            if isinstance(unified_profile, dict):
                unified_profile = dict(unified_profile)
                unified_profile["strategy_sync_skipped"] = True
                applied["unified_profile"] = unified_profile
        return applied

    adaptive_profile = applied.get("adaptive_profile")
    if isinstance(adaptive_profile, dict):
        adaptive_profile = dict(adaptive_profile)
        adaptive_profile["remote_sync_skipped"] = True
        applied["adaptive_profile"] = adaptive_profile
    return applied
