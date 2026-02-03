#!/usr/bin/env python3
"""
Per-ticker strategy tuning + test-week evaluation.

This script:
1) Loads OHLCV data for each ticker.
2) Tunes key strategy parameters per ticker on a training window.
3) Evaluates the tuned parameters on a test week.
4) Writes strategy_overrides.json + tuning_results.json + test_week_results.json.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple

import pandas as pd

from available_data import get_discovery
from data_loader import DataLoader

# Import strategy engine (read-only) from market_regime_detection
STRATEGY_ROOT = Path(__file__).resolve().parent.parent / "market_regime_detection"
if STRATEGY_ROOT.exists():
    import sys

    sys.path.append(str(STRATEGY_ROOT))
    from src.day_trading_manager import DayTradingManager


@contextmanager
def suppress_output():
    """Silence noisy strategy debug prints for faster tuning."""
    devnull = open(os.devnull, "w")
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = devnull, devnull
        yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        devnull.close()

@dataclass
class TuneResult:
    params: Dict[str, Any]
    score: float
    total_pnl_pct: float
    trades: int
    days_used: int


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def date_range(start: str, end: str) -> List[str]:
    """Inclusive date range, weekdays only."""
    s = parse_date(start)
    e = parse_date(end)
    out = []
    cur = s
    while cur <= e:
        if cur.weekday() < 5:
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def load_ticker_df(loader: DataLoader, ticker: str) -> pd.DataFrame:
    discovery = get_discovery()
    dr = discovery.get_date_range(ticker)
    if not dr["start"] or not dr["end"]:
        raise RuntimeError(f"No data range for ticker {ticker}")
    data_file = discovery.get_file_for_date(ticker, dr["end"])
    if not data_file:
        raise RuntimeError(f"No data file for {ticker}")
    df = loader.load_csv(data_file)
    df["date_only"] = df["timestamp"].dt.date
    return df


def get_available_dates(df: pd.DataFrame) -> List[str]:
    dates = sorted({d.strftime("%Y-%m-%d") for d in df["date_only"].unique()})
    return dates


def select_training_dates(available: List[str], test_start: str, count: int) -> List[str]:
    """Pick last N available dates before test_start."""
    prior = [d for d in available if d < test_start]
    return prior[-count:] if len(prior) >= count else prior


def run_day(
    ticker: str,
    date: str,
    day_rows: List[Tuple],
    params_by_strategy: Dict[str, Dict[str, Any]],
    regime_detection_minutes: int = 5,
) -> Tuple[float, int, str]:
    dtm = DayTradingManager(regime_detection_minutes=regime_detection_minutes)

    # Apply params to strategies
    for strat_name, params in params_by_strategy.items():
        strat = dtm.strategies.get(strat_name)
        if not strat:
            continue
        for k, v in params.items():
            if hasattr(strat, k):
                setattr(strat, k, v)

    run_id = "tune"
    with suppress_output():
        for row in day_rows:
            ts = row.timestamp.to_pydatetime()
            dtm.process_bar(
                run_id=run_id,
                ticker=ticker,
                timestamp=ts,
                bar_data={
                    "open": float(row.open),
                    "high": float(row.high),
                    "low": float(row.low),
                    "close": float(row.close),
                    "volume": float(row.volume),
                    "vwap": float(row.vwap) if hasattr(row, "vwap") else None,
                },
            )

    session = dtm.get_session(run_id, ticker, date)
    if not session:
        return 0.0, 0, ""
    return session.total_pnl, len(session.trades), session.selected_strategy or ""


def score_result(total_pnl: float, trades: int, min_trades: int = 2) -> float:
    score = total_pnl
    if trades == 0:
        score -= 5.0
    elif trades < min_trades:
        score -= (min_trades - trades) * 0.5
    return score


def grid(values: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    keys = list(values.keys())
    combos = []
    for combo in itertools.product(*[values[k] for k in keys]):
        combos.append(dict(zip(keys, combo)))
    return combos


def tune_strategy_for_ticker(
    ticker: str,
    day_rows_map: Dict[str, List[Tuple]],
    dates: List[str],
    strategy_name: str,
    param_grid: Dict[str, List[Any]],
) -> TuneResult:
    best = TuneResult(params={}, score=-1e9, total_pnl_pct=0.0, trades=0, days_used=0)
    combos = grid(param_grid)

    for params in combos:
        total_pnl = 0.0
        total_trades = 0
        days_used = 0
        for date in dates:
            day_rows = day_rows_map.get(date)
            if not day_rows:
                continue
            pnl, trades, selected = run_day(
                ticker=ticker,
                date=date,
                day_rows=day_rows,
                params_by_strategy={strategy_name: params},
            )
            if selected != strategy_name:
                # Skip days where the strategy isn't used
                continue
            total_pnl += pnl
            total_trades += trades
            days_used += 1

        if days_used == 0:
            continue

        score = score_result(total_pnl, total_trades)
        if score > best.score:
            best = TuneResult(params=params, score=score, total_pnl_pct=total_pnl, trades=total_trades, days_used=days_used)

    return best


def evaluate_test_week(
    ticker: str,
    day_rows_map: Dict[str, List[Tuple]],
    test_dates: List[str],
    overrides: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    total_pnl = 0.0
    total_trades = 0
    day_results = []
    for date in test_dates:
        day_rows = day_rows_map.get(date)
        if not day_rows:
            continue
        pnl, trades, selected = run_day(
            ticker=ticker,
            date=date,
            day_rows=day_rows,
            params_by_strategy=overrides,
        )
        day_results.append({
            "date": date,
            "pnl_pct": round(pnl, 2),
            "trades": trades,
            "strategy": selected,
        })
        total_pnl += pnl
        total_trades += trades
    return {
        "ticker": ticker,
        "total_pnl_pct": round(total_pnl, 2),
        "total_trades": total_trades,
        "days": day_results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", type=str, default="")
    parser.add_argument("--test-start", type=str, default="2026-01-12")
    parser.add_argument("--test-end", type=str, default="2026-01-15")
    parser.add_argument("--train-days", type=int, default=3)
    parser.add_argument("--out", type=str, default="strategy_overrides.json")
    args = parser.parse_args()

    discovery = get_discovery()
    tickers = (
        [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        if args.tickers
        else discovery.get_tickers()
    )

    test_dates = date_range(args.test_start, args.test_end)

    loader = DataLoader()
    tuning_results = {}
    overrides = {}

    # Param grids (small, pragmatic)
    mean_rev_grid = {
        "entry_deviation_pct": [0.25, 0.4],
        "atr_stop_mult": [1.5, 2.0],
        "min_confidence": [55.0],
        "trailing_stop_pct": [0.3],
    }
    momentum_grid = {
        "breakout_atr_mult": [0.25, 0.35],
        "volume_threshold": [1.2],
        "rr_ratio": [2.0, 2.5],
        "trailing_stop_pct": [1.0],
    }

    for ticker in tickers:
        try:
            df = load_ticker_df(loader, ticker)
        except Exception as e:
            print(f"[WARN] {ticker}: {e}")
            continue

        print(f"[INFO] Tuning {ticker}...")
        available = get_available_dates(df)
        train_dates = select_training_dates(available, args.test_start, args.train_days)

        if not train_dates:
            print(f"[WARN] {ticker}: no training dates found")
            continue

        # Precompute day rows for speed
        day_rows_map: Dict[str, List[Tuple]] = {}
        for date in set(train_dates + test_dates):
            day_df = loader.filter_trading_day(df, date)
            if day_df.empty:
                continue
            day_rows_map[date] = list(day_df.itertuples(index=False))

        mean_rev = tune_strategy_for_ticker(ticker, day_rows_map, train_dates, "mean_reversion", mean_rev_grid)
        momentum = tune_strategy_for_ticker(ticker, day_rows_map, train_dates, "momentum", momentum_grid)

        tuning_results[ticker] = {
            "mean_reversion": mean_rev.__dict__,
            "momentum": momentum.__dict__,
            "train_dates": train_dates,
        }

        overrides[ticker] = {
            "mean_reversion": mean_rev.params,
            "momentum": momentum.params,
        }

    # Evaluate test week
    test_results = {"test_start": args.test_start, "test_end": args.test_end, "tickers": {}}
    for ticker in tickers:
        if ticker not in overrides:
            continue
        df = load_ticker_df(loader, ticker)
        day_rows_map: Dict[str, List[Tuple]] = {}
        for date in test_dates:
            day_df = loader.filter_trading_day(df, date)
            if day_df.empty:
                continue
            day_rows_map[date] = list(day_df.itertuples(index=False))
        res = evaluate_test_week(ticker, day_rows_map, test_dates, overrides[ticker])
        test_results["tickers"][ticker] = res

    # Write outputs
    out_path = Path(args.out)
    out_path.write_text(json.dumps(overrides, indent=2))
    Path("tuning_results.json").write_text(json.dumps(tuning_results, indent=2))
    Path("test_week_results.json").write_text(json.dumps(test_results, indent=2))

    print("Wrote:")
    print(f"  {out_path}")
    print("  tuning_results.json")
    print("  test_week_results.json")


if __name__ == "__main__":
    main()
