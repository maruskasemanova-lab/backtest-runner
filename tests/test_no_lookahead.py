import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.day_trading_manager import DayTradingManager  # noqa: E402
from src.strategies.base_strategy import Regime, Signal, SignalType  # noqa: E402


class NoLookaheadInvariantTests(unittest.TestCase):
    def test_signal_bar_index_is_strictly_before_entry_bar_index(self) -> None:
        manager = DayTradingManager(
            regime_detection_minutes=0,
            max_trades_per_day=5,
            trade_cooldown_bars=0,
        )
        manager.ticker_params["NVDA"] = {"time_filter_enabled": False, "trading_hours": None}

        # Keep only one deterministic strategy for test stability.
        for name, strat in manager.strategies.items():
            strat.enabled = (name == "mean_reversion")
        manager.strategies["mean_reversion"].allowed_regimes = [
            Regime.TRENDING,
            Regime.CHOPPY,
            Regime.MIXED,
        ]

        signal_sent = {"done": False}

        def scripted_signal(current_price, ohlcv, indicators, regime, timestamp):
            if signal_sent["done"]:
                return None
            signal_sent["done"] = True
            return Signal(
                strategy_name="MeanReversion",
                signal_type=SignalType.BUY,
                price=current_price,
                timestamp=timestamp,
                confidence=95.0,
                stop_loss=current_price * 0.99,
                take_profit=current_price * 1.01,
                trailing_stop=False,
                reasoning="unit-test scripted signal",
            )

        manager.strategies["mean_reversion"].generate_signal = scripted_signal

        start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)  # 09:30 ET
        prices = [100.00, 100.05, 100.20, 101.30, 101.10, 101.00]

        # First bar initializes session; then force pattern detector to no-op
        # so scripted signal path is deterministic in this unit test.
        manager.process_bar(
            run_id="lookahead-test",
            ticker="NVDA",
            timestamp=start,
            bar_data={
                "open": prices[0] - 0.05,
                "high": prices[0] + 0.10,
                "low": prices[0] - 0.10,
                "close": prices[0],
                "volume": 1000,
                "vwap": prices[0],
            },
        )
        session = manager.get_session("lookahead-test", "NVDA", "2026-02-03")
        self.assertIsNotNone(session)
        manager.ticker_params["NVDA"] = {"time_filter_enabled": False, "trading_hours": None}
        session.multi_layer.require_pattern = False
        session.multi_layer.pattern_detector.detect = lambda ohlcv, indicators=None: []

        for idx, close in enumerate(prices[1:], start=1):
            ts = start + timedelta(minutes=idx)
            manager.process_bar(
                run_id="lookahead-test",
                ticker="NVDA",
                timestamp=ts,
                bar_data={
                    "open": close - 0.05,
                    "high": close + (0.40 if idx == 3 else 0.10),
                    "low": close - 0.10,
                    "close": close,
                    "volume": 1000 + idx * 25,
                    "vwap": close,
                },
            )

        self.assertGreaterEqual(len(session.trades), 1)

        for trade in session.trades:
            self.assertIsNotNone(trade.signal_bar_index)
            self.assertIsNotNone(trade.entry_bar_index)
            self.assertLess(trade.signal_bar_index, trade.entry_bar_index)


if __name__ == "__main__":
    unittest.main()
