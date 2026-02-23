#!/usr/bin/env python3
"""
Monte Carlo robustness analysis for trade sequences.

Usage:
  python monte_carlo.py --trades-file aos_trades_NVDA_2026-01-01_2026-02-01.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _pick_pnl_column(fieldnames: Iterable[str]) -> str:
    candidates = ["pnl_dollars", "pnl_pct", "pnl", "net_pnl"]
    fields = [f.strip() for f in fieldnames if f]
    for name in candidates:
        if name in fields:
            return name
    raise ValueError(f"No PnL column found. Supported columns: {candidates}")


def load_trade_pnls(csv_path: Path) -> Tuple[List[float], str]:
    with csv_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {csv_path}")
        pnl_col = _pick_pnl_column(reader.fieldnames)
        pnls: List[float] = []
        for row in reader:
            raw = row.get(pnl_col)
            if raw is None or raw == "":
                continue
            try:
                pnls.append(float(raw))
            except ValueError:
                continue
    if not pnls:
        raise ValueError(f"No valid pnl values found in column '{pnl_col}'")
    return pnls, pnl_col


def max_drawdown(equity_curve: List[float]) -> Tuple[float, float]:
    if not equity_curve:
        return 0.0, 0.0
    peak = equity_curve[0]
    worst_pct = 0.0
    worst_abs = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd_abs = peak - eq
        if dd_abs > worst_abs:
            worst_abs = dd_abs
        if peak > 0:
            dd = ((peak - eq) / peak) * 100.0
            if dd > worst_pct:
                worst_pct = dd
    return worst_pct, worst_abs


def simulate_drawdown_distribution(
    trade_pnls: List[float],
    iterations: int,
    start_equity: float,
    seed: int | None = None,
) -> Tuple[List[float], List[float]]:
    if seed is not None:
        random.seed(seed)

    drawdowns_pct: List[float] = []
    drawdowns_dollars: List[float] = []
    for _ in range(iterations):
        shuffled = trade_pnls[:]
        random.shuffle(shuffled)
        equity = start_equity
        curve = [equity]
        for pnl in shuffled:
            equity += pnl
            curve.append(equity)
        dd_pct, dd_abs = max_drawdown(curve)
        drawdowns_pct.append(dd_pct)
        drawdowns_dollars.append(dd_abs)
    drawdowns_pct.sort()
    drawdowns_dollars.sort()
    return drawdowns_pct, drawdowns_dollars


def percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(
        len(sorted_values) - 1,
        max(0, int(math.ceil((pct / 100.0) * len(sorted_values)) - 1)),
    )
    return float(sorted_values[idx])


def summarize(
    drawdowns_pct: List[float], drawdowns_dollars: List[float]
) -> Dict[str, float]:
    if not drawdowns_pct:
        return {}
    n = len(drawdowns_pct)
    mean_dd = sum(drawdowns_pct) / n
    median_dd = percentile(drawdowns_pct, 50)
    p90 = percentile(drawdowns_pct, 90)
    p95 = percentile(drawdowns_pct, 95)
    p99 = percentile(drawdowns_pct, 99)
    mean_dd_dollars = sum(drawdowns_dollars) / n if drawdowns_dollars else 0.0
    p95_dollars = percentile(drawdowns_dollars, 95) if drawdowns_dollars else 0.0
    return {
        "iterations": float(n),
        "mean_drawdown_pct": mean_dd,
        "median_drawdown_pct": median_dd,
        "p90_drawdown_pct": p90,
        "p95_drawdown_pct": p95,
        "p99_drawdown_pct": p99,
        "worst_drawdown_pct": max(drawdowns_pct),
        "mean_drawdown_dollars": mean_dd_dollars,
        "p95_drawdown_dollars": p95_dollars,
        "worst_drawdown_dollars": max(drawdowns_dollars) if drawdowns_dollars else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Monte Carlo drawdown analysis for trade sequences"
    )
    parser.add_argument(
        "--trades-file", required=True, help="Path to CSV with trade PnL values"
    )
    parser.add_argument(
        "--iterations", type=int, default=10_000, help="Number of Monte Carlo runs"
    )
    parser.add_argument(
        "--start-equity", type=float, default=10_000.0, help="Initial equity in dollars"
    )
    parser.add_argument(
        "--max-p95-drawdown-dollars",
        type=float,
        default=500.0,
        help="Validation threshold for P95 max drawdown in dollars (default: 500)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    args = parser.parse_args()

    csv_path = Path(args.trades_file)
    if not csv_path.exists():
        raise SystemExit(f"File not found: {csv_path}")

    trade_pnls, pnl_col = load_trade_pnls(csv_path)
    drawdowns_pct, drawdowns_dollars = simulate_drawdown_distribution(
        trade_pnls=trade_pnls,
        iterations=max(1, int(args.iterations)),
        start_equity=float(args.start_equity),
        seed=args.seed,
    )
    stats = summarize(drawdowns_pct, drawdowns_dollars)

    print(f"File: {csv_path}")
    print(f"Trades loaded: {len(trade_pnls)} | PnL column: {pnl_col}")
    print(f"Iterations: {int(stats['iterations'])}")
    print(f"Mean DD:   {stats['mean_drawdown_pct']:.2f}%")
    print(f"Median DD: {stats['median_drawdown_pct']:.2f}%")
    print(f"P90 DD:    {stats['p90_drawdown_pct']:.2f}%")
    print(f"P95 DD:    {stats['p95_drawdown_pct']:.2f}%")
    print(f"P99 DD:    {stats['p99_drawdown_pct']:.2f}%")
    print(f"Worst DD:  {stats['worst_drawdown_pct']:.2f}%")
    print(f"P95 DD $:  ${stats['p95_drawdown_dollars']:.2f}")
    print(f"Worst DD $:${stats['worst_drawdown_dollars']:.2f}")

    if stats["p95_drawdown_dollars"] > float(args.max_p95_drawdown_dollars):
        print(
            f"Risk flag: P95 max drawdown ${stats['p95_drawdown_dollars']:.2f} "
            f"is above ${float(args.max_p95_drawdown_dollars):.2f}"
        )
        raise SystemExit(2)
    else:
        print(
            f"Risk flag: P95 max drawdown ${stats['p95_drawdown_dollars']:.2f} "
            f"is within ${float(args.max_p95_drawdown_dollars):.2f}"
        )


if __name__ == "__main__":
    main()
