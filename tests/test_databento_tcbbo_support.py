from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.databento_service import DataCatalog, DatabentoService


def _make_service(tmp_path: Path) -> DatabentoService:
    svc = DatabentoService.__new__(DatabentoService)
    svc.catalog = DataCatalog(str(tmp_path / "catalog.json"))
    svc._active_downloads = {}
    svc.l2_dir = tmp_path / "l2"
    svc.ohlcv_dir = tmp_path / "ohlcv"
    svc.l2_dir.mkdir(parents=True, exist_ok=True)
    svc.ohlcv_dir.mkdir(parents=True, exist_ok=True)
    svc._project_root = tmp_path
    svc._ohlcv_scan_dirs = [svc.ohlcv_dir]
    svc._l2_scan_dirs = [svc.l2_dir]
    svc._refresh_data_roots = lambda: None
    return svc


def test_parse_tcbbo_basename_supports_compact_dates():
    parsed = DatabentoService._parse_tcbbo_basename("MU_OPRA_tcbbo_20260126_20260130")
    assert parsed == ("MU", "tcbbo", "2026-01-26", "2026-01-30")


def test_scan_existing_files_registers_tcbbo(tmp_path: Path):
    svc = _make_service(tmp_path)
    tcbbo_path = svc.ohlcv_dir / "MU_OPRA_tcbbo_20260126_20260130.parquet"
    pd.DataFrame(
        {
            "ts_event": ["2026-01-26T14:30:00.000000000Z"],
            "symbol": ["MU    260130C00100000"],
            "price": [1.0],
            "size": [1],
            "bid_px_00": [0.95],
            "ask_px_00": [1.05],
            "action": ["T"],
            "side": ["N"],
        }
    ).to_parquet(tcbbo_path, index=False)

    entries = svc.scan_existing_files()
    assert entries
    found = svc.catalog.find("MU", "tcbbo", "2026-01-26", "2026-01-30")
    assert found is not None
    assert found["dataset"] == "OPRA.PILLAR"
    assert found["file_parquet"] == str(tcbbo_path)


def test_get_cost_estimate_tcbbo_uses_parent_symbology(tmp_path: Path):
    svc = _make_service(tmp_path)
    calls = {}

    class _FakeMetadata:
        def get_cost(self, **kwargs):
            calls.update(kwargs)
            return 7.25

    class _FakeClient:
        metadata = _FakeMetadata()

    svc._get_client = lambda: _FakeClient()

    result = svc.get_cost_estimate(
        ticker="MU",
        schema="tcbbo",
        start="2026-01-26",
        end="2026-01-30",
        dataset="XNAS.ITCH",
    )

    assert result["estimated_cost_usd"] == 7.25
    assert result["dataset"] == "OPRA.PILLAR"
    assert calls["dataset"] == "OPRA.PILLAR"
    assert calls["symbols"] == ["MU.OPT"]
    assert calls["stype_in"] == "parent"
    assert calls["schema"] == "tcbbo"
    assert calls["start"] == "2026-01-26"
    assert calls["end"] == "2026-01-31"


def test_blocking_download_tcbbo_writes_parquet(tmp_path: Path):
    svc = _make_service(tmp_path)
    calls = {}

    payload = pd.DataFrame(
        {
            "ts_event": ["2026-01-30T14:30:00.000000000Z"],
            "symbol": ["MU    260130C00100000"],
            "price": [1.0],
            "size": [1],
            "bid_px_00": [0.95],
            "ask_px_00": [1.05],
            "action": ["T"],
            "side": ["N"],
        }
    )

    class _FakeData:
        def to_df(self):
            return payload

        def replay(self, _path: str) -> None:
            raise AssertionError("TCBBO branch should not call replay()")

    class _FakeTimeSeries:
        def get_range(self, **kwargs):
            calls.update(kwargs)
            return _FakeData()

    class _FakeClient:
        timeseries = _FakeTimeSeries()

    svc._get_client = lambda: _FakeClient()

    entry = svc._blocking_download(
        ticker="MU",
        schema="tcbbo",
        start="2026-01-30",
        end="2026-01-30",
        dataset="XNAS.ITCH",
        convert_to_parquet=True,
    )

    assert entry.status == "ready"
    assert entry.dataset == "OPRA.PILLAR"
    assert entry.schema == "tcbbo"
    assert entry.file_parquet is not None
    assert Path(entry.file_parquet).exists()
    assert Path(entry.file_parquet).name == "MU_OPRA_tcbbo_20260130_20260130.parquet"
    assert entry.row_count == 1
    assert calls["dataset"] == "OPRA.PILLAR"
    assert calls["symbols"] == ["MU.OPT"]
    assert calls["stype_in"] == "parent"
    assert calls["schema"] == "tcbbo"
