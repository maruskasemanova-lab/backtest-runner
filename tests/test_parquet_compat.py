from __future__ import annotations

import pandas as pd
import pytest

from data_loader import DataLoader
import src.parquet_compat as parquet_compat
from src.parquet_compat import read_parquet_compat, write_parquet_compat


def test_read_parquet_compat_prefers_polars_lazy_scan(tmp_path, monkeypatch):
    if parquet_compat.pl is None:
        pytest.skip("polars is not available")

    parquet_path = tmp_path / "bars.parquet"
    write_parquet_compat(
        pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    ["2026-02-03T14:30:00Z", "2026-02-03T14:31:00Z"], utc=True
                ),
                "open": [100.0, 101.0],
                "close": [100.5, 101.5],
                "ignored": [1, 2],
            }
        ),
        parquet_path,
        index=False,
    )

    scan_calls = []
    real_scan = parquet_compat.pl.scan_parquet

    def _counting_scan(*args, **kwargs):
        scan_calls.append(str(args[0]) if args else "")
        return real_scan(*args, **kwargs)

    def _fail_pandas_read(*args, **kwargs):
        raise AssertionError("pandas.read_parquet should not run when polars succeeds")

    monkeypatch.setattr(parquet_compat.pl, "scan_parquet", _counting_scan)
    monkeypatch.setattr(parquet_compat.pd, "read_parquet", _fail_pandas_read)

    frame = read_parquet_compat(parquet_path, columns=["timestamp", "open", "close"])

    assert scan_calls == [str(parquet_path)]
    assert list(frame.columns) == ["timestamp", "open", "close"]
    assert len(frame.index) == 2
    assert frame["open"].tolist() == [100.0, 101.0]


def test_data_loader_load_parquet_keeps_projection_compatible_with_alt_columns(tmp_path):
    parquet_path = tmp_path / "alt_bars.parquet"
    write_parquet_compat(
        pd.DataFrame(
            {
                "ts_event": [
                    "2026-02-03T14:30:00Z",
                    "2026-02-03T14:31:00Z",
                ],
                "Open": [100.0, 101.0],
                "High": [101.0, 102.0],
                "Low": [99.0, 100.0],
                "Close": [100.5, 101.5],
                "Volume": [1000, 1100],
                "vwap": [100.25, 101.25],
                "ignored": [1, 2],
            }
        ),
        parquet_path,
        index=False,
    )

    loader = DataLoader(data_dirs=[str(tmp_path)])
    frame = loader.load_parquet(
        parquet_path.name,
        columns=loader.preferred_parquet_columns(),
    )

    assert "timestamp" in frame.columns
    assert frame["close"].tolist() == [100.5, 101.5]

    bars = list(loader.get_bars_iterator(frame))
    assert len(bars) == 2
    assert bars[0]["index"] == 0
    assert bars[0]["vwap"] == 100.25
    assert bars[1]["close"] == 101.5


def test_data_loader_load_parquet_bars_for_range_uses_direct_polars_path(tmp_path):
    parquet_path = tmp_path / "bars_range.parquet"
    write_parquet_compat(
        pd.DataFrame(
            {
                "ts_event": [
                    "2026-02-03T14:00:00Z",
                    "2026-02-03T14:30:00Z",
                    "2026-02-03T21:30:00Z",
                ],
                "Open": [99.0, 100.0, 101.0],
                "High": [99.5, 101.0, 101.5],
                "Low": [98.5, 99.0, 100.5],
                "Close": [99.25, 100.5, 101.25],
                "Volume": [900, 1000, 1100],
                "vwap": [99.1, 100.25, 101.1],
            }
        ),
        parquet_path,
        index=False,
    )

    loader = DataLoader(data_dirs=[str(tmp_path)])
    bars = loader.load_parquet_bars_for_range(
        [parquet_path.name],
        start_date="2026-02-03",
        end_date="2026-02-03",
        include_premarket=False,
    )

    assert len(bars) == 1
    assert bars[0]["index"] == 0
    assert bars[0]["close"] == 100.5
    assert bars[0]["vwap"] == 100.25
