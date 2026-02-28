from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.services.saas_plan_resolution_utils import resolve_effective_plan


def _now() -> datetime:
    return datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)


def test_resolve_effective_plan_admin_role_short_circuit() -> None:
    effective = resolve_effective_plan(
        role="admin",
        claim_plan_tier="free",
        subscription=None,
        now_utc=_now(),
    )
    assert effective == "admin"


def test_resolve_effective_plan_active_cancel_after_period_end_uses_scheduled() -> None:
    effective = resolve_effective_plan(
        role="free",
        claim_plan_tier="free",
        subscription={
            "plan_tier": "premium",
            "status": "active",
            "current_period_end": (_now() - timedelta(days=1)).isoformat(),
            "cancel_at_period_end": 1,
            "scheduled_plan_tier": "free",
        },
        now_utc=_now(),
    )
    assert effective == "free"


def test_resolve_effective_plan_active_before_period_end_keeps_plan() -> None:
    effective = resolve_effective_plan(
        role="free",
        claim_plan_tier="free",
        subscription={
            "plan_tier": "premium",
            "status": "active",
            "current_period_end": (_now() + timedelta(days=1)).isoformat(),
            "cancel_at_period_end": 1,
            "scheduled_plan_tier": "free",
        },
        now_utc=_now(),
    )
    assert effective == "premium"


def test_resolve_effective_plan_grace_uses_grace_until_or_period_end() -> None:
    by_grace_until = resolve_effective_plan(
        role="free",
        claim_plan_tier="free",
        subscription={
            "plan_tier": "premium",
            "status": "grace",
            "grace_until": (_now() + timedelta(hours=2)).isoformat(),
            "current_period_end": (_now() - timedelta(days=2)).isoformat(),
        },
        now_utc=_now(),
    )
    assert by_grace_until == "premium"

    by_period_end = resolve_effective_plan(
        role="free",
        claim_plan_tier="free",
        subscription={
            "plan_tier": "premium",
            "status": "past_due",
            "grace_until": (_now() - timedelta(hours=1)).isoformat(),
            "current_period_end": (_now() + timedelta(hours=1)).isoformat(),
        },
        now_utc=_now(),
    )
    assert by_period_end == "premium"


def test_resolve_effective_plan_canceled_premium_until_period_end() -> None:
    still_premium = resolve_effective_plan(
        role="free",
        claim_plan_tier="free",
        subscription={
            "plan_tier": "premium",
            "status": "canceled",
            "current_period_end": (_now() + timedelta(days=1)).isoformat(),
            "scheduled_plan_tier": "free",
        },
        now_utc=_now(),
    )
    assert still_premium == "premium"

    downgraded = resolve_effective_plan(
        role="free",
        claim_plan_tier="free",
        subscription={
            "plan_tier": "premium",
            "status": "canceled",
            "current_period_end": (_now() - timedelta(days=1)).isoformat(),
            "scheduled_plan_tier": "starter",
        },
        now_utc=_now(),
    )
    assert downgraded == "free"


def test_resolve_effective_plan_falls_back_to_claim_when_subscription_missing() -> None:
    assert (
        resolve_effective_plan(
            role="free",
            claim_plan_tier="premium",
            subscription=None,
            now_utc=_now(),
        )
        == "premium"
    )
    assert (
        resolve_effective_plan(
            role="free",
            claim_plan_tier="unknown",
            subscription=None,
            now_utc=_now(),
        )
        == "free"
    )
