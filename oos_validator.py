#!/usr/bin/env python3
"""
Chronological 60/20/20 train/validation/test evaluator.

Unlike rolling WFO, this script enforces a strict hold-out test segment that is
never used for parameter search.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from src.services.data_discovery import get_discovery
from data_loader import DataLoader
from wfo_optimizer import (
    PARAM_GRIDS,
    evaluate_on_dates,
    get_trading_dates,
    optimize_strategy_for_dates,
)


@dataclass
class SplitResult:
    train_dates: List[str]
    validation_dates: List[str]
    test_dates: List[str]


def split_dates_chronological(
    dates: List[str],
    train_ratio: float = 0.6,
    validation_ratio: float = 0.2,
) -> SplitResult:
    n = len(dates)
    if n < 5:
        raise ValueError(f"Need at least 5 dates for 60/20/20 split, got {n}")

    train_end = max(1, int(n * train_ratio))
    val_end = train_end + max(1, int(n * validation_ratio))
    if val_end >= n:
        val_end = n - 1

    train = dates[:train_end]
    validation = dates[train_end:val_end]
    test = dates[val_end:]
    if not validation or not test:
        raise ValueError(
            "Split produced empty validation/test bucket. Add more history."
        )
    return SplitResult(train_dates=train, validation_dates=validation, test_dates=test)


def build_day_rows_map(
    ticker: str, loader: DataLoader
) -> Tuple[List[str], Dict[str, List[Tuple]]]:
    discovery = get_discovery()
    dates = get_trading_dates(ticker, loader)
    if not dates:
        return [], {}

    dr = discovery.get_date_range(ticker)
    if not dr["start"] or not dr["end"]:
        return [], {}

    files = discovery.get_files_for_range(ticker, dr["start"], dr["end"])
    if not files:
        return [], {}

    dfs: List[pd.DataFrame] = []
    for file in files:
        if file.endswith((".parquet", ".parq")):
            dfs.append(loader.load_parquet(file))
        else:
            dfs.append(loader.load_csv(file))

    df = pd.concat(dfs, ignore_index=True)
    df = (
        df.drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    day_rows_map: Dict[str, List[Tuple]] = {}
    for date in dates:
        day_df = loader.filter_trading_day(df, date)
        if day_df.empty:
            continue
        day_rows_map[date] = list(day_df.itertuples(index=False))
    return dates, day_rows_map


def win_rate(wins: int, trades: int) -> float:
    return (wins / trades * 100.0) if trades > 0 else 0.0


def run_for_ticker(
    ticker: str, loader: DataLoader, train_ratio: float, validation_ratio: float
) -> Dict[str, Any]:
    dates, day_rows_map = build_day_rows_map(ticker, loader)
    if not dates or not day_rows_map:
        return {"ticker": ticker, "error": "No data available"}

    split = split_dates_chronological(
        dates, train_ratio=train_ratio, validation_ratio=validation_ratio
    )

    best_results = {}
    for strategy_name, param_grid in PARAM_GRIDS.items():
        result = optimize_strategy_for_dates(
            ticker=ticker,
            day_rows_map=day_rows_map,
            dates=split.train_dates,
            strategy_name=strategy_name,
            param_grid=param_grid,
        )
        best_results[strategy_name] = result

    overrides = {name: r.params for name, r in best_results.items() if r.params}
    if not overrides:
        return {
            "ticker": ticker,
            "error": "No valid optimized parameters",
            "split": split.__dict__,
        }

    tr_pnl, tr_trades, tr_wins, _, _ = evaluate_on_dates(
        ticker=ticker,
        day_rows_map=day_rows_map,
        dates=split.train_dates,
        overrides=overrides,
    )
    val_pnl, val_trades, val_wins, _, _ = evaluate_on_dates(
        ticker=ticker,
        day_rows_map=day_rows_map,
        dates=split.validation_dates,
        overrides=overrides,
    )
    test_pnl, test_trades, test_wins, _, _ = evaluate_on_dates(
        ticker=ticker,
        day_rows_map=day_rows_map,
        dates=split.test_dates,
        overrides=overrides,
    )

    return {
        "ticker": ticker,
        "split": split.__dict__,
        "best_params": overrides,
        "train": {
            "pnl_pct": tr_pnl,
            "trades": tr_trades,
            "win_rate": win_rate(tr_wins, tr_trades),
        },
        "validation": {
            "pnl_pct": val_pnl,
            "trades": val_trades,
            "win_rate": win_rate(val_wins, val_trades),
        },
        "test": {
            "pnl_pct": test_pnl,
            "trades": test_trades,
            "win_rate": win_rate(test_wins, test_trades),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Strict chronological 60/20/20 OOS validation"
    )
    parser.add_argument(
        "--tickers", type=str, default="", help="Comma-separated tickers; default all"
    )
    parser.add_argument("--train-ratio", type=float, default=0.6)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--output", type=str, default="oos_validation_results.json")
    args = parser.parse_args()

    discovery = get_discovery()
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = discovery.get_tickers()

    loader = DataLoader()
    results = []
    for ticker in tickers:
        try:
            res = run_for_ticker(
                ticker=ticker,
                loader=loader,
                train_ratio=float(args.train_ratio),
                validation_ratio=float(args.validation_ratio),
            )
        except Exception as e:
            res = {"ticker": ticker, "error": str(e)}
        results.append(res)

    payload = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "tickers": tickers,
            "train_ratio": args.train_ratio,
            "validation_ratio": args.validation_ratio,
            "test_ratio": max(0.0, 1.0 - args.train_ratio - args.validation_ratio),
        },
        "results": results,
    }

    out_path = Path(args.output)
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Saved OOS validation report: {out_path}")


if __name__ == "__main__":
    main()
