from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.context import ApiServices
from src.routes.system_routes import router


def _build_services(*, l2_manager, l2_features) -> ApiServices:
    noop_async = lambda *_args, **_kwargs: None
    noop_sync = lambda *_args, **_kwargs: {}
    return ApiServices(
        data_loader=SimpleNamespace(),
        l2_manager=l2_manager,
        l2_features=l2_features,
        active_runners={},
        databento_svc=SimpleNamespace(
            get_available_data_summary=lambda refresh=False: {},
        ),
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


def _build_client(*, l2_manager, l2_features) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.api_services = _build_services(
        l2_manager=l2_manager,
        l2_features=l2_features,
    )
    return TestClient(app)


def test_get_l2_runtime_reports_current_values():
    l2_manager = SimpleNamespace(
        max_cached_tickers=1,
        max_cached_rows=2_000_000,
        max_cached_bytes=536_870_912,
    )
    l2_features = SimpleNamespace(iceberg_detection_enabled=True)
    client = _build_client(l2_manager=l2_manager, l2_features=l2_features)

    response = client.get("/api/system/l2/runtime")
    assert response.status_code == 200
    payload = response.json()
    assert payload["iceberg_detection_enabled"] is True
    assert payload["cache_max_tickers"] == 1
    assert payload["cache_max_rows"] == 2_000_000
    assert payload["cache_max_bytes"] == 536_870_912


def test_update_l2_runtime_applies_overrides():
    l2_manager = SimpleNamespace(
        max_cached_tickers=1,
        max_cached_rows=2_000_000,
        max_cached_bytes=536_870_912,
    )
    l2_features = SimpleNamespace(iceberg_detection_enabled=True)
    client = _build_client(l2_manager=l2_manager, l2_features=l2_features)

    response = client.post(
        "/api/system/l2/runtime",
        json={
            "iceberg_detection_enabled": False,
            "cache_max_rows": 5_000_000,
            "cache_max_bytes": 2_147_483_648,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["updated"]["iceberg_detection_enabled"] is False
    assert payload["updated"]["cache_max_rows"] == 5_000_000
    assert payload["updated"]["cache_max_bytes"] == 2_147_483_648
    assert payload["runtime"]["iceberg_detection_enabled"] is False
    assert payload["runtime"]["cache_max_rows"] == 5_000_000
    assert payload["runtime"]["cache_max_bytes"] == 2_147_483_648
    assert l2_features.iceberg_detection_enabled is False
    assert l2_manager.max_cached_rows == 5_000_000
    assert l2_manager.max_cached_bytes == 2_147_483_648


def test_update_l2_runtime_rejects_negative_cache():
    l2_manager = SimpleNamespace(
        max_cached_tickers=1,
        max_cached_rows=2_000_000,
        max_cached_bytes=536_870_912,
    )
    l2_features = SimpleNamespace(iceberg_detection_enabled=True)
    client = _build_client(l2_manager=l2_manager, l2_features=l2_features)

    response = client.post("/api/system/l2/runtime", json={"cache_max_rows": -1})
    assert response.status_code == 400
    assert "cache_max_rows" in response.json()["detail"]
