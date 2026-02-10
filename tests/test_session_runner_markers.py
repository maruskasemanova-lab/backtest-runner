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


def test_session_end_marker_emitted_once_per_market_day() -> None:
    config = RunConfig(run_id="r1b", ticker="MU", date="2026-02-06_to_2026-02-07")
    runner = SessionRunner(config)

    ts_day1 = datetime(2026, 2, 6, 20, 55, tzinfo=timezone.utc)
    ts_day2 = datetime(2026, 2, 7, 20, 55, tzinfo=timezone.utc)
    bar = {"close": 100.5}

    response_day1 = {
        "phase": "END_OF_DAY",
        "session_summary": {"date": "2026-02-06", "total_pnl_pct": -0.35},
    }
    response_day2 = {
        "phase": "END_OF_DAY",
        "session_summary": {"date": "2026-02-07", "total_pnl_pct": 0.42},
    }

    asyncio.run(runner._process_decision_markers(response_day1, bar, ts_day1))
    asyncio.run(runner._process_decision_markers(response_day1, bar, ts_day1))
    asyncio.run(runner._process_decision_markers(response_day2, bar, ts_day2))

    markers = runner.get_markers()
    session_end_count = sum(1 for marker in markers if marker["marker_type"] == "session_ended")
    assert session_end_count == 2


def test_summary_uses_recorded_trades_for_range_totals() -> None:
    config = RunConfig(run_id="r1c", ticker="MU", date="2026-02-01_to_2026-02-05")
    runner = SessionRunner(config)
    runner.current_bar_index = 123
    runner.session_summary = {
        "date": "2026-02-01",
        "total_trades": 1,
        "total_pnl_pct": 0.18,
        "win_rate": 100.0,
    }

    runner.perf_tracker.record_trade(
        strategy="MomentumFlow",
        regime="TRENDING",
        ticker="MU",
        date=config.date,
        side="short",
        entry_price=100.0,
        exit_price=99.0,
        entry_time="2026-02-01T15:00:00+00:00",
        exit_time="2026-02-01T15:05:00+00:00",
        pnl_pct=1.0,
        pnl_dollars=10.0,
        exit_reason="take_profit",
    )
    runner.perf_tracker.record_trade(
        strategy="Evidence:l2_flow_aggression",
        regime="TRENDING",
        ticker="MU",
        date=config.date,
        side="long",
        entry_price=100.0,
        exit_price=99.5,
        entry_time="2026-02-02T15:00:00+00:00",
        exit_time="2026-02-02T15:05:00+00:00",
        pnl_pct=-0.5,
        pnl_dollars=-5.0,
        exit_reason="stop_loss",
    )

    summary = runner.get_summary()["session_summary"]
    assert summary["total_trades"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1
    assert summary["total_pnl_dollars"] == 5.0
    assert summary["bars_processed"] == 123


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


def test_pattern_marker_ignored_even_without_engine_hint() -> None:
    config = RunConfig(run_id="r3", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 10, 0, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "patterns_detected": [
            {"name": "Bullish Harami", "direction": "bullish", "strength": 72.0}
        ]
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    assert all(marker["marker_type"] != "pattern_detected" for marker in markers)


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
