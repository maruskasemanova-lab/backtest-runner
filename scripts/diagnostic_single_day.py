#!/usr/bin/env python3
"""
FE-synchronized diagnostic + recursive pattern miner for intraday levels study.

Main goals:
1) Run through FE-equivalent endpoints (/api/run/start + /play + /state + /summary + /bars + /markers).
2) Produce richer logs in a readable structure (JSON + Markdown).
3) Mine time/price/volume/POC relationships, including non-return levels.
4) Support recursive loops: run -> analyze -> derive rule hints -> adjust small overrides -> rerun.
5) Persist abstract knowledge snippets for future rule design.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple
from urllib import error as urlerror
from urllib import request as urlrequest


SMART_MONEY_BASE_PARAMS: Dict[str, Any] = {
    # Core run / execution setup
    "include_extended_hours": False,
    "apply_aos_optimizations_on_start": True,
    "apply_positioning_config_on_start": True,
    "cold_start_each_day": True,
    "comparable_mode": True,
    "start_mode": "day_isolated_audit",
    "strategy_selection_mode": "all_enabled",
    "max_active_strategies": 3,
    "l2_only": False,
    "l2_confirm_enabled": False,
    # Positioning / risk baseline
    "account_size_usd": 10000,
    "risk_per_trade_pct": 0.6,
    "max_position_notional_pct": 25.0,
    "max_fill_participation_rate": 0.10,
    "min_fill_ratio": 0.50,
    "trailing_activation_pct": 0.20,
    "trailing_stop_pct": 0.80,
    "break_even_buffer_pct": 0.03,
    "break_even_min_hold_bars": 3,
    "trailing_enabled_in_choppy": True,
    "time_exit_bars": 20,
    "adverse_flow_exit_enabled": True,
    "adverse_flow_threshold": 0.12,
    "adverse_flow_min_hold_bars": 3,
    "global_exit_rr_ratio": 2.0,
    "global_risk_atr_stop_multiplier": 1.0,
    "global_risk_volume_stop_pct": 1.0,
    "global_risk_min_stop_loss_pct": 0.15,
    "stop_loss_mode": "strategy",
    "fixed_stop_loss_pct": 0.0,
    # Intraday Levels Tracker baseline
    "intraday_levels_enabled": True,
    "intraday_levels_swing_left_bars": 2,
    "intraday_levels_swing_right_bars": 2,
    "intraday_levels_test_tolerance_pct": 0.08,
    "intraday_levels_break_tolerance_pct": 0.05,
    "intraday_levels_breakout_volume_lookback": 20,
    "intraday_levels_breakout_volume_multiplier": 1.2,
    "intraday_levels_volume_profile_bin_size_pct": 0.05,
    "intraday_levels_value_area_pct": 0.7,
    "intraday_levels_entry_quality_enabled": True,
    "intraday_levels_min_levels_for_context": 1,
    "intraday_levels_entry_tolerance_pct": 0.10,
    "intraday_levels_break_cooldown_bars": 3,
    "intraday_levels_rotation_max_tests": 2,
    "intraday_levels_rotation_volume_max_ratio": 0.95,
    "intraday_levels_recent_bounce_lookback_bars": 6,
    "intraday_levels_require_recent_bounce_for_mean_reversion": True,
    "intraday_levels_momentum_break_max_age_bars": 3,
    "intraday_levels_momentum_min_room_pct": 0.15,
    "intraday_levels_momentum_min_broken_ratio": 0.30,
    "intraday_levels_min_confluence_score": 1,
    "intraday_levels_memory_enabled": True,
    "intraday_levels_memory_min_tests": 2,
    "intraday_levels_memory_max_age_days": 5,
    "intraday_levels_memory_decay_after_days": 2,
    "intraday_levels_memory_decay_weight": 0.5,
    "intraday_levels_memory_max_levels": 12,
    "intraday_levels_opening_range_enabled": True,
    "intraday_levels_opening_range_minutes": 30,
    "intraday_levels_opening_range_break_tolerance_pct": 0.05,
    "intraday_levels_poc_migration_enabled": True,
    "intraday_levels_poc_migration_interval_bars": 30,
    "intraday_levels_poc_migration_trend_threshold_pct": 0.2,
    "intraday_levels_poc_migration_range_threshold_pct": 0.1,
    "intraday_levels_composite_profile_enabled": True,
    "intraday_levels_composite_profile_days": 3,
    "intraday_levels_composite_profile_current_day_weight": 1.0,
    "intraday_levels_spike_detection_enabled": True,
    "intraday_levels_spike_min_wick_ratio": 0.6,
    "intraday_levels_prior_day_anchors_enabled": True,
    "intraday_levels_gap_analysis_enabled": True,
    "intraday_levels_gap_min_pct": 0.3,
    "intraday_levels_gap_momentum_threshold_pct": 2.0,
    "intraday_levels_rvol_filter_enabled": True,
    "intraday_levels_rvol_lookback_bars": 20,
    "intraday_levels_rvol_min_threshold": 0.8,
    "intraday_levels_rvol_strong_threshold": 1.5,
    "intraday_levels_adaptive_window_enabled": True,
    "intraday_levels_adaptive_window_min_bars": 6,
    "intraday_levels_adaptive_window_rvol_threshold": 0.5,
    "intraday_levels_adaptive_window_atr_ratio_max": 1.5,
    "intraday_levels_micro_confirmation_enabled": True,
    "intraday_levels_micro_confirmation_bars": 2,
    "intraday_levels_confluence_sizing_enabled": True,
    # Context-aware risk
    "context_aware_risk_enabled": True,
    "context_risk_sl_buffer_pct": 0.10,
    "context_risk_min_room_pct": 0.08,
    "context_risk_min_effective_rr": 0.5,
    "context_risk_trailing_tighten_zone": 0.2,
    "context_risk_trailing_tighten_factor": 0.5,
    "context_risk_max_anchor_search_pct": 2.5,
    "context_risk_min_level_tests_for_sl": 1,
}


FORCE_TRADE_OVERRIDES: Dict[str, Any] = {
    # Intentional aggressive setup for pattern mining coverage.
    "include_extended_hours": True,
    "strategy_selection_mode": "all_enabled",
    "max_active_strategies": 8,
    "apply_positioning_config_on_start": False,
    "risk_per_trade_pct": 0.35,
    "max_position_notional_pct": 40.0,
    "max_fill_participation_rate": 0.25,
    "min_fill_ratio": 0.20,
    "trailing_activation_pct": 0.03,
    "trailing_stop_pct": 0.22,
    "break_even_buffer_pct": 0.0,
    "break_even_min_hold_bars": 1,
    "time_exit_bars": 2,
    "adverse_flow_exit_enabled": False,
    "global_exit_rr_ratio": 1.1,
    "global_risk_min_stop_loss_pct": 0.05,
    "intraday_levels_entry_tolerance_pct": 0.25,
    "intraday_levels_break_cooldown_bars": 1,
    "intraday_levels_rotation_max_tests": 7,
    "intraday_levels_rotation_volume_max_ratio": 2.0,
    "intraday_levels_recent_bounce_lookback_bars": 2,
    "intraday_levels_require_recent_bounce_for_mean_reversion": False,
    "intraday_levels_momentum_break_max_age_bars": 8,
    "intraday_levels_momentum_min_room_pct": 0.02,
    "intraday_levels_momentum_min_broken_ratio": 0.05,
    "intraday_levels_min_confluence_score": 1,
    "intraday_levels_micro_confirmation_enabled": False,
    "intraday_levels_rvol_filter_enabled": False,
    "intraday_levels_adaptive_window_enabled": False,
    "intraday_levels_confluence_sizing_enabled": False,
    "context_aware_risk_enabled": False,
}


FORCE_TRADE_SWEEP_VARIANTS: List[Dict[str, Any]] = [
    {
        "variant_name": "burst_base",
    },
    {
        "variant_name": "burst_t2",
        "time_exit_bars": 2,
        "trailing_activation_pct": 0.03,
        "trailing_stop_pct": 0.22,
        "intraday_levels_entry_tolerance_pct": 0.25,
    },
    {
        "variant_name": "burst_t3",
        "time_exit_bars": 3,
        "trailing_activation_pct": 0.04,
        "trailing_stop_pct": 0.28,
        "intraday_levels_entry_tolerance_pct": 0.20,
    },
    {
        "variant_name": "burst_t4",
        "time_exit_bars": 4,
        "trailing_activation_pct": 0.05,
        "trailing_stop_pct": 0.30,
        "intraday_levels_entry_tolerance_pct": 0.18,
    },
]


DEFAULT_KNOWLEDGE_PATH = Path("reports") / "pattern_logs" / "knowledge_base.jsonl"

# Keep aligned with src/aos_config.py POSITIONING_CONFIG_KEYS so profile split
# routes execution fields to /api/positioning-config/update.
POSITIONING_PROFILE_KEYS: Set[str] = {
    "risk_per_trade_pct",
    "max_position_notional_pct",
    "max_fill_participation_rate",
    "min_fill_ratio",
    "enable_partial_take_profit",
    "partial_take_profit_rr",
    "partial_take_profit_fraction",
    "trailing_stop_pct",
    "global_exit_rr_ratio",
    "global_risk_atr_stop_multiplier",
    "global_risk_volume_stop_pct",
    "global_risk_min_stop_loss_pct",
    "trailing_activation_pct",
    "break_even_buffer_pct",
    "break_even_min_hold_bars",
    "trailing_enabled_in_choppy",
    "time_exit_bars",
    "adverse_flow_exit_enabled",
    "adverse_flow_threshold",
    "adverse_flow_min_hold_bars",
    "adverse_flow_consistency_threshold",
    "adverse_book_pressure_threshold",
    "stop_loss_mode",
    "fixed_stop_loss_pct",
}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rand_suffix(size: int = 5) -> str:
    return "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=size))


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_mean(values: Iterable[float]) -> Optional[float]:
    vals = [float(v) for v in values if isinstance(v, (int, float))]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _quantile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    q = _clamp(float(q), 0.0, 1.0)
    sorted_vals = sorted(float(v) for v in values)
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    ratio = pos - lo
    return sorted_vals[lo] * (1.0 - ratio) + sorted_vals[hi] * ratio


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    x_mean = _safe_mean(xs)
    y_mean = _safe_mean(ys)
    if x_mean is None or y_mean is None:
        return None

    cov = 0.0
    x_var = 0.0
    y_var = 0.0
    for x, y in zip(xs, ys):
        dx = x - x_mean
        dy = y - y_mean
        cov += dx * dy
        x_var += dx * dx
        y_var += dy * dy

    if x_var <= 0.0 or y_var <= 0.0:
        return None
    return cov / math.sqrt(x_var * y_var)


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_run_key(run_key: str) -> Tuple[str, str, str]:
    parts = str(run_key or "").split(":")
    if len(parts) < 3:
        raise ValueError(f"Invalid run_key: {run_key}")
    return ":".join(parts[:-2]), parts[-2], parts[-1]


def _http_json(
    method: str,
    api_base: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    url = f"{api_base.rstrip('/')}{path}"
    data = None
    headers: Dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"_raw": parsed}
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {body[:400]}") from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"{method} {path} -> connection error: {exc}") from exc


def _http_json_list(
    method: str,
    api_base: str,
    path: str,
    timeout: float = 60.0,
) -> List[Dict[str, Any]]:
    url = f"{api_base.rstrip('/')}{path}"
    req = urlrequest.Request(url, method=method.upper())
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        parsed = json.loads(raw) if raw else []
        if isinstance(parsed, list):
            return [row for row in parsed if isinstance(row, dict)]
        return []


def _auto_cast(raw_value: str) -> Any:
    token = str(raw_value).strip()
    lowered = token.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"none", "null"}:
        return None
    maybe_num = token.replace(",", ".")
    try:
        if "." in maybe_num:
            return float(maybe_num)
        return int(maybe_num)
    except ValueError:
        return token


def _parse_overrides(param_tokens: Optional[List[str]]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for raw in param_tokens or []:
        token = str(raw).strip()
        if not token:
            continue
        if "=" not in token:
            print(f"[warn] Ignoring invalid override (missing '='): {token}")
            continue
        key, value = token.split("=", 1)
        key = key.strip()
        if not key:
            continue
        overrides[key] = _auto_cast(value)
    return overrides


def _build_payload(
    *,
    ticker: str,
    date: str,
    date_from: str,
    date_to: str,
    strategy_api_url: str,
    base_params: Dict[str, Any],
    overrides: Dict[str, Any],
    run_tag: str,
) -> Dict[str, Any]:
    run_id = f"{run_tag}-{int(time.time())}-{_rand_suffix()}"
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "ticker": ticker.upper(),
        "date": date,
        "date_from": date_from,
        "date_to": date_to,
        "strategy_api_url": strategy_api_url,
    }
    merged = dict(base_params)
    merged.update(overrides)
    payload.update(merged)
    return payload


def _apply_unified_profile(
    *,
    api_base: str,
    ticker: str,
    profile_id: str,
    strategy_api_url: str,
) -> Dict[str, Any]:
    payload = {
        "ticker": ticker.upper(),
        "profile_id": profile_id,
        "strategy_api_url": strategy_api_url,
        "apply_now": True,
        "apply_execution": True,
    }
    return _http_json(
        "POST", api_base, "/api/profiles/apply", payload=payload, timeout=180
    )


def _start_play_collect(
    *,
    api_base: str,
    run_payload: Dict[str, Any],
    poll_sec: float,
    timeout_sec: float,
) -> Dict[str, Any]:
    start_res = _http_json(
        "POST", api_base, "/api/run/start", payload=run_payload, timeout=240
    )
    run_key = str(start_res.get("run_key") or "").strip()
    run_id, ticker, date_label = _parse_run_key(run_key)
    base = f"/api/run/{run_id}/{ticker}/{date_label}"

    _http_json(
        "POST", api_base, f"{base}/play", payload={"speed_ms": "max"}, timeout=60
    )

    deadline = time.time() + max(30.0, timeout_sec)
    last_state: Dict[str, Any] = {}
    while True:
        last_state = _http_json("GET", api_base, f"{base}/state", timeout=60)
        phase = str(last_state.get("phase") or "").upper()
        current_idx = _to_int(last_state.get("current_bar_index"), 0)
        total_bars = _to_int(last_state.get("total_bars"), 0)
        is_running = bool(last_state.get("is_running"))

        finished = phase == "END_OF_DAY" or (
            not is_running and total_bars > 0 and current_idx >= total_bars
        )
        if finished:
            break
        if phase == "ERROR":
            break
        if time.time() > deadline:
            raise TimeoutError(f"Run timed out. state={last_state}")
        time.sleep(max(0.05, poll_sec))

    summary = _http_json("GET", api_base, f"{base}/summary", timeout=120)
    bars_payload = _http_json("GET", api_base, f"{base}/bars", timeout=120)
    markers = _http_json_list("GET", api_base, f"{base}/markers", timeout=120)

    return {
        "run_key": run_key,
        "run_id": run_id,
        "ticker": ticker,
        "date_label": date_label,
        "start_response": start_res,
        "state": last_state,
        "summary": summary,
        "bars_payload": bars_payload,
        "markers": markers,
    }


def _normalize_bars(raw_bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    prev_close: Optional[float] = None

    for idx, bar in enumerate(raw_bars):
        ts = _parse_ts(bar.get("timestamp"))
        if ts is None:
            continue

        close = _to_float(bar.get("close"), 0.0)
        if close <= 0.0:
            continue
        open_px = _to_float(bar.get("open"), close)
        high = _to_float(bar.get("high"), close)
        low = _to_float(bar.get("low"), close)
        volume = max(0.0, _to_float(bar.get("volume"), 0.0))
        vwap_raw = _to_float(bar.get("vwap"), close)
        vwap = vwap_raw if vwap_raw > 0 else close

        range_pct = ((high - low) / close) * 100.0 if close > 0 else 0.0
        body_pct = (abs(close - open_px) / max(1e-9, open_px)) * 100.0
        close_ret_pct = 0.0
        if prev_close and prev_close > 0:
            close_ret_pct = ((close - prev_close) / prev_close) * 100.0
        vwap_dev_pct = ((close - vwap) / vwap) * 100.0 if vwap > 0 else 0.0

        normalized.append(
            {
                "idx": idx,
                "timestamp": ts,
                "open": open_px,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "vwap": vwap,
                "range_pct": range_pct,
                "body_pct": body_pct,
                "close_ret_pct": close_ret_pct,
                "vwap_dev_pct": vwap_dev_pct,
                "next_close_ret_pct": None,
            }
        )
        prev_close = close

    for i in range(len(normalized) - 1):
        cur = normalized[i]
        nxt = normalized[i + 1]
        cur_close = _to_float(cur.get("close"), 0.0)
        nxt_close = _to_float(nxt.get("close"), 0.0)
        if cur_close > 0 and nxt_close > 0:
            cur["next_close_ret_pct"] = ((nxt_close - cur_close) / cur_close) * 100.0
        else:
            cur["next_close_ret_pct"] = None

    return normalized


def _build_time_buckets(
    bars: List[Dict[str, Any]], bucket_minutes: int
) -> List[Dict[str, Any]]:
    bucket_size = max(1, int(bucket_minutes))
    by_bucket: Dict[Tuple[datetime, datetime], Dict[str, Any]] = {}

    for bar in bars:
        ts: datetime = bar["timestamp"]
        minute_floor = (ts.minute // bucket_size) * bucket_size
        start = ts.replace(minute=minute_floor, second=0, microsecond=0)
        end = start + timedelta(minutes=bucket_size)
        key = (start, end)

        row = by_bucket.get(key)
        if row is None:
            row = {
                "start": start,
                "end": end,
                "volume": 0.0,
                "vwap_num": 0.0,
                "bar_count": 0,
                "high": -math.inf,
                "low": math.inf,
                "first_idx": bar["idx"],
                "last_idx": bar["idx"],
                "abs_return_sum": 0.0,
                "range_sum": 0.0,
            }
            by_bucket[key] = row

        vol = bar["volume"]
        price = bar["vwap"] if bar["vwap"] > 0 else bar["close"]
        row["volume"] += vol
        row["vwap_num"] += price * vol
        row["bar_count"] += 1
        row["high"] = max(row["high"], bar["high"])
        row["low"] = min(row["low"], bar["low"])
        row["last_idx"] = bar["idx"]
        row["abs_return_sum"] += abs(_to_float(bar.get("close_ret_pct"), 0.0))
        row["range_sum"] += _to_float(bar.get("range_pct"), 0.0)

    buckets: List[Dict[str, Any]] = []
    for row in by_bucket.values():
        vol = row["volume"]
        bar_count = max(1, _to_int(row.get("bar_count"), 0))
        row["vwap"] = row["vwap_num"] / vol if vol > 0 else 0.0
        row["tod_label"] = row["start"].strftime("%H:%M")
        row["avg_abs_return_pct"] = row["abs_return_sum"] / bar_count
        row["avg_range_pct"] = row["range_sum"] / bar_count
        row.pop("vwap_num", None)
        row.pop("abs_return_sum", None)
        row.pop("range_sum", None)
        buckets.append(row)
    buckets.sort(key=lambda item: item["start"])
    return buckets


def _top_time_interval_revisits(
    bars: List[Dict[str, Any]],
    buckets: List[Dict[str, Any]],
    *,
    top_n: int,
    revisit_tolerance_pct: float,
) -> List[Dict[str, Any]]:
    if not bars:
        return []
    top = sorted(buckets, key=lambda item: item["volume"], reverse=True)[
        : max(1, int(top_n))
    ]
    out: List[Dict[str, Any]] = []
    tol_pct = max(0.01, float(revisit_tolerance_pct))

    for rank, bucket in enumerate(top, start=1):
        center = _to_float(bucket.get("vwap"), 0.0)
        if center <= 0:
            continue
        width = center * (tol_pct / 100.0)
        zone_low = center - width
        zone_high = center + width

        first_idx: Optional[int] = None
        revisit_count = 0
        max_up = 0.0
        max_down = 0.0
        for bar in bars[int(bucket["last_idx"]) + 1 :]:
            if bar["low"] <= zone_high and bar["high"] >= zone_low:
                revisit_count += 1
                if first_idx is None:
                    first_idx = int(bar["idx"])

            max_up = max(max_up, ((bar["high"] - center) / center) * 100.0)
            max_down = max(max_down, ((center - bar["low"]) / center) * 100.0)

        first_revisit_ts = (
            bars[first_idx]["timestamp"].isoformat() if first_idx is not None else None
        )
        bars_until = (
            first_idx - int(bucket["last_idx"]) if first_idx is not None else None
        )

        out.append(
            {
                "rank": rank,
                "interval_start": bucket["start"].isoformat(),
                "interval_end": bucket["end"].isoformat(),
                "tod_label": bucket["tod_label"],
                "volume": round(_to_float(bucket["volume"]), 2),
                "vwap": round(center, 4),
                "zone_low": round(zone_low, 4),
                "zone_high": round(zone_high, 4),
                "avg_abs_return_pct": round(
                    _to_float(bucket.get("avg_abs_return_pct"), 0.0), 4
                ),
                "avg_range_pct": round(_to_float(bucket.get("avg_range_pct"), 0.0), 4),
                "revisit_count_after_interval": revisit_count,
                "first_revisit_timestamp": first_revisit_ts,
                "bars_until_first_revisit": bars_until,
                "max_up_move_after_interval_pct": round(max_up, 4),
                "max_down_move_after_interval_pct": round(max_down, 4),
            }
        )
    return out


def _top_recurring_volume_windows(
    buckets: List[Dict[str, Any]], top_n: int
) -> List[Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = {}
    for bucket in buckets:
        key = str(bucket.get("tod_label") or "")
        if not key:
            continue
        row = agg.get(key)
        if row is None:
            row = {
                "tod_label": key,
                "total_volume": 0.0,
                "occurrences": 0,
                "abs_return_sum": 0.0,
                "range_sum": 0.0,
            }
            agg[key] = row
        row["total_volume"] += _to_float(bucket.get("volume"), 0.0)
        row["occurrences"] += 1
        row["abs_return_sum"] += _to_float(bucket.get("avg_abs_return_pct"), 0.0)
        row["range_sum"] += _to_float(bucket.get("avg_range_pct"), 0.0)

    rows = list(agg.values())
    rows.sort(key=lambda item: item["total_volume"], reverse=True)
    out: List[Dict[str, Any]] = []
    for item in rows[: max(1, int(top_n))]:
        occ = max(1, _to_int(item.get("occurrences"), 0))
        out.append(
            {
                "tod_label": item["tod_label"],
                "total_volume": round(item["total_volume"], 2),
                "occurrences": occ,
                "avg_volume_per_occurrence": round(item["total_volume"] / occ, 2),
                "avg_abs_return_pct": round(item["abs_return_sum"] / occ, 4),
                "avg_range_pct": round(item["range_sum"] / occ, 4),
            }
        )
    return out


def _build_price_nodes(
    bars: List[Dict[str, Any]],
    *,
    bin_size_pct: float,
) -> Tuple[List[Dict[str, Any]], float]:
    closes = [bar["close"] for bar in bars if bar["close"] > 0]
    if not closes:
        return [], 0.01

    median_price = statistics.median(closes)
    abs_bin = max(0.01, median_price * max(0.01, float(bin_size_pct)) / 100.0)
    nodes: Dict[int, Dict[str, Any]] = {}

    for bar in bars:
        price = bar["close"] if bar["close"] > 0 else (bar["vwap"] or 0.0)
        if price <= 0:
            continue
        node_idx = int(round(price / abs_bin))
        row = nodes.get(node_idx)
        if row is None:
            center = node_idx * abs_bin
            row = {
                "node_idx": node_idx,
                "center": center,
                "low": center - abs_bin / 2.0,
                "high": center + abs_bin / 2.0,
                "volume": 0.0,
                "first_idx": bar["idx"],
                "last_idx": bar["idx"],
                "touches": 0,
            }
            nodes[node_idx] = row
        row["volume"] += bar["volume"]
        row["last_idx"] = bar["idx"]
        row["touches"] += 1

    sorted_nodes = sorted(nodes.values(), key=lambda item: item["volume"], reverse=True)
    return sorted_nodes, abs_bin


def _top_price_volume_nodes(
    bars: List[Dict[str, Any]],
    *,
    bin_size_pct: float,
    top_n: int,
) -> List[Dict[str, Any]]:
    nodes, _ = _build_price_nodes(bars, bin_size_pct=bin_size_pct)
    top = nodes[: max(1, int(top_n))]

    out: List[Dict[str, Any]] = []
    for rank, node in enumerate(top, start=1):
        revisit_count = 0
        first_revisit_idx: Optional[int] = None
        for bar in bars[int(node["first_idx"]) + 1 :]:
            if bar["low"] <= node["high"] and bar["high"] >= node["low"]:
                revisit_count += 1
                if first_revisit_idx is None:
                    first_revisit_idx = int(bar["idx"])

        first_revisit_ts = (
            bars[first_revisit_idx]["timestamp"].isoformat()
            if first_revisit_idx is not None
            else None
        )
        out.append(
            {
                "rank": rank,
                "price_low": round(_to_float(node["low"]), 4),
                "price_high": round(_to_float(node["high"]), 4),
                "center": round(_to_float(node["center"]), 4),
                "volume": round(_to_float(node["volume"]), 2),
                "touches": _to_int(node.get("touches"), 0),
                "revisit_count_after_first_touch": revisit_count,
                "first_revisit_timestamp": first_revisit_ts,
            }
        )
    return out


def _volume_price_relationships(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not bars:
        return {
            "correlations": {},
            "high_volume_group": {},
            "low_volume_group": {},
            "volume_thresholds": {},
        }

    volumes = [_to_float(bar.get("volume"), 0.0) for bar in bars]
    ranges = [_to_float(bar.get("range_pct"), 0.0) for bar in bars]
    bodies = [_to_float(bar.get("body_pct"), 0.0) for bar in bars]
    abs_next_returns = [
        abs(_to_float(bar.get("next_close_ret_pct"), 0.0))
        for bar in bars
        if bar.get("next_close_ret_pct") is not None
    ]
    vols_for_next_returns = [
        _to_float(bar.get("volume"), 0.0)
        for bar in bars
        if bar.get("next_close_ret_pct") is not None
    ]

    vol_q25 = _quantile(volumes, 0.25)
    vol_q75 = _quantile(volumes, 0.75)

    high_group = [
        bar for bar in bars if vol_q75 is not None and bar["volume"] >= vol_q75
    ]
    low_group = [
        bar for bar in bars if vol_q25 is not None and bar["volume"] <= vol_q25
    ]

    def _group_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        next_abs = [
            abs(_to_float(row.get("next_close_ret_pct"), 0.0))
            for row in rows
            if row.get("next_close_ret_pct") is not None
        ]
        return {
            "bars": len(rows),
            "avg_volume": round(
                _to_float(
                    _safe_mean([_to_float(r.get("volume"), 0.0) for r in rows]), 0.0
                ),
                2,
            ),
            "avg_range_pct": round(
                _to_float(
                    _safe_mean([_to_float(r.get("range_pct"), 0.0) for r in rows]), 0.0
                ),
                4,
            ),
            "avg_body_pct": round(
                _to_float(
                    _safe_mean([_to_float(r.get("body_pct"), 0.0) for r in rows]), 0.0
                ),
                4,
            ),
            "avg_abs_next_ret_pct": round(_to_float(_safe_mean(next_abs), 0.0), 4),
        }

    corrs = {
        "vol_vs_range_pct": _pearson(volumes, ranges),
        "vol_vs_body_pct": _pearson(volumes, bodies),
        "vol_vs_next_abs_ret_pct": _pearson(vols_for_next_returns, abs_next_returns),
    }

    return {
        "correlations": {
            key: (round(val, 6) if isinstance(val, (int, float)) else None)
            for key, val in corrs.items()
        },
        "volume_thresholds": {
            "q25": round(_to_float(vol_q25, 0.0), 2) if vol_q25 is not None else None,
            "q75": round(_to_float(vol_q75, 0.0), 2) if vol_q75 is not None else None,
        },
        "high_volume_group": _group_stats(high_group),
        "low_volume_group": _group_stats(low_group),
    }


def _hourly_price_action_volume(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_hour: Dict[int, Dict[str, Any]] = defaultdict(
        lambda: {
            "bars": 0,
            "volume": 0.0,
            "range_sum": 0.0,
            "body_sum": 0.0,
            "abs_ret_sum": 0.0,
            "vwap_dev_abs_sum": 0.0,
        }
    )

    for bar in bars:
        hour = (
            _parse_ts(bar.get("timestamp")).hour
            if _parse_ts(bar.get("timestamp"))
            else bar["timestamp"].hour
        )
        row = by_hour[hour]
        row["bars"] += 1
        row["volume"] += _to_float(bar.get("volume"), 0.0)
        row["range_sum"] += _to_float(bar.get("range_pct"), 0.0)
        row["body_sum"] += _to_float(bar.get("body_pct"), 0.0)
        row["abs_ret_sum"] += abs(_to_float(bar.get("close_ret_pct"), 0.0))
        row["vwap_dev_abs_sum"] += abs(_to_float(bar.get("vwap_dev_pct"), 0.0))

    rows: List[Dict[str, Any]] = []
    for hour in sorted(by_hour.keys()):
        row = by_hour[hour]
        bars_count = max(1, _to_int(row.get("bars"), 0))
        rows.append(
            {
                "hour_utc": hour,
                "bars": bars_count,
                "total_volume": round(_to_float(row.get("volume"), 0.0), 2),
                "avg_volume": round(_to_float(row.get("volume"), 0.0) / bars_count, 2),
                "avg_range_pct": round(
                    _to_float(row.get("range_sum"), 0.0) / bars_count, 4
                ),
                "avg_body_pct": round(
                    _to_float(row.get("body_sum"), 0.0) / bars_count, 4
                ),
                "avg_abs_return_pct": round(
                    _to_float(row.get("abs_ret_sum"), 0.0) / bars_count, 4
                ),
                "avg_abs_vwap_dev_pct": round(
                    _to_float(row.get("vwap_dev_abs_sum"), 0.0) / bars_count, 4
                ),
            }
        )

    top_volume = sorted(rows, key=lambda item: item["total_volume"], reverse=True)[:5]
    top_move = sorted(rows, key=lambda item: item["avg_abs_return_pct"], reverse=True)[
        :5
    ]
    return {
        "by_hour_utc": rows,
        "top_hours_by_volume": top_volume,
        "top_hours_by_abs_move": top_move,
    }


def _non_returning_price_zones(
    bars: List[Dict[str, Any]],
    *,
    tolerance_pct: float,
    lookahead_bars: int,
    min_move_pct: float,
    top_n: int,
    anchor_volume_quantile: float,
) -> Dict[str, Any]:
    if not bars or len(bars) < 8:
        return {
            "candidate_count": 0,
            "non_return_count": 0,
            "non_return_ratio": 0.0,
            "non_return_by_hour_utc": [],
            "top_non_return_zones": [],
            "top_returned_zones": [],
        }

    lookahead = max(1, int(lookahead_bars))
    tol_pct = max(0.01, float(tolerance_pct))
    min_move = max(0.0, float(min_move_pct))

    vols = [_to_float(bar.get("volume"), 0.0) for bar in bars]
    vol_threshold = _quantile(vols, _clamp(anchor_volume_quantile, 0.0, 1.0))
    if vol_threshold is None:
        vol_threshold = 0.0

    candidates: List[Dict[str, Any]] = []
    hour_stats: Dict[int, Dict[str, int]] = defaultdict(
        lambda: {"candidates": 0, "non_return": 0}
    )

    for bar in bars:
        idx = _to_int(bar.get("idx"), 0)
        if idx + lookahead >= len(bars):
            continue
        if _to_float(bar.get("volume"), 0.0) < vol_threshold:
            continue

        center = _to_float(bar.get("vwap"), _to_float(bar.get("close"), 0.0))
        if center <= 0:
            continue
        zone_half = center * (tol_pct / 100.0)
        zone_low = center - zone_half
        zone_high = center + zone_half

        future = bars[idx + lookahead :]
        first_return_idx: Optional[int] = None
        max_up = 0.0
        max_down = 0.0
        for nxt in future:
            max_up = max(max_up, ((nxt["high"] - center) / center) * 100.0)
            max_down = max(max_down, ((center - nxt["low"]) / center) * 100.0)
            if (
                first_return_idx is None
                and nxt["low"] <= zone_high
                and nxt["high"] >= zone_low
            ):
                first_return_idx = _to_int(nxt.get("idx"), 0)

        dominant_move = max(max_up, max_down)
        if dominant_move < min_move:
            continue

        ts: datetime = bar["timestamp"]
        hour_stats[ts.hour]["candidates"] += 1
        is_non_return = first_return_idx is None
        if is_non_return:
            hour_stats[ts.hour]["non_return"] += 1

        candidates.append(
            {
                "anchor_idx": idx,
                "anchor_timestamp": ts.isoformat(),
                "anchor_tod": ts.strftime("%H:%M"),
                "anchor_price": round(center, 4),
                "zone_low": round(zone_low, 4),
                "zone_high": round(zone_high, 4),
                "anchor_volume": round(_to_float(bar.get("volume"), 0.0), 2),
                "max_up_move_pct": round(max_up, 4),
                "max_down_move_pct": round(max_down, 4),
                "dominant_direction": "up" if max_up >= max_down else "down",
                "dominant_move_pct": round(dominant_move, 4),
                "is_non_return": is_non_return,
                "first_return_timestamp": (
                    bars[first_return_idx]["timestamp"].isoformat()
                    if first_return_idx is not None
                    else None
                ),
                "bars_to_first_return": (
                    first_return_idx - idx if first_return_idx is not None else None
                ),
            }
        )

    non_return = [row for row in candidates if row["is_non_return"]]
    returned = [row for row in candidates if not row["is_non_return"]]

    non_return_sorted = sorted(
        non_return,
        key=lambda item: (item["anchor_volume"], item["dominant_move_pct"]),
        reverse=True,
    )[: max(1, int(top_n))]
    returned_sorted = sorted(
        returned,
        key=lambda item: (item["anchor_volume"], item["dominant_move_pct"]),
        reverse=True,
    )[: max(1, int(top_n))]

    by_hour_rows = []
    for hour in sorted(hour_stats.keys()):
        row = hour_stats[hour]
        cands = max(1, _to_int(row.get("candidates"), 0))
        by_hour_rows.append(
            {
                "hour_utc": hour,
                "candidates": cands,
                "non_return_count": _to_int(row.get("non_return"), 0),
                "non_return_ratio": round(_to_int(row.get("non_return"), 0) / cands, 4),
            }
        )

    total_candidates = len(candidates)
    total_non_return = len(non_return)
    ratio = (total_non_return / total_candidates) if total_candidates > 0 else 0.0

    return {
        "candidate_count": total_candidates,
        "non_return_count": total_non_return,
        "non_return_ratio": round(ratio, 4),
        "non_return_by_hour_utc": by_hour_rows,
        "top_non_return_zones": non_return_sorted,
        "top_returned_zones": returned_sorted,
        "settings": {
            "tolerance_pct": tol_pct,
            "lookahead_bars": lookahead,
            "min_move_pct": min_move,
            "anchor_volume_quantile": anchor_volume_quantile,
        },
    }


def _poc_magnet_and_migration(
    bars: List[Dict[str, Any]],
    *,
    bin_size_pct: float,
    touch_tolerance_pct: float,
    poc_shift_threshold_pct: float,
) -> Dict[str, Any]:
    nodes, abs_bin = _build_price_nodes(bars, bin_size_pct=bin_size_pct)
    if not bars or not nodes:
        return {
            "final_poc": None,
            "touch_count": 0,
            "touch_rate": 0.0,
            "crossings": 0,
            "longest_no_touch_bars": 0,
            "avg_distance_pct": None,
            "distance_pct_by_hour_utc": [],
            "migration_event_count": 0,
            "migration_events": [],
            "migration_direction_counts": {},
            "poc_path_change_pct": None,
        }

    final_poc = _to_float(nodes[0].get("center"), 0.0)
    if final_poc <= 0:
        return {
            "final_poc": None,
            "touch_count": 0,
            "touch_rate": 0.0,
            "crossings": 0,
            "longest_no_touch_bars": 0,
            "avg_distance_pct": None,
            "distance_pct_by_hour_utc": [],
            "migration_event_count": 0,
            "migration_events": [],
            "migration_direction_counts": {},
            "poc_path_change_pct": None,
        }

    tol_abs = max(abs_bin / 2.0, final_poc * max(0.01, touch_tolerance_pct) / 100.0)
    zone_low = final_poc - tol_abs
    zone_high = final_poc + tol_abs

    touch_count = 0
    no_touch_streak = 0
    max_no_touch_streak = 0
    crossings = 0
    last_sign = 0
    distances: List[float] = []
    dist_hour_sum: Dict[int, float] = defaultdict(float)
    dist_hour_count: Dict[int, int] = defaultdict(int)

    for bar in bars:
        close = _to_float(bar.get("close"), 0.0)
        if close <= 0:
            continue
        dist_pct = abs((close - final_poc) / final_poc) * 100.0
        distances.append(dist_pct)
        hour = bar["timestamp"].hour
        dist_hour_sum[hour] += dist_pct
        dist_hour_count[hour] += 1

        touched = bar["low"] <= zone_high and bar["high"] >= zone_low
        if touched:
            touch_count += 1
            no_touch_streak = 0
        else:
            no_touch_streak += 1
            max_no_touch_streak = max(max_no_touch_streak, no_touch_streak)

        diff = close - final_poc
        sign = 0
        if diff > tol_abs:
            sign = 1
        elif diff < -tol_abs:
            sign = -1
        if sign != 0:
            if last_sign != 0 and sign != last_sign:
                crossings += 1
            last_sign = sign

    dist_hour_rows = []
    for hour in sorted(dist_hour_count.keys()):
        count = max(1, dist_hour_count[hour])
        dist_hour_rows.append(
            {
                "hour_utc": hour,
                "avg_distance_pct": round(dist_hour_sum[hour] / count, 4),
                "bars": count,
            }
        )

    # Running POC migration
    bin_volumes: Dict[int, float] = defaultdict(float)
    running_poc: Optional[float] = None
    migrations: List[Dict[str, Any]] = []
    direction_counts = Counter()
    first_poc: Optional[float] = None

    for bar in bars:
        price = _to_float(bar.get("close"), 0.0)
        if price <= 0:
            continue
        node_idx = int(round(price / abs_bin))
        bin_volumes[node_idx] += _to_float(bar.get("volume"), 0.0)

        best_idx = max(bin_volumes.keys(), key=lambda idx: bin_volumes[idx])
        current_poc = best_idx * abs_bin
        if first_poc is None:
            first_poc = current_poc

        if running_poc is not None and running_poc > 0 and current_poc != running_poc:
            delta_pct = abs((current_poc - running_poc) / running_poc) * 100.0
            if delta_pct >= max(0.0, float(poc_shift_threshold_pct)):
                direction = "up" if current_poc > running_poc else "down"
                direction_counts[direction] += 1
                migrations.append(
                    {
                        "timestamp": bar["timestamp"].isoformat(),
                        "idx": _to_int(bar.get("idx"), 0),
                        "from_poc": round(running_poc, 4),
                        "to_poc": round(current_poc, 4),
                        "delta_pct": round(delta_pct, 4),
                        "direction": direction,
                    }
                )
        running_poc = current_poc

    path_change_pct = None
    if first_poc is not None and running_poc is not None and first_poc > 0:
        path_change_pct = ((running_poc - first_poc) / first_poc) * 100.0

    return {
        "final_poc": round(final_poc, 4),
        "poc_zone_low": round(zone_low, 4),
        "poc_zone_high": round(zone_high, 4),
        "touch_count": touch_count,
        "touch_rate": round(touch_count / max(1, len(bars)), 4),
        "crossings": crossings,
        "longest_no_touch_bars": max_no_touch_streak,
        "avg_distance_pct": (
            round(_to_float(_safe_mean(distances), 0.0), 4) if distances else None
        ),
        "distance_pct_by_hour_utc": dist_hour_rows,
        "migration_event_count": len(migrations),
        "migration_events": migrations[:40],
        "migration_direction_counts": dict(direction_counts),
        "poc_path_change_pct": (
            round(path_change_pct, 4) if path_change_pct is not None else None
        ),
        "bin_size_abs": round(abs_bin, 6),
    }


def _iter_leaf_items(
    node: Any, prefix: str = "", max_list_items: int = 6
) -> Iterator[Tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            key_txt = str(key)
            child_prefix = f"{prefix}.{key_txt}" if prefix else key_txt
            yield from _iter_leaf_items(
                value, child_prefix, max_list_items=max_list_items
            )
        return
    if isinstance(node, list):
        for idx, value in enumerate(node[: max(0, int(max_list_items))]):
            child_prefix = f"{prefix}[{idx}]"
            yield from _iter_leaf_items(
                value, child_prefix, max_list_items=max_list_items
            )
        return
    yield prefix, node


def _extract_marker_level_context(markers: List[Dict[str, Any]]) -> Dict[str, Any]:
    marker_type_counts = Counter()
    detail_keys = Counter()
    level_context_markers = 0
    level_context_by_hour = Counter()

    numeric_tokens = {
        "poc",
        "vwap",
        "room",
        "ratio",
        "score",
        "test",
        "level",
        "rvol",
        "atr",
        "imbalance",
        "pressure",
        "delta",
        "wick",
        "volume",
    }
    categorical_tokens = {
        "reason",
        "type",
        "mode",
        "setup",
        "context",
        "state",
        "label",
        "classification",
    }

    numeric_sum: Dict[str, float] = defaultdict(float)
    numeric_count: Dict[str, int] = defaultdict(int)
    categorical_counts: Dict[str, Counter] = defaultdict(Counter)

    for marker in markers:
        marker_type = str(marker.get("type") or marker.get("marker_type") or "?")
        marker_type_counts[marker_type] += 1

        details = marker.get("details")
        if not isinstance(details, dict):
            continue

        if isinstance(details.get("level_context"), dict):
            level_context_markers += 1
            ts = _parse_ts(marker.get("timestamp"))
            if ts is not None:
                level_context_by_hour[ts.hour] += 1

        for path, value in _iter_leaf_items(details):
            if not path:
                continue
            detail_keys[path] += 1
            path_lower = path.lower()

            if isinstance(value, (int, float)):
                if any(token in path_lower for token in numeric_tokens):
                    numeric_sum[path] += float(value)
                    numeric_count[path] += 1
            elif isinstance(value, str):
                if len(value) > 80:
                    continue
                if any(token in path_lower for token in categorical_tokens):
                    categorical_counts[path][value] += 1

    top_numeric = []
    for path, count in sorted(
        numeric_count.items(), key=lambda item: item[1], reverse=True
    )[:25]:
        avg = numeric_sum[path] / max(1, count)
        top_numeric.append({"path": path, "samples": count, "avg": round(avg, 6)})

    top_categorical = []
    for path, counter in sorted(
        categorical_counts.items(), key=lambda item: sum(item[1].values()), reverse=True
    )[:20]:
        top_categorical.append(
            {
                "path": path,
                "top_values": [
                    {"value": value, "count": cnt}
                    for value, cnt in counter.most_common(6)
                ],
            }
        )

    level_context_hour_rows = [
        {"hour_utc": hour, "count": count}
        for hour, count in sorted(level_context_by_hour.items())
    ]

    return {
        "markers_total": len(markers),
        "marker_type_counts": dict(marker_type_counts),
        "detail_key_hotspots": [
            {"path": path, "count": count}
            for path, count in detail_keys.most_common(25)
        ],
        "level_context_markers": level_context_markers,
        "level_context_marker_ratio": round(
            level_context_markers / max(1, len(markers)), 4
        ),
        "level_context_by_hour_utc": level_context_hour_rows,
        "tracked_numeric_fields": top_numeric,
        "tracked_categorical_fields": top_categorical,
    }


def _extract_flow_stats(markers: List[Dict[str, Any]]) -> Dict[str, Any]:
    metric_names = {
        "signed_aggression",
        "directional_consistency",
        "imbalance",
        "delta_acceleration",
        "delta_price_divergence",
        "book_pressure",
        "cvd",
        "sweep_intensity",
    }
    overall_sum = defaultdict(float)
    overall_sq = defaultdict(float)
    overall_count = defaultdict(int)
    hour_sum: Dict[int, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    hour_count: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hour_events = Counter()
    flow_event_count = 0

    for marker in markers:
        details = marker.get("details")
        if not isinstance(details, dict):
            continue
        flow = details.get("flow_snapshot")
        merged: Dict[str, Any] = {}
        if isinstance(flow, dict):
            merged.update(flow)
        merged.update({k: details.get(k) for k in metric_names if k in details})

        found_numeric = False
        hour = None
        ts = _parse_ts(marker.get("timestamp"))
        if ts is not None:
            hour = ts.hour

        for metric in metric_names:
            val = merged.get(metric)
            if not isinstance(val, (int, float)):
                continue
            found_numeric = True
            fv = float(val)
            overall_sum[metric] += fv
            overall_sq[metric] += fv * fv
            overall_count[metric] += 1
            if hour is not None:
                hour_sum[hour][metric] += fv
                hour_count[hour][metric] += 1

        if found_numeric:
            flow_event_count += 1
            if hour is not None:
                hour_events[hour] += 1

    overall_avg = {}
    overall_std = {}
    for metric in sorted(overall_sum.keys()):
        count = overall_count[metric]
        if count <= 0:
            continue
        mean = overall_sum[metric] / count
        variance = max(0.0, (overall_sq[metric] / count) - (mean * mean))
        overall_avg[metric] = round(mean, 6)
        overall_std[metric] = round(math.sqrt(variance), 6)

    by_hour = []
    for hour in sorted(hour_events.keys()):
        hour_avg = {}
        for metric in sorted(hour_sum[hour].keys()):
            c = hour_count[hour].get(metric, 0)
            if c > 0:
                hour_avg[metric] = round(hour_sum[hour][metric] / c, 6)
        by_hour.append(
            {
                "hour_utc": hour,
                "flow_event_count": int(hour_events[hour]),
                "avg_metrics": hour_avg,
            }
        )

    return {
        "flow_event_count": int(flow_event_count),
        "overall_avg_metrics": overall_avg,
        "overall_std_metrics": overall_std,
        "by_hour_utc": by_hour,
    }


def _trade_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    session_summary = summary.get("session_summary")
    if not isinstance(session_summary, dict):
        return {
            "trades": 0,
            "win_rate_pct": None,
            "total_pnl_dollars": None,
            "max_drawdown_dollars": None,
            "exit_reason_counts": {},
            "strategy_counts": {},
            "entry_hour_counts_utc": {},
        }

    trades = session_summary.get("trades")
    if not isinstance(trades, list):
        trades = []
    exit_counts = Counter()
    strat_counts = Counter()
    entry_hour_counts = Counter()
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        exit_counts[str(trade.get("exit_reason") or "?")] += 1
        strat_counts[str(trade.get("strategy") or "?")] += 1
        entry_ts = _parse_ts(trade.get("entry_time"))
        if entry_ts is not None:
            entry_hour_counts[entry_ts.hour] += 1

    win_rate = session_summary.get("win_rate")
    total_pnl_dollars = session_summary.get("total_pnl_dollars")
    max_drawdown_dollars = session_summary.get("max_drawdown_dollars")
    return {
        "trades": len(trades),
        "win_rate_pct": round(_to_float(win_rate), 4) if win_rate is not None else None,
        "total_pnl_dollars": (
            round(_to_float(total_pnl_dollars), 6)
            if total_pnl_dollars is not None
            else None
        ),
        "max_drawdown_dollars": (
            round(_to_float(max_drawdown_dollars), 6)
            if max_drawdown_dollars is not None
            else None
        ),
        "exit_reason_counts": dict(
            sorted(exit_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "strategy_counts": dict(
            sorted(strat_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "entry_hour_counts_utc": {
            str(hour): count for hour, count in sorted(entry_hour_counts.items())
        },
    }


def _derive_rule_candidates(
    *,
    top_intervals: List[Dict[str, Any]],
    volume_price_rel: Dict[str, Any],
    non_return: Dict[str, Any],
    poc: Dict[str, Any],
    flow_stats: Dict[str, Any],
    marker_ctx: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []

    non_return_ratio = _to_float(non_return.get("non_return_ratio"), 0.0)
    if non_return_ratio >= 0.30:
        confidence = _clamp(0.35 + non_return_ratio, 0.05, 0.95)
        rules.append(
            {
                "rule_id": "one_way_auction_window",
                "hypothesis": "High-volume anchors often act as one-way launch zones during session auction.",
                "trigger": "When volume anchor forms and non-return ratio stays elevated, prefer continuation logic.",
                "risk_note": "Fails when day shifts into balancing regime.",
                "confidence": round(confidence, 3),
                "evidence": {
                    "non_return_ratio": round(non_return_ratio, 4),
                    "non_return_count": _to_int(non_return.get("non_return_count"), 0),
                    "candidate_count": _to_int(non_return.get("candidate_count"), 0),
                },
            }
        )

    touch_rate = _to_float(poc.get("touch_rate"), 0.0)
    crossings = _to_int(poc.get("crossings"), 0)
    if touch_rate >= 0.20 and crossings >= 3:
        confidence = _clamp(
            0.35 + (touch_rate * 0.8) + min(0.2, crossings * 0.02), 0.05, 0.95
        )
        rules.append(
            {
                "rule_id": "poc_magnet_rotation",
                "hypothesis": "Final session POC acts as intraday magnet with repeated rotations.",
                "trigger": "When POC touch rate and crossings stay high, rotation setups around POC are favored.",
                "risk_note": "Breakout trend days can ignore magnet behavior.",
                "confidence": round(confidence, 3),
                "evidence": {
                    "touch_rate": round(touch_rate, 4),
                    "touch_count": _to_int(poc.get("touch_count"), 0),
                    "crossings": crossings,
                    "migration_event_count": _to_int(
                        poc.get("migration_event_count"), 0
                    ),
                },
            }
        )

    corr_next = volume_price_rel.get("correlations", {}).get("vol_vs_next_abs_ret_pct")
    high_next = _to_float(
        volume_price_rel.get("high_volume_group", {}).get("avg_abs_next_ret_pct"), 0.0
    )
    low_next = _to_float(
        volume_price_rel.get("low_volume_group", {}).get("avg_abs_next_ret_pct"), 0.0
    )

    if (
        isinstance(corr_next, (int, float))
        and corr_next >= 0.18
        and high_next > low_next
    ):
        confidence = _clamp(0.4 + corr_next, 0.05, 0.95)
        rules.append(
            {
                "rule_id": "volume_impulse_continuation",
                "hypothesis": "Higher volume bars are followed by larger next-bar expansion.",
                "trigger": "Use breakout continuation when high-volume percentile confirms impulse.",
                "risk_note": "False breaks increase in low-RVOL midday windows.",
                "confidence": round(confidence, 3),
                "evidence": {
                    "corr_vol_next_abs_ret": round(corr_next, 6),
                    "high_volume_avg_next_abs_ret_pct": round(high_next, 4),
                    "low_volume_avg_next_abs_ret_pct": round(low_next, 4),
                },
            }
        )

    if (
        isinstance(corr_next, (int, float))
        and corr_next <= -0.10
        and high_next < low_next
    ):
        confidence = _clamp(0.35 + abs(corr_next), 0.05, 0.90)
        rules.append(
            {
                "rule_id": "volume_exhaustion_reversal",
                "hypothesis": "High volume tends to exhaust and mean-revert on this configuration.",
                "trigger": "After volume spike + weak follow-through, prefer fade/rotation structure.",
                "risk_note": "Strong trend regime can invalidate fade quickly.",
                "confidence": round(confidence, 3),
                "evidence": {
                    "corr_vol_next_abs_ret": round(corr_next, 6),
                    "high_volume_avg_next_abs_ret_pct": round(high_next, 4),
                    "low_volume_avg_next_abs_ret_pct": round(low_next, 4),
                },
            }
        )

    signed_aggr = abs(
        _to_float(
            flow_stats.get("overall_avg_metrics", {}).get("signed_aggression"), 0.0
        )
    )
    flow_events = _to_int(flow_stats.get("flow_event_count"), 0)
    if flow_events >= 10 and signed_aggr >= 0.12:
        confidence = _clamp(
            0.30 + min(0.4, signed_aggr) + min(0.2, flow_events / 200.0), 0.05, 0.92
        )
        rules.append(
            {
                "rule_id": "flow_pressure_bias",
                "hypothesis": "Flow snapshot imbalance provides directional pressure edge.",
                "trigger": "Elevated signed aggression with frequent events can bias setup filtering.",
                "risk_note": "Need robust thresholding to avoid noisy prints.",
                "confidence": round(confidence, 3),
                "evidence": {
                    "flow_event_count": flow_events,
                    "abs_signed_aggression": round(signed_aggr, 6),
                },
            }
        )

    first_interval = top_intervals[0] if top_intervals else {}
    if first_interval:
        rev_count = _to_int(first_interval.get("revisit_count_after_interval"), 0)
        bars_to_rev = first_interval.get("bars_until_first_revisit")
        if rev_count <= 1 and (bars_to_rev is None or _to_int(bars_to_rev, 0) >= 25):
            confidence = _clamp(
                0.35
                + min(0.4, _to_float(first_interval.get("volume"), 0.0) / 1_000_000.0),
                0.05,
                0.88,
            )
            rules.append(
                {
                    "rule_id": "high_volume_time_window_persistence",
                    "hypothesis": "Top volume interval creates persistent reference level that is not quickly revisited.",
                    "trigger": "Tag top intraday volume windows and watch for delayed return events.",
                    "risk_note": "In balancing sessions revisit can happen quickly.",
                    "confidence": round(confidence, 3),
                    "evidence": {
                        "tod_label": first_interval.get("tod_label"),
                        "revisit_count": rev_count,
                        "bars_until_first_revisit": bars_to_rev,
                    },
                }
            )

    level_ctx_ratio = _to_float(marker_ctx.get("level_context_marker_ratio"), 0.0)
    if level_ctx_ratio >= 0.35:
        confidence = _clamp(0.28 + level_ctx_ratio, 0.05, 0.90)
        rules.append(
            {
                "rule_id": "level_context_density",
                "hypothesis": "Level-context diagnostics are dense enough to support rule extraction from markers.",
                "trigger": "Mine `level_context` and entry quality diagnostics for condition templates.",
                "risk_note": "Quality depends on marker completeness and consistency.",
                "confidence": round(confidence, 3),
                "evidence": {
                    "level_context_marker_ratio": round(level_ctx_ratio, 4),
                    "level_context_markers": _to_int(
                        marker_ctx.get("level_context_markers"), 0
                    ),
                    "markers_total": _to_int(marker_ctx.get("markers_total"), 0),
                },
            }
        )

    rules.sort(key=lambda item: _to_float(item.get("confidence"), 0.0), reverse=True)
    for i, row in enumerate(rules, start=1):
        row["priority_rank"] = i
    return rules


def _analyze_run(
    *,
    run_artifacts: Dict[str, Any],
    bucket_minutes: int,
    top_buckets: int,
    revisit_tolerance_pct: float,
    price_bin_size_pct: float,
    top_price_nodes: int,
    non_return_lookahead_bars: int,
    non_return_min_move_pct: float,
    non_return_top_n: int,
    poc_shift_threshold_pct: float,
) -> Dict[str, Any]:
    bars_payload = run_artifacts.get("bars_payload", {})
    bars_raw = bars_payload.get("bars")
    bars = _normalize_bars(bars_raw if isinstance(bars_raw, list) else [])
    markers = run_artifacts.get("markers", [])
    summary = run_artifacts.get("summary", {})

    buckets = _build_time_buckets(bars, bucket_minutes=bucket_minutes)
    top_intervals = _top_time_interval_revisits(
        bars,
        buckets,
        top_n=top_buckets,
        revisit_tolerance_pct=revisit_tolerance_pct,
    )
    recurring_windows = _top_recurring_volume_windows(buckets, top_n=top_buckets)
    top_nodes = _top_price_volume_nodes(
        bars,
        bin_size_pct=price_bin_size_pct,
        top_n=top_price_nodes,
    )
    flow_stats = _extract_flow_stats(markers if isinstance(markers, list) else [])
    trade_stats = _trade_summary(summary if isinstance(summary, dict) else {})
    marker_context = _extract_marker_level_context(
        markers if isinstance(markers, list) else []
    )
    volume_price_rel = _volume_price_relationships(bars)
    hourly_profile = _hourly_price_action_volume(bars)
    non_return = _non_returning_price_zones(
        bars,
        tolerance_pct=revisit_tolerance_pct,
        lookahead_bars=non_return_lookahead_bars,
        min_move_pct=non_return_min_move_pct,
        top_n=non_return_top_n,
        anchor_volume_quantile=0.75,
    )
    poc_analysis = _poc_magnet_and_migration(
        bars,
        bin_size_pct=price_bin_size_pct,
        touch_tolerance_pct=revisit_tolerance_pct,
        poc_shift_threshold_pct=poc_shift_threshold_pct,
    )

    rules = _derive_rule_candidates(
        top_intervals=top_intervals,
        volume_price_rel=volume_price_rel,
        non_return=non_return,
        poc=poc_analysis,
        flow_stats=flow_stats,
        marker_ctx=marker_context,
    )

    return {
        "run_key": run_artifacts.get("run_key"),
        "run_id": run_artifacts.get("run_id"),
        "ticker": run_artifacts.get("ticker"),
        "date_label": run_artifacts.get("date_label"),
        "bars_processed": len(bars),
        "markers_count": len(markers) if isinstance(markers, list) else 0,
        "trade_summary": trade_stats,
        "top_volume_intervals": top_intervals,
        "top_recurring_volume_windows_utc": recurring_windows,
        "top_price_volume_nodes": top_nodes,
        "temporal_profile": hourly_profile,
        "volume_price_relationships": volume_price_rel,
        "non_returning_price_zones": non_return,
        "poc_magnet_and_migration": poc_analysis,
        "marker_level_context": marker_context,
        "flow_stats": flow_stats,
        "rule_candidates": rules,
        "summary_execution_config": (
            run_artifacts.get("summary", {}).get("execution_config", {})
            if isinstance(run_artifacts.get("summary"), dict)
            else {}
        ),
        "summary_profile_meta": {
            "unified_profile_id": (
                run_artifacts.get("summary", {}).get("unified_profile_id")
                if isinstance(run_artifacts.get("summary"), dict)
                else None
            ),
            "unified_profile_name": (
                run_artifacts.get("summary", {}).get("unified_profile_name")
                if isinstance(run_artifacts.get("summary"), dict)
                else None
            ),
        },
    }


def _default_log_path(run_id: str, variant_name: str = "") -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_variant = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in variant_name.strip()
    )
    suffix = f"_{safe_variant}" if safe_variant else ""
    return Path("reports") / "pattern_logs" / f"{stamp}_{run_id}{suffix}.json"


def _candidate_log_path(explicit_path: str, variant_name: str) -> str:
    if not explicit_path:
        return ""
    out = Path(explicit_path)
    suffix = out.suffix if out.suffix else ".json"
    if variant_name and variant_name != "single":
        return str(out.with_name(f"{out.stem}_{variant_name}{suffix}"))
    if out.suffix:
        return str(out)
    return str(out.with_suffix(".json"))


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _markdown_table(headers: List[str], rows: List[List[Any]]) -> List[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_md(item) for item in row) + " |")
    return lines


def _write_markdown_report(payload: Dict[str, Any], json_path: Path) -> Path:
    analysis = payload.get("analysis", {}) if isinstance(payload, dict) else {}
    trade = analysis.get("trade_summary", {}) if isinstance(analysis, dict) else {}
    non_return = (
        analysis.get("non_returning_price_zones", {})
        if isinstance(analysis, dict)
        else {}
    )
    poc = (
        analysis.get("poc_magnet_and_migration", {})
        if isinstance(analysis, dict)
        else {}
    )
    rel = (
        analysis.get("volume_price_relationships", {})
        if isinstance(analysis, dict)
        else {}
    )

    md_path = json_path.with_suffix(".md")
    lines: List[str] = []
    lines.append(f"# Diagnostic Pattern Report - {payload.get('candidate')}")
    lines.append("")
    lines.append(f"- generated_at: `{payload.get('generated_at')}`")
    lines.append(f"- run_key: `{analysis.get('run_key')}`")
    lines.append(f"- ticker: `{analysis.get('ticker')}`")
    lines.append(f"- bars_processed: `{analysis.get('bars_processed')}`")
    lines.append(f"- markers: `{analysis.get('markers_count')}`")
    lines.append("")

    lines.append("## Session Summary")
    lines.extend(
        _markdown_table(
            ["trades", "win_rate_pct", "total_pnl_dollars", "max_drawdown_dollars"],
            [
                [
                    trade.get("trades"),
                    trade.get("win_rate_pct"),
                    trade.get("total_pnl_dollars"),
                    trade.get("max_drawdown_dollars"),
                ]
            ],
        )
    )
    lines.append("")

    lines.append("## Top Rule Candidates")
    rule_rows = []
    for rule in analysis.get("rule_candidates", [])[:8]:
        ev = rule.get("evidence") if isinstance(rule.get("evidence"), dict) else {}
        short_ev = ", ".join(f"{k}={v}" for k, v in list(ev.items())[:3])
        rule_rows.append(
            [
                rule.get("priority_rank"),
                rule.get("rule_id"),
                rule.get("confidence"),
                rule.get("hypothesis"),
                short_ev,
            ]
        )
    if rule_rows:
        lines.extend(
            _markdown_table(
                ["rank", "rule_id", "confidence", "hypothesis", "evidence"], rule_rows
            )
        )
    else:
        lines.append("No rule candidates generated.")
    lines.append("")

    lines.append("## Non-Return Zones")
    lines.extend(
        _markdown_table(
            ["candidate_count", "non_return_count", "non_return_ratio"],
            [
                [
                    non_return.get("candidate_count"),
                    non_return.get("non_return_count"),
                    non_return.get("non_return_ratio"),
                ]
            ],
        )
    )
    zone_rows = []
    for row in non_return.get("top_non_return_zones", [])[:10]:
        zone_rows.append(
            [
                row.get("anchor_tod"),
                row.get("anchor_price"),
                row.get("anchor_volume"),
                row.get("dominant_direction"),
                row.get("dominant_move_pct"),
                row.get("first_return_timestamp") or "never",
            ]
        )
    if zone_rows:
        lines.append("")
        lines.extend(
            _markdown_table(
                [
                    "time_utc",
                    "anchor_price",
                    "anchor_volume",
                    "direction",
                    "move_pct",
                    "first_return",
                ],
                zone_rows,
            )
        )
    lines.append("")

    lines.append("## POC Magnet + Migration")
    lines.extend(
        _markdown_table(
            [
                "final_poc",
                "touch_rate",
                "touch_count",
                "crossings",
                "migration_event_count",
                "poc_path_change_pct",
            ],
            [
                [
                    poc.get("final_poc"),
                    poc.get("touch_rate"),
                    poc.get("touch_count"),
                    poc.get("crossings"),
                    poc.get("migration_event_count"),
                    poc.get("poc_path_change_pct"),
                ]
            ],
        )
    )
    lines.append("")

    lines.append("## Volume-Price Relationships")
    corr = rel.get("correlations", {}) if isinstance(rel, dict) else {}
    lines.extend(
        _markdown_table(
            ["vol_vs_range_pct", "vol_vs_body_pct", "vol_vs_next_abs_ret_pct"],
            [
                [
                    corr.get("vol_vs_range_pct"),
                    corr.get("vol_vs_body_pct"),
                    corr.get("vol_vs_next_abs_ret_pct"),
                ]
            ],
        )
    )
    lines.append("")

    top_interval_rows = []
    for row in analysis.get("top_volume_intervals", [])[:10]:
        top_interval_rows.append(
            [
                row.get("rank"),
                row.get("tod_label"),
                row.get("volume"),
                row.get("vwap"),
                row.get("revisit_count_after_interval"),
                row.get("bars_until_first_revisit") or "n/a",
            ]
        )
    if top_interval_rows:
        lines.append("## Top Volume Time Intervals")
        lines.extend(
            _markdown_table(
                [
                    "rank",
                    "time_utc",
                    "volume",
                    "vwap",
                    "revisits",
                    "bars_to_first_revisit",
                ],
                top_interval_rows,
            )
        )
        lines.append("")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def _write_log(
    payload: Dict[str, Any],
    path: Optional[str],
    *,
    variant_name: str = "",
    write_markdown: bool = True,
) -> Tuple[Path, Optional[Path]]:
    run_id = str(payload.get("analysis", {}).get("run_id") or "run")
    out = (
        Path(path)
        if path
        else _default_log_path(run_id=run_id, variant_name=variant_name)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)

    md_path = _write_markdown_report(payload, out) if write_markdown else None
    return out, md_path


def _print_analysis(analysis: Dict[str, Any], title: str) -> None:
    trade = analysis.get("trade_summary", {})
    non_return = analysis.get("non_returning_price_zones", {})
    poc = analysis.get("poc_magnet_and_migration", {})
    rel = analysis.get("volume_price_relationships", {})
    corr = rel.get("correlations", {}) if isinstance(rel, dict) else {}

    print("\n" + "=" * 92)
    print(f"  {title}")
    print("=" * 92)
    print(f"  Run Key: {analysis.get('run_key')}")
    print(
        f"  Trades: {trade.get('trades')} | WinRate: {trade.get('win_rate_pct')} | "
        f"PnL$: {trade.get('total_pnl_dollars')} | MaxDD$: {trade.get('max_drawdown_dollars')}"
    )
    print(
        f"  Bars Processed: {analysis.get('bars_processed')} | Markers: {analysis.get('markers_count')}"
    )
    print(
        f"  Unified Profile: {analysis.get('summary_profile_meta', {}).get('unified_profile_id')}"
    )

    print("\n  Core Pattern Signals")
    print(
        f"    Non-return ratio: {non_return.get('non_return_ratio')} "
        f"({non_return.get('non_return_count')}/{non_return.get('candidate_count')})"
    )
    print(
        f"    POC touch rate: {poc.get('touch_rate')} | crossings: {poc.get('crossings')} "
        f"| migration_events: {poc.get('migration_event_count')}"
    )
    print(
        "    Correlations: "
        f"vol-range={corr.get('vol_vs_range_pct')} "
        f"vol-body={corr.get('vol_vs_body_pct')} "
        f"vol-next_abs_ret={corr.get('vol_vs_next_abs_ret_pct')}"
    )

    print("\n  Top Rule Candidates")
    rules = analysis.get("rule_candidates", [])
    if not rules:
        print("    (none)")
    for row in rules[:8]:
        print(
            "    "
            f"#{row.get('priority_rank')} {row.get('rule_id')} conf={row.get('confidence')} "
            f"hypothesis={row.get('hypothesis')}"
        )

    print("\n  Top Volume Intervals + Revisit")
    for row in analysis.get("top_volume_intervals", [])[:8]:
        print(
            "    "
            f"#{row['rank']} {row['tod_label']} vol={row['volume']:.0f} vwap={row['vwap']:.3f} "
            f"revisit={row['revisit_count_after_interval']} "
            f"bars_to_revisit={row['bars_until_first_revisit']}"
        )

    print("\n  Non-Returning Anchor Zones")
    for row in non_return.get("top_non_return_zones", [])[:8]:
        print(
            "    "
            f"{row['anchor_tod']} price={row['anchor_price']:.3f} vol={row['anchor_volume']:.0f} "
            f"dir={row['dominant_direction']} move={row['dominant_move_pct']:.3f}%"
        )

    flow = analysis.get("flow_stats", {})
    print(
        "\n  Flow/L2 Snapshot:"
        f" events={flow.get('flow_event_count')} "
        f"avg={json.dumps(flow.get('overall_avg_metrics', {}), ensure_ascii=True)}"
    )


def _score_candidate(analysis: Dict[str, Any]) -> Tuple[int, float]:
    trade = analysis.get("trade_summary", {})
    trades = _to_int(trade.get("trades"), 0)
    pnl = _to_float(trade.get("total_pnl_dollars"), 0.0)
    return trades, pnl


def _parse_date_ymd(raw: str) -> datetime:
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"Invalid date format '{raw}', expected YYYY-MM-DD") from exc


def _build_evaluation_windows(
    *,
    date_from: str,
    date_to: str,
    window_days: int,
    window_count: int,
    include_full_range: bool,
) -> List[Dict[str, str]]:
    start_dt = _parse_date_ymd(date_from)
    end_dt = _parse_date_ymd(date_to)
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    total_days = (end_dt.date() - start_dt.date()).days + 1
    if total_days <= 1:
        return [
            {
                "date_from": start_dt.strftime("%Y-%m-%d"),
                "date_to": end_dt.strftime("%Y-%m-%d"),
                "label": f"{start_dt.strftime('%Y-%m-%d')}_to_{end_dt.strftime('%Y-%m-%d')}",
            }
        ]

    windows: List[Dict[str, str]] = []
    seen = set()

    def _append_window(window_start: datetime, window_end: datetime) -> None:
        s = window_start.strftime("%Y-%m-%d")
        e = window_end.strftime("%Y-%m-%d")
        key = (s, e)
        if key in seen:
            return
        seen.add(key)
        windows.append({"date_from": s, "date_to": e, "label": f"{s}_to_{e}"})

    if include_full_range:
        _append_window(start_dt, end_dt)

    count = max(0, int(window_count))
    if count <= 0:
        return windows

    win_days = max(1, min(int(window_days), total_days))
    if win_days >= total_days:
        _append_window(start_dt, end_dt)
        return windows

    max_start_idx = total_days - win_days
    if count == 1:
        start_indices = [max_start_idx // 2]
    else:
        start_indices = []
        for i in range(count):
            ratio = i / max(1, count - 1)
            idx = int(round(ratio * max_start_idx))
            start_indices.append(idx)

    for idx in sorted(set(start_indices)):
        window_start = start_dt + timedelta(days=idx)
        window_end = window_start + timedelta(days=win_days - 1)
        _append_window(window_start, window_end)

    return windows


def _aggregate_round_metrics(
    *,
    round_results: List[Dict[str, Any]],
    min_trades_target: int,
    universal_rule_min_presence: float,
    universal_time_window_min_presence: float,
) -> Dict[str, Any]:
    if not round_results:
        return {
            "window_count": 0,
            "windows": [],
            "aggregate": {
                "avg_trades": 0.0,
                "median_trades": 0.0,
                "min_trades": 0,
                "max_trades": 0,
                "avg_pnl_dollars": 0.0,
                "median_pnl_dollars": 0.0,
                "min_pnl_dollars": 0.0,
                "max_pnl_dollars": 0.0,
                "positive_pnl_ratio": 0.0,
                "trade_target_ratio": 0.0,
                "avg_win_rate_pct": 0.0,
                "avg_stop_exit_ratio": 0.0,
                "pnl_std_dollars": 0.0,
                "robust_score": 0.0,
            },
            "stable_rules": [],
            "stable_time_windows_utc": [],
        }

    window_rows: List[Dict[str, Any]] = []
    pnl_vals: List[float] = []
    trade_vals: List[float] = []
    win_vals: List[float] = []
    stop_vals: List[float] = []
    rule_count = Counter()
    rule_conf_sum = defaultdict(float)
    time_window_count = Counter()
    positive_count = 0
    trade_target_count = 0

    for item in round_results:
        analysis = item.get("analysis", {})
        window = item.get("window", {})
        trade = analysis.get("trade_summary", {}) if isinstance(analysis, dict) else {}
        trades = _to_int(trade.get("trades"), 0)
        pnl = _to_float(trade.get("total_pnl_dollars"), 0.0)
        win_rate = _to_float(trade.get("win_rate_pct"), 0.0)

        exits = (
            trade.get("exit_reason_counts", {})
            if isinstance(trade.get("exit_reason_counts"), dict)
            else {}
        )
        exit_total = sum(_to_int(v, 0) for v in exits.values())
        stop_like = sum(
            _to_int(v, 0) for k, v in exits.items() if "stop" in str(k).lower()
        )
        stop_ratio = (stop_like / exit_total) if exit_total > 0 else 0.0

        corr_next = (
            analysis.get("volume_price_relationships", {})
            .get("correlations", {})
            .get("vol_vs_next_abs_ret_pct")
        )
        non_return_ratio = analysis.get("non_returning_price_zones", {}).get(
            "non_return_ratio"
        )
        poc_touch_rate = analysis.get("poc_magnet_and_migration", {}).get("touch_rate")

        row = {
            "window_label": window.get("label"),
            "date_from": window.get("date_from"),
            "date_to": window.get("date_to"),
            "trades": trades,
            "pnl_dollars": round(pnl, 6),
            "win_rate_pct": round(win_rate, 4),
            "stop_exit_ratio": round(stop_ratio, 4),
            "non_return_ratio": round(_to_float(non_return_ratio, 0.0), 4),
            "poc_touch_rate": round(_to_float(poc_touch_rate, 0.0), 4),
            "vol_next_abs_ret_corr": (
                round(_to_float(corr_next, 0.0), 6)
                if isinstance(corr_next, (int, float))
                else None
            ),
            "log_path": item.get("log_path"),
            "markdown_path": item.get("markdown_path"),
            "run_key": analysis.get("run_key"),
        }
        window_rows.append(row)

        pnl_vals.append(pnl)
        trade_vals.append(float(trades))
        win_vals.append(win_rate)
        stop_vals.append(stop_ratio)
        positive_count += 1 if pnl > 0 else 0
        trade_target_count += 1 if trades >= max(1, int(min_trades_target)) else 0

        for rule in analysis.get("rule_candidates", [])[:8]:
            rule_id = str(rule.get("rule_id") or "").strip()
            if not rule_id:
                continue
            conf = _to_float(rule.get("confidence"), 0.0)
            rule_count[rule_id] += 1
            rule_conf_sum[rule_id] += conf
        # Count each TOD at most once per window to keep presence_ratio in [0, 1].
        tod_seen_in_window = set()
        for interval in analysis.get("top_volume_intervals", [])[:6]:
            tod = str(interval.get("tod_label") or "").strip()
            if not tod or tod in tod_seen_in_window:
                continue
            tod_seen_in_window.add(tod)
            time_window_count[tod] += 1

    n = len(window_rows)
    avg_trades = _to_float(_safe_mean(trade_vals), 0.0)
    avg_pnl = _to_float(_safe_mean(pnl_vals), 0.0)
    avg_win = _to_float(_safe_mean(win_vals), 0.0)
    avg_stop_ratio = _to_float(_safe_mean(stop_vals), 0.0)
    pnl_std = statistics.pstdev(pnl_vals) if len(pnl_vals) > 1 else 0.0
    positive_ratio = positive_count / max(1, n)
    trade_target_ratio = trade_target_count / max(1, n)

    trade_term = _clamp(avg_trades / max(1.0, float(min_trades_target)), 0.0, 2.0) / 2.0
    pnl_term = 0.5 + 0.5 * math.tanh(avg_pnl / 120.0)
    stability_term = 1.0 / (1.0 + (pnl_std / (abs(avg_pnl) + 20.0)))
    win_term = _clamp(avg_win / 100.0, 0.0, 1.0)
    robust_score = (
        0.30 * positive_ratio
        + 0.25 * trade_term
        + 0.20 * pnl_term
        + 0.15 * stability_term
        + 0.10 * win_term
    )

    min_presence_rules = max(
        1, int(math.ceil(n * _clamp(universal_rule_min_presence, 0.0, 1.0)))
    )
    stable_rules = []
    for rule_id, count in rule_count.most_common():
        if count < min_presence_rules:
            continue
        stable_rules.append(
            {
                "rule_id": rule_id,
                "presence_count": count,
                "presence_ratio": round(count / max(1, n), 4),
                "avg_confidence": round(rule_conf_sum[rule_id] / max(1, count), 4),
            }
        )

    min_presence_time = max(
        1, int(math.ceil(n * _clamp(universal_time_window_min_presence, 0.0, 1.0)))
    )
    stable_time = []
    for tod, count in time_window_count.most_common():
        if count < min_presence_time:
            continue
        stable_time.append(
            {
                "tod_label": tod,
                "presence_count": count,
                "presence_ratio": round(count / max(1, n), 4),
            }
        )

    return {
        "window_count": n,
        "windows": window_rows,
        "aggregate": {
            "avg_trades": round(avg_trades, 4),
            "median_trades": (
                round(statistics.median(trade_vals), 4) if trade_vals else 0.0
            ),
            "min_trades": int(min(trade_vals)) if trade_vals else 0,
            "max_trades": int(max(trade_vals)) if trade_vals else 0,
            "avg_pnl_dollars": round(avg_pnl, 6),
            "median_pnl_dollars": (
                round(statistics.median(pnl_vals), 6) if pnl_vals else 0.0
            ),
            "min_pnl_dollars": round(min(pnl_vals), 6) if pnl_vals else 0.0,
            "max_pnl_dollars": round(max(pnl_vals), 6) if pnl_vals else 0.0,
            "positive_pnl_ratio": round(positive_ratio, 4),
            "trade_target_ratio": round(trade_target_ratio, 4),
            "avg_win_rate_pct": round(avg_win, 4),
            "avg_stop_exit_ratio": round(avg_stop_ratio, 4),
            "pnl_std_dollars": round(pnl_std, 6),
            "robust_score": round(robust_score, 6),
        },
        "stable_rules": stable_rules,
        "stable_time_windows_utc": stable_time,
    }


def _write_round_summary(
    *,
    round_name: str,
    summary_payload: Dict[str, Any],
    write_markdown: bool,
) -> Tuple[Path, Optional[Path]]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in round_name
    )
    base = Path("reports") / "pattern_logs" / f"{stamp}_round_summary_{safe_name}"
    json_path = base.with_suffix(".json")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, indent=2)

    md_path: Optional[Path] = None
    if write_markdown:
        md_path = base.with_suffix(".md")
        lines: List[str] = []
        lines.append(f"# Round Summary - {round_name}")
        lines.append("")
        lines.append(f"- generated_at: `{summary_payload.get('generated_at')}`")
        lines.append(f"- round: `{summary_payload.get('round')}`")
        lines.append(f"- window_count: `{summary_payload.get('window_count')}`")
        lines.append("")

        agg = summary_payload.get("aggregate", {})
        lines.append("## Aggregate")
        lines.extend(
            _markdown_table(
                [
                    "robust_score",
                    "avg_trades",
                    "avg_pnl_dollars",
                    "positive_pnl_ratio",
                    "trade_target_ratio",
                    "avg_win_rate_pct",
                    "avg_stop_exit_ratio",
                ],
                [
                    [
                        agg.get("robust_score"),
                        agg.get("avg_trades"),
                        agg.get("avg_pnl_dollars"),
                        agg.get("positive_pnl_ratio"),
                        agg.get("trade_target_ratio"),
                        agg.get("avg_win_rate_pct"),
                        agg.get("avg_stop_exit_ratio"),
                    ]
                ],
            )
        )
        lines.append("")

        rows = []
        for row in summary_payload.get("windows", []):
            rows.append(
                [
                    row.get("window_label"),
                    row.get("trades"),
                    row.get("pnl_dollars"),
                    row.get("win_rate_pct"),
                    row.get("stop_exit_ratio"),
                    row.get("non_return_ratio"),
                    row.get("poc_touch_rate"),
                ]
            )
        if rows:
            lines.append("## Windows")
            lines.extend(
                _markdown_table(
                    [
                        "window",
                        "trades",
                        "pnl_dollars",
                        "win_rate_pct",
                        "stop_exit_ratio",
                        "non_return_ratio",
                        "poc_touch_rate",
                    ],
                    rows,
                )
            )
            lines.append("")

        stable_rules = summary_payload.get("stable_rules", [])
        if stable_rules:
            lines.append("## Stable Rules")
            lines.extend(
                _markdown_table(
                    ["rule_id", "presence_count", "presence_ratio", "avg_confidence"],
                    [
                        [
                            row.get("rule_id"),
                            row.get("presence_count"),
                            row.get("presence_ratio"),
                            row.get("avg_confidence"),
                        ]
                        for row in stable_rules
                    ],
                )
            )
            lines.append("")

        stable_windows = summary_payload.get("stable_time_windows_utc", [])
        if stable_windows:
            lines.append("## Stable Time Windows (UTC)")
            lines.extend(
                _markdown_table(
                    ["tod_label", "presence_count", "presence_ratio"],
                    [
                        [
                            row.get("tod_label"),
                            row.get("presence_count"),
                            row.get("presence_ratio"),
                        ]
                        for row in stable_windows
                    ],
                )
            )
            lines.append("")

        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return json_path, md_path


def _derive_recursive_overrides_from_round(
    *,
    round_summary: Dict[str, Any],
    current_overrides: Dict[str, Any],
    min_trades: int,
    min_positive_ratio: float,
) -> Tuple[Dict[str, Any], List[str]]:
    updates: Dict[str, Any] = {}
    reasons: List[str] = []

    agg = round_summary.get("aggregate", {}) if isinstance(round_summary, dict) else {}
    avg_trades = _to_float(agg.get("avg_trades"), 0.0)
    positive_ratio = _to_float(agg.get("positive_pnl_ratio"), 0.0)
    avg_stop_ratio = _to_float(agg.get("avg_stop_exit_ratio"), 0.0)
    avg_pnl = _to_float(agg.get("avg_pnl_dollars"), 0.0)
    stable_rules = {
        str(row.get("rule_id") or "") for row in round_summary.get("stable_rules", [])
    }

    if avg_trades < max(1.0, float(min_trades)):
        base_tol = _to_float(
            current_overrides.get(
                "intraday_levels_entry_tolerance_pct",
                FORCE_TRADE_OVERRIDES.get(
                    "intraday_levels_entry_tolerance_pct",
                    SMART_MONEY_BASE_PARAMS.get(
                        "intraday_levels_entry_tolerance_pct", 0.1
                    ),
                ),
            ),
            0.1,
        )
        updates["intraday_levels_entry_tolerance_pct"] = round(
            min(0.40, base_tol + 0.04), 4
        )
        base_rot = _to_int(
            current_overrides.get(
                "intraday_levels_rotation_max_tests",
                FORCE_TRADE_OVERRIDES.get(
                    "intraday_levels_rotation_max_tests",
                    SMART_MONEY_BASE_PARAMS.get(
                        "intraday_levels_rotation_max_tests", 2
                    ),
                ),
            ),
            2,
        )
        updates["intraday_levels_rotation_max_tests"] = min(14, base_rot + 1)
        updates["intraday_levels_break_cooldown_bars"] = 1
        reasons.append("avg_trades_below_target_relax_entry_context")

    if positive_ratio < _clamp(min_positive_ratio, 0.0, 1.0) or avg_pnl < 0.0:
        base_risk = _to_float(
            current_overrides.get(
                "risk_per_trade_pct",
                FORCE_TRADE_OVERRIDES.get(
                    "risk_per_trade_pct",
                    SMART_MONEY_BASE_PARAMS.get("risk_per_trade_pct", 0.6),
                ),
            ),
            0.4,
        )
        updates["risk_per_trade_pct"] = round(max(0.20, base_risk - 0.05), 4)
        base_confluence = _to_int(
            current_overrides.get(
                "intraday_levels_min_confluence_score",
                FORCE_TRADE_OVERRIDES.get(
                    "intraday_levels_min_confluence_score",
                    SMART_MONEY_BASE_PARAMS.get(
                        "intraday_levels_min_confluence_score", 1
                    ),
                ),
            ),
            1,
        )
        updates["intraday_levels_min_confluence_score"] = min(2, base_confluence + 1)
        reasons.append("low_profit_consistency_tighten_risk_and_confluence")

    if avg_stop_ratio > 0.58:
        base_stop = _to_float(
            current_overrides.get(
                "global_risk_min_stop_loss_pct",
                FORCE_TRADE_OVERRIDES.get(
                    "global_risk_min_stop_loss_pct",
                    SMART_MONEY_BASE_PARAMS.get("global_risk_min_stop_loss_pct", 0.15),
                ),
            ),
            0.05,
        )
        updates["global_risk_min_stop_loss_pct"] = round(min(0.15, base_stop + 0.01), 4)
        reasons.append("stop_exit_dominance_widen_min_stop")

    if "volume_impulse_continuation" in stable_rules and positive_ratio >= 0.50:
        base_age = _to_int(
            current_overrides.get(
                "intraday_levels_momentum_break_max_age_bars",
                FORCE_TRADE_OVERRIDES.get(
                    "intraday_levels_momentum_break_max_age_bars",
                    SMART_MONEY_BASE_PARAMS.get(
                        "intraday_levels_momentum_break_max_age_bars", 3
                    ),
                ),
            ),
            3,
        )
        updates["intraday_levels_momentum_break_max_age_bars"] = min(12, base_age + 1)
        reasons.append("stable_impulse_rule_extend_momentum_break_age")

    if "poc_magnet_rotation" in stable_rules:
        updates["intraday_levels_require_recent_bounce_for_mean_reversion"] = True
        base_bounce = _to_int(
            current_overrides.get(
                "intraday_levels_recent_bounce_lookback_bars",
                FORCE_TRADE_OVERRIDES.get(
                    "intraday_levels_recent_bounce_lookback_bars",
                    SMART_MONEY_BASE_PARAMS.get(
                        "intraday_levels_recent_bounce_lookback_bars", 6
                    ),
                ),
            ),
            6,
        )
        updates["intraday_levels_recent_bounce_lookback_bars"] = max(
            3, min(10, base_bounce + 1)
        )
        reasons.append("stable_poc_rotation_rule_strengthen_bounce_filter")

    # Keep updates minimal and deterministic.
    compact = {}
    for key, value in updates.items():
        if current_overrides.get(key) != value:
            compact[key] = value
    return compact, reasons


def _build_profile_payload_from_overrides(
    overrides: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    aos_cfg: Dict[str, Any] = {}
    positioning_cfg: Dict[str, Any] = {}
    for key, value in overrides.items():
        if key in POSITIONING_PROFILE_KEYS:
            positioning_cfg[key] = value
        else:
            aos_cfg[key] = value
    return aos_cfg, positioning_cfg


def _materialize_profile_from_overrides(
    *,
    api_base: str,
    strategy_api_url: str,
    ticker: str,
    profile_name: str,
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    aos_cfg, positioning_cfg = _build_profile_payload_from_overrides(overrides)
    write_log: Dict[str, Any] = {
        "aos_update": None,
        "positioning_update": None,
        "capture": None,
    }

    if aos_cfg:
        write_log["aos_update"] = _http_json(
            "POST",
            api_base,
            "/api/aos-config/update",
            payload={"ticker": ticker.upper(), "config": aos_cfg},
            timeout=120,
        )
    if positioning_cfg:
        write_log["positioning_update"] = _http_json(
            "POST",
            api_base,
            "/api/positioning-config/update",
            payload={"ticker": ticker.upper(), "config": positioning_cfg},
            timeout=120,
        )

    capture = _http_json(
        "POST",
        api_base,
        "/api/profiles/capture",
        payload={
            "ticker": ticker.upper(),
            "profile_name": profile_name,
            "strategy_api_url": strategy_api_url,
            "set_active": True,
        },
        timeout=180,
    )
    write_log["capture"] = capture
    return write_log


def _build_knowledge_entry(
    *,
    candidate: str,
    run_payload: Dict[str, Any],
    analysis: Dict[str, Any],
    recursive_round: Optional[int],
    applied_adjustments: Optional[Dict[str, Any]],
    adjustment_reasons: Optional[List[str]],
) -> Dict[str, Any]:
    trade = analysis.get("trade_summary", {})
    non_return = analysis.get("non_returning_price_zones", {})
    poc = analysis.get("poc_magnet_and_migration", {})
    top_rules = analysis.get("rule_candidates", [])

    return {
        "generated_at": _now_utc_iso(),
        "candidate": candidate,
        "recursive_round": recursive_round,
        "run_key": analysis.get("run_key"),
        "ticker": run_payload.get("ticker"),
        "date_from": run_payload.get("date_from"),
        "date_to": run_payload.get("date_to"),
        "trade_count": _to_int(trade.get("trades"), 0),
        "win_rate_pct": trade.get("win_rate_pct"),
        "total_pnl_dollars": trade.get("total_pnl_dollars"),
        "non_return_ratio": non_return.get("non_return_ratio"),
        "poc_touch_rate": poc.get("touch_rate"),
        "poc_migration_event_count": poc.get("migration_event_count"),
        "top_time_windows_utc": [
            row.get("tod_label") for row in analysis.get("top_volume_intervals", [])[:3]
        ],
        "top_rules": [
            {
                "rule_id": row.get("rule_id"),
                "confidence": row.get("confidence"),
            }
            for row in top_rules[:5]
        ],
        "applied_adjustments": applied_adjustments or {},
        "adjustment_reasons": adjustment_reasons or [],
    }


def _append_knowledge(path: str, entry: Dict[str, Any]) -> Path:
    out = Path(path) if path else DEFAULT_KNOWLEDGE_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return out


def _load_knowledge_rows(path: str, max_rows: int = 500) -> List[Dict[str, Any]]:
    src = Path(path) if path else DEFAULT_KNOWLEDGE_PATH
    if not src.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with src.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    if max_rows > 0:
        return rows[-max_rows:]
    return rows


def _summarize_knowledge(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {
            "rows": 0,
            "rule_frequency": [],
            "common_time_windows_utc": [],
            "avg_non_return_ratio": None,
            "avg_poc_touch_rate": None,
            "avg_trade_count": None,
        }

    rule_count = Counter()
    rule_conf_sum = defaultdict(float)
    time_count = Counter()
    non_return_vals = []
    poc_touch_vals = []
    trades = []

    for row in rows:
        for t in row.get("top_time_windows_utc", []) or []:
            if t:
                time_count[str(t)] += 1

        nr = row.get("non_return_ratio")
        if isinstance(nr, (int, float)):
            non_return_vals.append(float(nr))

        pt = row.get("poc_touch_rate")
        if isinstance(pt, (int, float)):
            poc_touch_vals.append(float(pt))

        tc = row.get("trade_count")
        if isinstance(tc, (int, float)):
            trades.append(float(tc))

        for rule in row.get("top_rules", []) or []:
            if not isinstance(rule, dict):
                continue
            rid = str(rule.get("rule_id") or "")
            if not rid:
                continue
            conf = _to_float(rule.get("confidence"), 0.0)
            rule_count[rid] += 1
            rule_conf_sum[rid] += conf

    rule_rows = []
    for rid, count in rule_count.most_common(10):
        rule_rows.append(
            {
                "rule_id": rid,
                "count": count,
                "avg_confidence": round(rule_conf_sum[rid] / max(1, count), 4),
            }
        )

    return {
        "rows": len(rows),
        "rule_frequency": rule_rows,
        "common_time_windows_utc": [
            {"tod_label": tod, "count": count}
            for tod, count in time_count.most_common(10)
        ],
        "avg_non_return_ratio": (
            round(_to_float(_safe_mean(non_return_vals), 0.0), 4)
            if non_return_vals
            else None
        ),
        "avg_poc_touch_rate": (
            round(_to_float(_safe_mean(poc_touch_vals), 0.0), 4)
            if poc_touch_vals
            else None
        ),
        "avg_trade_count": (
            round(_to_float(_safe_mean(trades), 0.0), 4) if trades else None
        ),
    }


def _run_candidate(
    *,
    args: argparse.Namespace,
    variant_name: str,
    base_params: Dict[str, Any],
    user_overrides: Dict[str, Any],
    recursive_round: Optional[int] = None,
    applied_adjustments: Optional[Dict[str, Any]] = None,
    adjustment_reasons: Optional[List[str]] = None,
    date_from_override: Optional[str] = None,
    date_to_override: Optional[str] = None,
    window_label: Optional[str] = None,
) -> Dict[str, Any]:
    effective_date_from = date_from_override or args.date_from or args.date
    effective_date_to = date_to_override or args.date_to or args.date
    date_anchor = effective_date_from
    payload = _build_payload(
        ticker=args.ticker,
        date=date_anchor,
        date_from=effective_date_from,
        date_to=effective_date_to,
        strategy_api_url=args.strategy_api_url,
        base_params=base_params,
        overrides=user_overrides,
        run_tag=f"diag-{variant_name}",
    )
    print(
        f"\n[start] candidate='{variant_name}' run_id={payload['run_id']} "
        f"range={payload['date_from']}..{payload['date_to']}"
        + (f" window={window_label}" if window_label else "")
    )

    run_artifacts = _start_play_collect(
        api_base=args.api_base,
        run_payload=payload,
        poll_sec=args.poll_sec,
        timeout_sec=args.timeout_sec,
    )

    analysis = _analyze_run(
        run_artifacts=run_artifacts,
        bucket_minutes=args.bucket_minutes,
        top_buckets=args.top_buckets,
        revisit_tolerance_pct=args.revisit_tolerance_pct,
        price_bin_size_pct=args.price_bin_size_pct,
        top_price_nodes=args.top_price_nodes,
        non_return_lookahead_bars=args.non_return_lookahead_bars,
        non_return_min_move_pct=args.non_return_min_move_pct,
        non_return_top_n=args.non_return_top_n,
        poc_shift_threshold_pct=args.poc_shift_threshold_pct,
    )
    _print_analysis(analysis, title=f"DIAGNOSTIC ANALYSIS ({variant_name})")

    log_payload = {
        "generated_at": _now_utc_iso(),
        "candidate": variant_name,
        "window_label": window_label,
        "recursive_round": recursive_round,
        "applied_adjustments": applied_adjustments or {},
        "adjustment_reasons": adjustment_reasons or [],
        "run_payload": payload,
        "run_artifacts_meta": {
            "run_key": run_artifacts.get("run_key"),
            "phase": (
                run_artifacts.get("state", {}).get("phase")
                if isinstance(run_artifacts.get("state"), dict)
                else None
            ),
            "bars_endpoint_count": len(
                (run_artifacts.get("bars_payload", {}) or {}).get("bars", [])
                if isinstance(run_artifacts.get("bars_payload"), dict)
                else []
            ),
            "markers_count": len(
                run_artifacts.get("markers", [])
                if isinstance(run_artifacts.get("markers"), list)
                else []
            ),
        },
        "analysis": analysis,
    }

    candidate_log_path = _candidate_log_path(args.log_path, variant_name)
    json_log, md_log = _write_log(
        log_payload,
        candidate_log_path,
        variant_name=variant_name,
        write_markdown=not args.no_markdown_report,
    )
    print(f"[log] json={json_log}")
    if md_log is not None:
        print(f"[log] markdown={md_log}")

    knowledge_path = None
    knowledge_entry = None
    if not args.no_knowledge_store:
        knowledge_entry = _build_knowledge_entry(
            candidate=variant_name,
            run_payload=payload,
            analysis=analysis,
            recursive_round=recursive_round,
            applied_adjustments=applied_adjustments,
            adjustment_reasons=adjustment_reasons,
        )
        knowledge_path = _append_knowledge(args.knowledge_path, knowledge_entry)
        print(f"[log] knowledge={knowledge_path}")

    return {
        "candidate": variant_name,
        "window": {
            "label": window_label or f"{effective_date_from}_to_{effective_date_to}",
            "date_from": effective_date_from,
            "date_to": effective_date_to,
        },
        "analysis": analysis,
        "log_path": str(json_log),
        "markdown_path": str(md_log) if md_log else None,
        "knowledge_path": str(knowledge_path) if knowledge_path else None,
        "knowledge_entry": knowledge_entry,
        "run_payload": payload,
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="FE-synced diagnostic + recursive pattern miner with optional force-trades mode"
    )
    parser.add_argument("--ticker", default="MU", help="Ticker symbol (default: MU)")
    parser.add_argument("--date", required=True, help="Trading date (YYYY-MM-DD)")
    parser.add_argument("--date-from", help="Start date for multi-day run")
    parser.add_argument("--date-to", help="End date for multi-day run")

    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8002",
        help="Backtest runner API base URL",
    )
    parser.add_argument(
        "--strategy-api-url",
        default="http://127.0.0.1:8001",
        help="Strategy API URL (forwarded to /api/run/start)",
    )
    parser.add_argument(
        "--profile-id", default="", help="Unified profile to apply before run"
    )
    parser.add_argument(
        "--skip-profile-apply",
        action="store_true",
        help="Do not call /api/profiles/apply even if --profile-id is provided",
    )

    parser.add_argument(
        "--force-trades",
        action="store_true",
        help="Apply aggressive high-frequency overrides",
    )
    parser.add_argument(
        "--force-trade-sweep",
        type=int,
        default=0,
        help="Run N force-trade variants (max 4) and rank by trade count",
    )
    parser.add_argument(
        "--time-exit",
        type=int,
        default=None,
        help="Explicit override for time_exit_bars",
    )
    parser.add_argument("--params", nargs="*", help="Additional overrides key=value")

    parser.add_argument(
        "--bucket-minutes",
        type=int,
        default=15,
        help="Time bucket size for volume patterns",
    )
    parser.add_argument(
        "--top-buckets",
        type=int,
        default=8,
        help="How many top time buckets to analyze",
    )
    parser.add_argument(
        "--revisit-tolerance-pct",
        type=float,
        default=0.15,
        help="Price tolerance around bucket VWAP for revisit checks",
    )
    parser.add_argument(
        "--price-bin-size-pct",
        type=float,
        default=0.20,
        help="Price node bin size as pct of median price",
    )
    parser.add_argument(
        "--top-price-nodes",
        type=int,
        default=8,
        help="How many top price-volume nodes to log",
    )

    parser.add_argument(
        "--non-return-lookahead-bars",
        type=int,
        default=20,
        help="Lookahead bars before checking if anchor price returns",
    )
    parser.add_argument(
        "--non-return-min-move-pct",
        type=float,
        default=0.25,
        help="Minimum dominant move pct required to keep anchor candidate",
    )
    parser.add_argument(
        "--non-return-top-n",
        type=int,
        default=12,
        help="Max number of non-return zones to persist in top list",
    )
    parser.add_argument(
        "--poc-shift-threshold-pct",
        type=float,
        default=0.12,
        help="Minimum POC shift pct to count migration event",
    )

    parser.add_argument(
        "--recursive-rounds",
        type=int,
        default=1,
        help="Recursive loop rounds: run -> analyze -> adjust -> rerun",
    )
    parser.add_argument(
        "--recursive-min-trades",
        type=int,
        default=20,
        help="Target minimum trades for recursive adjustment heuristics",
    )
    parser.add_argument(
        "--recursive-min-positive-ratio",
        type=float,
        default=0.55,
        help="Minimum profitable-window ratio target for recursive adjustments",
    )
    parser.add_argument(
        "--robust-window-days",
        type=int,
        default=10,
        help="Evaluation window length in days for recursive robustness runs",
    )
    parser.add_argument(
        "--robust-window-count",
        type=int,
        default=3,
        help="How many rolling robustness windows to test in each recursive round",
    )
    parser.add_argument(
        "--no-robust-full-range",
        action="store_true",
        help="Exclude full date range from recursive round robustness windows",
    )
    parser.add_argument(
        "--universal-rule-min-presence",
        type=float,
        default=0.60,
        help="Minimum per-round presence ratio for a rule to be marked stable",
    )
    parser.add_argument(
        "--universal-time-window-min-presence",
        type=float,
        default=0.60,
        help="Minimum per-round presence ratio for a time window to be marked stable",
    )
    parser.add_argument(
        "--materialize-final-profile",
        action="store_true",
        help="Persist best recursive overrides into AOS/positioning and capture unified profile",
    )
    parser.add_argument(
        "--final-profile-name",
        default="",
        help="Optional explicit profile name for --materialize-final-profile",
    )
    parser.add_argument(
        "--final-profile-output",
        default="",
        help="Optional path for final profile recommendation JSON",
    )

    parser.add_argument(
        "--poll-sec", type=float, default=0.25, help="State polling interval"
    )
    parser.add_argument(
        "--timeout-sec", type=float, default=1200.0, help="Run timeout in seconds"
    )
    parser.add_argument(
        "--log-path",
        default="",
        help="Optional explicit JSON output path (suffix is auto-expanded per variant)",
    )
    parser.add_argument(
        "--knowledge-path",
        default=str(DEFAULT_KNOWLEDGE_PATH),
        help="JSONL store for abstract pattern knowledge",
    )
    parser.add_argument(
        "--no-knowledge-store",
        action="store_true",
        help="Do not append knowledge rows to the knowledge JSONL store",
    )
    parser.add_argument(
        "--no-markdown-report",
        action="store_true",
        help="Disable companion markdown report output",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    ticker = str(args.ticker or "").strip().upper()
    if not ticker:
        raise SystemExit("ticker is required")
    args.ticker = ticker

    date_from = str(args.date_from or args.date).strip()
    date_to = str(args.date_to or args.date).strip()
    args.date_from = date_from
    args.date_to = date_to

    recursive_rounds = max(1, int(args.recursive_rounds))
    args.recursive_rounds = recursive_rounds

    print("\n=== FE-Synced Recursive Diagnostic Pattern Miner ===")
    print(f"ticker={args.ticker} range={args.date_from}..{args.date_to}")
    print(f"api_base={args.api_base} strategy_api={args.strategy_api_url}")
    print(
        f"force_trades={bool(args.force_trades)} sweep={args.force_trade_sweep} "
        f"recursive_rounds={args.recursive_rounds}"
    )

    if args.profile_id and not args.skip_profile_apply:
        print(f"\n[profile] applying unified profile: {args.profile_id}")
        apply_result = _apply_unified_profile(
            api_base=args.api_base,
            ticker=args.ticker,
            profile_id=args.profile_id,
            strategy_api_url=args.strategy_api_url,
        )
        print(
            "[profile] result: "
            f"success={apply_result.get('success')} "
            f"profile={apply_result.get('profile_id')} "
            f"applied_execution={apply_result.get('applied_execution')}"
        )

    base_params = dict(SMART_MONEY_BASE_PARAMS)
    if args.force_trades:
        base_params.update(FORCE_TRADE_OVERRIDES)

    user_overrides = _parse_overrides(args.params)
    if args.time_exit is not None:
        user_overrides["time_exit_bars"] = int(args.time_exit)

    candidate_results: List[Dict[str, Any]] = []
    round_summaries: List[Dict[str, Any]] = []
    final_profile_recommendation: Optional[Dict[str, Any]] = None

    if recursive_rounds > 1:
        # In recursive mode we run one adaptive chain over multiple windows.
        if args.force_trade_sweep:
            print("[note] --force-trade-sweep ignored in recursive mode")

        evaluation_windows = _build_evaluation_windows(
            date_from=args.date_from,
            date_to=args.date_to,
            window_days=args.robust_window_days,
            window_count=args.robust_window_count,
            include_full_range=not bool(args.no_robust_full_range),
        )
        print("\n[robust] evaluation windows:")
        for idx, window in enumerate(evaluation_windows, start=1):
            print(
                f"  w{idx:02d}: {window['date_from']}..{window['date_to']} ({window['label']})"
            )

        current_overrides = dict(user_overrides)
        last_adjustments: Dict[str, Any] = {}
        last_reasons: List[str] = []

        for r in range(1, recursive_rounds + 1):
            round_name = f"recursive_r{r:02d}"
            print(f"\n[recursive] round {r}/{recursive_rounds}")
            if last_adjustments:
                print(
                    f"[recursive] applied overrides: {json.dumps(last_adjustments, ensure_ascii=True)}"
                )
                if last_reasons:
                    print(f"[recursive] reasons: {', '.join(last_reasons)}")

            round_window_results: List[Dict[str, Any]] = []
            for w_idx, window in enumerate(evaluation_windows, start=1):
                variant_name = f"{round_name}_w{w_idx:02d}"
                result = _run_candidate(
                    args=args,
                    variant_name=variant_name,
                    base_params=base_params,
                    user_overrides=current_overrides,
                    recursive_round=r,
                    applied_adjustments=last_adjustments,
                    adjustment_reasons=last_reasons,
                    date_from_override=window.get("date_from"),
                    date_to_override=window.get("date_to"),
                    window_label=window.get("label"),
                )
                candidate_results.append(result)
                round_window_results.append(result)

            round_summary = _aggregate_round_metrics(
                round_results=round_window_results,
                min_trades_target=args.recursive_min_trades,
                universal_rule_min_presence=args.universal_rule_min_presence,
                universal_time_window_min_presence=args.universal_time_window_min_presence,
            )

            next_updates: Dict[str, Any] = {}
            next_reasons: List[str] = []
            if r < recursive_rounds:
                next_updates, next_reasons = _derive_recursive_overrides_from_round(
                    round_summary=round_summary,
                    current_overrides=current_overrides,
                    min_trades=args.recursive_min_trades,
                    min_positive_ratio=args.recursive_min_positive_ratio,
                )

            round_payload = {
                "generated_at": _now_utc_iso(),
                "ticker": args.ticker,
                "round": round_name,
                "round_index": r,
                "window_count": round_summary.get("window_count"),
                "aggregate": round_summary.get("aggregate"),
                "stable_rules": round_summary.get("stable_rules"),
                "stable_time_windows_utc": round_summary.get("stable_time_windows_utc"),
                "windows": round_summary.get("windows"),
                "active_overrides": dict(current_overrides),
                "applied_adjustments": dict(last_adjustments),
                "adjustment_reasons": list(last_reasons),
                "next_override_candidate": dict(next_updates),
                "next_override_reasons": list(next_reasons),
            }
            round_json, round_md = _write_round_summary(
                round_name=round_name,
                summary_payload=round_payload,
                write_markdown=not args.no_markdown_report,
            )
            print(
                f"[round] {round_name} robust_score={round_summary.get('aggregate', {}).get('robust_score')} "
                f"avg_trades={round_summary.get('aggregate', {}).get('avg_trades')} "
                f"avg_pnl={round_summary.get('aggregate', {}).get('avg_pnl_dollars')} "
                f"positive_ratio={round_summary.get('aggregate', {}).get('positive_pnl_ratio')}"
            )
            if round_summary.get("stable_rules"):
                stable_rule_text = ", ".join(
                    f"{row.get('rule_id')}({row.get('presence_ratio')})"
                    for row in round_summary.get("stable_rules", [])[:6]
                )
                print(f"[round] stable_rules={stable_rule_text}")
            print(f"[round] summary_json={round_json}")
            if round_md is not None:
                print(f"[round] summary_md={round_md}")

            round_summaries.append(
                {
                    "round": round_name,
                    "overrides": dict(current_overrides),
                    "summary": round_summary,
                    "json_path": str(round_json),
                    "markdown_path": str(round_md) if round_md else None,
                }
            )

            if r < recursive_rounds:
                last_adjustments = next_updates
                last_reasons = next_reasons
                if next_updates:
                    current_overrides.update(next_updates)
                    print(
                        f"[recursive] next_overrides={json.dumps(next_updates, ensure_ascii=True)}"
                    )
                else:
                    print("[recursive] no further adaptive overrides suggested")

        if round_summaries:
            ranked_rounds = sorted(
                round_summaries,
                key=lambda row: (
                    _to_float(
                        row.get("summary", {}).get("aggregate", {}).get("robust_score"),
                        0.0,
                    ),
                    _to_float(
                        row.get("summary", {})
                        .get("aggregate", {})
                        .get("avg_pnl_dollars"),
                        0.0,
                    ),
                    _to_float(
                        row.get("summary", {}).get("aggregate", {}).get("avg_trades"),
                        0.0,
                    ),
                ),
                reverse=True,
            )
            print(
                "\n=== Recursive Round Ranking (robust_score, avg_pnl, avg_trades) ==="
            )
            for row in ranked_rounds:
                agg = row.get("summary", {}).get("aggregate", {})
                print(
                    f"  {row.get('round')}: robust={agg.get('robust_score')} "
                    f"avg_pnl={agg.get('avg_pnl_dollars')} avg_trades={agg.get('avg_trades')} "
                    f"positive_ratio={agg.get('positive_pnl_ratio')} summary={row.get('json_path')}"
                )

            best_round = ranked_rounds[0]
            best_round_name = str(best_round.get("round") or "recursive")
            best_round_summary = best_round.get("summary", {})
            effective_profile_overrides: Dict[str, Any] = {}
            if args.force_trades:
                effective_profile_overrides.update(FORCE_TRADE_OVERRIDES)
            effective_profile_overrides.update(user_overrides)
            effective_profile_overrides.update(best_round.get("overrides", {}))

            final_profile_recommendation = {
                "generated_at": _now_utc_iso(),
                "ticker": args.ticker,
                "source_mode": "recursive_robustness",
                "selected_round": best_round_name,
                "selected_round_summary": best_round_summary.get("aggregate", {}),
                "stable_rules": best_round_summary.get("stable_rules", []),
                "stable_time_windows_utc": best_round_summary.get(
                    "stable_time_windows_utc", []
                ),
                "recommended_overrides": effective_profile_overrides,
                "round_summaries": [
                    {
                        "round": row.get("round"),
                        "aggregate": row.get("summary", {}).get("aggregate", {}),
                        "summary_json": row.get("json_path"),
                        "summary_md": row.get("markdown_path"),
                    }
                    for row in ranked_rounds
                ],
            }

    else:
        sweep_count = max(0, int(args.force_trade_sweep))
        if args.force_trades and sweep_count > 0:
            variants = FORCE_TRADE_SWEEP_VARIANTS[
                : min(len(FORCE_TRADE_SWEEP_VARIANTS), sweep_count)
            ]
            for variant in variants:
                variant_name = str(
                    variant.get("variant_name") or f"variant_{len(candidate_results)+1}"
                )
                variant_overrides = dict(user_overrides)
                variant_overrides.update(
                    {k: v for k, v in variant.items() if k != "variant_name"}
                )
                result = _run_candidate(
                    args=args,
                    variant_name=variant_name,
                    base_params=base_params,
                    user_overrides=variant_overrides,
                    recursive_round=None,
                    applied_adjustments={},
                    adjustment_reasons=[],
                )
                candidate_results.append(result)
        else:
            result = _run_candidate(
                args=args,
                variant_name="single",
                base_params=base_params,
                user_overrides=user_overrides,
                recursive_round=None,
                applied_adjustments={},
                adjustment_reasons=[],
            )
            candidate_results.append(result)

    ranked = sorted(
        candidate_results,
        key=lambda row: _score_candidate(row.get("analysis", {})),
        reverse=True,
    )
    print("\n=== Candidate Ranking (trade_count, pnl$) ===")
    for row in ranked:
        analysis = row.get("analysis", {})
        trades, pnl = _score_candidate(analysis)
        window_label = (
            row.get("window", {}).get("label")
            if isinstance(row.get("window"), dict)
            else None
        )
        print(
            f"  {row.get('candidate')}: trades={trades} pnl={pnl:.4f} "
            f"window={window_label} json={row.get('log_path')} md={row.get('markdown_path')}"
        )

    if ranked:
        best = ranked[0]
        best_analysis = best.get("analysis", {})
        print("\n[best] candidate summary")
        print(f"  candidate={best.get('candidate')}")
        print(f"  run_key={best_analysis.get('run_key')}")
        print(f"  trades={best_analysis.get('trade_summary', {}).get('trades')}")
        print(f"  json={best.get('log_path')}")
        if best.get("markdown_path"):
            print(f"  markdown={best.get('markdown_path')}")

    if final_profile_recommendation:
        profile_out = (
            Path(args.final_profile_output)
            if str(args.final_profile_output or "").strip()
            else Path("reports")
            / "pattern_logs"
            / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{args.ticker.lower()}_profile_recommendation.json"
        )
        profile_out.parent.mkdir(parents=True, exist_ok=True)
        profile_out.write_text(
            json.dumps(final_profile_recommendation, indent=2), encoding="utf-8"
        )
        print(f"\n[profile] recommendation_json={profile_out}")

        if args.materialize_final_profile:
            capture_name = str(args.final_profile_name or "").strip()
            if not capture_name:
                capture_name = f"{args.ticker.lower()}_robust_hf_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
            print(f"[profile] materializing profile name={capture_name}")
            materialized = _materialize_profile_from_overrides(
                api_base=args.api_base,
                strategy_api_url=args.strategy_api_url,
                ticker=args.ticker,
                profile_name=capture_name,
                overrides=final_profile_recommendation.get("recommended_overrides", {}),
            )
            print(
                "[profile] capture_result="
                f"{json.dumps(materialized.get('capture', {}), ensure_ascii=True)}"
            )

    if not args.no_knowledge_store:
        knowledge_rows = _load_knowledge_rows(args.knowledge_path, max_rows=500)
        knowledge_summary = _summarize_knowledge(knowledge_rows)
        print("\n=== Knowledge Summary (recent knowledge store) ===")
        print(
            "  rows={rows} avg_trades={avg_trades} avg_non_return={avg_non_return} avg_poc_touch={avg_poc_touch}".format(
                rows=knowledge_summary.get("rows"),
                avg_trades=knowledge_summary.get("avg_trade_count"),
                avg_non_return=knowledge_summary.get("avg_non_return_ratio"),
                avg_poc_touch=knowledge_summary.get("avg_poc_touch_rate"),
            )
        )
        print("  top_rules:")
        for row in knowledge_summary.get("rule_frequency", [])[:8]:
            print(
                "    "
                f"{row.get('rule_id')} count={row.get('count')} avg_conf={row.get('avg_confidence')}"
            )
        print("  top_time_windows_utc:")
        for row in knowledge_summary.get("common_time_windows_utc", [])[:8]:
            print("    " f"{row.get('tod_label')} count={row.get('count')}")


if __name__ == "__main__":
    main()
