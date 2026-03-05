from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

from .repository import TickerConfigAggregate, normalize_profile_ref_token
from .resolver import resolve_local_aos_applied_snapshot

_INTRADAY_PROFILE_RUNTIME_PREFIXES = ("intraday_levels_",)
_INTRADAY_PROFILE_RUNTIME_KEYS = {
    "liquidity_sweep_detection_enabled",
    "sweep_min_aggression_z",
    "sweep_min_book_pressure_z",
    "sweep_max_price_change_pct",
}


class EffectiveConfigResolverDeps(Protocol):
    normalize_strategy_combo_profiles: Any
    normalize_unified_profiles: Any
    normalize_tuner_profiles: Any
    normalize_strategy_selection_mode: Any
    normalize_clamped_int: Any
    normalize_momentum_diversification_payload: Any


@dataclass(frozen=True)
class EffectiveAosState:
    aggregate: TickerConfigAggregate
    ticker_config: Dict[str, Any]
    applied: Dict[str, Any]
    unified_profile: Dict[str, Any]
    active_adaptive_candidate: Dict[str, Any]
    active_adaptive_runtime: Dict[str, Any]


def _parse_positive_int_override(value: Any, *, min_value: int) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return max(min_value, parsed)


def build_effective_ticker_config(aggregate: TickerConfigAggregate) -> Dict[str, Any]:
    ticker_config = dict(aggregate.ticker_config)
    if aggregate.strategy_combo_profiles:
        ticker_config["strategy_combo_profiles"] = aggregate.strategy_combo_profiles
    if aggregate.adaptive_tuner_profiles:
        ticker_config["adaptive_tuner_profiles"] = aggregate.adaptive_tuner_profiles
    if aggregate.unified_profiles:
        ticker_config["unified_profiles"] = aggregate.unified_profiles
    if aggregate.active_strategy_combo_profile_id is not None:
        ticker_config["active_strategy_combo_profile_id"] = (
            aggregate.active_strategy_combo_profile_id
        )
    if aggregate.active_adaptive_tuner_profile_id is not None:
        ticker_config["active_adaptive_tuner_profile_id"] = (
            aggregate.active_adaptive_tuner_profile_id
        )
    if aggregate.active_unified_profile_id is not None:
        ticker_config["active_unified_profile_id"] = aggregate.active_unified_profile_id
    return ticker_config


def resolve_active_adaptive_tuner_candidate(
    ticker_config: Dict[str, Any],
    deps: EffectiveConfigResolverDeps,
) -> Dict[str, Any]:
    active_profile_id = normalize_profile_ref_token(
        ticker_config.get("active_adaptive_tuner_profile_id")
    )
    if not active_profile_id:
        return {}
    profiles = deps.normalize_tuner_profiles(
        ticker_config.get("adaptive_tuner_profiles", [])
    )
    target_profile = next(
        (
            profile
            for profile in profiles
            if normalize_profile_ref_token(profile.get("profile_id")) == active_profile_id
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
    deps: EffectiveConfigResolverDeps,
) -> Dict[str, Any]:
    active_profile_id = normalize_profile_ref_token(
        ticker_config.get("active_unified_profile_id")
    )
    if not active_profile_id:
        return {}
    profiles = deps.normalize_unified_profiles(
        ticker_config.get("unified_profiles", [])
    )
    target_profile = next(
        (
            profile
            for profile in profiles
            if normalize_profile_ref_token(profile.get("profile_id")) == active_profile_id
        ),
        None,
    )
    if isinstance(target_profile, dict):
        return target_profile
    return {}


def extract_profile_runtime_overrides(
    candidate: Dict[str, Any],
    deps: EffectiveConfigResolverDeps,
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
    for key, min_value in (
        ("regime_detection_minutes", 1),
        ("regime_refresh_bars", 3),
    ):
        value = _parse_positive_int_override(candidate.get(key), min_value=min_value)
        if value is not None:
            runtime[key] = value
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
    for key, value in candidate.items():
        if value is None:
            continue
        if key in _INTRADAY_PROFILE_RUNTIME_KEYS or key.startswith(
            _INTRADAY_PROFILE_RUNTIME_PREFIXES
        ):
            runtime[key] = value
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

    context_exit = candidate.get("adaptive", {}).get("context_exit_response")
    if isinstance(context_exit, dict) and context_exit:
        runtime["context_exit_response"] = context_exit
    else:
        flat_context_keys = {
            "context_flow_reversal_move_to_breakeven": "flow_reversal_move_to_breakeven",
            "context_flow_reversal_exit_when_losing": "flow_reversal_exit_when_losing",
            "context_regime_flip_tighten_stop_pct": "regime_flip_tighten_stop_pct",
            "context_regime_flip_shorten_time_pct": "regime_flip_shorten_time_pct",
            "context_regime_flip_exit_when_losing": "regime_flip_exit_when_losing",
            "context_regime_flip_exit_loss_threshold_pct": "regime_flip_exit_loss_threshold_pct",
            "context_momentum_stall_time_multiplier": "momentum_stall_time_multiplier",
        }
        flat_context: Dict[str, Any] = {}
        for flat_key, nested_key in flat_context_keys.items():
            if flat_key in candidate:
                flat_context[nested_key] = candidate[flat_key]
        if flat_context:
            runtime["context_exit_response"] = flat_context

    return runtime


def extract_unified_runtime_overrides(
    strategy_profile: Dict[str, Any],
    deps: EffectiveConfigResolverDeps,
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
    if "trading_hours" in strategy_profile and isinstance(
        strategy_profile.get("trading_hours"), list
    ):
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
            runtime["time_filter_enabled"] = bool(
                strategy_profile.get("time_filter_enabled", True)
            )

    if "long_only" in strategy_profile:
        runtime["long_only"] = bool(strategy_profile.get("long_only"))

    for key, min_value in (
        ("regime_detection_minutes", 1),
        ("regime_refresh_bars", 3),
    ):
        raw_value = (
            strategy_profile.get(key) if key in strategy_profile else runtime.get(key)
        )
        value = _parse_positive_int_override(raw_value, min_value=min_value)
        if value is not None:
            runtime[key] = value
        else:
            runtime.pop(key, None)

    direct_runtime_keys = (
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
        "intraday_levels_entry_tolerance_pct",
        "intraday_levels_memory_enabled",
        "intraday_levels_memory_min_tests",
        "intraday_levels_memory_max_age_days",
        "intraday_levels_memory_decay_after_days",
        "intraday_levels_memory_decay_weight",
        "intraday_levels_memory_max_levels",
        "intraday_levels_poc_migration_enabled",
        "intraday_levels_poc_migration_interval_bars",
        "intraday_levels_poc_migration_trend_threshold_pct",
        "intraday_levels_poc_migration_range_threshold_pct",
        "intraday_levels_micro_confirmation_enabled",
        "intraday_levels_micro_confirmation_bars",
        "intraday_levels_micro_confirmation_disable_for_sweep",
        "intraday_levels_micro_confirmation_sweep_bars",
        "intraday_levels_micro_confirmation_require_intrabar",
        "intraday_levels_micro_confirmation_intrabar_window_seconds",
        "intraday_levels_micro_confirmation_intrabar_min_coverage_points",
        "intraday_levels_micro_confirmation_intrabar_min_move_pct",
        "intraday_levels_micro_confirmation_intrabar_min_push_ratio",
        "intraday_levels_micro_confirmation_intrabar_max_spread_bps",
    )
    for key, value in strategy_profile.items():
        if value is None:
            continue
        if key in direct_runtime_keys or key in _INTRADAY_PROFILE_RUNTIME_KEYS:
            runtime[key] = value
            continue
        if key.startswith(_INTRADAY_PROFILE_RUNTIME_PREFIXES):
            runtime[key] = value

    momentum_runtime = deps.normalize_momentum_diversification_payload(
        strategy_profile.get("momentum_diversification")
    )
    if momentum_runtime:
        runtime["momentum_diversification"] = momentum_runtime
    return runtime


def _resolve_unified_applied(
    *,
    ticker_config: Dict[str, Any],
    positioning_config: Dict[str, Any],
    unified_profile: Dict[str, Any],
    deps: EffectiveConfigResolverDeps,
) -> Dict[str, Any]:
    applied: Dict[str, Any] = {
        "unified_profile": {
            "active_profile_id": str(unified_profile.get("profile_id") or "").strip()
            or None,
            "profile_name": str(unified_profile.get("profile_name") or "").strip()
            or None,
        }
    }
    strategy_profile = unified_profile.get("strategy_profile")
    if not isinstance(strategy_profile, dict):
        strategy_profile = {}
    execution_profile = unified_profile.get("execution_profile")
    if not isinstance(execution_profile, dict):
        execution_profile = {}

    strategy_params = strategy_profile.get("strategy_params")
    if not isinstance(strategy_params, dict):
        strategy_params = {}

    runtime_overrides = extract_unified_runtime_overrides(strategy_profile, deps)
    applied["adaptive_profile"] = {
        "active_profile_id": applied["unified_profile"]["active_profile_id"],
        "profile_name": applied["unified_profile"]["profile_name"],
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
        raw_hours = strategy_profile.get(
            "trading_hours", ticker_config.get("trading_hours")
        )
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
        applied["long_only"] = bool(
            ticker_config.get("long_only", params.get("long_only", False))
        )
        applied["long_only_source"] = "ticker_config"

    strategy_selection_mode = (
        str(
            runtime_overrides.get(
                "strategy_selection_mode",
                strategy_profile.get(
                    "strategy_selection_mode",
                    ticker_config.get("strategy_selection_mode", "adaptive_top_n"),
                ),
            )
        )
        .strip()
        .lower()
    )
    if strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
        strategy_selection_mode = "adaptive_top_n"
    applied["strategy_selection_mode"] = strategy_selection_mode
    try:
        raw_max_active = int(
            runtime_overrides.get(
                "max_active_strategies",
                strategy_profile.get(
                    "max_active_strategies",
                    ticker_config.get("max_active_strategies", 3),
                ),
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
        applied["l2"] = dict(strategy_profile.get("l2", {}))
    elif isinstance(ticker_config.get("l2"), dict):
        applied["l2"] = dict(ticker_config.get("l2", {}))
    if isinstance(strategy_profile.get("adaptive"), dict):
        applied["adaptive"] = dict(strategy_profile.get("adaptive", {}))
    elif isinstance(ticker_config.get("adaptive"), dict):
        applied["adaptive"] = dict(ticker_config.get("adaptive", {}))

    inline_positioning = execution_profile.get("positioning")
    merged_positioning = dict(positioning_config)
    if isinstance(inline_positioning, dict) and inline_positioning:
        merged_positioning.update(inline_positioning)
    if merged_positioning:
        applied["positioning"] = merged_positioning
    return applied


def _resolve_legacy_applied(
    *,
    aggregate: TickerConfigAggregate,
    ticker_config: Dict[str, Any],
    deps: EffectiveConfigResolverDeps,
    active_candidate: Dict[str, Any] | None = None,
    active_profile_runtime: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    applied = resolve_local_aos_applied_snapshot(aggregate)
    if not isinstance(active_candidate, dict):
        active_candidate = resolve_active_adaptive_tuner_candidate(ticker_config, deps)
    if not isinstance(active_profile_runtime, dict):
        active_profile_runtime = extract_profile_runtime_overrides(active_candidate, deps)
    active_profile_id = str(
        ticker_config.get("active_adaptive_tuner_profile_id") or ""
    ).strip() or None
    if active_profile_id or active_profile_runtime:
        enabled_raw = (
            active_candidate.get("enabled_strategies", [])
            if isinstance(active_candidate, dict)
            else []
        )
        enabled_strategies = [
            str(item).strip() for item in enabled_raw if str(item).strip()
        ]
        applied["adaptive_profile"] = {
            "active_profile_id": active_profile_id,
            "runtime_overrides": active_profile_runtime,
            "enabled_strategies": enabled_strategies,
            "candidate_applied": bool(enabled_strategies),
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
            ticker_config.get(
                "time_filter_enabled", bool(ticker_config.get("trading_hours"))
            )
        )
        applied["trading_hours_source"] = "ticker_config"

    if "long_only" in active_profile_runtime:
        applied["long_only"] = bool(active_profile_runtime.get("long_only"))
        applied["long_only_source"] = "adaptive_profile"
    else:
        params = dict(ticker_config.get("params", {}))
        applied["long_only"] = bool(
            ticker_config.get("long_only", params.get("long_only", False))
        )
        applied["long_only_source"] = "ticker_config"
    return applied


def resolve_effective_aos_applied_snapshot(
    aggregate: TickerConfigAggregate,
    deps: EffectiveConfigResolverDeps,
) -> Dict[str, Any]:
    return resolve_effective_aos_state(aggregate, deps).applied


def resolve_effective_aos_state(
    aggregate: TickerConfigAggregate,
    deps: EffectiveConfigResolverDeps,
) -> EffectiveAosState:
    ticker_config = build_effective_ticker_config(aggregate)
    unified_profile = resolve_active_unified_profile(ticker_config, deps)
    if isinstance(unified_profile, dict) and unified_profile:
        return EffectiveAosState(
            aggregate=aggregate,
            ticker_config=ticker_config,
            applied=_resolve_unified_applied(
                ticker_config=ticker_config,
                positioning_config=dict(aggregate.positioning),
                unified_profile=unified_profile,
                deps=deps,
            ),
            unified_profile=unified_profile,
            active_adaptive_candidate={},
            active_adaptive_runtime={},
        )
    active_candidate = resolve_active_adaptive_tuner_candidate(ticker_config, deps)
    active_profile_runtime = extract_profile_runtime_overrides(active_candidate, deps)
    return EffectiveAosState(
        aggregate=aggregate,
        ticker_config=ticker_config,
        applied=_resolve_legacy_applied(
            aggregate=aggregate,
            ticker_config=ticker_config,
            deps=deps,
            active_candidate=active_candidate,
            active_profile_runtime=active_profile_runtime,
        ),
        unified_profile={},
        active_adaptive_candidate=active_candidate,
        active_adaptive_runtime=active_profile_runtime,
    )
