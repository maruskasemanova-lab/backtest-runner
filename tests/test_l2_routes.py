from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.context import ApiServices
from src.routes.l2_routes import router


def _build_services(*, l2_manager) -> ApiServices:
    noop_async = lambda *_args, **_kwargs: None
    noop_sync = lambda *_args, **_kwargs: {}
    return ApiServices(
        data_loader=SimpleNamespace(),
        l2_manager=l2_manager,
        l2_features=SimpleNamespace(),
        active_runners={},
        databento_svc=SimpleNamespace(get_available_data_summary=lambda refresh=False: {}),
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


def _build_client(*, l2_manager) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.api_services = _build_services(l2_manager=l2_manager)
    return TestClient(app)


def test_get_icebergs_filters_ranks_and_limits_results():
    class _L2Manager:
        def __init__(self):
            self.load_calls = []

        def load_data(self, ticker, start_date, end_date):
            self.load_calls.append((ticker, start_date, end_date))

        def detect_icebergs(self, _ticker, _start_dt, _end_dt):
            return [
                {"id": "a", "time": "2026-02-13T14:30:01Z", "trade_size": 220, "hidden_size": 210},
                {"id": "b", "time": "2026-02-13T14:31:01Z", "trade_size": 650, "hidden_size": 150},
                {"id": "c", "time": "2026-02-13T14:32:01Z", "trade_size": 900, "hidden_size": 500},
                {"id": "d", "time": "2026-02-13T14:33:01Z", "trade_size": 800, "hidden_size": 400},
                {"id": "e", "time": "2026-02-13T14:34:01Z", "trade_size": 700, "hidden_size": 300},
            ]

    manager = _L2Manager()
    client = _build_client(l2_manager=manager)

    response = client.get(
        "/api/l2/icebergs/MU",
        params={
            "start_time": "2026-02-13T14:00:00Z",
            "end_time": "2026-02-13T15:00:00Z",
            "min_hidden_size": 250,
            "min_trade_size": 600,
            "limit": 2,
            "sort": "hidden_size",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert [row["id"] for row in payload] == ["c", "d"]
    assert manager.load_calls == [("MU", "2026-02-13", "2026-02-13")]


def test_get_icebergs_time_limit_keeps_latest_events():
    class _L2Manager:
        def load_data(self, _ticker, _start_date, _end_date):
            return None

        def detect_icebergs(self, _ticker, _start_dt, _end_dt):
            return [
                {"id": "a", "time": "2026-02-13T14:30:01Z", "trade_size": 100, "hidden_size": 40},
                {"id": "b", "time": "2026-02-13T14:31:01Z", "trade_size": 120, "hidden_size": 50},
                {"id": "c", "time": "2026-02-13T14:32:01Z", "trade_size": 130, "hidden_size": 60},
            ]

    client = _build_client(l2_manager=_L2Manager())

    response = client.get(
        "/api/l2/icebergs/MU",
        params={
            "start_time": "2026-02-13T14:00:00Z",
            "end_time": "2026-02-13T15:00:00Z",
            "limit": 2,
            "sort": "time",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert [row["id"] for row in payload] == ["b", "c"]


def test_get_icebergs_rejects_invalid_timestamp():
    class _L2Manager:
        def load_data(self, _ticker, _start_date, _end_date):
            return None

        def detect_icebergs(self, _ticker, _start_dt, _end_dt):
            return []

    client = _build_client(l2_manager=_L2Manager())

    response = client.get(
        "/api/l2/icebergs/MU",
        params={
            "start_time": "not-a-date",
            "end_time": "2026-02-13T15:00:00Z",
        },
    )
    assert response.status_code == 400
    assert "Invalid timestamp format" in response.json()["detail"]
