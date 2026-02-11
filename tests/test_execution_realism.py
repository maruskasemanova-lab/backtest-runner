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

    def test_fixed_stop_loss_mode_overrides_strategy_stop(self):
        manager, session = self._build_manager_session()
        session.stop_loss_mode = "fixed"
        session.fixed_stop_loss_pct = 0.5
        session.max_fill_participation_rate = 1.0
        session.min_fill_ratio = 1.0

        ts = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        signal = Signal(
            strategy_name="MomentumFlow",
            signal_type=SignalType.BUY,
            price=100.0,
            timestamp=ts,
            confidence=80.0,
            stop_loss=98.0,
            take_profit=103.0,
            trailing_stop=False,
            reasoning="fixed-stop-test",
        )
        pos = manager._open_position(
            session=session,
            signal=signal,
            entry_price=100.0,
            entry_time=ts,
            signal_bar_index=0,
            entry_bar_index=0,
            entry_bar_volume=50_000.0,
        )
        self.assertAlmostEqual(pos.stop_loss, 99.5, places=4)

    def test_capped_stop_loss_mode_only_tightens_wide_strategy_stop(self):
        manager, session = self._build_manager_session()
        session.stop_loss_mode = "capped"
        session.fixed_stop_loss_pct = 0.5
        session.max_fill_participation_rate = 1.0
        session.min_fill_ratio = 1.0
        ts = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)

        # Already tight stop should remain unchanged.
        tight_signal = Signal(
            strategy_name="MomentumFlow",
            signal_type=SignalType.BUY,
            price=100.0,
            timestamp=ts,
            confidence=80.0,
            stop_loss=99.8,
            take_profit=103.0,
            trailing_stop=False,
            reasoning="capped-stop-tight",
        )
        tight_pos = manager._open_position(
            session=session,
            signal=tight_signal,
            entry_price=100.0,
            entry_time=ts,
            signal_bar_index=0,
            entry_bar_index=0,
            entry_bar_volume=50_000.0,
        )
        self.assertAlmostEqual(tight_pos.stop_loss, 99.8, places=4)

        session.active_position = None

        # Wide stop should be capped to fixed percentage.
        wide_signal = Signal(
            strategy_name="MomentumFlow",
            signal_type=SignalType.BUY,
            price=100.0,
            timestamp=ts,
            confidence=80.0,
            stop_loss=99.0,
            take_profit=103.0,
            trailing_stop=False,
            reasoning="capped-stop-wide",
        )
        wide_pos = manager._open_position(
            session=session,
            signal=wide_signal,
            entry_price=100.0,
            entry_time=ts,
            signal_bar_index=0,
            entry_bar_index=0,
            entry_bar_volume=50_000.0,
        )
        self.assertAlmostEqual(wide_pos.stop_loss, 99.5, places=4)

    def test_position_size_scales_down_for_low_source_agreement(self):
        manager, session = self._build_manager_session()
        session.account_size_usd = 10_000.0
        session.risk_per_trade_pct = 1.0
        session.max_position_notional_pct = 100.0
        session.max_fill_participation_rate = 1.0
        session.min_fill_ratio = 1.0

        ts = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        base_kwargs = dict(
            strategy_name="MomentumFlow",
            signal_type=SignalType.BUY,
            price=100.0,
            timestamp=ts,
            confidence=80.0,
            stop_loss=99.0,
            take_profit=103.0,
            trailing_stop=False,
            reasoning="agreement-size",
        )
        low_agreement_signal = Signal(
            **base_kwargs,
            metadata={"layer_scores": {"confirming_sources": 1}},
        )
        high_agreement_signal = Signal(
            **base_kwargs,
            metadata={"layer_scores": {"confirming_sources": 3}},
        )

        low_size = manager._calculate_position_size(session, low_agreement_signal, 100.0)
        high_size = manager._calculate_position_size(session, high_agreement_signal, 100.0)
        self.assertLess(low_size, high_size)

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
                    l2_book_pressure=-0.25,
                )
            )

        session.bars.extend(bars)
        result = manager._process_trading_bar(session, bars[-1], bars[-1].timestamp)

        self.assertEqual(result.get("action"), "position_closed_adverse_flow")
        self.assertEqual(result.get("trade_closed", {}).get("exit_reason"), "adverse_flow")
        self.assertIsNone(session.active_position)

    def test_intrabar_quotes_can_resolve_tp_before_later_stop(self):
        manager, session = self._build_manager_session()
        session.enable_partial_take_profit = False
        session.adverse_flow_exit_enabled = False
        session.time_exit_bars = 500

        ts = datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc)
        pos = self._open_long_position(manager, session, ts)
        pos.stop_loss = 99.0
        pos.take_profit = 101.0

        # OHLC touches both stop and TP, but 1s quote path reaches TP first.
        bar = BarData(
            timestamp=ts + timedelta(minutes=1),
            open=100.0,
            high=101.3,
            low=98.7,
            close=100.4,
            volume=8_000.0,
            vwap=100.2,
            intrabar_quotes_1s=[
                {"s": 5, "bid": 100.2, "ask": 100.3},
                {"s": 12, "bid": 101.05, "ask": 101.1},  # TP hit first for long exit.
                {"s": 45, "bid": 98.95, "ask": 99.0},    # Stop would hit later.
            ],
        )

        result = manager._process_trading_bar(session, bar, bar.timestamp)
        self.assertEqual(result.get("action"), "position_closed_take_profit")
        self.assertEqual(result.get("trade_closed", {}).get("exit_reason"), "take_profit")
        self.assertIsNone(session.active_position)

    def test_intrabar_quotes_same_second_conflict_keeps_conservative_stop(self):
        manager, session = self._build_manager_session()
        ts = datetime(2026, 2, 3, 15, 10, tzinfo=timezone.utc)
        pos = self._open_long_position(manager, session, ts)
        pos.stop_loss = 99.0
        pos.take_profit = 101.0

        bar = BarData(
            timestamp=ts + timedelta(minutes=1),
            open=100.0,
            high=101.4,
            low=98.8,
            close=100.1,
            volume=7_500.0,
            vwap=100.0,
            # Same-second quote implies ambiguity; stop must win.
            intrabar_quotes_1s=[{"s": 22, "bid": 98.9, "ask": 101.2}],
        )
        exit_result = manager._resolve_exit_for_bar(pos, bar)
        self.assertIsNotNone(exit_result)
        exit_reason, exit_price = exit_result
        self.assertEqual(exit_reason, "stop_loss")
        self.assertAlmostEqual(exit_price, 99.0, places=4)

    def test_intrabar_fallback_to_ohlc_when_quotes_have_no_coverage(self):
        manager, session = self._build_manager_session()
        ts = datetime(2026, 2, 3, 15, 20, tzinfo=timezone.utc)
        pos = self._open_long_position(manager, session, ts)
        pos.stop_loss = 99.0
        pos.take_profit = 101.0

        bar = BarData(
            timestamp=ts + timedelta(minutes=1),
            open=100.0,
            high=101.1,
            low=98.9,
            close=100.0,
            volume=6_000.0,
            vwap=100.0,
            # No valid bid/ask -> should fall back to OHLC conservative stop.
            intrabar_quotes_1s=[{"s": 10, "bid": 0.0, "ask": 0.0}],
        )
        exit_result = manager._resolve_exit_for_bar(pos, bar)
        self.assertIsNotNone(exit_result)
        exit_reason, _ = exit_result
        self.assertEqual(exit_reason, "stop_loss")


if __name__ == "__main__":
    unittest.main()
