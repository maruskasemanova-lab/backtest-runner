#!/usr/bin/env python3
"""Analyze MU tuning results and generate recommendations."""

import json
from pathlib import Path

if __name__ == "__main__":
    report_path = Path("reports/mu_tuner_options_20260213_154929.json")

    with open(report_path) as f:
        data = json.load(f)

    profiles = data.get("profiles", [])

    print("=" * 80)
    print("MU TUNING RESULTS ANALYSIS")
    print("=" * 80)
    print(f"\nTotal profiles: {len(profiles)}")
    print(f"L2 coverage: {data.get('l2_overlap_range', {})}")

    # Sort by score
    sorted_profiles = sorted(profiles, key=lambda x: x.get("score", -999), reverse=True)

    print("\n" + "-" * 80)
    print("TOP 10 PROFILES BY SCORE")
    print("-" * 80)

    for i, p in enumerate(sorted_profiles[:10]):
        m = p.get("metrics", {})
        c = p.get("candidate", {})

        print(f"\n{i+1}. Profile: {p.get('profile_id', 'N/A')}")
        print(f"   Score: {p.get('score', 0):.4f}")
        print(f"   Method: {p.get('method', 'N/A')}")
        print(f"   Trades: {m.get('total_trades', 0)}")
        print(f"   PnL: {m.get('total_pnl_pct', 0):.2f}%")
        print(f"   Win Rate: {m.get('avg_win_rate_pct', 0):.1f}%")
        print(f"   Strategies: {c.get('enabled_strategies', [])}")
        print(f"   Regime Filter: {c.get('regime_filter', [])}")
        print(f"   L2 Delta: {c.get('l2_min_delta', 0)}")
        print(f"   L2 Imbalance: {c.get('l2_min_imbalance', 0)}")

    # Find best by different metrics
    print("\n" + "-" * 80)
    print("BEST BY METRIC")
    print("-" * 80)

    valid_profiles = [
        p for p in profiles if p.get("metrics", {}).get("total_trades", 0) > 0
    ]

    if valid_profiles:
        best_pnl = max(
            valid_profiles,
            key=lambda x: x.get("metrics", {}).get("total_pnl_pct", -999),
        )
        print(f"\nBest PnL: {best_pnl.get('profile_id', 'N/A')}")
        print(f"   PnL: {best_pnl.get('metrics', {}).get('total_pnl_pct', 0):.2f}%")

        best_wr = max(
            valid_profiles,
            key=lambda x: x.get("metrics", {}).get("avg_win_rate_pct", 0),
        )
        print(f"\nBest Win Rate: {best_wr.get('profile_id', 'N/A')}")
        print(f"   WR: {best_wr.get('metrics', {}).get('avg_win_rate_pct', 0):.1f}%")

        best_trades = max(
            valid_profiles, key=lambda x: x.get("metrics", {}).get("total_trades", 0)
        )
        print(f"\nMost Trades: {best_trades.get('profile_id', 'N/A')}")
        print(f"   Trades: {best_trades.get('metrics', {}).get('total_trades', 0)}")

    # Strategy analysis
    print("\n" + "-" * 80)
    print("STRATEGY PERFORMANCE")
    print("-" * 80)

    strategy_stats = {}
    for p in valid_profiles:
        strategies = p.get("candidate", {}).get("enabled_strategies", [])
        pnl = p.get("metrics", {}).get("total_pnl_pct", 0)
        trades = p.get("metrics", {}).get("total_trades", 0)

        for s in strategies:
            if s not in strategy_stats:
                strategy_stats[s] = {"count": 0, "total_pnl": 0, "total_trades": 0}
            strategy_stats[s]["count"] += 1
            strategy_stats[s]["total_pnl"] += pnl
            strategy_stats[s]["total_trades"] += trades

    for s, stats in sorted(
        strategy_stats.items(), key=lambda x: x[1]["total_pnl"], reverse=True
    ):
        avg_pnl = stats["total_pnl"] / stats["count"] if stats["count"] > 0 else 0
        print(f"\n{s}:")
        print(f"   Profiles: {stats['count']}")
        print(f"   Total PnL: {stats['total_pnl']:.2f}%")
        print(f"   Avg PnL: {avg_pnl:.2f}%")
        print(f"   Total Trades: {stats['total_trades']}")

    # Generate recommendation
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if valid_profiles:
        # Find profile with best balance of PnL and trades
        balanced = sorted(
            valid_profiles,
            key=lambda x: (
                x.get("metrics", {}).get("total_pnl_pct", 0)
                * min(1.0, x.get("metrics", {}).get("total_trades", 0) / 10)
            ),
            reverse=True,
        )[0]

        print(f"\nRecommended Profile: {balanced.get('profile_id', 'N/A')}")
        print(f"   Score: {balanced.get('score', 0):.4f}")
        print(f"   PnL: {balanced.get('metrics', {}).get('total_pnl_pct', 0):.2f}%")
        print(f"   Trades: {balanced.get('metrics', {}).get('total_trades', 0)}")
        print(
            f"   Win Rate: {balanced.get('metrics', {}).get('avg_win_rate_pct', 0):.1f}%"
        )

        c = balanced.get("candidate", {})
        print(f"\nConfiguration:")
        print(json.dumps(c, indent=2, default=str))
