#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

MARKET_TZ = ZoneInfo("America/New_York")
RTH_START = time(9, 30)
RTH_END = time(16, 0)

L2_FILE_RE = re.compile(r"^MU_(\d{4}-\d{2}-\d{2})_\1\.parquet$")
PRECOMP_FILE_RE = re.compile(r"^MU_(\d{4}-\d{2}-\d{2})\.parquet$")

PERIODS: dict[str, tuple[str, str]] = {
    "2025-10": ("2025-10-01", "2025-10-31"),
    "2025-11": ("2025-11-01", "2025-11-30"),
    "2025-12": ("2025-12-01", "2025-12-31"),
    "2025-q4": ("2025-10-01", "2025-12-31"),
    "2026-01": ("2026-01-01", "2026-01-31"),
}


@dataclass(frozen=True)
class Event:
    event_date: str
    level_name: str
    approach_side: str
    outcome: str


def round_float(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(number) or np.isinf(number):
        return None
    return round(number, digits)


def qstats(series: pd.Series) -> dict[str, float | int | None]:
    if series.empty:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "p05": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "min": None,
            "max": None,
        }
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "p05": None,
            "p10": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "min": None,
            "max": None,
        }
    return {
        "count": int(len(s)),
        "mean": round_float(s.mean()),
        "median": round_float(s.median()),
        "std": round_float(s.std(ddof=0)),
        "p05": round_float(s.quantile(0.05)),
        "p10": round_float(s.quantile(0.10)),
        "p25": round_float(s.quantile(0.25)),
        "p50": round_float(s.quantile(0.50)),
        "p75": round_float(s.quantile(0.75)),
        "p90": round_float(s.quantile(0.90)),
        "p95": round_float(s.quantile(0.95)),
        "p99": round_float(s.quantile(0.99)),
        "min": round_float(s.min()),
        "max": round_float(s.max()),
    }


def in_period(day: str, start_day: str, end_day: str) -> bool:
    return start_day <= day <= end_day


def list_l2_days(l2_dir: Path, start_day: str, end_day: str) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for path in sorted(l2_dir.glob("MU_*.parquet")):
        match = L2_FILE_RE.match(path.name)
        if not match:
            continue
        day = match.group(1)
        if in_period(day, start_day, end_day):
            items.append((day, path))
    return items


def list_precomputed_days(
    pre_dir: Path, start_day: str, end_day: str
) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for path in sorted(pre_dir.glob("MU_*.parquet")):
        match = PRECOMP_FILE_RE.match(path.name)
        if not match:
            continue
        day = match.group(1)
        if in_period(day, start_day, end_day):
            items.append((day, path))
    return items


def load_trade_bars_1m(
    l2_files: list[tuple[str, Path]],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, Any]]:
    daily_frames: list[pd.DataFrame] = []
    bars_by_day: dict[str, pd.DataFrame] = {}
    rows_total = 0
    files_with_trades = 0

    for day, path in l2_files:
        columns = ["ts_event", "action", "price", "size"]
        raw = pd.read_parquet(path, columns=columns)
        rows_total += int(len(raw))
        if raw.empty:
            continue

        action = raw["action"].astype(str).str.upper().str.strip()
        trades = raw.loc[action == "T", ["ts_event", "price", "size"]].copy()
        if trades.empty:
            continue

        ts_utc = pd.to_datetime(trades["ts_event"], errors="coerce", utc=True)
        trades["ts_ny"] = ts_utc.dt.tz_convert(MARKET_TZ)
        trades["price"] = pd.to_numeric(trades["price"], errors="coerce")
        trades["size"] = pd.to_numeric(trades["size"], errors="coerce")
        trades = trades.dropna(subset=["ts_ny", "price", "size"])
        if trades.empty:
            continue

        trades = trades[(trades["price"] > 0) & (trades["size"] > 0)]
        if trades.empty:
            continue

        tod = trades["ts_ny"].dt.time
        trades = trades[(tod >= RTH_START) & (tod < RTH_END)]
        if trades.empty:
            continue

        trades["minute_ny"] = trades["ts_ny"].dt.floor("min")
        grouped = trades.groupby("minute_ny", sort=True)
        bars = grouped.agg(
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            volume=("size", "sum"),
            trade_count=("size", "count"),
        ).reset_index()
        if bars.empty:
            continue

        bars["date"] = bars["minute_ny"].dt.date.astype(str)
        bars["range_pct"] = ((bars["high"] - bars["low"]) / bars["open"]) * 100.0
        bars = bars.sort_values("minute_ny").reset_index(drop=True)

        files_with_trades += 1
        daily_frames.append(bars)
        bars_by_day[day] = bars.copy()

    if daily_frames:
        bars_1m = (
            pd.concat(daily_frames, ignore_index=True)
            .sort_values("minute_ny")
            .reset_index(drop=True)
        )
    else:
        bars_1m = pd.DataFrame(
            columns=[
                "minute_ny",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "trade_count",
                "date",
                "range_pct",
            ]
        )

    coverage = {
        "l2_files_total": len(l2_files),
        "l2_files_with_trades": files_with_trades,
        "l2_rows_loaded": rows_total,
        "bars_1m_rows": int(len(bars_1m)),
        "bars_1m_days": int(bars_1m["date"].nunique()) if not bars_1m.empty else 0,
    }
    return bars_1m, bars_by_day, coverage


def load_precomputed_minutes(
    pre_files: list[tuple[str, Path]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    rows_total = 0

    for day, path in pre_files:
        raw = pd.read_parquet(
            path,
            columns=[
                "minute_key",
                "l2_book_pressure",
                "l2_signed_aggression",
                "l2_delta",
                "l2_volume",
            ],
        )
        if raw.empty:
            continue

        rows_total += int(len(raw))
        minute_ts = pd.to_datetime(
            raw["minute_key"], unit="m", utc=True, errors="coerce"
        )
        raw["minute_ny"] = minute_ts.dt.tz_convert(MARKET_TZ)
        tod = raw["minute_ny"].dt.time
        raw = raw[(tod >= RTH_START) & (tod < RTH_END)].copy()
        if raw.empty:
            continue

        raw["date"] = raw["minute_ny"].dt.date.astype(str)
        frames.append(raw)

    if frames:
        l2_1m = (
            pd.concat(frames, ignore_index=True)
            .sort_values("minute_ny")
            .reset_index(drop=True)
        )
    else:
        l2_1m = pd.DataFrame(
            columns=[
                "minute_key",
                "l2_book_pressure",
                "l2_signed_aggression",
                "l2_delta",
                "l2_volume",
                "minute_ny",
                "date",
            ]
        )

    coverage = {
        "precomputed_files_total": len(pre_files),
        "precomputed_rows_loaded": rows_total,
        "precomputed_rows_rth": int(len(l2_1m)),
        "precomputed_days_rth": int(l2_1m["date"].nunique()) if not l2_1m.empty else 0,
    }
    return l2_1m, coverage


def build_5m_from_1m(bars_1m: pd.DataFrame) -> pd.DataFrame:
    if bars_1m.empty:
        return pd.DataFrame(
            columns=[
                "minute_ny",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "trade_count",
                "date",
                "range_pct",
            ]
        )

    out: list[pd.DataFrame] = []
    for day, day_df in bars_1m.groupby("date", sort=True):
        block = day_df.sort_values("minute_ny").set_index("minute_ny")
        resampled = block.resample("5min", label="left", closed="left").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            trade_count=("trade_count", "sum"),
        )
        resampled = resampled.dropna(
            subset=["open", "high", "low", "close"]
        ).reset_index()
        if resampled.empty:
            continue
        resampled["date"] = day
        resampled["range_pct"] = (
            (resampled["high"] - resampled["low"]) / resampled["open"]
        ) * 100.0
        out.append(resampled)
    if out:
        return (
            pd.concat(out, ignore_index=True)
            .sort_values("minute_ny")
            .reset_index(drop=True)
        )
    return pd.DataFrame(
        columns=[
            "minute_ny",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "trade_count",
            "date",
            "range_pct",
        ]
    )


def zigzag_pivots(prices: np.ndarray, reversal_pct: float) -> list[tuple[int, float]]:
    if len(prices) < 2:
        return []
    pivot_idx = 0
    pivot_price = float(prices[0])
    direction = 0
    extreme_idx = pivot_idx
    extreme_price = pivot_price
    pivots: list[tuple[int, float]] = [(pivot_idx, pivot_price)]

    for i in range(1, len(prices)):
        price = float(prices[i])
        if price <= 0 or pivot_price <= 0:
            continue

        if direction == 0:
            up_move = ((price - pivot_price) / pivot_price) * 100.0
            down_move = ((pivot_price - price) / pivot_price) * 100.0
            if up_move >= reversal_pct:
                direction = 1
                extreme_idx, extreme_price = i, price
            elif down_move >= reversal_pct:
                direction = -1
                extreme_idx, extreme_price = i, price
            else:
                if price > extreme_price:
                    extreme_idx, extreme_price = i, price
                elif price < extreme_price:
                    extreme_idx, extreme_price = i, price
            continue

        if direction == 1:
            if price > extreme_price:
                extreme_idx, extreme_price = i, price
                continue
            retrace = (
                ((extreme_price - price) / extreme_price) * 100.0
                if extreme_price > 0
                else 0.0
            )
            if retrace >= reversal_pct:
                pivots.append((extreme_idx, extreme_price))
                pivot_idx, pivot_price = extreme_idx, extreme_price
                direction = -1
                extreme_idx, extreme_price = i, price
            continue

        if direction == -1:
            if price < extreme_price:
                extreme_idx, extreme_price = i, price
                continue
            rebound = (
                ((price - extreme_price) / extreme_price) * 100.0
                if extreme_price > 0
                else 0.0
            )
            if rebound >= reversal_pct:
                pivots.append((extreme_idx, extreme_price))
                pivot_idx, pivot_price = extreme_idx, extreme_price
                direction = 1
                extreme_idx, extreme_price = i, price

    if pivots and pivots[-1][0] != extreme_idx:
        pivots.append((extreme_idx, extreme_price))
    return pivots


def compute_pullback_profile(
    bars_1m: pd.DataFrame,
    reversal_pct: float = 0.35,
    min_trend_pct: float = 2.0,
    min_continuation_pct: float = 0.5,
) -> dict[str, Any]:
    pullback_ratios: list[float] = []
    pullback_abs_pct: list[float] = []
    leg1_moves: list[float] = []
    continuation_moves: list[float] = []

    for _, day_df in bars_1m.groupby("date", sort=True):
        closes = day_df.sort_values("minute_ny")["close"].to_numpy(dtype=float)
        if len(closes) < 20:
            continue
        pivots = zigzag_pivots(closes, reversal_pct=reversal_pct)
        if len(pivots) < 4:
            continue

        for i in range(len(pivots) - 3):
            a_idx, a_price = pivots[i]
            b_idx, b_price = pivots[i + 1]
            c_idx, c_price = pivots[i + 2]
            d_idx, d_price = pivots[i + 3]
            if min(a_price, b_price, c_price, d_price) <= 0:
                continue
            if not (a_idx < b_idx < c_idx < d_idx):
                continue

            leg1 = ((b_price - a_price) / a_price) * 100.0
            leg2 = ((c_price - b_price) / b_price) * 100.0
            leg3 = ((d_price - c_price) / c_price) * 100.0

            if abs(leg1) < min_trend_pct:
                continue
            if abs(leg3) < min_continuation_pct:
                continue
            if np.sign(leg1) == 0 or np.sign(leg2) == 0 or np.sign(leg3) == 0:
                continue
            if np.sign(leg1) != np.sign(leg3):
                continue
            if np.sign(leg2) == np.sign(leg1):
                continue

            ratio = abs(leg2) / abs(leg1)
            pullback_ratios.append(ratio)
            pullback_abs_pct.append(abs(leg2))
            leg1_moves.append(abs(leg1))
            continuation_moves.append(abs(leg3))

    ratio_series = pd.Series(pullback_ratios, dtype=float)
    leg1_series = pd.Series(leg1_moves, dtype=float)
    cont_series = pd.Series(continuation_moves, dtype=float)
    abs_pb_series = pd.Series(pullback_abs_pct, dtype=float)

    if ratio_series.empty:
        return {
            "criteria": {
                "zigzag_reversal_pct": reversal_pct,
                "min_initial_trend_pct": min_trend_pct,
                "min_continuation_pct": min_continuation_pct,
            },
            "trend_sequences": 0,
            "pullback_ratio": qstats(pd.Series(dtype=float)),
            "pullback_abs_move_pct": qstats(pd.Series(dtype=float)),
            "initial_leg_pct": qstats(pd.Series(dtype=float)),
            "continuation_leg_pct": qstats(pd.Series(dtype=float)),
            "share_pullback_le_30pct_of_leg": None,
            "share_pullback_le_50pct_of_leg": None,
            "suggested_trailing_pullback_budget_pct_of_leg": None,
            "suggested_break_even_activation_move_pct": None,
        }

    trailing_budget = ratio_series.quantile(0.75) * 100.0
    be_trigger = max(0.5, leg1_series.quantile(0.25) * 0.5)
    return {
        "criteria": {
            "zigzag_reversal_pct": reversal_pct,
            "min_initial_trend_pct": min_trend_pct,
            "min_continuation_pct": min_continuation_pct,
        },
        "trend_sequences": int(len(ratio_series)),
        "pullback_ratio": qstats(ratio_series),
        "pullback_abs_move_pct": qstats(abs_pb_series),
        "initial_leg_pct": qstats(leg1_series),
        "continuation_leg_pct": qstats(cont_series),
        "share_pullback_le_30pct_of_leg": round_float(
            (ratio_series <= 0.30).mean() * 100.0
        ),
        "share_pullback_le_50pct_of_leg": round_float(
            (ratio_series <= 0.50).mean() * 100.0
        ),
        "suggested_trailing_pullback_budget_pct_of_leg": round_float(trailing_budget),
        "suggested_break_even_activation_move_pct": round_float(be_trigger),
    }


def compute_phase1(bars_1m: pd.DataFrame) -> dict[str, Any]:
    bars_5m = build_5m_from_1m(bars_1m)
    one_min = (
        qstats(bars_1m["range_pct"])
        if "range_pct" in bars_1m
        else qstats(pd.Series(dtype=float))
    )
    five_min = (
        qstats(bars_5m["range_pct"])
        if "range_pct" in bars_5m
        else qstats(pd.Series(dtype=float))
    )

    sl_from_mean = None
    sl_from_p75 = None
    sl_recommended = None
    if five_min["mean"] is not None:
        sl_from_mean = round_float(float(five_min["mean"]) * 1.25)
    if five_min["p75"] is not None:
        sl_from_p75 = round_float(float(five_min["p75"]))
    if sl_from_mean is not None or sl_from_p75 is not None:
        sl_recommended = round_float(
            max(v for v in [sl_from_mean, sl_from_p75] if v is not None)
        )

    return {
        "sample": {
            "trading_days": int(bars_1m["date"].nunique()) if not bars_1m.empty else 0,
            "bars_1m": int(len(bars_1m)),
            "bars_5m": int(len(bars_5m)),
        },
        "volatility": {
            "range_pct_1m": one_min,
            "range_pct_5m": five_min,
            "suggested_sl_floor_pct": {
                "from_5m_mean_x1_25": sl_from_mean,
                "from_5m_p75": sl_from_p75,
                "recommended_min_sl_pct": sl_recommended,
            },
        },
        "pullback_profile": compute_pullback_profile(bars_1m),
    }


def compute_phase2(l2_1m: pd.DataFrame) -> dict[str, Any]:
    if l2_1m.empty:
        empty = qstats(pd.Series(dtype=float))
        return {
            "sample": {"minutes": 0, "trading_days": 0},
            "book_pressure": {"raw": empty, "zscore": empty},
            "signed_aggression": {"raw": empty, "zscore": empty},
            "delta_baseline": {
                "raw_delta": empty,
                "abs_delta": empty,
                "share_abs_delta_ge_2200_pct": None,
                "share_pos_delta_ge_2200_pct": None,
                "share_neg_delta_le_minus2200_pct": None,
                "suggested_min_delta_abs_soft_p90": None,
                "suggested_min_delta_abs_hard_p95": None,
            },
            "hard_block_hints": {
                "book_pressure_z_p95": None,
                "book_pressure_z_p05": None,
                "signed_aggression_z_p95": None,
                "signed_aggression_z_p05": None,
            },
        }

    bp = pd.to_numeric(l2_1m["l2_book_pressure"], errors="coerce").dropna()
    aggr = pd.to_numeric(l2_1m["l2_signed_aggression"], errors="coerce").dropna()
    delta = pd.to_numeric(l2_1m["l2_delta"], errors="coerce").dropna()
    abs_delta = delta.abs()

    bp_std = float(bp.std(ddof=0)) if len(bp) else 0.0
    aggr_std = float(aggr.std(ddof=0)) if len(aggr) else 0.0
    bp_z = (
        ((bp - bp.mean()) / bp_std)
        if bp_std > 0
        else pd.Series(np.zeros(len(bp)), index=bp.index)
    )
    aggr_z = (
        ((aggr - aggr.mean()) / aggr_std)
        if aggr_std > 0
        else pd.Series(np.zeros(len(aggr)), index=aggr.index)
    )

    return {
        "sample": {
            "minutes": int(len(l2_1m)),
            "trading_days": int(l2_1m["date"].nunique()),
        },
        "book_pressure": {
            "raw": qstats(bp),
            "zscore": qstats(bp_z),
        },
        "signed_aggression": {
            "raw": qstats(aggr),
            "zscore": qstats(aggr_z),
        },
        "delta_baseline": {
            "raw_delta": qstats(delta),
            "abs_delta": qstats(abs_delta),
            "share_abs_delta_ge_2200_pct": round_float(
                (abs_delta >= 2200).mean() * 100.0
            ),
            "share_pos_delta_ge_2200_pct": round_float((delta >= 2200).mean() * 100.0),
            "share_neg_delta_le_minus2200_pct": round_float(
                (delta <= -2200).mean() * 100.0
            ),
            "suggested_min_delta_abs_soft_p90": round_float(abs_delta.quantile(0.90)),
            "suggested_min_delta_abs_hard_p95": round_float(abs_delta.quantile(0.95)),
        },
        "hard_block_hints": {
            "book_pressure_z_p95": round_float(bp_z.quantile(0.95)),
            "book_pressure_z_p05": round_float(bp_z.quantile(0.05)),
            "signed_aggression_z_p95": round_float(aggr_z.quantile(0.95)),
            "signed_aggression_z_p05": round_float(aggr_z.quantile(0.05)),
        },
    }


def compute_phase3(bars_1m: pd.DataFrame) -> dict[str, Any]:
    if bars_1m.empty:
        return {
            "sample": {"minutes": 0, "trading_days": 0},
            "bucket_30m": [],
            "big_move_definition": {
                "forward_window_minutes": 30,
                "threshold_quantile": 0.90,
                "abs_return_threshold_pct": None,
            },
            "big_move_concentration": {
                "share_of_big_moves_before_11_30_pct": None,
                "time_for_70pct_big_moves": None,
            },
            "regime_proxy": {
                "method": "ER30 on 1m close, TRENDING if ER>=0.35 else CHOPPY",
                "samples": 0,
                "trending_pct": None,
                "choppy_pct": None,
            },
        }

    work = bars_1m.copy().sort_values("minute_ny").reset_index(drop=True)
    work["bucket"] = work["minute_ny"].dt.floor("30min").dt.strftime("%H:%M")
    total_volume = float(work["volume"].sum()) if len(work) else 0.0

    big_move_rows: list[pd.DataFrame] = []
    regime_rows: list[pd.DataFrame] = []
    for _, day_df in work.groupby("date", sort=True):
        day_df = day_df.sort_values("minute_ny").copy()
        day_df["fwd30_ret_pct"] = (
            (day_df["close"].shift(-30) / day_df["close"]) - 1.0
        ) * 100.0
        big_move_rows.append(day_df[["minute_ny", "bucket", "fwd30_ret_pct"]])

        delta_abs = day_df["close"].diff().abs()
        net_move = (day_df["close"] - day_df["close"].shift(30)).abs()
        noise = delta_abs.rolling(30).sum()
        er = net_move / noise.replace(0, np.nan)
        regime_rows.append(pd.DataFrame({"er30": er}))

    big_df = pd.concat(big_move_rows, ignore_index=True)
    valid_big = big_df.dropna(subset=["fwd30_ret_pct"]).copy()
    threshold = (
        valid_big["fwd30_ret_pct"].abs().quantile(0.90)
        if not valid_big.empty
        else np.nan
    )
    if np.isnan(threshold):
        threshold = 0.0
    valid_big["is_big_move"] = valid_big["fwd30_ret_pct"].abs() >= threshold

    bucket_agg = work.groupby("bucket", sort=True).agg(
        volume_sum=("volume", "sum"),
        avg_range_pct_1m=("range_pct", "mean"),
        median_range_pct_1m=("range_pct", "median"),
        bars=("bucket", "count"),
    )
    big_counts = valid_big.groupby("bucket", sort=True)["is_big_move"].sum().astype(int)
    bucket_agg["big_move_count"] = big_counts.reindex(bucket_agg.index, fill_value=0)
    big_total = int(bucket_agg["big_move_count"].sum())
    bucket_agg["big_move_share_pct"] = (
        (bucket_agg["big_move_count"] / big_total) * 100.0 if big_total > 0 else 0.0
    )
    bucket_agg["volume_share_pct"] = (
        (bucket_agg["volume_sum"] / total_volume) * 100.0 if total_volume > 0 else 0.0
    )
    bucket_agg = bucket_agg.reset_index()

    before_1130 = bucket_agg[bucket_agg["bucket"] < "11:30"]["big_move_count"].sum()
    share_before_1130 = (before_1130 / big_total) * 100.0 if big_total > 0 else None

    cum = bucket_agg.sort_values("bucket").copy()
    cum["cum_share"] = cum["big_move_share_pct"].cumsum()
    time_for_70 = None
    hit = cum[cum["cum_share"] >= 70.0]
    if not hit.empty:
        time_for_70 = str(hit.iloc[0]["bucket"])

    er_df = pd.concat(regime_rows, ignore_index=True)
    er_series = pd.to_numeric(er_df["er30"], errors="coerce").dropna()
    trending_pct = (
        round_float((er_series >= 0.35).mean() * 100.0) if not er_series.empty else None
    )
    choppy_pct = (
        round_float((er_series < 0.35).mean() * 100.0) if not er_series.empty else None
    )

    bucket_rows = []
    for row in bucket_agg.sort_values("bucket").itertuples(index=False):
        bucket_rows.append(
            {
                "bucket": str(row.bucket),
                "volume_share_pct": round_float(row.volume_share_pct),
                "avg_range_pct_1m": round_float(row.avg_range_pct_1m),
                "median_range_pct_1m": round_float(row.median_range_pct_1m),
                "big_move_count": int(row.big_move_count),
                "big_move_share_pct": round_float(row.big_move_share_pct),
            }
        )

    return {
        "sample": {
            "minutes": int(len(work)),
            "trading_days": int(work["date"].nunique()),
        },
        "bucket_30m": bucket_rows,
        "big_move_definition": {
            "forward_window_minutes": 30,
            "threshold_quantile": 0.90,
            "abs_return_threshold_pct": round_float(threshold),
        },
        "big_move_concentration": {
            "share_of_big_moves_before_11_30_pct": (
                round_float(share_before_1130)
                if share_before_1130 is not None
                else None
            ),
            "time_for_70pct_big_moves": time_for_70,
        },
        "regime_proxy": {
            "method": "ER30 on 1m close, TRENDING if ER>=0.35 else CHOPPY",
            "samples": int(len(er_series)),
            "trending_pct": trending_pct,
            "choppy_pct": choppy_pct,
        },
    }


def compute_daily_levels(
    day_df: pd.DataFrame, price_bin: float = 0.05, value_area_pct: float = 0.70
) -> dict[str, float] | None:
    if day_df.empty:
        return None
    typical_price = (day_df["high"] + day_df["low"] + day_df["close"]) / 3.0
    bins = (np.round(typical_price / price_bin) * price_bin).astype(float)
    profile = (
        pd.DataFrame({"bin": bins, "vol": day_df["volume"]})
        .groupby("bin", sort=True)["vol"]
        .sum()
    )
    if profile.empty:
        return None

    prices = profile.index.to_numpy(dtype=float)
    vols = profile.to_numpy(dtype=float)
    poc_idx = int(np.argmax(vols))
    poc = float(prices[poc_idx])
    total = float(vols.sum())
    target = total * value_area_pct

    low_i = poc_idx
    high_i = poc_idx
    acc = float(vols[poc_idx])
    while acc < target and (low_i > 0 or high_i < len(vols) - 1):
        left_vol = vols[low_i - 1] if low_i > 0 else -1.0
        right_vol = vols[high_i + 1] if high_i < len(vols) - 1 else -1.0
        if right_vol >= left_vol:
            high_i += 1
            acc += float(vols[high_i])
        else:
            low_i -= 1
            acc += float(vols[low_i])

    return {
        "poc": round_float(poc, 4),
        "val": round_float(float(prices[low_i]), 4),
        "vah": round_float(float(prices[high_i]), 4),
    }


def classify_touch_outcome(
    day_df: pd.DataFrame, touch_idx: int, level_price: float, approach_side: str
) -> str:
    up_target = level_price * 1.005
    down_target = level_price * 0.995
    horizon_end = min(len(day_df), touch_idx + 1 + 60)
    future = day_df.iloc[touch_idx + 1 : horizon_end]
    if future.empty:
        return "undecided"

    for row in future.itertuples(index=False):
        hit_up = float(row.high) >= up_target
        hit_down = float(row.low) <= down_target
        if not hit_up and not hit_down:
            continue
        if approach_side == "below":
            if hit_up and not hit_down:
                return "breakout"
            if hit_down and not hit_up:
                return "bounce"
            return "breakout" if float(row.close) >= level_price else "bounce"
        if hit_down and not hit_up:
            return "breakout"
        if hit_up and not hit_down:
            return "bounce"
        return "breakout" if float(row.close) <= level_price else "bounce"
    return "undecided"


def build_level_events(all_bars_by_day: dict[str, pd.DataFrame]) -> list[Event]:
    ordered_days = sorted(all_bars_by_day.keys())
    levels_by_day: dict[str, dict[str, float] | None] = {
        day: compute_daily_levels(all_bars_by_day[day]) for day in ordered_days
    }
    events: list[Event] = []

    for idx in range(1, len(ordered_days)):
        day = ordered_days[idx]
        prev_day = ordered_days[idx - 1]
        prev_levels = levels_by_day.get(prev_day)
        if not prev_levels:
            continue

        day_df = all_bars_by_day[day].sort_values("minute_ny").reset_index(drop=True)
        if day_df.empty:
            continue

        for level_name in ("poc", "vah", "val"):
            level_price = prev_levels.get(level_name)
            if not level_price or level_price <= 0:
                continue
            last_touch_idx = -10_000
            for bar_idx, bar in enumerate(day_df.itertuples(index=False)):
                if bar_idx - last_touch_idx < 15:
                    continue
                if not (float(bar.low) <= level_price <= float(bar.high)):
                    continue
                if bar_idx == 0:
                    continue
                prev_close = float(day_df.iloc[bar_idx - 1]["close"])
                if prev_close == level_price:
                    continue
                approach_side = "below" if prev_close < level_price else "above"
                outcome = classify_touch_outcome(
                    day_df, bar_idx, level_price, approach_side
                )
                events.append(
                    Event(
                        event_date=day,
                        level_name=level_name,
                        approach_side=approach_side,
                        outcome=outcome,
                    )
                )
                last_touch_idx = bar_idx
    return events


def compute_phase4(events: list[Event], start_day: str, end_day: str) -> dict[str, Any]:
    selected = [e for e in events if in_period(e.event_date, start_day, end_day)]
    by_level: dict[str, dict[str, Any]] = {}
    for level_name in ("poc", "vah", "val"):
        subset = [e for e in selected if e.level_name == level_name]
        breakout = sum(1 for e in subset if e.outcome == "breakout")
        bounce = sum(1 for e in subset if e.outcome == "bounce")
        undecided = sum(1 for e in subset if e.outcome == "undecided")
        resolved = breakout + bounce
        by_level[level_name] = {
            "touches_total": len(subset),
            "resolved": resolved,
            "breakout_count": breakout,
            "bounce_count": bounce,
            "undecided_count": undecided,
            "breakout_rate_pct": (
                round_float((breakout / resolved) * 100.0) if resolved > 0 else None
            ),
            "bounce_rate_pct": (
                round_float((bounce / resolved) * 100.0) if resolved > 0 else None
            ),
        }

    poc = by_level["poc"]
    poc_hint: str
    if poc["resolved"] == 0:
        poc_hint = "insufficient_events"
    elif (poc["bounce_rate_pct"] or 0) >= 60.0:
        poc_hint = "favor_bounce_mean_reversion"
    elif (poc["breakout_rate_pct"] or 0) >= 60.0:
        poc_hint = "favor_breakout_continuation"
    else:
        poc_hint = "mixed_reactions_no_edge"

    return {
        "event_definition": {
            "trigger": "touch of prior-day level by 1m bar (low<=level<=high)",
            "dedup_cooldown_bars": 15,
            "outcome_window_bars": 60,
            "move_threshold_pct": 0.5,
        },
        "levels": by_level,
        "poc_strategy_hint": poc_hint,
    }


def slice_bars_period(
    all_bars_1m: pd.DataFrame, start_day: str, end_day: str
) -> pd.DataFrame:
    if all_bars_1m.empty:
        return all_bars_1m.copy()
    return all_bars_1m[
        (all_bars_1m["date"] >= start_day) & (all_bars_1m["date"] <= end_day)
    ].copy()


def slice_l2_period(
    all_l2_1m: pd.DataFrame, start_day: str, end_day: str
) -> pd.DataFrame:
    if all_l2_1m.empty:
        return all_l2_1m.copy()
    return all_l2_1m[
        (all_l2_1m["date"] >= start_day) & (all_l2_1m["date"] <= end_day)
    ].copy()


def build_period_result(
    period_key: str,
    all_bars_1m: pd.DataFrame,
    all_l2_1m: pd.DataFrame,
    events: list[Event],
) -> dict[str, Any]:
    start_day, end_day = PERIODS[period_key]
    bars = slice_bars_period(all_bars_1m, start_day, end_day)
    l2m = slice_l2_period(all_l2_1m, start_day, end_day)
    return {
        "range": {"start": start_day, "end": end_day},
        "phase1": compute_phase1(bars),
        "phase2": compute_phase2(l2m),
        "phase3": compute_phase3(bars),
        "phase4": compute_phase4(events, start_day, end_day),
    }


def md_header_line() -> str:
    return "| Period | 1m mean | 1m p95 | 5m mean | 5m p95 | SL min reco | Pullback median | Pullback p75 |"


def md_separator_line() -> str:
    return "|---|---:|---:|---:|---:|---:|---:|---:|"


def fmt(v: Any, digits: int = 3) -> str:
    if v is None:
        return "n/a"
    try:
        value = float(v)
    except (TypeError, ValueError):
        return "n/a"
    if np.isnan(value) or np.isinf(value):
        return "n/a"
    return f"{value:.{digits}f}"


def build_markdown(result: dict[str, Any]) -> str:
    periods = result["periods"]
    order = ["2025-10", "2025-11", "2025-12", "2025-q4", "2026-01"]
    lines: list[str] = []
    lines.append("# MU 4-Phase Analysis")
    lines.append("")
    lines.append(
        "Coverage: October 2025, November 2025, December 2025, Q4 aggregate, January 2026."
    )
    lines.append("")
    lines.append("## Faza 1 - Volatilita a Pullback Profil")
    lines.append("")
    lines.append(md_header_line())
    lines.append(md_separator_line())
    for key in order:
        p = periods[key]["phase1"]
        lines.append(
            "| "
            + key
            + " | "
            + fmt(p["volatility"]["range_pct_1m"]["mean"])
            + " | "
            + fmt(p["volatility"]["range_pct_1m"]["p95"])
            + " | "
            + fmt(p["volatility"]["range_pct_5m"]["mean"])
            + " | "
            + fmt(p["volatility"]["range_pct_5m"]["p95"])
            + " | "
            + fmt(p["volatility"]["suggested_sl_floor_pct"]["recommended_min_sl_pct"])
            + " | "
            + fmt(
                p["pullback_profile"]["pullback_ratio"]["p50"] * 100.0
                if p["pullback_profile"]["pullback_ratio"]["p50"] is not None
                else None
            )
            + "% | "
            + fmt(
                p["pullback_profile"]["pullback_ratio"]["p75"] * 100.0
                if p["pullback_profile"]["pullback_ratio"]["p75"] is not None
                else None
            )
            + "% |"
        )

    lines.append("")
    lines.append("## Faza 2 - Distribucia L2")
    lines.append("")
    lines.append(
        "| Period | BP z p95 | BP z p05 | Agg z p95 | |Delta| median | |Delta| p95 | Share |Delta|>=2200 |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for key in order:
        p = periods[key]["phase2"]
        lines.append(
            "| "
            + key
            + " | "
            + fmt(p["hard_block_hints"]["book_pressure_z_p95"])
            + " | "
            + fmt(p["hard_block_hints"]["book_pressure_z_p05"])
            + " | "
            + fmt(p["hard_block_hints"]["signed_aggression_z_p95"])
            + " | "
            + fmt(p["delta_baseline"]["abs_delta"]["median"], 1)
            + " | "
            + fmt(p["delta_baseline"]["abs_delta"]["p95"], 1)
            + " | "
            + fmt(p["delta_baseline"]["share_abs_delta_ge_2200_pct"])
            + "% |"
        )

    lines.append("")
    lines.append("## Faza 3 - Cas dna a rezimy")
    lines.append("")
    lines.append(
        "| Period | 70% big moves do | Share big moves <11:30 | Trending | Choppy |"
    )
    lines.append("|---|---|---:|---:|---:|")
    for key in order:
        p = periods[key]["phase3"]
        lines.append(
            "| "
            + key
            + " | "
            + str(p["big_move_concentration"]["time_for_70pct_big_moves"] or "n/a")
            + " | "
            + fmt(p["big_move_concentration"]["share_of_big_moves_before_11_30_pct"])
            + "% | "
            + fmt(p["regime_proxy"]["trending_pct"])
            + "% | "
            + fmt(p["regime_proxy"]["choppy_pct"])
            + "% |"
        )

    lines.append("")
    lines.append("Top 30m buckets by big move share (Q4):")
    q4_top = sorted(
        periods["2025-q4"]["phase3"]["bucket_30m"],
        key=lambda x: x["big_move_share_pct"] or 0.0,
        reverse=True,
    )[:5]
    lines.append("")
    lines.append("| Bucket | Big move share | Volume share | Avg 1m range |")
    lines.append("|---|---:|---:|---:|")
    for row in q4_top:
        lines.append(
            "| "
            + row["bucket"]
            + " | "
            + fmt(row["big_move_share_pct"])
            + "% | "
            + fmt(row["volume_share_pct"])
            + "% | "
            + fmt(row["avg_range_pct_1m"])
            + "% |"
        )

    lines.append("")
    lines.append("## Faza 4 - Validacia urovni (POC/VAH/VAL)")
    lines.append("")
    lines.append(
        "| Period | Level | Touches | Resolved | Bounce rate | Breakout rate |"
    )
    lines.append("|---|---|---:|---:|---:|---:|")
    for key in order:
        p4 = periods[key]["phase4"]["levels"]
        for lvl in ("poc", "vah", "val"):
            level = p4[lvl]
            lines.append(
                "| "
                + key
                + " | "
                + lvl.upper()
                + " | "
                + str(level["touches_total"])
                + " | "
                + str(level["resolved"])
                + " | "
                + fmt(level["bounce_rate_pct"])
                + "% | "
                + fmt(level["breakout_rate_pct"])
                + "% |"
            )

    lines.append("")
    lines.append("POC strategy hints:")
    for key in order:
        hint = periods[key]["phase4"]["poc_strategy_hint"]
        lines.append(f"- {key}: {hint}")
    lines.append("")
    lines.append(
        "Detailed per-bucket heatmaps and full metric distributions are in the JSON output."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="4-phase MU analysis for Oct-Nov-Dec + Jan."
    )
    parser.add_argument("--l2-dir", type=Path, default=Path("data/l2"))
    parser.add_argument(
        "--precomputed-dir", type=Path, default=Path("data/l2_precomputed")
    )
    parser.add_argument("--start-day", default="2025-10-01")
    parser.add_argument("--end-day", default="2026-01-31")
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path("reports/mu_four_phase_analysis_2025-10_2026-01.json"),
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path("reports/mu_four_phase_analysis_2025-10_2026-01.md"),
    )
    args = parser.parse_args()

    start_day = args.start_day
    end_day = args.end_day

    l2_files = list_l2_days(args.l2_dir, start_day, end_day)
    pre_files = list_precomputed_days(args.precomputed_dir, start_day, end_day)

    all_bars_1m, bars_by_day, bars_cov = load_trade_bars_1m(l2_files)
    all_l2_1m, l2_cov = load_precomputed_minutes(pre_files)
    events = build_level_events(bars_by_day)

    periods: dict[str, Any] = {}
    for key in ("2025-10", "2025-11", "2025-12", "2025-q4", "2026-01"):
        periods[key] = build_period_result(
            period_key=key,
            all_bars_1m=all_bars_1m,
            all_l2_1m=all_l2_1m,
            events=events,
        )

    coverage_by_month: dict[str, dict[str, int]] = defaultdict(
        lambda: {"l2_files": 0, "bars_days": 0, "precomputed_files": 0}
    )
    for day, _ in l2_files:
        coverage_by_month[day[:7]]["l2_files"] += 1
    for day in bars_by_day.keys():
        coverage_by_month[day[:7]]["bars_days"] += 1
    for day, _ in pre_files:
        coverage_by_month[day[:7]]["precomputed_files"] += 1

    result = {
        "meta": {
            "ticker": "MU",
            "requested_windows": {
                "q4_months": ["2025-10", "2025-11", "2025-12"],
                "january": "2026-01",
            },
            "analysis_range": {"start": start_day, "end": end_day},
            "session_filter": "RTH 09:30-16:00 America/New_York",
            "inputs": {
                "l2_dir": str(args.l2_dir),
                "precomputed_dir": str(args.precomputed_dir),
            },
            "coverage": {
                "raw_l2": bars_cov,
                "precomputed": l2_cov,
                "by_month": coverage_by_month,
                "level_events_total": len(events),
            },
            "regime_method": "ER30 proxy on 1m closes (TRENDING if ER>=0.35, else CHOPPY)",
            "phase4_method": "Prior-day volume profile from typical price bins (0.05), touch event with 0.5% move target in 60 bars",
        },
        "periods": periods,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    args.out_md.write_text(build_markdown(result), encoding="utf-8")

    print(f"Wrote JSON: {args.out_json}")
    print(f"Wrote MD:   {args.out_md}")


if __name__ == "__main__":
    main()
