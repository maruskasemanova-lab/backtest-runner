from __future__ import annotations

from typing import Any, Optional, Tuple

TRADE_EVAL_MODE_STANDARD = "standard"
TRADE_EVAL_MODE_INTRABAR_1S = "intrabar_1s"
TRADE_EVAL_MODE_INTRABAR_5S = "intrabar_5s"

_STANDARD_MODE_ALIASES = {
    "standard",
    "bar",
    "bars",
    "fast",
    "default",
    "minute",
    "false",
    "0",
    "off",
}
_INTRABAR_1S_MODE_ALIASES = {
    "intrabar_1s",
    "intrabar",
    "intrabar-1s",
    "intrabar1s",
    "1s",
    "1sec",
    "1secs",
    "1second",
    "1seconds",
    "second",
    "seconds",
    "true",
    "1",
    "on",
}
_INTRABAR_5S_MODE_ALIASES = {
    "intrabar_5s",
    "intrabar-5s",
    "intrabar5s",
    "5s",
    "5sec",
    "5secs",
    "5second",
    "5seconds",
}


def normalize_trade_eval_mode(raw_mode: Any) -> Optional[str]:
    if isinstance(raw_mode, bool):
        return (
            TRADE_EVAL_MODE_INTRABAR_1S if raw_mode else TRADE_EVAL_MODE_STANDARD
        )
    if raw_mode is None:
        return None
    normalized = str(raw_mode).strip().lower()
    if not normalized:
        return None
    if normalized in _STANDARD_MODE_ALIASES:
        return TRADE_EVAL_MODE_STANDARD
    if normalized in _INTRABAR_5S_MODE_ALIASES:
        return TRADE_EVAL_MODE_INTRABAR_5S
    if normalized in _INTRABAR_1S_MODE_ALIASES:
        return TRADE_EVAL_MODE_INTRABAR_1S
    return None


def normalize_intrabar_eval_step_seconds(raw_step_seconds: Any) -> int:
    try:
        parsed = int(raw_step_seconds)
    except (TypeError, ValueError):
        parsed = 1
    return 5 if parsed >= 5 else 1


def resolve_trade_eval_mode_from_settings(
    *, intrabar_enabled: bool, intrabar_eval_step_seconds: Any
) -> str:
    if not bool(intrabar_enabled):
        return TRADE_EVAL_MODE_STANDARD
    return (
        TRADE_EVAL_MODE_INTRABAR_5S
        if normalize_intrabar_eval_step_seconds(intrabar_eval_step_seconds) >= 5
        else TRADE_EVAL_MODE_INTRABAR_1S
    )


def resolve_trade_eval_settings(
    *,
    requested_mode: Any,
    fallback_intrabar_enabled: bool,
    fallback_intrabar_eval_step_seconds: Any = 1,
) -> Tuple[str, bool, int]:
    normalized_mode = normalize_trade_eval_mode(requested_mode)
    if normalized_mode == TRADE_EVAL_MODE_STANDARD:
        return (TRADE_EVAL_MODE_STANDARD, False, 1)
    if normalized_mode == TRADE_EVAL_MODE_INTRABAR_5S:
        return (TRADE_EVAL_MODE_INTRABAR_5S, True, 5)
    if normalized_mode == TRADE_EVAL_MODE_INTRABAR_1S:
        return (TRADE_EVAL_MODE_INTRABAR_1S, True, 1)

    effective_intrabar_enabled = bool(fallback_intrabar_enabled)
    effective_step_seconds = (
        normalize_intrabar_eval_step_seconds(fallback_intrabar_eval_step_seconds)
        if effective_intrabar_enabled
        else 1
    )
    effective_mode = resolve_trade_eval_mode_from_settings(
        intrabar_enabled=effective_intrabar_enabled,
        intrabar_eval_step_seconds=effective_step_seconds,
    )
    return (effective_mode, effective_intrabar_enabled, effective_step_seconds)
