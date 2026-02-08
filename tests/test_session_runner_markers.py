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


def test_pattern_marker_skipped_for_evidence_engine() -> None:
    config = RunConfig(run_id="r2", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 10, 0, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "patterns_detected": [
            {"name": "Bullish Harami", "direction": "bullish", "strength": 72.0}
        ],
        "layer_scores": {"engine": "evidence_v1"},
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    assert all(marker["marker_type"] != "pattern_detected" for marker in markers)


def test_pattern_marker_emitted_for_multilayer_engine() -> None:
    config = RunConfig(run_id="r3", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 10, 0, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "patterns_detected": [
            {"name": "Bullish Harami", "direction": "bullish", "strength": 72.0}
        ],
        "layer_scores": {"engine": "multilayer_v2"},
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    assert any(marker["marker_type"] == "pattern_detected" for marker in markers)


def test_regime_explanation_does_not_claim_high_te_when_low() -> None:
    config = RunConfig(run_id="r4", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    response = {
        "regime": "TRENDING",
        "micro_regime": "CHOPPY",
        "indicators": {
            "trend_efficiency": 0.04,
            "volatility": 0.28,
            "adx": 17.2,
            "atr": 0.51,
        },
    }

    text = runner._generate_regime_explanation(response)
    assert "high trend efficiency" not in text.lower()
    assert "low" in text.lower()
