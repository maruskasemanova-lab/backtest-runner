#!/usr/bin/env python3
"""
Audit one ticker over a date range using day-by-day backtests.

Designed for quick edge checks:
- skips weekends
- optional skip Fridays
- treats missing-data days as skipped (commonly holidays)
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

# Make project root imports available when running as `python scripts/...`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_strategy_test import StrategyTester


@dataclass
class DailyAuditResult:
    date: str
    status: str
    total_bars: int = 0
    total_trades: int = 0
    total_pnl_dollars: float = 0.0
    total_pnl_pct: float = 0.0
    errors: List[str] = field(default_factory=list)
    regime: str = ""
    strategy: str = ""


def _iter_dates(start_date: str, end_date: str, skip_friday: bool) -> List[str]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    out: List[str] = []
    cur = start
    while cur <= end:
        weekday = cur.weekday()
        if weekday < 5 and not (skip_friday and weekday == 4):
            out.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return out


def _is_missing_data_error(errors: List[str]) -> bool:
    text = " | ".join(errors).lower()
    markers = [
        "no data files found",
        "no data available",
        "no usable data files",
        "start failed",
    ]
    return any(m in text for m in markers)


async def run_audit(args: argparse.Namespace) -> Dict[str, Any]:
    tester = StrategyTester(api_url=args.api_url, strategy_api_url=args.strategy_api_url)
    dates = _iter_dates(args.start_date, args.end_date, skip_friday=args.skip_friday)

    start_overrides = {
        "allow_mock_data": False,
        "l2_only": bool(args.l2_only),
        "l2_confirm_enabled": bool(args.l2_confirm_enabled),
        "l2_min_delta": float(args.l2_min_delta),
        "l2_min_imbalance": float(args.l2_min_imbalance),
        "l2_min_iceberg_bias": float(args.l2_min_iceberg_bias),
        "l2_lookback_bars": int(args.l2_lookback_bars),
        "l2_min_participation_ratio": float(args.l2_min_participation_ratio),
        "l2_min_directional_consistency": float(args.l2_min_directional_consistency),
        "l2_min_signed_aggression": float(args.l2_min_signed_aggression),
    }

    daily: List[DailyAuditResult] = []
    skipped_missing = 0

    for date in dates:
        run_id = f"audit-{args.ticker}-{date}-{int(datetime.now().timestamp())}"
        report = await tester.run_test(
            ticker=args.ticker,
            date=date,
            run_id=run_id,
            verbose=False,
            cleanup_run=True,
            start_overrides=start_overrides,
            execution_mode=args.execution_mode,
            play_speed=args.play_speed,
            poll_interval_sec=float(args.poll_interval_sec),
            play_timeout_sec=float(args.play_timeout_sec),
        )

        status = "ok"
        if report.errors:
            if report.total_bars == 0 and _is_missing_data_error(report.errors):
                status = "skipped_missing_data"
                skipped_missing += 1
            else:
                status = "error"

        daily.append(
            DailyAuditResult(
                date=date,
                status=status,
                total_bars=report.total_bars,
                total_trades=report.total_trades,
                total_pnl_dollars=report.total_pnl_dollars,
                total_pnl_pct=report.total_pnl_pct,
                errors=report.errors,
                regime=report.regime_detected or "",
                strategy=report.strategy_selected or "",
            )
        )

    tested = [d for d in daily if d.status == "ok"]
    errored = [d for d in daily if d.status == "error"]
    total_trades = sum(d.total_trades for d in tested)
    total_pnl_dollars = sum(d.total_pnl_dollars for d in tested)
    total_pnl_pct = sum(d.total_pnl_pct for d in tested)
    winning_days = sum(1 for d in tested if d.total_pnl_dollars > 0)
    losing_days = sum(1 for d in tested if d.total_pnl_dollars < 0)
    flat_days = sum(1 for d in tested if d.total_pnl_dollars == 0)

    summary = {
        "ticker": args.ticker.upper(),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "skip_friday": bool(args.skip_friday),
        "candidate_days": len(dates),
        "tested_days": len(tested),
        "skipped_missing_data_days": skipped_missing,
        "error_days": len(errored),
        "total_trades": total_trades,
        "total_pnl_dollars_sum": round(total_pnl_dollars, 4),
        "total_pnl_pct_sum": round(total_pnl_pct, 4),
        "avg_pnl_dollars_per_tested_day": round((total_pnl_dollars / len(tested)) if tested else 0.0, 4),
        "winning_days": winning_days,
        "losing_days": losing_days,
        "flat_days": flat_days,
        "win_day_rate_pct": round((winning_days / len(tested) * 100.0) if tested else 0.0, 2),
        "l2_config": start_overrides,
        "execution_mode": args.execution_mode,
        "play_speed": args.play_speed,
        "poll_interval_sec": float(args.poll_interval_sec),
        "play_timeout_sec": float(args.play_timeout_sec),
    }

    return {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "daily": [asdict(d) for d in daily],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit one ticker across a date range.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--api-url", default="http://localhost:8002")
    parser.add_argument("--strategy-api-url", default="http://localhost:8001")
    parser.add_argument("--skip-friday", action="store_true")
    parser.add_argument(
        "--execution-mode",
        choices=["step", "play"],
        default="play",
        help="Bar execution method. 'play' is much faster for range audits.",
    )
    parser.add_argument(
        "--play-speed",
        default="max",
        help="Value passed to /play endpoint when execution-mode=play.",
    )
    parser.add_argument(
        "--poll-interval-sec",
        type=float,
        default=0.25,
        help="State polling interval in seconds when execution-mode=play.",
    )
    parser.add_argument(
        "--play-timeout-sec",
        type=float,
        default=300.0,
        help="Per-day timeout in seconds when execution-mode=play.",
    )

    parser.add_argument("--l2-only", action="store_true")
    parser.add_argument("--l2-confirm-enabled", action="store_true")
    parser.add_argument("--l2-min-delta", type=float, default=0.0)
    parser.add_argument("--l2-min-imbalance", type=float, default=0.0)
    parser.add_argument("--l2-min-iceberg-bias", type=float, default=0.0)
    parser.add_argument("--l2-lookback-bars", type=int, default=3)
    parser.add_argument("--l2-min-participation-ratio", type=float, default=0.0)
    parser.add_argument("--l2-min-directional-consistency", type=float, default=0.0)
    parser.add_argument("--l2-min-signed-aggression", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = asyncio.run(run_audit(args))
    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Audit written to {args.output}")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
