from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, Optional

from src.momentum_diversification import normalize_momentum_diversification_payload
from src.normalization import (
    normalize_strategy_combo_profiles,
    normalize_tuner_profiles,
    normalize_unified_profiles,
)
from src.services.adaptive_tuner_core_service import (
    normalize_clamped_int,
    normalize_strategy_selection_mode,
)
from src.services.config_domain import (
    TickerConfigRepositoryDeps,
    load_ticker_config_aggregate,
    resolve_effective_aos_applied_snapshot,
)


def _local_profile_resolution_deps() -> Any:
    return SimpleNamespace(
        normalize_strategy_combo_profiles=normalize_strategy_combo_profiles,
        normalize_unified_profiles=normalize_unified_profiles,
        normalize_tuner_profiles=normalize_tuner_profiles,
        normalize_strategy_selection_mode=normalize_strategy_selection_mode,
        normalize_clamped_int=normalize_clamped_int,
        normalize_momentum_diversification_payload=(
            normalize_momentum_diversification_payload
        ),
    )


def resolve_local_aos_applied(
    *,
    ticker: str,
    load_aos_config: Callable[..., Dict[str, Any]],
    get_ticker_positioning_config: Callable[[str], Dict[str, Any]],
    positioning_config_keys: Iterable[str] = (),
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    aggregate = load_ticker_config_aggregate(
        ticker=ticker,
        deps=TickerConfigRepositoryDeps(
            load_aos_config=load_aos_config,
            get_ticker_positioning_config=get_ticker_positioning_config,
            normalize_strategy_combo_profiles=normalize_strategy_combo_profiles,
            normalize_unified_profiles=normalize_unified_profiles,
            normalize_tuner_profiles=normalize_tuner_profiles,
            positioning_config_keys=positioning_config_keys,
        ),
        aos_config_path=aos_config_path,
    )
    return resolve_effective_aos_applied_snapshot(
        aggregate,
        _local_profile_resolution_deps(),
    )
