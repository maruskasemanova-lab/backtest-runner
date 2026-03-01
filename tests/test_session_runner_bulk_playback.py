from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List

import polars as pl
import pytest

import session_runner as session_runner_module
from session_runner import RunConfig, SessionRunner


def _build_bar(minute: int) -> Dict[str, Any]:
    return {
        "timestamp": datetime(2026, 2, 6, 15, minute, tzinfo=timezone.utc),
        "open": 100.0 + minute,
        "high": 100.5 + minute,
        "low": 99.5 + minute,
        "close": 100.2 + minute,
        "volume": 1_000.0 + minute,
    }


def test_run_all_uses_bulk_batches_and_throttles_bar_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKTEST_RUNNER_BULK_PLAYBACK_ENABLED", "1")
    monkeypatch.setenv("BACKTEST_RUNNER_BULK_TRADE_CHUNK_SIZE", "2")
    monkeypatch.setenv("BACKTEST_RUNNER_WS_THROTTLE_MS", "3600000")
    monkeypatch.setenv("BACKTEST_RUNNER_WS_PROGRESS_STEP_PCT", "101")

    runner = SessionRunner(
        RunConfig(
            run_id="bulk-playback-1",
            ticker="MU",
            date="2026-02-06",
            strategy_api_url="http://strategy-api.test",
        )
    )
    runner._trade_start_time = datetime(2026, 2, 6, 15, 1, tzinfo=timezone.utc)
    runner.load_bars([_build_bar(0), _build_bar(1), _build_bar(2)])

    bar_events: List[Dict[str, Any]] = []
    runner.on_bar(lambda bar: bar_events.append(dict(bar)))

    captured_batch_sizes: List[int] = []
    captured_content_types: List[str] = []

    class _Response:
        def __init__(self, payload: Dict[str, Any]):
            self.status = 200
            self._payload = payload

        async def json(self) -> Dict[str, Any]:
            return self._payload

        async def text(self) -> str:
            return ""

    class _BatchSession:
        def __init__(self, *args: Any, **kwargs: Any):
            self.closed = False

        def post(self, url: str, **kwargs: Any) -> _Response:
            assert str(url).endswith("/api/session/bars")
            captured_content_types.append(
                str((kwargs.get("headers") or {}).get("content-type") or "")
            )
            rows = pl.read_ipc(BytesIO(kwargs["content"])).to_dicts()
            captured_batch_sizes.append(len(rows))
            return _Response(
                {
                    "results": [
                        {
                            "phase": "TRADING",
                            "action": "hold",
                            "signals": [],
                            "warmup_only": bool(row.get("warmup_only")),
                        }
                        for row in rows
                    ]
                }
            )

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(session_runner_module.httpx, "AsyncClient", _BatchSession)

    summary = asyncio.run(runner.run_all(speed_ms="max"))

    assert summary["processed_bars"] == 3
    assert runner.current_bar_index == 3
    assert captured_batch_sizes == [1, 2]
    assert captured_content_types == [
        "application/vnd.apache.arrow.stream",
        "application/vnd.apache.arrow.stream",
    ]
    assert len(bar_events) == 3
    assert bar_events[0]["warmup_only"] is True
    assert bar_events[1]["warmup_only"] is False
    assert bar_events[1]["bar_index"] == 1
    assert bar_events[-1]["bar_index"] == 2
