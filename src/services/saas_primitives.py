from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class PlanLimits:
    plan_tier: str
    concurrent_runs: int
    max_range_days: int
    req_per_min: int
    retention_days: int
    ads_enabled: bool


FREE_LIMITS = PlanLimits(
    plan_tier="free",
    concurrent_runs=1,
    max_range_days=5,
    req_per_min=30,
    retention_days=7,
    ads_enabled=True,
)

PREMIUM_LIMITS = PlanLimits(
    plan_tier="premium",
    concurrent_runs=5,
    max_range_days=60,
    req_per_min=300,
    retention_days=180,
    ads_enabled=False,
)

ADMIN_LIMITS = PlanLimits(
    plan_tier="admin",
    concurrent_runs=20,
    max_range_days=365,
    req_per_min=2000,
    retention_days=365,
    ads_enabled=False,
)

PLAN_LIMITS: Dict[str, PlanLimits] = {
    "free": FREE_LIMITS,
    "premium": PREMIUM_LIMITS,
    "admin": ADMIN_LIMITS,
}
MAX_USER_SETTINGS_BYTES = 262_144


def resolve_plan_limits(plan_tier: str) -> PlanLimits:
    normalized = str(plan_tier or "free").strip().lower()
    return PLAN_LIMITS.get(normalized, FREE_LIMITS)


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def utc_day_key(day: Optional[date] = None) -> str:
    if isinstance(day, date):
        return day.isoformat()
    return datetime.now(tz=timezone.utc).date().isoformat()


def parse_utc_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            as_float = float(raw)
        except Exception:
            return None
        try:
            return datetime.fromtimestamp(as_float, tz=timezone.utc)
        except Exception:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_user_settings_payload(settings: Any) -> Dict[str, Any]:
    if settings is None:
        return {}
    if not isinstance(settings, dict):
        raise ValueError("settings must be a JSON object")
    try:
        serialized = json.dumps(settings, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("settings must be JSON-serializable") from exc
    if len(serialized.encode("utf-8")) > MAX_USER_SETTINGS_BYTES:
        raise ValueError(f"settings payload exceeds {MAX_USER_SETTINGS_BYTES} bytes")
    parsed = json.loads(serialized)
    if not isinstance(parsed, dict):
        raise ValueError("settings must be a JSON object")
    return parsed


def normalize_run_summary_payload(summary: Any) -> Dict[str, Any]:
    if summary is None:
        return {}
    if not isinstance(summary, dict):
        raise ValueError("run summary must be a JSON object")
    try:
        serialized = json.dumps(summary, separators=(",", ":"), default=str)
    except (TypeError, ValueError) as exc:
        raise ValueError("run summary must be JSON-serializable") from exc
    parsed = json.loads(serialized)
    if not isinstance(parsed, dict):
        raise ValueError("run summary must be a JSON object")
    return parsed


class InMemorySlidingWindowLimiter:
    def __init__(self, *, default_window_seconds: int = 60):
        self.default_window_seconds = max(1, int(default_window_seconds))
        self._events: Dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def consume(
        self, key: str, *, limit: int, window_seconds: Optional[int] = None
    ) -> Tuple[bool, int]:
        max_allowed = max(1, int(limit))
        window = max(1, int(window_seconds or self.default_window_seconds))
        now = time.time()
        floor = now - window

        with self._lock:
            bucket = self._events.get(key, [])
            bucket = [ts for ts in bucket if ts >= floor]
            if len(bucket) >= max_allowed:
                self._events[key] = bucket
                return False, len(bucket)
            bucket.append(now)
            self._events[key] = bucket
            return True, len(bucket)
