from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

from fastapi import HTTPException

from src.services.config_domain import (
    TickerConfigRepositoryDeps,
    load_ticker_config_aggregate,
)


def extract_tuner_candidate(profile: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    candidate = profile.get("candidate")
    if isinstance(candidate, dict):
        return candidate
    best_trial = profile.get("best_trial")
    if isinstance(best_trial, dict) and isinstance(best_trial.get("candidate"), dict):
        return best_trial.get("candidate", {})
    return {}


def profile_updated_ts(
    profile: Dict[str, Any],
    *,
    parse_utc_iso: Callable[[Any], Optional[datetime]],
) -> float:
    if not isinstance(profile, dict):
        return 0.0
    raw = str(profile.get("updated_at") or profile.get("created_at") or "").strip()
    parsed = parse_utc_iso(raw)
    if parsed is None:
        return 0.0
    return float(parsed.timestamp())


def normalize_profile_ref_token(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    if token.lower() in {"none", "null", "n/a", "na"}:
        return ""
    return token


def derived_unified_profile_id(
    ticker_upper: str,
    combo_profile_id: str,
    adaptive_profile_id: str,
) -> str:
    combo_token = str(combo_profile_id or "").strip() or "none"
    adaptive_token = str(adaptive_profile_id or "").strip() or "none"
    return f"legacy-unified-{ticker_upper}-{combo_token}-{adaptive_token}"


def build_legacy_unified_profile_variants(
    ticker_upper: str,
    ticker_cfg: Dict[str, Any],
    *,
    normalize_strategy_combo_profiles: Callable[[Any], List[Dict[str, Any]]],
    normalize_tuner_profiles: Callable[[Any], List[Dict[str, Any]]],
    normalize_strategy_selection_mode: Callable[[Any], str],
    normalize_clamped_int: Callable[..., int],
    get_ticker_positioning_config: Callable[[str], Dict[str, Any]],
    parse_utc_iso: Callable[[Any], Optional[datetime]],
    max_profiles: int = 60,
) -> List[Dict[str, Any]]:
    combo_profiles = normalize_strategy_combo_profiles(
        ticker_cfg.get("strategy_combo_profiles", [])
    )
    adaptive_profiles = normalize_tuner_profiles(
        ticker_cfg.get("adaptive_tuner_profiles", [])
    )
    if not combo_profiles and not adaptive_profiles:
        return []

    active_combo_id = normalize_profile_ref_token(
        ticker_cfg.get("active_strategy_combo_profile_id", "")
    )
    active_adaptive_id = normalize_profile_ref_token(
        ticker_cfg.get("active_adaptive_tuner_profile_id", "")
    )

    def _ordered_rows(
        rows: List[Dict[str, Any]],
        active_id: str,
    ) -> List[Dict[str, Any]]:
        if not rows:
            return []
        active: List[Dict[str, Any]] = []
        rest: List[Dict[str, Any]] = []
        for row in rows:
            row_id = str(row.get("profile_id") or "").strip()
            if active_id and row_id == active_id:
                active.append(row)
            else:
                rest.append(row)
        rest.sort(
            key=lambda item: profile_updated_ts(item, parse_utc_iso=parse_utc_iso),
            reverse=True,
        )
        return active + rest

    combo_candidates = _ordered_rows(combo_profiles, active_combo_id)
    adaptive_candidates = _ordered_rows(adaptive_profiles, active_adaptive_id)
    combo_candidates = combo_candidates[:12] if combo_candidates else [None]
    adaptive_candidates = adaptive_candidates[:12] if adaptive_candidates else [None]

    now_iso = datetime.utcnow().isoformat() + "Z"
    positioning = get_ticker_positioning_config(ticker_upper)
    base_execution_profile = {
        "positioning": positioning if isinstance(positioning, dict) else {},
    }

    rows: List[Dict[str, Any]] = []
    for combo_profile in combo_candidates:
        for adaptive_profile in adaptive_candidates:
            combo_row = combo_profile if isinstance(combo_profile, dict) else {}
            adaptive_row = (
                adaptive_profile if isinstance(adaptive_profile, dict) else {}
            )
            combo_id = str(combo_row.get("profile_id") or "").strip()
            adaptive_id = str(adaptive_row.get("profile_id") or "").strip()
            if not combo_id and not adaptive_id:
                continue

            combo_name = str(combo_row.get("profile_name") or combo_id or "").strip()
            adaptive_name = str(
                adaptive_row.get("profile_name") or adaptive_id or ""
            ).strip()
            if combo_name and adaptive_name:
                profile_name = f"legacy: {combo_name} + {adaptive_name}"
            else:
                profile_name = f"legacy: {combo_name or adaptive_name or ticker_upper}"

            strategy_profile: Dict[str, Any] = {
                "strategy_params": (
                    combo_row.get("strategy_params")
                    if isinstance(combo_row.get("strategy_params"), dict)
                    else {}
                ),
                "strategy_selection_mode": normalize_strategy_selection_mode(
                    ticker_cfg.get("strategy_selection_mode")
                ),
                "max_active_strategies": normalize_clamped_int(
                    ticker_cfg.get("max_active_strategies"),
                    default=3,
                    min_value=1,
                    max_value=20,
                ),
                "trading_hours": (
                    ticker_cfg.get("trading_hours")
                    if isinstance(ticker_cfg.get("trading_hours"), list)
                    else []
                ),
                "time_filter_enabled": bool(
                    ticker_cfg.get("time_filter_enabled", False)
                ),
                "long_only": bool(ticker_cfg.get("long_only", False)),
            }
            if isinstance(ticker_cfg.get("l2"), dict):
                strategy_profile["l2"] = dict(ticker_cfg.get("l2", {}))
            if isinstance(ticker_cfg.get("adaptive"), dict):
                strategy_profile["adaptive"] = dict(ticker_cfg.get("adaptive", {}))
            if combo_id:
                strategy_profile["active_strategy_combo_profile_id"] = combo_id
            if adaptive_id:
                strategy_profile["active_adaptive_tuner_profile_id"] = adaptive_id
            adaptive_candidate = extract_tuner_candidate(adaptive_row)
            if adaptive_candidate:
                strategy_profile["adaptive_candidate"] = adaptive_candidate

            created_at = (
                str(combo_row.get("created_at") or "").strip()
                or str(adaptive_row.get("created_at") or "").strip()
                or now_iso
            )
            updated_at = (
                str(
                    combo_row.get("updated_at") or combo_row.get("created_at") or ""
                ).strip()
                or str(
                    adaptive_row.get("updated_at")
                    or adaptive_row.get("created_at")
                    or ""
                ).strip()
                or now_iso
            )

            row: Dict[str, Any] = {
                "profile_id": derived_unified_profile_id(
                    ticker_upper, combo_id, adaptive_id
                ),
                "profile_name": profile_name,
                "created_at": created_at,
                "updated_at": updated_at,
                "strategy_profile": strategy_profile,
                "execution_profile": base_execution_profile,
            }
            if combo_id:
                row["source_strategy_combo_profile_id"] = combo_id
            if adaptive_id:
                row["source_adaptive_tuner_profile_id"] = adaptive_id
            rows.append(row)

    rows.sort(
        key=lambda item: profile_updated_ts(item, parse_utc_iso=parse_utc_iso),
        reverse=True,
    )

    preferred_derived_active_id = derived_unified_profile_id(
        ticker_upper,
        active_combo_id,
        active_adaptive_id,
    )
    if preferred_derived_active_id:
        rows.sort(
            key=lambda item: (
                0
                if str(item.get("profile_id") or "").strip()
                == preferred_derived_active_id
                else 1
            )
        )
    return rows[: max(1, int(max_profiles))]


def build_strategy_combo_options_payload(
    ticker: str,
    *,
    load_aos_config: Callable[[], Dict[str, Any]],
    normalize_strategy_combo_profiles: Callable[[Any], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    ticker_upper = str(ticker or "").upper().strip()
    if not ticker_upper:
        raise HTTPException(400, "ticker is required")
    aggregate = load_ticker_config_aggregate(
        ticker=ticker_upper,
        deps=TickerConfigRepositoryDeps(
            load_aos_config=load_aos_config,
            get_ticker_positioning_config=lambda *_args, **_kwargs: {},
            normalize_strategy_combo_profiles=normalize_strategy_combo_profiles,
            normalize_unified_profiles=lambda value: [],
            normalize_tuner_profiles=lambda value: [],
            positioning_config_keys=(),
        ),
    )
    return {
        "ticker": ticker_upper,
        "profiles": aggregate.strategy_combo_profiles,
        "active_profile_id": aggregate.active_strategy_combo_profile_id,
    }


def build_adaptive_tuner_options_payload(
    ticker: str,
    *,
    load_aos_config: Callable[[], Dict[str, Any]],
    normalize_tuner_profiles: Callable[[Any], List[Dict[str, Any]]],
    covered_days_for_schema: Callable[[str, str], List[str]],
    range_summary_from_days: Callable[[List[str]], Dict[str, Any]],
) -> Dict[str, Any]:
    ticker_upper = str(ticker or "").upper().strip()
    if not ticker_upper:
        raise HTTPException(400, "ticker is required")

    ohlcv_days = covered_days_for_schema(ticker_upper, "ohlcv-1m")
    l2_days = covered_days_for_schema(ticker_upper, "mbp-10")
    overlap_days = sorted(set(ohlcv_days).intersection(set(l2_days)))

    ohlcv_range = range_summary_from_days(ohlcv_days)
    l2_range = range_summary_from_days(l2_days)
    overlap_range = range_summary_from_days(overlap_days)

    aggregate = load_ticker_config_aggregate(
        ticker=ticker_upper,
        deps=TickerConfigRepositoryDeps(
            load_aos_config=load_aos_config,
            get_ticker_positioning_config=lambda *_args, **_kwargs: {},
            normalize_strategy_combo_profiles=lambda value: [],
            normalize_unified_profiles=lambda value: [],
            normalize_tuner_profiles=normalize_tuner_profiles,
            positioning_config_keys=(),
        ),
    )

    default_from = overlap_range.get("start") or ohlcv_range.get("start")
    default_to = overlap_range.get("end") or ohlcv_range.get("end")

    return {
        "ticker": ticker_upper,
        "ohlcv_range": ohlcv_range,
        "l2_range": l2_range,
        "l2_overlap_range": overlap_range,
        "l2_overlap_days": overlap_days,
        "default_date_from": default_from,
        "default_date_to": default_to,
        "has_l2_overlap": bool(overlap_days),
        "profiles": aggregate.adaptive_tuner_profiles,
        "active_profile_id": aggregate.active_adaptive_tuner_profile_id,
    }


def build_unified_profile_options_payload(
    ticker: str,
    *,
    load_aos_config: Callable[[], Dict[str, Any]],
    normalize_unified_profiles: Callable[[Any], List[Dict[str, Any]]],
    normalize_strategy_combo_profiles: Callable[[Any], List[Dict[str, Any]]],
    normalize_tuner_profiles: Callable[[Any], List[Dict[str, Any]]],
    normalize_strategy_selection_mode: Callable[[Any], str],
    normalize_clamped_int: Callable[..., int],
    get_ticker_positioning_config: Callable[[str], Dict[str, Any]],
    positioning_config_keys: Iterable[str] = (),
    parse_utc_iso: Callable[[Any], Optional[datetime]],
    max_profiles: int = 60,
) -> Dict[str, Any]:
    ticker_upper = str(ticker or "").upper().strip()
    if not ticker_upper:
        raise HTTPException(400, "ticker is required")

    aggregate = load_ticker_config_aggregate(
        ticker=ticker_upper,
        deps=TickerConfigRepositoryDeps(
            load_aos_config=load_aos_config,
            get_ticker_positioning_config=get_ticker_positioning_config,
            normalize_strategy_combo_profiles=normalize_strategy_combo_profiles,
            normalize_unified_profiles=normalize_unified_profiles,
            normalize_tuner_profiles=normalize_tuner_profiles,
            positioning_config_keys=positioning_config_keys,
        ),
    )
    ticker_cfg = aggregate.ticker_config

    stored_profiles = aggregate.unified_profiles
    derived_profiles = build_legacy_unified_profile_variants(
        ticker_upper,
        ticker_cfg,
        normalize_strategy_combo_profiles=normalize_strategy_combo_profiles,
        normalize_tuner_profiles=normalize_tuner_profiles,
        normalize_strategy_selection_mode=normalize_strategy_selection_mode,
        normalize_clamped_int=normalize_clamped_int,
        get_ticker_positioning_config=lambda _ticker: dict(aggregate.positioning),
        parse_utc_iso=parse_utc_iso,
        max_profiles=max_profiles,
    )

    merged_profiles: List[Dict[str, Any]] = []
    seen_profile_ids: set[str] = set()
    for profile in stored_profiles + derived_profiles:
        profile_id = str(profile.get("profile_id") or "").strip()
        if not profile_id or profile_id in seen_profile_ids:
            continue
        seen_profile_ids.add(profile_id)
        merged_profiles.append(profile)

    active_profile_id = aggregate.active_unified_profile_id
    if not active_profile_id:
        active_combo_id = aggregate.active_strategy_combo_profile_id or ""
        active_adaptive_id = aggregate.active_adaptive_tuner_profile_id or ""
        derived_active = derived_unified_profile_id(
            ticker_upper,
            active_combo_id,
            active_adaptive_id,
        )
        if derived_active in seen_profile_ids:
            active_profile_id = derived_active
    if active_profile_id and active_profile_id not in seen_profile_ids:
        active_profile_id = None

    merged_profiles.sort(
        key=lambda item: profile_updated_ts(item, parse_utc_iso=parse_utc_iso),
        reverse=True,
    )
    if active_profile_id:
        merged_profiles.sort(
            key=lambda item: (
                0
                if str(item.get("profile_id") or "").strip() == active_profile_id
                else 1
            )
        )
    return {
        "ticker": ticker_upper,
        "profiles": merged_profiles[: max(1, int(max_profiles))],
        "active_profile_id": active_profile_id,
    }
