#!/usr/bin/env python3
"""
Walk-Forward Backtest Runner with Regime Detection and Performance Tracking.

Runs backtests across multiple days and tickers, tracking performance
per regime and selecting best strategies adaptively.
"""
import asyncio
import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

from run_strategy_test import StrategyTester, BacktestReport
from performance_tracker import PerformanceTracker, TradeRecord
from available_data import get_discovery


@dataclass
class WalkForwardConfig:
    """Configuration for walk-forward backtest."""
    tickers: List[str]
    start_date: str
    end_date: str
    api_url: str = "http://localhost:8002"
    strategy_api_url: str = "http://localhost:8001"
    output_dir: str = "walk_forward_results"
    strategy_selection_mode: str = "adaptive_top_n"
    max_active_strategies: int = 3
    parallel_all_strategies: bool = False
    verbose: bool = True


@dataclass
class DailyResult:
    """Result for a single day."""
    date: str
    ticker: str
    regime: Optional[str]
    strategy: Optional[str]
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl_pct: float
    total_pnl_dollars: float
    total_costs: float
    trades: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class WalkForwardRunner:
    """
    Walk-forward backtest runner with regime-aware strategy selection.
    """
    
    def __init__(self, config: WalkForwardConfig):
        self.config = config
        self.tester = StrategyTester(
            api_url=config.api_url,
            strategy_api_url=config.strategy_api_url
        )
        self.tracker = PerformanceTracker()
        self.results: List[DailyResult] = []
        
        # Ensure output directory exists
        self.output_path = Path(config.output_dir)
        self.output_path.mkdir(parents=True, exist_ok=True)
    
    def _generate_dates(self) -> List[str]:
        """Generate trading dates between start and end."""
        start = datetime.strptime(self.config.start_date, "%Y-%m-%d")
        end = datetime.strptime(self.config.end_date, "%Y-%m-%d")
        
        dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        
        return dates
    
    def _get_available_tickers(self) -> List[str]:
        """Get list of tickers with available data."""
        discovery = get_discovery()
        return discovery.get_tickers()

    def _build_start_overrides(self) -> Dict[str, Any]:
        """Build /api/run/start overrides used for walk-forward runs."""
        mode = str(self.config.strategy_selection_mode or "adaptive_top_n").strip().lower()
        if mode not in {"adaptive_top_n", "all_enabled"}:
            mode = "adaptive_top_n"
        max_active = max(1, min(20, int(self.config.max_active_strategies or 3)))

        if self.config.parallel_all_strategies:
            mode = "all_enabled"
            max_active = 20

        return {
            "strategy_selection_mode": mode,
            "max_active_strategies": max_active,
        }
    
    async def run_single_day(
        self,
        ticker: str,
        date: str
    ) -> DailyResult:
        """Run backtest for a single day."""
        run_id = f"wf-{ticker}-{date}-{int(datetime.now().timestamp())}"
        
        if self.config.verbose:
            print(f"\n📅 Running {ticker} on {date}...")
        
        try:
            report = await self.tester.run_test(
                ticker=ticker,
                date=date,
                run_id=run_id,
                start_overrides=self._build_start_overrides(),
                verbose=False  # Keep individual runs quiet
            )
            
            # Create daily result
            result = DailyResult(
                date=date,
                ticker=ticker,
                regime=report.regime_detected,
                strategy=report.strategy_selected,
                total_trades=report.total_trades,
                winning_trades=report.winning_trades,
                losing_trades=report.losing_trades,
                total_pnl_pct=report.total_pnl_pct,
                total_pnl_dollars=report.total_pnl_dollars,
                total_costs=report.total_costs,
                trades=[self._trade_to_dict(t) for t in report.trades],
                errors=report.errors
            )
            
            # Record trades in performance tracker
            for trade in report.trades:
                flow_snapshot = trade.flow_snapshot if isinstance(trade.flow_snapshot, dict) else {}
                signal_metadata = trade.signal_metadata if isinstance(trade.signal_metadata, dict) else {}
                order_flow = signal_metadata.get("order_flow") if isinstance(signal_metadata, dict) else {}
                if not isinstance(order_flow, dict):
                    order_flow = {}
                book_pressure_avg = flow_snapshot.get("book_pressure_avg", order_flow.get("book_pressure_avg"))
                book_pressure_trend = flow_snapshot.get("book_pressure_trend", order_flow.get("book_pressure_trend"))
                signed_aggression = flow_snapshot.get("signed_aggression", order_flow.get("signed_aggression"))

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
                    book_pressure_confirmed=flow_snapshot.get("l2_confirmation_passed"),
                    book_pressure_avg=book_pressure_avg,
                    book_pressure_trend=book_pressure_trend,
                    signed_aggression=signed_aggression,
                )
            
            if self.config.verbose:
                icon = "🟢" if result.total_pnl_dollars >= 0 else "🔴"
                print(f"   {icon} Regime: {result.regime or 'None':10} | "
                      f"Strategy: {result.strategy or 'None':15} | "
                      f"Trades: {result.total_trades:2} | "
                      f"PnL: ${result.total_pnl_dollars:+.2f}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            if self.config.verbose:
                print(f"   ❌ Error: {error_msg}")
            
            return DailyResult(
                date=date,
                ticker=ticker,
                regime=None,
                strategy=None,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl_pct=0,
                total_pnl_dollars=0,
                total_costs=0,
                errors=[error_msg]
            )
    
    def _trade_to_dict(self, trade) -> Dict[str, Any]:
        """Convert TradeResult to dictionary."""
        return {
            'id': trade.id,
            'strategy': trade.strategy,
            'side': trade.side,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'entry_time': trade.entry_time,
            'exit_time': trade.exit_time,
            'pnl_pct': trade.pnl_pct,
            'pnl_dollars': trade.pnl_dollars,
            'exit_reason': trade.exit_reason,
            'gross_pnl_pct': trade.gross_pnl_pct,
            'total_costs': trade.total_costs,
            'signal_metadata': trade.signal_metadata,
            'flow_snapshot': trade.flow_snapshot,
        }
    
    async def run(self) -> Dict[str, Any]:
        """Run walk-forward backtest."""
        print("=" * 80)
        print("🚀 WALK-FORWARD BACKTEST STARTED")
        print("=" * 80)
        print(f"Tickers: {', '.join(self.config.tickers)}")
        print(f"Date Range: {self.config.start_date} to {self.config.end_date}")
        start_overrides = self._build_start_overrides()
        print(
            "Selection Mode: "
            f"{start_overrides['strategy_selection_mode']} "
            f"(max_active_strategies={start_overrides['max_active_strategies']})"
        )
        print(f"Output: {self.output_path}")
        print("=" * 80)
        
        # Generate dates
        dates = self._generate_dates()
        print(f"\n📊 Total trading days: {len(dates)}")
        
        # Run for each ticker and date
        total_runs = len(self.config.tickers) * len(dates)
        run_count = 0
        
        for ticker in self.config.tickers:
            print(f"\n{'='*80}")
            print(f"📈 TICKER: {ticker}")
            print(f"{'='*80}")
            
            for date in dates:
                run_count += 1
                if self.config.verbose:
                    print(f"\n[{run_count}/{total_runs}] ", end="")
                
                result = await self.run_single_day(ticker, date)
                self.results.append(result)
        
        # Generate and save report
        report = self._generate_report()
        self._save_report(report)
        
        # Print summary
        self._print_summary(report)
        
        return report
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive report."""
        # Aggregate results
        total_trades = sum(r.total_trades for r in self.results)
        total_pnl = sum(r.total_pnl_dollars for r in self.results)
        total_costs = sum(r.total_costs for r in self.results)
        winning_days = sum(1 for r in self.results if r.total_pnl_dollars > 0)
        losing_days = sum(1 for r in self.results if r.total_pnl_dollars < 0)
        
        # Results by ticker
        ticker_results = {}
        for r in self.results:
            if r.ticker not in ticker_results:
                ticker_results[r.ticker] = {
                    'trades': 0,
                    'pnl': 0,
                    'costs': 0,
                    'days': 0
                }
            ticker_results[r.ticker]['trades'] += r.total_trades
            ticker_results[r.ticker]['pnl'] += r.total_pnl_dollars
            ticker_results[r.ticker]['costs'] += r.total_costs
            ticker_results[r.ticker]['days'] += 1
        
        # Results by regime
        regime_results = {}
        for r in self.results:
            regime = r.regime or "UNKNOWN"
            if regime not in regime_results:
                regime_results[regime] = {
                    'trades': 0,
                    'pnl': 0,
                    'days': 0
                }
            regime_results[regime]['trades'] += r.total_trades
            regime_results[regime]['pnl'] += r.total_pnl_dollars
            regime_results[regime]['days'] += 1
        
        # Results by strategy
        strategy_results = {}
        for r in self.results:
            strategy = r.strategy or "NONE"
            if strategy not in strategy_results:
                strategy_results[strategy] = {
                    'trades': 0,
                    'pnl': 0,
                    'days': 0
                }
            strategy_results[strategy]['trades'] += r.total_trades
            strategy_results[strategy]['pnl'] += r.total_pnl_dollars
            strategy_results[strategy]['days'] += 1
        
        report = {
            'run_timestamp': datetime.now().isoformat(),
            'config': {
                'tickers': self.config.tickers,
                'start_date': self.config.start_date,
                'end_date': self.config.end_date,
                'total_days': len(self._generate_dates()),
                'strategy_selection_mode': self._build_start_overrides()["strategy_selection_mode"],
                'max_active_strategies': self._build_start_overrides()["max_active_strategies"],
                'parallel_all_strategies': bool(self.config.parallel_all_strategies),
            },
            'summary': {
                'total_trades': total_trades,
                'total_pnl_dollars': round(total_pnl, 2),
                'total_costs': round(total_costs, 2),
                'net_pnl': round(total_pnl, 2),
                'winning_days': winning_days,
                'losing_days': losing_days,
                'total_days': len(self.results),
                'avg_trades_per_day': round(total_trades / len(self.results), 2) if self.results else 0,
                'avg_pnl_per_day': round(total_pnl / len(self.results), 2) if self.results else 0
            },
            'by_ticker': ticker_results,
            'by_regime': regime_results,
            'by_strategy': strategy_results,
            'strategy_rankings': self.tracker.get_strategy_rankings(),
            'regime_summaries': {
                regime: self.tracker.get_regime_summary(regime)
                for regime in ['TRENDING', 'CHOPPY', 'MIXED']
            },
            'hourly_summary': self.tracker.get_hourly_summary(),
            'weekday_summary': self.tracker.get_weekday_summary(),
            'overall_stats': self.tracker.get_overall_stats(),
            'daily_results': [
                {
                    'date': r.date,
                    'ticker': r.ticker,
                    'regime': r.regime,
                    'strategy': r.strategy,
                    'trades': r.total_trades,
                    'pnl_dollars': round(r.total_pnl_dollars, 2),
                    'pnl_pct': round(r.total_pnl_pct, 2),
                    'costs': round(r.total_costs, 2)
                }
                for r in self.results
            ]
        }
        
        return report
    
    def _save_report(self, report: Dict[str, Any]):
        """Save report to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON report
        json_path = self.output_path / f"walk_forward_report_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 JSON report saved: {json_path}")
        
        # CSV trades
        csv_path = self.output_path / f"trades_{timestamp}.csv"
        self.tracker.export_csv(str(csv_path))
        print(f"💾 CSV trades saved: {csv_path}")
        
        # Performance data
        perf_path = self.output_path / f"performance_data_{timestamp}.json"
        self.tracker.save(str(perf_path))
        print(f"💾 Performance data saved: {perf_path}")
    
    def _print_summary(self, report: Dict[str, Any]):
        """Print formatted summary."""
        s = report['summary']
        
        print("\n" + "=" * 80)
        print("📊 WALK-FORWARD BACKTEST SUMMARY")
        print("=" * 80)
        
        print(f"\nOverall Performance:")
        print(f"  Total Trades:     {s['total_trades']}")
        print(f"  Total Days:       {s['total_days']}")
        print(f"  Winning Days:     {s['winning_days']}")
        print(f"  Losing Days:      {s['losing_days']}")
        print(f"  Avg Trades/Day:   {s['avg_trades_per_day']:.2f}")
        
        pnl_color = "🟢" if s['total_pnl_dollars'] >= 0 else "🔴"
        print(f"\nPnL:")
        print(f"  Gross PnL:        {pnl_color} ${s['total_pnl_dollars']:+.2f}")
        print(f"  Total Costs:      ${s['total_costs']:.2f}")
        print(f"  Net PnL:          ${s['net_pnl']:+.2f}")
        print(f"  Avg PnL/Day:      ${s['avg_pnl_per_day']:+.2f}")
        
        print(f"\nBy Ticker:")
        for ticker, data in report['by_ticker'].items():
            icon = "🟢" if data['pnl'] >= 0 else "🔴"
            print(f"  {ticker:6} | Trades: {data['trades']:3} | PnL: {icon} ${data['pnl']:+.2f}")
        
        print(f"\nBy Regime:")
        for regime, data in report['by_regime'].items():
            icon = "🟢" if data['pnl'] >= 0 else "🔴"
            print(f"  {regime:10} | Days: {data['days']:3} | Trades: {data['trades']:3} | PnL: {icon} ${data['pnl']:+.2f}")
        
        print(f"\nBy Strategy:")
        for strategy, data in report['by_strategy'].items():
            icon = "🟢" if data['pnl'] >= 0 else "🔴"
            print(f"  {strategy:15} | Days: {data['days']:3} | Trades: {data['trades']:3} | PnL: {icon} ${data['pnl']:+.2f}")
        
        print(f"\nTop Strategies by Score:")
        rankings = report['strategy_rankings'][:5]
        for i, r in enumerate(rankings, 1):
            pf = r['profit_factor']
            pf_str = f"{pf:.2f}" if isinstance(pf, (int, float)) else str(pf)
            print(f"  {i}. {r['strategy']:15} ({r['regime']:8}) | "
                  f"Score: {r['score']:6.1f} | "
                  f"Win Rate: {r['win_rate']:5.1f}% | "
                  f"PF: {pf_str}")
        
        print("=" * 80)


async def main():
    parser = argparse.ArgumentParser(description="Walk-Forward Backtest Runner")
    parser.add_argument("--tickers", "-t", nargs="+", default=["NVDA"],
                        help="List of tickers to test (default: NVDA)")
    parser.add_argument("--start-date", "-s", default="2026-01-20",
                        help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", "-e", default="2026-01-28",
                        help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", "-o", default="walk_forward_results",
                        help="Output directory")
    parser.add_argument("--api-url", default="http://localhost:8002",
                        help="Backtest runner API URL")
    parser.add_argument("--strategy-url", default="http://localhost:8001",
                        help="Strategy API URL")
    parser.add_argument(
        "--strategy-selection-mode",
        choices=["adaptive_top_n", "all_enabled"],
        default="adaptive_top_n",
        help="Strategy selection mode for each walk-forward run start",
    )
    parser.add_argument(
        "--max-active-strategies",
        type=int,
        default=3,
        help="Maximum active strategies when using adaptive_top_n mode",
    )
    parser.add_argument(
        "--parallel-all-strategies",
        action="store_true",
        help="Force all_enabled mode and activate all eligible strategies in parallel",
    )
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Quiet mode (less output)")
    
    args = parser.parse_args()
    
    config = WalkForwardConfig(
        tickers=args.tickers,
        start_date=args.start_date,
        end_date=args.end_date,
        api_url=args.api_url,
        strategy_api_url=args.strategy_url,
        output_dir=args.output,
        strategy_selection_mode=args.strategy_selection_mode,
        max_active_strategies=args.max_active_strategies,
        parallel_all_strategies=args.parallel_all_strategies,
        verbose=not args.quiet
    )
    
    runner = WalkForwardRunner(config)
    report = await runner.run()
    
    return report


if __name__ == "__main__":
    asyncio.run(main())
