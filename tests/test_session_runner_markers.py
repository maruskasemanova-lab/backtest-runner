import asyncio
from datetime import datetime, timezone

from session_runner import RunConfig, SessionRunner


def test_session_end_marker_emitted_only_once() -> None:
    config = RunConfig(run_id="r1", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner.load_bars(
        [
            {
                "timestamp": datetime(2026, 2, 6, 15, 55, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 1000.0,
            }
        ]
    )

    ts = datetime(2026, 2, 6, 15, 55, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "phase": "END_OF_DAY",
        "session_summary": {"total_pnl_pct": -0.35},
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    asyncio.run(runner._process_decision_markers(response, bar, ts))

    markers = runner.get_markers()
    session_end_count = sum(1 for marker in markers if marker["marker_type"] == "session_ended")
    assert session_end_count == 1

