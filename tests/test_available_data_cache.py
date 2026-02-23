from datetime import datetime, timedelta

from available_data import DataDiscovery


def test_scan_refreshes_cache_older_than_day_even_when_seconds_remainder_is_small(
    tmp_path,
):
    discovery = DataDiscovery(data_dir=str(tmp_path))

    first = discovery.scan(force_refresh=True)
    assert "MU" not in first

    (tmp_path / "MU_ohlcv-1m_2025-10-01_2026-02-13.csv").write_text(
        "timestamp,open,high,low,close,volume\n",
        encoding="utf-8",
    )

    discovery._cache_time = datetime.now() - timedelta(days=2, seconds=30)

    refreshed = discovery.scan()
    assert "MU" in refreshed
