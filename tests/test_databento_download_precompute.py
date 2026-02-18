from __future__ import annotations

import asyncio
from pathlib import Path

from src.databento_service import CatalogEntry, DataCatalog, DatabentoService


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
    svc._auto_precompute_l2_on_download = True
    svc._auto_precompute_l2_include_icebergs = False
    return svc


def test_download_auto_precomputes_l2_days(monkeypatch, tmp_path: Path):
    svc = _make_service(tmp_path)
    calls = []

    def _fake_blocking_download(ticker, schema, start, end, dataset, convert_to_parquet):
        parquet_file = svc.l2_dir / f"{ticker}_{start}_{end}.parquet"
        parquet_file.write_bytes(b"PAR1")
        return CatalogEntry(
            ticker=ticker,
            schema=schema,
            dataset=dataset,
            start_date=start,
            end_date=end,
            file_parquet=str(parquet_file),
            row_count=100,
            size_bytes=parquet_file.stat().st_size,
            status="ready",
            source_root=str(svc.l2_dir),
            managed=True,
        )

    def _fake_blocking_precompute_l2_day(ticker, day, include_icebergs):
        calls.append((ticker, day, include_icebergs))
        return {
            "built": True,
            "ticker": ticker,
            "day": day,
            "minutes": 900,
            "file": str(tmp_path / f"{ticker}_{day}.parquet"),
        }

    monkeypatch.setattr(svc, "_blocking_download", _fake_blocking_download)
    monkeypatch.setattr(svc, "_blocking_precompute_l2_day", _fake_blocking_precompute_l2_day)

    result = asyncio.run(
        svc.download(
            ticker="MU",
            schema="mbp-10",
            start_date="2026-02-10",
            end_date="2026-02-11",
            convert_to_parquet=True,
        )
    )

    assert result.status == "ready"
    assert calls == [
        ("MU", "2026-02-10", False),
        ("MU", "2026-02-11", False),
    ]


def test_download_does_not_auto_precompute_non_l2(monkeypatch, tmp_path: Path):
    svc = _make_service(tmp_path)
    calls = []

    def _fake_blocking_download(ticker, schema, start, end, dataset, convert_to_parquet):
        csv_file = svc.ohlcv_dir / f"{ticker}_{schema}_{start}_{end}.csv"
        csv_file.write_text("timestamp,open,high,low,close,volume\n")
        return CatalogEntry(
            ticker=ticker,
            schema=schema,
            dataset=dataset,
            start_date=start,
            end_date=end,
            file_csv=str(csv_file),
            row_count=0,
            size_bytes=csv_file.stat().st_size,
            status="ready",
            source_root=str(svc.ohlcv_dir),
            managed=True,
        )

    def _fake_blocking_precompute_l2_day(ticker, day, include_icebergs):
        calls.append((ticker, day, include_icebergs))
        return {"built": True}

    monkeypatch.setattr(svc, "_blocking_download", _fake_blocking_download)
    monkeypatch.setattr(svc, "_blocking_precompute_l2_day", _fake_blocking_precompute_l2_day)

    result = asyncio.run(
        svc.download(
            ticker="MU",
            schema="ohlcv-1m",
            start_date="2026-02-10",
            end_date="2026-02-10",
            convert_to_parquet=True,
        )
    )

    assert result.status == "ready"
    assert calls == []
