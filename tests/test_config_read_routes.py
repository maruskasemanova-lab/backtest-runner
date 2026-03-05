from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.config_read_routes import router
from src.routes.context import ApiServices


def _normalize_profiles(value):
    return list(value) if isinstance(value, list) else []


def _build_services() -> ApiServices:
    noop_async = lambda *_args, **_kwargs: None
    noop_sync = lambda *_args, **_kwargs: {}
    return ApiServices(
        data_loader=SimpleNamespace(),
        l2_manager=SimpleNamespace(),
        l2_features=SimpleNamespace(),
        active_runners={},
        databento_svc=SimpleNamespace(),
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None),
        get_live_trader_artifacts_dir=lambda: None,
        live_run_active_window_seconds=60,
        load_strategy_overrides=noop_sync,
        build_strategy_combo_options_payload=lambda _ticker: {},
        load_aos_config=lambda: {
            "version": "1.0.0",
            "tickers": {
                "MU": {
                    "strategy_selection_mode": "adaptive_top_n",
                    "risk_per_trade_pct": 0.35,
                }
            },
        },
        load_positioning_config=noop_sync,
        merge_positioning_into_aos_snapshot=lambda aos, _pos: aos,
        get_ticker_positioning_config=lambda _ticker: {"trailing_stop_pct": 0.8},
        positioning_config_keys=("risk_per_trade_pct", "trailing_stop_pct"),
        build_adaptive_tuner_options_payload=lambda _ticker: {},
        build_unified_profile_options_payload=lambda _ticker: {},
        build_config_write_deps=lambda: SimpleNamespace(
            normalize_strategy_combo_profiles=_normalize_profiles,
            normalize_unified_profiles=_normalize_profiles,
            normalize_tuner_profiles=_normalize_profiles,
        ),
        build_run_control_deps=lambda: None,
        build_adaptive_tuner_deps=lambda: None,
        start_run=noop_async,
        prewarm_run=noop_async,
        prewarm_status=noop_async,
        broadcast=noop_async,
        refresh_runtime_data_services=lambda: None,
        reset_discovery=lambda: None,
        state_store=None,
    )


def test_get_ticker_aos_config_merges_positioning_into_db_backed_ticker_payload():
    app = FastAPI()
    app.include_router(router)
    app.state.api_services = _build_services()
    client = TestClient(app)

    response = client.get("/api/aos-config/MU")

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_selection_mode"] == "adaptive_top_n"
    assert payload["risk_per_trade_pct"] == 0.35
    assert payload["positioning"] == {
        "risk_per_trade_pct": 0.35,
        "trailing_stop_pct": 0.8,
    }
