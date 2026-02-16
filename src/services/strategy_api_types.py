from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List


@dataclass
class StrategyApiIntegrationDeps:
    load_strategy_overrides: Callable[[], Dict[str, Any]]
    sanitize_strategy_params: Callable[[Any], Dict[str, Any]]
    normalize_strategy_combo_profiles: Callable[[Any], List[Dict[str, Any]]]
    normalize_tuner_profiles: Callable[[Any], List[Dict[str, Any]]]
    normalize_strategy_selection_mode: Callable[[Any], str]
    normalize_clamped_int: Callable[..., int]
    normalize_momentum_diversification_payload: Callable[[Any], Any]
    load_aos_config: Callable[..., Dict[str, Any]]
    get_ticker_positioning_config: Callable[..., Dict[str, Any]]
    positioning_config_keys: Iterable[str]
    apply_strategy_param_map: Callable[[str, Dict[str, Dict[str, Any]]], Awaitable[Dict[str, Any]]]
    apply_orchestrator_config: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]
    fetch_remote_strategies: Callable[[str], Awaitable[Dict[str, Any]]]
    apply_active_strategy_combo: Callable[[str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]
    apply_active_adaptive_tuner_profile: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]
    logger: Any
