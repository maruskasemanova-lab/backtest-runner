#!/usr/bin/env python3
"""
Short-Term Trend Analysis for AOS

Identifies intraday momentum patterns:
1. Early trend detection (first 15-30 mins)
2. Trend continuation probability
3. Reversal detection
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, time
from typing import Dict, List, Any, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    # For demo, analyze based on trade results
    results_dir = REPO_ROOT / "aos_walk_forward_results"
    csv_files = sorted(results_dir.glob("aos_trades_*.csv"))

    if not csv_files:
        print("No trade files found")
        raise SystemExit(0)

    df = pd.read_csv(csv_files[-1])
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])

    print("=" * 70)
    print("📈 SHORT-TERM TREND ANALYSIS")
    print("=" * 70)

    # Group by date
    df["date"] = df["entry_time"].dt.date

    # Analyze trend patterns per day
    daily_patterns = []

    for date, day_df in df.groupby("date"):
        day_df = day_df.sort_values("entry_time")
        trades = day_df.to_dict("records")

        if len(trades) < 2:
            continue

        # First trade sets the tone
        first_trade = trades[0]
        first_pnl = first_trade["pnl_dollars"]
        first_side = first_trade["side"]

        # Calculate subsequent trades
        subsequent_same_side = [t for t in trades[1:] if t["side"] == first_side]
        subsequent_opposite = [t for t in trades[1:] if t["side"] != first_side]

        same_side_pnl = (
            sum(t["pnl_dollars"] for t in subsequent_same_side)
            if subsequent_same_side
            else 0
        )
        opposite_pnl = (
            sum(t["pnl_dollars"] for t in subsequent_opposite)
            if subsequent_opposite
            else 0
        )

        # Total day direction
        total_pnl = day_df["pnl_dollars"].sum()
        longs_pnl = day_df[day_df["side"] == "long"]["pnl_dollars"].sum()
        shorts_pnl = day_df[day_df["side"] == "short"]["pnl_dollars"].sum()

        daily_patterns.append(
            {
                "date": date,
                "first_side": first_side,
                "first_pnl": first_pnl,
                "same_side_pnl": same_side_pnl,
                "opposite_pnl": opposite_pnl,
                "total_pnl": total_pnl,
                "longs_pnl": longs_pnl,
                "shorts_pnl": shorts_pnl,
                "trend": (
                    "BULLISH"
                    if longs_pnl > shorts_pnl
                    else "BEARISH" if shorts_pnl > longs_pnl else "NEUTRAL"
                ),
            }
        )

    patterns_df = pd.DataFrame(daily_patterns)

    print("\n📊 DAILY TREND ANALYSIS")
    print("-" * 50)

    for _, row in patterns_df.iterrows():
        trend_icon = (
            "📈"
            if row["trend"] == "BULLISH"
            else "📉" if row["trend"] == "BEARISH" else "➡️"
        )
        pnl_icon = "🟢" if row["total_pnl"] >= 0 else "🔴"
        print(
            f"  {row['date']} | {trend_icon} {row['trend']:8} | "
            f"{pnl_icon} ${row['total_pnl']:+8.2f} | "
            f"L: ${row['longs_pnl']:+.0f} / S: ${row['shorts_pnl']:+.0f}"
        )

    print("\n📊 TREND CONTINUATION ANALYSIS")
    print("-" * 50)

    # First trade winner analysis
    first_winners = patterns_df[patterns_df["first_pnl"] > 0]
    first_losers = patterns_df[patterns_df["first_pnl"] <= 0]

    print(f"\nWhen FIRST trade WINS:")
    if len(first_winners) > 0:
        same_side_after_win = first_winners["same_side_pnl"].mean()
        opp_side_after_win = first_winners["opposite_pnl"].mean()
        print(f"  Same direction avg: ${same_side_after_win:+.2f}")
        print(f"  Opposite direction avg: ${opp_side_after_win:+.2f}")
        better = "CONTINUE" if same_side_after_win > opp_side_after_win else "REVERSE"
        print(f"  → Better to: {better}")

    print(f"\nWhen FIRST trade LOSES:")
    if len(first_losers) > 0:
        same_side_after_loss = first_losers["same_side_pnl"].mean()
        opp_side_after_loss = first_losers["opposite_pnl"].mean()
        print(f"  Same direction avg: ${same_side_after_loss:+.2f}")
        print(f"  Opposite direction avg: ${opp_side_after_loss:+.2f}")
        better = "PERSIST" if same_side_after_loss > opp_side_after_loss else "FLIP"
        print(f"  → Better to: {better}")

    print("\n📊 LONG vs SHORT ANALYSIS")
    print("-" * 50)

    longs = df[df["side"] == "long"]
    shorts = df[df["side"] == "short"]

    print(f"\n  LONG trades:")
    print(f"    Count: {len(longs)}")
    print(f"    Total PnL: ${longs['pnl_dollars'].sum():+.2f}")
    print(
        f"    Win Rate: {len(longs[longs['pnl_dollars'] > 0]) / len(longs) * 100:.1f}%"
        if len(longs) > 0
        else "0%"
    )

    print(f"\n  SHORT trades:")
    print(f"    Count: {len(shorts)}")
    print(f"    Total PnL: ${shorts['pnl_dollars'].sum():+.2f}")
    print(
        f"    Win Rate: {len(shorts[shorts['pnl_dollars'] > 0]) / len(shorts) * 100:.1f}%"
        if len(shorts) > 0
        else "0%"
    )

    print("\n" + "=" * 70)
    print("💡 RECOMMENDATIONS FOR SHORT-TERM TRENDS")
    print("=" * 70)

    # Generate recommendations
    long_pnl = longs["pnl_dollars"].sum() if len(longs) > 0 else 0
    short_pnl = shorts["pnl_dollars"].sum() if len(shorts) > 0 else 0

    if long_pnl > 0 and short_pnl < 0:
        print("  ✅ LONG bias is more profitable - consider disabling shorts")
    elif short_pnl > 0 and long_pnl < 0:
        print("  ✅ SHORT bias is more profitable - consider disabling longs")
    else:
        print("  ➡️ Both directions show mixed results - use regime to decide")

    if len(first_losers) > 0:
        if (
            first_losers["same_side_pnl"].mean() < 0
            and first_losers["opposite_pnl"].mean() > 0
        ):
            print("  ✅ After first loss, FLIP direction for better results")
        elif first_losers["same_side_pnl"].mean() > first_losers["opposite_pnl"].mean():
            print("  ✅ After first loss, PERSIST in same direction")

    print("\n" + "=" * 70)
