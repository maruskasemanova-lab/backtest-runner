import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .shared import normalize_iso_timestamp


def _load_profile_options_from_aos_config(
    *,
    project_root: Path,
    ticker: str,
    profiles_key: str,
    active_profile_key: str,
    source: str,
) -> List[Dict[str, Any]]:
    config_path = project_root / "aos_optimization" / "aos_config.json"
    if not config_path.exists() or not config_path.is_file():
        return []
    try:
        raw = config_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []

    tickers_payload = (
        payload.get("tickers", {}) if isinstance(payload.get("tickers"), dict) else {}
    )
    ticker_payload = (
        tickers_payload.get(ticker, {})
        if isinstance(tickers_payload.get(ticker), dict)
        else {}
    )
    active_profile_id = (
        str(ticker_payload.get(active_profile_key) or "").strip() or None
    )
    profiles = ticker_payload.get(profiles_key, [])
    if not isinstance(profiles, list):
        profiles = []

    collected: Dict[str, Dict[str, Any]] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("profile_id") or "").strip()
        if not profile_id:
            continue
        profile_name = (
            str(profile.get("profile_name") or "").strip()
            or str(profile.get("name") or "").strip()
            or None
        )
        created_at = normalize_iso_timestamp(profile.get("created_at"))
        existing = collected.get(profile_id)
        if existing is None:
            collected[profile_id] = {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "active": bool(active_profile_id and active_profile_id == profile_id),
                "latest_created_at": created_at,
                "source": source,
            }
            continue
        if not existing.get("profile_name") and profile_name:
            existing["profile_name"] = profile_name
        existing["active"] = bool(existing.get("active")) or bool(
            active_profile_id and active_profile_id == profile_id
        )
        existing_created_at = str(existing.get("latest_created_at") or "")
        if created_at and created_at > existing_created_at:
            existing["latest_created_at"] = created_at

    if active_profile_id and active_profile_id not in collected:
        collected[active_profile_id] = {
            "profile_id": active_profile_id,
            "profile_name": None,
            "active": True,
            "latest_created_at": None,
            "source": source,
        }

    options = list(collected.values())
    options.sort(key=lambda item: str(item.get("profile_id") or ""))
    options.sort(
        key=lambda item: str(item.get("latest_created_at") or ""), reverse=True
    )
    options.sort(key=lambda item: 0 if bool(item.get("active")) else 1)
    return options


def _merge_profile_options(
    history_options: List[Dict[str, Any]],
    aos_options: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for option in history_options + aos_options:
        if not isinstance(option, dict):
            continue
        profile_id = str(option.get("profile_id") or "").strip()
        if not profile_id:
            continue
        profile_name = str(option.get("profile_name") or "").strip() or None
        source = str(option.get("source") or "").strip() or "history"
        active = bool(option.get("active"))
        latest_created_at = str(option.get("latest_created_at") or "").strip() or None

        existing = merged.get(profile_id)
        if existing is None:
            merged[profile_id] = {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "active": active,
                "latest_created_at": latest_created_at,
                "sources": {source},
            }
            continue

        if not existing.get("profile_name") and profile_name:
            existing["profile_name"] = profile_name
        existing["active"] = bool(existing.get("active")) or active
        current_created = str(existing.get("latest_created_at") or "")
        if latest_created_at and latest_created_at > current_created:
            existing["latest_created_at"] = latest_created_at
        existing_sources = existing.get("sources")
        if isinstance(existing_sources, set):
            existing_sources.add(source)
        else:
            existing["sources"] = {source}

    options = []
    for item in merged.values():
        sources = (
            sorted(item.get("sources", set()))
            if isinstance(item.get("sources"), set)
            else []
        )
        options.append(
            {
                "profile_id": item.get("profile_id"),
                "profile_name": item.get("profile_name"),
                "active": bool(item.get("active")),
                "latest_created_at": item.get("latest_created_at"),
                "source": ",".join(sources) if sources else None,
            }
        )
    options.sort(key=lambda item: str(item.get("profile_id") or ""))
    options.sort(
        key=lambda item: str(item.get("latest_created_at") or ""), reverse=True
    )
    options.sort(key=lambda item: 0 if bool(item.get("active")) else 1)
    return options


def build_history_profile_options(
    *,
    project_root: Path,
    ticker: str,
    history_profile_names: Dict[str, Set[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    history_profile_options = [
        {
            "profile_id": profile_id,
            "profile_name": sorted(names)[0] if names else None,
            "active": False,
            "latest_created_at": None,
            "source": "history",
        }
        for profile_id, names in history_profile_names.items()
    ]
    history_profile_options.sort(key=lambda item: str(item.get("profile_id") or ""))

    adaptive_profile_options = _merge_profile_options(
        history_profile_options,
        _load_profile_options_from_aos_config(
            project_root=project_root,
            ticker=ticker,
            profiles_key="adaptive_tuner_profiles",
            active_profile_key="active_adaptive_tuner_profile_id",
            source="aos_config",
        ),
    )
    unified_profile_options = _merge_profile_options(
        history_profile_options,
        _load_profile_options_from_aos_config(
            project_root=project_root,
            ticker=ticker,
            profiles_key="unified_profiles",
            active_profile_key="active_unified_profile_id",
            source="aos_unified",
        ),
    )
    return {
        "adaptive_profiles": adaptive_profile_options,
        "unified_profiles": unified_profile_options,
    }
