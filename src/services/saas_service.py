from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Protocol, Tuple
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import requests


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


class UserSettingsStore(Protocol):
    def get_user_settings(self, *, user_id: str) -> Dict[str, Any]: ...

    def merge_user_settings(
        self,
        *,
        user_id: str,
        tenant_id: str,
        patch: Dict[str, Any],
    ) -> Dict[str, Any]: ...


class RunReportsStore(Protocol):
    def upsert_run_summary(
        self,
        *,
        run_key: str,
        summary: Dict[str, Any],
    ) -> None: ...

    def get_run_summary(
        self,
        *,
        run_key: str,
    ) -> Optional[Dict[str, Any]]: ...

    def list_run_summaries(
        self,
        *,
        limit: int = 300,
    ) -> list[Dict[str, Any]]: ...


class SupabaseStoreRequestError(RuntimeError):
    def __init__(self, *, status_code: int, body: str):
        self.status_code = int(status_code)
        self.body = str(body or "")
        snippet = self.body.strip()[:400]
        super().__init__(
            f"Supabase user_settings request failed [{self.status_code}]: {snippet}"
        )


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


class SupabaseUserSettingsStore:
    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        table_name: str = "user_settings",
        timeout_seconds: float = 8.0,
    ):
        base_url = str(supabase_url or "").strip().rstrip("/")
        api_key = str(service_role_key or "").strip()
        if not base_url:
            raise ValueError("supabase_url is required")
        if not api_key:
            raise ValueError("service_role_key is required")
        safe_table = str(table_name or "user_settings").strip() or "user_settings"
        self._base_url = base_url
        self._table_name = safe_table
        self._endpoint = f"{base_url}/rest/v1/{safe_table}"
        self._run_summaries_endpoint = f"{base_url}/rest/v1/run_summaries"
        self._users_endpoint = f"{base_url}/rest/v1/users"
        self._tenants_endpoint = f"{base_url}/rest/v1/tenants"
        self._api_key = api_key
        self._timeout = max(1.0, float(timeout_seconds))
        self._fallback_mode = False

    def _headers(self, *, prefer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "apikey": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request_json(
        self,
        *,
        method: str,
        params: Optional[Dict[str, str]] = None,
        payload: Optional[Any] = None,
        prefer: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> Any:
        response = requests.request(
            method=str(method or "GET").strip().upper(),
            url=str(endpoint or self._endpoint),
            params=params or None,
            json=payload,
            headers=self._headers(prefer=prefer),
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            raise SupabaseStoreRequestError(
                status_code=response.status_code,
                body=str(response.text or ""),
            )
        text = str(response.text or "").strip()
        if not text:
            return None
        parsed = response.json()
        return parsed

    def _is_missing_primary_table(self, exc: Exception) -> bool:
        if not isinstance(exc, SupabaseStoreRequestError):
            return False
        if int(exc.status_code) != 404:
            return False
        body = str(exc.body or "").lower()
        if "pgrst205" not in body:
            return False
        expected = f"public.{self._table_name.lower()}"
        return expected in body

    def _settings_run_key(self, user_id: str) -> str:
        return f"__user_settings__:{str(user_id or '').strip()}"

    def _coerce_tenant_uuid(self, *, tenant_id: str, user_id: str) -> str:
        normalized = str(tenant_id or "").strip()
        if normalized:
            try:
                return str(UUID(normalized))
            except ValueError:
                pass
        seed = normalized or str(user_id or "").strip()
        return str(uuid5(NAMESPACE_URL, f"tenant:{seed}"))

    def _extract_settings_from_summary(self, summary: Any) -> Dict[str, Any]:
        if isinstance(summary, dict):
            if isinstance(summary.get("settings_json"), dict):
                return normalize_user_settings_payload(summary.get("settings_json"))
            return normalize_user_settings_payload(summary)
        return {}

    def _resolve_existing_tenant_uuid(self, *, user_id: str) -> Optional[str]:
        rows = self._request_json(
            method="GET",
            endpoint=self._users_endpoint,
            params={
                "select": "tenant_id",
                "id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[0] if isinstance(rows[0], dict) else {}
        tenant_id = str(row.get("tenant_id") or "").strip()
        if not tenant_id:
            return None
        try:
            return str(UUID(tenant_id))
        except ValueError:
            return None

    def _ensure_identity(self, *, user_id: str, tenant_id: str) -> str:
        tenant_uuid = self._resolve_existing_tenant_uuid(user_id=user_id)
        if not tenant_uuid:
            tenant_uuid = self._coerce_tenant_uuid(tenant_id=tenant_id, user_id=user_id)
        now = utc_now_iso()

        self._request_json(
            method="POST",
            endpoint=self._tenants_endpoint,
            params={
                "on_conflict": "id",
                "select": "id",
            },
            payload=[
                {
                    "id": tenant_uuid,
                    "owner_user_id": user_id,
                    "name": f"tenant_{user_id[:24]}",
                    "updated_at": now,
                }
            ],
            prefer="resolution=merge-duplicates,return=representation",
        )
        self._request_json(
            method="POST",
            endpoint=self._users_endpoint,
            params={
                "on_conflict": "id",
                "select": "id,tenant_id",
            },
            payload=[
                {
                    "id": user_id,
                    "tenant_id": tenant_uuid,
                    "role": "free",
                    "updated_at": now,
                }
            ],
            prefer="resolution=merge-duplicates,return=representation",
        )
        return tenant_uuid

    def _get_user_settings_run_summary_fallback(
        self, *, user_id: str
    ) -> Dict[str, Any]:
        run_key = self._settings_run_key(user_id)
        rows = self._request_json(
            method="GET",
            endpoint=self._run_summaries_endpoint,
            params={
                "select": "summary",
                "run_key": f"eq.{run_key}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        if not isinstance(rows, list) or not rows:
            return {}
        row = rows[0] if isinstance(rows[0], dict) else {}
        return self._extract_settings_from_summary(row.get("summary"))

    def _upsert_user_settings_run_summary_fallback(
        self,
        *,
        user_id: str,
        tenant_id: str,
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_settings = normalize_user_settings_payload(settings)
        resolved_tenant_id = self._ensure_identity(user_id=user_id, tenant_id=tenant_id)
        run_key = self._settings_run_key(user_id)

        rows = self._request_json(
            method="POST",
            endpoint=self._run_summaries_endpoint,
            params={
                "on_conflict": "run_key",
                "select": "summary",
            },
            payload=[
                {
                    "run_key": run_key,
                    "tenant_id": resolved_tenant_id,
                    "user_id": user_id,
                    "summary": {
                        "settings_json": normalized_settings,
                    },
                    "updated_at": utc_now_iso(),
                }
            ],
            prefer="resolution=merge-duplicates,return=representation",
        )
        if isinstance(rows, list) and rows:
            row = rows[0] if isinstance(rows[0], dict) else {}
            return self._extract_settings_from_summary(row.get("summary"))
        return normalized_settings

    def get_user_settings(self, *, user_id: str) -> Dict[str, Any]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return {}
        if self._fallback_mode:
            return self._get_user_settings_run_summary_fallback(
                user_id=normalized_user_id
            )

        try:
            rows = self._request_json(
                method="GET",
                params={
                    "select": "settings_json",
                    "user_id": f"eq.{normalized_user_id}",
                    "limit": "1",
                },
            )
        except Exception as exc:
            if self._is_missing_primary_table(exc):
                self._fallback_mode = True
                return self._get_user_settings_run_summary_fallback(
                    user_id=normalized_user_id
                )
            raise
        if not isinstance(rows, list) or not rows:
            return {}
        row = rows[0] if isinstance(rows[0], dict) else {}
        return normalize_user_settings_payload(row.get("settings_json") or {})

    def upsert_user_settings(
        self,
        *,
        user_id: str,
        tenant_id: str,
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            raise ValueError("user_id is required")
        normalized_tenant_id = (
            str(tenant_id or "").strip() or f"tenant_{normalized_user_id}"
        )
        normalized_settings = normalize_user_settings_payload(settings)
        if self._fallback_mode:
            return self._upsert_user_settings_run_summary_fallback(
                user_id=normalized_user_id,
                tenant_id=normalized_tenant_id,
                settings=normalized_settings,
            )

        try:
            rows = self._request_json(
                method="POST",
                params={
                    "on_conflict": "user_id",
                    "select": "settings_json",
                },
                payload=[
                    {
                        "user_id": normalized_user_id,
                        "tenant_id": normalized_tenant_id,
                        "settings_json": normalized_settings,
                        "updated_at": utc_now_iso(),
                    }
                ],
                prefer="resolution=merge-duplicates,return=representation",
            )
        except Exception as exc:
            if self._is_missing_primary_table(exc):
                self._fallback_mode = True
                return self._upsert_user_settings_run_summary_fallback(
                    user_id=normalized_user_id,
                    tenant_id=normalized_tenant_id,
                    settings=normalized_settings,
                )
            raise

        if isinstance(rows, list) and rows:
            row = rows[0] if isinstance(rows[0], dict) else {}
            return normalize_user_settings_payload(row.get("settings_json") or {})
        return normalized_settings

    def merge_user_settings(
        self,
        *,
        user_id: str,
        tenant_id: str,
        patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_patch = normalize_user_settings_payload(patch)
        merged = self.get_user_settings(user_id=user_id)
        merged.update(normalized_patch)
        return self.upsert_user_settings(
            user_id=user_id,
            tenant_id=tenant_id,
            settings=merged,
        )


class SupabaseRunReportsStore:
    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        table_name: str = "run_summaries",
        timeout_seconds: float = 8.0,
        default_user_id: str = "backtest-runner",
        default_tenant_id: str = "",
    ):
        base_url = str(supabase_url or "").strip().rstrip("/")
        api_key = str(service_role_key or "").strip()
        if not base_url:
            raise ValueError("supabase_url is required")
        if not api_key:
            raise ValueError("service_role_key is required")
        safe_table = str(table_name or "run_summaries").strip() or "run_summaries"
        safe_user_id = str(default_user_id or "").strip() or "backtest-runner"
        self._base_url = base_url
        self._table_name = safe_table
        self._endpoint = f"{base_url}/rest/v1/{safe_table}"
        self._users_endpoint = f"{base_url}/rest/v1/users"
        self._tenants_endpoint = f"{base_url}/rest/v1/tenants"
        self._api_key = api_key
        self._timeout = max(1.0, float(timeout_seconds))
        self._default_user_id = safe_user_id
        self._default_tenant_id = str(default_tenant_id or "").strip()

    def _headers(self, *, prefer: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "apikey": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request_json(
        self,
        *,
        method: str,
        params: Optional[Dict[str, str]] = None,
        payload: Optional[Any] = None,
        prefer: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> Any:
        response = requests.request(
            method=str(method or "GET").strip().upper(),
            url=str(endpoint or self._endpoint),
            params=params or None,
            json=payload,
            headers=self._headers(prefer=prefer),
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            raise SupabaseStoreRequestError(
                status_code=response.status_code,
                body=str(response.text or ""),
            )
        text = str(response.text or "").strip()
        if not text:
            return None
        parsed = response.json()
        return parsed

    def _coerce_tenant_uuid(self, *, tenant_id: str, user_id: str) -> str:
        normalized = str(tenant_id or "").strip()
        if normalized:
            try:
                return str(UUID(normalized))
            except ValueError:
                pass
        seed = normalized or str(user_id or "").strip()
        return str(uuid5(NAMESPACE_URL, f"tenant:{seed}"))

    def _resolve_existing_tenant_uuid(self, *, user_id: str) -> Optional[str]:
        rows = self._request_json(
            method="GET",
            endpoint=self._users_endpoint,
            params={
                "select": "tenant_id",
                "id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[0] if isinstance(rows[0], dict) else {}
        tenant_id = str(row.get("tenant_id") or "").strip()
        if not tenant_id:
            return None
        try:
            return str(UUID(tenant_id))
        except ValueError:
            return None

    def _ensure_identity(self, *, user_id: str, tenant_id: str) -> str:
        tenant_uuid = self._resolve_existing_tenant_uuid(user_id=user_id)
        if not tenant_uuid:
            tenant_uuid = self._coerce_tenant_uuid(tenant_id=tenant_id, user_id=user_id)
        now = utc_now_iso()

        self._request_json(
            method="POST",
            endpoint=self._tenants_endpoint,
            params={
                "on_conflict": "id",
                "select": "id",
            },
            payload=[
                {
                    "id": tenant_uuid,
                    "owner_user_id": user_id,
                    "name": f"tenant_{user_id[:24]}",
                    "updated_at": now,
                }
            ],
            prefer="resolution=merge-duplicates,return=representation",
        )
        self._request_json(
            method="POST",
            endpoint=self._users_endpoint,
            params={
                "on_conflict": "id",
                "select": "id,tenant_id",
            },
            payload=[
                {
                    "id": user_id,
                    "tenant_id": tenant_uuid,
                    "role": "free",
                    "updated_at": now,
                }
            ],
            prefer="resolution=merge-duplicates,return=representation",
        )
        return tenant_uuid

    def upsert_run_summary(
        self,
        *,
        run_key: str,
        summary: Dict[str, Any],
    ) -> None:
        normalized_run_key = str(run_key or "").strip()
        if not normalized_run_key:
            raise ValueError("run_key is required")
        normalized_summary = normalize_run_summary_payload(summary)
        user_id = self._default_user_id
        tenant_uuid = self._ensure_identity(
            user_id=user_id, tenant_id=self._default_tenant_id
        )
        self._request_json(
            method="POST",
            endpoint=self._endpoint,
            params={
                "on_conflict": "run_key",
                "select": "run_key,updated_at",
            },
            payload=[
                {
                    "run_key": normalized_run_key,
                    "tenant_id": tenant_uuid,
                    "user_id": user_id,
                    "summary": normalized_summary,
                    "updated_at": utc_now_iso(),
                }
            ],
            prefer="resolution=merge-duplicates,return=representation",
        )

    def get_run_summary(
        self,
        *,
        run_key: str,
    ) -> Optional[Dict[str, Any]]:
        normalized_run_key = str(run_key or "").strip()
        if not normalized_run_key:
            return None

        params: Dict[str, str] = {
            "select": "run_key,summary,updated_at",
            "run_key": f"eq.{normalized_run_key}",
            "limit": "1",
        }
        if self._default_user_id:
            params["user_id"] = f"eq.{self._default_user_id}"

        rows = self._request_json(
            method="GET",
            endpoint=self._endpoint,
            params=params,
        )
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[0] if isinstance(rows[0], dict) else {}
        summary_payload = row.get("summary")
        if not isinstance(summary_payload, dict):
            summary_payload = {}
        return {
            "run_key": str(row.get("run_key") or normalized_run_key),
            "summary": summary_payload,
            "updated_at": row.get("updated_at"),
        }

    def list_run_summaries(
        self,
        *,
        limit: int = 300,
    ) -> list[Dict[str, Any]]:
        query_limit = max(1, min(int(limit or 300), 5000))
        params: Dict[str, str] = {
            "select": "run_key,summary,updated_at",
            "order": "updated_at.desc",
            "limit": str(query_limit),
        }
        if self._default_user_id:
            params["user_id"] = f"eq.{self._default_user_id}"
        rows = self._request_json(
            method="GET",
            endpoint=self._endpoint,
            params=params,
        )
        if not isinstance(rows, list):
            return []

        payload_rows: list[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            run_key = str(row.get("run_key") or "").strip()
            summary = row.get("summary")
            if isinstance(summary, dict):
                summary_payload = summary
            else:
                summary_payload = {}
            payload_rows.append(
                {
                    "run_key": run_key,
                    "summary": summary_payload,
                    "updated_at": row.get("updated_at"),
                }
            )
        return payload_rows


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


class SaaSStateStore:
    def __init__(self, db_path: str):
        resolved = Path(str(db_path or "").strip() or "data/saas_state.db")
        self.db_path = resolved if resolved.is_absolute() else (Path.cwd() / resolved)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _table_columns(self, table: str) -> set[str]:
        cur = self._conn.cursor()
        rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row["name"]) for row in rows if row and row["name"]}

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        cols = self._table_columns(table)
        if column in cols:
            return
        cur = self._conn.cursor()
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    email TEXT,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_id TEXT PRIMARY KEY,
                    plan_tier TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    current_period_end TEXT,
                    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                    scheduled_plan_tier TEXT,
                    grace_until TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    settings_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS run_summaries (
                    run_key TEXT PRIMARY KEY,
                    summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS usage_counters_daily (
                    user_id TEXT NOT NULL,
                    day_key TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, day_key, metric)
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    idempotency_key TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 1,
                    payload_json TEXT,
                    result_json TEXT,
                    error TEXT,
                    run_key TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_key TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    date_label TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS webhook_events (
                    event_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    payload_json TEXT,
                    processed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS billing_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT,
                    provider TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    user_id TEXT,
                    previous_plan_tier TEXT,
                    next_plan_tier TEXT,
                    previous_status TEXT,
                    next_status TEXT,
                    note TEXT,
                    payload_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS adaptive_strategy_profiles (
                    profile_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    owner_user_id TEXT,
                    owner_tenant_id TEXT,
                    ticker TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    adaptive_version INTEGER NOT NULL DEFAULT 1,
                    candidate_json TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagnostic_payload_cache (
                    cache_key TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    phase INTEGER NOT NULL,
                    source_path TEXT NOT NULL,
                    source_mtime_ns INTEGER NOT NULL,
                    payload_gzip BLOB NOT NULL,
                    payload_sha256 TEXT NOT NULL,
                    payload_size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_status_created
                    ON jobs(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_user_status
                    ON jobs(user_id, status, created_at);
                CREATE INDEX IF NOT EXISTS idx_user_settings_tenant_updated
                    ON user_settings(tenant_id, updated_at);
                CREATE INDEX IF NOT EXISTS idx_run_summaries_updated
                    ON run_summaries(updated_at);
                CREATE INDEX IF NOT EXISTS idx_billing_audit_user_created
                    ON billing_audit_events(user_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_adaptive_profiles_scope_owner
                    ON adaptive_strategy_profiles(scope, owner_user_id, owner_tenant_id, ticker, updated_at);
                CREATE INDEX IF NOT EXISTS idx_diagnostic_cache_lookup
                    ON diagnostic_payload_cache(ticker, profile, phase, source_mtime_ns);
                """
            )
            self._ensure_column("jobs", "idempotency_key", "TEXT")
            self._ensure_column("jobs", "attempts", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column("jobs", "max_attempts", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(
                "subscriptions", "cancel_at_period_end", "INTEGER NOT NULL DEFAULT 0"
            )
            self._ensure_column("subscriptions", "scheduled_plan_tier", "TEXT")
            self._ensure_column("subscriptions", "grace_until", "TEXT")
            cur.executescript(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_user_type_idempotency
                    ON jobs(user_id, job_type, idempotency_key)
                    WHERE idempotency_key IS NOT NULL;
                """
            )
            self._conn.commit()

    def ensure_identity(
        self,
        *,
        user_id: str,
        tenant_id: str,
        role: str,
        email: Optional[str],
    ) -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO users(user_id, tenant_id, email, role, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    tenant_id=excluded.tenant_id,
                    email=excluded.email,
                    role=excluded.role,
                    updated_at=excluded.updated_at
                """,
                (user_id, tenant_id, email, role, now, now),
            )
            self._conn.commit()

    def get_effective_plan(
        self, *, user_id: str, claim_plan_tier: str, role: str
    ) -> str:
        role_norm = str(role or "").strip().lower()
        if role_norm == "admin":
            return "admin"

        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                """
                SELECT
                    plan_tier,
                    status,
                    current_period_end,
                    cancel_at_period_end,
                    scheduled_plan_tier,
                    grace_until
                FROM subscriptions
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        now = datetime.now(tz=timezone.utc)
        if row:
            plan = str(row["plan_tier"] or "").strip().lower()
            status = str(row["status"] or "").strip().lower()
            period_end = parse_utc_datetime(row["current_period_end"])
            grace_until = parse_utc_datetime(row["grace_until"])
            cancel_at_period_end = bool(int(row["cancel_at_period_end"] or 0))
            scheduled_plan = str(row["scheduled_plan_tier"] or "").strip().lower()
            if scheduled_plan not in PLAN_LIMITS:
                scheduled_plan = "free"

            if status == "active" and plan in PLAN_LIMITS:
                if (
                    cancel_at_period_end
                    and period_end is not None
                    and now >= period_end
                ):
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

        claim = str(claim_plan_tier or "free").strip().lower()
        if claim in PLAN_LIMITS:
            return claim
        return "free"

    def get_subscription(self, *, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT * FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_user(self, *, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT user_id, tenant_id, role, email FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    @staticmethod
    def _normalize_settings_payload(settings: Any) -> Dict[str, Any]:
        return normalize_user_settings_payload(settings)

    def get_user_settings(self, *, user_id: str) -> Dict[str, Any]:
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT settings_json FROM user_settings WHERE user_id = ?",
                (str(user_id),),
            ).fetchone()
        if not row:
            return {}
        return self._decode_json(row["settings_json"])

    def upsert_user_settings(
        self,
        *,
        user_id: str,
        tenant_id: str,
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = self._normalize_settings_payload(settings)
        serialized = json.dumps(normalized, separators=(",", ":"), sort_keys=True)
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO user_settings(user_id, tenant_id, settings_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    tenant_id=excluded.tenant_id,
                    settings_json=excluded.settings_json,
                    updated_at=excluded.updated_at
                """,
                (str(user_id), str(tenant_id), serialized, now, now),
            )
            self._conn.commit()
        return normalized

    def merge_user_settings(
        self,
        *,
        user_id: str,
        tenant_id: str,
        patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_patch = self._normalize_settings_payload(patch)
        merged = self.get_user_settings(user_id=user_id)
        merged.update(normalized_patch)
        return self.upsert_user_settings(
            user_id=user_id,
            tenant_id=tenant_id,
            settings=merged,
        )

    def upsert_run_summary(
        self,
        *,
        run_key: str,
        summary: Dict[str, Any],
    ) -> None:
        normalized_run_key = str(run_key or "").strip()
        if not normalized_run_key:
            raise ValueError("run_key is required")
        normalized_summary = normalize_run_summary_payload(summary)
        serialized = json.dumps(
            normalized_summary, separators=(",", ":"), sort_keys=True
        )
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO run_summaries(run_key, summary_json, created_at, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(run_key) DO UPDATE SET
                    summary_json=excluded.summary_json,
                    updated_at=excluded.updated_at
                """,
                (normalized_run_key, serialized, now, now),
            )
            self._conn.commit()

    def get_run_summary(
        self,
        *,
        run_key: str,
    ) -> Optional[Dict[str, Any]]:
        normalized_run_key = str(run_key or "").strip()
        if not normalized_run_key:
            return None
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                """
                SELECT run_key, summary_json, updated_at
                FROM run_summaries
                WHERE run_key = ?
                LIMIT 1
                """,
                (normalized_run_key,),
            ).fetchone()
        if row is None:
            return None
        return {
            "run_key": str(row["run_key"] or normalized_run_key),
            "summary": self._decode_json(row["summary_json"]),
            "updated_at": row["updated_at"],
        }

    def list_run_summaries(
        self,
        *,
        limit: int = 300,
    ) -> list[Dict[str, Any]]:
        query_limit = max(1, min(int(limit or 300), 5000))
        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(
                """
                SELECT run_key, summary_json, updated_at
                FROM run_summaries
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (query_limit,),
            ).fetchall()

        payload_rows: list[Dict[str, Any]] = []
        for row in rows:
            summary_payload = self._decode_json(row["summary_json"])
            payload_rows.append(
                {
                    "run_key": str(row["run_key"] or ""),
                    "summary": summary_payload,
                    "updated_at": row["updated_at"],
                }
            )
        return payload_rows

    def upsert_subscription(
        self,
        *,
        user_id: str,
        plan_tier: str,
        status: str,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        current_period_end: Optional[str] = None,
        cancel_at_period_end: bool = False,
        scheduled_plan_tier: Optional[str] = None,
        grace_until: Optional[str] = None,
    ) -> None:
        now = utc_now_iso()
        normalized_status = str(status or "active").strip().lower()
        normalized_plan_tier = str(plan_tier or "free").strip().lower()
        normalized_scheduled_plan = (
            str(scheduled_plan_tier or "").strip().lower() or None
        )
        if normalized_scheduled_plan and normalized_scheduled_plan not in PLAN_LIMITS:
            normalized_scheduled_plan = "free"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO subscriptions(
                    user_id,
                    plan_tier,
                    status,
                    stripe_customer_id,
                    stripe_subscription_id,
                    current_period_end,
                    cancel_at_period_end,
                    scheduled_plan_tier,
                    grace_until,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    plan_tier=excluded.plan_tier,
                    status=excluded.status,
                    stripe_customer_id=excluded.stripe_customer_id,
                    stripe_subscription_id=excluded.stripe_subscription_id,
                    current_period_end=excluded.current_period_end,
                    cancel_at_period_end=excluded.cancel_at_period_end,
                    scheduled_plan_tier=excluded.scheduled_plan_tier,
                    grace_until=excluded.grace_until,
                    updated_at=excluded.updated_at
                """,
                (
                    user_id,
                    normalized_plan_tier,
                    normalized_status,
                    stripe_customer_id,
                    stripe_subscription_id,
                    current_period_end,
                    1 if cancel_at_period_end else 0,
                    normalized_scheduled_plan,
                    grace_until,
                    now,
                ),
            )
            self._conn.commit()

    def get_stripe_customer_id(self, *, user_id: str) -> Optional[str]:
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT stripe_customer_id FROM subscriptions WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        value = str(row["stripe_customer_id"] or "").strip()
        return value or None

    def find_user_id_by_stripe_customer(self, customer_id: str) -> Optional[str]:
        needle = str(customer_id or "").strip()
        if not needle:
            return None
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT user_id FROM subscriptions WHERE stripe_customer_id = ?",
                (needle,),
            ).fetchone()
        if not row:
            return None
        value = str(row["user_id"] or "").strip()
        return value or None

    def find_user_id_by_stripe_subscription(
        self, subscription_id: str
    ) -> Optional[str]:
        needle = str(subscription_id or "").strip()
        if not needle:
            return None
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT user_id FROM subscriptions WHERE stripe_subscription_id = ?",
                (needle,),
            ).fetchone()
        if not row:
            return None
        value = str(row["user_id"] or "").strip()
        return value or None

    def increment_usage(
        self,
        *,
        user_id: str,
        metric: str,
        amount: int = 1,
        day_key: Optional[str] = None,
    ) -> int:
        key = str(day_key or utc_day_key()).strip()
        metric_name = str(metric or "").strip().lower()
        increment = max(0, int(amount))
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO usage_counters_daily(user_id, day_key, metric, value, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(user_id, day_key, metric) DO UPDATE SET
                    value = usage_counters_daily.value + excluded.value,
                    updated_at = excluded.updated_at
                """,
                (user_id, key, metric_name, increment, now),
            )
            row = cur.execute(
                "SELECT value FROM usage_counters_daily WHERE user_id = ? AND day_key = ? AND metric = ?",
                (user_id, key, metric_name),
            ).fetchone()
            self._conn.commit()
        return int(row["value"] or 0) if row else 0

    def get_usage_for_day(
        self, *, user_id: str, day_key: Optional[str] = None
    ) -> Dict[str, int]:
        key = str(day_key or utc_day_key()).strip()
        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(
                "SELECT metric, value FROM usage_counters_daily WHERE user_id = ? AND day_key = ?",
                (user_id, key),
            ).fetchall()
        payload: Dict[str, int] = {}
        for row in rows:
            payload[str(row["metric"])] = int(row["value"] or 0)
        return payload

    def prune_user_history(
        self,
        *,
        user_id: str,
        retention_days: int,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, int]:
        horizon_days = max(1, int(retention_days))
        now = (
            now_utc if isinstance(now_utc, datetime) else datetime.now(tz=timezone.utc)
        )
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        cutoff_ts = (now - timedelta(days=horizon_days)).isoformat()
        cutoff_day = (now - timedelta(days=horizon_days)).date().isoformat()

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                DELETE FROM jobs
                WHERE user_id = ?
                  AND lower(status) NOT IN ('queued', 'running')
                  AND updated_at < ?
                """,
                (user_id, cutoff_ts),
            )
            jobs_deleted = int(cur.rowcount or 0)

            cur.execute(
                """
                DELETE FROM runs
                WHERE user_id = ?
                  AND lower(status) NOT IN ('queued', 'running', 'ready', 'active')
                  AND updated_at < ?
                """,
                (user_id, cutoff_ts),
            )
            runs_deleted = int(cur.rowcount or 0)

            cur.execute(
                """
                DELETE FROM usage_counters_daily
                WHERE user_id = ? AND day_key < ?
                """,
                (user_id, cutoff_day),
            )
            usage_deleted = int(cur.rowcount or 0)

            self._conn.commit()

        return {
            "jobs_deleted": jobs_deleted,
            "runs_deleted": runs_deleted,
            "usage_deleted": usage_deleted,
            "retention_days": horizon_days,
            "cutoff_day": cutoff_day,
        }

    def create_job(
        self,
        *,
        job_id: str,
        user_id: str,
        tenant_id: str,
        job_type: str,
        payload: Optional[Dict[str, Any]],
        status: str = "queued",
        idempotency_key: Optional[str] = None,
        max_attempts: int = 1,
    ) -> None:
        now = utc_now_iso()
        normalized_idempotency_key = str(idempotency_key or "").strip() or None
        normalized_max_attempts = max(1, int(max_attempts))
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO jobs(
                    job_id,
                    user_id,
                    tenant_id,
                    job_type,
                    status,
                    idempotency_key,
                    attempts,
                    max_attempts,
                    payload_json,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    user_id,
                    tenant_id,
                    job_type,
                    status,
                    normalized_idempotency_key,
                    0,
                    normalized_max_attempts,
                    json.dumps(payload or {}, separators=(",", ":"), sort_keys=True),
                    now,
                    now,
                ),
            )
            self._conn.commit()

    def begin_job_attempt(self, *, job_id: str) -> Tuple[int, int]:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT attempts, max_attempts FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"Unknown job_id '{job_id}'")
            attempts = max(0, int(row["attempts"] or 0)) + 1
            max_attempts = max(1, int(row["max_attempts"] or 1))
            cur.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    attempts = ?,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (attempts, now, job_id),
            )
            self._conn.commit()
        return attempts, max_attempts

    def update_job(
        self,
        *,
        job_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        run_key: Optional[str] = None,
    ) -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE jobs
                SET status = ?,
                    result_json = ?,
                    error = ?,
                    run_key = COALESCE(?, run_key),
                    updated_at = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    (
                        json.dumps(result or {}, separators=(",", ":"), sort_keys=True)
                        if result is not None
                        else None
                    ),
                    str(error or "").strip() or None,
                    run_key,
                    now,
                    job_id,
                ),
            )
            self._conn.commit()

    def get_job(self, *, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_job_payload(row)

    def get_job_by_idempotency_key(
        self,
        *,
        user_id: str,
        job_type: str,
        idempotency_key: str,
    ) -> Optional[Dict[str, Any]]:
        normalized_key = str(idempotency_key or "").strip()
        if not normalized_key:
            return None
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                """
                SELECT *
                FROM jobs
                WHERE user_id = ? AND job_type = ? AND idempotency_key = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, str(job_type or "").strip(), normalized_key),
            ).fetchone()
        if not row:
            return None
        return self._row_to_job_payload(row)

    def count_active_jobs(
        self, *, user_id: str, job_types: Optional[Iterable[str]] = None
    ) -> int:
        return self.count_jobs(
            user_id=user_id,
            statuses=("queued", "running"),
            job_types=job_types,
        )

    def count_jobs(
        self,
        *,
        statuses: Optional[Iterable[str]] = None,
        job_types: Optional[Iterable[str]] = None,
        user_id: Optional[str] = None,
    ) -> int:
        args: list[Any] = []
        clauses: list[str] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            args.append(str(user_id))

        if statuses:
            normalized_statuses = [
                str(item).strip().lower() for item in statuses if str(item).strip()
            ]
            if normalized_statuses:
                placeholders = ",".join("?" for _ in normalized_statuses)
                clauses.append(f"lower(status) IN ({placeholders})")
                args.extend(normalized_statuses)

        if job_types:
            normalized_types = [
                str(item).strip() for item in job_types if str(item).strip()
            ]
            if normalized_types:
                placeholders = ",".join("?" for _ in normalized_types)
                clauses.append(f"job_type IN ({placeholders})")
                args.extend(normalized_types)

        query = "SELECT COUNT(*) AS c FROM jobs"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(query, tuple(args)).fetchone()
        return int(row["c"] or 0) if row else 0

    def upsert_run(
        self,
        *,
        run_key: str,
        user_id: str,
        tenant_id: str,
        run_id: str,
        ticker: str,
        date_label: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO runs(
                    run_key,
                    user_id,
                    tenant_id,
                    run_id,
                    ticker,
                    date_label,
                    status,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_key) DO UPDATE SET
                    status=excluded.status,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    run_key,
                    user_id,
                    tenant_id,
                    run_id,
                    ticker,
                    date_label,
                    status,
                    json.dumps(metadata or {}, separators=(",", ":"), sort_keys=True),
                    now,
                    now,
                ),
            )
            self._conn.commit()

    def update_run_status(self, *, run_key: str, status: str) -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE run_key = ?",
                (status, now, run_key),
            )
            self._conn.commit()

    def count_active_runs(self, *, user_id: str) -> int:
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM runs
                WHERE user_id = ? AND status IN ('queued','running','ready','active')
                """,
                (user_id,),
            ).fetchone()
        return int(row["c"] or 0) if row else 0

    def list_run_keys_by_user(
        self, *, user_id: str, statuses: Iterable[str]
    ) -> list[str]:
        normalized = [
            str(item).strip().lower() for item in statuses if str(item).strip()
        ]
        if not normalized:
            return []
        placeholders = ",".join("?" for _ in normalized)
        args = [user_id, *normalized]
        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(
                f"SELECT run_key FROM runs WHERE user_id = ? AND lower(status) IN ({placeholders})",
                tuple(args),
            ).fetchall()
        return [str(row["run_key"]) for row in rows if row and row["run_key"]]

    def mark_webhook_event_processed(
        self,
        *,
        provider: str,
        event_id: str,
        payload: Dict[str, Any],
    ) -> bool:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT event_id FROM webhook_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row:
                return False
            cur.execute(
                """
                INSERT INTO webhook_events(event_id, provider, payload_json, processed_at)
                VALUES(?, ?, ?, ?)
                """,
                (
                    event_id,
                    str(provider or "stripe").strip().lower(),
                    json.dumps(payload or {}, separators=(",", ":"), sort_keys=True),
                    now,
                ),
            )
            self._conn.commit()
        return True

    def record_billing_audit_event(
        self,
        *,
        provider: str,
        event_id: Optional[str],
        event_type: str,
        user_id: Optional[str],
        previous_plan_tier: Optional[str],
        next_plan_tier: Optional[str],
        previous_status: Optional[str],
        next_status: Optional[str],
        note: Optional[str],
        payload: Optional[Dict[str, Any]],
    ) -> None:
        now = utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO billing_audit_events(
                    event_id,
                    provider,
                    event_type,
                    user_id,
                    previous_plan_tier,
                    next_plan_tier,
                    previous_status,
                    next_status,
                    note,
                    payload_json,
                    created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event_id or "").strip() or None,
                    str(provider or "stripe").strip().lower(),
                    str(event_type or "").strip().lower() or "unknown",
                    str(user_id or "").strip() or None,
                    str(previous_plan_tier or "").strip().lower() or None,
                    str(next_plan_tier or "").strip().lower() or None,
                    str(previous_status or "").strip().lower() or None,
                    str(next_status or "").strip().lower() or None,
                    str(note or "").strip() or None,
                    json.dumps(payload or {}, separators=(",", ":"), sort_keys=True),
                    now,
                ),
            )
            self._conn.commit()

    @staticmethod
    def diagnostic_cache_key(*, ticker: str, profile: str, phase: int) -> str:
        return f"{str(ticker or '').strip().upper()}:{str(profile or '').strip().lower()}:{int(phase)}"

    @staticmethod
    def _normalize_profile_scope(scope: str) -> str:
        normalized = str(scope or "").strip().lower()
        if normalized not in {"user", "global"}:
            raise ValueError("scope must be 'user' or 'global'")
        return normalized

    def upsert_adaptive_strategy_profile(
        self,
        *,
        profile_id: Optional[str],
        scope: str,
        owner_user_id: Optional[str],
        owner_tenant_id: Optional[str],
        ticker: str,
        profile_name: str,
        adaptive_version: int,
        candidate: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        normalized_scope = self._normalize_profile_scope(scope)
        normalized_ticker = str(ticker or "").strip().upper()
        normalized_name = str(profile_name or "").strip()
        normalized_id = str(profile_id or "").strip() or f"asp_{uuid4().hex[:16]}"
        normalized_version = max(1, int(adaptive_version or 1))

        if not normalized_ticker:
            raise ValueError("ticker is required")
        if not normalized_name:
            raise ValueError("profile_name is required")

        if normalized_scope == "global":
            normalized_owner_user = None
            normalized_owner_tenant = None
        else:
            normalized_owner_user = str(owner_user_id or "").strip()
            normalized_owner_tenant = str(owner_tenant_id or "").strip()
            if not normalized_owner_user or not normalized_owner_tenant:
                raise ValueError(
                    "user scope profile requires owner_user_id and owner_tenant_id"
                )

        now = utc_now_iso()
        candidate_payload = candidate if isinstance(candidate, dict) else {}
        metadata_payload = metadata if isinstance(metadata, dict) else {}

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO adaptive_strategy_profiles(
                    profile_id,
                    scope,
                    owner_user_id,
                    owner_tenant_id,
                    ticker,
                    profile_name,
                    adaptive_version,
                    candidate_json,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    scope=excluded.scope,
                    owner_user_id=excluded.owner_user_id,
                    owner_tenant_id=excluded.owner_tenant_id,
                    ticker=excluded.ticker,
                    profile_name=excluded.profile_name,
                    adaptive_version=excluded.adaptive_version,
                    candidate_json=excluded.candidate_json,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    normalized_id,
                    normalized_scope,
                    normalized_owner_user,
                    normalized_owner_tenant,
                    normalized_ticker,
                    normalized_name,
                    normalized_version,
                    json.dumps(
                        candidate_payload, separators=(",", ":"), sort_keys=True
                    ),
                    json.dumps(metadata_payload, separators=(",", ":"), sort_keys=True),
                    now,
                    now,
                ),
            )
            self._conn.commit()

        result = self.get_adaptive_strategy_profile(profile_id=normalized_id)
        if not result:
            raise RuntimeError("Failed to load saved adaptive strategy profile")
        return result

    def get_adaptive_strategy_profile(
        self, *, profile_id: str
    ) -> Optional[Dict[str, Any]]:
        key = str(profile_id or "").strip()
        if not key:
            return None
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT * FROM adaptive_strategy_profiles WHERE profile_id = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_adaptive_profile_payload(row)

    def list_adaptive_strategy_profiles(
        self,
        *,
        user_id: str,
        tenant_id: str,
        ticker: Optional[str] = None,
        include_user: bool = True,
        include_global: bool = True,
    ) -> list[Dict[str, Any]]:
        visibility_clauses: list[str] = []
        args: list[Any] = []
        normalized_user = str(user_id or "").strip()
        normalized_tenant = str(tenant_id or "").strip()

        if include_user and normalized_user and normalized_tenant:
            visibility_clauses.append(
                "(scope = 'user' AND owner_user_id = ? AND owner_tenant_id = ?)"
            )
            args.extend([normalized_user, normalized_tenant])
        if include_global:
            visibility_clauses.append("(scope = 'global')")
        if not visibility_clauses:
            return []

        clauses = ["(" + " OR ".join(visibility_clauses) + ")"]
        if ticker:
            clauses.append("ticker = ?")
            args.append(str(ticker).strip().upper())

        query = "SELECT * FROM adaptive_strategy_profiles WHERE " + " AND ".join(
            clauses
        )
        query += " ORDER BY CASE WHEN scope = 'global' THEN 0 ELSE 1 END, updated_at DESC, profile_id ASC"

        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(query, tuple(args)).fetchall()

        return [self._row_to_adaptive_profile_payload(row) for row in rows]

    def delete_adaptive_strategy_profile(self, *, profile_id: str) -> bool:
        key = str(profile_id or "").strip()
        if not key:
            return False
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "DELETE FROM adaptive_strategy_profiles WHERE profile_id = ?",
                (key,),
            )
            deleted = int(cur.rowcount or 0)
            self._conn.commit()
        return deleted > 0

    def upsert_diagnostic_payload_cache(
        self,
        *,
        cache_key: str,
        ticker: str,
        profile: str,
        phase: int,
        source_path: str,
        source_mtime_ns: int,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        key = str(cache_key or "").strip()
        if not key:
            raise ValueError("cache_key is required")
        serialized = json.dumps(
            payload if isinstance(payload, dict) else {},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        compressed = gzip.compress(serialized, compresslevel=6)
        checksum = hashlib.sha256(serialized).hexdigest()
        now = utc_now_iso()

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO diagnostic_payload_cache(
                    cache_key,
                    ticker,
                    profile,
                    phase,
                    source_path,
                    source_mtime_ns,
                    payload_gzip,
                    payload_sha256,
                    payload_size_bytes,
                    created_at,
                    updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    ticker=excluded.ticker,
                    profile=excluded.profile,
                    phase=excluded.phase,
                    source_path=excluded.source_path,
                    source_mtime_ns=excluded.source_mtime_ns,
                    payload_gzip=excluded.payload_gzip,
                    payload_sha256=excluded.payload_sha256,
                    payload_size_bytes=excluded.payload_size_bytes,
                    updated_at=excluded.updated_at
                """,
                (
                    key,
                    str(ticker or "").strip().upper(),
                    str(profile or "").strip().lower(),
                    int(phase),
                    str(source_path or "").strip(),
                    int(source_mtime_ns),
                    compressed,
                    checksum,
                    int(len(serialized)),
                    now,
                    now,
                ),
            )
            self._conn.commit()

        return {
            "cache_key": key,
            "payload_sha256": checksum,
            "payload_size_bytes": int(len(serialized)),
            "compressed_size_bytes": int(len(compressed)),
        }

    def get_diagnostic_payload_cache(
        self,
        *,
        cache_key: str,
        source_path: str,
        source_mtime_ns: int,
    ) -> Optional[Dict[str, Any]]:
        key = str(cache_key or "").strip()
        if not key:
            return None
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                """
                SELECT payload_gzip
                FROM diagnostic_payload_cache
                WHERE cache_key = ? AND source_path = ? AND source_mtime_ns = ?
                """,
                (
                    key,
                    str(source_path or "").strip(),
                    int(source_mtime_ns),
                ),
            ).fetchone()
        if not row:
            return None

        raw_blob = row["payload_gzip"]
        if raw_blob is None:
            return None
        try:
            compressed = bytes(raw_blob)
            decoded = gzip.decompress(compressed).decode("utf-8")
            parsed = json.loads(decoded)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _decode_json(raw: Optional[str]) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _row_to_job_payload(self, row: sqlite3.Row) -> Dict[str, Any]:
        payload = dict(row)
        payload["payload"] = self._decode_json(payload.pop("payload_json", None))
        payload["result"] = self._decode_json(payload.pop("result_json", None))
        return payload

    def _row_to_adaptive_profile_payload(self, row: sqlite3.Row) -> Dict[str, Any]:
        payload = dict(row)
        payload["candidate"] = self._decode_json(payload.pop("candidate_json", None))
        payload["metadata"] = self._decode_json(payload.pop("metadata_json", None))
        payload["adaptive_version"] = max(1, int(payload.get("adaptive_version") or 1))
        payload["scope"] = str(payload.get("scope") or "user").strip().lower()
        return payload


@dataclass
class V2Services:
    store: SaaSStateStore
    limiter: InMemorySlidingWindowLimiter
    internal_strategy_api_url: str
    ads_enabled: bool
    ads_provider: str
    ads_placements: list[str]
    user_settings_store: Optional[UserSettingsStore] = None
    job_semaphore: Any = None
    max_queue_backlog: int = 200
    default_job_max_attempts: int = 2
    job_retry_base_seconds: float = 0.75
    job_retry_max_delay_seconds: float = 8.0
    active_dispatch_job_ids: set[str] = field(default_factory=set)
    dispatch_lock: Any = None
    retention_cleanup_markers: Dict[str, str] = field(default_factory=dict)
