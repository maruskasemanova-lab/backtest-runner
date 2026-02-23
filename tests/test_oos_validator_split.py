import pytest

from oos_validator import split_dates_chronological, win_rate


def test_split_dates_chronological_maintains_order_and_non_empty_buckets() -> None:
    dates = [
        "2026-01-01",
        "2026-01-02",
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
        "2026-01-08",
        "2026-01-09",
        "2026-01-12",
        "2026-01-13",
        "2026-01-14",
    ]
    split = split_dates_chronological(dates, train_ratio=0.6, validation_ratio=0.2)

    assert split.train_dates == dates[:6]
    assert split.validation_dates == dates[6:8]
    assert split.test_dates == dates[8:]
    assert split.train_dates[-1] < split.validation_dates[0] < split.test_dates[0]


def test_split_dates_requires_minimum_history() -> None:
    with pytest.raises(ValueError):
        split_dates_chronological(
            ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
        )


def test_win_rate_handles_zero_trades() -> None:
    assert win_rate(0, 0) == 0.0
    assert win_rate(7, 10) == 70.0
