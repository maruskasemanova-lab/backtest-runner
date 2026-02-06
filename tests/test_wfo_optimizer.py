import unittest
from unittest.mock import patch

import wfo_optimizer


class WfoOptimizerExecutedStrategyTests(unittest.TestCase):
    def test_optimize_uses_executed_strategy_stats(self) -> None:
        dates = ["2026-01-05", "2026-01-06"]
        day_rows_map = {
            "2026-01-05": [object()],
            "2026-01-06": [object()],
        }

        fake_per_strategy = {
            # Simulates adaptive session where non-target strategy also traded.
            "mean_reversion": {
                "pnl": -3.0,
                "trades": 3.0,
                "wins": 1.0,
                "gross_wins": 1.5,
                "gross_losses": 4.5,
            },
            "momentum": {
                "pnl": 4.0,
                "trades": 2.0,
                "wins": 1.0,
                "gross_wins": 5.0,
                "gross_losses": 1.0,
            },
        }

        with patch.object(wfo_optimizer, "grid", return_value=[{"x": 1}]), patch.object(
            wfo_optimizer,
            "run_single_day",
            return_value=(1.0, 5, 2, 6.5, 5.5, fake_per_strategy),
        ):
            result = wfo_optimizer.optimize_strategy_for_dates(
                ticker="NVDA",
                day_rows_map=day_rows_map,
                dates=dates,
                strategy_name="momentum",
                param_grid={"x": [1]},
            )

        # Should aggregate only the target strategy stats (not overall session stats).
        self.assertEqual(result.trades, 4)
        self.assertAlmostEqual(result.total_pnl_pct, 8.0)
        self.assertAlmostEqual(result.win_rate, 50.0)
        self.assertAlmostEqual(result.profit_factor, 5.0)
        self.assertEqual(result.days_used, 2)


if __name__ == "__main__":
    unittest.main()
