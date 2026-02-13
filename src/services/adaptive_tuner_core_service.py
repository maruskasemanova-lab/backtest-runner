from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException


def normalize_strategy_selection_mode(mode: Any) -> str:
    normalized = str(mode or "adaptive_top_n").strip().lower()
    return "all_enabled" if normalized == "all_enabled" else "adaptive_top_n"


def normalize_non_negative_int(
    value: Any,
    default: int = 0,
    max_value: int = 10_000,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(0, min(max_value, parsed))


def normalize_clamped_int(
    value: Any,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(min_value, min(max_value, parsed))


def normalize_bool_options(values: Optional[List[bool]], default: List[bool]) -> List[bool]:
    if not isinstance(values, list) or not values:
        return list(default)
    normalized = []
    seen = set()
    for value in values:
        current = bool(value)
        if current in seen:
            continue
        seen.add(current)
        normalized.append(current)
    return normalized or list(default)


def normalize_int_options(
    values: Optional[List[int]],
    default: List[int],
    *,
    min_value: int,
    max_value: int,
) -> List[int]:
    if not isinstance(values, list) or not values:
        return list(default)
    normalized = []
    seen = set()
    for value in values:
        current = normalize_clamped_int(value, default[0], min_value, max_value)
        if current in seen:
            continue
        seen.add(current)
        normalized.append(current)
    return normalized or list(default)


def normalize_mode_options(values: Optional[List[str]]) -> List[str]:
    defaults = ["adaptive_top_n", "all_enabled"]
    if not isinstance(values, list) or not values:
        return defaults
    normalized = []
    seen = set()
    for value in values:
        mode = normalize_strategy_selection_mode(value)
        if mode in seen:
            continue
        seen.add(mode)
        normalized.append(mode)
    return normalized or defaults


def normalize_float_options(
    values: Optional[List[float]],
    default: List[float],
    *,
    min_value: float = 0.0,
    max_value: float = 1_000_000.0,
) -> List[float]:
    if not isinstance(values, list) or not values:
        return list(default)
    normalized = []
    seen = set()
    for value in values:
        try:
            current = float(value)
        except (TypeError, ValueError):
            current = default[0] if default else 0.0
        current = max(min_value, min(max_value, current))
        rounded = round(current, 6)
        if rounded in seen:
            continue
        seen.add(rounded)
        normalized.append(rounded)
    return normalized or list(default)


def normalize_strategy_sets(
    raw_sets: Optional[List[List[str]]],
    enabled_strategies: List[str],
) -> List[List[str]]:
    """Normalize strategy sets for v2 search. Returns list of sorted strategy lists."""
    if not isinstance(raw_sets, list) or not raw_sets:
        defaults = [[s] for s in enabled_strategies]
        if len(enabled_strategies) > 1:
            defaults.append(sorted(enabled_strategies))
        return defaults or [["momentum_flow"]]
    normalized = []
    seen = set()
    for strategy_set in raw_sets:
        if not isinstance(strategy_set, list) or not strategy_set:
            continue
        cleaned = sorted(set(str(s).strip().lower() for s in strategy_set if str(s).strip()))
        if not cleaned:
            continue
        key = tuple(cleaned)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized or [[s] for s in enabled_strategies] or [["momentum_flow"]]


def normalize_regime_filter_sets(
    raw_sets: Optional[List[List[str]]],
) -> List[List[str]]:
    """Normalize regime filter sets for v2 search."""
    valid_regimes = {"TRENDING", "CHOPPY", "MIXED"}
    defaults = [
        ["TRENDING"],
        ["TRENDING", "MIXED"],
        ["TRENDING", "MIXED", "CHOPPY"],
    ]
    if not isinstance(raw_sets, list) or not raw_sets:
        return defaults
    normalized = []
    seen = set()
    for regime_set in raw_sets:
        if not isinstance(regime_set, list) or not regime_set:
            continue
        cleaned = sorted(
            set(
                str(r).strip().upper()
                for r in regime_set
                if str(r).strip().upper() in valid_regimes
            )
        )
        if not cleaned:
            continue
        key = tuple(cleaned)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized or defaults


def normalize_time_window_sets(
    raw_sets: Optional[List[List[int]]],
) -> List[List[int]]:
    """Normalize time window sets for v2 search.

    Each set is a list of allowed trading hours (0-23).
    Default windows: morning-only, extended morning, full day.
    """
    defaults = [
        [9, 10],
        [9, 10, 11, 12],
        [9, 10, 11, 12, 13, 14, 15],
    ]
    if not isinstance(raw_sets, list) or not raw_sets:
        return defaults
    normalized = []
    seen = set()
    for tw in raw_sets:
        if not isinstance(tw, list) or not tw:
            continue
        cleaned = sorted(
            set(h for h in (int(x) for x in tw if isinstance(x, (int, float))) if 0 <= h <= 23)
        )
        if not cleaned:
            continue
        key = tuple(cleaned)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized or defaults


def normalize_regime_strategy_map_sets(
    raw_sets: Optional[List[Optional[Dict[str, List[str]]]]],
    enabled_strategies: List[str],
    build_regime_strategy_map_options: Callable[[List[str]], List[Optional[Dict[str, List[str]]]]],
) -> List[Optional[Dict[str, List[str]]]]:
    """Normalize v2 regime->strategy map sets.

    Always includes ``None`` as the first option (flat mode).
    """
    defaults = build_regime_strategy_map_options(enabled_strategies)
    if not isinstance(raw_sets, list) or not raw_sets:
        return defaults

    allowed = {str(name).strip().lower() for name in enabled_strategies if str(name).strip()}
    normalized: List[Optional[Dict[str, List[str]]]] = []
    seen_maps = set()
    has_flat_mode = False

    for raw_map in raw_sets:
        if raw_map is None:
            has_flat_mode = True
            continue
        if not isinstance(raw_map, dict):
            continue

        cleaned_map: Dict[str, List[str]] = {}
        for regime in ("TRENDING", "MIXED", "CHOPPY"):
            raw_values = raw_map.get(regime, [])
            cleaned_values: List[str] = []
            seen_values = set()
            if isinstance(raw_values, list):
                for value in raw_values:
                    strategy_key = str(value).strip().lower()
                    if not strategy_key or strategy_key in seen_values:
                        continue
                    if allowed and strategy_key not in allowed:
                        continue
                    seen_values.add(strategy_key)
                    cleaned_values.append(strategy_key)
            cleaned_map[regime] = cleaned_values

        if not any(cleaned_map.values()):
            continue

        map_key = json.dumps(cleaned_map, sort_keys=True)
        if map_key in seen_maps:
            continue
        seen_maps.add(map_key)
        normalized.append(cleaned_map)

    if not normalized and not has_flat_mode:
        return defaults
    return [None] + normalized


def iter_date_strings(date_from: str, date_to: str) -> List[str]:
    try:
        start_dt = datetime.strptime(date_from, "%Y-%m-%d")
        end_dt = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(400, f"Invalid date format: {exc}")
    if end_dt < start_dt:
        raise HTTPException(400, "date_to must be on or after date_from")
    dates: List[str] = []
    current = start_dt
    while current <= end_dt:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


def as_iso_day_set(days: List[str]) -> set:
    out = set()
    for day in days:
        value = str(day or "").strip()
        if not value:
            continue
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            continue
        out.add(value)
    return out


def resolve_l2_tuning_dates(
    *,
    ticker: str,
    date_from: str,
    date_to: str,
    l2_required: bool,
    databento_svc: Any,
) -> List[str]:
    requested_days = iter_date_strings(date_from, date_to)
    if not l2_required:
        return requested_days

    ohlcv_cov = databento_svc.get_range_coverage(
        ticker=ticker,
        schema="ohlcv-1m",
        start_date=date_from,
        end_date=date_to,
    )
    l2_cov = databento_svc.get_range_coverage(
        ticker=ticker,
        schema="mbp-10",
        start_date=date_from,
        end_date=date_to,
    )
    ohlcv_days = as_iso_day_set(ohlcv_cov.get("covered_days", []))
    l2_days = as_iso_day_set(l2_cov.get("covered_days", []))
    return sorted(ohlcv_days.intersection(l2_days))


def sample_evenly_spaced_days(days: List[str], *, max_days: int) -> List[str]:
    """Pick a representative subset of ISO days while preserving chronology."""
    ordered_days = sorted(as_iso_day_set(days))
    if not ordered_days:
        return []
    max_days = normalize_clamped_int(max_days, default=2, min_value=1, max_value=30)
    if len(ordered_days) <= max_days:
        return ordered_days
    if max_days == 1:
        return [ordered_days[len(ordered_days) // 2]]

    picks = []
    for idx in range(max_days):
        raw_index = round(idx * (len(ordered_days) - 1) / (max_days - 1))
        picks.append(ordered_days[int(raw_index)])
    return sorted(set(picks))


def resolve_tuner_trial_budget(
    *,
    requested_trials: Any,
    default_trials: int,
    quick_mode: bool,
    quick_trial_boost: Any,
    max_trials: int = 400,
) -> Dict[str, int]:
    requested = normalize_clamped_int(
        requested_trials, default=default_trials, min_value=1, max_value=max_trials
    )
    boost = 1
    if quick_mode:
        boost = normalize_clamped_int(quick_trial_boost, default=3, min_value=1, max_value=10)
    effective = min(max_trials, requested * boost)
    return {"requested": requested, "boost": boost, "effective": effective}


def covered_days_for_schema(ticker: str, schema: str, databento_svc: Any) -> List[str]:
    ticker_upper = str(ticker or "").upper().strip()
    schema_lower = str(schema or "").lower().strip()
    if not ticker_upper or not schema_lower:
        return []

    entries = databento_svc.list_catalog(refresh=False, ticker=ticker_upper)
    days = set()
    for entry in entries:
        if str(entry.get("status", "")).lower() != "ready":
            continue
        if str(entry.get("schema", "")).lower() != schema_lower:
            continue

        preferred_file = databento_svc._preferred_entry_file(entry)
        preferred_path = databento_svc._resolve_entry_path(preferred_file)
        if not preferred_path or not preferred_path.exists():
            continue

        start_date = str(entry.get("start_date", "")).strip()
        end_date = str(entry.get("end_date", "")).strip()
        if schema_lower.startswith("ohlcv-"):
            start_date, end_date = databento_svc._effective_entry_range(entry)

        try:
            for day in databento_svc._iter_days(start_date, end_date):
                days.add(day)
        except Exception:
            continue

    return sorted(days)


def range_summary_from_days(days: List[str]) -> Dict[str, Any]:
    day_list = sorted(as_iso_day_set(days))
    if not day_list:
        return {"start": None, "end": None, "total_days": 0}
    return {
        "start": day_list[0],
        "end": day_list[-1],
        "total_days": len(day_list),
    }


def normalize_tuner_profiles(raw_profiles: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_profiles, list):
        return []
    profiles = []
    for item in raw_profiles:
        if not isinstance(item, dict):
            continue
        profile_id = str(item.get("profile_id", "")).strip()
        candidate = item.get("candidate")
        if not profile_id or not isinstance(candidate, dict):
            continue
        profiles.append(dict(item))
    profiles.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
    return profiles


def sanitize_strategy_params(params: Any) -> Dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    sanitized: Dict[str, Any] = {}
    for raw_key, value in params.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        if key == "allowed_regimes":
            if not isinstance(value, list):
                continue
            seen = set()
            regimes: List[str] = []
            for item in value:
                regime = str(item or "").strip().upper()
                if regime not in {"TRENDING", "CHOPPY", "MIXED"}:
                    continue
                if regime in seen:
                    continue
                seen.add(regime)
                regimes.append(regime)
            if regimes:
                sanitized[key] = regimes
            continue
        if isinstance(value, (bool, int, float, str)) or value is None:
            sanitized[key] = value
    return sanitized


def extract_strategy_params_for_profile(
    strategies_payload: Any,
) -> Dict[str, Dict[str, Any]]:
    if not isinstance(strategies_payload, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    skip_fields = {
        "display_name",
        "name",
        "open_positions",
        "total_signals",
        "last_signal",
        "regimes",
    }
    for raw_name, cfg in strategies_payload.items():
        strat_name = str(raw_name or "").strip()
        if not strat_name or not isinstance(cfg, dict):
            continue
        draft = {key: value for key, value in cfg.items() if key not in skip_fields}
        if "allowed_regimes" not in draft and isinstance(cfg.get("regimes"), list):
            draft["allowed_regimes"] = cfg.get("regimes")
        sanitized = sanitize_strategy_params(draft)
        if sanitized:
            out[strat_name] = sanitized
    return out


def normalize_strategy_combo_profiles(raw_profiles: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_profiles, list):
        return []
    profiles: List[Dict[str, Any]] = []
    for row in raw_profiles:
        if not isinstance(row, dict):
            continue
        profile_id = str(row.get("profile_id", "")).strip()
        profile_name = str(row.get("profile_name", "")).strip()
        strategy_params = row.get("strategy_params")
        if not profile_id or not isinstance(strategy_params, dict):
            continue
        normalized_strategy_params: Dict[str, Dict[str, Any]] = {}
        for raw_name, params in strategy_params.items():
            strat_name = str(raw_name or "").strip()
            if not strat_name:
                continue
            clean = sanitize_strategy_params(params)
            if clean:
                normalized_strategy_params[strat_name] = clean
        if not normalized_strategy_params:
            continue
        profiles.append(
            {
                "profile_id": profile_id,
                "profile_name": profile_name or profile_id,
                "created_at": str(row.get("created_at", "")),
                "updated_at": str(row.get("updated_at", "")),
                "strategy_params": normalized_strategy_params,
            }
        )
    profiles.sort(
        key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
        reverse=True,
    )
    return profiles
