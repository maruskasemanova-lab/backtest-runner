from __future__ import annotations

from src.normalization import normalize_tuner_profiles


def test_normalize_tuner_profiles_preserves_candidate_runtime_payload() -> None:
    profiles = normalize_tuner_profiles(
        [
            {
                "profile_id": "p1",
                "candidate": {
                    "enabled_strategies": ["momentum"],
                    "trading_hours": [11, 12],
                    "time_filter_enabled": True,
                },
                "adaptive_version": 2,
                "score": 3.5,
            }
        ]
    )

    assert profiles[0]["candidate"]["enabled_strategies"] == ["momentum"]
    assert profiles[0]["candidate"]["trading_hours"] == [11, 12]
    assert profiles[0]["adaptive_version"] == 2
    assert profiles[0]["score"] == 3.5


def test_normalize_tuner_profiles_maps_legacy_best_candidate_to_candidate() -> None:
    profiles = normalize_tuner_profiles(
        [{"profile_id": "p1", "best_candidate": {"enabled_strategies": ["pullback"]}}]
    )

    assert profiles[0]["best_candidate"]["enabled_strategies"] == ["pullback"]
    assert profiles[0]["candidate"]["enabled_strategies"] == ["pullback"]
