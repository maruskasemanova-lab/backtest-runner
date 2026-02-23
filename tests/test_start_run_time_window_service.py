import pytest
from fastapi import HTTPException

from src.models.run_requests import StartRunRequest
from src.services.start_run_time_window_service import (
    filter_bars_for_requested_time_window,
    filter_reference_map_for_requested_time_window,
)
from src.time_utils import to_utc_datetime


def test_filter_bars_for_requested_time_window_keeps_only_segment() -> None:
    request = StartRunRequest(
        run_id="seg-1",
        ticker="MU",
        date="2026-02-10",
        start_time="2026-02-10T14:31:00Z",
        end_time="2026-02-10T14:33:00Z",
    )
    bars = [
        {"timestamp": "2026-02-10T14:30:00Z", "close": 1},
        {"timestamp": "2026-02-10T14:31:00Z", "close": 2},
        {"timestamp": "2026-02-10T14:32:00Z", "close": 3},
        {"timestamp": "2026-02-10T14:33:00Z", "close": 4},
        {"timestamp": "2026-02-10T14:34:00Z", "close": 5},
    ]

    filtered = filter_bars_for_requested_time_window(
        bars=bars,
        request=request,
        to_utc_datetime=to_utc_datetime,
    )

    assert [bar["close"] for bar in filtered] == [2, 3, 4]


def test_filter_reference_map_for_requested_time_window_keeps_only_segment() -> None:
    request = StartRunRequest(
        run_id="seg-2",
        ticker="MU",
        date="2026-02-10",
        start_time="2026-02-10T14:32:00Z",
        end_time="2026-02-10T14:33:00Z",
    )
    ref_map = {
        "2026-02-10T14:31:00Z": {"close": 10},
        "2026-02-10T14:32:00Z": {"close": 11},
        "2026-02-10T14:33:00Z": {"close": 12},
        "2026-02-10T14:34:00Z": {"close": 13},
    }

    filtered = filter_reference_map_for_requested_time_window(
        ref_bars_map=ref_map,
        request=request,
        to_utc_datetime=to_utc_datetime,
    )

    assert list(filtered.keys()) == [
        "2026-02-10T14:32:00Z",
        "2026-02-10T14:33:00Z",
    ]


def test_filter_time_window_rejects_inverted_window() -> None:
    request = StartRunRequest(
        run_id="seg-3",
        ticker="MU",
        date="2026-02-10",
        start_time="2026-02-10T14:35:00Z",
        end_time="2026-02-10T14:30:00Z",
    )

    with pytest.raises(HTTPException):
        filter_bars_for_requested_time_window(
            bars=[],
            request=request,
            to_utc_datetime=to_utc_datetime,
        )
