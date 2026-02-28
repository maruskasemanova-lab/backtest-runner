from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple


def bar_time_token(value: Any) -> str:
    if hasattr(value, "isoformat"):
        try:
            return str(value.isoformat())
        except Exception:
            return str(value)
    return str(value)


def iso_day_token(value: Any) -> str:
    if hasattr(value, "date"):
        try:
            return str(value.date().isoformat())
        except Exception:
            pass
    text = str(value or "")
    if len(text) >= 10:
        return text[:10]
    return text


def summarize_days_compact(days: List[str], *, max_days: int = 8) -> str:
    ordered = [str(day) for day in days if str(day).strip()]
    if not ordered:
        return ""
    if len(ordered) <= max_days:
        return ",".join(ordered)
    preview = ",".join(ordered[:max_days])
    return f"{preview},...(+{len(ordered) - max_days} more)"


def iso_day_ordinal(day: Any) -> int | None:
    try:
        return int(datetime.strptime(str(day), "%Y-%m-%d").toordinal())
    except Exception:
        return None


def is_day_range_superset(
    cached_start: str,
    cached_end: str,
    requested_start: str,
    requested_end: str,
) -> bool:
    return str(cached_start) <= str(requested_start) and str(cached_end) >= str(
        requested_end
    )


def range_span_days(start: str, end: str) -> int:
    start_ord = iso_day_ordinal(start)
    end_ord = iso_day_ordinal(end)
    if start_ord is None or end_ord is None:
        return 10**9
    return max(0, end_ord - start_ord)


def slice_bars_for_day_range(
    bars: List[Dict[str, Any]],
    *,
    range_start: str,
    range_end: str,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for bar in bars:
        day_token = iso_day_token(bar.get("timestamp"))
        if day_token and str(range_start) <= day_token <= str(range_end):
            selected.append(bar)
    return selected


def slice_reference_map_for_day_range(
    ref_map: Dict[str, Any],
    *,
    range_start: str,
    range_end: str,
) -> Dict[str, Any]:
    selected: Dict[str, Any] = {}
    for ts_key, ref_bar in ref_map.items():
        day_token = iso_day_token(ts_key)
        if day_token and str(range_start) <= day_token <= str(range_end):
            selected[str(ts_key)] = ref_bar
    return selected
