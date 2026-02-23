from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def coerce_bool(value: Any, *, default: Optional[bool] = None) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def pick_l2_float(
    *,
    request_value: Any,
    cfg_key: str,
    profile_key: str,
    aos_l2_cfg: Dict[str, Any],
    adaptive_profile_runtime: Dict[str, Any],
) -> float:
    try:
        profile_value = float(adaptive_profile_runtime.get(profile_key, 0.0) or 0.0)
    except (TypeError, ValueError):
        profile_value = 0.0
    if abs(profile_value) > 1e-12:
        return profile_value
    try:
        req = float(request_value)
    except (TypeError, ValueError):
        req = 0.0
    if abs(req) > 1e-12:
        return req
    try:
        return float(aos_l2_cfg.get(cfg_key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def resolve_optional_runtime_non_negative_int(
    key: str, adaptive_profile_runtime: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    adaptive_profile_runtime = adaptive_profile_runtime or {}
    if key not in adaptive_profile_runtime:
        return None
    raw = adaptive_profile_runtime.get(key)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return None


def resolve_optional_runtime_bool(
    key: str, adaptive_profile_runtime: Optional[Dict[str, Any]] = None
) -> Optional[bool]:
    adaptive_profile_runtime = adaptive_profile_runtime or {}
    if key not in adaptive_profile_runtime:
        return None
    return coerce_bool(adaptive_profile_runtime.get(key), default=None)


def resolve_positioning_float(
    *,
    request_value: Any,
    request_default: float,
    positioning_key: str,
    positioning_cfg: Optional[Dict[str, Any]] = None,
    adaptive_profile_runtime: Optional[Dict[str, Any]] = None,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    runtime_key: Optional[str] = None,
    runtime_positive_only: bool = False,
) -> Tuple[float, str]:
    positioning_cfg = positioning_cfg or {}
    adaptive_profile_runtime = adaptive_profile_runtime or {}
    source = "request"
    try:
        resolved = float(request_value)
    except (TypeError, ValueError):
        resolved = float(request_default)
        source = "default"

    if abs(resolved - float(request_default)) < 1e-12 and positioning_cfg:
        raw = positioning_cfg.get(positioning_key)
        if raw is not None:
            try:
                resolved = float(raw)
                source = "positioning_config"
            except (TypeError, ValueError):
                pass

    if runtime_key:
        try:
            runtime_value = float(adaptive_profile_runtime.get(runtime_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            runtime_value = 0.0
        runtime_valid = (
            runtime_value > 0 if runtime_positive_only else abs(runtime_value) > 1e-12
        )
        if runtime_valid:
            resolved = runtime_value
            source = "adaptive_profile"

    if min_value is not None:
        resolved = max(min_value, resolved)
    if max_value is not None:
        resolved = min(max_value, resolved)
    return resolved, source


def resolve_positioning_int(
    *,
    request_value: Any,
    request_default: int,
    positioning_key: str,
    positioning_cfg: Optional[Dict[str, Any]] = None,
    adaptive_profile_runtime: Optional[Dict[str, Any]] = None,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    runtime_key: Optional[str] = None,
    runtime_positive_only: bool = False,
) -> Tuple[int, str]:
    positioning_cfg = positioning_cfg or {}
    adaptive_profile_runtime = adaptive_profile_runtime or {}
    source = "request"
    try:
        resolved = int(request_value)
    except (TypeError, ValueError):
        resolved = int(request_default)
        source = "default"

    if resolved == int(request_default) and positioning_cfg:
        raw = positioning_cfg.get(positioning_key)
        if raw is not None:
            try:
                resolved = int(raw)
                source = "positioning_config"
            except (TypeError, ValueError):
                pass

    if runtime_key:
        try:
            runtime_value = int(adaptive_profile_runtime.get(runtime_key, 0) or 0)
        except (TypeError, ValueError):
            runtime_value = 0
        runtime_valid = (
            runtime_value > 0 if runtime_positive_only else runtime_value != 0
        )
        if runtime_valid:
            resolved = runtime_value
            source = "adaptive_profile"

    if min_value is not None:
        resolved = max(min_value, resolved)
    if max_value is not None:
        resolved = min(max_value, resolved)
    return resolved, source


def resolve_positioning_bool(
    *,
    request_value: Any,
    request_default: bool,
    positioning_key: str,
    positioning_cfg: Optional[Dict[str, Any]] = None,
    adaptive_profile_runtime: Optional[Dict[str, Any]] = None,
    runtime_key: Optional[str] = None,
) -> Tuple[bool, str]:
    positioning_cfg = positioning_cfg or {}
    adaptive_profile_runtime = adaptive_profile_runtime or {}
    source = "request"
    resolved = coerce_bool(request_value, default=request_default)
    if resolved is None:
        resolved = request_default
        source = "default"
    if (
        resolved == bool(request_default)
        and positioning_cfg
        and positioning_key in positioning_cfg
    ):
        positioned = coerce_bool(positioning_cfg.get(positioning_key), default=None)
        if positioned is not None:
            resolved = positioned
            source = "positioning_config"
    if runtime_key:
        runtime_bool = coerce_bool(
            adaptive_profile_runtime.get(runtime_key), default=None
        )
        if runtime_bool is not None:
            resolved = runtime_bool
            source = "adaptive_profile"
    return bool(resolved), source


def resolve_positioning_str(
    *,
    request_value: Any,
    request_default: str,
    positioning_key: str,
    positioning_cfg: Optional[Dict[str, Any]] = None,
    adaptive_profile_runtime: Optional[Dict[str, Any]] = None,
    runtime_key: Optional[str] = None,
    strip: bool = True,
) -> Tuple[str, str]:
    positioning_cfg = positioning_cfg or {}
    adaptive_profile_runtime = adaptive_profile_runtime or {}
    source = "request"
    if request_value is None:
        resolved = str(request_default or "")
        source = "default"
    else:
        resolved = str(request_value)
    if strip:
        resolved = resolved.strip()
    default_text = str(request_default or "")
    if strip:
        default_text = default_text.strip()

    if (
        resolved == default_text
        and positioning_cfg
        and positioning_key in positioning_cfg
    ):
        positioned = positioning_cfg.get(positioning_key)
        if positioned is not None:
            resolved = str(positioned)
            if strip:
                resolved = resolved.strip()
            source = "positioning_config"
    if runtime_key and runtime_key in adaptive_profile_runtime:
        runtime_val = adaptive_profile_runtime.get(runtime_key)
        if runtime_val is not None:
            resolved = str(runtime_val)
            if strip:
                resolved = resolved.strip()
            source = "adaptive_profile"
    return resolved, source


def resolve_stop_loss_mode(
    *,
    request_mode: Any,
    positioning_cfg: Optional[Dict[str, Any]] = None,
    request_default: str = "strategy",
    positioning_key: str = "stop_loss_mode",
) -> Tuple[str, str]:
    positioning_cfg = positioning_cfg or {}
    valid_modes = {"strategy", "fixed", "capped"}
    source = "request"
    normalized_default = str(request_default).strip().lower() or "strategy"
    mode = str(request_mode or normalized_default).strip().lower()
    if mode not in valid_modes:
        mode = normalized_default
        source = "default"
    if mode == normalized_default and positioning_cfg:
        positioned_mode = str(positioning_cfg.get(positioning_key, "")).strip().lower()
        if positioned_mode in valid_modes:
            mode = positioned_mode
            source = "positioning_config"
    return mode, source


def resolve_adverse_flow_threshold(
    *,
    request_value: Any,
    request_default: float,
    positioning_key: str,
    aos_key: str,
    runtime_key: str,
    positioning_cfg: Optional[Dict[str, Any]] = None,
    aos_applied: Optional[Dict[str, Any]] = None,
    adaptive_profile_runtime: Optional[Dict[str, Any]] = None,
) -> Tuple[float, str]:
    positioning_cfg = positioning_cfg or {}
    aos_applied = aos_applied or {}
    adaptive_profile_runtime = adaptive_profile_runtime or {}
    source = "request"
    try:
        resolved = float(request_value)
    except (TypeError, ValueError):
        resolved = request_default
        source = "default"
    if abs(resolved - request_default) < 1e-12:
        if positioning_cfg and positioning_key in positioning_cfg:
            try:
                resolved = float(positioning_cfg.get(positioning_key))
                source = "positioning_config"
            except (TypeError, ValueError):
                pass
        if source in {"request", "default"}:
            try:
                resolved = float(aos_applied.get(aos_key, request_default))
                source = "aos_config"
            except (TypeError, ValueError):
                resolved = request_default
                source = "default"
    try:
        runtime_value = float(adaptive_profile_runtime.get(runtime_key, 0.0) or 0.0)
    except (TypeError, ValueError):
        runtime_value = 0.0
    if runtime_value > 0:
        resolved = runtime_value
        source = "adaptive_profile"
    return max(0.02, resolved), source
