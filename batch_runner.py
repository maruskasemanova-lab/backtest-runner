#!/usr/bin/env python3
"""
Batch Backtest Runner - Runs backtests over a date range and aggregates results.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field

# Reuse classes from single runner
from run_strategy_test import StrategyTester, BacktestReport


@dataclass
class BatchReport:
    """Aggregated report for multiple runs."""

    ticker: str
    start_date: str
    end_date: str
    run_timestamp: str

    total_days: int = 0
    param_regime_detection_minutes: int = 15

    # Aggregated Stats
    total_trades: int = 0
    total_pnl_dollars: float = 0.0
    total_costs: float = 0.0

    winning_trades: int = 0
    losing_trades: int = 0

    # Per-day results
    daily_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def avg_pnl_per_day(self) -> float:
        if self.total_days == 0:
            return 0.0
        return self.total_pnl_dollars / self.total_days


class BatchRunner:
    def __init__(
        self,
        api_url: str = "http://localhost:8002",
        strategy_url: str = "http://localhost:8001",
    ):
        self.tester = StrategyTester(api_url=api_url, strategy_api_url=strategy_url)

    async def run_batch(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        output_file: Optional[str] = None,
    ) -> BatchReport:

        # 1. Generate dates
        dates = self._generate_dates(start_date, end_date)
        print(
            f"🚀 Starting batch run for {ticker} over {len(dates)} days ({dates[0]} to {dates[-1]})"
        )

        batch_report = BatchReport(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            run_timestamp=datetime.now().isoformat(),
        )

        # 2. Run for each date
        for i, date in enumerate(dates):
            print(f"\n[{i+1}/{len(dates)}] Running for {date}...")

            try:
                run_id = f"batch-{ticker}-{date}-{int(datetime.now().timestamp())}"
                report = await self.tester.run_test(
                    ticker=ticker,
                    date=date,
                    run_id=run_id,
                    verbose=False,  # Keep individual runs quiet
                )

                # Add to aggregate
                batch_report.total_days += 1
                batch_report.total_trades += report.total_trades
                batch_report.winning_trades += report.winning_trades
                batch_report.losing_trades += report.losing_trades
                batch_report.total_pnl_dollars += report.total_pnl_dollars
                batch_report.total_costs += report.total_costs

                # Store daily result summary
                batch_report.daily_results.append(
                    {
                        "date": date,
                        "regime": report.regime_detected,
                        "strategy": report.strategy_selected,
                        "trades": report.total_trades,
                        "pnl": report.total_pnl_dollars,
                        "win_rate": report.win_rate,
                    }
                )

                # Print daily summary
                pnl_icon = "🟢" if report.total_pnl_dollars >= 0 else "🔴"
                print(
                    f"   ✅ Finished. Regime: {report.regime_detected or 'None'}. Trades: {report.total_trades}. PnL: {pnl_icon} ${report.total_pnl_dollars:.2f}"
                )

            except Exception as e:
                print(f"   ❌ Failed: {e}")
                batch_report.errors.append(f"{date}: {str(e)}")

        # 3. Print Final Report
        self.print_batch_report(batch_report)

        # 4. Save
        if output_file:
            self.save_report(batch_report, output_file)

        return batch_report

    def _generate_dates(self, start_str: str, end_str: str) -> List[str]:
        """Generate weekdays between start and end date (inclusive)."""
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")

        dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:  # 0-4 is Mon-Fri
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return dates

    def print_batch_report(self, report: BatchReport):
        print("\n" + "=" * 60)
        print("📊 BATCH BACKTEST SUMMARY")
        print("=" * 60)
        print(f"Ticker: {report.ticker}")
        print(
            f"Period: {report.start_date} to {report.end_date} ({report.total_days} days)"
        )
        print("-" * 40)

        print(f"Total Trades: {report.total_trades}")
        print(f"Win Rate:     {report.win_rate:.1f}%")

        pnl_color = "🟢" if report.total_pnl_dollars >= 0 else "🔴"
        print(f"Total PnL:    {pnl_color} ${report.total_pnl_dollars:.2f}")
        print(f"Total Costs:  ${report.total_costs:.2f}")
        print(f"Avg PnL/Day:  ${report.avg_pnl_per_day:.2f}")

        print("\nDetails per Day:")
        print(f"{'Date':<12} | {'Regime':<10} | {'Trades':<6} | {'PnL':<10}")
        print("-" * 50)

        for day in report.daily_results:
            pnl_str = f"${day['pnl']:.2f}"
            print(
                f"{day['date']:<12} | {str(day['regime'])[:10]:<10} | {day['trades']:<6} | {pnl_str:<10}"
            )

        print("=" * 60)

    def save_report(self, report: BatchReport, filepath: str):
        with open(filepath, "w") as f:
            json.dump(asdict(report), f, indent=2, default=str)
        print(f"\n💾 Batch report saved to: {filepath}")


async def main():
    parser = argparse.ArgumentParser(description="Run batch strategy backtest")
    parser.add_argument(
        "--ticker", "-t", required=True, help="Ticker symbol (e.g., TSLA)"
    )
    parser.add_argument(
        "--start-date", "-s", required=True, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument("--end-date", "-e", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", "-o", help="Output JSON file path")

    args = parser.parse_args()

    runner = BatchRunner()
    await runner.run_batch(
        ticker=args.ticker,
        start_date=args.start_date,
        end_date=args.end_date,
        output_file=args.output,
    )


if __name__ == "__main__":
    asyncio.run(main())
