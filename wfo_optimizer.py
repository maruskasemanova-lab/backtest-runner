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
import importlib.util
import itertools
import json
import os
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd

from available_data import get_discovery
from data_loader import DataLoader


def _load_day_trading_manager() -> Any:
    """Load DayTradingManager from sibling strategy service without clobbering local src imports."""
    workspace_root = Path(__file__).resolve().parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    try:
        from market_regime_detection.src.day_trading_manager import (
            DayTradingManager as dtm,
        )

        return dtm
    except Exception:
        pass

    hyphen_module_path = (
        workspace_root / "market-regime-detection" / "src" / "day_trading_manager.py"
    )
    if hyphen_module_path.exists():
        spec = importlib.util.spec_from_file_location(
            "_wfo_day_trading_manager", hyphen_module_path
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return getattr(module, "DayTradingManager", None)

    return None


DayTradingManager = _load_day_trading_manager()


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
    },
    "momentum_flow": {
        "min_signed_aggression": [0.06, 0.08, 0.10],
        "min_directional_consistency": [0.5, 0.55, 0.6],
        "min_sweep_intensity": [0.05, 0.08, 0.12],
        "min_book_pressure": [0.0, 0.02, 0.05],
        "min_confidence": [52.0, 58.0, 64.0],
    },
    "absorption_reversal": {
        "min_absorption_rate": [0.45, 0.5, 0.55],
        "min_signed_aggression": [0.06, 0.08, 0.1],
        "min_book_pressure": [0.03, 0.05, 0.08],
        "min_divergence": [0.12, 0.15, 0.2],
        "min_confidence": [58.0, 62.0, 66.0],
    },
    "exhaustion_fade": {
        "min_delta_zscore": [1.1, 1.4, 1.8],
        "min_signed_aggression": [0.02, 0.04, 0.06],
        "max_sweep_intensity": [0.6, 0.8, 1.0],
        "min_book_pressure": [0.0, 0.02, 0.05],
        "min_confidence": [58.0, 63.0, 68.0],
    },
    "rotation": {
        "lookback_period": [8, 12],
        "rotation_threshold": [0.4, 0.7],
        "volume_increase_ratio": [1.0, 1.1],
        "volume_stop_pct": [0.7, 1.1],
        "min_confidence": [48.0, 60.0],
    },
    "volume_profile": {
        "profile_lookback": [45, 90],
        "num_bins": [16, 24],
        "pb_threshold": [0.45, 0.8],
        "symmetry_tolerance_pct": [0.10, 0.20],
        "min_confidence": [60.0, 70.0],
        "atr_stop_mult": [2.0, 3.0],
    },
    "gap_liquidity": {
        "gap_threshold_pct": [0.2, 0.5],
        "swing_lookback": [14, 30],
        "liquidity_cluster_bars": [4, 7],
        "gap_fill_tolerance_pct": [0.08, 0.15],
        "min_confidence": [60.0, 70.0],
        "atr_stop_mult": [2.0, 3.0],
    },
    "iceberg_defense": {
        "min_iceberg_bias": [0.35, 0.65],
        "min_book_pressure": [0.0, 0.05],
        "max_opposing_aggression": [0.02, 0.05],
        "min_absorption_rate": [0.20, 0.40],
        "min_confidence": [55.0, 65.0],
        "atr_stop_multiplier": [1.0, 1.6],
    },
    "scalp_l2_intrabar": {
        "min_flow_score": [44.0, 54.0],
        "min_signed_aggression": [0.035, 0.055],
        "min_directional_consistency": [0.5, 0.66],
        "min_intrabar_move_pct": [0.025, 0.05],
        "min_round_trip_cost_bps": [5.0, 8.0],
        "min_reward_to_cost_ratio": [1.4, 2.0],
        "min_confidence": [52.0, 64.0],
    },
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


def canonical_strategy_name(strategy_name: str) -> str:
    """Normalize strategy labels from trades/session into snake_case keys."""
    if not strategy_name:
        return ""
    normalized = strategy_name.strip().replace("-", "_").replace(" ", "_")
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", normalized).lower()
    snake = re.sub(r"_+", "_", snake).strip("_")

    compact = re.sub(r"[^a-z0-9]", "", snake)
    for key in PARAM_GRIDS.keys():
        if key.replace("_", "") == compact:
            return key
    return snake


def get_trading_dates(ticker: str, loader: DataLoader) -> List[str]:
    """Get list of available trading dates for a ticker."""
    discovery = get_discovery()
    dr = discovery.get_date_range(ticker)
    if not dr["start"] or not dr["end"]:
        return []

    files = discovery.get_files_for_range(ticker, dr["start"], dr["end"])
    if not files:
        return []

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
    df = loader.filter_trading_range(df, dr["start"], dr["end"])
    df["date_only"] = loader._market_timestamp_series(df).dt.date
    dates = sorted({d.strftime("%Y-%m-%d") for d in df["date_only"].unique()})
    return dates


def grid(values: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    """Generate all parameter combinations."""
    keys = list(values.keys())
    combos = []
    for combo in itertools.product(*[values[k] for k in keys]):
        combos.append(dict(zip(keys, combo)))
    return combos


def _session_metrics(
    session: Any,
) -> Tuple[float, int, int, float, float, Dict[str, Dict[str, float]]]:
    """Extract aggregate + per-strategy metrics from DayTradingManager session."""
    if not session:
        return 0.0, 0, 0, 0.0, 0.0, {}

    winning = sum(1 for t in session.trades if t.pnl_pct > 0)
    gross_wins = sum(t.pnl_pct for t in session.trades if t.pnl_pct > 0)
    gross_losses = abs(sum(t.pnl_pct for t in session.trades if t.pnl_pct <= 0))
    per_strategy_stats: Dict[str, Dict[str, float]] = {}
    for trade in session.trades:
        strategy_key = canonical_strategy_name(getattr(trade, "strategy", ""))
        if not strategy_key:
            continue
        bucket = per_strategy_stats.setdefault(
            strategy_key,
            {
                "pnl": 0.0,
                "trades": 0.0,
                "wins": 0.0,
                "gross_wins": 0.0,
                "gross_losses": 0.0,
            },
        )
        pnl_pct = float(getattr(trade, "pnl_pct", 0.0) or 0.0)
        bucket["pnl"] += pnl_pct
        bucket["trades"] += 1.0
        if pnl_pct > 0:
            bucket["wins"] += 1.0
            bucket["gross_wins"] += pnl_pct
        else:
            bucket["gross_losses"] += abs(pnl_pct)

    return (
        float(getattr(session, "total_pnl", 0.0) or 0.0),
        len(getattr(session, "trades", []) or []),
        winning,
        float(gross_wins),
        float(gross_losses),
        per_strategy_stats,
    )


def _process_day_with_manager(
    dtm: Any,
    *,
    ticker: str,
    date: str,
    day_rows: List[Tuple],
    run_id: str,
) -> Tuple[float, int, int, float, float, Dict[str, Dict[str, float]]]:
    """Process one day through a configured DayTradingManager and return metrics."""
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
    return _session_metrics(session)


def _run_single_day_strategy_isolated(
    *,
    ticker: str,
    date: str,
    day_rows: List[Tuple],
    strategy_name: str,
    strategy_params: Dict[str, Any],
    regime_detection_minutes: int,
) -> Tuple[float, int, int, float, float, Dict[str, Dict[str, float]]]:
    """
    Run one strategy in isolation (all other strategies disabled) on the same day.
    Used for true strategy-parallel portfolio simulation in WFO.
    """
    dtm = DayTradingManager(regime_detection_minutes=regime_detection_minutes)
    target_strategy = dtm.strategies.get(strategy_name)
    if not target_strategy:
        return 0.0, 0, 0, 0.0, 0.0, {}

    for name, strat in dtm.strategies.items():
        strat.enabled = name == strategy_name

    for key, value in strategy_params.items():
        if hasattr(target_strategy, key):
            setattr(target_strategy, key, value)

    run_id = f"wfo-{strategy_name}"
    dtm.set_run_defaults(
        run_id=run_id,
        ticker=ticker,
        strategy_selection_mode="all_enabled",
        max_active_strategies=1,
    )
    return _process_day_with_manager(
        dtm,
        ticker=ticker,
        date=date,
        day_rows=day_rows,
        run_id=run_id,
    )


def run_single_day(
    ticker: str,
    date: str,
    day_rows: List[Tuple],
    params_by_strategy: Dict[str, Dict[str, Any]],
    regime_detection_minutes: int = 30,
    parallel_all_strategies: bool = False,
) -> Tuple[float, int, int, float, float, Dict[str, Dict[str, float]]]:
    """
    Run simulation for a single day.
    Returns:
      (pnl_pct, total_trades, winning_trades, gross_wins, gross_losses, per_strategy_stats)
    """
    if DayTradingManager is None:
        raise RuntimeError(
            "DayTradingManager is not available. Ensure market_regime_detection is present in the sibling directory."
        )

    if parallel_all_strategies and len(params_by_strategy) > 1:
        total_pnl = 0.0
        total_trades = 0
        total_wins = 0
        total_gross_wins = 0.0
        total_gross_losses = 0.0
        per_strategy_stats: Dict[str, Dict[str, float]] = {}

        for strategy_name in sorted(params_by_strategy.keys()):
            pnl, trades, wins, gross_wins, gross_losses, strat_stats = (
                _run_single_day_strategy_isolated(
                    ticker=ticker,
                    date=date,
                    day_rows=day_rows,
                    strategy_name=strategy_name,
                    strategy_params=params_by_strategy.get(strategy_name, {}) or {},
                    regime_detection_minutes=regime_detection_minutes,
                )
            )
            total_pnl += pnl
            total_trades += trades
            total_wins += wins
            total_gross_wins += gross_wins
            total_gross_losses += gross_losses
            for key, bucket in strat_stats.items():
                merged = per_strategy_stats.setdefault(
                    key,
                    {
                        "pnl": 0.0,
                        "trades": 0.0,
                        "wins": 0.0,
                        "gross_wins": 0.0,
                        "gross_losses": 0.0,
                    },
                )
                for metric in ("pnl", "trades", "wins", "gross_wins", "gross_losses"):
                    merged[metric] += float(bucket.get(metric, 0.0) or 0.0)

        return (
            float(total_pnl),
            int(total_trades),
            int(total_wins),
            float(total_gross_wins),
            float(total_gross_losses),
            per_strategy_stats,
        )

    dtm = DayTradingManager(regime_detection_minutes=regime_detection_minutes)
    run_id = "wfo"

    if parallel_all_strategies:
        dtm.set_run_defaults(
            run_id=run_id,
            ticker=ticker,
            strategy_selection_mode="all_enabled",
            max_active_strategies=max(1, min(20, len(getattr(dtm, "strategies", {})))),
        )

    # Apply params to strategies
    for strat_name, params in params_by_strategy.items():
        strat = dtm.strategies.get(strat_name)
        if not strat:
            continue
        for k, v in params.items():
            if hasattr(strat, k):
                setattr(strat, k, v)

    return _process_day_with_manager(
        dtm,
        ticker=ticker,
        date=date,
        day_rows=day_rows,
        run_id=run_id,
    )


def score_result(
    pnl: float,
    trades: int,
    wins: int,
    gross_wins: float,
    gross_losses: float,
    min_trades: int = 4,
) -> float:
    """
    Calculate optimization score from real trade outcomes.
    """
    if trades == 0:
        return -100.0

    win_rate = wins / trades if trades > 0 else 0
    profit_factor = (
        gross_wins / gross_losses
        if gross_losses > 0
        else (2.0 if gross_wins > 0 else 0.0)
    )
    trade_weight = min(1.5, 0.5 + trades / 20.0)

    # Balance profitability, consistency, and PF, then scale by sample size.
    score = (
        (pnl * 1.5) + (win_rate * 40.0) + ((profit_factor - 1.0) * 20.0)
    ) * trade_weight

    if trades < min_trades:
        score -= (min_trades - trades) * 8

    return score


def optimize_strategy_for_dates(
    ticker: str,
    day_rows_map: Dict[str, List[Tuple]],
    dates: List[str],
    strategy_name: str,
    param_grid: Dict[str, List[Any]],
    parallel_all_strategies: bool = False,
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
        days_used=0,
    )

    combos = grid(param_grid)

    target_strategy = canonical_strategy_name(strategy_name)
    for params in combos:
        total_pnl = 0.0
        total_trades = 0
        total_wins = 0
        total_gross_wins = 0.0
        total_gross_losses = 0.0
        days_used = 0

        for date in dates:
            day_rows = day_rows_map.get(date)
            if not day_rows:
                continue

            _, _, _, _, _, per_strategy_stats = run_single_day(
                ticker=ticker,
                date=date,
                day_rows=day_rows,
                params_by_strategy={strategy_name: params},
                parallel_all_strategies=parallel_all_strategies,
            )

            strategy_stats = per_strategy_stats.get(target_strategy)
            if not strategy_stats:
                continue

            total_pnl += float(strategy_stats.get("pnl", 0.0))
            total_trades += int(strategy_stats.get("trades", 0.0))
            total_wins += int(strategy_stats.get("wins", 0.0))
            total_gross_wins += float(strategy_stats.get("gross_wins", 0.0))
            total_gross_losses += float(strategy_stats.get("gross_losses", 0.0))
            days_used += 1

        if days_used == 0:
            continue

        score = score_result(
            total_pnl,
            total_trades,
            total_wins,
            total_gross_wins,
            total_gross_losses,
        )
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

        if score > best.score:
            pf = (
                total_gross_wins / total_gross_losses
                if total_gross_losses > 0
                else (2.0 if total_gross_wins > 0 else 0.0)
            )
            best = OptimizationResult(
                strategy=strategy_name,
                params=params,
                score=score,
                total_pnl_pct=total_pnl,
                trades=total_trades,
                win_rate=win_rate,
                profit_factor=pf,
                days_used=days_used,
            )

    return best


def evaluate_on_dates(
    ticker: str,
    day_rows_map: Dict[str, List[Tuple]],
    dates: List[str],
    overrides: Dict[str, Dict[str, Any]],
    parallel_all_strategies: bool = False,
) -> Tuple[float, int, int, float, float]:
    """Evaluate strategy with given overrides on test dates."""
    total_pnl = 0.0
    total_trades = 0
    total_wins = 0
    total_gross_wins = 0.0
    total_gross_losses = 0.0

    for date in dates:
        day_rows = day_rows_map.get(date)
        if not day_rows:
            continue

        pnl, trades, wins, gross_wins, gross_losses, _ = run_single_day(
            ticker=ticker,
            date=date,
            day_rows=day_rows,
            params_by_strategy=overrides,
            parallel_all_strategies=parallel_all_strategies,
        )
        total_pnl += pnl
        total_trades += trades
        total_wins += wins
        total_gross_wins += gross_wins
        total_gross_losses += gross_losses

    return total_pnl, total_trades, total_wins, total_gross_wins, total_gross_losses


def run_walk_forward(
    ticker: str,
    all_dates: List[str],
    day_rows_map: Dict[str, List[Tuple]],
    train_days: int = 10,
    test_days: int = 3,
    parallel_all_strategies: bool = False,
) -> TickerOptResult:
    """
    Run rolling walk-forward optimization for a ticker.
    """
    print(f"\n{'='*60}")
    print(f"🔧 Optimizing {ticker}")
    print(f"{'='*60}")

    if len(all_dates) < train_days + test_days:
        print(
            f"   ⚠️  Not enough data ({len(all_dates)} days, need {train_days + test_days})"
        )
        return TickerOptResult(
            ticker=ticker,
            best_params={},
            train_pnl=0,
            test_pnl=0,
            train_trades=0,
            test_trades=0,
            train_win_rate=0,
            test_win_rate=0,
        )

    windows: List[Tuple[List[str], List[str]]] = []
    start_idx = 0
    while start_idx + train_days + test_days <= len(all_dates):
        train_slice = all_dates[start_idx : start_idx + train_days]
        test_slice = all_dates[
            start_idx + train_days : start_idx + train_days + test_days
        ]
        windows.append((train_slice, test_slice))
        start_idx += test_days

    print(
        f"   Windows: {len(windows)} | Train days/window: {train_days} | Test days/window: {test_days}"
    )

    rolling_best_params: Dict[str, Dict[str, Any]] = {}
    train_pnl_total = 0.0
    test_pnl_total = 0.0
    train_trades_total = 0
    test_trades_total = 0
    train_wins_total = 0
    test_wins_total = 0

    for idx, (train_dates, test_dates) in enumerate(windows, 1):
        print(f"\n   ─ Window {idx}/{len(windows)}")
        print(
            f"     Train: {train_dates[0]} → {train_dates[-1]} ({len(train_dates)} days)"
        )
        print(
            f"     Test:  {test_dates[0]} → {test_dates[-1]} ({len(test_dates)} days)"
        )

        best_results: Dict[str, OptimizationResult] = {}
        for strategy_name, param_grid in PARAM_GRIDS.items():
            result = optimize_strategy_for_dates(
                ticker=ticker,
                day_rows_map=day_rows_map,
                dates=train_dates,
                strategy_name=strategy_name,
                param_grid=param_grid,
                parallel_all_strategies=parallel_all_strategies,
            )
            best_results[strategy_name] = result

            if result.trades > 0:
                print(
                    f"     📊 {strategy_name:15} | Score: {result.score:7.2f} | "
                    f"PnL: {result.total_pnl_pct:+.2f}% | Trades: {result.trades:3} | WR: {result.win_rate:.1f}%"
                )

        window_params = {
            name: res.params for name, res in best_results.items() if res.params
        }
        if not window_params:
            print("     ⚠️  No valid params in this window, skipping evaluation")
            continue

        train_pnl, train_trades, train_wins, _, _ = evaluate_on_dates(
            ticker=ticker,
            day_rows_map=day_rows_map,
            dates=train_dates,
            overrides=window_params,
            parallel_all_strategies=parallel_all_strategies,
        )
        test_pnl, test_trades, test_wins, _, _ = evaluate_on_dates(
            ticker=ticker,
            day_rows_map=day_rows_map,
            dates=test_dates,
            overrides=window_params,
            parallel_all_strategies=parallel_all_strategies,
        )

        train_pnl_total += train_pnl
        test_pnl_total += test_pnl
        train_trades_total += train_trades
        test_trades_total += test_trades
        train_wins_total += train_wins
        test_wins_total += test_wins
        rolling_best_params = window_params

        train_wr = (train_wins / train_trades * 100) if train_trades > 0 else 0.0
        test_wr = (test_wins / test_trades * 100) if test_trades > 0 else 0.0
        print(
            f"     📈 Train: PnL {train_pnl:+.2f}% | {train_trades} trades | WR {train_wr:.1f}%"
        )
        print(
            f"     📉 Test:  PnL {test_pnl:+.2f}% | {test_trades} trades | WR {test_wr:.1f}%"
        )

    train_win_rate = (
        (train_wins_total / train_trades_total * 100) if train_trades_total > 0 else 0.0
    )
    test_win_rate = (
        (test_wins_total / test_trades_total * 100) if test_trades_total > 0 else 0.0
    )
    print(
        f"\n   📈 Aggregate Train: PnL {train_pnl_total:+.2f}% | {train_trades_total} trades | WR {train_win_rate:.1f}%"
    )
    print(
        f"   📉 Aggregate Test:  PnL {test_pnl_total:+.2f}% | {test_trades_total} trades | WR {test_win_rate:.1f}%"
    )

    return TickerOptResult(
        ticker=ticker,
        best_params=rolling_best_params,
        train_pnl=train_pnl_total,
        test_pnl=test_pnl_total,
        train_trades=train_trades_total,
        test_trades=test_trades_total,
        train_win_rate=train_win_rate,
        test_win_rate=test_win_rate,
    )


def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Strategy Optimizer")
    parser.add_argument(
        "--tickers",
        type=str,
        default="",
        help="Comma-separated list of tickers (default: all available)",
    )
    parser.add_argument(
        "--train-days", type=int, default=10, help="Number of in-sample training days"
    )
    parser.add_argument(
        "--test-days", type=int, default=3, help="Number of out-of-sample test days"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="strategy_overrides.json",
        help="Output file for strategy overrides",
    )
    parser.add_argument(
        "--parallel-all-strategies",
        action="store_true",
        help="Evaluate/run WFO windows with all eligible strategies active in parallel (all_enabled mode)",
    )
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
    print(f"Parallel All Strategies: {args.parallel_all_strategies}")

    loader = DataLoader()
    all_results: List[TickerOptResult] = []
    final_overrides: Dict[str, Dict[str, Any]] = {}

    for ticker in tickers:
        # Get available dates
        dates = get_trading_dates(ticker, loader)
        if not dates:
            print(f"\n⚠️  {ticker}: No data available")
            continue

        dr = discovery.get_date_range(ticker)
        if not dr["start"] or not dr["end"]:
            continue

        files = discovery.get_files_for_range(ticker, dr["start"], dr["end"])
        if not files:
            continue

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
            test_days=args.test_days,
            parallel_all_strategies=args.parallel_all_strategies,
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
        print(
            f"{r.ticker:6} | Train: {r.train_pnl:+6.2f}% ({r.train_trades:3} trades) | "
            f"Test: {icon} {r.test_pnl:+6.2f}% ({r.test_trades:3} trades)"
        )
        total_train_pnl += r.train_pnl
        total_test_pnl += r.test_pnl

    print("-" * 70)
    test_icon = "🟢" if total_test_pnl > 0 else "🔴"
    print(
        f"TOTAL  | Train: {total_train_pnl:+6.2f}% | Test: {test_icon} {total_test_pnl:+6.2f}%"
    )

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
            "tickers": tickers,
            "parallel_all_strategies": bool(args.parallel_all_strategies),
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
        "totals": {"train_pnl": total_train_pnl, "test_pnl": total_test_pnl},
    }
    results_path.write_text(json.dumps(results_data, indent=2))
    print(f"💾 Saved detailed results to: {results_path}")

    print("\n✅ Optimization complete!")


if __name__ == "__main__":
    main()
