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


def test_run_adaptive_tuner_rejects_unsupported_version() -> None:
    request = _base_request(adaptive_version=3)

    with pytest.raises(api_server.HTTPException) as exc:
        asyncio.run(api_server.run_adaptive_tuner(request))

    assert exc.value.status_code == 400
    assert "versions 1 and 2" in str(exc.value.detail).lower()


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


def test_sample_evenly_spaced_days() -> None:
    days = [
        "2026-02-01",
        "2026-02-02",
        "2026-02-03",
        "2026-02-04",
        "2026-02-05",
    ]
    sampled = api_server._sample_evenly_spaced_days(days, max_days=2)
    assert sampled == ["2026-02-01", "2026-02-05"]

    sampled_mid = api_server._sample_evenly_spaced_days(days, max_days=1)
    assert sampled_mid == ["2026-02-03"]


def test_resolve_tuner_trial_budget_quick_mode() -> None:
    standard = api_server._resolve_tuner_trial_budget(
        requested_trials=16,
        default_trials=16,
        quick_mode=False,
        quick_trial_boost=3,
    )
    assert standard == {"requested": 16, "boost": 1, "effective": 16}

    quick = api_server._resolve_tuner_trial_budget(
        requested_trials=16,
        default_trials=16,
        quick_mode=True,
        quick_trial_boost=4,
    )
    assert quick == {"requested": 16, "boost": 4, "effective": 64}


def test_run_adaptive_tuner_requires_overlap_when_l2_required(monkeypatch) -> None:
    def _empty_cov(*args, **kwargs):
        return {"covered_days": []}

    monkeypatch.setattr(api_server.databento_svc, "get_range_coverage", _empty_cov)
    request = _base_request(l2_required=True)
    with pytest.raises(api_server.HTTPException) as exc:
        asyncio.run(api_server.run_adaptive_tuner(request))
    assert exc.value.status_code == 400
    assert "no eligible dates" in str(exc.value.detail).lower()


def test_run_adaptive_tuner_quick_mode_samples_dates_and_sets_metadata(monkeypatch) -> None:
    api_server.adaptive_tuner_jobs.clear()
    scheduled = []

    class _FakeUUID:
        hex = "quickjob789"

    def _fake_create_task(coro):
        scheduled.append(coro)

        class _Task:
            def cancel(self):
                return True

        return _Task()

    monkeypatch.setattr(api_server, "uuid4", lambda: _FakeUUID())
    monkeypatch.setattr(api_server.asyncio, "create_task", _fake_create_task)

    request = _base_request(
        method="random",
        quick_mode=True,
        quick_max_days=2,
        quick_trial_boost=4,
        date_from="2026-02-01",
        date_to="2026-02-05",
    )
    result = asyncio.run(api_server.run_adaptive_tuner(request))

    assert result["job_id"] == "quickjob789"
    assert result["quick_mode"] is True
    assert result["source_effective_days"] == 5
    assert result["effective_days"] == 2

    job = api_server.adaptive_tuner_jobs["quickjob789"]
    assert job["quick_mode"] is True
    assert job["quick_max_days"] == 2
    assert job["quick_trial_boost"] == 4
    assert job["source_effective_days"] == 5
    assert len(job["source_effective_dates"]) == 5
    assert job["effective_dates"] == ["2026-02-01", "2026-02-05"]
    assert len(scheduled) == 1

    scheduled[0].close()
    api_server.adaptive_tuner_jobs.clear()


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


# ============ V2 Multi-Dimensional Vector Discovery Tests ============


def _base_v2_request(**overrides):
    payload = {
        "ticker": "MU",
        "date_from": "2026-02-03",
        "date_to": "2026-02-05",
        "strategy_api_url": "http://localhost:8001",
        "method": "random",
        "adaptive_version": 2,
    }
    payload.update(overrides)
    return api_server.AdaptiveTunerRequest(**payload)


def _ticker_config():
    return {
        "strategy": "momentum_flow",
        "backup_strategy": "absorption_reversal",
        "regime_filter": ["TRENDING", "MIXED"],
        "l2": {
            "min_delta": 800,
            "min_imbalance": 0.15,
            "min_signed_aggression": 0.10,
            "min_directional_consistency": 0.55,
        },
        "adaptive": {
            "version": 1,
            "flow_bias_enabled": True,
            "use_ohlcv_fallbacks": True,
        },
    }


def test_v2_build_search_space_defaults() -> None:
    request = _base_v2_request()
    space = api_server._build_v2_search_space(request, _ticker_config())

    # V1 dims should still be present
    assert "strategy_selection_mode" in space
    assert "flow_bias_enabled" in space

    # V2 strategy sets should include individual + combo
    assert "strategy_sets" in space
    strategy_sets = space["strategy_sets"]
    assert isinstance(strategy_sets, list)
    assert len(strategy_sets) >= 2  # at least momentum_flow alone + both combined
    assert ["momentum_flow"] in strategy_sets

    # L2 options should use ticker config defaults
    assert "l2_min_imbalance" in space
    assert 0.15 in space["l2_min_imbalance"]  # from ticker config

    assert "l2_min_signed_aggression" in space

    # Regime filter sets populated
    assert "regime_filter_sets" in space
    assert len(space["regime_filter_sets"]) >= 2

    # Evidence options
    assert "base_threshold" in space
    assert "min_confirming_sources" in space
    assert 2 in space["min_confirming_sources"]


def test_v2_build_search_space_custom_options() -> None:
    request = _base_v2_request(
        strategy_sets=[["momentum_flow"], ["exhaustion_fade", "pullback"]],
        l2_min_imbalance_options=[0.08, 0.20, 0.40],
        regime_filter_sets=[["TRENDING"], ["CHOPPY", "MIXED"]],
        base_threshold_options=[40.0, 55.0, 70.0],
        min_confirming_sources_options=[1, 3],
    )
    space = api_server._build_v2_search_space(request, _ticker_config())

    assert len(space["strategy_sets"]) == 2
    assert ["momentum_flow"] in space["strategy_sets"]
    assert sorted(["exhaustion_fade", "pullback"]) in space["strategy_sets"]

    assert space["l2_min_imbalance"] == [0.08, 0.20, 0.40]
    assert len(space["regime_filter_sets"]) == 2
    assert space["base_threshold"] == [40.0, 55.0, 70.0]
    assert space["min_confirming_sources"] == [1, 3]


def test_v2_candidate_config_injects_all_dimensions() -> None:
    candidate = {
        "strategy_selection_mode": "all_enabled",
        "max_active_strategies": 4,
        "min_active_bars_before_switch": 2,
        "switch_cooldown_bars": 3,
        "flow_bias_enabled": False,
        "use_ohlcv_fallbacks": True,
        "enabled_strategies": ["exhaustion_fade", "pullback"],
        "l2_min_delta": 2000.0,
        "l2_min_imbalance": 0.25,
        "l2_min_signed_aggression": 0.30,
        "l2_min_directional_consistency": 0.6,
        "regime_filter": ["TRENDING", "CHOPPY"],
        "base_threshold": 60.0,
        "min_confirming_sources": 3,
    }
    cfg = api_server._build_v2_candidate_config(_ticker_config(), candidate, 2)

    # Strategy dimension
    assert cfg["strategy"] == "exhaustion_fade"
    assert cfg["backup_strategy"] == "pullback"

    # L2 dimension
    assert cfg["l2"]["min_delta"] == 2000.0
    assert cfg["l2"]["min_imbalance"] == 0.25
    assert cfg["l2"]["min_signed_aggression"] == 0.30
    assert cfg["l2"]["min_directional_consistency"] == 0.6

    # Regime dimension
    assert cfg["regime_filter"] == ["TRENDING", "CHOPPY"]

    # Evidence dimension
    assert cfg["adaptive"]["evidence_base_threshold"] == 60.0
    assert cfg["adaptive"]["evidence_min_confirming_sources"] == 3

    # V1 dims still applied
    assert cfg["strategy_selection_mode"] == "all_enabled"
    assert cfg["max_active_strategies"] == 4
    assert cfg["adaptive"]["flow_bias_enabled"] is False
    assert cfg["adaptive"]["version"] == 2


def test_v2_analyze_vectors_dimension_importance() -> None:
    trials = [
        {
            "score": 5.0,
            "metrics": {"total_trades": 10},
            "candidate": {
                "enabled_strategies": ["momentum_flow"],
                "regime_filter": ["TRENDING"],
                "l2_min_imbalance": 0.10,
                "l2_min_signed_aggression": 0.10,
                "base_threshold": 50,
                "min_confirming_sources": 2,
                "strategy_selection_mode": "all_enabled",
                "flow_bias_enabled": True,
            },
        },
        {
            "score": 1.0,
            "metrics": {"total_trades": 8},
            "candidate": {
                "enabled_strategies": ["absorption_reversal"],
                "regime_filter": ["CHOPPY"],
                "l2_min_imbalance": 0.30,
                "l2_min_signed_aggression": 0.30,
                "base_threshold": 65,
                "min_confirming_sources": 1,
                "strategy_selection_mode": "adaptive_top_n",
                "flow_bias_enabled": False,
            },
        },
        {
            "score": 4.0,
            "metrics": {"total_trades": 6},
            "candidate": {
                "enabled_strategies": ["momentum_flow"],
                "regime_filter": ["TRENDING"],
                "l2_min_imbalance": 0.20,
                "l2_min_signed_aggression": 0.20,
                "base_threshold": 55,
                "min_confirming_sources": 2,
                "strategy_selection_mode": "all_enabled",
                "flow_bias_enabled": True,
            },
        },
        {
            "score": -0.5,
            "metrics": {"total_trades": 5},
            "candidate": {
                "enabled_strategies": ["absorption_reversal"],
                "regime_filter": ["CHOPPY", "MIXED"],
                "l2_min_imbalance": 0.10,
                "l2_min_signed_aggression": 0.10,
                "base_threshold": 50,
                "min_confirming_sources": 3,
                "strategy_selection_mode": "adaptive_top_n",
                "flow_bias_enabled": False,
            },
        },
    ]
    analysis = api_server._analyze_vectors(trials, min_trades=3)

    assert "dimension_importance" in analysis
    dim_imp = analysis["dimension_importance"]
    assert len(dim_imp) == 5
    # Sum should be ~1.0
    total = sum(dim_imp.values())
    assert abs(total - 1.0) < 0.02, f"importance sum {total} not near 1.0"

    assert "top_interactions" in analysis
    assert isinstance(analysis["top_interactions"], list)

    assert "surprising_vectors" in analysis
    assert "stats" in analysis
    assert analysis["stats"]["total_valid_trials"] == 4


def test_v2_analyze_vectors_interaction_effects() -> None:
    # Create trials with known interaction: strategy + regime combo matters
    trials = []
    for i, (strat, regime, score) in enumerate([
        (["momentum_flow"], ["TRENDING"], 8.0),
        (["momentum_flow"], ["CHOPPY"], 1.0),
        (["absorption_reversal"], ["TRENDING"], 2.0),
        (["absorption_reversal"], ["CHOPPY"], 7.0),
    ]):
        trials.append({
            "score": score,
            "metrics": {"total_trades": 10},
            "candidate": {
                "enabled_strategies": strat,
                "regime_filter": regime,
                "l2_min_imbalance": 0.15,
                "l2_min_signed_aggression": 0.15,
                "base_threshold": 50,
                "min_confirming_sources": 2,
                "strategy_selection_mode": "all_enabled",
                "flow_bias_enabled": True,
            },
        })
    analysis = api_server._analyze_vectors(trials, min_trades=3)

    interactions = analysis["top_interactions"]
    assert len(interactions) > 0
    # The top interaction should involve strategy_set and regime_filter
    top = interactions[0]
    assert "strategy_set" in top["dims"] or "regime_filter" in top["dims"]
    assert top["effect_size"] > 0


def test_v2_backward_compatible_with_v1() -> None:
    """V1 request should still work exactly as before."""
    request = _base_request(adaptive_version=1)
    space = api_server._build_adaptive_tuner_search_space(request)
    assert "strategy_selection_mode" in space
    assert "max_active_strategies" in space
    # V2-only keys should NOT be in v1 search space
    assert "strategy_sets" not in space
    assert "regime_filter_sets" not in space


def test_v2_run_adaptive_tuner_creates_v2_job(monkeypatch) -> None:
    api_server.adaptive_tuner_jobs.clear()
    scheduled = []

    class _FakeUUID:
        hex = "v2job456"

    def _fake_create_task(coro):
        scheduled.append(coro)

        class _Task:
            def cancel(self):
                return True

        return _Task()

    monkeypatch.setattr(api_server, "uuid4", lambda: _FakeUUID())
    monkeypatch.setattr(api_server.asyncio, "create_task", _fake_create_task)

    request = _base_v2_request(method="random")
    result = asyncio.run(api_server.run_adaptive_tuner(request))

    assert result["job_id"] == "v2job456"
    assert result["status"] == "queued"
    assert result["adaptive_version"] == 2
    assert result["effective_days"] == 3
    assert "v2job456" in api_server.adaptive_tuner_jobs
    job = api_server.adaptive_tuner_jobs["v2job456"]
    assert job["adaptive_version"] == 2
    assert job["progress"]["method"] == "random"
    assert len(scheduled) == 1

    scheduled[0].close()
    api_server.adaptive_tuner_jobs.clear()


def test_v2_random_candidates_deduplicate() -> None:
    request = _base_v2_request()
    space = api_server._build_v2_search_space(request, _ticker_config())
    candidates = api_server._build_v2_random_candidates(space, n_trials=20, seed=42)

    keys = set()
    for c in candidates:
        key = api_server._v2_candidate_key(c)
        assert key not in keys, f"Duplicate candidate found: {key}"
        keys.add(key)

    assert len(candidates) <= 20
    assert len(candidates) > 0
    # Every candidate should have v2 keys
    for c in candidates:
        assert "enabled_strategies" in c
        assert "regime_filter" in c
        assert "l2_min_imbalance" in c
        assert "base_threshold" in c


def test_v2_profile_shape() -> None:
    """Profile entry should contain adaptive_version=2 when built from v2 request."""
    request = _base_v2_request()
    best_trial = {
        "score": 3.5,
        "candidate": {
            "enabled_strategies": ["momentum_flow"],
            "regime_filter": ["TRENDING"],
            "l2_min_imbalance": 0.12,
            "base_threshold": 55.0,
        },
        "metrics": {"total_trades": 15, "avg_pnl_pct": 1.2},
    }
    profile = api_server._build_tuner_profile_entry(
        ticker="MU",
        request=request,
        method_used="random",
        dates=["2026-02-03", "2026-02-04"],
        best_trial=best_trial,
    )
    assert profile["adaptive_version"] == 2
    assert profile["ticker"] == "MU"
    assert profile["method"] == "random"
    assert profile["candidate"]["enabled_strategies"] == ["momentum_flow"]
    assert profile["quick_mode"] is False


def test_normalize_float_options() -> None:
    result = api_server._normalize_float_options(
        [0.05, 0.2, 0.2, -1.0, 5.0],
        default=[0.1],
        min_value=0.0,
        max_value=1.0,
    )
    assert result == [0.05, 0.2, 0.0, 1.0]


def test_normalize_strategy_sets() -> None:
    result = api_server._normalize_strategy_sets(
        [["Momentum_Flow"], ["absorption_reversal", "MOMENTUM_FLOW"]],
        enabled_strategies=["momentum_flow"],
    )
    assert ["momentum_flow"] in result
    assert sorted(["absorption_reversal", "momentum_flow"]) in result
    assert len(result) == 2


def test_normalize_regime_filter_sets() -> None:
    result = api_server._normalize_regime_filter_sets(
        [["trending"], ["CHOPPY", "invalid", "MIXED"]],
    )
    assert ["TRENDING"] in result
    assert sorted(["CHOPPY", "MIXED"]) in result
    assert len(result) == 2
