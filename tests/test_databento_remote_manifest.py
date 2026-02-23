from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.databento_service import CatalogEntry, DataCatalog, DatabentoService


class _DummyResponse:
    def __init__(self, *, payload=None, content: bytes = b"", status_code: int = 200):
        self._payload = payload
        self._content = content
        self.status_code = int(status_code)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload

    def iter_content(self, chunk_size: int = 1024):
        data = self._content
        for idx in range(0, len(data), max(1, chunk_size)):
            yield data[idx : idx + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyS3Body:
    def __init__(self, payload: bytes):
        self._payload = payload
        self._offset = 0

    def read(self, chunk_size: int = -1) -> bytes:
        if chunk_size is None or chunk_size < 0:
            chunk_size = len(self._payload) - self._offset
        if self._offset >= len(self._payload):
            return b""
        start = self._offset
        end = min(len(self._payload), start + max(1, int(chunk_size)))
        self._offset = end
        return self._payload[start:end]


class _DummyS3Client:
    def __init__(self, objects: dict[tuple[str, str], bytes]):
        self._objects = objects

    def get_object(self, Bucket: str, Key: str):
        payload = self._objects.get((Bucket, Key))
        if payload is None:
            raise KeyError((Bucket, Key))
        return {"Body": _DummyS3Body(payload)}


def _make_service(tmp_path: Path) -> DatabentoService:
    svc = DatabentoService.__new__(DatabentoService)
    svc.catalog = DataCatalog(str(tmp_path / "catalog.json"))
    svc._active_downloads = {}
    svc._project_root = tmp_path
    svc._remote_request_timeout_s = 5.0
    svc._remote_manifest_url = ""
    svc._ohlcv_range_cache = {}
    svc.ohlcv_dir = tmp_path / "ohlcv"
    svc.l2_dir = tmp_path / "l2"
    svc._ohlcv_scan_dirs = [svc.ohlcv_dir]
    svc._l2_scan_dirs = [svc.l2_dir]
    return svc


def test_sync_remote_manifest_upserts_entries(tmp_path: Path, monkeypatch):
    svc = _make_service(tmp_path)

    manifest_payload = {
        "entries": [
            {
                "ticker": "MU",
                "schema": "mbp-10",
                "dataset": "XNAS.ITCH",
                "start_date": "2026-02-10",
                "end_date": "2026-02-10",
                "file_parquet": "https://example.test/mu/l2/MU_2026-02-10_2026-02-10.parquet",
                "size_bytes": 1234,
                "row_count": 321,
                "status": "ready",
            }
        ]
    }

    def _fake_get(url: str, timeout: float = 0, stream: bool = False):
        _ = (url, timeout, stream)
        return _DummyResponse(payload=manifest_payload)

    monkeypatch.setattr("src.databento_service.requests.get", _fake_get)

    synced = svc.sync_remote_manifest("https://example.test/manifest.json")
    assert synced == 1

    rows = svc.list_catalog(refresh=False, ticker="MU")
    assert len(rows) == 1
    row = rows[0]
    assert row["managed"] is False
    assert row["schema"] == "mbp-10"
    assert row["file_parquet"].startswith("https://example.test/")


def test_sync_remote_manifest_from_s3_uri(tmp_path: Path, monkeypatch):
    svc = _make_service(tmp_path)

    manifest_payload = {
        "entries": [
            {
                "ticker": "MU",
                "schema": "mbp-10",
                "dataset": "XNAS.ITCH",
                "start_date": "2026-02-10",
                "end_date": "2026-02-10",
                "file_parquet": "s3://market-data/mu/l2/MU_2026-02-10_2026-02-10.parquet",
                "size_bytes": 99,
                "row_count": 12,
                "status": "ready",
            }
        ]
    }
    dummy_s3 = _DummyS3Client(
        {
            ("market-data", "mu/manifests/mu_janfeb_manifest.json"): bytes(
                json.dumps(manifest_payload), "utf-8"
            ),
        }
    )
    monkeypatch.setattr(svc, "_get_s3_client", lambda: dummy_s3)

    synced = svc.sync_remote_manifest(
        "s3://market-data/mu/manifests/mu_janfeb_manifest.json"
    )
    assert synced == 1

    rows = svc.list_catalog(refresh=False, ticker="MU")
    assert len(rows) == 1
    assert rows[0]["file_parquet"].startswith("s3://market-data/")


def test_remote_coverage_does_not_require_local_file(tmp_path: Path):
    svc = _make_service(tmp_path)
    svc.catalog.upsert(
        CatalogEntry(
            ticker="MU",
            schema="mbp-10",
            dataset="XNAS.ITCH",
            start_date="2026-02-11",
            end_date="2026-02-11",
            file_parquet="https://example.test/mu/l2/MU_2026-02-11_2026-02-11.parquet",
            status="ready",
            managed=False,
        )
    )

    coverage = svc.get_range_coverage(
        ticker="MU",
        schema="mbp-10",
        start_date="2026-02-11",
        end_date="2026-02-11",
    )
    assert coverage["fully_covered"] is True
    assert coverage["covered_days"] == ["2026-02-11"]


def test_get_files_for_range_downloads_remote_file(tmp_path: Path, monkeypatch):
    svc = _make_service(tmp_path)
    svc.catalog.upsert(
        CatalogEntry(
            ticker="MU",
            schema="ohlcv-1m",
            dataset="XNAS.ITCH",
            start_date="2026-02-12",
            end_date="2026-02-12",
            file_csv="https://example.test/mu/ohlcv/MU_ohlcv-1m_2026-02-12_2026-02-12.csv",
            status="ready",
            managed=False,
        )
    )

    csv_payload = (
        b"timestamp,open,high,low,close,volume,symbol\n"
        b"2026-02-12 09:30:00+00:00,1,1,1,1,1,MU\n"
    )

    def _fake_get(url: str, timeout: float = 0, stream: bool = False):
        _ = (url, timeout, stream)
        return _DummyResponse(content=csv_payload)

    monkeypatch.setattr("src.databento_service.requests.get", _fake_get)
    monkeypatch.setenv("BACKTEST_REMOTE_CACHE_DIR", str(tmp_path / "cache"))

    files = svc.get_files_for_range(
        ticker="MU",
        start_date="2026-02-12",
        end_date="2026-02-12",
        schema_prefix="ohlcv-",
    )
    assert len(files) == 1
    cached = Path(files[0])
    assert cached.exists()
    assert cached.read_text(encoding="utf-8").startswith("timestamp,open,high")


def test_get_files_for_range_downloads_s3_file(tmp_path: Path, monkeypatch):
    svc = _make_service(tmp_path)
    svc.catalog.upsert(
        CatalogEntry(
            ticker="MU",
            schema="ohlcv-1m",
            dataset="XNAS.ITCH",
            start_date="2026-02-12",
            end_date="2026-02-12",
            file_csv="s3://market-data/mu/ohlcv/MU_ohlcv-1m_2026-02-12_2026-02-12.csv",
            status="ready",
            managed=False,
        )
    )

    csv_payload = (
        b"timestamp,open,high,low,close,volume,symbol\n"
        b"2026-02-12 09:30:00+00:00,1,1,1,1,1,MU\n"
    )
    dummy_s3 = _DummyS3Client(
        {("market-data", "mu/ohlcv/MU_ohlcv-1m_2026-02-12_2026-02-12.csv"): csv_payload}
    )
    monkeypatch.setattr(svc, "_get_s3_client", lambda: dummy_s3)
    monkeypatch.setenv("BACKTEST_REMOTE_CACHE_DIR", str(tmp_path / "cache"))

    files = svc.get_files_for_range(
        ticker="MU",
        start_date="2026-02-12",
        end_date="2026-02-12",
        schema_prefix="ohlcv-",
    )
    assert len(files) == 1
    cached = Path(files[0])
    assert cached.exists()
    assert cached.read_text(encoding="utf-8").startswith("timestamp,open,high")


def test_available_data_summary_remote_only_filters_local_entries(tmp_path: Path):
    svc = _make_service(tmp_path)
    svc._available_data_remote_only = True

    svc.catalog.upsert(
        CatalogEntry(
            ticker="AAPL",
            schema="mbp-10",
            dataset="XNAS.ITCH",
            start_date="2026-02-10",
            end_date="2026-02-10",
            file_parquet=str(tmp_path / "local" / "AAPL_2026-02-10_2026-02-10.parquet"),
            status="ready",
            managed=True,
        )
    )
    svc.catalog.upsert(
        CatalogEntry(
            ticker="MU",
            schema="mbp-10",
            dataset="XNAS.ITCH",
            start_date="2026-02-10",
            end_date="2026-02-10",
            file_parquet="https://example.test/mu/l2/MU_2026-02-10_2026-02-10.parquet",
            status="ready",
            managed=False,
        )
    )

    summary = svc.get_available_data_summary(refresh=False)
    assert summary["tickers"] == ["MU"]
    assert summary["l2_tickers"] == ["MU"]
    assert summary.get("remote_manifest", {}).get("remote_only") is True


def test_available_data_summary_requires_manifest_tickers(tmp_path: Path, monkeypatch):
    svc = _make_service(tmp_path)
    svc._remote_manifest_required = True
    svc._available_data_remote_only = True
    svc._remote_manifest_url = "https://example.test/manifest.json"
    monkeypatch.setattr(
        svc,
        "_sync_remote_manifest_if_due",
        lambda force=False: {
            "enabled": True,
            "url": "https://example.test/manifest.json",
            "synced_entries": 0,
            "performed": True,
            "forced": bool(force),
        },
    )

    with pytest.raises(RuntimeError, match="yielded no available tickers"):
        svc.get_available_data_summary(refresh=False)


def test_sync_remote_manifest_retries_http_fetch(tmp_path: Path, monkeypatch):
    svc = _make_service(tmp_path)
    attempts = {"count": 0}
    manifest_payload = {
        "entries": [
            {
                "ticker": "MU",
                "schema": "mbp-10",
                "dataset": "XNAS.ITCH",
                "start_date": "2026-02-12",
                "end_date": "2026-02-12",
                "file_parquet": "https://example.test/mu/l2/MU_2026-02-12_2026-02-12.parquet",
                "status": "ready",
            }
        ]
    }

    def _flaky_get(url: str, timeout: float = 0, stream: bool = False):
        _ = (url, timeout, stream)
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary disconnect")
        return _DummyResponse(payload=manifest_payload)

    monkeypatch.setattr("src.databento_service.requests.get", _flaky_get)
    monkeypatch.setattr("src.databento_service.time.sleep", lambda _seconds: None)

    synced = svc.sync_remote_manifest("https://example.test/manifest.json")
    assert synced == 1
    assert attempts["count"] == 2
