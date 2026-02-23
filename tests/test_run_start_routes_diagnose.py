from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.routes.context import get_api_services
from src.routes.run_start_routes import router


class _FakeDatabentoService:
    def scan_existing_files(self):
        return None

    def list_catalog(self, refresh=False, ticker=None):
        _ = refresh
        _ = ticker
        return [
            {"ticker": "MU", "schema": "ohlcv-1m", "status": "ready"},
            {"ticker": "MU", "schema": "mbp-10", "status": "ready"},
        ]

    def get_range_coverage(self, ticker, schema, start_date, end_date):
        _ = ticker
        _ = start_date
        _ = end_date
        if str(schema).lower().startswith("mbp-"):
            return {
                "schema": "mbp-10",
                "total_days": 1,
                "covered_days": ["2025-11-03"],
                "missing_days": [],
                "fully_covered": True,
            }
        return {
            "schema": "ohlcv-1m",
            "total_days": 1,
            "covered_days": ["2025-11-03"],
            "missing_days": [],
            "fully_covered": True,
        }


def _build_client(services):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_api_services] = lambda: services
    return TestClient(app)


def test_run_diagnose_returns_success_payload():
    async def _prewarm_status(_request):
        return {
            "ticker": "MU",
            "range_start": "2025-11-03",
            "range_end": "2025-11-03",
            "l2_requested": True,
            "use_l2": True,
        }

    async def _prewarm_run(_request):
        return {
            "bars": 240,
            "reference_bars": 240,
            "data_files_count": 1,
            "use_l2": True,
            "l2_only": False,
            "l2_confirm_enabled": True,
            "l2": {"missing_l2_days_count": 0},
            "cache_hit": False,
        }

    services = SimpleNamespace(
        prewarm_status=_prewarm_status,
        prewarm_run=_prewarm_run,
        databento_svc=_FakeDatabentoService(),
    )
    client = _build_client(services)

    response = client.post(
        "/api/run/diagnose?probe_start=true",
        json={"ticker": "MU", "date": "2025-11-03", "l2_confirm_enabled": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["probe"]["bars"] == 240
    assert payload["coverage"]["ohlcv_1m"]["fully_covered"] is True
    assert payload["coverage"]["best_l2_schema"] == "mbp-10"


def test_run_diagnose_returns_structured_failure():
    async def _prewarm_status(_request):
        return {
            "ticker": "MU",
            "range_start": "2025-11-27",
            "range_end": "2025-11-27",
            "l2_requested": False,
            "use_l2": False,
        }

    async def _prewarm_run(_request):
        raise HTTPException(
            status_code=400, detail="No data available for the specified date/range"
        )

    services = SimpleNamespace(
        prewarm_status=_prewarm_status,
        prewarm_run=_prewarm_run,
        databento_svc=_FakeDatabentoService(),
    )
    client = _build_client(services)

    response = client.post(
        "/api/run/diagnose?probe_start=true",
        json={"ticker": "MU", "date": "2025-11-27"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status_code"] == 400
    assert payload["error_kind"] == "no_ohlcv_data"
    assert "No data available" in payload["error"]


def test_run_diagnose_coverage_only_failure_without_probe():
    async def _prewarm_status(_request):
        return {
            "ticker": "MU",
            "range_start": "2025-12-25",
            "range_end": "2025-12-25",
            "l2_requested": False,
            "use_l2": False,
        }

    async def _prewarm_run(_request):
        raise HTTPException(
            status_code=400, detail="No data available for the specified date/range"
        )

    class _CoverageFailDatabento(_FakeDatabentoService):
        def get_range_coverage(self, ticker, schema, start_date, end_date):
            _ = ticker
            _ = start_date
            _ = end_date
            if str(schema).lower() == "ohlcv-1m":
                return {
                    "schema": "ohlcv-1m",
                    "total_days": 1,
                    "covered_days": [],
                    "missing_days": ["2025-12-25"],
                    "fully_covered": False,
                }
            return super().get_range_coverage(ticker, schema, start_date, end_date)

    services = SimpleNamespace(
        prewarm_status=_prewarm_status,
        prewarm_run=_prewarm_run,
        databento_svc=_CoverageFailDatabento(),
    )
    client = _build_client(services)

    response = client.post(
        "/api/run/diagnose", json={"ticker": "MU", "date": "2025-12-25"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["mode"] == "coverage_only"
    assert payload["error_kind"] == "no_ohlcv_data"
