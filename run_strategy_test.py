#!/usr/bin/env python3
"""
Strategy Tester - Runs a complete backtest and generates a report.

Usage:
    python run_strategy_test.py --ticker TSLA --date 2026-01-27
    python run_strategy_test.py --ticker NVDA --date 2026-01-27 --output report.json
"""
import argparse
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import aiohttp


@dataclass
class TradeResult:
    """Result of a single trade."""
    id: int
    strategy: str
    side: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    size: int
    pnl_pct: float
    pnl_dollars: float
    exit_reason: str
    gross_pnl_pct: Optional[float] = None
    total_costs: Optional[float] = None


@dataclass
class BacktestReport:
    """Complete backtest report."""
    run_id: str
    ticker: str
    date: str
    start_time: str
    end_time: str
    duration_seconds: float
    
    # Summary stats
    total_bars: int
    bars_processed: int
    regime_detected: Optional[str] = None
    strategy_selected: Optional[str] = None
    
    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_pct: float = 0.0
    total_pnl_dollars: float = 0.0
    total_costs: float = 0.0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    
    # Lists
    trades: List[TradeResult] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class StrategyTester:
    """Runs a complete backtest and collects results."""
    
    def __init__(
        self,
        api_url: str = "http://localhost:8002",
        strategy_api_url: str = "http://localhost:8001"
    ):
        self.api_url = api_url
        self.strategy_api_url = strategy_api_url

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _extract_trade_cost(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            for key in ("total", "total_costs", "cost"):
                if key in value:
                    try:
                        return float(value[key])
                    except (TypeError, ValueError):
                        continue
        return 0.0

    @staticmethod
    def _extract_summary_dict(summary_payload: Any) -> Dict[str, Any]:
        if isinstance(summary_payload, dict):
            nested = summary_payload.get("session_summary")
            if isinstance(nested, dict):
                return nested
            return summary_payload
        return {}

    @staticmethod
    def _extract_trades(summary_payload: Any) -> List[Dict[str, Any]]:
        if not isinstance(summary_payload, dict):
            return []

        direct = summary_payload.get("trades")
        if isinstance(direct, list):
            return direct

        nested = summary_payload.get("session_summary")
        if isinstance(nested, dict):
            nested_trades = nested.get("trades")
            if isinstance(nested_trades, list):
                return nested_trades

        return []
    
    async def run_test(
        self,
        ticker: str,
        date: str,
        run_id: Optional[str] = None,
        verbose: bool = False,
        cleanup_run: bool = True,
        start_overrides: Optional[Dict[str, Any]] = None,
    ) -> BacktestReport:
        """Run a complete backtest and return the report."""
        ticker = ticker.upper()
        if run_id is None:
            run_id = f"test-{ticker}-{date}-{int(datetime.now().timestamp())}"
        
        start_time = datetime.now()
        report = BacktestReport(
            run_id=run_id,
            ticker=ticker,
            date=date,
            start_time=start_time.isoformat(),
            end_time="",
            duration_seconds=0,
            total_bars=0,
            bars_processed=0
        )

        run_id_part: Optional[str] = None
        ticker_part: Optional[str] = None
        date_part: Optional[str] = None

        async with aiohttp.ClientSession() as session:
            # 1. Start the backtest
            if verbose:
                print(f"🚀 Starting backtest: {ticker} on {date}")
            
            try:
                start_payload: Dict[str, Any] = {
                    "run_id": run_id,
                    "ticker": ticker,
                    "date": date,
                    "strategy_api_url": self.strategy_api_url,
                }
                if start_overrides:
                    start_payload.update(start_overrides)

                async with session.post(
                    f"{self.api_url}/api/run/start",
                    json=start_payload
                ) as start_resp:
                    if start_resp.status != 200:
                        error_text = await start_resp.text()
                        report.errors.append(f"Start failed: {error_text}")
                        return report
                    
                    start_data = await start_resp.json()
                report.total_bars = start_data.get("total_bars", 0)
                run_key = start_data.get("run_key", f"{run_id}:{ticker}:{date}")
                
                if verbose:
                    print(f"📊 Loaded {report.total_bars} bars")
                
            except Exception as e:
                report.errors.append(f"Start error: {str(e)}")
                return report
            
            # Parse run_key
            parts = run_key.split(":", 2)
            if len(parts) != 3:
                report.errors.append(f"Invalid run_key format: {run_key}")
                return report
            run_id_part, ticker_part, date_part = parts[0], parts[1], parts[2]
            
            # 2. Process all bars
            if verbose:
                print(f"⏳ Processing {report.total_bars} bars...")
            
            bar_count = 0
            last_phase = None
            
            while bar_count < report.total_bars:
                try:
                    async with session.post(
                        f"{self.api_url}/api/run/{run_id_part}/{ticker_part}/{date_part}/step"
                    ) as step_resp:
                        if step_resp.status != 200:
                            error_text = await step_resp.text()
                            report.errors.append(f"Step {bar_count} failed: {error_text}")
                            break
                        
                        step_data = await step_resp.json()
                    
                    if not step_data.get("success"):
                        err = str(step_data.get("error", ""))
                        if step_data.get("phase") == "COMPLETED" or "No more bars" in err:
                            break
                        report.errors.append(f"Step {bar_count} unsuccessful: {step_data}")
                        break
                    
                    bar_count = step_data.get("bar_index", bar_count) + 1
                    phase = step_data.get("phase")
                    response = step_data.get("response", {})
                    
                    # Track regime detection
                    if response.get("regime") and not report.regime_detected:
                        report.regime_detected = response["regime"]
                        if verbose:
                            print(f"🎯 Regime detected: {report.regime_detected}")
                    
                    # Track strategy selection
                    if response.get("strategy") and not report.strategy_selected:
                        report.strategy_selected = response["strategy"]
                        if verbose:
                            print(f"📋 Strategy selected: {report.strategy_selected}")
                    
                    # Track phase changes
                    if phase != last_phase:
                        last_phase = phase
                        if verbose:
                            print(f"📈 Phase: {phase}")
                    
                    # Progress indicator
                    if verbose and bar_count % 100 == 0:
                        pct = bar_count / report.total_bars * 100
                        print(f"   Progress: {bar_count}/{report.total_bars} ({pct:.1f}%)")
                    
                except Exception as e:
                    report.errors.append(f"Step error at bar {bar_count}: {str(e)}")
                    break
            
            report.bars_processed = bar_count
            
            # 3. Get final summary
            if verbose:
                print(f"📄 Getting summary...")
            
            try:
                async with session.get(
                    f"{self.api_url}/api/run/{run_id_part}/{ticker_part}/{date_part}/summary"
                ) as summary_resp:
                    if summary_resp.status == 200:
                        summary_payload = await summary_resp.json()
                        summary = self._extract_summary_dict(summary_payload)
                        trades_data = self._extract_trades(summary_payload)

                        for t in trades_data:
                            trade_cost = self._extract_trade_cost(t.get("total_costs"))
                            if trade_cost == 0.0 and t.get("gross_pnl_pct") is not None and t.get("pnl_pct") is not None:
                                gross = self._coerce_float(t.get("gross_pnl_pct"), 0.0)
                                net = self._coerce_float(t.get("pnl_pct"), 0.0)
                                entry = self._coerce_float(t.get("entry_price"), 0.0)
                                size = self._coerce_float(t.get("size"), 0.0)
                                trade_cost = max(0.0, abs(gross - net) * entry * size / 100.0)
                            trade = TradeResult(
                                id=t.get("id", 0),
                                strategy=t.get("strategy", ""),
                                side=t.get("side", ""),
                                entry_price=t.get("entry_price", 0),
                                exit_price=t.get("exit_price", 0),
                                entry_time=t.get("entry_time", ""),
                                exit_time=t.get("exit_time", ""),
                                size=int(self._coerce_float(t.get("size", 0), 0.0)),
                                pnl_pct=t.get("pnl_pct", 0),
                                pnl_dollars=t.get("pnl_dollars", 0),
                                exit_reason=t.get("exit_reason", ""),
                                gross_pnl_pct=t.get("gross_pnl_pct"),
                                total_costs=trade_cost
                            )
                            report.trades.append(trade)
                        
                        # Calculate stats
                        report.total_trades = len(report.trades)

                        total_pnl_pct_candidates = [
                            summary.get("total_pnl_pct"),
                            summary.get("total_pnl"),
                            summary.get("pnl_pct"),
                        ]
                        report.total_pnl_pct = next(
                            (self._coerce_float(v) for v in total_pnl_pct_candidates if v is not None),
                            sum(t.pnl_pct for t in report.trades),
                        )

                        total_pnl_dollars_candidates = [
                            summary.get("total_pnl_dollars"),
                            summary.get("net_pnl"),
                            summary.get("pnl_dollars"),
                        ]
                        report.total_pnl_dollars = next(
                            (self._coerce_float(v) for v in total_pnl_dollars_candidates if v is not None),
                            sum(t.pnl_dollars for t in report.trades),
                        )

                        report.total_costs = sum(t.total_costs or 0.0 for t in report.trades)
                        if report.total_costs == 0:
                            report.total_costs = self._coerce_float(summary.get("total_costs", 0.0), 0.0)
                        
                        wins = [t for t in report.trades if t.pnl_pct > 0]
                        losses = [t for t in report.trades if t.pnl_pct <= 0]
                        
                        report.winning_trades = len(wins)
                        report.losing_trades = len(losses)
                        report.win_rate = len(wins) / len(report.trades) * 100 if report.trades else 0
                        
                        if wins:
                            report.avg_win_pct = sum(t.pnl_pct for t in wins) / len(wins)
                        if losses:
                            report.avg_loss_pct = sum(t.pnl_pct for t in losses) / len(losses)
                        
                        total_wins = sum(t.pnl_pct for t in wins) if wins else 0
                        total_losses = abs(sum(t.pnl_pct for t in losses)) if losses else 0
                        report.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
                    else:
                        text = await summary_resp.text()
                        report.errors.append(f"Summary HTTP {summary_resp.status}: {text}")
                    
            except Exception as e:
                report.errors.append(f"Summary error: {str(e)}")
            
            # 4. Get decisions
            try:
                async with session.get(
                    f"{self.api_url}/api/run/{run_id_part}/{ticker_part}/{date_part}/markers"
                ) as markers_resp:
                    if markers_resp.status == 200:
                        markers = await markers_resp.json()
                        # Handle both list and dict responses
                        if isinstance(markers, list):
                            report.decisions = markers
                        elif isinstance(markers, dict):
                            marker_list = markers.get("markers", [])
                            report.decisions = marker_list if isinstance(marker_list, list) else []
                        else:
                            report.decisions = []
                    else:
                        text = await markers_resp.text()
                        report.errors.append(f"Markers HTTP {markers_resp.status}: {text}")
                    
            except Exception as e:
                report.errors.append(f"Markers error: {str(e)}")

            # 5. Cleanup run state to prevent memory leaks between batch runs.
            if cleanup_run and run_id_part and ticker_part and date_part:
                try:
                    async with session.delete(
                        f"{self.api_url}/api/run/{run_id_part}/{ticker_part}/{date_part}"
                    ):
                        pass
                except Exception as e:
                    report.errors.append(f"Cleanup warning: {str(e)}")
        
        # Finalize report
        end_time = datetime.now()
        report.end_time = end_time.isoformat()
        report.duration_seconds = (end_time - start_time).total_seconds()
        
        return report
    
    def print_report(self, report: BacktestReport):
        """Print a formatted report to console."""
        print("\n" + "=" * 60)
        print("📊 BACKTEST REPORT")
        print("=" * 60)
        
        print(f"\n🏷️  Run: {report.run_id}")
        print(f"📈 Ticker: {report.ticker}")
        print(f"📅 Date: {report.date}")
        print(f"⏱️  Duration: {report.duration_seconds:.1f}s")
        
        print(f"\n📊 Bars: {report.bars_processed}/{report.total_bars}")
        print(f"🎯 Regime: {report.regime_detected or 'Not detected'}")
        print(f"📋 Strategy: {report.strategy_selected or 'None selected'}")
        
        print("\n" + "-" * 40)
        print("💰 TRADING RESULTS")
        print("-" * 40)
        
        print(f"Total Trades: {report.total_trades}")
        print(f"Winning: {report.winning_trades} | Losing: {report.losing_trades}")
        print(f"Win Rate: {report.win_rate:.1f}%")
        
        pnl_color = "🟢" if report.total_pnl_pct >= 0 else "🔴"
        print(f"\n{pnl_color} Total PnL: {report.total_pnl_pct:+.2f}% (${report.total_pnl_dollars:+.2f})")
        print(f"💸 Total Costs: ${report.total_costs:.2f}")
        
        if report.avg_win_pct:
            print(f"\n📈 Avg Win: +{report.avg_win_pct:.2f}%")
        if report.avg_loss_pct:
            print(f"📉 Avg Loss: {report.avg_loss_pct:.2f}%")
        print(f"⚖️  Profit Factor: {report.profit_factor:.2f}")
        
        if report.trades:
            print("\n" + "-" * 40)
            print("📝 TRADES")
            print("-" * 40)
            
            for t in report.trades:
                pnl_icon = "🟢" if t.pnl_pct > 0 else "🔴"
                print(f"\n  {pnl_icon} Trade #{t.id} ({t.strategy})")
                print(f"     {t.side.upper()} @ ${t.entry_price:.2f} → ${t.exit_price:.2f}")
                print(f"     PnL: {t.pnl_pct:+.2f}% | Reason: {t.exit_reason}")
                if t.total_costs:
                    print(f"     Costs: ${t.total_costs:.2f}")
        
        if report.errors:
            print("\n" + "-" * 40)
            print("⚠️  ERRORS")
            print("-" * 40)
            for err in report.errors:
                print(f"  ❌ {err}")
        
        print("\n" + "=" * 60)
    
    def save_report(self, report: BacktestReport, filepath: str):
        """Save report to JSON file."""
        # Convert to dict
        data = asdict(report)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"💾 Report saved to: {filepath}")


async def main():
    parser = argparse.ArgumentParser(description="Run strategy backtest and generate report")
    parser.add_argument("--ticker", "-t", required=True, help="Ticker symbol (e.g., TSLA)")
    parser.add_argument("--date", "-d", required=True, help="Trading date (YYYY-MM-DD)")
    parser.add_argument("--run-id", "-r", help="Custom run ID")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--api-url", default="http://localhost:8002", help="Backtest API URL")
    parser.add_argument("--strategy-url", default="http://localhost:8001", help="Strategy API URL")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode (less output)")
    
    args = parser.parse_args()
    
    tester = StrategyTester(
        api_url=args.api_url,
        strategy_api_url=args.strategy_url
    )
    
    report = await tester.run_test(
        ticker=args.ticker,
        date=args.date,
        run_id=args.run_id,
        verbose=not args.quiet
    )
    
    tester.print_report(report)
    
    if args.output:
        tester.save_report(report, args.output)


if __name__ == "__main__":
    asyncio.run(main())
