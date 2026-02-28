from __future__ import annotations

from uuid import UUID

from src.services.saas_service import (
    SaaSStateStore,
    SupabaseRunReportsStore,
    SupabaseRunStateMirror,
    SupabaseUserSettingsStore,
)


class _StubResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = int(status_code)
        self._payload = payload
        self.text = "" if payload is None else __import__("json").dumps(payload)

    def json(self):
        return self._payload


def _eq(params, key: str) -> str:
    raw = str((params or {}).get(key) or "")
    if raw.startswith("eq."):
        return raw[3:]
    return raw


def test_supabase_user_settings_store_fallback_to_run_summaries(monkeypatch):
    state = {
        "user_settings_exists": False,
        "tenants": {},
        "users": {},
        "run_summaries": {},
    }

    def _fake_request(
        method, url, params=None, json=None, headers=None, timeout=None, **kwargs
    ):
        method = str(method or "").upper()
        path = str(url or "")
        _ = headers, timeout, kwargs

        if path.endswith("/user_settings"):
            if not state["user_settings_exists"]:
                return _StubResponse(
                    404,
                    {
                        "code": "PGRST205",
                        "message": "Could not find the table 'public.user_settings' in the schema cache",
                    },
                )
            user_id = _eq(params, "user_id")
            if method == "GET":
                row = state["run_summaries"].get(f"direct:{user_id}")
                return _StubResponse(
                    200, [{"settings_json": row}] if row is not None else []
                )
            if method == "POST":
                row = (json or [{}])[0]
                state["run_summaries"][f"direct:{row['user_id']}"] = (
                    row.get("settings_json") or {}
                )
                return _StubResponse(
                    201, [{"settings_json": row.get("settings_json") or {}}]
                )

        if path.endswith("/users"):
            if method == "GET":
                user_id = _eq(params, "id")
                row = state["users"].get(user_id)
                return _StubResponse(
                    200, [{"tenant_id": row["tenant_id"]}] if row else []
                )
            if method == "POST":
                rows = []
                for row in json or []:
                    user_id = str(row.get("id") or "").strip()
                    merged = dict(state["users"].get(user_id) or {})
                    merged.update(row or {})
                    state["users"][user_id] = merged
                    rows.append({"id": user_id, "tenant_id": merged.get("tenant_id")})
                return _StubResponse(201, rows)

        if path.endswith("/tenants"):
            if method == "POST":
                rows = []
                for row in json or []:
                    tenant_id = str(row.get("id") or "").strip()
                    merged = dict(state["tenants"].get(tenant_id) or {})
                    merged.update(row or {})
                    state["tenants"][tenant_id] = merged
                    rows.append({"id": tenant_id})
                return _StubResponse(201, rows)

        if path.endswith("/run_summaries"):
            if method == "GET":
                run_key = _eq(params, "run_key")
                row = state["run_summaries"].get(run_key)
                return _StubResponse(
                    200, [{"summary": row.get("summary")}] if row else []
                )
            if method == "POST":
                rows = []
                for row in json or []:
                    run_key = str(row.get("run_key") or "").strip()
                    state["run_summaries"][run_key] = dict(row or {})
                    rows.append({"summary": dict(row.get("summary") or {})})
                return _StubResponse(201, rows)

        raise AssertionError(
            f"Unexpected request: {method} {url} params={params} json={json}"
        )

    monkeypatch.setattr(
        "src.services.saas_supabase_store.requests.request",
        _fake_request,
    )

    store = SupabaseUserSettingsStore(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role-key",
        table_name="user_settings",
    )

    assert store.get_user_settings(user_id="user-a") == {}
    merged = store.merge_user_settings(
        user_id="user-a",
        tenant_id="tenant_user-a",
        patch={"run_config_draft": {"ticker": "MU"}},
    )
    assert merged == {"run_config_draft": {"ticker": "MU"}}
    assert store.get_user_settings(user_id="user-a") == {
        "run_config_draft": {"ticker": "MU"}
    }

    created_user = state["users"]["user-a"]
    assert created_user["tenant_id"]
    UUID(created_user["tenant_id"])


def test_supabase_user_settings_store_primary_table(monkeypatch):
    state = {"user_settings": {}}

    def _fake_request(
        method, url, params=None, json=None, headers=None, timeout=None, **kwargs
    ):
        method = str(method or "").upper()
        _ = headers, timeout, kwargs
        if not str(url).endswith("/user_settings"):
            raise AssertionError(f"Unexpected URL {url}")

        if method == "GET":
            user_id = _eq(params, "user_id")
            settings = state["user_settings"].get(user_id)
            return _StubResponse(
                200, [{"settings_json": settings}] if settings is not None else []
            )

        if method == "POST":
            row = (json or [{}])[0]
            user_id = str(row.get("user_id") or "").strip()
            settings_json = dict(row.get("settings_json") or {})
            state["user_settings"][user_id] = settings_json
            return _StubResponse(201, [{"settings_json": settings_json}])

        raise AssertionError(f"Unexpected method {method}")

    monkeypatch.setattr(
        "src.services.saas_supabase_store.requests.request",
        _fake_request,
    )

    store = SupabaseUserSettingsStore(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role-key",
        table_name="user_settings",
    )

    assert store.get_user_settings(user_id="user-b") == {}
    out = store.merge_user_settings(
        user_id="user-b",
        tenant_id="tenant_user-b",
        patch={"sidebar_mode": "profiles"},
    )
    assert out == {"sidebar_mode": "profiles"}
    assert store.get_user_settings(user_id="user-b") == {"sidebar_mode": "profiles"}


def test_supabase_run_reports_store_upsert_and_list(monkeypatch):
    state = {
        "tenants": {},
        "users": {},
        "run_summaries": {},
    }

    def _fake_request(
        method, url, params=None, json=None, headers=None, timeout=None, **kwargs
    ):
        method = str(method or "").upper()
        path = str(url or "")
        _ = headers, timeout, kwargs

        if path.endswith("/users"):
            if method == "GET":
                user_id = _eq(params, "id")
                row = state["users"].get(user_id)
                return _StubResponse(
                    200, [{"tenant_id": row["tenant_id"]}] if row else []
                )
            if method == "POST":
                rows = []
                for row in json or []:
                    user_id = str(row.get("id") or "").strip()
                    merged = dict(state["users"].get(user_id) or {})
                    merged.update(row or {})
                    state["users"][user_id] = merged
                    rows.append({"id": user_id, "tenant_id": merged.get("tenant_id")})
                return _StubResponse(201, rows)

        if path.endswith("/tenants"):
            if method == "POST":
                rows = []
                for row in json or []:
                    tenant_id = str(row.get("id") or "").strip()
                    merged = dict(state["tenants"].get(tenant_id) or {})
                    merged.update(row or {})
                    state["tenants"][tenant_id] = merged
                    rows.append({"id": tenant_id})
                return _StubResponse(201, rows)

        if path.endswith("/run_summaries"):
            if method == "POST":
                rows = []
                for row in json or []:
                    run_key = str(row.get("run_key") or "").strip()
                    state["run_summaries"][run_key] = dict(row or {})
                    rows.append(
                        {"run_key": run_key, "updated_at": row.get("updated_at")}
                    )
                return _StubResponse(201, rows)
            if method == "GET":
                user_id = _eq(params, "user_id")
                rows = [
                    {
                        "run_key": run_key,
                        "summary": row.get("summary") if isinstance(row, dict) else {},
                        "updated_at": (
                            row.get("updated_at") if isinstance(row, dict) else None
                        ),
                    }
                    for run_key, row in state["run_summaries"].items()
                    if not user_id or str((row or {}).get("user_id") or "") == user_id
                ]
                return _StubResponse(200, rows)

        raise AssertionError(
            f"Unexpected request: {method} {url} params={params} json={json}"
        )

    monkeypatch.setattr(
        "src.services.saas_supabase_store.requests.request",
        _fake_request,
    )

    store = SupabaseRunReportsStore(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role-key",
        table_name="run_summaries",
        default_user_id="runner-user",
    )

    store.upsert_run_summary(
        run_key="run-1:MU:2026-02-03",
        summary={
            "run_id": "run-1",
            "ticker": "MU",
            "session_summary": {"total_trades": 1},
        },
    )

    rows = store.list_run_summaries(limit=25)
    assert len(rows) == 1
    assert rows[0]["run_key"] == "run-1:MU:2026-02-03"
    assert rows[0]["summary"]["run_id"] == "run-1"
    assert rows[0]["summary"]["ticker"] == "MU"
    single = store.get_run_summary(run_key="run-1:MU:2026-02-03")
    assert single is not None
    assert single["run_key"] == "run-1:MU:2026-02-03"
    assert single["summary"]["run_id"] == "run-1"

    created_user = state["users"]["runner-user"]
    assert created_user["tenant_id"]
    UUID(created_user["tenant_id"])


def test_supabase_run_state_mirror_upserts_job_and_run(monkeypatch):
    state = {
        "tenants": {},
        "users": {},
        "run_jobs": {},
        "runs": {},
    }

    def _fake_request(
        method, url, params=None, json=None, headers=None, timeout=None, **kwargs
    ):
        method = str(method or "").upper()
        path = str(url or "")
        _ = headers, timeout, kwargs

        if path.endswith("/users"):
            if method == "GET":
                user_id = _eq(params, "id")
                row = state["users"].get(user_id)
                return _StubResponse(
                    200, [{"tenant_id": row["tenant_id"]}] if row else []
                )
            if method == "POST":
                rows = []
                for row in json or []:
                    user_id = str(row.get("id") or "").strip()
                    merged = dict(state["users"].get(user_id) or {})
                    merged.update(row or {})
                    state["users"][user_id] = merged
                    rows.append({"id": user_id, "tenant_id": merged.get("tenant_id")})
                return _StubResponse(201, rows)

        if path.endswith("/tenants"):
            if method == "POST":
                rows = []
                for row in json or []:
                    tenant_id = str(row.get("id") or "").strip()
                    merged = dict(state["tenants"].get(tenant_id) or {})
                    merged.update(row or {})
                    state["tenants"][tenant_id] = merged
                    rows.append({"id": tenant_id})
                return _StubResponse(201, rows)

        if path.endswith("/run_jobs"):
            if method == "POST":
                rows = []
                for row in json or []:
                    job_id = str(row.get("id") or "").strip()
                    merged = dict(state["run_jobs"].get(job_id) or {})
                    merged.update(row or {})
                    state["run_jobs"][job_id] = merged
                    rows.append({"id": job_id, "updated_at": merged.get("updated_at")})
                return _StubResponse(201, rows)

        if path.endswith("/runs"):
            if method == "POST":
                rows = []
                for row in json or []:
                    run_key = str(row.get("run_key") or "").strip()
                    merged = dict(state["runs"].get(run_key) or {})
                    merged.update(row or {})
                    state["runs"][run_key] = merged
                    rows.append(
                        {"run_key": run_key, "updated_at": merged.get("updated_at")}
                    )
                return _StubResponse(201, rows)
            if method == "PATCH":
                run_key = _eq(params, "run_key")
                merged = dict(state["runs"].get(run_key) or {})
                merged.update(json or {})
                state["runs"][run_key] = merged
                return _StubResponse(
                    200, [{"run_key": run_key, "updated_at": merged.get("updated_at")}]
                )

        raise AssertionError(
            f"Unexpected request: {method} {url} params={params} json={json}"
        )

    monkeypatch.setattr(
        "src.services.saas_supabase_store.requests.request",
        _fake_request,
    )

    mirror = SupabaseRunStateMirror(
        supabase_url="https://example.supabase.co",
        service_role_key="service-role-key",
    )

    mirror.upsert_job_record(
        job={
            "job_id": "job-1",
            "user_id": "user-c",
            "tenant_id": "tenant_user-c",
            "job_type": "run",
            "status": "queued",
            "payload": {"request": {"ticker": "MU"}},
            "attempts": 0,
            "max_attempts": 2,
            "idempotency_key": "idem-1",
            "created_at": "2026-02-28T12:00:00Z",
            "updated_at": "2026-02-28T12:00:00Z",
        }
    )
    mirror.upsert_run_record(
        run_key="run-1:MU:2026-02-28",
        user_id="user-c",
        tenant_id="tenant_user-c",
        run_id="run-1",
        ticker="MU",
        date_label="2026-02-28",
        status="queued",
        metadata={"job_id": "job-1"},
    )
    mirror.update_run_status(run_key="run-1:MU:2026-02-28", status="running")

    created_user = state["users"]["user-c"]
    assert created_user["tenant_id"]
    UUID(created_user["tenant_id"])

    job_row = state["run_jobs"]["job-1"]
    assert job_row["idempotency_key"] == "idem-1"
    assert job_row["attempts"] == 0
    assert job_row["max_attempts"] == 2
    assert job_row["payload"]["request"]["ticker"] == "MU"

    run_row = state["runs"]["run-1:MU:2026-02-28"]
    assert run_row["status"] == "running"
    assert run_row["metadata"]["job_id"] == "job-1"


def test_sqlite_run_reports_store_upsert_and_list(tmp_path):
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))
    store.upsert_run_summary(
        run_key="run-2:MU:2026-02-12",
        summary={
            "run_id": "run-2",
            "ticker": "MU",
            "session_summary": {"total_trades": 3},
        },
    )
    store.upsert_run_summary(
        run_key="run-2:MU:2026-02-12",
        summary={
            "run_id": "run-2",
            "ticker": "MU",
            "session_summary": {"total_trades": 4},
        },
    )

    rows = store.list_run_summaries(limit=10)
    assert len(rows) == 1
    assert rows[0]["run_key"] == "run-2:MU:2026-02-12"
    assert rows[0]["summary"]["run_id"] == "run-2"
    assert rows[0]["summary"]["session_summary"]["total_trades"] == 4
    single = store.get_run_summary(run_key="run-2:MU:2026-02-12")
    assert single is not None
    assert single["run_key"] == "run-2:MU:2026-02-12"
    assert single["summary"]["session_summary"]["total_trades"] == 4
