#!/usr/bin/env python3
"""
AOS Time-Based Analysis - Analyzes trades by time of day and short-term trends.

Identifies:
1. Best trading hours (morning vs afternoon)
2. Short-term trend patterns (intraday momentum)
3. Optimal time windows for each ticker
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = REPO_ROOT / "aos_walk_forward_results"


def load_trades_from_csv(csv_path: str) -> pd.DataFrame:
    """Load trades from CSV file."""
    df = pd.read_csv(csv_path)

    # Parse entry_time to extract hour
    df["entry_time_parsed"] = pd.to_datetime(df["entry_time"])
    df["entry_hour"] = df["entry_time_parsed"].dt.hour
    df["entry_minute"] = df["entry_time_parsed"].dt.minute

    # Create time period categories
    def get_time_period(hour, minute):
        time_val = hour * 60 + minute
        if time_val < 10 * 60:  # Before 10:00
            return "EARLY_AM"  # 9:30-10:00
        elif time_val < 11 * 60 + 30:  # 10:00-11:30
            return "LATE_AM"
        elif time_val < 14 * 60:  # 11:30-14:00
            return "MIDDAY"
        elif time_val < 15 * 60 + 30:  # 14:00-15:30
            return "LATE_PM"
        else:  # 15:30+
            return "CLOSE"

    df["time_period"] = df.apply(
        lambda row: get_time_period(row["entry_hour"], row["entry_minute"]), axis=1
    )

    return df


def analyze_by_time_period(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze trades by time period."""
    results = {}

    for period in ["EARLY_AM", "LATE_AM", "MIDDAY", "LATE_PM", "CLOSE"]:
        period_df = df[df["time_period"] == period]

        if len(period_df) == 0:
            continue

        total_trades = len(period_df)
        winners = len(period_df[period_df["pnl_dollars"] > 0])
        win_rate = winners / total_trades * 100 if total_trades > 0 else 0
        total_pnl = period_df["pnl_dollars"].sum()
        avg_pnl = period_df["pnl_dollars"].mean()

        results[period] = {
            "trades": total_trades,
            "winners": winners,
            "losers": total_trades - winners,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(avg_pnl, 2),
            "best_trade": round(period_df["pnl_dollars"].max(), 2),
            "worst_trade": round(period_df["pnl_dollars"].min(), 2),
        }

    return results


def analyze_by_ticker_and_time(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """Analyze trades by ticker and time period."""
    results = {}

    for ticker in df["ticker"].unique():
        ticker_df = df[df["ticker"] == ticker]
        results[ticker] = analyze_by_time_period(ticker_df)

    return results


def analyze_short_trends(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze short-term trend patterns.

    Looking for:
    1. Consecutive winning/losing trades
    2. Momentum after first trade
    3. Reversal patterns
    """
    results = {
        "consecutive_patterns": {},
        "first_trade_analysis": {},
        "momentum_continuation": {},
    }

    # Group by date and ticker
    for (date, ticker), group in df.groupby(["date", "ticker"]):
        trades = group.sort_values("entry_time_parsed").to_dict("records")

        if len(trades) < 2:
            continue

        # First trade analysis
        first_pnl = trades[0]["pnl_dollars"]
        subsequent_pnl = sum(t["pnl_dollars"] for t in trades[1:])

        key = "first_win" if first_pnl > 0 else "first_loss"
        if key not in results["first_trade_analysis"]:
            results["first_trade_analysis"][key] = {
                "count": 0,
                "subsequent_pnl": 0,
                "subsequent_avg": 0,
            }

        results["first_trade_analysis"][key]["count"] += 1
        results["first_trade_analysis"][key]["subsequent_pnl"] += subsequent_pnl

    # Calculate averages
    for key in results["first_trade_analysis"]:
        count = results["first_trade_analysis"][key]["count"]
        if count > 0:
            results["first_trade_analysis"][key]["subsequent_avg"] = round(
                results["first_trade_analysis"][key]["subsequent_pnl"] / count, 2
            )

    # Consecutive patterns
    for (date, ticker), group in df.groupby(["date", "ticker"]):
        trades = group.sort_values("entry_time_parsed")["pnl_dollars"].tolist()

        if len(trades) < 2:
            continue

        # Check for consecutive wins/losses
        for i in range(len(trades) - 1):
            if trades[i] > 0 and trades[i + 1] > 0:
                pattern = "win_then_win"
            elif trades[i] > 0 and trades[i + 1] <= 0:
                pattern = "win_then_loss"
            elif trades[i] <= 0 and trades[i + 1] > 0:
                pattern = "loss_then_win"
            else:
                pattern = "loss_then_loss"

            if pattern not in results["consecutive_patterns"]:
                results["consecutive_patterns"][pattern] = 0
            results["consecutive_patterns"][pattern] += 1

    return results


def find_optimal_time_windows(df: pd.DataFrame) -> Dict[str, Any]:
    """Find optimal trading time windows based on profitability."""

    # Create hourly analysis
    hourly = (
        df.groupby("entry_hour")
        .agg({"pnl_dollars": ["sum", "count", "mean"], "trade_id": "count"})
        .round(2)
    )

    # Find best and worst hours
    hour_pnl = df.groupby("entry_hour")["pnl_dollars"].sum()
    best_hour = hour_pnl.idxmax()
    worst_hour = hour_pnl.idxmin()

    # Calculate cumulative PnL by time
    profitable_hours = hour_pnl[hour_pnl > 0].index.tolist()
    losing_hours = hour_pnl[hour_pnl <= 0].index.tolist()

    # Morning (9:30-11:30) vs Afternoon (14:00-16:00) analysis
    morning_df = df[(df["entry_hour"] >= 9) & (df["entry_hour"] < 12)]
    afternoon_df = df[(df["entry_hour"] >= 14) & (df["entry_hour"] < 16)]

    morning_pnl = morning_df["pnl_dollars"].sum() if len(morning_df) > 0 else 0
    afternoon_pnl = afternoon_df["pnl_dollars"].sum() if len(afternoon_df) > 0 else 0

    return {
        "best_hour": int(best_hour),
        "worst_hour": int(worst_hour),
        "profitable_hours": [int(h) for h in profitable_hours],
        "losing_hours": [int(h) for h in losing_hours],
        "morning_pnl": round(morning_pnl, 2),
        "afternoon_pnl": round(afternoon_pnl, 2),
        "recommended_session": (
            "MORNING" if morning_pnl > afternoon_pnl else "AFTERNOON"
        ),
        "hourly_breakdown": {
            int(hour): round(pnl, 2) for hour, pnl in hour_pnl.items()
        },
    }


def generate_time_filter_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """Generate specific recommendations for time filters."""
    recommendations = []

    optimal = analysis["optimal_time_windows"]

    # Session recommendation
    if optimal["morning_pnl"] > 0 and optimal["afternoon_pnl"] <= 0:
        recommendations.append(
            f"Trade MORNING session only (9:30-11:30): +${optimal['morning_pnl']}"
        )
        recommendations.append(f"SKIP afternoon session: ${optimal['afternoon_pnl']}")
    elif optimal["afternoon_pnl"] > 0 and optimal["morning_pnl"] <= 0:
        recommendations.append(
            f"Trade AFTERNOON session only (14:00-16:00): +${optimal['afternoon_pnl']}"
        )
        recommendations.append(f"SKIP morning session: ${optimal['morning_pnl']}")
    else:
        recommendations.append(
            f"Morning: ${optimal['morning_pnl']}, Afternoon: ${optimal['afternoon_pnl']}"
        )

    # Specific hour recommendations
    if optimal["profitable_hours"]:
        hours_str = ", ".join([f"{h}:00" for h in sorted(optimal["profitable_hours"])])
        recommendations.append(f"Profitable hours: {hours_str}")

    if optimal["losing_hours"]:
        hours_str = ", ".join([f"{h}:00" for h in sorted(optimal["losing_hours"])])
        recommendations.append(f"Avoid trading at: {hours_str}")

    # Pattern-based recommendations
    patterns = analysis.get("short_trends", {}).get("first_trade_analysis", {})
    if "first_loss" in patterns:
        first_loss = patterns["first_loss"]
        if first_loss["subsequent_avg"] < 0:
            recommendations.append(
                f"After first LOSS, subsequent trades average ${first_loss['subsequent_avg']} - "
                "consider stopping for the day"
            )

    return recommendations


if __name__ == "__main__":
    import sys

    csv_path = sys.argv[1] if len(sys.argv) > 1 else None

    # Find latest CSV if not specified
    if csv_path is None:
        results_dir = DEFAULT_RESULTS_DIR
        csv_files = sorted(results_dir.glob("aos_trades_*.csv"))
        if not csv_files:
            print("No trade CSV files found!")
            raise SystemExit(0)
        csv_path = str(csv_files[-1])

    print("=" * 80)
    print("⏰ AOS TIME-BASED ANALYSIS")
    print("=" * 80)
    print(f"Analyzing: {csv_path}")

    # Load data
    df = load_trades_from_csv(csv_path)
    print(f"Total trades: {len(df)}")

    # Run analyses
    analysis = {
        "by_time_period": analyze_by_time_period(df),
        "by_ticker_and_time": analyze_by_ticker_and_time(df),
        "short_trends": analyze_short_trends(df),
        "optimal_time_windows": find_optimal_time_windows(df),
    }

    # Print results
    print("\n" + "=" * 60)
    print("📊 PROFITABILITY BY TIME PERIOD")
    print("=" * 60)

    for period, data in analysis["by_time_period"].items():
        icon = "🟢" if data["total_pnl"] >= 0 else "🔴"
        print(f"\n{period}:")
        print(
            f"  {icon} PnL: ${data['total_pnl']:+.2f} | "
            f"Trades: {data['trades']} | "
            f"Win%: {data['win_rate']}%"
        )
        print(
            f"     Avg: ${data['avg_pnl']:+.2f} | "
            f"Best: ${data['best_trade']:+.2f} | "
            f"Worst: ${data['worst_trade']:.2f}"
        )

    print("\n" + "=" * 60)
    print("📊 OPTIMAL TIME WINDOWS")
    print("=" * 60)

    optimal = analysis["optimal_time_windows"]
    print(f"\n  Best Hour:      {optimal['best_hour']}:00")
    print(f"  Worst Hour:     {optimal['worst_hour']}:00")
    print(f"  Morning PnL:    ${optimal['morning_pnl']:+.2f}")
    print(f"  Afternoon PnL:  ${optimal['afternoon_pnl']:+.2f}")
    print(f"  Recommended:    {optimal['recommended_session']} session")

    print("\n  Hourly breakdown:")
    for hour, pnl in sorted(optimal["hourly_breakdown"].items()):
        bar = "█" * int(abs(pnl) / 10) if pnl != 0 else ""
        icon = "+" if pnl > 0 else "-" if pnl < 0 else " "
        print(f"    {hour:02d}:00 | {icon}${abs(pnl):6.2f} {bar}")

    print("\n" + "=" * 60)
    print("📊 SHORT-TERM TREND PATTERNS")
    print("=" * 60)

    patterns = analysis["short_trends"]["consecutive_patterns"]
    if patterns:
        total = sum(patterns.values())
        print("\n  Consecutive trade patterns:")
        for pattern, count in sorted(
            patterns.items(), key=lambda x: x[1], reverse=True
        ):
            pct = count / total * 100
            print(f"    {pattern:15} : {count:3} ({pct:.1f}%)")

    first_trade = analysis["short_trends"]["first_trade_analysis"]
    if first_trade:
        print("\n  After first trade of day:")
        for key, data in first_trade.items():
            print(
                f"    {key}: subsequent avg = ${data['subsequent_avg']:+.2f} ({data['count']} days)"
            )

    print("\n" + "=" * 60)
    print("💡 RECOMMENDATIONS")
    print("=" * 60)

    recommendations = generate_time_filter_recommendations(analysis)
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec}")

    print("\n" + "=" * 80)

    # Save analysis
    output_path = DEFAULT_RESULTS_DIR / "time_analysis.json"
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2, default=str)
    print(f"\n💾 Analysis saved to: {output_path}")
