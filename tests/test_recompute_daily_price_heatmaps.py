from __future__ import annotations

import pandas as pd

from scripts.recompute_daily_price_heatmaps import build_cumulative_rows_from_bars


def _row(df: pd.DataFrame, day: str, level: float) -> pd.Series:
    hit = df[(df["as_of_date"] == day) & (df["price_bin"] == level)]
    assert len(hit) == 1
    return hit.iloc[0]


def test_cumulative_rows_are_inclusive_and_carry_forward() -> None:
    bars = pd.DataFrame(
        {
            "trading_day": [
                "2026-09-13",
                "2026-09-13",
                "2026-09-14",
                "2026-09-14",
            ],
            "close": [100.10, 100.20, 101.00, 100.60],
            "volume": [10.0, 20.0, 30.0, 40.0],
        }
    )

    rows = build_cumulative_rows_from_bars(bars, ticker="MU", bin_size=0.5)
    assert not rows.empty

    d1_100 = _row(rows, "2026-09-13", 100.0)
    assert int(d1_100["day_bars"]) == 2
    assert int(d1_100["cumulative_bars"]) == 2
    assert float(d1_100["day_volume"]) == 30.0
    assert float(d1_100["cumulative_volume"]) == 30.0
    assert int(d1_100["total_bars_to_date"]) == 2

    d2_100 = _row(rows, "2026-09-14", 100.0)
    assert int(d2_100["day_bars"]) == 0
    assert int(d2_100["cumulative_bars"]) == 2
    assert float(d2_100["day_volume"]) == 0.0
    assert float(d2_100["cumulative_volume"]) == 30.0
    assert int(d2_100["total_bars_to_date"]) == 4

    d2_100_5 = _row(rows, "2026-09-14", 100.5)
    d2_101 = _row(rows, "2026-09-14", 101.0)
    assert int(d2_100_5["day_bars"]) == 1
    assert int(d2_101["day_bars"]) == 1
    assert int(d2_100_5["cumulative_bars"]) == 1
    assert int(d2_101["cumulative_bars"]) == 1
    assert float(d2_100_5["day_volume"]) == 40.0
    assert float(d2_101["day_volume"]) == 30.0
