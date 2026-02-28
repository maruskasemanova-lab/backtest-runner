from __future__ import annotations

import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Protocol, Tuple

from src.services.saas_adaptive_profile_utils import (
    build_adaptive_strategy_profile_record,
    build_list_adaptive_strategy_profiles_query,
    normalize_profile_scope as normalize_adaptive_profile_scope,
)
from src.services.saas_primitives import (
    InMemorySlidingWindowLimiter,
    PlanLimits,
    PLAN_LIMITS,
    normalize_run_summary_payload,
    normalize_user_settings_payload,
    resolve_plan_limits,
    utc_day_key,
    utc_now_iso,
)
from src.services.saas_plan_resolution_utils import resolve_effective_plan
from src.services.saas_payload_utils import (
    build_diagnostic_payload_blob as payload_build_diagnostic_payload_blob,
    decode_diagnostic_payload_blob as payload_decode_diagnostic_payload_blob,
    decode_json_object as payload_decode_json_object,
    json_dumps_compact as payload_json_dumps_compact,
    row_to_adaptive_profile_payload as payload_row_to_adaptive_profile_payload,
    row_to_job_payload as payload_row_to_job_payload,
)
from src.services.saas_query_utils import (
    build_jobs_count_query,
    build_run_keys_by_user_query,
)
from src.services.saas_supabase_store import (
    SupabaseRunReportsStore,
    SupabaseStoreRequestError,
    SupabaseUserSettingsStore,
)


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

        return resolve_effective_plan(
            role=role,
            claim_plan_tier=claim_plan_tier,
            subscription=dict(row) if row else None,
        )

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
        serialized = payload_json_dumps_compact(normalized)
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
        serialized = payload_json_dumps_compact(normalized_summary)
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
                    payload_json_dumps_compact(payload or {}),
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
                        payload_json_dumps_compact(result or {})
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
        query, args = build_jobs_count_query(
            statuses=statuses,
            job_types=job_types,
            user_id=user_id,
        )

        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(query, args).fetchone()
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
                    payload_json_dumps_compact(metadata or {}),
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
        query_payload = build_run_keys_by_user_query(
            user_id=user_id,
            statuses=statuses,
        )
        if query_payload is None:
            return []
        query, args = query_payload
        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(query, args).fetchall()
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
                    payload_json_dumps_compact(payload or {}),
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
                    payload_json_dumps_compact(payload or {}),
                    now,
                ),
            )
            self._conn.commit()

    @staticmethod
    def diagnostic_cache_key(*, ticker: str, profile: str, phase: int) -> str:
        return f"{str(ticker or '').strip().upper()}:{str(profile or '').strip().lower()}:{int(phase)}"

    @staticmethod
    def _normalize_profile_scope(scope: str) -> str:
        return normalize_adaptive_profile_scope(scope)

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
        record = build_adaptive_strategy_profile_record(
            profile_id=profile_id,
            scope=scope,
            owner_user_id=owner_user_id,
            owner_tenant_id=owner_tenant_id,
            ticker=ticker,
            profile_name=profile_name,
            adaptive_version=adaptive_version,
            candidate=candidate,
            metadata=metadata,
        )
        now = utc_now_iso()

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
                    record["profile_id"],
                    record["scope"],
                    record["owner_user_id"],
                    record["owner_tenant_id"],
                    record["ticker"],
                    record["profile_name"],
                    record["adaptive_version"],
                    payload_json_dumps_compact(record["candidate"]),
                    payload_json_dumps_compact(record["metadata"]),
                    now,
                    now,
                ),
            )
            self._conn.commit()

        result = self.get_adaptive_strategy_profile(profile_id=record["profile_id"])
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
        query_payload = build_list_adaptive_strategy_profiles_query(
            user_id=user_id,
            tenant_id=tenant_id,
            ticker=ticker,
            include_user=include_user,
            include_global=include_global,
        )
        if query_payload is None:
            return []
        query, args = query_payload

        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(query, args).fetchall()

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
        compressed, checksum, payload_size_bytes, compressed_size_bytes = (
            payload_build_diagnostic_payload_blob(payload)
        )
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
                    payload_size_bytes,
                    now,
                    now,
                ),
            )
            self._conn.commit()

        return {
            "cache_key": key,
            "payload_sha256": checksum,
            "payload_size_bytes": payload_size_bytes,
            "compressed_size_bytes": compressed_size_bytes,
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

        return payload_decode_diagnostic_payload_blob(row["payload_gzip"])

    @staticmethod
    def _decode_json(raw: Optional[str]) -> Dict[str, Any]:
        return payload_decode_json_object(raw)

    def _row_to_job_payload(self, row: sqlite3.Row) -> Dict[str, Any]:
        return payload_row_to_job_payload(dict(row))

    def _row_to_adaptive_profile_payload(self, row: sqlite3.Row) -> Dict[str, Any]:
        return payload_row_to_adaptive_profile_payload(dict(row))


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


__all__ = [
    "RunReportsStore",
    "SaaSStateStore",
    "SupabaseRunReportsStore",
    "SupabaseStoreRequestError",
    "SupabaseUserSettingsStore",
    "UserSettingsStore",
    "V2Services",
    "resolve_plan_limits",
]
