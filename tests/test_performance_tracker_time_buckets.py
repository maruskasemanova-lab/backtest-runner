import unittest

from performance_tracker import PerformanceTracker


class PerformanceTrackerTimeBucketTests(unittest.TestCase):
    def test_hourly_and_weekday_summaries(self) -> None:
        tracker = PerformanceTracker()
        tracker.record_trade(
            strategy="momentum_flow",
            regime="TRENDING",
            ticker="NVDA",
            date="2026-02-02",  # Monday
            side="long",
            entry_price=100.0,
            exit_price=101.0,
            entry_time="2026-02-02T14:35:00+00:00",
            exit_time="2026-02-02T14:45:00+00:00",
            pnl_pct=1.0,
            pnl_dollars=100.0,
            exit_reason="take_profit",
        )
        tracker.record_trade(
            strategy="mean_reversion",
            regime="CHOPPY",
            ticker="AAPL",
            date="2026-02-03",  # Tuesday
            side="long",
            entry_price=200.0,
            exit_price=199.0,
            entry_time="2026-02-03T15:10:00+00:00",
            exit_time="2026-02-03T15:20:00+00:00",
            pnl_pct=-0.5,
            pnl_dollars=-50.0,
            exit_reason="stop_loss",
        )

        hourly = tracker.get_hourly_summary()
        weekday = tracker.get_weekday_summary()

        self.assertIn("14:00", hourly)
        self.assertIn("15:00", hourly)
        self.assertIn("Monday", weekday)
        self.assertIn("Tuesday", weekday)


if __name__ == "__main__":
    unittest.main()
