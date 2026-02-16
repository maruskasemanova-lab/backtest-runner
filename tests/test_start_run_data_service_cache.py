from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List

import pandas as pd
import pytest

from src.services import start_run_data_service as svc


@dataclass
class _DummyDiscovery:
    files: List[str]

    def get_files_for_range(self, ticker: str, start_date: str, end_date: str) -> List[str]:
        return list(self.files)


@dataclass
class _DummyDatabento:
    files: List[str]

    def scan_existing_files(self) -> None:
        return None

    def get_files_for_range(
        self,
        *,
        ticker: str,
        start_date: str,
        end_date: str,
        schema_prefix: str,
    ) -> List[str]:
        return list(self.files)

    def list_catalog(self, refresh: bool, ticker: str) -> List[Dict[str, Any]]:
        return []


class _DummyDataLoader:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.load_csv_calls = 0
        self.load_parquet_calls = 0

    def load_csv(self, file: str) -> pd.DataFrame:
        self.load_csv_calls += 1
        return self.df.copy()

    def load_parquet(self, file: str) -> pd.DataFrame:
        self.load_parquet_calls += 1
        return self.df.copy()

    def filter_trading_range(self, df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
        return df

    def filter_trading_hours(self, df: pd.DataFrame, trading_hours: List[int]) -> pd.DataFrame:
        return df

    def generate_mock_data(self, ticker: str, date: str) -> pd.DataFrame:
        return self.df.copy()

    def get_bars_iterator(self, df: pd.DataFrame):
        for row in df.itertuples(index=False):
            yield {
                "timestamp": row.timestamp,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
            }


def _sample_df() -> pd.DataFrame:
    ts = pd.date_range("2026-02-03T14:30:00Z", periods=3, freq="1min", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000.0, 1100.0, 1200.0],
        }
    )


def _sample_df_multi_day() -> pd.DataFrame:
    ts = pd.to_datetime(
        [
            "2026-02-03T14:30:00Z",
            "2026-02-04T14:30:00Z",
            "2026-02-05T14:30:00Z",
        ],
        utc=True,
    )
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000.0, 1100.0, 1200.0],
        }
    )


def _sample_df_session_mix() -> pd.DataFrame:
    ts = pd.to_datetime(
        [
            "2026-02-03T14:15:00Z",  # 09:15 ET (pre-market)
            "2026-02-03T14:35:00Z",  # 09:35 ET (regular)
            "2026-02-03T20:30:00Z",  # 15:30 ET (regular)
            "2026-02-03T21:10:00Z",  # 16:10 ET (post-market)
        ],
        utc=True,
    )
    return pd.DataFrame(
        {
            "timestamp": ts,
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
            "volume": [1000.0, 1100.0, 1200.0, 1300.0],
        }
    )


class _RangeFilteringDataLoader(_DummyDataLoader):
    def filter_trading_range(self, df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
        ts = pd.to_datetime(df["timestamp"], utc=True)
        mask = (ts >= pd.Timestamp(f"{start}T00:00:00Z")) & (ts <= pd.Timestamp(f"{end}T23:59:59Z"))
        return df.loc[mask].reset_index(drop=True)


class _SessionScopeDataLoader(_DummyDataLoader):
    def __init__(self, df: pd.DataFrame):
        super().__init__(df)
        self.filter_trading_hours_calls = 0

    def _market_timestamp_series(self, df: pd.DataFrame):
        return pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("America/New_York")

    def filter_trading_hours(self, df: pd.DataFrame, trading_hours: List[int]) -> pd.DataFrame:
        self.filter_trading_hours_calls += 1
        market_ts = self._market_timestamp_series(df)
        normalized = {int(hour) for hour in trading_hours}
        return df.loc[market_ts.dt.hour.isin(normalized)].reset_index(drop=True)


@pytest.fixture
def isolated_disk_cache_dirs(tmp_path, monkeypatch):
    base_dir = tmp_path / "bars_cache"
    ref_dir = tmp_path / "ref_cache"
    l2_dir = tmp_path / "l2_cache"
    monkeypatch.setattr(svc, "_BASE_BARS_DISK_DIR", base_dir)
    monkeypatch.setattr(svc, "_REFERENCE_BARS_DISK_DIR", ref_dir)
    monkeypatch.setattr(svc, "_L2_ENRICH_DISK_DIR", l2_dir)
    svc.clear_start_run_data_caches(include_disk=True)
    yield
    svc.clear_start_run_data_caches(include_disk=True)


def test_load_run_bars_uses_cache_for_same_inputs(isolated_disk_cache_dirs) -> None:
    svc.clear_start_run_data_caches()

    loader = _DummyDataLoader(_sample_df())
    request = SimpleNamespace(data_file="mu_sample.csv", allow_mock_data=False)
    databento = _DummyDatabento(files=[])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    bars_a, files_a = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": True, "trading_hours": [9, 10, 11]},
        logger=logger,
    )
    bars_b, files_b = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": True, "trading_hours": [11, 10, 9]},
        logger=logger,
    )

    assert loader.load_csv_calls == 1
    assert files_a == ["mu_sample.csv"]
    assert files_b == files_a
    assert bars_a == bars_b
    assert bars_a is not bars_b

    bars_a[0]["open"] = 999.0
    bars_c, _ = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": True, "trading_hours": [9, 10, 11]},
        logger=logger,
    )
    assert bars_c[0]["open"] == 100.0


def test_load_run_bars_regular_session_override_excludes_pre_and_post_market(
    isolated_disk_cache_dirs,
) -> None:
    svc.clear_start_run_data_caches()

    loader = _SessionScopeDataLoader(_sample_df_session_mix())
    request = SimpleNamespace(
        data_file="mu_session_mix.csv",
        allow_mock_data=False,
        include_extended_hours=False,
    )
    databento = _DummyDatabento(files=[])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    bars, _ = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": False, "trading_hours": []},
        logger=logger,
    )

    assert len(bars) == 2
    assert str(bars[0]["timestamp"]).startswith("2026-02-03 14:35")
    assert str(bars[1]["timestamp"]).startswith("2026-02-03 20:30")


def test_load_run_bars_include_extended_hours_override_bypasses_aos_hour_filter(
    isolated_disk_cache_dirs,
) -> None:
    svc.clear_start_run_data_caches()

    loader = _SessionScopeDataLoader(_sample_df_session_mix())
    request = SimpleNamespace(
        data_file="mu_session_mix.csv",
        allow_mock_data=False,
        include_extended_hours=True,
    )
    databento = _DummyDatabento(files=[])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    bars, _ = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": True, "trading_hours": [10]},
        logger=logger,
    )

    assert len(bars) == 4
    assert loader.filter_trading_hours_calls == 0


def test_load_reference_bars_map_uses_cache_for_same_inputs(isolated_disk_cache_dirs) -> None:
    svc.clear_start_run_data_caches()

    loader = _DummyDataLoader(_sample_df())
    databento = _DummyDatabento(files=["qqq_sample.csv"])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None)

    ref_a = svc.load_reference_bars_map(
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        logger=logger,
    )
    ref_b = svc.load_reference_bars_map(
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        logger=logger,
    )

    assert loader.load_csv_calls == 1
    assert len(ref_a) == 3
    assert ref_a == ref_b
    assert ref_a is not ref_b

    first_key = next(iter(ref_a))
    ref_a[first_key]["open"] = 555.0

    ref_c = svc.load_reference_bars_map(
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        logger=logger,
    )
    assert ref_c[first_key]["open"] == 100.0


def test_load_run_bars_uses_disk_cache_after_memory_clear(isolated_disk_cache_dirs) -> None:
    request = SimpleNamespace(data_file="mu_sample.csv", allow_mock_data=False)
    databento = _DummyDatabento(files=[])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    loader_first = _DummyDataLoader(_sample_df())
    bars_first, _ = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader_first,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": True, "trading_hours": [9, 10, 11]},
        logger=logger,
    )
    assert loader_first.load_csv_calls == 1

    svc.clear_start_run_data_caches(include_disk=False)

    loader_second = _DummyDataLoader(_sample_df())
    bars_second, _ = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader_second,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": True, "trading_hours": [9, 10, 11]},
        logger=logger,
    )

    assert loader_second.load_csv_calls == 0
    assert bars_second == bars_first


def test_load_run_bars_uses_superset_memory_cache_for_subrange(isolated_disk_cache_dirs) -> None:
    svc.clear_start_run_data_caches()

    loader = _RangeFilteringDataLoader(_sample_df_multi_day())
    request = SimpleNamespace(data_file="mu_sample.csv", allow_mock_data=False)
    databento = _DummyDatabento(files=[])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    bars_full, _ = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-05",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": False, "trading_hours": []},
        logger=logger,
    )
    assert loader.load_csv_calls == 1
    assert len(bars_full) == 3

    bars_subset, _ = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-04",
        range_end="2026-02-04",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": False, "trading_hours": []},
        logger=logger,
    )
    assert loader.load_csv_calls == 1
    assert len(bars_subset) == 1
    assert str(bars_subset[0]["timestamp"]).startswith("2026-02-04")

    bars_subset[0]["open"] = 999.0
    bars_subset_again, _ = svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-04",
        range_end="2026-02-04",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": False, "trading_hours": []},
        logger=logger,
    )
    assert bars_subset_again[0]["open"] == 101.0


def test_load_reference_bars_map_uses_disk_cache_after_memory_clear(isolated_disk_cache_dirs) -> None:
    databento = _DummyDatabento(files=["qqq_sample.csv"])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None)

    loader_first = _DummyDataLoader(_sample_df())
    ref_first = svc.load_reference_bars_map(
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader_first,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        logger=logger,
    )
    assert loader_first.load_csv_calls == 1

    svc.clear_start_run_data_caches(include_disk=False)

    loader_second = _DummyDataLoader(_sample_df())
    ref_second = svc.load_reference_bars_map(
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader_second,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        logger=logger,
    )

    assert loader_second.load_csv_calls == 0
    assert ref_second == ref_first


def test_load_reference_bars_map_uses_superset_memory_cache_for_subrange(isolated_disk_cache_dirs) -> None:
    svc.clear_start_run_data_caches()

    loader = _RangeFilteringDataLoader(_sample_df_multi_day())
    databento = _DummyDatabento(files=["qqq_sample.csv"])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, debug=lambda *args, **kwargs: None)

    ref_full = svc.load_reference_bars_map(
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-05",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        logger=logger,
    )
    assert loader.load_csv_calls == 1
    assert len(ref_full) == 3

    ref_subset = svc.load_reference_bars_map(
        ticker="MU",
        range_start="2026-02-04",
        range_end="2026-02-04",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        logger=logger,
    )
    assert loader.load_csv_calls == 1
    assert len(ref_subset) == 1
    subset_key = next(iter(ref_subset))
    assert str(subset_key).startswith("2026-02-04")

    ref_subset[subset_key]["open"] = 777.0
    ref_subset_again = svc.load_reference_bars_map(
        ticker="MU",
        range_start="2026-02-04",
        range_end="2026-02-04",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        logger=logger,
    )
    assert ref_subset_again[subset_key]["open"] == 101.0


def _sample_bars() -> List[Dict[str, Any]]:
    loader = _DummyDataLoader(_sample_df())
    return list(loader.get_bars_iterator(loader.df))


def _epoch_minute_key(ts: Any) -> int:
    return int(pd.Timestamp(ts).timestamp() // 60)


def test_enrich_bars_with_l2_uses_cache_for_same_inputs(isolated_disk_cache_dirs) -> None:
    bars = _sample_bars()
    counters = {"build": 0, "attach": 0, "normalize": 0}

    def build_l2_feature_map(*, ticker: str, start_dt_utc: Any, end_dt_utc: Any):
        counters["build"] += 1
        feature_map = {
            _epoch_minute_key(bar["timestamp"]): {
                "l2_delta": 1.0,
                "l2_imbalance": 0.2,
                "l2_signed_aggression": 0.1,
            }
            for bar in bars
        }
        return feature_map, {"has_l2": True, "covered_minutes": len(feature_map), "footprint_bars": len(feature_map)}

    def normalize_l2_feature_map_for_market_day_sessions(*, feature_map: Dict[str, Any], bars: List[Dict[str, Any]]):
        counters["normalize"] += 1
        return {"sessionized_days": 1}

    def attach_l2_features(bars: List[Dict[str, Any]], feature_map: Dict[int, Dict[str, float]], l2_only: bool = False):
        counters["attach"] += 1
        enriched = []
        for bar in bars:
            key = _epoch_minute_key(bar["timestamp"])
            feats = feature_map.get(key)
            if feats:
                enriched.append({**bar, **feats})
            elif not l2_only:
                enriched.append(bar)
        return enriched, {"bars_with_l2": len(enriched), "bars_total": len(bars), "bars_after_filter": len(enriched)}

    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    bars_a, stats_a, sessionized_a = svc.enrich_bars_with_l2(
        bars=bars,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        requested_l2_only=False,
        requested_l2_confirm=True,
        comparable_mode=False,
        is_multi_day_request=False,
        aos_l2_config_applied=True,
        to_utc_datetime=lambda value: pd.Timestamp(value).to_pydatetime(),
        build_l2_feature_map=build_l2_feature_map,
        normalize_l2_feature_map_for_market_day_sessions=normalize_l2_feature_map_for_market_day_sessions,
        attach_l2_features=attach_l2_features,
        logger=logger,
    )

    bars_b, stats_b, sessionized_b = svc.enrich_bars_with_l2(
        bars=bars,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        requested_l2_only=False,
        requested_l2_confirm=True,
        comparable_mode=False,
        is_multi_day_request=False,
        aos_l2_config_applied=True,
        to_utc_datetime=lambda value: pd.Timestamp(value).to_pydatetime(),
        build_l2_feature_map=build_l2_feature_map,
        normalize_l2_feature_map_for_market_day_sessions=normalize_l2_feature_map_for_market_day_sessions,
        attach_l2_features=attach_l2_features,
        logger=logger,
    )

    assert counters["build"] == 1
    assert counters["attach"] == 1
    assert counters["normalize"] == 0
    assert bars_b == bars_a
    assert stats_b == stats_a
    assert sessionized_b == sessionized_a


def test_enrich_bars_with_l2_uses_disk_cache_after_memory_clear(isolated_disk_cache_dirs) -> None:
    bars = _sample_bars()
    first_counters = {"build": 0, "attach": 0}
    second_counters = {"build": 0, "attach": 0}

    def build_first(*, ticker: str, start_dt_utc: Any, end_dt_utc: Any):
        first_counters["build"] += 1
        feature_map = {
            _epoch_minute_key(bar["timestamp"]): {"l2_delta": 2.0, "l2_imbalance": 0.3}
            for bar in bars
        }
        return feature_map, {"has_l2": True, "covered_minutes": len(feature_map), "footprint_bars": len(feature_map)}

    def attach_first(bars: List[Dict[str, Any]], feature_map: Dict[int, Dict[str, float]], l2_only: bool = False):
        first_counters["attach"] += 1
        enriched = [{**bar, **feature_map.get(_epoch_minute_key(bar["timestamp"]), {})} for bar in bars]
        return enriched, {"bars_with_l2": len(enriched), "bars_total": len(bars), "bars_after_filter": len(enriched)}

    def build_second(*, ticker: str, start_dt_utc: Any, end_dt_utc: Any):
        second_counters["build"] += 1
        return {}, {"has_l2": False, "covered_minutes": 0, "footprint_bars": 0}

    def attach_second(bars: List[Dict[str, Any]], feature_map: Dict[int, Dict[str, float]], l2_only: bool = False):
        second_counters["attach"] += 1
        return bars, {"bars_with_l2": 0, "bars_total": len(bars), "bars_after_filter": len(bars)}

    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    bars_first, stats_first, _ = svc.enrich_bars_with_l2(
        bars=bars,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        requested_l2_only=False,
        requested_l2_confirm=True,
        comparable_mode=False,
        is_multi_day_request=False,
        aos_l2_config_applied=True,
        to_utc_datetime=lambda value: pd.Timestamp(value).to_pydatetime(),
        build_l2_feature_map=build_first,
        normalize_l2_feature_map_for_market_day_sessions=lambda **kwargs: {},
        attach_l2_features=attach_first,
        logger=logger,
    )

    assert first_counters["build"] == 1
    assert first_counters["attach"] == 1

    svc.clear_start_run_data_caches(include_disk=False)

    bars_second, stats_second, _ = svc.enrich_bars_with_l2(
        bars=bars,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        requested_l2_only=False,
        requested_l2_confirm=True,
        comparable_mode=False,
        is_multi_day_request=False,
        aos_l2_config_applied=True,
        to_utc_datetime=lambda value: pd.Timestamp(value).to_pydatetime(),
        build_l2_feature_map=build_second,
        normalize_l2_feature_map_for_market_day_sessions=lambda **kwargs: {},
        attach_l2_features=attach_second,
        logger=logger,
    )

    assert second_counters["build"] == 0
    assert second_counters["attach"] == 0
    assert bars_second == bars_first
    assert stats_second == stats_first


def test_enrich_bars_with_l2_raises_for_l2_only_missing_day_coverage(isolated_disk_cache_dirs) -> None:
    bars = list(_DummyDataLoader(_sample_df_multi_day()).get_bars_iterator(_sample_df_multi_day()))

    def build_l2_feature_map(*, ticker: str, start_dt_utc: Any, end_dt_utc: Any):
        feature_map = {
            _epoch_minute_key(bars[0]["timestamp"]): {"l2_delta": 1.0},
            _epoch_minute_key(bars[1]["timestamp"]): {"l2_delta": 1.0},
        }
        return feature_map, {"has_l2": True, "covered_minutes": len(feature_map), "footprint_bars": len(feature_map)}

    def attach_l2_features(bars: List[Dict[str, Any]], feature_map: Dict[int, Dict[str, float]], l2_only: bool = False):
        enriched = []
        for bar in bars:
            feats = feature_map.get(_epoch_minute_key(bar["timestamp"]))
            if feats:
                enriched.append({**bar, **feats})
            elif not l2_only:
                enriched.append(bar)
        return enriched, {"bars_with_l2": len(enriched), "bars_total": len(bars), "bars_after_filter": len(enriched)}

    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    with pytest.raises(svc.HTTPException) as exc:
        svc.enrich_bars_with_l2(
            bars=bars,
            ticker="MU",
            range_start="2026-02-03",
            range_end="2026-02-05",
            requested_l2_only=True,
            requested_l2_confirm=False,
            comparable_mode=False,
            is_multi_day_request=True,
            aos_l2_config_applied=True,
            to_utc_datetime=lambda value: pd.Timestamp(value).to_pydatetime(),
            build_l2_feature_map=build_l2_feature_map,
            normalize_l2_feature_map_for_market_day_sessions=lambda **kwargs: {},
            attach_l2_features=attach_l2_features,
            logger=logger,
        )
    assert exc.value.status_code == 400
    assert "missing L2 coverage" in exc.value.detail
    assert "2026-02-05" in exc.value.detail


def test_enrich_bars_with_l2_raises_for_l2_confirm_missing_coverage(isolated_disk_cache_dirs) -> None:
    bars = _sample_bars()

    def build_l2_feature_map(*, ticker: str, start_dt_utc: Any, end_dt_utc: Any):
        return {}, {"has_l2": False, "covered_minutes": 0, "footprint_bars": 0}

    def attach_l2_features(bars: List[Dict[str, Any]], feature_map: Dict[int, Dict[str, float]], l2_only: bool = False):
        return list(bars), {"bars_with_l2": 0, "bars_total": len(bars), "bars_after_filter": len(bars)}

    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    with pytest.raises(svc.HTTPException) as exc:
        svc.enrich_bars_with_l2(
            bars=bars,
            ticker="MU",
            range_start="2026-02-03",
            range_end="2026-02-03",
            requested_l2_only=False,
            requested_l2_confirm=True,
            comparable_mode=False,
            is_multi_day_request=False,
            aos_l2_config_applied=True,
            to_utc_datetime=lambda value: pd.Timestamp(value).to_pydatetime(),
            build_l2_feature_map=build_l2_feature_map,
            normalize_l2_feature_map_for_market_day_sessions=lambda **kwargs: {},
            attach_l2_features=attach_l2_features,
            logger=logger,
        )
    assert exc.value.status_code == 400
    assert "missing L2 coverage" in exc.value.detail
    assert "2026-02-03" in exc.value.detail


def test_flush_start_run_data_cache_clears_memory_and_disk(isolated_disk_cache_dirs) -> None:
    loader = _DummyDataLoader(_sample_df())
    request = SimpleNamespace(data_file="mu_sample.csv", allow_mock_data=False)
    databento = _DummyDatabento(files=[])
    discovery = _DummyDiscovery(files=[])
    logger = SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None)

    svc.load_run_bars(
        request=request,
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        data_loader=loader,
        databento_svc=databento,
        get_discovery=lambda: discovery,
        aos_applied={"time_filter_enabled": True, "trading_hours": [9, 10, 11]},
        logger=logger,
    )

    result = svc.flush_start_run_data_cache(include_disk=True)

    assert result["success"] is True
    assert result["include_disk"] is True
    assert result["before"]["memory"]["base_bars_entries"] >= 1
    assert result["before"]["disk"]["base_bars_entries"] >= 1
    assert result["after"]["memory"]["base_bars_entries"] == 0
    assert result["after"]["disk"]["base_bars_entries"] == 0
