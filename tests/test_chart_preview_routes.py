from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from data_loader import DataLoader
from src.routes.chart_preview_routes import router
from src.routes.context import ApiServices


def _build_services(*, data_loader, databento_svc, state_store=None) -> ApiServices:
    noop_async = lambda *_args, **_kwargs: None
    noop_sync = lambda *_args, **_kwargs: {}
    return ApiServices(
        data_loader=data_loader,
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
        state_store=state_store,
    )


def _build_client(*, data_loader, databento_svc, state_store=None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.api_services = _build_services(
        data_loader=data_loader,
        databento_svc=databento_svc,
        state_store=state_store,
    )
    return TestClient(app)


def _write_ohlcv_csv(path: Path) -> None:
    path.write_text(
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-02-23T14:30:00Z,100,101,99,100.5,1500\n"
            "2026-02-23T14:31:00Z,100.5,101.2,100.1,101,1700\n"
        ),
        encoding="utf-8",
    )


def test_chart_preview_uses_catalog_files_after_rescan(tmp_path: Path):
    csv_path = tmp_path / "MU_ohlcv-1m_2026-02-23_2026-02-23.csv"
    _write_ohlcv_csv(csv_path)
    loader = DataLoader(data_dirs=[str(tmp_path)])

    class _DatabentoSvc:
        def __init__(self):
            self.scan_calls = 0

        def get_files_for_range(
            self,
            ticker: str,
            start_date: str,
            end_date: str,
            schema_prefix: str = "ohlcv-",
        ):
            if self.scan_calls == 0:
                return []
            return [str(csv_path)]

        def scan_existing_files(self):
            self.scan_calls += 1
            return []

    svc = _DatabentoSvc()
    client = _build_client(data_loader=loader, databento_svc=svc)

    response = client.get(
        "/api/chart-preview/bars",
        params={
            "ticker": "MU",
            "date_from": "2026-02-23",
            "date_to": "2026-02-23",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MU"
    assert payload["bar_count"] == 2
    assert svc.scan_calls == 1


def test_chart_preview_returns_404_when_catalog_has_no_ohlcv_files(tmp_path: Path):
    loader = DataLoader(data_dirs=[str(tmp_path)])

    class _DatabentoSvc:
        def __init__(self):
            self.scan_calls = 0

        def get_files_for_range(
            self,
            ticker: str,
            start_date: str,
            end_date: str,
            schema_prefix: str = "ohlcv-",
        ):
            return []

        def scan_existing_files(self):
            self.scan_calls += 1
            return []

    svc = _DatabentoSvc()
    client = _build_client(data_loader=loader, databento_svc=svc)

    response = client.get(
        "/api/chart-preview/bars",
        params={
            "ticker": "MU",
            "date_from": "2026-02-23",
            "date_to": "2026-02-23",
        },
    )
    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No OHLCV data files found for MU in range 2026-02-23..2026-02-23"
    )
    assert svc.scan_calls == 1


def test_chart_preview_daily_heatmap_reads_from_state_store(tmp_path: Path):
    loader = DataLoader(data_dirs=[str(tmp_path)])

    class _DatabentoSvc:
        def get_files_for_range(
            self,
            ticker: str,
            start_date: str,
            end_date: str,
            schema_prefix: str = "ohlcv-",
        ):
            return []

        def scan_existing_files(self):
            return []

    class _StateStore:
        def list_daily_price_heatmap_rows(
            self,
            *,
            ticker: str,
            date_from: str,
            date_to: str,
            bin_size: float,
        ):
            assert ticker == "MU"
            assert date_from == "2026-02-23"
            assert date_to == "2026-02-24"
            assert float(bin_size) == 0.5
            return [
                {
                    "as_of_date": "2026-02-23",
                    "price_bin": 100.0,
                    "day_bars": 2,
                    "day_volume": 3000.0,
                    "cumulative_bars": 2,
                    "cumulative_volume": 3000.0,
                    "total_bars_to_date": 2,
                    "total_volume_to_date": 3000.0,
                    "cumulative_bar_share": 1.0,
                    "cumulative_volume_share": 1.0,
                },
                {
                    "as_of_date": "2026-02-24",
                    "price_bin": 101.0,
                    "day_bars": 1,
                    "day_volume": 2000.0,
                    "cumulative_bars": 1,
                    "cumulative_volume": 2000.0,
                    "total_bars_to_date": 4,
                    "total_volume_to_date": 7000.0,
                    "cumulative_bar_share": 0.25,
                    "cumulative_volume_share": 0.2857,
                },
                {
                    "as_of_date": "2026-02-24",
                    "price_bin": 100.0,
                    "day_bars": 1,
                    "day_volume": 2000.0,
                    "cumulative_bars": 3,
                    "cumulative_volume": 5000.0,
                    "total_bars_to_date": 4,
                    "total_volume_to_date": 7000.0,
                    "cumulative_bar_share": 0.75,
                    "cumulative_volume_share": 0.7143,
                },
            ]

    client = _build_client(
        data_loader=loader,
        databento_svc=_DatabentoSvc(),
        state_store=_StateStore(),
    )

    response = client.get(
        "/api/chart-preview/heatmap-daily-cumulative",
        params={
            "ticker": "MU",
            "date_from": "2026-02-23",
            "date_to": "2026-02-24",
            "bin_size": "0.5",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "MU"
    assert payload["days"] == ["2026-02-23", "2026-02-24"]
    assert payload["latest_as_of_date"] == "2026-02-24"
    assert payload["latest_summary"]["total_bars"] == 4
    assert payload["latest_summary"]["total_volume"] == 7000.0
    assert payload["rows"][0]["price_bin"] == 101.0
    assert payload["rows"][0]["cumulative_bars"] == [0, 1]
    assert payload["rows"][1]["price_bin"] == 100.0
    assert payload["rows"][1]["cumulative_bars"] == [2, 3]
    assert payload["top_by_time"][0]["price_bin"] == 100.0
    assert payload["top_by_time"][0]["cumulative_bars"] == 3


def test_chart_preview_daily_heatmap_returns_503_without_store(tmp_path: Path):
    loader = DataLoader(data_dirs=[str(tmp_path)])

    class _DatabentoSvc:
        def get_files_for_range(
            self,
            ticker: str,
            start_date: str,
            end_date: str,
            schema_prefix: str = "ohlcv-",
        ):
            return []

        def scan_existing_files(self):
            return []

    client = _build_client(
        data_loader=loader,
        databento_svc=_DatabentoSvc(),
        state_store=None,
    )
    response = client.get(
        "/api/chart-preview/heatmap-daily-cumulative",
        params={
            "ticker": "MU",
            "date_from": "2026-02-23",
            "date_to": "2026-02-24",
            "bin_size": "0.5",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Daily price heatmap store is not configured."
