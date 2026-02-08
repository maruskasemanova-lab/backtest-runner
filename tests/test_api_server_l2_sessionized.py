from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


_API_SERVER_PATH = Path(__file__).resolve().parents[1] / "api_server.py"
_PROJECT_ROOT = str(_API_SERVER_PATH.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_API_SERVER_SPEC = importlib.util.spec_from_file_location("api_server_module", _API_SERVER_PATH)
assert _API_SERVER_SPEC is not None and _API_SERVER_SPEC.loader is not None
api_server = importlib.util.module_from_spec(_API_SERVER_SPEC)
_API_SERVER_SPEC.loader.exec_module(api_server)


def _minute_key(ts_iso: str) -> int:
    return int(api_server._to_utc_datetime(ts_iso).timestamp() // 60)


def test_normalize_l2_feature_map_for_market_day_sessions_resets_day_scoped_fields() -> None:
    ts_1 = "2026-01-20T14:30:00+00:00"
    ts_2 = "2026-01-20T14:31:00+00:00"
    ts_3 = "2026-01-21T14:30:00+00:00"
    ts_4 = "2026-01-21T14:31:00+00:00"

    k1, k2, k3, k4 = (_minute_key(ts_1), _minute_key(ts_2), _minute_key(ts_3), _minute_key(ts_4))
    feature_map = {
        k1: {"l2_delta": 2.0, "l2_cumulative_delta": 102.0, "l2_delta_acceleration": 99.0, "l2_book_pressure": 0.10, "l2_book_pressure_delta": 5.0},
        k2: {"l2_delta": -1.0, "l2_cumulative_delta": 101.0, "l2_delta_acceleration": -77.0, "l2_book_pressure": 0.30, "l2_book_pressure_delta": -3.0},
        k3: {"l2_delta": 5.0, "l2_cumulative_delta": 205.0, "l2_delta_acceleration": 44.0, "l2_book_pressure": -0.20, "l2_book_pressure_delta": 4.0},
        k4: {"l2_delta": 1.0, "l2_cumulative_delta": 206.0, "l2_delta_acceleration": -11.0, "l2_book_pressure": 0.10, "l2_book_pressure_delta": -2.0},
    }
    bars = [{"timestamp": ts_1}, {"timestamp": ts_2}, {"timestamp": ts_3}, {"timestamp": ts_4}]

    stats = api_server._normalize_l2_feature_map_for_market_day_sessions(feature_map, bars)

    assert stats == {"sessionized_days": 2, "sessionized_minutes": 4}

    assert feature_map[k1]["l2_cumulative_delta"] == pytest.approx(2.0)
    assert feature_map[k2]["l2_cumulative_delta"] == pytest.approx(1.0)
    assert feature_map[k3]["l2_cumulative_delta"] == pytest.approx(5.0)
    assert feature_map[k4]["l2_cumulative_delta"] == pytest.approx(6.0)

    assert feature_map[k1]["l2_delta_acceleration"] == pytest.approx(2.0)
    assert feature_map[k2]["l2_delta_acceleration"] == pytest.approx(-3.0)
    assert feature_map[k3]["l2_delta_acceleration"] == pytest.approx(5.0)
    assert feature_map[k4]["l2_delta_acceleration"] == pytest.approx(-4.0)

    assert feature_map[k1]["l2_book_pressure_delta"] == pytest.approx(0.0)
    assert feature_map[k2]["l2_book_pressure_delta"] == pytest.approx(0.20)
    assert feature_map[k3]["l2_book_pressure_delta"] == pytest.approx(0.0)
    assert feature_map[k4]["l2_book_pressure_delta"] == pytest.approx(0.30)


def test_normalize_l2_feature_map_for_market_day_sessions_ignores_missing_minutes() -> None:
    ts_1 = "2026-01-20T14:30:00+00:00"
    ts_missing = "2026-01-20T14:31:00+00:00"
    k1 = _minute_key(ts_1)

    feature_map = {
        k1: {"l2_delta": 1.5, "l2_cumulative_delta": 100.0, "l2_book_pressure": 0.2},
    }
    bars = [{"timestamp": ts_1}, {"timestamp": ts_missing}]

    stats = api_server._normalize_l2_feature_map_for_market_day_sessions(feature_map, bars)

    assert stats == {"sessionized_days": 1, "sessionized_minutes": 1}
    assert feature_map[k1]["l2_cumulative_delta"] == pytest.approx(1.5)
    assert feature_map[k1]["l2_delta_acceleration"] == pytest.approx(1.5)
    assert feature_map[k1]["l2_book_pressure_delta"] == pytest.approx(0.0)


def test_normalize_l2_feature_map_for_market_day_sessions_empty() -> None:
    assert api_server._normalize_l2_feature_map_for_market_day_sessions({}, []) == {
        "sessionized_days": 0,
        "sessionized_minutes": 0,
    }
