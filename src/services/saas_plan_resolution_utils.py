from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from src.services.saas_primitives import PLAN_LIMITS, parse_utc_datetime


def _coerce_aware_utc(now_utc: Optional[datetime] = None) -> datetime:
    now = now_utc if isinstance(now_utc, datetime) else datetime.now(tz=timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _normalize_claim_plan_tier(claim_plan_tier: str) -> str:
    claim = str(claim_plan_tier or "free").strip().lower()
    if claim in PLAN_LIMITS:
        return claim
    return "free"


def _normalize_scheduled_plan_tier(raw_value: Any) -> str:
    normalized = str(raw_value or "").strip().lower()
    if normalized in PLAN_LIMITS:
        return normalized
    return "free"


def _coerce_cancel_at_period_end(raw_value: Any) -> bool:
    try:
        return bool(int(raw_value or 0))
    except Exception:
        return bool(raw_value)


def resolve_effective_plan(
    *,
    role: str,
    claim_plan_tier: str,
    subscription: Optional[Mapping[str, Any]],
    now_utc: Optional[datetime] = None,
) -> str:
    role_norm = str(role or "").strip().lower()
    if role_norm == "admin":
        return "admin"

    now = _coerce_aware_utc(now_utc)
    row = dict(subscription or {})
    if row:
        plan = str(row.get("plan_tier") or "").strip().lower()
        status = str(row.get("status") or "").strip().lower()
        period_end = parse_utc_datetime(row.get("current_period_end"))
        grace_until = parse_utc_datetime(row.get("grace_until"))
        cancel_at_period_end = _coerce_cancel_at_period_end(
            row.get("cancel_at_period_end")
        )
        scheduled_plan = _normalize_scheduled_plan_tier(row.get("scheduled_plan_tier"))

        if status == "active" and plan in PLAN_LIMITS:
            if cancel_at_period_end and period_end is not None and now >= period_end:
                return scheduled_plan
            return plan

        if status in {"grace", "past_due", "incomplete"} and plan in PLAN_LIMITS:
            if grace_until is not None and now < grace_until:
                return plan
            if period_end is not None and now < period_end:
                return plan

        if status in {"canceled", "paused"}:
            if plan == "premium" and period_end is not None and now < period_end:
                return "premium"
            return scheduled_plan or "free"

    return _normalize_claim_plan_tier(claim_plan_tier)
