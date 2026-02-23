from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

from fastapi import HTTPException


def _resolve_requested_time_window(
    *,
    request: Any,
    to_utc_datetime: Callable[[Any], Any],
):
    raw_start = getattr(request, "start_time", None)
    raw_end = getattr(request, "end_time", None)
    if raw_start in (None, "") and raw_end in (None, ""):
        return None

    try:
        start_dt = to_utc_datetime(raw_start) if raw_start not in (None, "") else None
        end_dt = to_utc_datetime(raw_end) if raw_end not in (None, "") else None
    except Exception as exc:  # pragma: no cover - exact parser exception varies
        raise HTTPException(400, f"Invalid intraday time window: {exc}") from exc

    if start_dt is not None and end_dt is not None and end_dt < start_dt:
        raise HTTPException(
            400, "Invalid intraday time window: end_time must be >= start_time"
        )

    return start_dt, end_dt


def filter_bars_for_requested_time_window(
    *,
    bars: Iterable[Dict[str, Any]],
    request: Any,
    to_utc_datetime: Callable[[Any], Any],
) -> List[Dict[str, Any]]:
    window = _resolve_requested_time_window(
        request=request, to_utc_datetime=to_utc_datetime
    )
    if window is None:
        return list(bars)

    start_dt, end_dt = window
    filtered: List[Dict[str, Any]] = []
    for bar in bars:
        try:
            ts = to_utc_datetime((bar or {}).get("timestamp"))
        except Exception:
            continue
        if start_dt is not None and ts < start_dt:
            continue
        if end_dt is not None and ts > end_dt:
            continue
        filtered.append(bar)
    return filtered


def filter_reference_map_for_requested_time_window(
    *,
    ref_bars_map: Dict[str, Any],
    request: Any,
    to_utc_datetime: Callable[[Any], Any],
) -> Dict[str, Any]:
    window = _resolve_requested_time_window(
        request=request, to_utc_datetime=to_utc_datetime
    )
    if window is None:
        return dict(ref_bars_map or {})

    start_dt, end_dt = window
    filtered: Dict[str, Any] = {}
    for ts_key, bar in (ref_bars_map or {}).items():
        try:
            ts = to_utc_datetime(ts_key)
        except Exception:
            continue
        if start_dt is not None and ts < start_dt:
            continue
        if end_dt is not None and ts > end_dt:
            continue
        filtered[str(ts_key)] = bar
    return filtered
