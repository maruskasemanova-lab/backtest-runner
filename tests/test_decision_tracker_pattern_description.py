from datetime import datetime, timezone

from decision_tracker import DecisionTracker


def test_pattern_description_uses_comparison_labels_not_fraction() -> None:
    tracker = DecisionTracker(run_id="r1", ticker="MU", date="2026-02-06")
    marker = tracker.add_pattern_detected(
        timestamp=datetime(2026, 2, 6, 15, 40, tzinfo=timezone.utc),
        bar_index=10,
        price=400.0,
        patterns=[{"name": "Morning Star", "strength": 100, "direction": "bullish"}],
        direction="bullish",
        layer_scores={
            "pattern_score": 70.0,
            "pattern_threshold": 58.0,
            "trade_gate_threshold": 68.0,
            "threshold_used": 58.0,
            "threshold_used_reason": "pattern_confirmation",
            "combined_raw": 45.0,
            "combined_norm_0_100": 100.0,
            "pattern_confirmation": True,
            "effective_strategy_weight": 1.0,
            "strategy_weight_source": "l2",
            "l2_coverage_ratio": 0.83,
        },
    )

    description = marker.description
    assert "Pattern score=70.0 >= 58.0 (confirm)" in description
    assert "Gate: used=58.0 (trade_th=68.0, reason=pattern_confirmation)" in description
    assert "Combined: raw=45.0 | norm=100.0/100" in description
    assert "Weights: effective_strategy_weight=1.00 | source=l2 | l2_coverage=0.83" in description
    assert "70.0/58.0" not in description


def test_pattern_description_marks_neutral_forced_zero() -> None:
    tracker = DecisionTracker(run_id="r1", ticker="MU", date="2026-02-06")
    marker = tracker.add_pattern_detected(
        timestamp=datetime(2026, 2, 6, 15, 41, tzinfo=timezone.utc),
        bar_index=11,
        price=401.0,
        patterns=[{"name": "Doji", "strength": 40, "direction": "neutral"}],
        direction="neutral",
        layer_scores={
            "pattern_score": 0.0,
            "pattern_threshold": 58.0,
            "trade_gate_threshold": 68.0,
            "threshold_used": 68.0,
            "threshold_used_reason": "no_pattern_confirmation",
            "combined_raw": 0.0,
            "combined_norm_0_100": 0.0,
            "pattern_confirmation": False,
            "strategy_weight": 0.55,
        },
    )

    description = marker.description
    assert "Pattern score=0.0 (neutral pattern -> forced to 0, th=58.0)" in description
    assert "Gate: used=68.0 (trade_th=68.0, reason=no_pattern_confirmation)" in description
    assert "Combined: raw=0.0 | norm=0.0/100" in description
    assert "Weights: effective_strategy_weight=0.55 | source=legacy" in description
    assert "Pattern confirmation: no" in description
