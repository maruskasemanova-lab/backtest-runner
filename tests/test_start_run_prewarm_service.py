from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.services import start_run_service as svc


def _build_request(**overrides):
    payload = {
        "ticker": "MU",
        "prewarm_scope": "range",
        "date": None,
        "date_from": "2026-02-03",
        "date_to": "2026-02-03",
        "data_file": "mu_sample.csv",
        "allow_mock_data": False,
        "l2_only": False,
        "l2_confirm_enabled": False,
        "l2_min_delta": 0.0,
        "l2_min_imbalance": 0.0,
        "l2_min_iceberg_bias": 0.0,
        "l2_lookback_bars": 3,
        "l2_min_participation_ratio": 0.0,
        "l2_min_directional_consistency": 0.0,
        "l2_min_signed_aggression": 0.0,
        "strategy_selection_mode": None,
        "max_active_strategies": None,
        "apply_positioning_config_on_start": True,
        "comparable_mode": False,
        "aos_config_path": None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _build_deps():
    return SimpleNamespace(
        logger=SimpleNamespace(info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None),
        data_loader=SimpleNamespace(),
        databento_svc=SimpleNamespace(),
        get_discovery=lambda: SimpleNamespace(),
        to_utc_datetime=lambda value: value,
        build_l2_feature_map=lambda **kwargs: ({}, {}),
        normalize_l2_feature_map_for_market_day_sessions=lambda **kwargs: {},
        attach_l2_features=lambda bars, feature_map, l2_only=False: (bars, {}),
        load_aos_config=lambda *args, **kwargs: {
            "tickers": {
                "MU": {
                    "time_filter_enabled": True,
                    "trading_hours": [9, 10, 11],
                    "l2": {"confirm_enabled": True},
                }
            }
        },
        get_ticker_positioning_config=lambda ticker: {},
    )


def test_prewarm_run_data_respects_aos_l2_defaults(monkeypatch):
    captured = {}

    def _fake_load_run_bars(**kwargs):
        captured["aos_applied"] = kwargs.get("aos_applied")
        return (
            [
                {
                    "timestamp": "2026-02-03T14:30:00Z",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 1000.0,
                }
            ],
            ["mu_sample.csv"],
        )

    def _fake_enrich_bars_with_l2(**kwargs):
        captured["requested_l2_confirm"] = kwargs.get("requested_l2_confirm")
        bars = kwargs.get("bars", [])
        return bars, {"covered_minutes": 1, "bars_with_l2": len(bars), "has_l2": True}, False

    def _fake_load_reference_bars_map(**kwargs):
        return {"2026-02-03T14:30:00+00:00": {"ticker": "QQQ"}}

    monkeypatch.setattr(svc, "load_run_bars", _fake_load_run_bars)
    monkeypatch.setattr(svc, "enrich_bars_with_l2", _fake_enrich_bars_with_l2)
    monkeypatch.setattr(svc, "load_reference_bars_map", _fake_load_reference_bars_map)
    monkeypatch.setattr(svc, "get_start_run_data_cache_stats", lambda: {"memory": {}, "disk": {}})
    monkeypatch.setattr(svc, "get_prewarm_result", lambda key: None)
    monkeypatch.setattr(svc, "set_prewarm_result", lambda key, payload: None)

    result = asyncio.run(svc.prewarm_run_data(_build_request(), _build_deps()))

    assert result["success"] is True
    assert result["bars"] == 1
    assert result["data_files_count"] == 1
    assert result["reference_bars"] == 1
    assert result["use_l2"] is True
    assert captured["requested_l2_confirm"] is True
    assert captured["aos_applied"]["time_filter_enabled"] is True


def test_prewarm_run_data_requires_date_range():
    req = _build_request(date=None, date_from=None, date_to=None)
    deps = _build_deps()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.prewarm_run_data(req, deps))

    assert exc.value.status_code == 400


def test_prewarm_run_data_uses_result_cache_hit(monkeypatch):
    req = _build_request()
    deps = _build_deps()

    cached_payload = {
        "success": True,
        "ticker": "MU",
        "range_start": "2026-02-03",
        "range_end": "2026-02-03",
        "bars": 123,
        "data_files_count": 2,
        "reference_bars": 55,
        "use_l2": True,
        "l2_only": False,
        "l2_confirm_enabled": True,
        "l2_sessionized_by_market_day": False,
        "l2": {"covered_minutes": 123, "bars_with_l2": 123, "has_l2": True},
        "cache_hit": False,
        "cache_key": "cached-key",
        "cache_stats": {"memory": {}, "disk": {}},
    }
    monkeypatch.setattr(svc, "get_prewarm_result", lambda key: dict(cached_payload))
    monkeypatch.setattr(svc, "get_start_run_data_cache_stats", lambda: {"memory": {"prewarm_results": 1}, "disk": {}})

    def _should_not_run(**kwargs):
        raise AssertionError("prewarm cache hit should bypass heavy loaders")

    monkeypatch.setattr(svc, "load_run_bars", _should_not_run)

    result = asyncio.run(svc.prewarm_run_data(req, deps))

    assert result["cache_hit"] is True
    assert result["bars"] == 123
    assert result["use_l2"] is True


def test_prewarm_run_data_ticker_scope_resolves_full_coverage(monkeypatch):
    captured = {}

    def _fake_load_run_bars(**kwargs):
        captured["range_start"] = kwargs.get("range_start")
        captured["range_end"] = kwargs.get("range_end")
        return (
            [
                {
                    "timestamp": "2026-02-03T14:30:00Z",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 1000.0,
                }
            ],
            ["mu_sample.csv"],
        )

    monkeypatch.setattr(svc, "load_run_bars", _fake_load_run_bars)
    monkeypatch.setattr(
        svc,
        "enrich_bars_with_l2",
        lambda **kwargs: (
            kwargs.get("bars", []),
            {"covered_minutes": 1, "bars_with_l2": 1, "has_l2": True},
            False,
        ),
    )
    monkeypatch.setattr(svc, "load_reference_bars_map", lambda **kwargs: {})
    monkeypatch.setattr(svc, "get_start_run_data_cache_stats", lambda: {"memory": {}, "disk": {}})
    monkeypatch.setattr(svc, "get_prewarm_result", lambda key: None)
    monkeypatch.setattr(svc, "set_prewarm_result", lambda key, payload: None)

    req = _build_request(
        prewarm_scope="ticker",
        date=None,
        date_from=None,
        date_to=None,
    )
    deps = _build_deps()
    deps.databento_svc = SimpleNamespace(
        scan_existing_files=lambda: None,
        get_available_data_summary=lambda refresh=False: {
            "date_ranges": {"MU": {"start": "2025-11-03", "end": "2026-02-10"}}
        },
    )

    result = asyncio.run(svc.prewarm_run_data(req, deps))

    assert result["success"] is True
    assert result["prewarm_scope"] == "ticker"
    assert result["range_start"] == "2025-11-03"
    assert result["range_end"] == "2026-02-10"
    assert captured["range_start"] == "2025-11-03"
    assert captured["range_end"] == "2026-02-10"


def test_prewarm_run_data_ticker_scope_disables_l2_for_large_ranges(monkeypatch):
    captured = {}

    def _fake_load_run_bars(**kwargs):
        return (
            [
                {
                    "timestamp": "2026-02-03T14:30:00Z",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 1000.0,
                }
            ],
            ["mu_sample.csv"],
        )

    def _fake_enrich_bars_with_l2(**kwargs):
        captured["requested_l2_only"] = kwargs.get("requested_l2_only")
        captured["requested_l2_confirm"] = kwargs.get("requested_l2_confirm")
        bars = kwargs.get("bars", [])
        return bars, {"covered_minutes": 0, "bars_with_l2": 0, "has_l2": False}, False

    monkeypatch.setattr(svc, "load_run_bars", _fake_load_run_bars)
    monkeypatch.setattr(svc, "enrich_bars_with_l2", _fake_enrich_bars_with_l2)
    monkeypatch.setattr(svc, "load_reference_bars_map", lambda **kwargs: {})
    monkeypatch.setattr(svc, "get_start_run_data_cache_stats", lambda: {"memory": {}, "disk": {}})
    monkeypatch.setattr(svc, "get_prewarm_result", lambda key: None)
    monkeypatch.setattr(svc, "set_prewarm_result", lambda key, payload: None)
    monkeypatch.setattr(svc, "PREWARM_TICKER_SCOPE_L2_MAX_DAYS", 3)
    monkeypatch.setattr(svc, "PREWARM_TICKER_SCOPE_L2_FORCE", False)

    req = _build_request(
        prewarm_scope="ticker",
        date=None,
        date_from=None,
        date_to=None,
        l2_confirm_enabled=True,
    )
    deps = _build_deps()
    deps.databento_svc = SimpleNamespace(
        scan_existing_files=lambda: None,
        get_available_data_summary=lambda refresh=False: {
            "date_ranges": {"MU": {"start": "2025-11-03", "end": "2026-02-10"}}
        },
    )

    result = asyncio.run(svc.prewarm_run_data(req, deps))

    assert captured["requested_l2_only"] is False
    assert captured["requested_l2_confirm"] is False
    assert result["l2_requested"] is True
    assert result["use_l2"] is False
    assert isinstance(result.get("l2_guard_reason"), str)
    assert "L2 prewarm skipped for ticker scope" in result["l2_guard_reason"]


def test_prewarm_run_data_range_scope_disables_l2_for_large_ranges(monkeypatch):
    captured = {}

    def _fake_load_run_bars(**kwargs):
        return (
            [
                {
                    "timestamp": "2025-11-03T14:30:00Z",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 1000.0,
                }
            ],
            ["mu_sample.csv"],
        )

    def _fake_enrich_bars_with_l2(**kwargs):
        captured["requested_l2_only"] = kwargs.get("requested_l2_only")
        captured["requested_l2_confirm"] = kwargs.get("requested_l2_confirm")
        bars = kwargs.get("bars", [])
        return bars, {"covered_minutes": 0, "bars_with_l2": 0, "has_l2": False}, False

    monkeypatch.setattr(svc, "load_run_bars", _fake_load_run_bars)
    monkeypatch.setattr(svc, "enrich_bars_with_l2", _fake_enrich_bars_with_l2)
    monkeypatch.setattr(svc, "load_reference_bars_map", lambda **kwargs: {})
    monkeypatch.setattr(svc, "get_start_run_data_cache_stats", lambda: {"memory": {}, "disk": {}})
    monkeypatch.setattr(svc, "get_prewarm_result", lambda key: None)
    monkeypatch.setattr(svc, "set_prewarm_result", lambda key, payload: None)
    monkeypatch.setattr(svc, "RUN_L2_MAX_DAYS", 3)
    monkeypatch.setattr(svc, "RUN_L2_FORCE", False)

    req = _build_request(
        prewarm_scope="range",
        date_from="2025-11-03",
        date_to="2025-11-07",
        l2_confirm_enabled=True,
    )
    deps = _build_deps()
    deps.databento_svc = SimpleNamespace(
        scan_existing_files=lambda: None,
        get_available_data_summary=lambda refresh=False: {"date_ranges": {}},
    )

    result = asyncio.run(svc.prewarm_run_data(req, deps))

    assert captured["requested_l2_only"] is False
    assert captured["requested_l2_confirm"] is False
    assert result["l2_requested"] is True
    assert result["use_l2"] is False
    assert isinstance(result.get("l2_guard_reason"), str)
    assert "L2 prewarm skipped for range scope" in result["l2_guard_reason"]
