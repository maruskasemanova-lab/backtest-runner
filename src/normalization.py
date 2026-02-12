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


def normalize_strategy_selection_mode(value: Any, default: str = "adaptive_top_n") -> str:
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


def normalize_bool_options(payload: Dict[str, Any], keys: Set[str]) -> Dict[str, bool]:
    """
    Normalize boolean options in payload.
    
    Args:
        payload: Input dictionary
        keys: Keys to normalize as booleans
        
    Returns:
        Dictionary with normalized boolean values
    """
    result = {}
    for key in keys:
        if key in payload:
            result[key] = bool(payload[key])
    return result


def normalize_strategy_sets(raw: Any) -> List[str]:
    """
    Normalize strategy set to list of lowercase strategy names.
    
    Args:
        raw: Raw input (string, list, or other)
        
    Returns:
        List of normalized strategy names
    """
    if isinstance(raw, str):
        items = raw.split(",")
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    
    result = []
    seen = set()
    for item in items:
        value = str(item or "").strip().lower()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def normalize_regime_filter_sets(raw: Any) -> List[str]:
    """
    Normalize regime filter to list of uppercase regime names.
    
    Args:
        raw: Raw input (string, list, or other)
        
    Returns:
        List of normalized regime names
    """
    valid_regimes = {"TRENDING", "MIXED", "CHOPPY"}
    
    if isinstance(raw, str):
        items = raw.split(",")
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    
    result = []
    seen = set()
    for item in items:
        value = str(item or "").strip().upper()
        if value in valid_regimes and value not in seen:
            seen.add(value)
            result.append(value)
    return result


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
        
        if isinstance(item.get("best_candidate"), dict):
            profile["best_candidate"] = item["best_candidate"]
        
        if isinstance(item.get("metrics"), dict):
            profile["metrics"] = item["metrics"]
        
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


def normalize_int_options(value: Any, valid_options: Set[int], default: int) -> int:
    """Normalize integer to one of valid options."""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result in valid_options else default


def normalize_mode_options(value: Any, valid_options: Set[str], default: str) -> str:
    """Normalize string to one of valid options."""
    mode = str(value or default).strip().lower()
    return mode if mode in valid_options else default


def normalize_float_options(
    value: Any,
    min_val: float,
    max_val: float,
    default: float,
) -> float:
    """Normalize and clamp float value."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    return max(min_val, min(max_val, result))


def normalize_time_window_sets(raw: Any) -> List[int]:
    """
    Normalize trading hours to list of integers.
    
    Args:
        raw: Raw input (string, list, or other)
        
    Returns:
        List of valid hour integers (0-23)
    """
    if isinstance(raw, str):
        items = raw.split(",")
    elif isinstance(raw, list):
        items = raw
    else:
        return []
    
    result = []
    seen = set()
    for item in items:
        try:
            hour = int(item)
            if 0 <= hour <= 23 and hour not in seen:
                seen.add(hour)
                result.append(hour)
        except (TypeError, ValueError):
            continue
    return sorted(result)


def normalize_regime_strategy_map_sets(raw: Any) -> Optional[Dict[str, List[str]]]:
    """
    Normalize regime strategy map.
    
    Args:
        raw: Raw input dictionary
        
    Returns:
        Normalized regime strategy map or None
    """
    if not isinstance(raw, dict):
        return None
    
    valid_regimes = {"TRENDING", "MIXED", "CHOPPY"}
    result = {}
    
    for regime, strategies in raw.items():
        regime_key = str(regime).strip().upper()
        if regime_key not in valid_regimes:
            continue
        result[regime_key] = normalize_strategy_sets(strategies)
    
    return result if result else None


def normalize_strategy_key(value: Any) -> str:
    """
    Normalize strategy key to lowercase snake_case.
    
    Args:
        value: Raw strategy name
        
    Returns:
        Normalized strategy key
    """
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
