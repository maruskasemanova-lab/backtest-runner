from datetime import datetime, timezone

import numpy as np

from decision_tracker import DecisionTracker


def test_marker_to_dict_handles_numpy_datetime64_and_scalars() -> None:
    tracker = DecisionTracker(run_id="r1", ticker="MU", date="2026-02-13")
    marker = tracker.add_session_start(
        timestamp=np.datetime64("2026-02-13T14:31:00"),
        bar_index=0,
        price=np.float64(101.25),
    )
    marker.details["nested"] = {
        "day": np.datetime64("2026-02-13"),
        "sizes": np.array([1, 2, 3], dtype=np.int64),
    }

    payload = marker.to_dict()

    assert payload["timestamp"].startswith("2026-02-13T14:31:00")
    assert payload["price"] == 101.25
    assert payload["details"]["nested"]["day"] == "2026-02-13"
    assert payload["details"]["nested"]["sizes"] == [1, 2, 3]


def test_chart_annotations_support_numpy_datetime64_timestamp() -> None:
    tracker = DecisionTracker(run_id="r1", ticker="MU", date="2026-02-13")
    tracker.add_session_start(
        timestamp=np.datetime64("2026-02-13T14:31:00"),
        bar_index=0,
        price=100.0,
    )

    annotations = tracker.get_chart_annotations()

    expected_epoch = int(
        datetime(2026, 2, 13, 14, 31, 0, tzinfo=timezone.utc).timestamp()
    )
    assert annotations[0]["time"] == expected_epoch
