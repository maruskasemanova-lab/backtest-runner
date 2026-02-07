from pathlib import Path

import pandas as pd

from src.databento_service import CatalogEntry, DataCatalog, DatabentoService


def _make_service(tmp_path: Path) -> DatabentoService:
    svc = DatabentoService.__new__(DatabentoService)
    svc.catalog = DataCatalog(str(tmp_path / "catalog.json"))
    svc._active_downloads = {}
    svc.l2_dir = tmp_path / "l2"
    svc.ohlcv_dir = tmp_path / "ohlcv"
    svc._project_root = tmp_path
    svc._ohlcv_scan_dirs = [svc.ohlcv_dir]
    svc._l2_scan_dirs = [svc.l2_dir]
    svc._ohlcv_range_cache = {}
    return svc


def test_get_files_for_range_uses_actual_ohlcv_coverage(tmp_path: Path):
    svc = _make_service(tmp_path)
    svc.ohlcv_dir.mkdir(parents=True, exist_ok=True)

    csv_path = svc.ohlcv_dir / "MU_ohlcv-1m_2026-02-04_2026-02-05.csv"
    df = pd.DataFrame(
        {
            "timestamp": [
                "2026-02-04 09:00:00+00:00",
                "2026-02-04 09:01:00+00:00",
                "2026-02-04 23:59:00+00:00",
            ],
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200],
        }
    )
    df.to_csv(csv_path, index=False)

    svc.catalog.upsert(
        CatalogEntry(
            ticker="MU",
            schema="ohlcv-1m",
            dataset="XNAS.ITCH",
            start_date="2026-02-04",
            end_date="2026-02-05",  # filename/catalog says 02-05, data does not
            file_csv=str(csv_path),
            status="ready",
            managed=True,
        )
    )

    # Real ET coverage is only 2026-02-04, so 2026-02-05 must not match.
    assert svc.get_files_for_range("MU", "2026-02-05", "2026-02-05", "ohlcv-") == []
    day4_files = svc.get_files_for_range("MU", "2026-02-04", "2026-02-04", "ohlcv-")
    assert day4_files == [str(csv_path)]


def test_available_data_summary_uses_effective_ohlcv_dates(tmp_path: Path):
    svc = _make_service(tmp_path)
    svc.ohlcv_dir.mkdir(parents=True, exist_ok=True)

    csv_path = svc.ohlcv_dir / "MU_ohlcv-1m_2026-02-04_2026-02-05.csv"
    pd.DataFrame(
        {
            "timestamp": [
                "2026-02-04 09:00:00+00:00",
                "2026-02-04 23:59:00+00:00",
            ],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        }
    ).to_csv(csv_path, index=False)

    svc.catalog.upsert(
        CatalogEntry(
            ticker="MU",
            schema="ohlcv-1m",
            dataset="XNAS.ITCH",
            start_date="2026-02-04",
            end_date="2026-02-05",
            file_csv=str(csv_path),
            status="ready",
            managed=True,
        )
    )

    summary = svc.get_available_data_summary(refresh=False)
    assert summary["date_ranges"]["MU"]["start"] == "2026-02-04"
    assert summary["date_ranges"]["MU"]["end"] == "2026-02-04"
