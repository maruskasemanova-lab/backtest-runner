from __future__ import annotations

from typing import Any, Optional, Tuple


def canonical_trading_hours(raw_hours: Any) -> Tuple[int, ...]:
    """Return stable, deduplicated 0-23 trading-hour tuple."""
    if not isinstance(raw_hours, list):
        return tuple()
    normalized = []
    seen = set()
    for item in raw_hours:
        try:
            hour = int(item)
        except (TypeError, ValueError):
            continue
        if hour < 0 or hour > 23 or hour in seen:
            continue
        seen.add(hour)
        normalized.append(hour)
    return tuple(sorted(normalized))


def coerce_include_extended_hours(value: Any) -> Optional[bool]:
    """Parse optional include_extended_hours flag from mixed input types."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return None
