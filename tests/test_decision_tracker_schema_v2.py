from datetime import datetime, timezone

from decision_tracker import DecisionTracker


def test_exit_marker_schema_v2_includes_cost_fields() -> None:
    tracker = DecisionTracker(run_id="r1", ticker="MU", date="2026-02-06")
    marker = tracker.add_exit(
        timestamp=datetime(2026, 2, 6, 16, 0, tzinfo=timezone.utc),
        bar_index=42,
        price=101.0,
        side="short",
        reason="stop_loss",
        pnl_pct=-0.62,
        pnl_dollars=-62.47,
        entry_price=100.0,
        entry_time="2026-02-06T15:55:00+00:00",
        bars_held=6,
        size=10.0,
        costs={"total": 1.50},
    )

    details = marker.details
    assert details["schema_version"] == 2
    assert details["cost_usd"] == 1.50
    assert details["position_notional_usd"] == 1000.0
    assert round(details["cost_pct"], 2) == 0.15
    assert details["pnl_usd"] == -62.47

