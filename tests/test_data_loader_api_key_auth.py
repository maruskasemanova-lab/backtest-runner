from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.context import ApiServices
from src.routes.data_loader_routes import router


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _make_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    part_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    part_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signed = f"{part_header}.{part_payload}".encode("utf-8")
    sig = _b64url(hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).digest())
    return f"{part_header}.{part_payload}.{sig}"


def _build_services() -> ApiServices:
    noop_async = lambda *_args, **_kwargs: None
    noop_sync = lambda *_args, **_kwargs: {}

    def _set_api_key(value: str):
        return {
            "databento_api_key": str(value or ""),
            "masked": "***" if value else "",
        }

    databento_svc = SimpleNamespace(
        set_api_key=_set_api_key,
        update_data_dirs=lambda **_kwargs: {},
        get_settings=lambda: {},
        get_schemas=lambda: {},
        get_cost_estimate=lambda **_kwargs: {},
        get_range_coverage=lambda **_kwargs: {"fully_covered": True},
        download=noop_async,
        get_active_downloads=lambda: [],
        catalog=SimpleNamespace(find=lambda *_args, **_kwargs: None),
        delete_entry=lambda *_args, **_kwargs: True,
        scan_existing_files=lambda: {},
        sync_remote_manifest=lambda _url=None: 3,
    )

    return ApiServices(
        data_loader=SimpleNamespace(),
        l2_manager=SimpleNamespace(),
        l2_features=SimpleNamespace(),
        active_runners={},
        databento_svc=databento_svc,
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        get_live_trader_artifacts_dir=lambda: None,
        live_run_active_window_seconds=60,
        load_strategy_overrides=noop_sync,
        build_strategy_combo_options_payload=lambda _ticker: {},
        load_aos_config=noop_sync,
        load_positioning_config=noop_sync,
        merge_positioning_into_aos_snapshot=lambda aos, _pos: aos,
        get_ticker_positioning_config=lambda _ticker: {},
        positioning_config_keys=(),
        build_adaptive_tuner_options_payload=lambda _ticker: {},
        build_unified_profile_options_payload=lambda _ticker: {},
        build_config_write_deps=lambda: None,
        build_run_control_deps=lambda: None,
        build_adaptive_tuner_deps=lambda: None,
        start_run=noop_async,
        prewarm_run=noop_async,
        prewarm_status=noop_async,
        broadcast=noop_async,
        refresh_runtime_data_services=lambda: None,
        reset_discovery=lambda: None,
    )


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.api_services = _build_services()
    return TestClient(app)


def test_api_key_endpoint_requires_admin_when_enforced(monkeypatch):
    monkeypatch.setenv("BACKTEST_ENFORCE_ADMIN_DATABENTO_API_KEY", "true")
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    client = _build_client()

    resp = client.put("/api/data-loader/api-key", json={"api_key": "abc"})
    assert resp.status_code == 401


def test_api_key_endpoint_denies_non_admin(monkeypatch):
    monkeypatch.setenv("BACKTEST_ENFORCE_ADMIN_DATABENTO_API_KEY", "true")
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    client = _build_client()

    token = _make_jwt(
        {
            "sub": "user-free",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "free", "plan_tier": "free"},
        },
        "test-secret",
    )
    resp = client.put(
        "/api/data-loader/api-key",
        json={"api_key": "abc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_api_key_endpoint_allows_admin(monkeypatch):
    monkeypatch.setenv("BACKTEST_ENFORCE_ADMIN_DATABENTO_API_KEY", "true")
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    client = _build_client()

    token = _make_jwt(
        {
            "sub": "user-admin",
            "exp": int(time.time()) + 3600,
            "app_metadata": {"role": "admin", "plan_tier": "admin"},
        },
        "test-secret",
    )
    resp = client.put(
        "/api/data-loader/api-key",
        json={"api_key": "secret-key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"


def test_api_key_endpoint_unlocked_in_local_mode(monkeypatch):
    monkeypatch.setenv("BACKTEST_ENFORCE_ADMIN_DATABENTO_API_KEY", "false")
    monkeypatch.setenv("BACKTEST_JWT_SECRET", "test-secret")
    client = _build_client()

    resp = client.put("/api/data-loader/api-key", json={"api_key": "abc"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_remote_sync_endpoint_returns_synced_count():
    client = _build_client()
    resp = client.post("/api/data-loader/catalog/remote-sync")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert payload["synced_entries"] == 3
