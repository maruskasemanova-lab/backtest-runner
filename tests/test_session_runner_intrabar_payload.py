import asyncio
from datetime import datetime, timezone

import pandas as pd

import session_runner as session_runner_module
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


def test_intrabar_quote_loader_applies_5s_sampling_without_breaking_cache() -> None:
    ts_grid = pd.to_datetime(
        [
            "2026-02-06T15:00:01Z",
            "2026-02-06T15:00:02Z",
            "2026-02-06T15:00:04Z",
            "2026-02-06T15:00:05Z",
            "2026-02-06T15:00:08Z",
            "2026-02-06T15:00:11Z",
        ],
        utc=True,
    )
    frames = pd.DataFrame(
        {
            "ts_sec": ts_grid,
            "top_bid_px": [100.1, 100.12, 100.14, 100.2, 100.28, 100.3],
            "top_ask_px": [100.15, 100.17, 100.19, 100.25, 100.33, 100.35],
            "has_book_coverage": [True, True, True, True, True, True],
        }
    )
    manager = _DummyL2Manager(frames)

    runner = SessionRunner(
        RunConfig(
            run_id="intrabar-cache-5s",
            ticker="MU",
            date="2026-02-06",
            intrabar_execution_recalc_1s=True,
            intrabar_eval_step_seconds=5,
        )
    )
    runner.l2_manager = manager
    ts = datetime(2026, 2, 6, 15, 0, 22, tzinfo=timezone.utc)

    sampled = runner._load_intrabar_quotes(ts)
    assert sampled == [
        {"s": 1, "bid": 100.1, "ask": 100.15},
        {"s": 5, "bid": 100.2, "ask": 100.25},
        {"s": 11, "bid": 100.3, "ask": 100.35},
    ]

    # Cache keeps full minute quotes, so switching back to 1s should not trigger a reload.
    runner.config.intrabar_eval_step_seconds = 1
    full = runner._load_intrabar_quotes(ts)
    assert manager.calls == 1
    assert full == [
        {"s": 1, "bid": 100.1, "ask": 100.15},
        {"s": 2, "bid": 100.12, "ask": 100.17},
        {"s": 4, "bid": 100.14, "ask": 100.19},
        {"s": 5, "bid": 100.2, "ask": 100.25},
        {"s": 8, "bid": 100.28, "ask": 100.33},
        {"s": 11, "bid": 100.3, "ask": 100.35},
    ]


def test_intrabar_attach_gate_depends_on_mode_and_l2_availability() -> None:
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
    assert runner._should_attach_intrabar_quotes() is True

    runner._pending_entry = True
    assert runner._should_attach_intrabar_quotes() is True

    runner._pending_entry = False
    runner._position_active = True
    assert runner._should_attach_intrabar_quotes() is True

    runner.l2_manager = None
    assert runner._should_attach_intrabar_quotes() is False

    runner.config.intrabar_execution_recalc_1s = False
    runner.l2_manager = _DummyL2Manager(pd.DataFrame())
    assert runner._should_attach_intrabar_quotes() is False


def test_l2_quality_fields_are_whitelisted_for_strategy_payload() -> None:
    assert "l2_quality_flags" in SessionRunner.L2_PAYLOAD_KEYS
    assert "l2_quality" in SessionRunner.L2_PAYLOAD_KEYS


def test_process_bar_attaches_intrabar_quotes_before_any_position(monkeypatch) -> None:
    ts_grid = pd.to_datetime(
        [
            "2026-02-06T15:00:01Z",
            "2026-02-06T15:00:05Z",
        ],
        utc=True,
    )
    frames = pd.DataFrame(
        {
            "ts_sec": ts_grid,
            "top_bid_px": [100.1, 100.2],
            "top_ask_px": [100.15, 100.25],
            "has_book_coverage": [True, True],
        }
    )
    runner = SessionRunner(
        RunConfig(
            run_id="intrabar-payload",
            ticker="MU",
            date="2026-02-06",
            intrabar_execution_recalc_1s=True,
            strategy_api_url="http://strategy-api.test",
        )
    )
    runner.l2_manager = _DummyL2Manager(frames)
    runner._position_active = False
    runner._pending_entry = False

    captured = {}

    class _FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {"phase": "RUNNING", "action": "hold"}

        async def text(self):
            return ""

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(session_runner_module.httpx, "AsyncClient", _FakeSession)

    bar = {
        "timestamp": datetime(2026, 2, 6, 15, 0, tzinfo=timezone.utc),
        "open": 100.0,
        "high": 100.4,
        "low": 99.9,
        "close": 100.2,
        "volume": 1_000.0,
    }
    runner.load_bars([bar])

    result = asyncio.run(runner._process_bar(runner.bars[0]))

    assert result["success"] is True
    assert captured["url"].endswith("/api/session/bar")
    assert "intrabar_quotes_1s" in captured["json"]
    assert captured["json"]["intrabar_quotes_1s"] == [
        {"s": 1, "bid": 100.1, "ask": 100.15},
        {"s": 5, "bid": 100.2, "ask": 100.25},
    ]
