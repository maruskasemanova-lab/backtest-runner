from __future__ import annotations

import base64
import hashlib
import hmac
import json
from pathlib import Path
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.parquet_compat import read_parquet_compat, write_parquet_compat
from src.routes.v2_routes import _request_prefers_local_user_datasets, router
from src.services.saas_service import (
    InMemorySlidingWindowLimiter,
    SaaSStateStore,
    V2Services,
)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _make_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    part_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    part_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signed = f"{part_header}.{part_payload}".encode("utf-8")
    sig = _b64url(hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest())
    return f"{part_header}.{part_payload}.{sig}"


def _build_client(
    tmp_path,
    *,
    internal_strategy_url: str = "http://internal-strategy:8001",
    start_run_impl=None,
    max_queue_backlog: int = 200,
    user_settings_store=None,
    user_datasets_store=None,
    run_state_mirror=None,
):
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))
    limiter = InMemorySlidingWindowLimiter(default_window_seconds=60)

    called_urls = []
    called_data_files = []
    called_tuner_urls = []
    called_download_tickers = []

    async def _start_run(request):
        called_urls.append(request.strategy_api_url)
        called_data_files.append(request.data_file)
        if callable(start_run_impl):
            return await start_run_impl(request)
        date_label = request.date or f"{request.date_from}_to_{request.date_to}"
        return {
            "run_key": f"{request.run_id}:{request.ticker}:{date_label}",
            "status": "ok",
        }

    async def _run_tuner(request):
        called_tuner_urls.append(request.strategy_api_url)
        return {"status": "ok", "internal_job_id": "inner-job-1"}

    async def _run_download(request):
        called_download_tickers.append(str(request.ticker).upper())
        return {"status": "completed"}

    app = FastAPI()
    app.include_router(router)
    app.state.v2_services = V2Services(
        store=store,
        limiter=limiter,
        internal_strategy_api_url=internal_strategy_url,
        ads_enabled=True,
        ads_provider="test",
        ads_placements=["dashboard"],
        user_settings_store=user_settings_store,
        user_datasets_store=user_datasets_store,
        run_state_mirror=run_state_mirror,
        max_queue_backlog=max_queue_backlog,
        job_retry_base_seconds=0.01,
        job_retry_max_delay_seconds=0.02,
    )
    app.state.api_services = SimpleNamespace(
        start_run=_start_run,
        v2_run_adaptive_tuner=_run_tuner,
        v2_run_download=_run_download,
        active_runners={},
    )
    return TestClient(app), {
        "run_urls": called_urls,
        "run_data_files": called_data_files,
        "tuner_urls": called_tuner_urls,
        "download_tickers": called_download_tickers,
        "store": store,
    }


def test_v2_auth_requires_bearer_token(tmp_path):
    client, _calls = _build_client(tmp_path)
    response = client.get("/api/v2/auth/me")
    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["code"] == "unauthorized"


def test_v2_auth_me_returns_context(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "user-1",
            "email": "user1@example.com",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    response = client.get(
        "/api/v2/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "user-1"
    assert payload["plan_tier"] == "free"
    assert payload["tenant_id"] == "tenant_user-1"


def test_v2_run_non_admin_forces_internal_strategy_url(tmp_path, monkeypatch):
    client, calls = _build_client(
        tmp_path, internal_strategy_url="http://internal:8001"
    )
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "user-2",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "r1",
            "ticker": "MU",
            "date": "2026-02-03",
            "strategy_api_url": "http://evil.internal:9999",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    job_id = payload["job_id"]

    # Poll until background task writes result.
    for _ in range(30):
        polled = client.get(
            f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert polled.status_code == 200
        state = polled.json()["job"]["status"]
        if state in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert calls["run_urls"], "run job should invoke start_run"
    assert calls["run_urls"][0] == "http://internal:8001"


def test_v2_run_free_plan_enforces_date_range_limit(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "user-3",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "r2",
            "ticker": "MU",
            "date_from": "2026-01-01",
            "date_to": "2026-01-15",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 402
    payload = response.json()
    assert payload["detail"]["code"] == "plan_limit_exceeded"


def test_v2_adaptive_tuner_forces_internal_strategy_url(tmp_path, monkeypatch):
    client, calls = _build_client(
        tmp_path, internal_strategy_url="http://internal:8001"
    )
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "user-4",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.post(
        "/api/v2/adaptive-tuner/run",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ticker": "MU",
            "date_from": "2026-02-01",
            "date_to": "2026-02-03",
            "strategy_api_url": "http://evil.internal:9999",
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    for _ in range(20):
        polled = client.get(
            f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert polled.status_code == 200
        if polled.json()["job"]["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert calls["tuner_urls"]
    assert calls["tuner_urls"][0] == "http://internal:8001"


def test_v2_download_respects_free_range_limit(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "user-5",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.post(
        "/api/v2/data/download",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ticker": "MU",
            "data_schema": "mbp-10",
            "start_date": "2026-01-01",
            "end_date": "2026-01-20",
            "dataset": "XNAS.ITCH",
            "convert_to_parquet": True,
        },
    )
    assert response.status_code == 402
    payload = response.json()
    assert payload["detail"]["code"] == "plan_limit_exceeded"


def test_v2_run_idempotency_key_reuses_existing_job(tmp_path, monkeypatch):
    client, calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "user-6",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "run-user-6-001",
    }
    body = {
        "run_id": "r3",
        "ticker": "MU",
        "date": "2026-02-03",
        "strategy_api_url": "http://localhost:8001",
    }

    first = client.post("/api/v2/runs", headers=headers, json=body)
    assert first.status_code == 200
    first_job = first.json()["job_id"]

    second = client.post("/api/v2/runs", headers=headers, json=body)
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["job_id"] == first_job
    assert second_payload["idempotent_replay"] is True

    for _ in range(30):
        polled = client.get(
            f"/api/v2/jobs/{first_job}", headers={"Authorization": f"Bearer {token}"}
        )
        assert polled.status_code == 200
        if polled.json()["job"]["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert len(calls["run_urls"]) == 1


def test_v2_run_retries_transient_failure(tmp_path, monkeypatch):
    attempts = {"count": 0}

    async def _flaky_start_run(request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise HTTPException(status_code=503, detail="temporary upstream error")
        date_label = request.date or f"{request.date_from}_to_{request.date_to}"
        return {
            "run_key": f"{request.run_id}:{request.ticker}:{date_label}",
            "status": "ok",
        }

    client, calls = _build_client(tmp_path, start_run_impl=_flaky_start_run)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_V2_JOB_MAX_ATTEMPTS_RUN", "2")

    token = _make_jwt(
        {
            "sub": "user-7",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "premium", "plan_tier": "premium"},
        },
        "test-secret",
    )
    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "r4",
            "ticker": "MU",
            "date": "2026-02-03",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    final_payload = None
    for _ in range(80):
        polled = client.get(
            f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert polled.status_code == 200
        final_payload = polled.json()["job"]
        if final_payload["status"] in {"completed", "failed"}:
            break
        time.sleep(0.03)

    assert final_payload is not None
    assert final_payload["status"] == "completed"
    assert final_payload["attempts"] == 2
    assert len(calls["run_urls"]) == 2


def test_v2_run_mirrors_job_and_run_state_updates(tmp_path, monkeypatch):
    class _StubRunStateMirror:
        def __init__(self):
            self.job_records = []
            self.run_records = []
            self.run_status_updates = []

        def upsert_job_record(self, *, job):
            self.job_records.append(dict(job))

        def upsert_run_record(self, **kwargs):
            self.run_records.append(dict(kwargs))

        def update_run_status(self, *, run_key: str, status: str):
            self.run_status_updates.append({"run_key": run_key, "status": status})

    mirror = _StubRunStateMirror()
    client, _calls = _build_client(tmp_path, run_state_mirror=mirror)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "user-mirror",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "mirror-run",
            "ticker": "MU",
            "date": "2026-02-03",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    run_key = response.json()["run_key"]

    for _ in range(40):
        polled = client.get(
            f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert polled.status_code == 200
        if polled.json()["job"]["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    job_statuses = [str(row.get("status") or "") for row in mirror.job_records]
    assert job_statuses
    assert job_statuses[0] == "queued"
    assert "running" in job_statuses
    assert job_statuses[-1] == "completed"

    run_statuses = [str(row.get("status") or "") for row in mirror.run_records]
    assert "queued" in run_statuses
    assert "ready" in run_statuses
    assert {"run_key": run_key, "status": "running"} in mirror.run_status_updates


def test_v2_run_with_dataset_id_uses_local_dataset_parquet(tmp_path, monkeypatch):
    client, calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv(
        "BACKTEST_USER_DATASETS_LOCAL_CACHE_DIR",
        str(tmp_path / "user_dataset_cache"),
    )

    store = calls["store"]
    dataset_id = "ds_run_1"
    local_path = tmp_path / "user_dataset_cache" / "run-user-1" / f"{dataset_id}.parquet"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    write_parquet_compat(
        pd.DataFrame(
            [
                {
                    "timestamp": "2026-02-03T14:30:00Z",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.5,
                    "close": 100.5,
                    "volume": 1000,
                }
            ]
        ),
        local_path,
        index=False,
    )
    store.upsert_user_dataset(
        dataset_id=dataset_id,
        user_id="run-user-1",
        tenant_id="tenant_run-user-1",
        dataset_name="Backtest Dataset",
        source_filename="bars.csv",
        s3_path="users/run-user-1/datasets/ds_run_1.parquet",
        status="ready",
        file_format="parquet",
        source_format="csv",
        row_count=1,
        size_bytes=int(local_path.stat().st_size),
        schema_name="ohlcv",
        metadata={"ingest": {"local_cache_path": str(local_path)}},
    )

    token = _make_jwt(
        {
            "sub": "run-user-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "dataset-run",
            "ticker": "MU",
            "date": "2026-02-03",
            "dataset_id": dataset_id,
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 200
    assert response.json()["dataset_id"] == dataset_id
    job_id = response.json()["job_id"]

    for _ in range(30):
        polled = client.get(
            f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert polled.status_code == 200
        if polled.json()["job"]["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert calls["run_data_files"]
    assert calls["run_data_files"][0] == str(local_path.resolve())


def test_v2_run_with_dataset_id_requires_local_dataset_file(tmp_path, monkeypatch):
    client, calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv(
        "BACKTEST_USER_DATASETS_LOCAL_CACHE_DIR",
        str(tmp_path / "user_dataset_cache"),
    )

    calls["store"].upsert_user_dataset(
        dataset_id="ds_missing_local",
        user_id="run-user-2",
        tenant_id="tenant_run-user-2",
        dataset_name="Missing Local Cache",
        source_filename="bars.csv",
        s3_path="users/run-user-2/datasets/ds_missing_local.parquet",
        status="ready",
        file_format="parquet",
        source_format="csv",
        row_count=1,
        size_bytes=123,
        schema_name="ohlcv",
        metadata={},
    )

    token = _make_jwt(
        {
            "sub": "run-user-2",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "dataset-run-missing",
            "ticker": "MU",
            "date": "2026-02-03",
            "dataset_id": "ds_missing_local",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "dataset_data_unavailable"


def test_v2_run_with_dataset_id_hydrates_from_s3_when_local_cache_missing(
    tmp_path, monkeypatch
):
    client, calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_USER_DATASETS_STORAGE_MODE", "remote")
    monkeypatch.setenv(
        "BACKTEST_USER_DATASETS_LOCAL_CACHE_DIR",
        str(tmp_path / "user_dataset_cache"),
    )

    remote_source = tmp_path / "remote_dataset.parquet"
    write_parquet_compat(
        pd.DataFrame(
            [
                {
                    "timestamp": "2026-02-03T14:30:00Z",
                    "open": 200.0,
                    "high": 201.0,
                    "low": 199.5,
                    "close": 200.5,
                    "volume": 1500,
                }
            ]
        ),
        remote_source,
        index=False,
    )
    remote_bytes = remote_source.read_bytes()

    class _StubBody:
        def __init__(self, payload: bytes):
            self._payload = payload
            self._offset = 0

        def read(self, size: int = -1):
            if size is None or size < 0:
                size = len(self._payload) - self._offset
            if self._offset >= len(self._payload):
                return b""
            chunk = self._payload[self._offset : self._offset + size]
            self._offset += len(chunk)
            return chunk

    class _StubS3Client:
        def __init__(self):
            self.calls = []

        def get_object(self, *, Bucket: str, Key: str):
            self.calls.append((Bucket, Key))
            return {"Body": _StubBody(remote_bytes)}

    stub_client = _StubS3Client()
    monkeypatch.setattr(
        "src.routes.v2_routes._build_user_dataset_s3_client",
        lambda: stub_client,
    )

    calls["store"].upsert_user_dataset(
        dataset_id="ds_remote_hydrate",
        user_id="run-user-3",
        tenant_id="tenant_run-user-3",
        dataset_name="Remote Hydrated Dataset",
        source_filename="bars.csv",
        s3_path="s3://datasets-bucket/users/run-user-3/datasets/ds_remote_hydrate.parquet",
        status="ready",
        file_format="parquet",
        source_format="csv",
        row_count=1,
        size_bytes=len(remote_bytes),
        schema_name="ohlcv",
        metadata={},
    )

    token = _make_jwt(
        {
            "sub": "run-user-3",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "dataset-run-remote",
            "ticker": "MU",
            "date": "2026-02-03",
            "dataset_id": "ds_remote_hydrate",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 200

    job_id = response.json()["job_id"]
    for _ in range(30):
        polled = client.get(
            f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert polled.status_code == 200
        if polled.json()["job"]["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert stub_client.calls == [
        ("datasets-bucket", "users/run-user-3/datasets/ds_remote_hydrate.parquet")
    ]
    assert calls["run_data_files"]
    hydrated_path = Path(calls["run_data_files"][0])
    assert hydrated_path.exists()
    frame = read_parquet_compat(hydrated_path)
    assert len(frame.index) == 1

    dataset_row = calls["store"].get_user_dataset(dataset_id="ds_remote_hydrate")
    assert dataset_row is not None
    ingest_meta = dataset_row["metadata"]["ingest"]
    assert ingest_meta["storage_mode"] == "s3"
    assert ingest_meta["local_cache_path"] == str(hydrated_path)


def test_v2_run_with_dataset_id_hydrates_from_http_when_remote_mode_enabled(
    tmp_path, monkeypatch
):
    client, calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_USER_DATASETS_STORAGE_MODE", "remote")
    monkeypatch.setenv(
        "BACKTEST_USER_DATASETS_LOCAL_CACHE_DIR",
        str(tmp_path / "user_dataset_cache"),
    )

    remote_source = tmp_path / "remote_http_dataset.parquet"
    write_parquet_compat(
        pd.DataFrame(
            [
                {
                    "timestamp": "2026-02-03T14:30:00Z",
                    "open": 300.0,
                    "high": 301.0,
                    "low": 299.5,
                    "close": 300.5,
                    "volume": 1700,
                }
            ]
        ),
        remote_source,
        index=False,
    )
    remote_bytes = remote_source.read_bytes()

    class _StubResponse:
        def __init__(self, payload: bytes):
            self._payload = payload

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=1024 * 1024):
            for start in range(0, len(self._payload), chunk_size):
                yield self._payload[start : start + chunk_size]

    def _fake_get(url, stream=False, timeout=None, **kwargs):
        _ = stream, timeout, kwargs
        assert (
            url
            == "https://cdn.example.com/users/run-user-4/datasets/ds_remote_http.parquet"
        )
        return _StubResponse(remote_bytes)

    monkeypatch.setattr("src.routes.v2_routes.requests.get", _fake_get)

    calls["store"].upsert_user_dataset(
        dataset_id="ds_remote_http",
        user_id="run-user-4",
        tenant_id="tenant_run-user-4",
        dataset_name="Remote HTTP Dataset",
        source_filename="bars.csv",
        s3_path="https://cdn.example.com/users/run-user-4/datasets/ds_remote_http.parquet",
        status="ready",
        file_format="parquet",
        source_format="csv",
        row_count=1,
        size_bytes=len(remote_bytes),
        schema_name="ohlcv",
        metadata={},
    )

    token = _make_jwt(
        {
            "sub": "run-user-4",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "dataset-run-http",
            "ticker": "MU",
            "date": "2026-02-03",
            "dataset_id": "ds_remote_http",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 200

    job_id = response.json()["job_id"]
    for _ in range(30):
        polled = client.get(
            f"/api/v2/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert polled.status_code == 200
        if polled.json()["job"]["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert calls["run_data_files"]
    hydrated_path = Path(calls["run_data_files"][0])
    assert hydrated_path.exists()
    frame = read_parquet_compat(hydrated_path)
    assert len(frame.index) == 1


def test_v2_backlog_limit_blocks_new_heavy_jobs(tmp_path, monkeypatch):
    client, calls = _build_client(tmp_path, max_queue_backlog=1)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    # Saturate global heavy queue with one queued job.
    calls["store"].create_job(
        job_id="job_seed",
        user_id="seed-user",
        tenant_id="tenant_seed-user",
        job_type="run",
        payload={"request": {}},
        status="queued",
    )

    token = _make_jwt(
        {
            "sub": "user-8",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "r5",
            "ticker": "MU",
            "date": "2026-02-03",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 429
    payload = response.json()
    assert payload["detail"]["code"] == "queue_backlog_exceeded"


def test_v2_billing_subscription_cancel_at_period_end_lifecycle(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "billing-user-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    in_grace_payload = {
        "id": "evt_sub_updated_future",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "active",
                "cancel_at_period_end": True,
                "current_period_end": int(time.time()) + 3600,
                "metadata": {"user_id": "billing-user-1"},
            }
        },
    }
    response = client.post("/api/v2/billing/webhook/stripe", json=in_grace_payload)
    assert response.status_code == 200
    assert response.json()["handled"] is True

    usage_resp = client.get(
        "/api/v2/usage", headers={"Authorization": f"Bearer {token}"}
    )
    assert usage_resp.status_code == 200
    assert usage_resp.json()["plan_tier"] == "premium"

    expired_payload = {
        "id": "evt_sub_updated_past",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_123",
                "customer": "cus_123",
                "status": "active",
                "cancel_at_period_end": True,
                "current_period_end": int(time.time()) - 60,
                "metadata": {"user_id": "billing-user-1"},
            }
        },
    }
    response_expired = client.post(
        "/api/v2/billing/webhook/stripe", json=expired_payload
    )
    assert response_expired.status_code == 200

    usage_after = client.get(
        "/api/v2/usage", headers={"Authorization": f"Bearer {token}"}
    )
    assert usage_after.status_code == 200
    assert usage_after.json()["plan_tier"] == "free"


def test_v2_billing_invoice_payment_failed_sets_grace(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_BILLING_GRACE_DAYS", "3")

    token = _make_jwt(
        {
            "sub": "billing-user-2",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    payload = {
        "id": "evt_invoice_failed_1",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_123",
                "subscription": "sub_456",
                "customer": "cus_456",
                "current_period_end": int(time.time()) + 1200,
                "metadata": {"user_id": "billing-user-2"},
            }
        },
    }
    response = client.post("/api/v2/billing/webhook/stripe", json=payload)
    assert response.status_code == 200
    assert response.json()["handled"] is True

    usage_resp = client.get(
        "/api/v2/usage", headers={"Authorization": f"Bearer {token}"}
    )
    assert usage_resp.status_code == 200
    assert usage_resp.json()["plan_tier"] == "premium"


def test_v2_invite_only_blocks_non_allowlisted_user(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_INVITE_ONLY_BETA", "1")
    monkeypatch.delenv("BACKTEST_INVITE_ALLOWLIST_USERS", raising=False)
    monkeypatch.delenv("BACKTEST_INVITE_ALLOWLIST_TENANTS", raising=False)
    monkeypatch.delenv("BACKTEST_INVITE_ALLOWLIST_EMAILS", raising=False)

    token = _make_jwt(
        {
            "sub": "non-invited-user",
            "email": "non-invited@example.com",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    response = client.get(
        "/api/v2/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "invite_only_beta"


def test_v2_invite_only_allows_allowlisted_user(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_INVITE_ONLY_BETA", "1")
    monkeypatch.setenv("BACKTEST_INVITE_ALLOWLIST_USERS", "allowed-user-1")

    token = _make_jwt(
        {
            "sub": "allowed-user-1",
            "email": "allowed@example.com",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    response = client.get(
        "/api/v2/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == "allowed-user-1"


def test_v2_heavy_ops_kill_switch_blocks_non_admin_run(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_V2_HEAVY_OPS_ENABLED", "0")

    token = _make_jwt(
        {
            "sub": "user-heavy-disabled",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "run-disabled-1",
            "ticker": "MU",
            "date": "2026-02-03",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "heavy_ops_disabled"


def test_v2_heavy_ops_kill_switch_allows_admin(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_V2_HEAVY_OPS_ENABLED", "0")

    token = _make_jwt(
        {
            "sub": "admin-heavy-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "admin", "plan_tier": "admin"},
        },
        "test-secret",
    )
    response = client.post(
        "/api/v2/runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "run_id": "run-admin-bypass-1",
            "ticker": "MU",
            "date": "2026-02-03",
            "strategy_api_url": "http://localhost:8001",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_v2_ops_metrics_requires_admin(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "free-metrics-user",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )

    response = client.get(
        "/api/v2/ops/metrics", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"


def test_v2_ops_metrics_returns_queue_runtime_and_storage(tmp_path, monkeypatch):
    client, calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    class _StubMetrics:
        def snapshot(self):
            return {
                "http_requests_total": 42,
                "http_latency_ms": {"p50": 11.0, "p95": 28.0},
            }

    client.app.state.runtime_metrics = _StubMetrics()
    client.app.state.connected_clients = [object(), object(), object()]
    client.app.state.max_ws_clients = 12

    store = calls["store"]
    store.create_job(
        job_id="ops-queued-1",
        user_id="u1",
        tenant_id="tenant_u1",
        job_type="run",
        payload={"request": {}},
        status="queued",
    )
    store.create_job(
        job_id="ops-running-1",
        user_id="u1",
        tenant_id="tenant_u1",
        job_type="adaptive_tuner",
        payload={"request": {}},
        status="running",
    )
    store.create_job(
        job_id="ops-failed-1",
        user_id="u1",
        tenant_id="tenant_u1",
        job_type="download",
        payload={"request": {}},
        status="failed",
    )
    store.create_job(
        job_id="ops-completed-1",
        user_id="u1",
        tenant_id="tenant_u1",
        job_type="run",
        payload={"request": {}},
        status="completed",
    )

    token = _make_jwt(
        {
            "sub": "admin-metrics-user",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "admin", "plan_tier": "admin"},
        },
        "test-secret",
    )
    response = client.get(
        "/api/v2/ops/metrics", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["queue"]["queued_heavy_jobs"] == 1
    assert payload["queue"]["running_heavy_jobs"] == 1
    assert payload["queue"]["completed_heavy_jobs"] == 1
    assert payload["queue"]["failed_heavy_jobs"] == 1
    assert payload["queue"]["heavy_fail_rate"] == 0.5
    assert payload["websocket"]["active_clients"] == 3
    assert payload["runtime"]["http_requests_total"] == 42
    assert payload["storage"]["saas_db_exists"] is True
    assert payload["storage"]["saas_db_size_bytes"] > 0


def test_v2_usage_retention_cleanup_prunes_old_terminal_records(tmp_path, monkeypatch):
    client, calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    store = calls["store"]
    user_id = "retention-user-1"
    tenant_id = f"tenant_{user_id}"
    old_ts = (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()

    store.create_job(
        job_id="job_ret_old_terminal",
        user_id=user_id,
        tenant_id=tenant_id,
        job_type="run",
        payload={"request": {}},
        status="completed",
    )
    store.create_job(
        job_id="job_ret_new_terminal",
        user_id=user_id,
        tenant_id=tenant_id,
        job_type="run",
        payload={"request": {}},
        status="completed",
    )
    store.upsert_run(
        run_key="ret-run-old:MU:2026-01-01",
        user_id=user_id,
        tenant_id=tenant_id,
        run_id="ret-run-old",
        ticker="MU",
        date_label="2026-01-01",
        status="completed",
        metadata={},
    )
    store.upsert_run(
        run_key="ret-run-new:MU:2026-01-02",
        user_id=user_id,
        tenant_id=tenant_id,
        run_id="ret-run-new",
        ticker="MU",
        date_label="2026-01-02",
        status="completed",
        metadata={},
    )
    old_usage_day = (
        (datetime.now(tz=timezone.utc) - timedelta(days=10)).date().isoformat()
    )
    store.increment_usage(user_id=user_id, metric="api_requests", day_key=old_usage_day)

    with store._lock:
        cur = store._conn.cursor()
        cur.execute(
            "UPDATE jobs SET created_at = ?, updated_at = ? WHERE job_id = ?",
            (old_ts, old_ts, "job_ret_old_terminal"),
        )
        cur.execute(
            "UPDATE runs SET created_at = ?, updated_at = ? WHERE run_key = ?",
            (old_ts, old_ts, "ret-run-old:MU:2026-01-01"),
        )
        store._conn.commit()

    token = _make_jwt(
        {
            "sub": user_id,
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    response = client.get("/api/v2/usage", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    with store._lock:
        cur = store._conn.cursor()
        jobs = {
            str(row["job_id"])
            for row in cur.execute(
                "SELECT job_id FROM jobs WHERE user_id = ?", (user_id,)
            ).fetchall()
        }
        runs = {
            str(row["run_key"])
            for row in cur.execute(
                "SELECT run_key FROM runs WHERE user_id = ?", (user_id,)
            ).fetchall()
        }
        usage_days = {
            str(row["day_key"])
            for row in cur.execute(
                "SELECT day_key FROM usage_counters_daily WHERE user_id = ?", (user_id,)
            ).fetchall()
        }

    assert "job_ret_old_terminal" not in jobs
    assert "job_ret_new_terminal" in jobs
    assert "ret-run-old:MU:2026-01-01" not in runs
    assert "ret-run-new:MU:2026-01-02" in runs
    assert old_usage_day not in usage_days


def test_v2_usage_retention_cleanup_keeps_old_active_records(tmp_path, monkeypatch):
    client, calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    store = calls["store"]
    user_id = "retention-user-2"
    tenant_id = f"tenant_{user_id}"
    old_ts = (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()

    store.create_job(
        job_id="job_ret_old_queued",
        user_id=user_id,
        tenant_id=tenant_id,
        job_type="run",
        payload={"request": {}},
        status="queued",
    )
    store.upsert_run(
        run_key="ret-run-active:MU:2026-01-03",
        user_id=user_id,
        tenant_id=tenant_id,
        run_id="ret-run-active",
        ticker="MU",
        date_label="2026-01-03",
        status="running",
        metadata={},
    )
    with store._lock:
        cur = store._conn.cursor()
        cur.execute(
            "UPDATE jobs SET created_at = ?, updated_at = ? WHERE job_id = ?",
            (old_ts, old_ts, "job_ret_old_queued"),
        )
        cur.execute(
            "UPDATE runs SET created_at = ?, updated_at = ? WHERE run_key = ?",
            (old_ts, old_ts, "ret-run-active:MU:2026-01-03"),
        )
        store._conn.commit()

    token = _make_jwt(
        {
            "sub": user_id,
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    response = client.get("/api/v2/usage", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    with store._lock:
        cur = store._conn.cursor()
        job_row = cur.execute(
            "SELECT job_id FROM jobs WHERE user_id = ? AND job_id = ?",
            (user_id, "job_ret_old_queued"),
        ).fetchone()
        run_row = cur.execute(
            "SELECT run_key FROM runs WHERE user_id = ? AND run_key = ?",
            (user_id, "ret-run-active:MU:2026-01-03"),
        ).fetchone()

    assert job_row is not None
    assert run_row is not None


def test_v2_adaptive_strategies_user_scope_lifecycle(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "adaptive-user-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    create_resp = client.post(
        "/api/v2/strategies/adaptive",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "ticker": "MU",
            "profile_name": "user momentum v1",
            "adaptive_version": 2,
            "scope": "user",
            "candidate": {
                "strategy_selection_mode": "adaptive_top_n",
                "max_active_strategies": 3,
            },
            "metadata": {"note": "personal profile"},
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()["profile"]
    assert created["scope"] == "user"
    assert created["ticker"] == "MU"
    assert created["profile_name"] == "user momentum v1"
    assert created["adaptive_version"] == 2
    assert created["owner_user_id"] == "adaptive-user-1"
    profile_id = created["profile_id"]

    list_resp = client.get(
        "/api/v2/strategies/adaptive?ticker=MU",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    profiles = list_resp.json()["profiles"]
    assert any(item["profile_id"] == profile_id for item in profiles)

    delete_resp = client.delete(
        f"/api/v2/strategies/adaptive/{profile_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True


def test_v2_adaptive_strategies_global_scope_requires_admin(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    free_token = _make_jwt(
        {
            "sub": "adaptive-user-free",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    denied = client.post(
        "/api/v2/strategies/adaptive",
        headers={"Authorization": f"Bearer {free_token}"},
        json={
            "ticker": "MU",
            "profile_name": "global denied",
            "scope": "global",
            "adaptive_version": 2,
            "candidate": {"max_active_strategies": 4},
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "forbidden"

    admin_token = _make_jwt(
        {
            "sub": "adaptive-admin-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "admin", "plan_tier": "admin"},
        },
        "test-secret",
    )
    created = client.post(
        "/api/v2/strategies/adaptive",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "ticker": "MU",
            "profile_name": "global default",
            "scope": "global",
            "adaptive_version": 2,
            "candidate": {"max_active_strategies": 5},
        },
    )
    assert created.status_code == 200
    created_profile_id = created.json()["profile"]["profile_id"]

    visible_for_free = client.get(
        "/api/v2/strategies/adaptive?ticker=MU",
        headers={"Authorization": f"Bearer {free_token}"},
    )
    assert visible_for_free.status_code == 200
    ids = {item["profile_id"] for item in visible_for_free.json()["profiles"]}
    assert created_profile_id in ids


def test_v2_adaptive_strategies_non_owner_cannot_delete_user_profile(
    tmp_path, monkeypatch
):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    owner_token = _make_jwt(
        {
            "sub": "adaptive-owner-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    created = client.post(
        "/api/v2/strategies/adaptive",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "ticker": "MU",
            "profile_name": "owner only profile",
            "scope": "user",
            "adaptive_version": 1,
            "candidate": {"strategy_selection_mode": "adaptive_top_n"},
        },
    )
    assert created.status_code == 200
    profile_id = created.json()["profile"]["profile_id"]

    other_token = _make_jwt(
        {
            "sub": "adaptive-other-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    denied = client.delete(
        f"/api/v2/strategies/adaptive/{profile_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "forbidden"

    admin_token = _make_jwt(
        {
            "sub": "adaptive-admin-2",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "admin", "plan_tier": "admin"},
        },
        "test-secret",
    )
    admin_delete = client.delete(
        f"/api/v2/strategies/adaptive/{profile_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_delete.status_code == 200
    assert admin_delete.json()["deleted"] is True


def test_v2_user_settings_roundtrip_and_top_level_merge(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "settings-user-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.get("/api/v2/user/settings", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["settings"] == {}

    first_payload = {
        "settings": {
            "run_config_draft": {
                "version": 1,
                "saved_at": "2026-02-17T10:00:00Z",
                "config": {
                    "ticker": "MU",
                    "date_from": "2026-02-10",
                    "date_to": "2026-02-11",
                },
                "selected_unified_profile_id": "mu_scalp_intrabar_fee_v1",
            },
            "sidebar_nav": {"active": "dates"},
        }
    }
    first = client.put("/api/v2/user/settings", headers=headers, json=first_payload)
    assert first.status_code == 200
    first_settings = first.json()["settings"]
    assert first_settings["run_config_draft"]["config"]["ticker"] == "MU"
    assert first_settings["sidebar_nav"]["active"] == "dates"

    second = client.put(
        "/api/v2/user/settings",
        headers=headers,
        json={"settings": {"sidebar_nav": {"active": "profiles"}}},
    )
    assert second.status_code == 200
    merged = second.json()["settings"]
    assert (
        merged["run_config_draft"]["selected_unified_profile_id"]
        == "mu_scalp_intrabar_fee_v1"
    )
    assert merged["sidebar_nav"]["active"] == "profiles"

    final = client.get("/api/v2/user/settings", headers=headers)
    assert final.status_code == 200
    final_settings = final.json()["settings"]
    assert final_settings["run_config_draft"]["config"]["ticker"] == "MU"
    assert final_settings["sidebar_nav"]["active"] == "profiles"


def test_v2_user_settings_are_user_scoped(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token_user_a = _make_jwt(
        {
            "sub": "settings-user-a",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    token_user_b = _make_jwt(
        {
            "sub": "settings-user-b",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers_a = {"Authorization": f"Bearer {token_user_a}"}
    headers_b = {"Authorization": f"Bearer {token_user_b}"}

    put_a = client.put(
        "/api/v2/user/settings",
        headers=headers_a,
        json={"settings": {"run_config_draft": {"config": {"ticker": "MU"}}}},
    )
    assert put_a.status_code == 200

    put_b = client.put(
        "/api/v2/user/settings",
        headers=headers_b,
        json={"settings": {"run_config_draft": {"config": {"ticker": "NVDA"}}}},
    )
    assert put_b.status_code == 200

    get_a = client.get("/api/v2/user/settings", headers=headers_a)
    get_b = client.get("/api/v2/user/settings", headers=headers_b)
    assert get_a.status_code == 200
    assert get_b.status_code == 200
    assert get_a.json()["settings"]["run_config_draft"]["config"]["ticker"] == "MU"
    assert get_b.json()["settings"]["run_config_draft"]["config"]["ticker"] == "NVDA"


def test_v2_user_settings_can_use_external_store_adapter(tmp_path, monkeypatch):
    class _StubSettingsStore:
        def __init__(self):
            self.calls = []
            self.rows = {}

        def get_user_settings(self, *, user_id: str):
            self.calls.append(("get", user_id))
            return dict(self.rows.get(user_id, {}))

        def merge_user_settings(self, *, user_id: str, tenant_id: str, patch: dict):
            self.calls.append(("merge", user_id, tenant_id, dict(patch)))
            current = dict(self.rows.get(user_id, {}))
            current.update(dict(patch or {}))
            self.rows[user_id] = current
            return dict(current)

    stub = _StubSettingsStore()
    client, _calls = _build_client(tmp_path, user_settings_store=stub)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "settings-external-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {"Authorization": f"Bearer {token}"}

    put_resp = client.put(
        "/api/v2/user/settings",
        headers=headers,
        json={"settings": {"run_config_draft": {"config": {"ticker": "AMD"}}}},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["settings"]["run_config_draft"]["config"]["ticker"] == "AMD"

    get_resp = client.get("/api/v2/user/settings", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["settings"]["run_config_draft"]["config"]["ticker"] == "AMD"
    assert any(call[0] == "merge" for call in stub.calls)
    assert any(call[0] == "get" for call in stub.calls)


def test_v2_user_datasets_roundtrip_with_default_object_path(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_USER_DATASETS_STORAGE_MODE", "remote")
    monkeypatch.setenv("BACKTEST_USER_DATASETS_BUCKET", "datasets-bucket")

    token = _make_jwt(
        {
            "sub": "dataset-user-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {"Authorization": f"Bearer {token}"}

    initial = client.get("/api/v2/datasets", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["datasets"] == []

    create = client.post(
        "/api/v2/datasets",
        headers=headers,
        json={
            "dataset_name": "My EURAUD Tick Data",
            "source_filename": "euraud_ticks.csv",
            "row_count": 1234,
            "size_bytes": 5678,
            "metadata": {"timezone": "UTC"},
        },
    )
    assert create.status_code == 200
    dataset = create.json()["dataset"]
    dataset_id = dataset["dataset_id"]
    assert dataset_id.startswith("ds_")
    assert dataset["status"] == "ready"
    assert dataset["file_format"] == "parquet"
    assert (
        dataset["s3_path"]
        == f"s3://datasets-bucket/users/dataset-user-1/datasets/{dataset_id}.parquet"
    )

    listed = client.get("/api/v2/datasets", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["datasets"][0]["dataset_id"] == dataset_id

    fetched = client.get(f"/api/v2/datasets/{dataset_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["dataset"]["dataset_name"] == "My EURAUD Tick Data"

    deleted = client.delete(f"/api/v2/datasets/{dataset_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    final = client.get("/api/v2/datasets", headers=headers)
    assert final.status_code == 200
    assert final.json()["datasets"] == []


def test_v2_user_datasets_default_path_is_local_in_auto_mode_on_testserver(
    tmp_path, monkeypatch
):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_USER_DATASETS_STORAGE_MODE", "auto")
    monkeypatch.setenv("BACKTEST_USER_DATASETS_BUCKET", "datasets-bucket")

    token = _make_jwt(
        {
            "sub": "dataset-user-auto",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create = client.post(
        "/api/v2/datasets",
        headers=headers,
        json={"dataset_name": "Auto Local Dataset"},
    )
    assert create.status_code == 200
    dataset = create.json()["dataset"]
    assert dataset["s3_path"].startswith("users/dataset-user-auto/datasets/")
    assert not dataset["s3_path"].startswith("s3://")


def test_v2_user_dataset_auto_mode_uses_bucket_only_for_non_local_hosts(monkeypatch):
    monkeypatch.setenv("BACKTEST_USER_DATASETS_STORAGE_MODE", "auto")
    request = SimpleNamespace(url=SimpleNamespace(hostname="prod.example.com"))

    monkeypatch.delenv("BACKTEST_USER_DATASETS_BUCKET", raising=False)
    assert _request_prefers_local_user_datasets(request) is True

    monkeypatch.setenv("BACKTEST_USER_DATASETS_BUCKET", "datasets-bucket")
    assert _request_prefers_local_user_datasets(request) is False


def test_v2_user_datasets_are_user_scoped(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token_user_a = _make_jwt(
        {
            "sub": "dataset-user-a",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    token_user_b = _make_jwt(
        {
            "sub": "dataset-user-b",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers_a = {"Authorization": f"Bearer {token_user_a}"}
    headers_b = {"Authorization": f"Bearer {token_user_b}"}

    create = client.post(
        "/api/v2/datasets",
        headers=headers_a,
        json={"dataset_name": "Private Dataset", "s3_path": "users/a/private.parquet"},
    )
    assert create.status_code == 200
    dataset_id = create.json()["dataset"]["dataset_id"]

    list_b = client.get("/api/v2/datasets", headers=headers_b)
    assert list_b.status_code == 200
    assert list_b.json()["datasets"] == []

    get_b = client.get(f"/api/v2/datasets/{dataset_id}", headers=headers_b)
    assert get_b.status_code == 403
    assert get_b.json()["detail"]["code"] == "forbidden"

    delete_b = client.delete(f"/api/v2/datasets/{dataset_id}", headers=headers_b)
    assert delete_b.status_code == 403
    assert delete_b.json()["detail"]["code"] == "forbidden"

    get_a = client.get(f"/api/v2/datasets/{dataset_id}", headers=headers_a)
    assert get_a.status_code == 200
    assert get_a.json()["dataset"]["dataset_name"] == "Private Dataset"


def test_v2_user_datasets_can_use_external_store_adapter(tmp_path, monkeypatch):
    class _StubDatasetsStore:
        def __init__(self):
            self.calls = []
            self.rows = {}

        def list_user_datasets(self, *, user_id: str, limit: int = 100, status=None):
            self.calls.append(("list", user_id, limit, status))
            rows = [
                dict(row)
                for row in self.rows.values()
                if str(row.get("user_id") or "") == user_id
            ]
            if status:
                rows = [
                    row
                    for row in rows
                    if str(row.get("status") or "").lower() == str(status).lower()
                ]
            return rows[:limit]

        def get_user_dataset(self, *, dataset_id: str):
            self.calls.append(("get", dataset_id))
            row = self.rows.get(dataset_id)
            return dict(row) if isinstance(row, dict) else None

        def upsert_user_dataset(self, **kwargs):
            self.calls.append(("upsert", dict(kwargs)))
            row = dict(kwargs)
            row.setdefault("created_at", "2026-02-28T12:00:00Z")
            row["updated_at"] = "2026-02-28T12:05:00Z"
            row["metadata"] = (
                row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            )
            self.rows[row["dataset_id"]] = row
            return dict(row)

        def delete_user_dataset(self, *, dataset_id: str, user_id: str):
            self.calls.append(("delete", dataset_id, user_id))
            row = self.rows.get(dataset_id)
            if not isinstance(row, dict):
                return False
            if str(row.get("user_id") or "") != user_id:
                return False
            del self.rows[dataset_id]
            return True

    stub = _StubDatasetsStore()
    client, _calls = _build_client(tmp_path, user_datasets_store=stub)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")

    token = _make_jwt(
        {
            "sub": "dataset-external-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {"Authorization": f"Bearer {token}"}

    put_resp = client.post(
        "/api/v2/datasets",
        headers=headers,
        json={
            "dataset_name": "Adapter Dataset",
            "s3_path": "users/dataset-external-1/datasets/adapter.parquet",
        },
    )
    assert put_resp.status_code == 200
    dataset_id = put_resp.json()["dataset"]["dataset_id"]

    list_resp = client.get("/api/v2/datasets", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] == 1
    assert list_resp.json()["datasets"][0]["dataset_id"] == dataset_id

    del_resp = client.delete(f"/api/v2/datasets/{dataset_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True
    assert any(call[0] == "upsert" for call in stub.calls)
    assert any(call[0] == "list" for call in stub.calls)
    assert any(call[0] == "delete" for call in stub.calls)


def test_v2_user_dataset_csv_upload_creates_local_parquet(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.delenv("BACKTEST_USER_DATASETS_BUCKET", raising=False)
    monkeypatch.setenv(
        "BACKTEST_USER_DATASETS_LOCAL_CACHE_DIR",
        str(tmp_path / "user_dataset_cache"),
    )

    token = _make_jwt(
        {
            "sub": "dataset-upload-1",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/csv; charset=utf-8",
    }

    response = client.post(
        "/api/v2/datasets/upload/csv",
        headers=headers,
        params={
            "dataset_name": "Uploaded CSV Dataset",
            "source_filename": "ticks.csv",
            "schema_name": "custom_ticks",
        },
        content=(
            b"ts,price,qty\n"
            b"2026-02-28T10:00:00Z,1.25,10\n"
            b"2026-02-28T10:00:01Z,1.30,12\n"
        ),
    )
    assert response.status_code == 200
    payload = response.json()
    dataset = payload["dataset"]
    upload = payload["upload"]

    assert dataset["dataset_name"] == "Uploaded CSV Dataset"
    assert dataset["source_format"] == "csv"
    assert dataset["file_format"] == "parquet"
    assert dataset["row_count"] == 2
    assert dataset["schema_name"] == "custom_ticks"
    assert dataset["s3_path"].startswith("users/dataset-upload-1/datasets/")
    assert upload["storage_mode"] == "local_cache"

    local_cache_path = upload["local_cache_path"]
    assert local_cache_path
    frame = read_parquet_compat(local_cache_path)
    assert len(frame.index) == 2
    assert list(frame.columns) == ["ts", "price", "qty"]

    dataset_id = dataset["dataset_id"]
    fetched = client.get(f"/api/v2/datasets/{dataset_id}", headers=headers)
    assert fetched.status_code == 200
    ingest_meta = fetched.json()["dataset"]["metadata"]["ingest"]
    assert ingest_meta["source"] == "csv_upload"
    assert ingest_meta["storage_mode"] == "local_cache"
    assert ingest_meta["local_cache_path"] == local_cache_path


def test_v2_user_dataset_csv_upload_enforces_size_limit(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_USER_DATASET_UPLOAD_MAX_BYTES", "16")

    token = _make_jwt(
        {
            "sub": "dataset-upload-2",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/csv",
    }

    response = client.post(
        "/api/v2/datasets/upload/csv",
        headers=headers,
        params={"dataset_name": "Too Large"},
        content=b"ts,price\n2026-02-28T10:00:00Z,1.25\n",
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "dataset_upload_too_large"


def test_v2_user_dataset_csv_upload_remote_mode_requires_bucket(tmp_path, monkeypatch):
    client, _calls = _build_client(tmp_path)
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    monkeypatch.setenv("BACKTEST_USER_DATASETS_STORAGE_MODE", "remote")
    monkeypatch.delenv("BACKTEST_USER_DATASETS_BUCKET", raising=False)

    token = _make_jwt(
        {
            "sub": "dataset-upload-3",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/csv",
    }

    response = client.post(
        "/api/v2/datasets/upload/csv",
        headers=headers,
        params={"dataset_name": "Remote Needs Bucket"},
        content=b"ts,price\n2026-02-28T10:00:00Z,1.25\n",
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "dataset_storage_unavailable"
