import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.day_trading_manager import BarData, DayTradingManager, SessionPhase, TradingCosts  # noqa: E402
from src.strategies.base_strategy import Signal, SignalType  # noqa: E402


class ExecutionRealismTests(unittest.TestCase):
    def _build_manager_session(self):
        manager = DayTradingManager(
            regime_detection_minutes=0,
            max_trades_per_day=10,
            trade_cooldown_bars=0,
        )
        session = manager.get_or_create_session("realism", "NVDA", "2026-02-03", 0)
        session.phase = SessionPhase.TRADING
        session.selected_strategy = None
        session.pending_signal = None
        return manager, session

    def _open_long_position(self, manager: DayTradingManager, session, ts: datetime, bar_volume: float = 5000.0):
        signal = Signal(
            strategy_name="MomentumFlow",
            signal_type=SignalType.BUY,
            price=100.0,
            timestamp=ts,
            confidence=90.0,
            stop_loss=99.0,
            take_profit=130.0,
            trailing_stop=False,
            reasoning="unit-test",
        )
        pos = manager._open_position(
            session=session,
            signal=signal,
            entry_price=100.0,
            entry_time=ts,
            signal_bar_index=0,
            entry_bar_index=0,
            entry_bar_volume=bar_volume,
        )
        self.assertIsNotNone(session.active_position)
        return pos

    def test_cost_model_increases_with_liquidity_stress(self):
        costs = TradingCosts()
        liquid = costs.calculate_costs(
            entry_price=100.0,
            exit_price=101.0,
            shares=100.0,
            side="long",
            avg_bar_volume=200_000.0,
        )
        stressed = costs.calculate_costs(
            entry_price=100.0,
            exit_price=101.0,
            shares=2_000.0,
            side="long",
            avg_bar_volume=3_000.0,
        )
        self.assertGreater(stressed["slippage"], liquid["slippage"])
        self.assertGreater(stressed["market_impact"], liquid["market_impact"])
        self.assertGreater(stressed["total"], liquid["total"])

    def test_position_sizing_respects_risk_and_fill_constraints(self):
        manager, session = self._build_manager_session()
        session.account_size_usd = 10_000.0
        session.risk_per_trade_pct = 1.0
        session.max_position_notional_pct = 100.0
        session.max_fill_participation_rate = 0.10
        session.min_fill_ratio = 0.20

        pos = self._open_long_position(
            manager=manager,
            session=session,
            ts=datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc),
            bar_volume=500.0,
        )
        # Risk sizing suggests ~100 shares, but 10% of 500 shares/bar caps fill to 50.
        self.assertAlmostEqual(pos.size, 50.0, places=3)
        self.assertAlmostEqual(pos.fill_ratio, 0.5, places=3)

    def test_time_exit_closes_stale_position(self):
        manager, session = self._build_manager_session()
        session.time_exit_bars = 2
        session.enable_partial_take_profit = False
        session.adverse_flow_exit_enabled = False

        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        self._open_long_position(manager, session, start)

        bars = [
            BarData(
                timestamp=start + timedelta(minutes=i),
                open=100.0,
                high=100.2,
                low=99.8,
                close=100.0,
                volume=10_000.0,
                vwap=100.0,
            )
            for i in range(3)
        ]
        session.bars.extend(bars)
        result = manager._process_trading_bar(session, bars[-1], bars[-1].timestamp)

        self.assertEqual(result.get("action"), "position_closed_time_exit")
        self.assertEqual(result.get("trade_closed", {}).get("exit_reason"), "time_exit")
        self.assertIsNone(session.active_position)

    def test_adverse_flow_exit_closes_against_flow(self):
        manager, session = self._build_manager_session()
        session.time_exit_bars = 500
        session.enable_partial_take_profit = False
        session.adverse_flow_exit_enabled = True
        session.adverse_flow_threshold = 0.05
        session.adverse_flow_min_hold_bars = 1

        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        self._open_long_position(manager, session, start)

        bars = []
        price = 100.0
        for i in range(6):
            price -= 0.10
            ts = start + timedelta(minutes=i)
            bars.append(
                BarData(
                    timestamp=ts,
                    open=price + 0.05,
                    high=price + 0.10,
                    low=price - 0.10,
                    close=price,
                    volume=12_000.0,
                    vwap=price,
                    l2_delta=-3_000.0,
                    l2_volume=5_000.0,
                    l2_imbalance=-0.25,
                )
            )

        session.bars.extend(bars)
        result = manager._process_trading_bar(session, bars[-1], bars[-1].timestamp)

        self.assertEqual(result.get("action"), "position_closed_adverse_flow")
        self.assertEqual(result.get("trade_closed", {}).get("exit_reason"), "adverse_flow")
        self.assertIsNone(session.active_position)


if __name__ == "__main__":
    unittest.main()

