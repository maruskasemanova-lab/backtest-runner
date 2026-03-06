#!/usr/bin/env python3
"""
AOS Walk-Forward Backtest Runner with Ticker-Specific Optimization.

Runs the AOS configuration through walk-forward validation to find edge.
Uses ticker-specific strategies and parameters from aos_config.json.
"""
import asyncio
import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from run_strategy_test import StrategyTester, BacktestReport
from performance_tracker import PerformanceTracker
from src.services.data_discovery import get_discovery

FLOW_PARAM_GRIDS: Dict[str, Dict[str, List[float]]] = {
    "momentum_flow": {
        "min_signed_aggression": [0.06, 0.08, 0.10],
        "min_book_pressure": [0.0, 0.02, 0.05],
        "min_sweep_intensity": [0.05, 0.08, 0.12],
    },
    "absorption_reversal": {
        "min_signed_aggression": [0.06, 0.08, 0.10],
        "min_book_pressure": [0.03, 0.05, 0.08],
        "min_divergence": [0.12, 0.15, 0.20],
    },
    "exhaustion_fade": {
        "min_signed_aggression": [0.02, 0.04, 0.06],
        "min_book_pressure": [0.0, 0.02, 0.05],
        "max_sweep_intensity": [0.6, 0.8, 1.0],
    },
}


@dataclass
class AOSConfig:
    """AOS Configuration loaded from file."""

    tickers: Dict[str, Dict[str, Any]]
    global_settings: Dict[str, Any]
    strategies: Dict[str, List[str]]
    risk_management: Dict[str, Any]


@dataclass
class DailyAOSResult:
    """Result for a single day with AOS rules applied."""

    date: str
    ticker: str
    regime: Optional[str]
    strategy_used: Optional[str]
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    should_trade: bool = True
    skip_reason: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_pct: float = 0.0
    total_pnl_dollars: float = 0.0
    total_costs: float = 0.0
    trades: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class AOSWalkForwardRunner:
    """
    Walk-forward runner with AOS optimization.

    Key features:
    1. Uses ticker-specific strategy/params from aos_config.json
    2. Applies regime and day filters
    3. Tracks performance per configuration
    4. Finds statistical edge
    """

    def __init__(
        self,
        config_path: str = str(REPO_ROOT / "aos_optimization" / "aos_config.json"),
        api_url: str = "http://localhost:8002",
        strategy_api_url: str = "http://localhost:8001",
        output_dir: str = str(REPO_ROOT / "aos_walk_forward_results"),
        verbose: bool = True,
    ):
        self.config_path = config_path
        self.api_url = api_url
        self.strategy_api_url = strategy_api_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose

        # Load config
        self.aos_config = self._load_config()

        # Initialize
        self.tester = StrategyTester(api_url, strategy_api_url)
        self.tracker = PerformanceTracker()
        self.results: List[DailyAOSResult] = []

        # Statistics
        self.skipped_trades = 0
        self.rule_violations = {"regime_filter": 0, "day_filter": 0, "no_trades": 0}

    def _load_config(self) -> AOSConfig:
        """Load AOS configuration from file."""
        with open(self.config_path, "r") as f:
            data = json.load(f)

        return AOSConfig(
            tickers=data.get("tickers", {}),
            global_settings=data.get("global_settings", {}),
            strategies=data.get("strategies", {}),
            risk_management=data.get("risk_management", {}),
        )

    def _should_trade(
        self, ticker: str, date: str, regime: Optional[str]
    ) -> tuple[bool, str]:
        """Apply AOS rules to determine if we should trade."""
        ticker_config = self.aos_config.tickers.get(ticker, {})
        global_settings = self.aos_config.global_settings

        # Parse date
        dt = datetime.strptime(date, "%Y-%m-%d")
        day_name = dt.strftime("%A")

        # 1. Global day filter
        if day_name in global_settings.get("avoid_days", []):
            return False, f"Global avoid day: {day_name}"

        # 2. Ticker-specific day filter
        if day_name in ticker_config.get("avoid_days", []):
            return False, f"Ticker avoid day: {day_name}"

        # 3. Regime filter (if we know the regime)
        if regime:
            regime_filter = ticker_config.get("regime_filter", [])
            if regime_filter and regime not in regime_filter:
                return False, f"Regime {regime} not in {regime_filter}"

        return True, "OK"

    def _get_strategy_for_ticker(self, ticker: str) -> tuple[str, Dict[str, Any]]:
        """Get the strategy and params for a ticker."""
        ticker_config = self.aos_config.tickers.get(ticker, {})

        strategy = ticker_config.get("strategy", "mean_reversion")
        params = ticker_config.get("params", {})

        return strategy, params

    def _generate_dates(self, start_date: str, end_date: str) -> List[str]:
        """Generate trading dates between start and end."""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:  # Monday-Friday
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        return dates

    async def run_single_day(self, ticker: str, date: str) -> DailyAOSResult:
        """Run backtest for a single day with AOS rules."""
        run_id = f"aos-{ticker}-{date}-{int(datetime.now().timestamp())}"

        # Get strategy for this ticker
        strategy, params = self._get_strategy_for_ticker(ticker)

        result = DailyAOSResult(
            date=date,
            ticker=ticker,
            regime=None,
            strategy_used=strategy,
            strategy_params=params,
        )

        # Pre-check: Day filter (before we even run)
        should_trade, reason = self._should_trade(ticker, date, None)
        if not should_trade:
            result.should_trade = False
            result.skip_reason = reason
            self.skipped_trades += 1
            self.rule_violations["day_filter"] += 1

            if self.verbose:
                print(f"   ⏭️  Skipped: {reason}")
            return result

        try:
            report = await self.tester.run_test(
                ticker=ticker, date=date, run_id=run_id, verbose=False
            )

            # Post-check: Regime filter
            result.regime = report.regime_detected
            should_trade, reason = self._should_trade(
                ticker, date, report.regime_detected
            )

            if not should_trade:
                result.should_trade = False
                result.skip_reason = reason
                self.skipped_trades += 1
                self.rule_violations["regime_filter"] += 1

                if self.verbose:
                    print(f"   ⏭️  Would skip (regime): {reason}")
                # Still record for analysis, but mark as skipped

            # Record results
            result.total_trades = report.total_trades
            result.winning_trades = report.winning_trades
            result.losing_trades = report.losing_trades
            result.total_pnl_pct = report.total_pnl_pct
            result.total_pnl_dollars = report.total_pnl_dollars
            result.total_costs = report.total_costs
            result.trades = [self._trade_to_dict(t) for t in report.trades]
            result.errors = report.errors

            if report.total_trades == 0:
                self.rule_violations["no_trades"] += 1

            # Track only trades that pass AOS rules.
            if result.should_trade:
                for trade in report.trades:
                    flow_snapshot = (
                        trade.flow_snapshot
                        if isinstance(trade.flow_snapshot, dict)
                        else {}
                    )
                    signal_metadata = (
                        trade.signal_metadata
                        if isinstance(trade.signal_metadata, dict)
                        else {}
                    )
                    order_flow = (
                        signal_metadata.get("order_flow")
                        if isinstance(signal_metadata, dict)
                        else {}
                    )
                    if not isinstance(order_flow, dict):
                        order_flow = {}
                    book_pressure_avg = flow_snapshot.get(
                        "book_pressure_avg", order_flow.get("book_pressure_avg")
                    )
                    book_pressure_trend = flow_snapshot.get(
                        "book_pressure_trend", order_flow.get("book_pressure_trend")
                    )
                    signed_aggression = flow_snapshot.get(
                        "signed_aggression", order_flow.get("signed_aggression")
                    )

                    self.tracker.record_trade(
                        strategy=trade.strategy,
                        regime=report.regime_detected or "UNKNOWN",
                        ticker=ticker,
                        date=date,
                        side=trade.side,
                        entry_price=trade.entry_price,
                        exit_price=trade.exit_price,
                        entry_time=trade.entry_time,
                        exit_time=trade.exit_time,
                        pnl_pct=trade.pnl_pct,
                        pnl_dollars=trade.pnl_dollars,
                        gross_pnl_pct=trade.gross_pnl_pct or 0,
                        total_costs=trade.total_costs or 0,
                        exit_reason=trade.exit_reason,
                        flow_strategy=("flow" in (trade.strategy or "").lower()),
                        book_pressure_confirmed=flow_snapshot.get(
                            "l2_confirmation_passed"
                        ),
                        book_pressure_avg=book_pressure_avg,
                        book_pressure_trend=book_pressure_trend,
                        signed_aggression=signed_aggression,
                    )

            if self.verbose:
                icon = "🟢" if result.total_pnl_dollars >= 0 else "🔴"
                skip_icon = "⚠️ " if not result.should_trade else ""
                print(
                    f"   {skip_icon}{icon} {result.regime or 'N/A':8} | "
                    f"{strategy:15} | Trades: {result.total_trades:2} | "
                    f"PnL: ${result.total_pnl_dollars:+.2f}"
                )

            return result

        except Exception as e:
            result.errors.append(str(e))
            if self.verbose:
                print(f"   ❌ Error: {e}")
            return result

    def _trade_to_dict(self, trade) -> Dict[str, Any]:
        """Convert TradeResult to dictionary."""
        return {
            "id": trade.id,
            "strategy": trade.strategy,
            "side": trade.side,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "entry_time": trade.entry_time,
            "exit_time": trade.exit_time,
            "pnl_pct": trade.pnl_pct,
            "pnl_dollars": trade.pnl_dollars,
            "exit_reason": trade.exit_reason,
            "gross_pnl_dollars": getattr(trade, "gross_pnl_dollars", None),
            "position_notional_usd": getattr(trade, "position_notional_usd", None),
            "cost_usd": getattr(trade, "cost_usd", None),
            "cost_pct": getattr(trade, "cost_pct", None),
            "signal_bar_index": getattr(trade, "signal_bar_index", None),
            "entry_bar_index": getattr(trade, "entry_bar_index", None),
            "signal_timestamp": getattr(trade, "signal_timestamp", None),
            "signal_price": getattr(trade, "signal_price", None),
            "take_profit": getattr(trade, "take_profit", None),
            "setup_type": getattr(trade, "setup_type", None),
            "setup_reason": getattr(trade, "setup_reason", None),
            "signal_metadata": trade.signal_metadata,
            "flow_snapshot": trade.flow_snapshot,
            "trade_audit": getattr(trade, "trade_audit", None),
        }

    async def run(
        self, tickers: List[str], start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Run walk-forward backtest with AOS configuration."""
        print("=" * 80)
        print("🤖 AOS WALK-FORWARD BACKTEST")
        print("=" * 80)
        print(f"Config: {self.config_path}")
        print(f"Tickers: {', '.join(tickers)}")
        print(f"Date Range: {start_date} to {end_date}")
        print("=" * 80)

        # Generate dates
        dates = self._generate_dates(start_date, end_date)
        print(f"\n📊 Trading days: {len(dates)}")

        # Show AOS config summary
        print("\n📋 AOS Ticker Configuration:")
        for ticker in tickers:
            config = self.aos_config.tickers.get(ticker, {})
            strategy = config.get("strategy", "default")
            regime_filter = config.get("regime_filter", ["ALL"])
            avoid_days = config.get("avoid_days", [])
            print(
                f"   {ticker:6} → {strategy:15} | Regimes: {regime_filter} | Avoid: {avoid_days or 'None'}"
            )

        # Run tests
        total_runs = len(tickers) * len(dates)
        run_count = 0

        for ticker in tickers:
            print(f"\n{'=' * 60}")
            print(f"📈 {ticker}")
            print(f"{'=' * 60}")

            for date in dates:
                run_count += 1
                if self.verbose:
                    print(f"\n[{run_count}/{total_runs}] {date}: ", end="")

                result = await self.run_single_day(ticker, date)
                self.results.append(result)

        # Generate report
        report = self._generate_report(tickers, start_date, end_date)
        self._save_report(report)
        self._print_summary(report)

        return report

    def _generate_report(
        self, tickers: List[str], start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Generate comprehensive AOS report."""

        # Separate traded vs skipped
        traded_results = [r for r in self.results if r.should_trade]
        skipped_results = [r for r in self.results if not r.should_trade]

        # Aggregate traded results
        total_trades = sum(r.total_trades for r in traded_results)
        total_pnl = sum(r.total_pnl_dollars for r in traded_results)
        total_costs = sum(r.total_costs for r in traded_results)
        winning_days = sum(1 for r in traded_results if r.total_pnl_dollars > 0)
        losing_days = sum(1 for r in traded_results if r.total_pnl_dollars < 0)

        # Would-have-been results (if we traded despite filters)
        skipped_pnl = sum(r.total_pnl_dollars for r in skipped_results)

        # By ticker
        ticker_results = {}
        for r in self.results:
            if r.ticker not in ticker_results:
                ticker_results[r.ticker] = {
                    "trades": 0,
                    "pnl": 0,
                    "costs": 0,
                    "traded_days": 0,
                    "skipped_days": 0,
                    "winning_days": 0,
                    "losing_days": 0,
                }

            if r.should_trade:
                ticker_results[r.ticker]["traded_days"] += 1
                ticker_results[r.ticker]["trades"] += r.total_trades
                ticker_results[r.ticker]["pnl"] += r.total_pnl_dollars
                ticker_results[r.ticker]["costs"] += r.total_costs
                if r.total_pnl_dollars > 0:
                    ticker_results[r.ticker]["winning_days"] += 1
                elif r.total_pnl_dollars < 0:
                    ticker_results[r.ticker]["losing_days"] += 1
            else:
                ticker_results[r.ticker]["skipped_days"] += 1

        # Calculate win rate per ticker
        for ticker in ticker_results:
            td = ticker_results[ticker]
            total_days = td["winning_days"] + td["losing_days"]
            td["win_rate"] = (
                (td["winning_days"] / total_days * 100) if total_days > 0 else 0
            )
            td["avg_pnl_per_day"] = (
                td["pnl"] / td["traded_days"] if td["traded_days"] > 0 else 0
            )

        # By regime
        regime_results = {}
        for r in traded_results:
            regime = r.regime or "UNKNOWN"
            if regime not in regime_results:
                regime_results[regime] = {"trades": 0, "pnl": 0, "days": 0}
            regime_results[regime]["trades"] += r.total_trades
            regime_results[regime]["pnl"] += r.total_pnl_dollars
            regime_results[regime]["days"] += 1

        # By strategy
        strategy_results = {}
        for r in traded_results:
            strategy = r.strategy_used or "NONE"
            if strategy not in strategy_results:
                strategy_results[strategy] = {"trades": 0, "pnl": 0, "days": 0}
            strategy_results[strategy]["trades"] += r.total_trades
            strategy_results[strategy]["pnl"] += r.total_pnl_dollars
            strategy_results[strategy]["days"] += 1

        report = {
            "run_timestamp": datetime.now().isoformat(),
            "config_path": self.config_path,
            "config": {
                "tickers": tickers,
                "start_date": start_date,
                "end_date": end_date,
                "total_days": len(self._generate_dates(start_date, end_date)),
                "flow_param_grids": FLOW_PARAM_GRIDS,
            },
            "summary": {
                "total_trades": total_trades,
                "total_pnl_dollars": round(total_pnl, 2),
                "total_costs": round(total_costs, 2),
                "net_pnl": round(total_pnl, 2),  # Costs already in trades
                "winning_days": winning_days,
                "losing_days": losing_days,
                "traded_days": len(traded_results),
                "skipped_days": len(skipped_results),
                "avg_pnl_per_traded_day": (
                    round(total_pnl / len(traded_results), 2) if traded_results else 0
                ),
                "day_win_rate": (
                    round(winning_days / (winning_days + losing_days) * 100, 1)
                    if (winning_days + losing_days) > 0
                    else 0
                ),
            },
            "filter_analysis": {
                "skipped_trades": self.skipped_trades,
                "skipped_pnl_if_traded": round(skipped_pnl, 2),
                "filter_effectiveness": "POSITIVE" if skipped_pnl < 0 else "NEGATIVE",
                "rule_violations": self.rule_violations,
            },
            "by_ticker": ticker_results,
            "by_regime": regime_results,
            "by_strategy": strategy_results,
            "overall_stats": self.tracker.get_overall_stats(),
            "daily_results": [
                {
                    "date": r.date,
                    "ticker": r.ticker,
                    "regime": r.regime,
                    "strategy": r.strategy_used,
                    "should_trade": r.should_trade,
                    "skip_reason": r.skip_reason,
                    "trades": r.total_trades,
                    "pnl_dollars": round(r.total_pnl_dollars, 2),
                    "pnl_pct": round(r.total_pnl_pct, 2),
                }
                for r in self.results
            ],
        }

        return report

    def _save_report(self, report: Dict[str, Any]):
        """Save report to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON report
        json_path = self.output_dir / f"aos_report_{timestamp}.json"
        with open(json_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 Report saved: {json_path}")

        # CSV trades
        csv_path = self.output_dir / f"aos_trades_{timestamp}.csv"
        self.tracker.export_csv(str(csv_path))
        print(f"💾 Trades CSV: {csv_path}")

    def _print_summary(self, report: Dict[str, Any]):
        """Print formatted summary."""
        s = report["summary"]
        f = report["filter_analysis"]

        print("\n" + "=" * 80)
        print("🤖 AOS BACKTEST SUMMARY")
        print("=" * 80)

        print(f"\nTrading Activity:")
        print(f"  Traded Days:     {s['traded_days']}")
        print(f"  Skipped Days:    {s['skipped_days']} (by AOS rules)")
        print(f"  Total Trades:    {s['total_trades']}")

        pnl_icon = "🟢" if s["total_pnl_dollars"] >= 0 else "🔴"
        print(f"\nPnL Summary:")
        print(f"  {pnl_icon} Total PnL:     ${s['total_pnl_dollars']:+.2f}")
        print(f"  Avg PnL/Day:     ${s['avg_pnl_per_traded_day']:+.2f}")
        print(f"  Day Win Rate:    {s['day_win_rate']:.1f}%")

        print(f"\nFilter Effectiveness:")
        skip_icon = "✅" if f["filter_effectiveness"] == "POSITIVE" else "❌"
        print(f"  {skip_icon} Filters saved: ${-f['skipped_pnl_if_traded']:+.2f}")
        print(
            f"  (If we had traded skipped days, we would have made ${f['skipped_pnl_if_traded']:+.2f})"
        )

        print(f"\nBy Ticker:")
        for ticker, data in sorted(
            report["by_ticker"].items(), key=lambda x: x[1]["pnl"], reverse=True
        ):
            icon = "🟢" if data["pnl"] >= 0 else "🔴"
            print(
                f"  {ticker:6} | {icon} ${data['pnl']:+8.2f} | "
                f"Trades: {data['trades']:3} | "
                f"Win%: {data['win_rate']:5.1f}% | "
                f"Skipped: {data['skipped_days']}"
            )

        print(f"\nBy Regime:")
        for regime, data in report["by_regime"].items():
            icon = "🟢" if data["pnl"] >= 0 else "🔴"
            print(
                f"  {regime:10} | {icon} ${data['pnl']:+8.2f} | Days: {data['days']:3}"
            )

        print(f"\nBy Strategy:")
        for strategy, data in sorted(
            report["by_strategy"].items(), key=lambda x: x[1]["pnl"], reverse=True
        ):
            icon = "🟢" if data["pnl"] >= 0 else "🔴"
            print(
                f"  {strategy:15} | {icon} ${data['pnl']:+8.2f} | Days: {data['days']:3}"
            )

        print("\n" + "=" * 80)

        # Edge Analysis
        print("\n📊 EDGE ANALYSIS")
        print("-" * 40)

        avg_daily = s["avg_pnl_per_traded_day"]
        if avg_daily > 0:
            print(f"✅ POSITIVE EDGE DETECTED")
            print(f"   Expected daily return: ${avg_daily:+.2f}")
            print(f"   Monthly expectancy (20 days): ${avg_daily * 20:+.2f}")
            print(f"   Yearly expectancy (250 days): ${avg_daily * 250:+.2f}")
        else:
            print(f"❌ NO EDGE - System needs optimization")
            print(f"   Current daily loss: ${avg_daily:.2f}")

        print("=" * 80)


async def main():
    parser = argparse.ArgumentParser(description="AOS Walk-Forward Backtest")
    parser.add_argument(
        "--tickers",
        "-t",
        nargs="+",
        default=["NVDA", "TSLA", "AAPL"],
        help="Tickers to test",
    )
    parser.add_argument("--start-date", "-s", default="2026-01-06", help="Start date")
    parser.add_argument("--end-date", "-e", default="2026-02-03", help="End date")
    parser.add_argument(
        "--config",
        "-c",
        default=str(REPO_ROOT / "aos_optimization" / "aos_config.json"),
        help="AOS config file",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(REPO_ROOT / "aos_walk_forward_results"),
        help="Output directory",
    )
    parser.add_argument("--api-url", default="http://localhost:8002")
    parser.add_argument("--strategy-url", default="http://localhost:8001")
    parser.add_argument("--quiet", "-q", action="store_true")

    args = parser.parse_args()

    runner = AOSWalkForwardRunner(
        config_path=args.config,
        api_url=args.api_url,
        strategy_api_url=args.strategy_url,
        output_dir=args.output,
        verbose=not args.quiet,
    )

    report = await runner.run(
        tickers=args.tickers, start_date=args.start_date, end_date=args.end_date
    )

    return report


if __name__ == "__main__":
    asyncio.run(main())
