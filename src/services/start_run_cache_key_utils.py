from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from src.services.start_run_range_utils import (
    bar_time_token,
    is_day_range_superset,
    range_span_days,
)


def file_identity(path_value: str) -> Tuple[str, int, int]:
    resolved = str(Path(path_value).resolve())
    try:
        stat = Path(resolved).stat()
        return resolved, int(stat.st_mtime_ns), int(stat.st_size)
    except OSError:
        return resolved, -1, -1


def build_base_bars_cache_key(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    data_files: List[str],
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
) -> str:
    file_identities = tuple(file_identity(file) for file in data_files)
    key_payload = (
        ticker.upper(),
        str(range_start),
        str(range_end),
        bool(time_filter_enabled),
        trading_hours,
        bool(regular_session_only),
        file_identities,
    )
    return repr(key_payload)


def build_reference_bars_cache_key(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    ref_files: List[str],
) -> str:
    file_identities = tuple(file_identity(file) for file in ref_files)
    key_payload = (
        ticker.upper(),
        str(range_start),
        str(range_end),
        file_identities,
    )
    return repr(key_payload)


def compute_l2_day_coverage(
    *,
    bars: List[Dict[str, Any]],
    feature_map: Dict[int, Dict[str, Any]],
    to_utc_datetime: Any,
) -> Dict[str, Any]:
    bar_day_counts: Dict[str, int] = {}
    l2_day_counts: Dict[str, int] = {}
    for bar in bars:
        ts_value = bar.get("timestamp")
        if ts_value is None:
            continue
        try:
            ts_utc = to_utc_datetime(ts_value)
        except Exception:
            continue
        day = ts_utc.strftime("%Y-%m-%d")
        bar_day_counts[day] = int(bar_day_counts.get(day, 0)) + 1
        minute_key = int(ts_utc.timestamp() // 60)
        if feature_map.get(minute_key):
            l2_day_counts[day] = int(l2_day_counts.get(day, 0)) + 1

    bar_days = sorted(bar_day_counts.keys())
    l2_days = sorted(l2_day_counts.keys())
    missing_days = sorted(day for day in bar_days if day not in l2_day_counts)
    return {
        "bar_days": bar_days,
        "l2_days": l2_days,
        "missing_days": missing_days,
        "bar_day_counts": bar_day_counts,
        "l2_day_counts": l2_day_counts,
    }


def build_l2_enrich_cache_key(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    comparable_mode: bool,
    is_multi_day_request: bool,
    bars: List[Dict[str, Any]],
) -> str:
    bars_count = len(bars)
    first_ts = bar_time_token(bars[0].get("timestamp")) if bars else ""
    last_ts = bar_time_token(bars[-1].get("timestamp")) if bars else ""

    sample_tokens: List[Tuple[int, str, float, float, float]] = []
    if bars_count:
        candidate_indices = [0, 1, bars_count // 2, bars_count - 2, bars_count - 1]
        seen_indices = set()
        for idx in candidate_indices:
            if idx < 0 or idx >= bars_count or idx in seen_indices:
                continue
            seen_indices.add(idx)
            bar = bars[idx] or {}
            sample_tokens.append(
                (
                    idx,
                    bar_time_token(bar.get("timestamp")),
                    float(bar.get("open", 0.0) or 0.0),
                    float(bar.get("close", 0.0) or 0.0),
                    float(bar.get("volume", 0.0) or 0.0),
                )
            )

    key_payload = (
        ticker.upper(),
        str(range_start),
        str(range_end),
        bool(requested_l2_only),
        bool(requested_l2_confirm),
        bool(comparable_mode),
        bool(is_multi_day_request),
        bars_count,
        first_ts,
        last_ts,
        tuple(sample_tokens),
    )
    return repr(key_payload)


def build_base_bars_meta(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> Dict[str, Any]:
    return {
        "ticker": str(ticker).upper(),
        "range_start": str(range_start),
        "range_end": str(range_end),
        "time_filter_enabled": bool(time_filter_enabled),
        "trading_hours": tuple(trading_hours),
        "regular_session_only": bool(regular_session_only),
        "file_identities": tuple(file_identities),
    }


def build_reference_bars_meta(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> Dict[str, Any]:
    return {
        "ticker": str(ticker).upper(),
        "range_start": str(range_start),
        "range_end": str(range_end),
        "file_identities": tuple(file_identities),
    }


def select_best_superset_entry(
    *,
    payload_store: OrderedDict,
    meta_store: Dict[str, Dict[str, Any]],
    range_start: str,
    range_end: str,
    meta_matches: Callable[[Dict[str, Any]], bool],
) -> Tuple[str, Any, str, str] | None:
    best_key: str | None = None
    best_payload: Any = None
    best_span: int | None = None
    best_start = ""
    best_end = ""
    for key, meta in meta_store.items():
        if not isinstance(meta, dict) or not meta_matches(meta):
            continue
        cached_start = str(meta.get("range_start", ""))
        cached_end = str(meta.get("range_end", ""))
        if not cached_start or not cached_end:
            continue
        if not is_day_range_superset(cached_start, cached_end, range_start, range_end):
            continue
        payload = payload_store.get(key)
        if payload is None:
            continue
        span = range_span_days(cached_start, cached_end)
        if best_span is not None and span >= best_span:
            continue
        best_key = key
        best_payload = payload
        best_span = span
        best_start = cached_start
        best_end = cached_end
    if best_key is None or best_payload is None:
        return None
    return best_key, best_payload, best_start, best_end


def base_cache_meta_matches(
    *,
    meta: Dict[str, Any],
    ticker: str,
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> bool:
    return (
        str(meta.get("ticker", "")).upper() == str(ticker).upper()
        and bool(meta.get("time_filter_enabled")) == bool(time_filter_enabled)
        and tuple(meta.get("trading_hours", ())) == tuple(trading_hours)
        and bool(meta.get("regular_session_only", False)) == bool(regular_session_only)
        and tuple(meta.get("file_identities", ())) == tuple(file_identities)
    )


def reference_cache_meta_matches(
    *,
    meta: Dict[str, Any],
    ticker: str,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> bool:
    return str(meta.get("ticker", "")).upper() == str(ticker).upper() and tuple(
        meta.get("file_identities", ())
    ) == tuple(file_identities)
