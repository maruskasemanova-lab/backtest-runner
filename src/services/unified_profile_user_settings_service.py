from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

USER_SETTINGS_UNIFIED_PROFILE_STORE_KEY = "unified_profile_store"
UNIFIED_PROFILE_STORE_TICKERS_KEY = "tickers"
LEGACY_UNIFIED_PROFILE_PREFIX = "legacy-unified-"


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_unified_profile_state_from_settings(
    *,
    settings: Any,
    ticker: str,
    normalize_unified_profiles: Callable[[Any], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    ticker_upper = str(ticker or "").upper().strip()
    root = _as_dict(settings)
    store = _as_dict(root.get(USER_SETTINGS_UNIFIED_PROFILE_STORE_KEY))
    tickers_payload = _as_dict(store.get(UNIFIED_PROFILE_STORE_TICKERS_KEY))
    ticker_payload = _as_dict(tickers_payload.get(ticker_upper))

    profiles = normalize_unified_profiles(ticker_payload.get("profiles", []))
    known_ids = {
        str(row.get("profile_id") or "").strip()
        for row in profiles
        if isinstance(row, dict)
    }
    active_profile_id = str(ticker_payload.get("active_profile_id") or "").strip() or None
    if active_profile_id and active_profile_id not in known_ids:
        active_profile_id = None

    return {
        "ticker": ticker_upper,
        "profiles": profiles,
        "active_profile_id": active_profile_id,
    }


def build_unified_profile_settings_patch(
    *,
    settings: Any,
    ticker: str,
    profiles: List[Dict[str, Any]],
    active_profile_id: Optional[str],
) -> Dict[str, Any]:
    ticker_upper = str(ticker or "").upper().strip()
    root = _as_dict(settings)
    store = _as_dict(root.get(USER_SETTINGS_UNIFIED_PROFILE_STORE_KEY))
    tickers_payload = _as_dict(store.get(UNIFIED_PROFILE_STORE_TICKERS_KEY))

    next_tickers = dict(tickers_payload)
    next_tickers[ticker_upper] = {
        "profiles": profiles if isinstance(profiles, list) else [],
        "active_profile_id": str(active_profile_id or "").strip(),
    }

    next_store = dict(store)
    next_store[UNIFIED_PROFILE_STORE_TICKERS_KEY] = next_tickers
    return {USER_SETTINGS_UNIFIED_PROFILE_STORE_KEY: next_store}


def merge_unified_profile_options_payload(
    *,
    base_payload: Dict[str, Any],
    user_profiles: List[Dict[str, Any]],
    user_active_profile_id: Optional[str],
) -> Dict[str, Any]:
    base_profiles = (
        list(base_payload.get("profiles", []))
        if isinstance(base_payload.get("profiles"), list)
        else []
    )
    legacy_profiles = [
        row
        for row in base_profiles
        if isinstance(row, dict)
        and str(row.get("profile_id") or "").strip().startswith(
            LEGACY_UNIFIED_PROFILE_PREFIX
        )
    ]

    merged_profiles: List[Dict[str, Any]] = []
    seen_profile_ids: set[str] = set()
    for row in list(user_profiles or []) + legacy_profiles:
        if not isinstance(row, dict):
            continue
        profile_id = str(row.get("profile_id") or "").strip()
        if not profile_id or profile_id in seen_profile_ids:
            continue
        seen_profile_ids.add(profile_id)
        merged_profiles.append(row)

    resolved_active = str(user_active_profile_id or "").strip() or str(
        base_payload.get("active_profile_id") or ""
    ).strip()
    if resolved_active and resolved_active not in seen_profile_ids:
        resolved_active = ""

    payload = dict(base_payload)
    payload["profiles"] = merged_profiles
    payload["active_profile_id"] = resolved_active or None
    return payload
