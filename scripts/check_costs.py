#!/usr/bin/env python3
"""Check if costs are included in backtest results."""

import json
from pathlib import Path

# Check tuner results
tuner_path = Path("reports/mu_tuner_options_20260213_154929.json")
with open(tuner_path) as f:
    d = json.load(f)

profiles = d.get("profiles", [])
best = max(profiles, key=lambda x: x.get("score", -999))
m = best.get("metrics", {})

print("=" * 80)
print("BEST PROFILE COST ANALYSIS")
print("=" * 80)
print(f"Profile ID: {best.get('profile_id', 'N/A')}")
print(f"Total PnL: {m.get('total_pnl_pct', 0):.2f}%")
print(f"Total Trades: {m.get('total_trades', 0)}")
print(f"Win Rate: {m.get('avg_win_rate_pct', 0):.1f}%")
print(f"Total Costs: ${m.get('total_costs', 0):.2f}")

# Check individual trades
trades = m.get("trades", [])
print(f"\nSample Trades ({len(trades)} total):")
for t in trades[:5]:
    pnl_pct = t.get("pnl_pct", 0)
    costs = t.get("total_costs", 0)
    gross = t.get("gross_pnl_pct", 0)
    print(f"  PnL: {pnl_pct:+.2f}%, Gross: {gross:+.2f}%, Costs: ${costs:.2f}")

# Check if costs are non-zero
total_costs = m.get("total_costs", 0)
if total_costs > 0:
    print(f"\n✅ Costs ARE included: ${total_costs:.2f} total")
else:
    print("\n⚠️ Costs may NOT be included (total_costs = 0)")

# Check a session summary for cost details
print("\n" + "=" * 80)
print("CHECKING SESSION SUMMARY FOR COST DETAILS")
print("=" * 80)

# Find a recent report with trades
reports_dir = Path("reports")
for report_dir in sorted(reports_dir.glob("*MU*"), reverse=True)[:3]:
    summary_path = report_dir / "session_summary.json"
    if summary_path.exists():
        with open(summary_path) as f:
            summary = json.load(f)
        
        overall = summary.get("overall", {})
        trades_list = summary.get("trades", [])
        
        print(f"\n{report_dir.name}:")
        print(f"  Total PnL: ${overall.get('total_pnl_dollars', 0):.2f}")
        print(f"  Total Costs: ${overall.get('total_costs', 0):.2f}")
        
        if trades_list:
            print(f"  Sample trade costs:")
            for t in trades_list[:2]:
                print(f"    - Costs: ${t.get('total_costs', 0):.2f}, Gross PnL: {t.get('gross_pnl_pct', 0):.2f}%")
        break
