from __future__ import annotations

from datetime import datetime, timezone

from src.services.start_run_range_utils import (
    bar_time_token,
    is_day_range_superset,
    range_span_days,
    slice_bars_for_day_range,
    slice_reference_map_for_day_range,
    summarize_days_compact,
)
from src.services.start_run_time_filter_utils import (
    canonical_trading_hours,
    coerce_include_extended_hours,
)


def test_canonical_trading_hours_sorts_deduplicates_and_filters() -> None:
    assert canonical_trading_hours([11, "9", 11, 24, -1, "bad", 10]) == (9, 10, 11)
    assert canonical_trading_hours(None) == ()


def test_coerce_include_extended_hours_handles_mixed_inputs() -> None:
    assert coerce_include_extended_hours(True) is True
    assert coerce_include_extended_hours(False) is False
    assert coerce_include_extended_hours("yes") is True
    assert coerce_include_extended_hours("off") is False
    assert coerce_include_extended_hours(1) is True
    assert coerce_include_extended_hours(0) is False
    assert coerce_include_extended_hours("maybe") is None
    assert coerce_include_extended_hours(None) is None


def test_summarize_days_compact_overflow_format() -> None:
    assert summarize_days_compact(["2026-02-01", "2026-02-02"], max_days=8) == (
        "2026-02-01,2026-02-02"
    )
    assert summarize_days_compact(
        ["2026-02-01", "2026-02-02", "2026-02-03"],
        max_days=2,
    ) == "2026-02-01,2026-02-02,...(+1 more)"


def test_range_helpers_for_superset_and_span() -> None:
    assert is_day_range_superset("2026-02-01", "2026-02-10", "2026-02-03", "2026-02-04")
    assert not is_day_range_superset(
        "2026-02-01",
        "2026-02-03",
        "2026-02-03",
        "2026-02-04",
    )
    assert range_span_days("2026-02-01", "2026-02-04") == 3


def test_slice_helpers_filter_by_day_window() -> None:
    bars = [
        {"timestamp": datetime(2026, 2, 2, 14, 0, tzinfo=timezone.utc), "open": 1.0},
        {"timestamp": datetime(2026, 2, 3, 14, 0, tzinfo=timezone.utc), "open": 2.0},
        {"timestamp": datetime(2026, 2, 4, 14, 0, tzinfo=timezone.utc), "open": 3.0},
    ]
    selected_bars = slice_bars_for_day_range(
        bars,
        range_start="2026-02-03",
        range_end="2026-02-04",
    )
    assert [bar["open"] for bar in selected_bars] == [2.0, 3.0]

    ref_map = {
        "2026-02-02T14:00:00+00:00": {"ticker": "QQQ", "close": 1.0},
        "2026-02-03T14:00:00+00:00": {"ticker": "QQQ", "close": 2.0},
    }
    selected_ref = slice_reference_map_for_day_range(
        ref_map,
        range_start="2026-02-03",
        range_end="2026-02-04",
    )
    assert list(selected_ref.keys()) == ["2026-02-03T14:00:00+00:00"]


def test_bar_time_token_prefers_isoformat() -> None:
    ts = datetime(2026, 2, 3, 14, 0, tzinfo=timezone.utc)
    assert bar_time_token(ts).startswith("2026-02-03T14:00:00")
