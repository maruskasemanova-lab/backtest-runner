from datetime import datetime, timezone

from decision_tracker import DecisionTracker, MarkerType


def test_pattern_marker_type_removed_from_enum() -> None:
    marker_values = {marker.value for marker in MarkerType}
    assert "pattern_detected" not in marker_values


def test_signal_marker_still_serializes_expected_fields() -> None:
    tracker = DecisionTracker(run_id="r1", ticker="MU", date="2026-02-06")
    marker = tracker.add_signal(
        timestamp=datetime(2026, 2, 6, 15, 40, tzinfo=timezone.utc),
        bar_index=10,
        price=400.0,
        signal_type="BUY",
        strategy="MomentumFlow",
        confidence=82.5,
        reasoning="L2 aggression aligned",
        stop_loss=396.0,
        take_profit=406.0,
    )

    payload = marker.to_dict()
    assert payload["marker_type"] == "signal_generated"
    assert payload["details"]["signal_type"] == "BUY"
    assert payload["details"]["stop_loss"] == 396.0
