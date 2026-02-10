from __future__ import annotations

import asyncio
import importlib.util
import json
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


def _base_request(**overrides):
    payload = {
        "ticker": "MU",
        "date_from": "2026-02-03",
        "date_to": "2026-02-05",
        "strategy_api_url": "http://localhost:8001",
        "method": "grid",
        "adaptive_version": 1,
    }
    payload.update(overrides)
    return api_server.AdaptiveTunerRequest(**payload)


def test_build_adaptive_tuner_search_space_normalizes_values() -> None:
    request = _base_request(
        selection_modes=["all_enabled", "anything-else"],
        max_active_options=[-9, 3, 999, 3],
        min_active_bars_options=[-5, 4, 4],
        switch_cooldown_bars_options=[0, 7, 999],
        flow_bias_options=[True, True, False],
        ohlcv_fallback_options=[False, False],
    )

    search_space = api_server._build_adaptive_tuner_search_space(request)

    assert search_space["strategy_selection_mode"] == ["all_enabled", "adaptive_top_n"]
    assert search_space["max_active_strategies"] == [1, 3, 20]
    assert search_space["min_active_bars_before_switch"] == [0, 4]
    assert search_space["switch_cooldown_bars"] == [0, 7, 500]
    assert search_space["flow_bias_enabled"] == [True, False]
    assert search_space["use_ohlcv_fallbacks"] == [False]


def test_compute_tuner_score_penalizes_zero_trades() -> None:
    score = api_server._compute_tuner_score(
        score_metric="pnl_pct",
        total_pnl_pct=2.0,
        total_pnl_dollars=200.0,
        avg_win_rate_pct=60.0,
        total_trades=0,
        valid_days=2,
    )
    assert score == pytest.approx(0.0)


def test_run_adaptive_tuner_rejects_non_v1() -> None:
    request = _base_request(adaptive_version=2)

    with pytest.raises(api_server.HTTPException) as exc:
        asyncio.run(api_server.run_adaptive_tuner(request))

    assert exc.value.status_code == 400
    assert "version 1" in str(exc.value.detail).lower()


def test_run_adaptive_tuner_creates_job_and_schedules_worker(monkeypatch) -> None:
    api_server.adaptive_tuner_jobs.clear()
    scheduled = []

    class _FakeUUID:
        hex = "job123"

    def _fake_create_task(coro):
        scheduled.append(coro)

        class _Task:
            def cancel(self):
                return True

        return _Task()

    monkeypatch.setattr(api_server, "uuid4", lambda: _FakeUUID())
    monkeypatch.setattr(api_server.asyncio, "create_task", _fake_create_task)

    request = _base_request(method="optuna")
    result = asyncio.run(api_server.run_adaptive_tuner(request))

    assert result["job_id"] == "job123"
    assert result["status"] == "queued"
    assert result["adaptive_version"] == 1
    assert result["effective_days"] == 3
    assert "job123" in api_server.adaptive_tuner_jobs
    assert api_server.adaptive_tuner_jobs["job123"]["progress"]["method"] == "optuna"
    assert api_server.adaptive_tuner_jobs["job123"]["effective_dates"] == [
        "2026-02-03",
        "2026-02-04",
        "2026-02-05",
    ]
    assert len(scheduled) == 1

    # Close coroutine to avoid "was never awaited" warnings in tests.
    scheduled[0].close()
    api_server.adaptive_tuner_jobs.clear()


def test_resolve_l2_tuning_dates_intersection(monkeypatch) -> None:
    def _fake_coverage(*, schema, **kwargs):
        if schema == "ohlcv-1m":
            return {"covered_days": ["2026-02-03", "2026-02-04", "2026-02-05"]}
        return {"covered_days": ["2026-02-04", "2026-02-05", "2026-02-06"]}

    monkeypatch.setattr(api_server.databento_svc, "get_range_coverage", _fake_coverage)
    dates = api_server._resolve_l2_tuning_dates(
        ticker="MU",
        date_from="2026-02-03",
        date_to="2026-02-06",
        l2_required=True,
    )
    assert dates == ["2026-02-04", "2026-02-05"]


def test_run_adaptive_tuner_requires_overlap_when_l2_required(monkeypatch) -> None:
    def _empty_cov(*args, **kwargs):
        return {"covered_days": []}

    monkeypatch.setattr(api_server.databento_svc, "get_range_coverage", _empty_cov)
    request = _base_request(l2_required=True)
    with pytest.raises(api_server.HTTPException) as exc:
        asyncio.run(api_server.run_adaptive_tuner(request))
    assert exc.value.status_code == 400
    assert "no eligible dates" in str(exc.value.detail).lower()


def test_apply_adaptive_tuner_profile_updates_aos_config(monkeypatch, tmp_path) -> None:
    temp_aos = tmp_path / "aos_config.json"
    temp_aos.write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "tickers": {
                    "MU": {
                        "strategy_selection_mode": "adaptive_top_n",
                        "max_active_strategies": 2,
                        "adaptive": {"version": 1, "flow_bias_enabled": True},
                        "adaptive_tuner_profiles": [
                            {
                                "profile_id": "p123",
                                "adaptive_version": 1,
                                "candidate": {
                                    "strategy_selection_mode": "all_enabled",
                                    "max_active_strategies": 5,
                                    "min_active_bars_before_switch": 3,
                                    "switch_cooldown_bars": 2,
                                    "flow_bias_enabled": False,
                                    "use_ohlcv_fallbacks": True,
                                },
                            }
                        ],
                    }
                },
            }
        )
    )
    monkeypatch.setattr(api_server, "AOS_CONFIG_PATH", temp_aos)

    request = api_server.AdaptiveTunerProfileApplyRequest(ticker="MU", profile_id="p123")
    result = asyncio.run(api_server.apply_adaptive_tuner_profile(request))
    assert result["success"] is True
    assert result["profile_id"] == "p123"

    saved = json.loads(temp_aos.read_text())
    mu_cfg = saved["tickers"]["MU"]
    assert mu_cfg["strategy_selection_mode"] == "all_enabled"
    assert mu_cfg["max_active_strategies"] == 5
    assert mu_cfg["adaptive"]["min_active_bars_before_switch"] == 3
    assert mu_cfg["adaptive"]["switch_cooldown_bars"] == 2
    assert mu_cfg["adaptive"]["flow_bias_enabled"] is False
    assert mu_cfg["active_adaptive_tuner_profile_id"] == "p123"
