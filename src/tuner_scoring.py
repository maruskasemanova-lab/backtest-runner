"""
Tuner Scoring - Scoring functions for adaptive tuner candidate evaluation.

This module provides scoring functions for evaluating backtest results
during adaptive tuning, including robust scoring that penalizes overfitting.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger("TunerScoring")


def compute_tuner_score(
    score_metric: str,
    total_pnl_pct: float,
    total_pnl_dollars: float,
    avg_win_rate_pct: float,
    total_trades: int,
    valid_days: int,
) -> float:
    """
    Compute tuner score based on specified metric.
    
    Args:
        score_metric: Metric to use (pnl_pct, pnl_dollars, win_rate, trade_adjusted)
        total_pnl_pct: Total PnL percentage
        total_pnl_dollars: Total PnL in dollars
        avg_win_rate_pct: Average win rate percentage
        total_trades: Total number of trades
        valid_days: Number of valid trading days
        
    Returns:
        Computed score value
    """
    if valid_days <= 0:
        return -1_000_000.0
    
    avg_pnl_pct = total_pnl_pct / valid_days
    avg_pnl_dollars = total_pnl_dollars / valid_days
    trade_density = total_trades / valid_days
    
    metric = str(score_metric or "pnl_pct").strip().lower()
    
    if metric == "pnl_dollars":
        base = avg_pnl_dollars
    elif metric == "win_rate":
        base = avg_win_rate_pct
    elif metric == "trade_adjusted":
        base = avg_pnl_pct + min(5.0, trade_density * 0.2)
    else:
        base = avg_pnl_pct
    
    if total_trades <= 0:
        return base - 1.0
    
    return base


def compute_tuner_score_robust(
    day_results: List[Dict[str, Any]],
) -> float:
    """
    Robust scoring that penalizes overfit by requiring consistency across days.

    Components:
    1. Consistency penalty: high day-to-day PnL variance = overfit
    2. Win-rate floor: < 40% overall → heavy penalty
    3. Positive-day ratio: must be profitable on ≥50% of days
    4. Trade-count normalization: don't reward raw trade count
    
    Args:
        day_results: List of daily result dictionaries
        
    Returns:
        Robust score value
    """
    valid = [d for d in day_results if d.get("success")]
    if not valid:
        return -1_000_000.0

    n_days = len(valid)
    daily_pnl = [float(d.get("pnl_pct", 0.0)) for d in valid]
    daily_trades = [int(d.get("trades", 0)) for d in valid]
    daily_wr = [float(d.get("win_rate_pct", 0.0)) for d in valid]

    total_trades = sum(daily_trades)
    if total_trades <= 0:
        return -1.0

    # — Average daily PnL (base metric) —
    avg_pnl = sum(daily_pnl) / n_days

    # — 1. Consistency factor (coefficient of variation penalty) —
    # Low CV = consistent across days = likely real edge
    # High CV = volatile across days = likely noise
    mean_abs = max(abs(avg_pnl), 0.001)
    variance = sum((p - avg_pnl) ** 2 for p in daily_pnl) / n_days
    std_dev = variance ** 0.5
    cv = std_dev / mean_abs  # coefficient of variation
    consistency = 1.0 / (1.0 + cv)  # 0→1, higher = more consistent

    # — 2. Expectancy-based quality gate —
    # Uses per-trade PnL as expectancy proxy. This correctly values strategies
    # with low win-rate but high risk-reward (e.g. 40% WR / 2.5:1 RR).
    daily_expectancy = []
    for d in valid:
        pnl = float(d.get("pnl_pct", 0.0))
        trades = max(int(d.get("trades", 0)), 1)
        daily_expectancy.append(pnl / trades)

    avg_expectancy = (
        sum(daily_expectancy) / len(daily_expectancy) if daily_expectancy else 0.0
    )
    if avg_expectancy < -0.05:
        quality_gate = 0.3   # losing per trade → heavy penalty
    elif avg_expectancy < 0.0:
        quality_gate = 0.6   # marginal negative → moderate penalty
    elif avg_expectancy < 0.02:
        quality_gate = 0.85  # marginal positive → slight discount
    else:
        quality_gate = 1.0   # clearly positive expectancy → no penalty

    # — 3. Positive-day ratio —
    positive_days = sum(1 for p in daily_pnl if p > 0)
    positive_ratio = positive_days / n_days
    if positive_ratio < 0.50:
        # Profitable on fewer than half the days → likely noise
        day_penalty = 0.5
    else:
        day_penalty = 1.0

    # — 4. Trade-count normalization —
    # Penalize excessive trading (>3 trades/day average → diminishing returns)
    avg_trades_per_day = total_trades / n_days
    if avg_trades_per_day > 3.0:
        trade_norm = 1.0 - min(0.3, (avg_trades_per_day - 3.0) * 0.05)
    else:
        trade_norm = 1.0

    # — 5. Min-trade gate —
    # Relaxed thresholds: flow-based strategies may legitimately produce
    # fewer trades while still having positive expectancy.
    if avg_trades_per_day < 0.5:
        trade_scarcity = 0.25  # truly no signal → heavy penalty
    elif avg_trades_per_day < 1.0:
        trade_scarcity = 0.65  # sparse but possible for flow strategies
    else:
        trade_scarcity = 1.0   # 1+ trade/day is sufficient

    # — 6. L2-confirmation bonus —
    # Reward profiles where L2 order-flow features confirmed entries.
    # Capped at +10% to avoid creating a new overfit vector.
    l2_confirmed_days = sum(
        1 for d in valid if float(d.get("l2_avg_score", 0.0)) > 0.3
    )
    l2_ratio = l2_confirmed_days / n_days if n_days > 0 else 0.0
    l2_bonus = 1.0 + (l2_ratio * 0.10)  # up to +10%

    # — Final robust score —
    score = avg_pnl * consistency * quality_gate * day_penalty * trade_norm * trade_scarcity
    score *= l2_bonus
    return round(score, 6)


def compute_adaptive_score(
    score_metric: str,
    total_pnl_pct: float,
    total_pnl_dollars: float,
    avg_win_rate_pct: float,
    total_trades: int,
    valid_days: int,
) -> float:
    """
    Compute adaptive score (alias for compute_tuner_score).
    
    Args:
        score_metric: Metric to use
        total_pnl_pct: Total PnL percentage
        total_pnl_dollars: Total PnL in dollars
        avg_win_rate_pct: Average win rate percentage
        total_trades: Total number of trades
        valid_days: Number of valid trading days
        
    Returns:
        Computed score value
    """
    return compute_tuner_score(
        score_metric,
        total_pnl_pct,
        total_pnl_dollars,
        avg_win_rate_pct,
        total_trades,
        valid_days,
    )


def compute_adaptive_score_robust(
    day_results: List[Dict[str, Any]],
) -> float:
    """
    Compute robust adaptive score (alias for compute_tuner_score_robust).
    
    Args:
        day_results: List of daily result dictionaries
        
    Returns:
        Robust score value
    """
    return compute_tuner_score_robust(day_results)


def aggregate_day_results(
    day_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Aggregate daily results into summary metrics.
    
    Args:
        day_results: List of daily result dictionaries
        
    Returns:
        Aggregated summary dictionary
    """
    valid = [d for d in day_results if d.get("success")]
    
    if not valid:
        return {
            "valid_days": 0,
            "total_pnl_pct": 0.0,
            "total_pnl_dollars": 0.0,
            "total_trades": 0,
            "avg_win_rate_pct": 0.0,
        }
    
    n_days = len(valid)
    total_pnl_pct = sum(float(d.get("pnl_pct", 0.0)) for d in valid)
    total_pnl_dollars = sum(float(d.get("pnl_dollars", 0.0)) for d in valid)
    total_trades = sum(int(d.get("trades", 0)) for d in valid)
    
    # Weighted average win rate by trade count
    if total_trades > 0:
        weighted_wr = sum(
            float(d.get("win_rate_pct", 0.0)) * int(d.get("trades", 0))
            for d in valid
        ) / total_trades
    else:
        weighted_wr = 0.0
    
    return {
        "valid_days": n_days,
        "total_pnl_pct": total_pnl_pct,
        "total_pnl_dollars": total_pnl_dollars,
        "total_trades": total_trades,
        "avg_win_rate_pct": weighted_wr,
    }
