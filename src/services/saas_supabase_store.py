from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import NAMESPACE_URL, UUID, uuid5

import requests

from src.services.saas_primitives import (
    normalize_run_summary_payload,
    normalize_user_settings_payload,
    utc_now_iso,
)


class SupabaseStoreRequestError(RuntimeError):
    def __init__(self, *, status_code: int, body: str):
        self.status_code = int(status_code)
        self.body = str(body or "")
        snippet = self.body.strip()[:400]
        super().__init__(
            f"Supabase user_settings request failed [{self.status_code}]: {snippet}"
        )


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


__all__ = [
    "SupabaseRunReportsStore",
    "SupabaseStoreRequestError",
    "SupabaseUserSettingsStore",
]
