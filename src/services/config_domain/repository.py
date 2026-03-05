from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

_PROFILE_PLACEHOLDER_TOKENS = {"none", "null", "n/a", "na", "undefined", "-"}


def normalize_profile_ref_token(value: Any) -> Optional[str]:
    token = str(value).strip() if value is not None else ""
    if not token:
        return None
    if token.lower() in _PROFILE_PLACEHOLDER_TOKENS:
        return None
    return token


@dataclass(frozen=True)
class TickerConfigAggregate:
    ticker: str
    ticker_config: Dict[str, Any]
    positioning: Dict[str, Any]
    strategy_combo_profiles: List[Dict[str, Any]]
    adaptive_tuner_profiles: List[Dict[str, Any]]
    unified_profiles: List[Dict[str, Any]]
    active_strategy_combo_profile_id: Optional[str]
    active_adaptive_tuner_profile_id: Optional[str]
    active_unified_profile_id: Optional[str]


@dataclass(frozen=True)
class TickerConfigRepositoryDeps:
    load_aos_config: Callable[..., Dict[str, Any]]
    get_ticker_positioning_config: Callable[..., Dict[str, Any]]
    normalize_strategy_combo_profiles: Callable[[Any], List[Dict[str, Any]]]
    normalize_unified_profiles: Callable[[Any], List[Dict[str, Any]]]
    normalize_tuner_profiles: Callable[[Any], List[Dict[str, Any]]]
    positioning_config_keys: Iterable[str]


def _load_aos_config_safe(
    *,
    load_aos_config: Callable[..., Dict[str, Any]],
    aos_config_path: Optional[str],
) -> Dict[str, Any]:
    try:
        config = (
            load_aos_config(aos_config_path) if aos_config_path else load_aos_config()
        )
    except TypeError:
        config = load_aos_config()
    except Exception:
        return {}
    return config if isinstance(config, dict) else {}


def _safe_ticker_config(aos_config: Dict[str, Any], ticker_upper: str) -> Dict[str, Any]:
    tickers = aos_config.get("tickers", {}) if isinstance(aos_config, dict) else {}
    if not isinstance(tickers, dict):
        return {}
    ticker_cfg = tickers.get(ticker_upper, {})
    return deepcopy(ticker_cfg) if isinstance(ticker_cfg, dict) else {}


def _safe_positioning(
    *,
    ticker_upper: str,
    ticker_cfg: Dict[str, Any],
    deps: TickerConfigRepositoryDeps,
) -> Dict[str, Any]:
    positioning_cfg: Dict[str, Any]
    try:
        raw_positioning = deps.get_ticker_positioning_config(ticker_upper)
    except Exception:
        raw_positioning = {}
    positioning_cfg = (
        deepcopy(raw_positioning) if isinstance(raw_positioning, dict) else {}
    )

    legacy_positioning: Dict[str, Any] = {}
    for key in deps.positioning_config_keys:
        if key in ticker_cfg:
            legacy_positioning[str(key)] = ticker_cfg.get(key)
    if not legacy_positioning:
        return positioning_cfg
    merged = dict(legacy_positioning)
    merged.update(positioning_cfg)
    return merged


def load_ticker_config_aggregate(
    *,
    ticker: str,
    deps: TickerConfigRepositoryDeps,
    aos_config_path: Optional[str] = None,
) -> TickerConfigAggregate:
    ticker_upper = str(ticker or "").upper().strip()
    aos_config = _load_aos_config_safe(
        load_aos_config=deps.load_aos_config,
        aos_config_path=aos_config_path,
    )
    ticker_cfg = _safe_ticker_config(aos_config, ticker_upper)
    positioning_cfg = _safe_positioning(
        ticker_upper=ticker_upper,
        ticker_cfg=ticker_cfg,
        deps=deps,
    )
    strategy_combo_profiles = deps.normalize_strategy_combo_profiles(
        ticker_cfg.get("strategy_combo_profiles", [])
    )
    adaptive_tuner_profiles = deps.normalize_tuner_profiles(
        ticker_cfg.get("adaptive_tuner_profiles", [])
    )
    unified_profiles = deps.normalize_unified_profiles(
        ticker_cfg.get("unified_profiles", [])
    )
    return TickerConfigAggregate(
        ticker=ticker_upper,
        ticker_config=ticker_cfg,
        positioning=positioning_cfg,
        strategy_combo_profiles=strategy_combo_profiles,
        adaptive_tuner_profiles=adaptive_tuner_profiles,
        unified_profiles=unified_profiles,
        active_strategy_combo_profile_id=normalize_profile_ref_token(
            ticker_cfg.get("active_strategy_combo_profile_id")
        ),
        active_adaptive_tuner_profile_id=normalize_profile_ref_token(
            ticker_cfg.get("active_adaptive_tuner_profile_id")
        ),
        active_unified_profile_id=normalize_profile_ref_token(
            ticker_cfg.get("active_unified_profile_id")
        ),
    )
