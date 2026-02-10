from datetime import datetime, timezone

import pandas as pd

from session_runner import RunConfig, SessionRunner


class _DummyL2Manager:
    def __init__(self, frames: pd.DataFrame):
        self.frames = frames
        self.calls = 0

    def get_intrabar_frames(self, ticker: str, start_time, end_time):
        self.calls += 1
        return self.frames.copy()


def test_intrabar_quote_loader_caches_per_minute() -> None:
    ts_grid = pd.to_datetime(
        [
            "2026-02-06T15:00:01Z",
            "2026-02-06T15:00:05Z",
            "2026-02-06T15:00:08Z",
        ],
        utc=True,
    )
    frames = pd.DataFrame(
        {
            "ts_sec": ts_grid,
            "top_bid_px": [100.1, 100.2, 100.3],
            "top_ask_px": [100.15, 100.25, 100.35],
            "has_book_coverage": [True, True, True],
        }
    )
    manager = _DummyL2Manager(frames)

    runner = SessionRunner(
        RunConfig(
            run_id="intrabar-cache",
            ticker="MU",
            date="2026-02-06",
            intrabar_execution_recalc_1s=True,
        )
    )
    runner.l2_manager = manager

    ts = datetime(2026, 2, 6, 15, 0, 22, tzinfo=timezone.utc)
    first = runner._load_intrabar_quotes(ts)
    second = runner._load_intrabar_quotes(ts)

    assert manager.calls == 1
    assert first == second
    assert first == [
        {"s": 1, "bid": 100.1, "ask": 100.15},
        {"s": 5, "bid": 100.2, "ask": 100.25},
        {"s": 8, "bid": 100.3, "ask": 100.35},
    ]


def test_intrabar_attach_gate_requires_execution_state() -> None:
    runner = SessionRunner(
        RunConfig(
            run_id="intrabar-gate",
            ticker="MU",
            date="2026-02-06",
            intrabar_execution_recalc_1s=True,
        )
    )
    runner.l2_manager = _DummyL2Manager(pd.DataFrame())

    runner._position_active = False
    runner._pending_entry = False
    assert runner._should_attach_intrabar_quotes() is False

    runner._pending_entry = True
    assert runner._should_attach_intrabar_quotes() is True

    runner._pending_entry = False
    runner._position_active = True
    assert runner._should_attach_intrabar_quotes() is True
