from __future__ import annotations

from pathlib import Path

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
    return svc


def test_blocking_download_mbp10_prefers_to_file(tmp_path: Path):
    svc = _make_service(tmp_path)
    calls = {"to_file": 0, "replay": 0}

    class _FakeData:
        def to_file(self, path: str):
            calls["to_file"] += 1
            Path(path).write_bytes(b"DBN")

        def replay(self, _path: str):  # pragma: no cover - defensive guard
            calls["replay"] += 1
            raise AssertionError("replay() should not be called when to_file exists")

    class _FakeTimeSeries:
        def get_range(self, **_kwargs):
            return _FakeData()

    class _FakeClient:
        timeseries = _FakeTimeSeries()

    svc._get_client = lambda: _FakeClient()

    entry = svc._blocking_download(
        ticker="MU",
        schema="mbp-10",
        start="2026-02-17",
        end="2026-02-17",
        dataset="XNAS.ITCH",
        convert_to_parquet=False,
    )

    assert entry.status == "ready"
    assert entry.file_mbn is not None
    assert Path(entry.file_mbn).exists()
    assert calls["to_file"] == 1
    assert calls["replay"] == 0


def test_blocking_download_mbp10_falls_back_to_replay_path(tmp_path: Path):
    svc = _make_service(tmp_path)
    calls = {"replay": 0}

    class _FakeData:
        def replay(self, path: str):
            calls["replay"] += 1
            Path(path).write_bytes(b"DBN")

    class _FakeTimeSeries:
        def get_range(self, **_kwargs):
            return _FakeData()

    class _FakeClient:
        timeseries = _FakeTimeSeries()

    svc._get_client = lambda: _FakeClient()

    entry = svc._blocking_download(
        ticker="MU",
        schema="mbp-10",
        start="2026-02-17",
        end="2026-02-17",
        dataset="XNAS.ITCH",
        convert_to_parquet=False,
    )

    assert entry.status == "ready"
    assert entry.file_mbn is not None
    assert Path(entry.file_mbn).exists()
    assert calls["replay"] == 1
