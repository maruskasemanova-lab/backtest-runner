#!/usr/bin/env python3
"""
Walk-Forward Optimization (WFO) System for Trading Strategies.

This script implements a rolling walk-forward optimization that:
1. Trains on N days (in-sample)
2. Tests on M days (out-of-sample)
3. Rolls forward and repeats
4. Generates per-ticker optimal parameters

Usage:
    python wfo_optimizer.py --tickers NVDA,TSLA --train-days 10 --test-days 3
"""
import argparse
import itertools
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd

# Add market_regime_detection to path
STRATEGY_ROOT = Path(__file__).resolve().parent.parent / "market_regime_detection"
if STRATEGY_ROOT.exists():
    sys.path.insert(0, str(STRATEGY_ROOT))
    from src.day_trading_manager import DayTradingManager

from available_data import get_discovery
from data_loader import DataLoader


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


# ============ Parameter Grids ============

PARAM_GRIDS = {
    "mean_reversion": {
        "entry_deviation_pct": [0.2, 0.3, 0.4],
        "trailing_stop_pct": [0.2, 0.3, 0.4],
        "volume_exhaustion_ratio": [0.7, 0.9],
        "min_confidence": [50, 55, 60],
    },
    "momentum": {
        "volume_threshold": [1.2, 1.5, 1.8],
        "consolidation_bars": [8, 10, 12],
        "rr_ratio": [2.0, 2.5, 3.0],
        "trailing_stop_pct": [0.8, 1.2, 1.5],
    },
    "pullback": {
        "pullback_threshold_pct": [0.3, 0.5, 0.7],
        "volume_surge_ratio": [1.0, 1.2, 1.5],
        "rr_ratio": [1.5, 2.0, 2.5],
        "trailing_stop_pct": [0.5, 0.8, 1.0],
    },
    "vwap_magnet": {
        "magnet_threshold": [0.1, 0.15, 0.2],
        "atr_multiplier": [1.0, 1.5, 2.0],
        "trailing_stop_pct": [0.3, 0.5, 0.7],
    }
}


@dataclass
class OptimizationResult:
    strategy: str
    params: Dict[str, Any]
    score: float
    total_pnl_pct: float
    trades: int
    win_rate: float
    profit_factor: float
    days_used: int


@dataclass
class TickerOptResult:
    ticker: str
    best_params: Dict[str, Dict[str, Any]]  # strategy -> params
    train_pnl: float
    test_pnl: float
    train_trades: int
    test_trades: int
    train_win_rate: float
    test_win_rate: float


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


def get_trading_dates(ticker: str, loader: DataLoader) -> List[str]:
    """Get list of available trading dates for a ticker."""
    discovery = get_discovery()
    dr = discovery.get_date_range(ticker)
    if not dr["start"] or not dr["end"]:
        return []
    
    data_file = discovery.get_file_for_date(ticker, dr["end"])
    if not data_file:
        return []
    
    df = loader.load_csv(data_file)
    df["date_only"] = df["timestamp"].dt.date
    dates = sorted({d.strftime("%Y-%m-%d") for d in df["date_only"].unique()})
    return dates


def grid(values: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    """Generate all parameter combinations."""
    keys = list(values.keys())
    combos = []
    for combo in itertools.product(*[values[k] for k in keys]):
        combos.append(dict(zip(keys, combo)))
    return combos


def run_single_day(
    ticker: str,
    date: str,
    day_rows: List[Tuple],
    params_by_strategy: Dict[str, Dict[str, Any]],
    regime_detection_minutes: int = 30,
) -> Tuple[float, int, int, str]:
    """
    Run simulation for a single day.
    Returns: (pnl_pct, total_trades, winning_trades, strategy_used)
    """
    dtm = DayTradingManager(regime_detection_minutes=regime_detection_minutes)
    
    # Apply params to strategies
    for strat_name, params in params_by_strategy.items():
        strat = dtm.strategies.get(strat_name)
        if not strat:
            continue
        for k, v in params.items():
            if hasattr(strat, k):
                setattr(strat, k, v)
    
    run_id = "wfo"
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
        return 0.0, 0, 0, ""
    
    winning = sum(1 for t in session.trades if t.pnl_pct > 0)
    return session.total_pnl, len(session.trades), winning, session.selected_strategy or ""


def score_result(pnl: float, trades: int, wins: int, min_trades: int = 2) -> float:
    """
    Calculate optimization score.
    Score = profit_factor * win_rate_weight * trade_count_weight
    """
    if trades == 0:
        return -10.0
    
    win_rate = wins / trades if trades > 0 else 0
    
    # Profit factor approximation (since we don't have individual trade data)
    if pnl > 0:
        pf = 1.0 + (pnl / 10)  # Rough approximation
    else:
        pf = max(0.1, 1.0 + (pnl / 10))
    
    # Trade count bonus (more trades = more data points)
    trade_weight = min(1.5, 0.5 + trades * 0.1)
    
    # Final score
    score = pnl * (0.5 + win_rate) * trade_weight
    
    # Penalty for too few trades
    if trades < min_trades:
        score -= (min_trades - trades) * 5
    
    return score


def optimize_strategy_for_dates(
    ticker: str,
    day_rows_map: Dict[str, List[Tuple]],
    dates: List[str],
    strategy_name: str,
    param_grid: Dict[str, List[Any]],
) -> OptimizationResult:
    """Optimize a single strategy across multiple dates."""
    best = OptimizationResult(
        strategy=strategy_name,
        params={},
        score=-1e9,
        total_pnl_pct=0.0,
        trades=0,
        win_rate=0.0,
        profit_factor=0.0,
        days_used=0
    )
    
    combos = grid(param_grid)
    
    for params in combos:
        total_pnl = 0.0
        total_trades = 0
        total_wins = 0
        days_used = 0
        
        for date in dates:
            day_rows = day_rows_map.get(date)
            if not day_rows:
                continue
            
            pnl, trades, wins, selected = run_single_day(
                ticker=ticker,
                date=date,
                day_rows=day_rows,
                params_by_strategy={strategy_name: params},
            )
            
            # Count all days where we got a regime
            total_pnl += pnl
            total_trades += trades
            total_wins += wins
            days_used += 1
        
        if days_used == 0:
            continue
        
        score = score_result(total_pnl, total_trades, total_wins)
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        if score > best.score:
            pf = 1.0 + (total_pnl / 10) if total_pnl > 0 else max(0.1, 1.0 + (total_pnl / 10))
            best = OptimizationResult(
                strategy=strategy_name,
                params=params,
                score=score,
                total_pnl_pct=total_pnl,
                trades=total_trades,
                win_rate=win_rate,
                profit_factor=pf,
                days_used=days_used
            )
    
    return best


def evaluate_on_dates(
    ticker: str,
    day_rows_map: Dict[str, List[Tuple]],
    dates: List[str],
    overrides: Dict[str, Dict[str, Any]],
) -> Tuple[float, int, int]:
    """Evaluate strategy with given overrides on test dates."""
    total_pnl = 0.0
    total_trades = 0
    total_wins = 0
    
    for date in dates:
        day_rows = day_rows_map.get(date)
        if not day_rows:
            continue
        
        pnl, trades, wins, _ = run_single_day(
            ticker=ticker,
            date=date,
            day_rows=day_rows,
            params_by_strategy=overrides,
        )
        total_pnl += pnl
        total_trades += trades
        total_wins += wins
    
    return total_pnl, total_trades, total_wins


def run_walk_forward(
    ticker: str,
    all_dates: List[str],
    day_rows_map: Dict[str, List[Tuple]],
    train_days: int = 10,
    test_days: int = 3,
) -> TickerOptResult:
    """
    Run rolling walk-forward optimization for a ticker.
    """
    print(f"\n{'='*60}")
    print(f"🔧 Optimizing {ticker}")
    print(f"{'='*60}")
    
    if len(all_dates) < train_days + test_days:
        print(f"   ⚠️  Not enough data ({len(all_dates)} days, need {train_days + test_days})")
        return TickerOptResult(
            ticker=ticker,
            best_params={},
            train_pnl=0, test_pnl=0,
            train_trades=0, test_trades=0,
            train_win_rate=0, test_win_rate=0
        )
    
    # Use most recent data for final test, train on preceding days
    test_dates = all_dates[-test_days:]
    train_dates = all_dates[-(train_days + test_days):-test_days]
    
    print(f"   Train: {train_dates[0]} to {train_dates[-1]} ({len(train_dates)} days)")
    print(f"   Test:  {test_dates[0]} to {test_dates[-1]} ({len(test_dates)} days)")
    
    # Optimize each strategy
    best_results: Dict[str, OptimizationResult] = {}
    
    for strategy_name, param_grid in PARAM_GRIDS.items():
        result = optimize_strategy_for_dates(
            ticker=ticker,
            day_rows_map=day_rows_map,
            dates=train_dates,
            strategy_name=strategy_name,
            param_grid=param_grid,
        )
        best_results[strategy_name] = result
        
        if result.trades > 0:
            print(f"   📊 {strategy_name:15} | Score: {result.score:6.1f} | "
                  f"PnL: {result.total_pnl_pct:+.2f}% | "
                  f"Trades: {result.trades:3} | "
                  f"WR: {result.win_rate:.1f}%")
    
    # Build best params dict
    best_params = {}
    for strat, result in best_results.items():
        if result.params:
            best_params[strat] = result.params
    
    # Calculate aggregate train stats
    train_pnl = sum(r.total_pnl_pct for r in best_results.values())
    train_trades = sum(r.trades for r in best_results.values())
    train_wins = sum(int(r.trades * r.win_rate / 100) for r in best_results.values())
    train_win_rate = (train_wins / train_trades * 100) if train_trades > 0 else 0
    
    # Evaluate on test set
    test_pnl, test_trades, test_wins = evaluate_on_dates(
        ticker=ticker,
        day_rows_map=day_rows_map,
        dates=test_dates,
        overrides=best_params
    )
    test_win_rate = (test_wins / test_trades * 100) if test_trades > 0 else 0
    
    print(f"\n   📈 Train Results: PnL {train_pnl:+.2f}% | {train_trades} trades | {train_win_rate:.1f}% WR")
    print(f"   📉 Test Results:  PnL {test_pnl:+.2f}% | {test_trades} trades | {test_win_rate:.1f}% WR")
    
    return TickerOptResult(
        ticker=ticker,
        best_params=best_params,
        train_pnl=train_pnl,
        test_pnl=test_pnl,
        train_trades=train_trades,
        test_trades=test_trades,
        train_win_rate=train_win_rate,
        test_win_rate=test_win_rate
    )


def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Strategy Optimizer")
    parser.add_argument("--tickers", type=str, default="",
                        help="Comma-separated list of tickers (default: all available)")
    parser.add_argument("--train-days", type=int, default=10,
                        help="Number of in-sample training days")
    parser.add_argument("--test-days", type=int, default=3,
                        help="Number of out-of-sample test days")
    parser.add_argument("--output", "-o", type=str, default="strategy_overrides.json",
                        help="Output file for strategy overrides")
    args = parser.parse_args()
    
    print("=" * 70)
    print("🚀 WALK-FORWARD STRATEGY OPTIMIZER")
    print("=" * 70)
    
    # Get tickers
    discovery = get_discovery()
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = discovery.get_tickers()
    
    print(f"Tickers: {', '.join(tickers)}")
    print(f"Train Days: {args.train_days}")
    print(f"Test Days: {args.test_days}")
    
    loader = DataLoader()
    all_results: List[TickerOptResult] = []
    final_overrides: Dict[str, Dict[str, Any]] = {}
    
    for ticker in tickers:
        # Get available dates
        dates = get_trading_dates(ticker, loader)
        if not dates:
            print(f"\n⚠️  {ticker}: No data available")
            continue
        
        # Load data for all dates
        data_file = discovery.get_file_for_date(ticker, dates[-1])
        if not data_file:
            continue
        
        df = loader.load_csv(data_file)
        
        # Build day_rows_map
        day_rows_map: Dict[str, List[Tuple]] = {}
        for date in dates:
            day_df = loader.filter_trading_day(df, date)
            if day_df.empty:
                continue
            day_rows_map[date] = list(day_df.itertuples(index=False))
        
        # Run optimization
        result = run_walk_forward(
            ticker=ticker,
            all_dates=dates,
            day_rows_map=day_rows_map,
            train_days=args.train_days,
            test_days=args.test_days
        )
        
        all_results.append(result)
        if result.best_params:
            final_overrides[ticker] = result.best_params
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 OPTIMIZATION SUMMARY")
    print("=" * 70)
    
    total_train_pnl = 0
    total_test_pnl = 0
    
    for r in all_results:
        icon = "🟢" if r.test_pnl > 0 else "🔴"
        print(f"{r.ticker:6} | Train: {r.train_pnl:+6.2f}% ({r.train_trades:3} trades) | "
              f"Test: {icon} {r.test_pnl:+6.2f}% ({r.test_trades:3} trades)")
        total_train_pnl += r.train_pnl
        total_test_pnl += r.test_pnl
    
    print("-" * 70)
    test_icon = "🟢" if total_test_pnl > 0 else "🔴"
    print(f"TOTAL  | Train: {total_train_pnl:+6.2f}% | Test: {test_icon} {total_test_pnl:+6.2f}%")
    
    # Save results
    output_path = Path(args.output)
    output_path.write_text(json.dumps(final_overrides, indent=2))
    print(f"\n💾 Saved optimized parameters to: {output_path}")
    
    # Also save detailed results
    results_path = Path("wfo_results.json")
    results_data = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "train_days": args.train_days,
            "test_days": args.test_days,
            "tickers": tickers
        },
        "results": [
            {
                "ticker": r.ticker,
                "best_params": r.best_params,
                "train_pnl": r.train_pnl,
                "test_pnl": r.test_pnl,
                "train_trades": r.train_trades,
                "test_trades": r.test_trades,
                "train_win_rate": r.train_win_rate,
                "test_win_rate": r.test_win_rate,
            }
            for r in all_results
        ],
        "totals": {
            "train_pnl": total_train_pnl,
            "test_pnl": total_test_pnl
        }
    }
    results_path.write_text(json.dumps(results_data, indent=2))
    print(f"💾 Saved detailed results to: {results_path}")
    
    print("\n✅ Optimization complete!")


if __name__ == "__main__":
    main()
