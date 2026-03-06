from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_HEATMAP_BIN_SIZE = 0.5
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_MAX_DISTANCE_PCT = 12.0
DEFAULT_HVN_PERCENTILE = 0.85
DEFAULT_LVN_PERCENTILE = 0.25
DEFAULT_MIN_PEAK_SEPARATION_BINS = 3
DEFAULT_MAX_HVN_ZONES = 4
DEFAULT_MAX_LVN_ZONES = 3
DEFAULT_MIN_ZONE_BINS = 1


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _parse_iso_day(value: Any) -> Optional[datetime]:
    token = str(value or "").strip()
    if not token:
        return None
    if len(token) >= 10:
        token = token[:10]
    try:
        return datetime.strptime(token, "%Y-%m-%d")
    except ValueError:
        return None


def _bar_timestamp_token(bar: Any) -> str:
    if isinstance(bar, dict):
        raw = bar.get("timestamp")
    else:
        raw = getattr(bar, "timestamp", None)
    if hasattr(raw, "isoformat"):
        return str(raw.isoformat())
    return str(raw or "")


def _bar_reference_price(bar: Any) -> Optional[float]:
    value = None
    if isinstance(bar, dict):
        value = bar.get("open")
        if value is None:
            value = bar.get("close")
    else:
        value = getattr(bar, "open", None)
        if value is None:
            value = getattr(bar, "close", None)
    resolved = _safe_float(value, 0.0)
    return resolved if resolved > 0.0 else None


def _extract_reference_prices_by_day(bars: Iterable[Any]) -> Dict[str, float]:
    ordered: Dict[str, float] = {}
    for bar in bars:
        ts_token = _bar_timestamp_token(bar)
        if len(ts_token) < 10:
            continue
        day = ts_token[:10]
        if day in ordered:
            continue
        reference_price = _bar_reference_price(bar)
        if reference_price is None:
            continue
        ordered[day] = reference_price
    return ordered


def _percentile(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    q = max(0.0, min(1.0, float(q)))
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low = int(pos)
    high = min(len(ordered) - 1, low + 1)
    weight = pos - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _smooth(values: List[float]) -> List[float]:
    if not values:
        return []
    smoothed: List[float] = []
    for idx in range(len(values)):
        start = max(0, idx - 1)
        end = min(len(values), idx + 2)
        window = values[start:end]
        smoothed.append(sum(window) / max(1, len(window)))
    return smoothed


def _is_local_max(values: List[float], idx: int) -> bool:
    current = values[idx]
    left = values[idx - 1] if idx > 0 else float("-inf")
    right = values[idx + 1] if idx + 1 < len(values) else float("-inf")
    return current >= left and current >= right and (current > left or current > right)


def _select_peak_indices(
    values: List[float],
    *,
    min_peak_separation_bins: int,
    hvn_percentile: float,
    max_hvn_zones: int,
) -> List[int]:
    if not values:
        return []
    threshold = _percentile(values, hvn_percentile)
    candidates = [
        idx for idx in range(len(values)) if _is_local_max(values, idx) and values[idx] >= threshold
    ]
    if not candidates:
        candidates = sorted(range(len(values)), key=lambda idx: values[idx], reverse=True)[:max_hvn_zones]
    selected: List[int] = []
    for idx in sorted(candidates, key=lambda item: values[item], reverse=True):
        if any(abs(idx - chosen) < min_peak_separation_bins for chosen in selected):
            continue
        selected.append(idx)
        if len(selected) >= max_hvn_zones:
            break
    return sorted(selected)


def _expand_peak_zone(
    prices: List[float],
    values: List[float],
    peak_idx: int,
    *,
    min_zone_bins: int,
) -> tuple[int, int]:
    peak_value = values[peak_idx]
    threshold = max(_percentile(values, 0.60), peak_value * 0.65)
    left = peak_idx
    right = peak_idx
    while left > 0 and values[left - 1] >= threshold:
        left -= 1
    while right + 1 < len(values) and values[right + 1] >= threshold:
        right += 1
    while (right - left) < max(0, int(min_zone_bins) - 1):
        if left > 0:
            left -= 1
        if right + 1 < len(values):
            right += 1
        if left == 0 and right + 1 >= len(values):
            break
    return left, right


def _expand_valley_zone(
    values: List[float],
    *,
    left_peak_idx: int,
    right_peak_idx: int,
    valley_idx: int,
    min_zone_bins: int,
) -> tuple[int, int]:
    valley_value = values[valley_idx]
    boundary_target = valley_value + (min(values[left_peak_idx], values[right_peak_idx]) - valley_value) * 0.35
    left = valley_idx
    right = valley_idx
    while left > left_peak_idx and values[left - 1] <= boundary_target:
        left -= 1
    while right < right_peak_idx and values[right + 1] <= boundary_target:
        right += 1
    while (right - left) < max(0, int(min_zone_bins) - 1):
        if left > left_peak_idx:
            left -= 1
        if right < right_peak_idx:
            right += 1
        if left <= left_peak_idx and right >= right_peak_idx:
            break
    return left, right


def _row_zone_payload(
    *,
    zone_type: str,
    zone_low: float,
    zone_high: float,
    peak_price: Optional[float],
    strength: float,
    bar_share: float,
    volume_share: float,
    source_day: str,
    valid_for_day: str,
    age_days: int,
) -> Dict[str, Any]:
    return {
        "source": "heatmap_d1",
        "trading_day": source_day,
        "valid_for_day": valid_for_day,
        "zone_type": zone_type,
        "zone_low": round(float(zone_low), 4),
        "zone_high": round(float(zone_high), 4),
        "zone_mid": round((float(zone_low) + float(zone_high)) / 2.0, 4),
        "peak_price": round(float(peak_price), 4) if peak_price is not None else None,
        "strength": round(max(0.0, min(1.0, float(strength))), 6),
        "cumulative_bar_share": round(float(bar_share), 8),
        "cumulative_volume_share": round(float(volume_share), 8),
        "age_days": int(max(0, age_days)),
        "is_broken": False,
        "touch_count_today": 0,
        "last_touch_ts": None,
        "confluence_points": 2 if str(zone_type).upper() == "LVN" else 1,
    }


def _build_day_payload(
    *,
    valid_for_day: str,
    source_day: str,
    source_rows: List[Dict[str, Any]],
    reference_price: float,
    max_distance_pct: float,
    hvn_percentile: float,
    lvn_percentile: float,
    min_peak_separation_bins: int,
    max_hvn_zones: int,
    max_lvn_zones: int,
    min_zone_bins: int,
) -> Optional[Dict[str, Any]]:
    price_min = float(reference_price) * (1.0 - max_distance_pct / 100.0)
    price_max = float(reference_price) * (1.0 + max_distance_pct / 100.0)
    scoped_rows = [
        row for row in source_rows
        if price_min <= _safe_float(row.get("price_bin"), 0.0) <= price_max
    ]
    if len(scoped_rows) < 5:
        scoped_rows = list(source_rows)
    if len(scoped_rows) < 5:
        return None

    scoped_rows = sorted(scoped_rows, key=lambda row: _safe_float(row.get("price_bin"), 0.0))
    prices = [_safe_float(row.get("price_bin"), 0.0) for row in scoped_rows]
    bar_shares = [_safe_float(row.get("cumulative_bar_share"), 0.0) for row in scoped_rows]
    volume_shares = [_safe_float(row.get("cumulative_volume_share"), 0.0) for row in scoped_rows]
    blended = [
        (bar_share + volume_share) / 2.0
        for bar_share, volume_share in zip(bar_shares, volume_shares)
    ]
    smoothed = _smooth(blended)
    max_strength = max(smoothed) if smoothed else 0.0
    if max_strength <= 0.0:
        return None

    source_dt = _parse_iso_day(source_day)
    valid_dt = _parse_iso_day(valid_for_day)
    age_days = 0
    if source_dt is not None and valid_dt is not None:
        age_days = max(0, (valid_dt.date() - source_dt.date()).days)

    peak_indices = _select_peak_indices(
        smoothed,
        min_peak_separation_bins=min_peak_separation_bins,
        hvn_percentile=hvn_percentile,
        max_hvn_zones=max_hvn_zones,
    )
    if not peak_indices:
        return None

    zones: List[Dict[str, Any]] = []
    for peak_idx in peak_indices:
        left_idx, right_idx = _expand_peak_zone(
            prices,
            smoothed,
            peak_idx,
            min_zone_bins=min_zone_bins,
        )
        zones.append(
            _row_zone_payload(
                zone_type="HVN",
                zone_low=prices[left_idx],
                zone_high=prices[right_idx],
                peak_price=prices[peak_idx],
                strength=smoothed[peak_idx] / max_strength,
                bar_share=bar_shares[peak_idx],
                volume_share=volume_shares[peak_idx],
                source_day=source_day,
                valid_for_day=valid_for_day,
                age_days=age_days,
            )
        )

    valley_threshold = _percentile(smoothed, lvn_percentile)
    lvn_zones: List[Dict[str, Any]] = []
    for left_peak_idx, right_peak_idx in zip(peak_indices, peak_indices[1:]):
        if right_peak_idx - left_peak_idx < 2:
            continue
        valley_candidates = range(left_peak_idx + 1, right_peak_idx)
        valley_idx = min(valley_candidates, key=lambda idx: smoothed[idx])
        if smoothed[valley_idx] > valley_threshold:
            continue
        left_idx, right_idx = _expand_valley_zone(
            smoothed,
            left_peak_idx=left_peak_idx,
            right_peak_idx=right_peak_idx,
            valley_idx=valley_idx,
            min_zone_bins=min_zone_bins,
        )
        lvn_zones.append(
            _row_zone_payload(
                zone_type="LVN",
                zone_low=prices[left_idx],
                zone_high=prices[right_idx],
                peak_price=prices[valley_idx],
                strength=1.0 - (smoothed[valley_idx] / max_strength),
                bar_share=bar_shares[valley_idx],
                volume_share=volume_shares[valley_idx],
                source_day=source_day,
                valid_for_day=valid_for_day,
                age_days=age_days,
            )
        )
    lvn_zones = sorted(lvn_zones, key=lambda item: float(item.get("strength", 0.0)), reverse=True)[:max_lvn_zones]

    zones.extend(lvn_zones)
    zones = sorted(zones, key=lambda item: float(item.get("zone_mid", 0.0)))
    return {
        "enabled": True,
        "valid_for_day": valid_for_day,
        "source_as_of_date": source_day,
        "reference_price": round(float(reference_price), 4),
        "max_distance_pct": float(max_distance_pct),
        "zone_count": len(zones),
        "zones": zones,
    }


def build_heatmap_memory_catalog(
    *,
    ticker: str,
    bars: Iterable[Any],
    state_store: Any,
    bin_size: float = DEFAULT_HEATMAP_BIN_SIZE,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_distance_pct: float = DEFAULT_MAX_DISTANCE_PCT,
    hvn_percentile: float = DEFAULT_HVN_PERCENTILE,
    lvn_percentile: float = DEFAULT_LVN_PERCENTILE,
    min_peak_separation_bins: int = DEFAULT_MIN_PEAK_SEPARATION_BINS,
    max_hvn_zones: int = DEFAULT_MAX_HVN_ZONES,
    max_lvn_zones: int = DEFAULT_MAX_LVN_ZONES,
    min_zone_bins: int = DEFAULT_MIN_ZONE_BINS,
) -> Optional[Dict[str, Any]]:
    list_rows = getattr(state_store, "list_daily_price_heatmap_rows", None)
    if not callable(list_rows):
        return None

    references_by_day = _extract_reference_prices_by_day(bars)
    if not references_by_day:
        return None

    ordered_days = sorted(references_by_day.keys())
    start_dt = _parse_iso_day(ordered_days[0])
    end_dt = _parse_iso_day(ordered_days[-1])
    if start_dt is None or end_dt is None:
        return None

    lookup_rows = list_rows(
        ticker=str(ticker or "").strip().upper(),
        date_from=(start_dt - timedelta(days=max(1, int(lookback_days)))).strftime("%Y-%m-%d"),
        date_to=(end_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
        bin_size=float(bin_size),
    )
    if not lookup_rows:
        return None

    rows_by_day: Dict[str, List[Dict[str, Any]]] = {}
    for row in lookup_rows:
        as_of_date = str(row.get("as_of_date") or "").strip()
        if not as_of_date:
            continue
        rows_by_day.setdefault(as_of_date, []).append(dict(row))

    if not rows_by_day:
        return None

    available_days = sorted(rows_by_day.keys())
    catalog_days: Dict[str, Dict[str, Any]] = {}
    for valid_for_day in ordered_days:
        reference_price = references_by_day.get(valid_for_day)
        if reference_price is None or reference_price <= 0.0:
            continue
        source_day = next(
            (day for day in reversed(available_days) if day < valid_for_day),
            None,
        )
        if source_day is None:
            continue
        day_payload = _build_day_payload(
            valid_for_day=valid_for_day,
            source_day=source_day,
            source_rows=rows_by_day.get(source_day, []),
            reference_price=reference_price,
            max_distance_pct=max_distance_pct,
            hvn_percentile=hvn_percentile,
            lvn_percentile=lvn_percentile,
            min_peak_separation_bins=min_peak_separation_bins,
            max_hvn_zones=max_hvn_zones,
            max_lvn_zones=max_lvn_zones,
            min_zone_bins=min_zone_bins,
        )
        if day_payload is None:
            continue
        catalog_days[valid_for_day] = day_payload

    if not catalog_days:
        return None

    return {
        "enabled": True,
        "ticker": str(ticker or "").strip().upper(),
        "bin_size": float(bin_size),
        "days": catalog_days,
        "summary": {
            "catalog_days": len(ordered_days),
            "populated_days": len(catalog_days),
            "first_day": ordered_days[0],
            "last_day": ordered_days[-1],
            "max_distance_pct": float(max_distance_pct),
            "lookback_days": int(max(1, lookback_days)),
            "max_hvn_zones": int(max_hvn_zones),
            "max_lvn_zones": int(max_lvn_zones),
        },
    }


__all__ = [
    "build_heatmap_memory_catalog",
]
