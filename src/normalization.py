"""
Normalization - Input validation and normalization utilities.

This module provides centralized normalization functions for:
- Strategy selection modes
- Integer/float clamping
- Boolean options
- Strategy sets and regime filters
- Strategy combo profiles
- Tuner profiles
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union


def normalize_strategy_selection_mode(
    value: Any, default: str = "adaptive_top_n"
) -> str:
    """
    Normalize strategy selection mode.

    Args:
        value: Raw input value
        default: Default value if invalid

    Returns:
        Normalized strategy selection mode string
    """
    valid_modes = {
        "adaptive_top_n",
        "regime_conditional",
        "single",
        "all",
    }
    mode = str(value or default).strip().lower()
    return mode if mode in valid_modes else default


def normalize_clamped_int(
    value: Any,
    default: int,
    min_val: int,
    max_val: int,
) -> int:
    """
    Normalize and clamp integer value.

    Args:
        value: Raw input value
        default: Default value if invalid
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped integer value
    """
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(min_val, min(max_val, result))


def sanitize_strategy_params(
    params: Dict[str, Any],
    allowed_keys: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Sanitize strategy parameters for API transmission.

    Args:
        params: Raw parameters dictionary
        allowed_keys: Optional set of allowed parameter keys

    Returns:
        Sanitized parameters dictionary
    """
    if not isinstance(params, dict):
        return {}

    result = {}
    for key, value in params.items():
        # Skip None values
        if value is None:
            continue

        # Skip non-allowed keys if specified
        if allowed_keys and key not in allowed_keys:
            continue

        # Convert value based on type
        if isinstance(value, bool):
            result[key] = value
        elif isinstance(value, (int, float)):
            result[key] = value
        elif isinstance(value, str):
            result[key] = value.strip()
        elif isinstance(value, (list, dict)):
            result[key] = value

    return result


def normalize_strategy_combo_profiles(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalize strategy combo profiles list.

    Args:
        raw: Raw input (list or other)

    Returns:
        List of normalized profile dictionaries
    """
    if not isinstance(raw, list):
        return []

    result = []
    seen_ids = set()

    for item in raw:
        if not isinstance(item, dict):
            continue

        profile_id = str(item.get("profile_id") or "").strip()
        if not profile_id or profile_id in seen_ids:
            continue
        seen_ids.add(profile_id)

        profile = {
            "profile_id": profile_id,
            "profile_name": str(item.get("profile_name") or profile_id).strip(),
            "created_at": item.get("created_at") or datetime.utcnow().isoformat() + "Z",
            "updated_at": item.get("updated_at") or datetime.utcnow().isoformat() + "Z",
        }

        if isinstance(item.get("strategy_params"), dict):
            profile["strategy_params"] = item["strategy_params"]

        if isinstance(item.get("notes"), str):
            profile["notes"] = item["notes"].strip()

        result.append(profile)

    return result


def normalize_unified_profiles(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalize unified profiles list.

    Unified profile contains two sections:
    - strategy_profile: strategy params map
    - execution_profile: run/execution/runtime config map
    """
    if not isinstance(raw, list):
        return []

    result = []
    seen_ids = set()

    for item in raw:
        if not isinstance(item, dict):
            continue

        profile_id = str(item.get("profile_id") or "").strip()
        if not profile_id or profile_id in seen_ids:
            continue
        seen_ids.add(profile_id)

        profile = {
            "profile_id": profile_id,
            "profile_name": str(item.get("profile_name") or profile_id).strip(),
            "created_at": item.get("created_at") or datetime.utcnow().isoformat() + "Z",
            "updated_at": item.get("updated_at") or datetime.utcnow().isoformat() + "Z",
        }

        strategy_profile = item.get("strategy_profile")
        if isinstance(strategy_profile, dict):
            profile["strategy_profile"] = strategy_profile

        execution_profile = item.get("execution_profile")
        if isinstance(execution_profile, dict):
            profile["execution_profile"] = execution_profile

        if isinstance(item.get("source_strategy_combo_profile_id"), str):
            profile["source_strategy_combo_profile_id"] = str(
                item.get("source_strategy_combo_profile_id") or ""
            ).strip()
        if isinstance(item.get("source_adaptive_tuner_profile_id"), str):
            profile["source_adaptive_tuner_profile_id"] = str(
                item.get("source_adaptive_tuner_profile_id") or ""
            ).strip()

        if isinstance(item.get("notes"), str):
            profile["notes"] = item["notes"].strip()

        result.append(profile)

    return result


def normalize_tuner_profiles(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalize tuner profiles list.

    Args:
        raw: Raw input (list or other)

    Returns:
        List of normalized profile dictionaries
    """
    if not isinstance(raw, list):
        return []

    result = []
    seen_ids = set()

    for item in raw:
        if not isinstance(item, dict):
            continue

        profile_id = str(item.get("profile_id") or "").strip()
        if not profile_id or profile_id in seen_ids:
            continue
        seen_ids.add(profile_id)

        profile = {
            "profile_id": profile_id,
            "profile_name": str(item.get("profile_name") or profile_id).strip(),
            "created_at": item.get("created_at") or datetime.utcnow().isoformat() + "Z",
            "updated_at": item.get("updated_at") or datetime.utcnow().isoformat() + "Z",
        }

        if isinstance(item.get("search_space"), dict):
            profile["search_space"] = item["search_space"]

        candidate = item.get("candidate")
        if isinstance(candidate, dict):
            profile["candidate"] = candidate

        best_trial = item.get("best_trial")
        if isinstance(best_trial, dict):
            profile["best_trial"] = best_trial

        if isinstance(item.get("best_candidate"), dict):
            profile["best_candidate"] = item["best_candidate"]
            if "candidate" not in profile:
                profile["candidate"] = item["best_candidate"]

        if isinstance(item.get("metrics"), dict):
            profile["metrics"] = item["metrics"]

        if isinstance(item.get("metadata"), dict):
            profile["metadata"] = item["metadata"]

        if isinstance(item.get("vector_analysis"), dict):
            profile["vector_analysis"] = item["vector_analysis"]

        if isinstance(item.get("ticker"), str):
            profile["ticker"] = str(item.get("ticker") or "").strip().upper()

        if isinstance(item.get("method"), str):
            profile["method"] = str(item.get("method") or "").strip()

        if isinstance(item.get("score_metric"), str):
            profile["score_metric"] = str(item.get("score_metric") or "").strip()

        if isinstance(item.get("date_from"), str):
            profile["date_from"] = str(item.get("date_from") or "").strip()

        if isinstance(item.get("date_to"), str):
            profile["date_to"] = str(item.get("date_to") or "").strip()

        if isinstance(item.get("scope"), str):
            profile["scope"] = str(item.get("scope") or "").strip().lower()

        if isinstance(item.get("owner_user_id"), str):
            profile["owner_user_id"] = str(item.get("owner_user_id") or "").strip()

        if isinstance(item.get("owner_tenant_id"), str):
            profile["owner_tenant_id"] = str(item.get("owner_tenant_id") or "").strip()

        try:
            adaptive_version = int(item.get("adaptive_version", 1))
        except (TypeError, ValueError):
            adaptive_version = 1
        profile["adaptive_version"] = max(1, adaptive_version)

        for key in ("evaluated_days", "quick_max_days", "quick_trial_boost"):
            if key not in item:
                continue
            try:
                profile[key] = int(item.get(key))
            except (TypeError, ValueError):
                continue

        for key in ("score",):
            if key not in item:
                continue
            try:
                profile[key] = float(item.get(key))
            except (TypeError, ValueError):
                continue

        for key in ("l2_required", "l2_only", "quick_mode"):
            if key in item:
                profile[key] = bool(item.get(key))

        if isinstance(item.get("notes"), str):
            profile["notes"] = item["notes"].strip()

        result.append(profile)

    return result


def normalize_non_negative_int(value: Any, default: int = 0) -> int:
    """Normalize to non-negative integer."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return max(0, result)
