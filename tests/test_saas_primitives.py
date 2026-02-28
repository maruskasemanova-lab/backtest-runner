from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.services import saas_primitives as primitives


def test_resolve_plan_limits_known_and_unknown_tiers() -> None:
    assert primitives.resolve_plan_limits("premium").plan_tier == "premium"
    assert primitives.resolve_plan_limits("ADMIN").plan_tier == "admin"
    assert primitives.resolve_plan_limits("unknown").plan_tier == "free"


def test_utc_day_key_and_parse_datetime_roundtrip() -> None:
    assert primitives.utc_day_key(date(2026, 2, 28)) == "2026-02-28"
    parsed = primitives.parse_utc_datetime("2026-02-28T12:00:00Z")
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert parsed.isoformat().startswith("2026-02-28T12:00:00")


def test_parse_utc_datetime_accepts_epoch_and_rejects_invalid() -> None:
    parsed = primitives.parse_utc_datetime("1772280000")
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert primitives.parse_utc_datetime("not-a-datetime") is None


def test_normalize_user_settings_payload_validates_shape() -> None:
    payload = {"a": 1, "nested": {"b": True}}
    normalized = primitives.normalize_user_settings_payload(payload)
    assert normalized == payload
    with pytest.raises(ValueError):
        primitives.normalize_user_settings_payload(["not", "an", "object"])


def test_normalize_run_summary_payload_coerces_datetimes() -> None:
    payload = {"run_key": "rk", "saved_at": datetime(2026, 2, 28, tzinfo=timezone.utc)}
    normalized = primitives.normalize_run_summary_payload(payload)
    assert normalized["run_key"] == "rk"
    assert isinstance(normalized["saved_at"], str)


def test_in_memory_sliding_window_limiter_respects_limit_and_window(monkeypatch) -> None:
    limiter = primitives.InMemorySlidingWindowLimiter(default_window_seconds=5)
    now = 1000.0

    monkeypatch.setattr(primitives.time, "time", lambda: now)
    allowed_1, used_1 = limiter.consume("user-1", limit=2)
    allowed_2, used_2 = limiter.consume("user-1", limit=2)
    allowed_3, used_3 = limiter.consume("user-1", limit=2)

    assert (allowed_1, used_1) == (True, 1)
    assert (allowed_2, used_2) == (True, 2)
    assert (allowed_3, used_3) == (False, 2)

    now += 6.0
    allowed_4, used_4 = limiter.consume("user-1", limit=2)
    assert (allowed_4, used_4) == (True, 1)
