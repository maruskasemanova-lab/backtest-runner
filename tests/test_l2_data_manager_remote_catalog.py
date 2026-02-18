from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.l2_data_manager import L2DataManager


class _StubRemoteCatalog:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.calls = []

    def get_files_for_range(self, *, ticker: str, start_date: str, end_date: str, schema_prefix: str):
        self.calls.append(
            {
                "ticker": ticker,
                "start_date": start_date,
                "end_date": end_date,
                "schema_prefix": schema_prefix,
            }
        )
        return [str(self.file_path)]


def test_load_data_uses_remote_catalog_when_local_files_missing(tmp_path: Path):
    remote_file = tmp_path / "MU_2026-02-12_2026-02-12.parquet"
    df = pd.DataFrame(
        {
            "action": ["T", "T"],
            "side": ["B", "A"],
            "price": [100.25, 100.0],
            "size": [10, 8],
        },
        index=pd.to_datetime(
            [
                "2026-02-12T14:30:01Z",
                "2026-02-12T14:30:02Z",
            ],
            utc=True,
        ),
    )
    df.to_parquet(remote_file)

    manager = L2DataManager(data_dirs=[str(tmp_path / "missing-local-l2-root")])
    remote_catalog = _StubRemoteCatalog(remote_file)
    manager.databento_service = remote_catalog

    loaded = manager.load_data("MU", "2026-02-12", "2026-02-12")

    assert loaded is not None
    assert not loaded.empty
    assert remote_catalog.calls
    assert remote_catalog.calls[0]["schema_prefix"] == "mbp-10"
