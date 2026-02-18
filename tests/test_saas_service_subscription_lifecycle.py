from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.services.saas_service import SaaSStateStore


def _iso_offset(*, days: int) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).replace(microsecond=0).isoformat()


def test_subscription_active_cancel_at_period_end_stays_premium_until_period_end(tmp_path):
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))
    user_id = "user-sub-1"
    store.upsert_subscription(
        user_id=user_id,
        plan_tier="premium",
        status="active",
        current_period_end=_iso_offset(days=2),
        cancel_at_period_end=True,
        scheduled_plan_tier="free",
    )

    effective = store.get_effective_plan(user_id=user_id, claim_plan_tier="free", role="free")
    assert effective == "premium"


def test_subscription_active_cancel_at_period_end_downgrades_after_period_end(tmp_path):
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))
    user_id = "user-sub-2"
    store.upsert_subscription(
        user_id=user_id,
        plan_tier="premium",
        status="active",
        current_period_end=_iso_offset(days=-1),
        cancel_at_period_end=True,
        scheduled_plan_tier="free",
    )

    effective = store.get_effective_plan(user_id=user_id, claim_plan_tier="free", role="free")
    assert effective == "free"


def test_subscription_grace_window_keeps_premium_until_grace_expires(tmp_path):
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))
    user_id = "user-sub-3"
    store.upsert_subscription(
        user_id=user_id,
        plan_tier="premium",
        status="grace",
        grace_until=_iso_offset(days=1),
    )
    assert store.get_effective_plan(user_id=user_id, claim_plan_tier="free", role="free") == "premium"

    store.upsert_subscription(
        user_id=user_id,
        plan_tier="premium",
        status="grace",
        grace_until=_iso_offset(days=-1),
    )
    assert store.get_effective_plan(user_id=user_id, claim_plan_tier="free", role="free") == "free"

