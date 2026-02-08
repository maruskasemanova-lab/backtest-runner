"""
Tests for regime-aware trailing stop behavior.
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.day_trading_manager import BarData, DayTradingManager, SessionPhase  # noqa: E402
from src.strategies.base_strategy import Regime, Signal, SignalType  # noqa: E402


class RegimeAwareTrailingStopTests(unittest.TestCase):
    """Tests for the new regime-aware trailing stop logic."""

    def _build_manager_session(self, regime: Regime = Regime.TRENDING):
        """Create a manager and session with specified regime."""
        manager = DayTradingManager(
            regime_detection_minutes=0,
            max_trades_per_day=10,
            trade_cooldown_bars=0,
        )
        session = manager.get_or_create_session("trailing", "NVDA", "2026-02-03", 0)
        session.phase = SessionPhase.TRADING
        session.detected_regime = regime
        session.selected_strategy = None
        session.pending_signal = None
        return manager, session

    def _open_long_position(
        self, 
        manager: DayTradingManager, 
        session, 
        ts: datetime,
        trailing_stop: bool = True,
        entry_price: float = 100.0,
    ):
        """Open a long position with optional trailing stop."""
        signal = Signal(
            strategy_name="MomentumFlow",
            signal_type=SignalType.BUY,
            price=entry_price,
            timestamp=ts,
            confidence=90.0,
            stop_loss=entry_price * 0.99,
            take_profit=entry_price * 1.05,
            trailing_stop=trailing_stop,
            reasoning="unit-test",
        )
        pos = manager._open_position(
            session=session,
            signal=signal,
            entry_price=entry_price,
            entry_time=ts,
            signal_bar_index=0,
            entry_bar_index=0,
            entry_bar_volume=10_000.0,
        )
        return pos

    def test_trailing_disabled_in_choppy_regime(self):
        """Trailing stop should not update in CHOPPY regime by default."""
        manager, session = self._build_manager_session(regime=Regime.CHOPPY)
        session.trailing_enabled_in_choppy = False  # Default
        session.trailing_activation_pct = 0.0  # No threshold for this test
        
        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        pos = self._open_long_position(manager, session, start, trailing_stop=True)
        
        # Simulate profitable bar
        bar = BarData(
            timestamp=start + timedelta(minutes=1),
            open=100.0,
            high=102.0,
            low=100.0,
            close=101.5,  # +1.5% profit
            volume=10_000.0,
            vwap=101.0,
        )
        session.bars.append(bar)
        
        initial_trailing_price = pos.trailing_stop_price
        manager._update_trailing_from_close(session, pos, bar)
        
        # Trailing should NOT have been updated in CHOPPY
        self.assertEqual(pos.trailing_stop_price, initial_trailing_price)
        self.assertFalse(pos.break_even_stop_active)

    def test_trailing_activates_only_after_profit_threshold(self):
        """Trailing stop should only activate after reaching profit threshold."""
        manager, session = self._build_manager_session(regime=Regime.TRENDING)
        session.trailing_activation_pct = 0.30  # Require 0.3% profit
        session.break_even_buffer_pct = 0.05
        
        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        pos = self._open_long_position(manager, session, start, trailing_stop=True, entry_price=100.0)
        
        # Bar with only +0.2% profit (below threshold)
        bar1 = BarData(
            timestamp=start + timedelta(minutes=1),
            open=100.0,
            high=100.25,
            low=100.0,
            close=100.20,  # +0.2% - below threshold
            volume=10_000.0,
            vwap=100.1,
        )
        session.bars.append(bar1)
        manager._update_trailing_from_close(session, pos, bar1)
        
        # Should NOT have triggered break-even or trailing
        self.assertFalse(pos.trailing_activation_pnl_met)
        self.assertFalse(pos.break_even_stop_active)
        self.assertEqual(pos.trailing_stop_price, 0.0)
        
        # Bar with +0.5% profit (above threshold)
        bar2 = BarData(
            timestamp=start + timedelta(minutes=2),
            open=100.20,
            high=100.60,
            low=100.20,
            close=100.50,  # +0.5% - above threshold
            volume=10_000.0,
            vwap=100.3,
        )
        session.bars.append(bar2)
        manager._update_trailing_from_close(session, pos, bar2)
        
        # Should now have triggered break-even
        self.assertTrue(pos.trailing_activation_pnl_met)
        self.assertTrue(pos.break_even_stop_active)
        # Stop should be at entry + buffer
        expected_be_stop = 100.0 * (1 + 0.05 / 100)
        self.assertAlmostEqual(pos.stop_loss, expected_be_stop, places=4)

    def test_break_even_set_before_trailing(self):
        """Break-even stop must be set before trailing starts updating."""
        manager, session = self._build_manager_session(regime=Regime.TRENDING)
        session.trailing_activation_pct = 0.30
        session.break_even_buffer_pct = 0.05
        session.trailing_stop_pct = 0.8
        
        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        pos = self._open_long_position(manager, session, start, trailing_stop=True, entry_price=100.0)
        original_stop = pos.stop_loss
        
        # Bar with +0.5% profit to trigger threshold
        bar1 = BarData(
            timestamp=start + timedelta(minutes=1),
            open=100.0,
            high=100.60,
            low=100.0,
            close=100.50,
            volume=10_000.0,
            vwap=100.25,
        )
        session.bars.append(bar1)
        manager._update_trailing_from_close(session, pos, bar1)
        
        # Verify break-even was set
        self.assertTrue(pos.break_even_stop_active)
        self.assertGreater(pos.stop_loss, original_stop)
        
        # Now with higher price, trailing should engage
        bar2 = BarData(
            timestamp=start + timedelta(minutes=2),
            open=100.50,
            high=101.50,
            low=100.50,
            close=101.20,  # New high
            volume=10_000.0,
            vwap=101.0,
        )
        session.bars.append(bar2)
        manager._update_trailing_from_close(session, pos, bar2)
        
        # Trailing stop should now be set
        self.assertGreater(pos.trailing_stop_price, 0.0)
        # Should be based on highest price
        expected_trail = pos.highest_price * (1 - session.trailing_stop_pct / 100)
        self.assertAlmostEqual(pos.trailing_stop_price, expected_trail, places=4)

    def test_time_exit_shorter_in_choppy(self):
        """Time exit should use shorter limit in CHOPPY regime."""
        manager, session = self._build_manager_session(regime=Regime.CHOPPY)
        session.time_exit_bars = 40
        session.choppy_time_exit_bars = 12
        session.enable_partial_take_profit = False
        session.adverse_flow_exit_enabled = False
        
        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        pos = self._open_long_position(manager, session, start, trailing_stop=False)
        pos.entry_bar_index = 0
        
        # Generate bars up to choppy limit
        for i in range(13):
            bar = BarData(
                timestamp=start + timedelta(minutes=i),
                open=100.0,
                high=100.2,
                low=99.8,
                close=100.0,
                volume=10_000.0,
                vwap=100.0,
            )
            session.bars.append(bar)
        
        # Should trigger time exit (12 bars + 1)
        result = manager._should_time_exit(session, pos, 12)
        self.assertTrue(result)
        
    def test_time_exit_normal_in_trending(self):
        """Time exit should use normal limit in TRENDING regime."""
        manager, session = self._build_manager_session(regime=Regime.TRENDING)
        session.time_exit_bars = 40
        session.choppy_time_exit_bars = 12
        
        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        pos = self._open_long_position(manager, session, start, trailing_stop=False)
        pos.entry_bar_index = 0
        
        # Generate bars 
        for i in range(20):
            bar = BarData(
                timestamp=start + timedelta(minutes=i),
                open=100.0,
                high=100.2,
                low=99.8,
                close=100.0,
                volume=10_000.0,
                vwap=100.0,
            )
            session.bars.append(bar)
        
        # Should NOT trigger time exit at 12 bars in TRENDING
        result = manager._should_time_exit(session, pos, 12)
        self.assertFalse(result)

    def _open_short_position(
        self, 
        manager: DayTradingManager, 
        session, 
        ts: datetime,
        trailing_stop: bool = True,
        entry_price: float = 100.0,
    ):
        """Open a SHORT position with optional trailing stop."""
        signal = Signal(
            strategy_name="MomentumFlow",
            signal_type=SignalType.SELL,
            price=entry_price,
            timestamp=ts,
            confidence=90.0,
            stop_loss=entry_price * 1.01,  # Stop ABOVE entry for short
            take_profit=entry_price * 0.95,  # TP BELOW entry for short
            trailing_stop=trailing_stop,
            reasoning="unit-test-short",
        )
        pos = manager._open_position(
            session=session,
            signal=signal,
            entry_price=entry_price,
            entry_time=ts,
            signal_bar_index=0,
            entry_bar_index=0,
            entry_bar_volume=10_000.0,
        )
        return pos

    def test_short_stop_loss_is_above_entry(self):
        """Verify SHORT stop-loss is set ABOVE entry price."""
        manager, session = self._build_manager_session(regime=Regime.TRENDING)
        
        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        pos = self._open_short_position(manager, session, start, entry_price=100.0)
        
        # Stop loss must be above entry for SHORT
        self.assertGreater(pos.stop_loss, pos.entry_price)
        # Take profit must be below entry for SHORT
        self.assertLess(pos.take_profit, pos.entry_price)

    def test_short_break_even_is_above_entry(self):
        """Verify SHORT break-even stop is set ABOVE entry (protects profit)."""
        manager, session = self._build_manager_session(regime=Regime.TRENDING)
        session.trailing_activation_pct = 0.30
        session.break_even_buffer_pct = 0.05  # 0.05% buffer
        
        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        pos = self._open_short_position(manager, session, start, entry_price=100.0)
        original_stop = pos.stop_loss  # Should be 101.0 (1% above)
        
        # Simulate profitable drop (for SHORT, price going down = profit)
        bar = BarData(
            timestamp=start + timedelta(minutes=1),
            open=100.0,
            high=100.0,
            low=99.4,
            close=99.50,  # +0.5% profit for SHORT
            volume=10_000.0,
            vwap=99.7,
        )
        session.bars.append(bar)
        manager._update_trailing_from_close(session, pos, bar)
        
        # Break-even should have activated
        self.assertTrue(pos.trailing_activation_pnl_met)
        self.assertTrue(pos.break_even_stop_active)
        
        # For SHORT, break-even stop = entry * (1 + buffer) = 100.05
        # This is LOWER than original stop (101), so it's more protective
        expected_be_stop = 100.0 * (1 + 0.05 / 100)  # 100.05
        self.assertAlmostEqual(pos.stop_loss, expected_be_stop, places=4)
        
        # Be stop must still be ABOVE entry
        self.assertGreater(pos.stop_loss, pos.entry_price)
        # Be stop should be lower (more protective) than original stop
        self.assertLess(pos.stop_loss, original_stop)

    def test_short_stop_exit_has_negative_pnl(self):
        """Verify SHORT stopped out at stop_loss results in NEGATIVE PnL."""
        manager, session = self._build_manager_session(regime=Regime.TRENDING)
        session.trailing_activation_pct = 10.0  # High threshold so no break-even
        
        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
        pos = self._open_short_position(manager, session, start, entry_price=100.0)
        
        # Stop should be above entry
        self.assertGreater(pos.stop_loss, pos.entry_price)
        
        # Create bar that hits stop (price goes UP = loss for short)
        bar = BarData(
            timestamp=start + timedelta(minutes=1),
            open=100.0,
            high=101.5,  # Goes above stop at 101
            low=99.8,
            close=101.2,
            volume=10_000.0,
            vwap=100.5,
        )
        session.bars.append(bar)
        
        # Resolve exit
        exit_result = manager._resolve_exit_for_bar(pos, bar)
        self.assertIsNotNone(exit_result)
        exit_reason, exit_price = exit_result
        
        self.assertEqual(exit_reason, "stop_loss")
        # Exit price should be at or above entry (loss for short)
        self.assertGreater(exit_price, pos.entry_price)


if __name__ == "__main__":
    unittest.main()
