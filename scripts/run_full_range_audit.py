#!/usr/bin/env python3
"""
Run MU backtests across the full date range day-by-day via API.
Collects per-day results for overfitting analysis.

Usage:
    python3 scripts/run_full_range_audit.py [--run-id PREFIX] [--no-context-risk] [--start-date 2025-10-01]
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

RUNNER_URL = "http://localhost:8002"
STRATEGY_URL = "http://localhost:8001"
TICKER = "MU"
ACCOUNT_SIZE = 10_000.0


def get_covered_days(date_from="2025-10-01", date_to="2026-02-28"):
    """Get all covered trading days from the diagnose endpoint."""
    resp = requests.post(f"{RUNNER_URL}/api/run/diagnose", json={
        "ticker": TICKER,
        "prewarm_scope": "range",
        "date_from": date_from,
        "date_to": date_to,
    }, timeout=30)
    data = resp.json()
    return data.get("coverage", {}).get("ohlcv_1m", {}).get("covered_days", [])


def run_single_day(run_id, date, no_context_risk=False):
    """Run a single day backtest and return results."""
    req = {
        "run_id": run_id,
        "ticker": TICKER,
        "date": date,
        "strategy_api_url": STRATEGY_URL,
        "account_size_usd": ACCOUNT_SIZE,
        "comparable_mode": True,
        "cold_start_each_day": True,
        "include_extended_hours": True,
        "l2_confirm_enabled": True,
        "apply_positioning_config_on_start": True,
        "apply_ticker_overrides_on_start": True,
        "apply_aos_optimizations_on_start": True,
        "intraday_levels_enabled": True,
        "intraday_levels_entry_quality_enabled": True,
        "intraday_levels_spike_detection_enabled": True,
        "intraday_levels_gap_analysis_enabled": True,
    }
    if no_context_risk:
        req["context_aware_risk_enabled"] = False
    else:
        req["context_aware_risk_enabled"] = True
        req["context_risk_min_room_pct"] = 0.04
        req["context_risk_min_effective_rr"] = 0.25
        req["context_risk_min_sl_pct"] = 0.15
        req["context_risk_max_anchor_search_pct"] = 1.5

    # Start the run
    try:
        resp = requests.post(f"{RUNNER_URL}/api/run/start", json=req, timeout=30)
        if resp.status_code != 200:
            return {"date": date, "error": f"start failed: {resp.status_code}", "trades": []}
        start_data = resp.json()
        total_bars = start_data.get("total_bars", 0)
    except Exception as e:
        return {"date": date, "error": str(e), "trades": []}

    # Play the run
    try:
        requests.post(f"{RUNNER_URL}/api/run/{run_id}/{TICKER}/{date}/play", timeout=5)
    except Exception:
        pass

    # Poll for completion
    max_wait = 300
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            state_resp = requests.get(
                f"{RUNNER_URL}/api/run/{run_id}/{TICKER}/{date}/state", timeout=10
            )
            if state_resp.status_code == 200:
                state = state_resp.json()
                phase = state.get("phase", "")
                if phase in ("COMPLETED", "END_OF_DAY", "ERROR", "FAILED", "STOPPED"):
                    break
        except Exception:
            pass
        time.sleep(1.0)

    # Get summary
    time.sleep(0.5)
    try:
        summary_resp = requests.get(
            f"{RUNNER_URL}/api/run/{run_id}/{TICKER}/{date}/summary", timeout=15
        )
        if summary_resp.status_code == 200:
            summary = summary_resp.json()
        else:
            summary = {"date": date, "error": f"summary {summary_resp.status_code}"}
    except Exception as e:
        summary = {"date": date, "error": str(e)}

    # Use session_summary if available (more reliable than marker parsing)
    sess = summary.get("session_summary", {}) or {}
    trades_from_summary = sess.get("trades", [])

    # Also extract trades from markers as fallback
    trades = []
    if trades_from_summary:
        for t in trades_from_summary:
            trades.append({
                "strategy": t.get("strategy", ""),
                "side": t.get("side", ""),
                "entry_price": t.get("entry_price"),
                "exit_price": t.get("exit_price"),
                "pnl_pct": t.get("pnl_pct", 0),
                "pnl_dollars": t.get("pnl_dollars", 0),
                "exit_reason": t.get("exit_reason", ""),
                "regime": t.get("regime", ""),
            })
    else:
        markers = summary.get("markers", [])
        for m in markers:
            if m.get("marker_type") in ("exit_executed", "exit_stop_loss", "exit_time", "exit_eod"):
                details = m.get("details", {})
                trades.append({
                    "strategy": m.get("strategy", ""),
                    "side": details.get("side", m.get("side", "")),
                    "entry_price": details.get("entry_price"),
                    "exit_price": details.get("exit_price", m.get("price")),
                    "pnl_pct": details.get("pnl_pct", 0),
                    "pnl_dollars": details.get("pnl_dollars", 0),
                    "exit_reason": m.get("marker_type", ""),
                    "regime": m.get("regime", ""),
                })

    # Prefer session_summary aggregates when available
    total_pnl = float(sess.get("total_pnl_dollars", 0) or 0) if sess.get("total_trades") else sum(t.get("pnl_dollars", 0) or 0 for t in trades)
    total_pnl_pct = float(sess.get("total_pnl_pct", 0) or 0) if sess.get("total_trades") else sum(t.get("pnl_pct", 0) or 0 for t in trades)
    ntrades = int(sess.get("total_trades", 0) or 0) if sess.get("total_trades") else len(trades)
    wins = int(sess.get("winning_trades", 0) or 0) if sess.get("total_trades") else sum(1 for t in trades if (t.get("pnl_dollars", 0) or 0) > 0)

    return {
        "date": date,
        "total_bars": total_bars,
        "total_trades": ntrades,
        "total_pnl_dollars": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 4),
        "wins": wins,
        "losses": ntrades - wins,
        "win_rate": round(wins / ntrades * 100, 1) if ntrades else 0,
        "trades": trades,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="audit", help="Run ID prefix")
    parser.add_argument("--no-context-risk", action="store_true")
    parser.add_argument("--start-date", default="2025-10-01")
    parser.add_argument("--end-date", default="2026-02-28")
    args = parser.parse_args()

    label = "no_cr" if args.no_context_risk else "baseline"
    output_path = Path("analysis") / f"mu_full_audit_{label}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    output_path.parent.mkdir(exist_ok=True)

    # Get available days
    print(f"Getting covered days for {TICKER}...")
    days = get_covered_days(args.start_date, args.end_date)
    if args.start_date:
        days = [d for d in days if d >= args.start_date]
    print(f"Found {len(days)} trading days: {days[0]} to {days[-1]}")

    results = []
    cumulative_pnl = 0
    total_trades = 0
    winning_days = 0
    losing_days = 0
    flat_days = 0

    for i, date in enumerate(days):
        run_id = f"{args.run_id}-{label}-{date}"
        print(f"[{i+1}/{len(days)}] {date}...", end=" ", flush=True)
        t0 = time.time()

        result = run_single_day(run_id, date, args.no_context_risk)
        elapsed = time.time() - t0

        pnl = result.get("total_pnl_dollars", 0)
        ntrades = result.get("total_trades", 0)
        cumulative_pnl += pnl
        total_trades += ntrades

        if pnl > 0:
            winning_days += 1
        elif pnl < 0:
            losing_days += 1
        else:
            flat_days += 1

        symbol = "+" if pnl > 0 else ("-" if pnl < 0 else "=")
        print(f"{symbol} {ntrades}T ${pnl:+.2f} (cum: ${cumulative_pnl:+.2f}) [{elapsed:.1f}s]")

        results.append(result)

        # Save intermediate
        with open(output_path, "w") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "config_label": label,
                "ticker": TICKER,
                "days_completed": len(results),
                "days_total": len(days),
                "summary": {
                    "total_trades": total_trades,
                    "cumulative_pnl_dollars": round(cumulative_pnl, 2),
                    "winning_days": winning_days,
                    "losing_days": losing_days,
                    "flat_days": flat_days,
                    "win_day_rate": round(winning_days / max(1, winning_days + losing_days) * 100, 1),
                },
                "daily": results,
            }, f, indent=2, default=str)

    # Final summary
    print(f"\n{'='*60}")
    print(f"AUDIT COMPLETE: {label}")
    print(f"Days: {len(results)} | Trades: {total_trades}")
    print(f"PnL: ${cumulative_pnl:+.2f}")
    print(f"Win/Loss/Flat: {winning_days}/{losing_days}/{flat_days}")
    print(f"Win day rate: {winning_days / max(1, winning_days + losing_days) * 100:.1f}%")
    print(f"Saved to: {output_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
