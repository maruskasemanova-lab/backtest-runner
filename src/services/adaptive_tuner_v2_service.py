from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from src.models.tuner_requests import AdaptiveTunerRequest


@dataclass
class AdaptiveTunerV2Deps:
    build_adaptive_tuner_search_space: Callable[
        [AdaptiveTunerRequest], Dict[str, List[Any]]
    ]
    normalize_momentum_diversification_payload: Callable[[Any], Any]
    normalize_strategy_sets: Callable[[Any, List[str]], Any]
    normalize_float_options: Callable[..., List[float]]
    normalize_regime_filter_sets: Callable[[Any], Any]
    normalize_int_options: Callable[..., List[int]]
    normalize_time_window_sets: Callable[[Any], Any]
    normalize_bool_options: Callable[[Any, List[bool]], List[bool]]
    normalize_regime_strategy_map_sets: Callable[[Any, List[str]], Any]
    normalize_strategy_selection_mode: Callable[[Any], str]
    build_adaptive_candidate_config: Callable[..., Dict[str, Any]]
    strategy_family_map: Dict[str, str]
    random_factory: Callable[[int], Any]


def build_v2_search_space(
    request: AdaptiveTunerRequest,
    ticker_config: Dict[str, Any],
    deps: AdaptiveTunerV2Deps,
) -> Dict[str, Any]:
    """Build multi-dimensional search space from request options + AOS ticker config defaults."""
    _normalize_momentum_diversification_payload = (
        deps.normalize_momentum_diversification_payload
    )
    _normalize_strategy_sets = deps.normalize_strategy_sets
    _normalize_float_options = deps.normalize_float_options
    _normalize_regime_filter_sets = deps.normalize_regime_filter_sets
    _normalize_int_options = deps.normalize_int_options
    _normalize_time_window_sets = deps.normalize_time_window_sets
    _normalize_bool_options = deps.normalize_bool_options
    _normalize_regime_strategy_map_sets = deps.normalize_regime_strategy_map_sets
    _build_adaptive_tuner_search_space = deps.build_adaptive_tuner_search_space

    l2_cfg = (
        ticker_config.get("l2", {}) if isinstance(ticker_config.get("l2"), dict) else {}
    )
    adaptive_cfg = (
        ticker_config.get("adaptive", {})
        if isinstance(ticker_config.get("adaptive"), dict)
        else {}
    )
    momentum_cfg = (
        _normalize_momentum_diversification_payload(
            adaptive_cfg.get("momentum_diversification")
        )
        or {}
    )

    enabled_strategies: List[str] = []
    strategy_name = ticker_config.get("strategy", "")
    if isinstance(strategy_name, str) and strategy_name.strip():
        enabled_strategies.append(strategy_name.strip().lower())
    backup = ticker_config.get("backup_strategy", "")
    if isinstance(backup, str) and backup.strip():
        backup_lower = backup.strip().lower()
        if backup_lower not in enabled_strategies:
            enabled_strategies.append(backup_lower)
    if not enabled_strategies:
        enabled_strategies = ["momentum_flow"]

    v1_space = _build_adaptive_tuner_search_space(request)

    return {
        **v1_space,
        "strategy_sets": _normalize_strategy_sets(
            request.strategy_sets, enabled_strategies
        ),
        "l2_min_delta": _normalize_float_options(
            request.l2_min_delta_options,
            default=[float(l2_cfg.get("min_delta", 500)), 1000, 2000, 5000],
            min_value=0.0,
            max_value=100_000.0,
        ),
        "l2_min_imbalance": _normalize_float_options(
            request.l2_min_imbalance_options,
            default=[0.05, float(l2_cfg.get("min_imbalance", 0.12)), 0.20, 0.35],
            min_value=0.0,
            max_value=1.0,
        ),
        "l2_min_signed_aggression": _normalize_float_options(
            request.l2_min_signed_aggression_options,
            default=[
                0.05,
                float(l2_cfg.get("min_signed_aggression", 0.12)),
                0.20,
                0.35,
            ],
            min_value=0.0,
            max_value=1.0,
        ),
        "l2_min_directional_consistency": _normalize_float_options(
            request.l2_min_directional_consistency_options,
            default=[0.3, float(l2_cfg.get("min_directional_consistency", 0.5)), 0.7],
            min_value=0.0,
            max_value=1.0,
        ),
        "regime_filter_sets": _normalize_regime_filter_sets(request.regime_filter_sets),
        "base_threshold": _normalize_float_options(
            request.base_threshold_options,
            default=[45.0, 50.0, 55.0, 60.0, 65.0],
            min_value=0.0,
            max_value=100.0,
        ),
        "min_confirming_sources": _normalize_int_options(
            request.min_confirming_sources_options,
            default=[1, 2, 3],
            min_value=1,
            max_value=5,
        ),
        "min_confidence": _normalize_float_options(
            request.min_confidence_options,
            default=[50.0, 55.0, 60.0, 65.0],
            min_value=30.0,
            max_value=90.0,
        ),
        "atr_stop_multiplier": _normalize_float_options(
            request.atr_stop_multiplier_options,
            default=[0.7, 1.0, 1.3, 1.8],
            min_value=0.3,
            max_value=4.0,
        ),
        "rr_ratio": _normalize_float_options(
            request.rr_ratio_options,
            default=[1.5, 2.0, 2.5, 3.0],
            min_value=1.0,
            max_value=5.0,
        ),
        "time_window_sets": _normalize_time_window_sets(request.time_window_sets),
        "adverse_flow_consistency": _normalize_float_options(
            request.adverse_flow_consistency_options,
            default=[0.35, 0.45, 0.55],
            min_value=0.1,
            max_value=0.9,
        ),
        "adverse_book_pressure": _normalize_float_options(
            request.adverse_book_pressure_options,
            default=[0.10, 0.15, 0.22],
            min_value=0.05,
            max_value=0.5,
        ),
        "time_exit_bars": _normalize_int_options(
            request.time_exit_bars_options,
            default=[15, 25, 35, 50],
            min_value=5,
            max_value=120,
        ),
        "trailing_stop_pct": _normalize_float_options(
            request.trailing_stop_pct_options,
            default=[0.4, 0.6, 0.8, 1.0, 1.3],
            min_value=0.1,
            max_value=3.0,
        ),
        "momentum_diversification_enabled": _normalize_bool_options(
            request.momentum_diversification_enabled_options,
            default=[True, False],
        ),
        "momentum_route_enabled": _normalize_bool_options(
            request.momentum_route_enabled_options,
            default=[True, False],
        ),
        "momentum_min_flow_score": _normalize_float_options(
            request.momentum_min_flow_score_options,
            default=[float(momentum_cfg.get("min_flow_score", 52.0)), 60.0, 68.0],
            min_value=0.0,
            max_value=100.0,
        ),
        "momentum_min_directional_consistency": _normalize_float_options(
            request.momentum_min_directional_consistency_options,
            default=[
                float(momentum_cfg.get("min_directional_consistency", 0.35)),
                0.45,
                0.55,
            ],
            min_value=0.0,
            max_value=1.0,
        ),
        "momentum_min_signed_aggression": _normalize_float_options(
            request.momentum_min_signed_aggression_options,
            default=[
                float(momentum_cfg.get("min_signed_aggression", 0.03)),
                0.06,
                0.10,
            ],
            min_value=0.0,
            max_value=1.0,
        ),
        "momentum_min_imbalance": _normalize_float_options(
            request.momentum_min_imbalance_options,
            default=[float(momentum_cfg.get("min_imbalance", 0.02)), 0.06, 0.12],
            min_value=0.0,
            max_value=1.0,
        ),
        "momentum_min_cvd": _normalize_float_options(
            request.momentum_min_cvd_options,
            default=[float(momentum_cfg.get("min_cvd", 0.0)), 1000.0, 3000.0],
            min_value=-1_000_000_000.0,
            max_value=1_000_000_000.0,
        ),
        "momentum_min_directional_price_change_pct": _normalize_float_options(
            request.momentum_min_directional_price_change_pct_options,
            default=[
                float(momentum_cfg.get("min_directional_price_change_pct", 0.0)),
                0.05,
                0.15,
            ],
            min_value=-100.0,
            max_value=100.0,
        ),
        "momentum_min_price_trend_efficiency": _normalize_float_options(
            request.momentum_min_price_trend_efficiency_options,
            default=[
                float(momentum_cfg.get("min_price_trend_efficiency", 0.0)),
                0.22,
                0.35,
            ],
            min_value=0.0,
            max_value=1.0,
        ),
        "momentum_min_last_bar_body_ratio": _normalize_float_options(
            request.momentum_min_last_bar_body_ratio_options,
            default=[
                float(momentum_cfg.get("min_last_bar_body_ratio", 0.0)),
                0.30,
                0.45,
            ],
            min_value=0.0,
            max_value=1.0,
        ),
        "momentum_min_last_bar_close_location": _normalize_float_options(
            request.momentum_min_last_bar_close_location_options,
            default=[
                float(momentum_cfg.get("min_last_bar_close_location", 0.0)),
                0.55,
                0.70,
            ],
            min_value=0.0,
            max_value=1.0,
        ),
        "momentum_min_delta_acceleration": _normalize_float_options(
            request.momentum_min_delta_acceleration_options,
            default=[
                float(momentum_cfg.get("min_delta_acceleration", 0.0)),
                500.0,
                1500.0,
            ],
            min_value=-1_000_000.0,
            max_value=1_000_000.0,
        ),
        "momentum_min_delta_price_divergence": _normalize_float_options(
            request.momentum_min_delta_price_divergence_options,
            default=[
                float(momentum_cfg.get("min_delta_price_divergence", -0.45)),
                -0.20,
                0.0,
            ],
            min_value=-10.0,
            max_value=10.0,
        ),
        "momentum_route_flow_score_impulse": _normalize_float_options(
            request.momentum_route_flow_score_impulse_options,
            default=[
                float(momentum_cfg.get("route_flow_score_impulse", 62.0)),
                68.0,
                74.0,
            ],
            min_value=0.0,
            max_value=100.0,
        ),
        "momentum_fail_fast_exit_enabled": _normalize_bool_options(
            request.momentum_fail_fast_exit_enabled_options,
            default=[True, False],
        ),
        "momentum_fail_fast_max_bars": _normalize_int_options(
            request.momentum_fail_fast_max_bars_options,
            default=[int(momentum_cfg.get("fail_fast_max_bars", 3)), 4, 6],
            min_value=1,
            max_value=30,
        ),
        # Context-aware exit response dimensions (Phase 3)
        "context_regime_flip_tighten_stop_pct": _normalize_float_options(
            request.context_regime_flip_tighten_stop_pct_options,
            default=[0.0, 0.15, 0.30, 0.50],
            min_value=0.0,
            max_value=0.8,
        ),
        "context_regime_flip_shorten_time_pct": _normalize_float_options(
            request.context_regime_flip_shorten_time_pct_options,
            default=[0.0, 0.30, 0.50],
            min_value=0.0,
            max_value=1.0,
        ),
        "context_regime_flip_exit_when_losing": _normalize_bool_options(
            request.context_regime_flip_exit_when_losing_options,
            default=[False, True],
        ),
        "context_regime_flip_exit_loss_threshold_pct": _normalize_float_options(
            request.context_regime_flip_exit_loss_threshold_pct_options,
            default=[0.2, 0.3, 0.5],
            min_value=0.0,
            max_value=2.0,
        ),
        "context_flow_reversal_move_to_breakeven": _normalize_bool_options(
            request.context_flow_reversal_move_to_breakeven_options,
            default=[False, True],
        ),
        "context_flow_reversal_exit_when_losing": _normalize_bool_options(
            request.context_flow_reversal_exit_when_losing_options,
            default=[False, True],
        ),
        "context_momentum_stall_time_multiplier": _normalize_float_options(
            request.context_momentum_stall_time_multiplier_options,
            default=[0.5, 0.7, 1.0],
            min_value=0.3,
            max_value=1.0,
        ),
        "context_volatility_spike_tighten_pct": _normalize_float_options(
            request.context_volatility_spike_tighten_pct_options,
            default=[0.0, 0.15, 0.25],
            min_value=0.0,
            max_value=0.5,
        ),
        "context_response_grace_bars": _normalize_int_options(
            request.context_response_grace_bars_options,
            default=[1, 2, 3],
            min_value=1,
            max_value=5,
        ),
        "regime_strategy_maps": _normalize_regime_strategy_map_sets(
            request.regime_strategy_map_sets,
            enabled_strategies,
        ),
    }


def v2_candidate_key(candidate: Dict[str, Any], deps: AdaptiveTunerV2Deps) -> tuple:
    """Create a hashable key for v2 candidate deduplication."""
    _normalize_strategy_selection_mode = deps.normalize_strategy_selection_mode
    strategy_key = tuple(sorted(candidate.get("enabled_strategies", [])))
    regime_key = tuple(sorted(candidate.get("regime_filter", [])))
    return (
        strategy_key,
        regime_key,
        candidate.get("l2_min_delta"),
        candidate.get("l2_min_imbalance"),
        candidate.get("l2_min_signed_aggression"),
        candidate.get("l2_min_directional_consistency"),
        candidate.get("base_threshold"),
        candidate.get("min_confirming_sources"),
        candidate.get("min_confidence"),
        candidate.get("atr_stop_multiplier"),
        candidate.get("rr_ratio"),
        tuple(sorted(candidate.get("trading_hours", []) or [])),
        candidate.get("adverse_flow_consistency"),
        candidate.get("adverse_book_pressure"),
        candidate.get("time_exit_bars"),
        candidate.get("trailing_stop_pct"),
        candidate.get("momentum_diversification_enabled"),
        candidate.get("momentum_route_enabled"),
        candidate.get("momentum_min_flow_score"),
        candidate.get("momentum_min_directional_consistency"),
        candidate.get("momentum_min_signed_aggression"),
        candidate.get("momentum_min_imbalance"),
        candidate.get("momentum_min_cvd"),
        candidate.get("momentum_min_directional_price_change_pct"),
        candidate.get("momentum_min_price_trend_efficiency"),
        candidate.get("momentum_min_last_bar_body_ratio"),
        candidate.get("momentum_min_last_bar_close_location"),
        candidate.get("momentum_min_delta_acceleration"),
        candidate.get("momentum_min_delta_price_divergence"),
        candidate.get("momentum_route_flow_score_impulse"),
        candidate.get("momentum_fail_fast_exit_enabled"),
        candidate.get("momentum_fail_fast_max_bars"),
        _normalize_strategy_selection_mode(candidate.get("strategy_selection_mode")),
        candidate.get("flow_bias_enabled"),
        (
            json.dumps(candidate.get("regime_strategy_map"), sort_keys=True)
            if candidate.get("regime_strategy_map") is not None
            else None
        ),
        candidate.get("context_regime_flip_tighten_stop_pct"),
        candidate.get("context_regime_flip_shorten_time_pct"),
        candidate.get("context_regime_flip_exit_when_losing"),
        candidate.get("context_regime_flip_exit_loss_threshold_pct"),
        candidate.get("context_flow_reversal_move_to_breakeven"),
        candidate.get("context_flow_reversal_exit_when_losing"),
        candidate.get("context_momentum_stall_time_multiplier"),
        candidate.get("context_volatility_spike_tighten_pct"),
        candidate.get("context_response_grace_bars"),
    )


def build_v2_baseline_candidate(
    search_space: Dict[str, Any],
    deps: AdaptiveTunerV2Deps,
) -> Dict[str, Any]:
    """Build a baseline candidate using the first (default) value of each dimension."""

    def _first(key: str):
        vals = search_space.get(key, [])
        return vals[0] if vals else None

    return {
        "strategy_selection_mode": _first("strategy_selection_mode"),
        "max_active_strategies": _first("max_active_strategies"),
        "min_active_bars_before_switch": _first("min_active_bars_before_switch"),
        "switch_cooldown_bars": _first("switch_cooldown_bars"),
        "flow_bias_enabled": _first("flow_bias_enabled"),
        "use_ohlcv_fallbacks": _first("use_ohlcv_fallbacks"),
        "enabled_strategies": (
            list(search_space["strategy_sets"][0])
            if search_space.get("strategy_sets")
            else []
        ),
        "l2_min_delta": _first("l2_min_delta"),
        "l2_min_imbalance": _first("l2_min_imbalance"),
        "l2_min_signed_aggression": _first("l2_min_signed_aggression"),
        "l2_min_directional_consistency": _first("l2_min_directional_consistency"),
        "regime_filter": (
            list(search_space["regime_filter_sets"][0])
            if search_space.get("regime_filter_sets")
            else []
        ),
        "base_threshold": _first("base_threshold"),
        "min_confirming_sources": _first("min_confirming_sources"),
        "min_confidence": _first("min_confidence"),
        "atr_stop_multiplier": _first("atr_stop_multiplier"),
        "rr_ratio": _first("rr_ratio"),
        "trading_hours": (
            list(search_space["time_window_sets"][0])
            if search_space.get("time_window_sets")
            else []
        ),
        "adverse_flow_consistency": _first("adverse_flow_consistency"),
        "adverse_book_pressure": _first("adverse_book_pressure"),
        "time_exit_bars": _first("time_exit_bars"),
        "trailing_stop_pct": _first("trailing_stop_pct"),
        "momentum_diversification_enabled": _first("momentum_diversification_enabled"),
        "momentum_route_enabled": _first("momentum_route_enabled"),
        "momentum_min_flow_score": _first("momentum_min_flow_score"),
        "momentum_min_directional_consistency": _first(
            "momentum_min_directional_consistency"
        ),
        "momentum_min_signed_aggression": _first("momentum_min_signed_aggression"),
        "momentum_min_imbalance": _first("momentum_min_imbalance"),
        "momentum_min_cvd": _first("momentum_min_cvd"),
        "momentum_min_directional_price_change_pct": _first(
            "momentum_min_directional_price_change_pct"
        ),
        "momentum_min_price_trend_efficiency": _first(
            "momentum_min_price_trend_efficiency"
        ),
        "momentum_min_last_bar_body_ratio": _first("momentum_min_last_bar_body_ratio"),
        "momentum_min_last_bar_close_location": _first(
            "momentum_min_last_bar_close_location"
        ),
        "momentum_min_delta_acceleration": _first("momentum_min_delta_acceleration"),
        "momentum_min_delta_price_divergence": _first(
            "momentum_min_delta_price_divergence"
        ),
        "momentum_route_flow_score_impulse": _first(
            "momentum_route_flow_score_impulse"
        ),
        "momentum_fail_fast_exit_enabled": _first("momentum_fail_fast_exit_enabled"),
        "momentum_fail_fast_max_bars": _first("momentum_fail_fast_max_bars"),
        "context_regime_flip_tighten_stop_pct": _first(
            "context_regime_flip_tighten_stop_pct"
        ),
        "context_regime_flip_shorten_time_pct": _first(
            "context_regime_flip_shorten_time_pct"
        ),
        "context_regime_flip_exit_when_losing": _first(
            "context_regime_flip_exit_when_losing"
        ),
        "context_regime_flip_exit_loss_threshold_pct": _first(
            "context_regime_flip_exit_loss_threshold_pct"
        ),
        "context_flow_reversal_move_to_breakeven": _first(
            "context_flow_reversal_move_to_breakeven"
        ),
        "context_flow_reversal_exit_when_losing": _first(
            "context_flow_reversal_exit_when_losing"
        ),
        "context_momentum_stall_time_multiplier": _first(
            "context_momentum_stall_time_multiplier"
        ),
        "context_volatility_spike_tighten_pct": _first(
            "context_volatility_spike_tighten_pct"
        ),
        "context_response_grace_bars": _first("context_response_grace_bars"),
        "regime_strategy_map": (
            search_space.get("regime_strategy_maps", [None])[0]
            if search_space.get("regime_strategy_maps")
            else None
        ),
    }


def build_v2_random_candidates(
    search_space: Dict[str, Any],
    *,
    n_trials: int,
    seed: int,
    neighborhood_search: bool = False,
    deps: AdaptiveTunerV2Deps,
) -> List[Dict[str, Any]]:
    """Build random candidates sampling across all v2 dimensions."""
    rng = deps.random_factory(seed)
    attempts = 0
    max_attempts = max(500, n_trials * 30)
    candidates: List[Dict[str, Any]] = []
    seen = set()

    baseline = build_v2_baseline_candidate(search_space, deps)

    n_neighborhood = (n_trials // 2) if neighborhood_search else 0

    perturbable_dims = [
        "l2_min_delta",
        "l2_min_imbalance",
        "l2_min_signed_aggression",
        "l2_min_directional_consistency",
        "base_threshold",
        "min_confirming_sources",
        "min_confidence",
        "atr_stop_multiplier",
        "rr_ratio",
        "adverse_flow_consistency",
        "adverse_book_pressure",
        "time_exit_bars",
        "trailing_stop_pct",
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
        "context_regime_flip_tighten_stop_pct",
        "context_regime_flip_shorten_time_pct",
        "context_regime_flip_exit_when_losing",
        "context_regime_flip_exit_loss_threshold_pct",
        "context_flow_reversal_move_to_breakeven",
        "context_flow_reversal_exit_when_losing",
        "context_momentum_stall_time_multiplier",
        "context_volatility_spike_tighten_pct",
        "context_response_grace_bars",
    ]
    list_dims = [
        "strategy_sets",
        "regime_filter_sets",
        "time_window_sets",
        "regime_strategy_maps",
    ]

    neighbor_attempts = 0
    while len(candidates) < n_neighborhood and neighbor_attempts < max_attempts:
        neighbor_attempts += 1
        candidate = dict(baseline)
        n_perturb = rng.choice([1, 1, 1, 2])
        dims_to_change = rng.sample(
            perturbable_dims + list_dims,
            min(n_perturb, len(perturbable_dims) + len(list_dims)),
        )
        for dim in dims_to_change:
            if dim == "strategy_sets":
                candidate["enabled_strategies"] = list(
                    rng.choice(search_space["strategy_sets"])
                )
            elif dim == "regime_filter_sets":
                candidate["regime_filter"] = list(
                    rng.choice(search_space["regime_filter_sets"])
                )
            elif dim == "regime_strategy_maps":
                candidate["regime_strategy_map"] = rng.choice(
                    search_space["regime_strategy_maps"]
                )
            elif dim == "time_window_sets":
                candidate["trading_hours"] = list(
                    rng.choice(search_space["time_window_sets"])
                )
            elif dim in search_space:
                candidate[dim] = rng.choice(search_space[dim])
        key = v2_candidate_key(candidate, deps)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)

    while len(candidates) < n_trials and attempts < max_attempts:
        attempts += 1
        strategy_set = rng.choice(search_space["strategy_sets"])
        regime_set = rng.choice(search_space["regime_filter_sets"])

        candidate = {
            "strategy_selection_mode": rng.choice(
                search_space["strategy_selection_mode"]
            ),
            "max_active_strategies": rng.choice(search_space["max_active_strategies"]),
            "min_active_bars_before_switch": rng.choice(
                search_space["min_active_bars_before_switch"]
            ),
            "switch_cooldown_bars": rng.choice(search_space["switch_cooldown_bars"]),
            "flow_bias_enabled": rng.choice(search_space["flow_bias_enabled"]),
            "use_ohlcv_fallbacks": rng.choice(search_space["use_ohlcv_fallbacks"]),
            "enabled_strategies": list(strategy_set),
            "l2_min_delta": rng.choice(search_space["l2_min_delta"]),
            "l2_min_imbalance": rng.choice(search_space["l2_min_imbalance"]),
            "l2_min_signed_aggression": rng.choice(
                search_space["l2_min_signed_aggression"]
            ),
            "l2_min_directional_consistency": rng.choice(
                search_space["l2_min_directional_consistency"]
            ),
            "regime_filter": list(regime_set),
            "base_threshold": rng.choice(search_space["base_threshold"]),
            "min_confirming_sources": rng.choice(
                search_space["min_confirming_sources"]
            ),
            "min_confidence": rng.choice(search_space["min_confidence"]),
            "atr_stop_multiplier": rng.choice(search_space["atr_stop_multiplier"]),
            "rr_ratio": rng.choice(search_space["rr_ratio"]),
            "trading_hours": list(rng.choice(search_space["time_window_sets"])),
            "adverse_flow_consistency": rng.choice(
                search_space["adverse_flow_consistency"]
            ),
            "adverse_book_pressure": rng.choice(search_space["adverse_book_pressure"]),
            "time_exit_bars": rng.choice(search_space["time_exit_bars"]),
            "trailing_stop_pct": rng.choice(search_space["trailing_stop_pct"]),
            "momentum_diversification_enabled": rng.choice(
                search_space["momentum_diversification_enabled"]
            ),
            "momentum_route_enabled": rng.choice(
                search_space["momentum_route_enabled"]
            ),
            "momentum_min_flow_score": rng.choice(
                search_space["momentum_min_flow_score"]
            ),
            "momentum_min_directional_consistency": rng.choice(
                search_space["momentum_min_directional_consistency"]
            ),
            "momentum_min_signed_aggression": rng.choice(
                search_space["momentum_min_signed_aggression"]
            ),
            "momentum_min_imbalance": rng.choice(
                search_space["momentum_min_imbalance"]
            ),
            "momentum_min_cvd": rng.choice(search_space["momentum_min_cvd"]),
            "momentum_min_directional_price_change_pct": rng.choice(
                search_space["momentum_min_directional_price_change_pct"]
            ),
            "momentum_min_price_trend_efficiency": rng.choice(
                search_space["momentum_min_price_trend_efficiency"]
            ),
            "momentum_min_last_bar_body_ratio": rng.choice(
                search_space["momentum_min_last_bar_body_ratio"]
            ),
            "momentum_min_last_bar_close_location": rng.choice(
                search_space["momentum_min_last_bar_close_location"]
            ),
            "momentum_min_delta_acceleration": rng.choice(
                search_space["momentum_min_delta_acceleration"]
            ),
            "momentum_min_delta_price_divergence": rng.choice(
                search_space["momentum_min_delta_price_divergence"]
            ),
            "momentum_route_flow_score_impulse": rng.choice(
                search_space["momentum_route_flow_score_impulse"]
            ),
            "momentum_fail_fast_exit_enabled": rng.choice(
                search_space["momentum_fail_fast_exit_enabled"]
            ),
            "momentum_fail_fast_max_bars": rng.choice(
                search_space["momentum_fail_fast_max_bars"]
            ),
            "context_regime_flip_tighten_stop_pct": rng.choice(
                search_space["context_regime_flip_tighten_stop_pct"]
            ),
            "context_regime_flip_shorten_time_pct": rng.choice(
                search_space["context_regime_flip_shorten_time_pct"]
            ),
            "context_regime_flip_exit_when_losing": rng.choice(
                search_space["context_regime_flip_exit_when_losing"]
            ),
            "context_regime_flip_exit_loss_threshold_pct": rng.choice(
                search_space["context_regime_flip_exit_loss_threshold_pct"]
            ),
            "context_flow_reversal_move_to_breakeven": rng.choice(
                search_space["context_flow_reversal_move_to_breakeven"]
            ),
            "context_flow_reversal_exit_when_losing": rng.choice(
                search_space["context_flow_reversal_exit_when_losing"]
            ),
            "context_momentum_stall_time_multiplier": rng.choice(
                search_space["context_momentum_stall_time_multiplier"]
            ),
            "context_volatility_spike_tighten_pct": rng.choice(
                search_space["context_volatility_spike_tighten_pct"]
            ),
            "context_response_grace_bars": rng.choice(
                search_space["context_response_grace_bars"]
            ),
            "regime_strategy_map": rng.choice(
                search_space.get("regime_strategy_maps", [None])
            ),
        }
        key = v2_candidate_key(candidate, deps)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def build_v2_candidate_config(
    ticker_config: Dict[str, Any],
    candidate: Dict[str, Any],
    adaptive_version: int,
    deps: AdaptiveTunerV2Deps,
) -> Dict[str, Any]:
    """Apply all v2 candidate dimensions to ticker config."""
    _build_adaptive_candidate_config = deps.build_adaptive_candidate_config
    _normalize_momentum_diversification_payload = (
        deps.normalize_momentum_diversification_payload
    )

    cfg = _build_adaptive_candidate_config(ticker_config, candidate, adaptive_version)

    enabled = candidate.get("enabled_strategies", [])
    if isinstance(enabled, list) and enabled:
        cfg["strategy"] = str(enabled[0])
        cfg["backup_strategy"] = str(enabled[1]) if len(enabled) > 1 else ""

    l2_cfg = cfg.get("l2", {})
    if not isinstance(l2_cfg, dict):
        l2_cfg = {}
    l2_keys = [
        ("l2_min_delta", "min_delta"),
        ("l2_min_imbalance", "min_imbalance"),
        ("l2_min_signed_aggression", "min_signed_aggression"),
        ("l2_min_directional_consistency", "min_directional_consistency"),
    ]
    for candidate_key, config_key in l2_keys:
        val = candidate.get(candidate_key)
        if val is not None:
            try:
                l2_cfg[config_key] = float(val)
            except (TypeError, ValueError):
                pass
    cfg["l2"] = l2_cfg

    regime_filter = candidate.get("regime_filter")
    if isinstance(regime_filter, list) and regime_filter:
        cfg["regime_filter"] = list(regime_filter)

    adaptive_cfg = cfg.get("adaptive", {})
    if not isinstance(adaptive_cfg, dict):
        adaptive_cfg = {}
    base_thresh = candidate.get("base_threshold")
    if base_thresh is not None:
        try:
            adaptive_cfg["evidence_base_threshold"] = float(base_thresh)
        except (TypeError, ValueError):
            pass
    min_sources = candidate.get("min_confirming_sources")
    if min_sources is not None:
        try:
            adaptive_cfg["evidence_min_confirming_sources"] = int(min_sources)
        except (TypeError, ValueError):
            pass
    cfg["adaptive"] = adaptive_cfg

    strategy_param_overrides: Dict[str, Any] = {}
    for param_key in ("min_confidence", "atr_stop_multiplier", "rr_ratio"):
        val = candidate.get(param_key)
        if val is not None:
            try:
                strategy_param_overrides[param_key] = float(val)
            except (TypeError, ValueError):
                pass
    if strategy_param_overrides:
        cfg["v2_strategy_param_overrides"] = strategy_param_overrides

    trading_hours = candidate.get("trading_hours")
    if isinstance(trading_hours, list) and trading_hours:
        cfg["trading_hours"] = [int(h) for h in trading_hours]
        cfg["time_filter_enabled"] = True
    else:
        cfg["time_filter_enabled"] = False

    adv_consistency = candidate.get("adverse_flow_consistency")
    if adv_consistency is not None:
        cfg["adverse_flow_consistency_threshold"] = float(adv_consistency)
    adv_book = candidate.get("adverse_book_pressure")
    if adv_book is not None:
        cfg["adverse_book_pressure_threshold"] = float(adv_book)

    te_bars = candidate.get("time_exit_bars")
    if te_bars is not None:
        cfg["time_exit_bars"] = int(te_bars)
    ts_pct = candidate.get("trailing_stop_pct")
    if ts_pct is not None:
        overrides = cfg.get("v2_strategy_param_overrides", {})
        overrides["trailing_stop_pct"] = float(ts_pct)
        cfg["v2_strategy_param_overrides"] = overrides

    momentum_key_map = {
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
    raw_momentum_cfg: Dict[str, Any] = {}
    for candidate_key, cfg_key in momentum_key_map.items():
        if candidate_key in candidate:
            raw_momentum_cfg[cfg_key] = candidate.get(candidate_key)

    direct_momentum_cfg = _normalize_momentum_diversification_payload(
        candidate.get("momentum_diversification")
    )
    if direct_momentum_cfg:
        raw_momentum_cfg.update(direct_momentum_cfg)

    normalized_momentum_cfg = _normalize_momentum_diversification_payload(
        raw_momentum_cfg
    )
    if normalized_momentum_cfg:
        adaptive_cfg = cfg.get("adaptive", {})
        if not isinstance(adaptive_cfg, dict):
            adaptive_cfg = {}
        existing_momentum = (
            _normalize_momentum_diversification_payload(
                adaptive_cfg.get("momentum_diversification")
            )
            or {}
        )
        existing_momentum.update(normalized_momentum_cfg)
        adaptive_cfg["momentum_diversification"] = existing_momentum
        cfg["adaptive"] = adaptive_cfg
        cfg["momentum_diversification"] = existing_momentum

    # Context-aware exit response parameters → adaptive.context_exit_response
    context_key_map = {
        "context_regime_flip_tighten_stop_pct": "regime_flip_tighten_stop_pct",
        "context_regime_flip_shorten_time_pct": "regime_flip_shorten_time_pct",
        "context_regime_flip_exit_when_losing": "regime_flip_exit_when_losing",
        "context_regime_flip_exit_loss_threshold_pct": "regime_flip_exit_loss_threshold_pct",
        "context_flow_reversal_move_to_breakeven": "flow_reversal_move_to_breakeven",
        "context_flow_reversal_exit_when_losing": "flow_reversal_exit_when_losing",
        "context_momentum_stall_time_multiplier": "momentum_stall_time_multiplier",
        "context_volatility_spike_tighten_pct": "volatility_spike_tighten_pct",
        "context_response_grace_bars": "context_response_grace_bars",
    }
    context_exit_cfg: Dict[str, Any] = {}
    for candidate_key, cfg_key in context_key_map.items():
        val = candidate.get(candidate_key)
        if val is not None:
            context_exit_cfg[cfg_key] = val
    if context_exit_cfg:
        adaptive_cfg = cfg.get("adaptive", {})
        if not isinstance(adaptive_cfg, dict):
            adaptive_cfg = {}
        existing = adaptive_cfg.get("context_exit_response", {})
        if not isinstance(existing, dict):
            existing = {}
        existing.update(context_exit_cfg)
        adaptive_cfg["context_exit_response"] = existing
        cfg["adaptive"] = adaptive_cfg

    if "regime_strategy_map" in candidate:
        regime_map = candidate.get("regime_strategy_map")
        adaptive_cfg = cfg.get("adaptive", {})
        if not isinstance(adaptive_cfg, dict):
            adaptive_cfg = {}
        if isinstance(regime_map, dict):
            normalized_map: Dict[str, List[str]] = {}
            for regime in ("TRENDING", "MIXED", "CHOPPY"):
                raw_values = regime_map.get(regime, [])
                cleaned_values: List[str] = []
                seen_values = set()
                if isinstance(raw_values, list):
                    for value in raw_values:
                        strategy_key = str(value).strip().lower()
                        if not strategy_key or strategy_key in seen_values:
                            continue
                        seen_values.add(strategy_key)
                        cleaned_values.append(strategy_key)
                normalized_map[regime] = cleaned_values
            adaptive_cfg["regime_preferences"] = normalized_map
            cfg["regime_strategy_map"] = normalized_map
        else:
            adaptive_cfg.pop("regime_preferences", None)
            cfg.pop("regime_strategy_map", None)
        cfg["adaptive"] = adaptive_cfg

    return cfg


def analyze_vectors(
    trials: List[Dict[str, Any]],
    *,
    min_trades: int = 3,
    deps: AdaptiveTunerV2Deps,
) -> Dict[str, Any]:
    """Analyze trial results to discover dimension importance & surprising vectors."""
    STRATEGY_FAMILY_MAP = deps.strategy_family_map

    if not trials:
        return {
            "dimension_importance": {},
            "top_interactions": [],
            "surprising_vectors": [],
        }

    valid_trials = [
        t
        for t in trials
        if isinstance(t, dict)
        and float(t.get("score", -1e12)) > -999_999
        and int(t.get("metrics", {}).get("total_trades", 0)) >= min_trades
    ]
    if len(valid_trials) < 2:
        return {
            "dimension_importance": {},
            "top_interactions": [],
            "surprising_vectors": [],
        }

    scores = [float(t["score"]) for t in valid_trials]
    overall_mean = sum(scores) / len(scores)
    total_variance = sum((s - overall_mean) ** 2 for s in scores) / len(scores)
    if total_variance < 1e-12:
        return {
            "dimension_importance": {},
            "top_interactions": [],
            "surprising_vectors": [],
        }

    dimension_extractors = {
        "strategy_set": lambda c: str(sorted(c.get("enabled_strategies", []))),
        "l2_thresholds": lambda c: f"{c.get('l2_min_imbalance', 0):.3f}|{c.get('l2_min_signed_aggression', 0):.3f}",
        "regime_filter": lambda c: str(sorted(c.get("regime_filter", []))),
        "evidence_params": lambda c: f"{c.get('base_threshold', 50)}|{c.get('min_confirming_sources', 2)}",
        "v1_adaptive": lambda c: f"{c.get('strategy_selection_mode')}|{c.get('flow_bias_enabled')}",
    }

    dim_importance = {}
    for dim_name, extractor in dimension_extractors.items():
        groups: Dict[str, List[float]] = {}
        for trial in valid_trials:
            candidate = trial.get("candidate", {})
            group_key = extractor(candidate)
            groups.setdefault(group_key, []).append(float(trial["score"]))

        if len(groups) < 2:
            dim_importance[dim_name] = 0.0
            continue

        group_means = [sum(vals) / len(vals) for vals in groups.values()]
        between_var = sum((gm - overall_mean) ** 2 for gm in group_means) / len(
            group_means
        )
        dim_importance[dim_name] = round(min(1.0, between_var / total_variance), 4)

    total_imp = sum(dim_importance.values())
    if total_imp > 0:
        dim_importance = {k: round(v / total_imp, 4) for k, v in dim_importance.items()}

    dim_names = list(dimension_extractors.keys())
    interactions = []
    for i in range(len(dim_names)):
        for j in range(i + 1, len(dim_names)):
            d1, d2 = dim_names[i], dim_names[j]
            ext1, ext2 = dimension_extractors[d1], dimension_extractors[d2]
            groups: Dict[str, List[float]] = {}
            for trial in valid_trials:
                candidate = trial.get("candidate", {})
                combo_key = f"{ext1(candidate)}||{ext2(candidate)}"
                groups.setdefault(combo_key, []).append(float(trial["score"]))
            if len(groups) < 2:
                continue
            group_means = [sum(v) / len(v) for v in groups.values()]
            between_var = sum((gm - overall_mean) ** 2 for gm in group_means) / len(
                group_means
            )
            effect = (
                round(min(1.0, between_var / total_variance), 4)
                if total_variance > 0
                else 0.0
            )
            interactions.append({"dims": [d1, d2], "effect_size": effect})
    interactions.sort(key=lambda x: x["effect_size"], reverse=True)

    score_std = (total_variance**0.5) if total_variance > 0 else 1.0
    threshold = overall_mean + score_std
    surprising = []
    for trial in valid_trials:
        trial_score = float(trial["score"])
        if trial_score < threshold:
            continue
        candidate = trial.get("candidate", {})
        strategies = candidate.get("enabled_strategies", [])
        regime = candidate.get("regime_filter", [])

        desc_parts = []
        if strategies:
            desc_parts.append("+".join(strategies))
        if regime:
            desc_parts.append(f"regime={','.join(regime)}")
        l2_imb = candidate.get("l2_min_imbalance")
        if l2_imb is not None:
            desc_parts.append(f"l2_imb={l2_imb:.2f}")
        base_t = candidate.get("base_threshold")
        if base_t is not None:
            desc_parts.append(f"ev_thresh={base_t:.0f}")

        surprising.append(
            {
                "description": " | ".join(desc_parts) if desc_parts else "unknown",
                "score": trial_score,
                "z_score": round((trial_score - overall_mean) / score_std, 2),
                "trial_index": trial.get("trial_index"),
                "candidate": candidate,
            }
        )
    surprising.sort(key=lambda x: x["score"], reverse=True)

    for vec in surprising:
        strategies = vec.get("candidate", {}).get("enabled_strategies", [])
        families = set()
        for s in strategies:
            fam = STRATEGY_FAMILY_MAP.get(s) or STRATEGY_FAMILY_MAP.get(s.lower())
            if fam:
                families.add(fam)
        n_families = len(families)
        n_strategies = max(len(strategies), 1)

        if n_strategies <= 1:
            diversity = 0.5
        else:
            diversity = round(min(1.0, n_families / max(n_strategies, 1) * 1.5), 3)

        if n_families == 1 and n_strategies > 1:
            vec["score"] = round(vec["score"] * 0.85, 4)
            vec["correlation_note"] = "Same-family penalty applied (×0.85)"
        elif n_families >= 3:
            vec["score"] = round(vec["score"] * 1.10, 4)
            vec["correlation_note"] = "Multi-family bonus applied (×1.10)"

        vec["diversity_score"] = diversity
        vec["n_families"] = n_families
        vec["strategy_families"] = sorted(families)

    surprising.sort(key=lambda x: x["score"], reverse=True)

    return {
        "dimension_importance": dim_importance,
        "top_interactions": interactions[:5],
        "surprising_vectors": surprising[:10],
        "stats": {
            "total_valid_trials": len(valid_trials),
            "overall_mean_score": round(overall_mean, 4),
            "score_std": round(score_std, 4),
        },
    }
