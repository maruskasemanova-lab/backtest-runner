from pathlib import Path

import pytest

from src.databento_service import CatalogEntry, DataCatalog, DatabentoService


def _make_service(tmp_path: Path) -> DatabentoService:
    svc = DatabentoService.__new__(DatabentoService)
    svc.catalog = DataCatalog(str(tmp_path / "catalog.json"))
    svc._active_downloads = {}
    svc.l2_dir = tmp_path / "l2"
    svc.ohlcv_dir = tmp_path / "ohlcv"
    svc._project_root = tmp_path
    return svc


def test_iter_days_is_inclusive():
    assert DatabentoService._iter_days("2026-02-03", "2026-02-05") == [
        "2026-02-03",
        "2026-02-04",
        "2026-02-05",
    ]


def test_iter_days_rejects_reversed_range():
    with pytest.raises(ValueError):
        DatabentoService._iter_days("2026-02-05", "2026-02-03")


def test_range_coverage_uses_day_overlap(tmp_path: Path):
    svc = _make_service(tmp_path)
    l2_dir = tmp_path / "l2"
    l2_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = l2_dir / "MU_2026-02-03_2026-02-05.parquet"
    parquet_path.write_bytes(b"ok")

    svc.catalog.upsert(
        CatalogEntry(
            ticker="MU",
            schema="mbp-10",
            dataset="XNAS.ITCH",
            start_date="2026-02-03",
            end_date="2026-02-05",
            file_parquet=str(parquet_path),
            status="ready",
            managed=True,
        )
    )

    coverage = svc.get_range_coverage(
        ticker="MU",
        schema="mbp-10",
        start_date="2026-02-03",
        end_date="2026-02-06",
    )

    assert coverage["total_days"] == 4
    assert coverage["covered_days"] == ["2026-02-03", "2026-02-04", "2026-02-05"]
    assert coverage["missing_days"] == ["2026-02-06"]
    assert coverage["fully_covered"] is False


def test_range_coverage_ignores_missing_files(tmp_path: Path):
    svc = _make_service(tmp_path)
    missing_parquet = tmp_path / "l2" / "MU_2026-02-03_2026-02-03.parquet"

    svc.catalog.upsert(
        CatalogEntry(
            ticker="MU",
            schema="mbp-10",
            dataset="XNAS.ITCH",
            start_date="2026-02-03",
            end_date="2026-02-03",
            file_parquet=str(missing_parquet),
            status="ready",
            managed=True,
        )
    )

    coverage = svc.get_range_coverage(
        ticker="MU",
        schema="mbp-10",
        start_date="2026-02-03",
        end_date="2026-02-03",
    )

    assert coverage["covered_days"] == []
    assert coverage["missing_days"] == ["2026-02-03"]
    assert coverage["fully_covered"] is False
