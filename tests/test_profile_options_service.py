from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.services.profile_options_service import (
    build_adaptive_tuner_options_payload,
)


def test_build_adaptive_tuner_options_payload_uses_overlap_defaults() -> None:
    def _load_aos_config():
        return {
            "tickers": {
                "MU": {
                    "adaptive_tuner_profiles": [{"profile_id": "p1"}],
                    "active_adaptive_tuner_profile_id": "p1",
                }
            }
        }

    def _normalize_tuner_profiles(raw):
        return list(raw or [])

    def _covered_days_for_schema(ticker: str, schema: str):
        assert ticker == "MU"
        if schema == "ohlcv-1m":
            return ["2026-02-01", "2026-02-02", "2026-02-03"]
        if schema == "mbp-10":
            return ["2026-02-02", "2026-02-03", "2026-02-04"]
        return []

    def _range_summary_from_days(days):
        values = sorted(days)
        if not values:
            return {"start": None, "end": None}
        return {"start": values[0], "end": values[-1]}

    payload = build_adaptive_tuner_options_payload(
        "MU",
        load_aos_config=_load_aos_config,
        normalize_tuner_profiles=_normalize_tuner_profiles,
        covered_days_for_schema=_covered_days_for_schema,
        range_summary_from_days=_range_summary_from_days,
    )

    assert payload["ticker"] == "MU"
    assert payload["l2_overlap_days"] == ["2026-02-02", "2026-02-03"]
    assert payload["default_date_from"] == "2026-02-02"
    assert payload["default_date_to"] == "2026-02-03"
    assert payload["has_l2_overlap"] is True
    assert payload["profiles"] == [{"profile_id": "p1"}]
    assert payload["active_profile_id"] == "p1"


def test_build_adaptive_tuner_options_payload_requires_ticker() -> None:
    with pytest.raises(HTTPException) as exc:
        build_adaptive_tuner_options_payload(
            "",
            load_aos_config=lambda: {},
            normalize_tuner_profiles=lambda value: [],
            covered_days_for_schema=lambda _ticker, _schema: [],
            range_summary_from_days=lambda _days: {"start": None, "end": None},
        )

    assert exc.value.status_code == 400
    assert "ticker is required" in str(exc.value.detail).lower()
