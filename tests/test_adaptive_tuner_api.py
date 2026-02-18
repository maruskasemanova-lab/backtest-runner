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
    assert result["max_parallel_jobs"] == 3
    assert "job123" in api_server.adaptive_tuner_jobs
    assert api_server.adaptive_tuner_jobs["job123"]["progress"]["method"] == "optuna"
    assert api_server.adaptive_tuner_jobs["job123"]["max_parallel_jobs"] == 3
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
    assert result["max_parallel_jobs"] == 3

    job = api_server.adaptive_tuner_jobs["quickjob789"]
    assert job["quick_mode"] is True
    assert job["quick_max_days"] == 2
    assert job["quick_trial_boost"] == 4
    assert job["max_parallel_jobs"] == 3
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
                        "active_strategy_combo_profile_id": "combo123",
                        "active_unified_profile_id": "mu-unified-stale",
                        "adaptive": {"version": 1, "flow_bias_enabled": True},
                        "strategy_combo_profiles": [
                            {
                                "profile_id": "combo123",
                                "profile_name": "Combo 123",
                                "strategy_params": {"momentum": {"enabled": True}},
                            }
                        ],
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
    assert mu_cfg["active_unified_profile_id"] == ""

    unified_payload = api_server._build_unified_profile_options_payload("MU")
    assert unified_payload["active_profile_id"] == "legacy-unified-MU-combo123-p123"


def test_create_isolated_tuner_aos_config_snapshot(monkeypatch, tmp_path) -> None:
    base_aos = tmp_path / "aos_config.json"
    base_payload = {"version": "1.0.0", "tickers": {"MU": {"strategy": "momentum_flow"}}}
    base_aos.write_text(json.dumps(base_payload))

    isolated_dir = tmp_path / "isolated"
    monkeypatch.setattr(api_server, "AOS_CONFIG_PATH", base_aos)
    monkeypatch.setattr(api_server, "ADAPTIVE_TUNER_AOS_DIR", isolated_dir)

    created = api_server._create_isolated_tuner_aos_config("jobabc")
    assert created.exists()
    assert created.parent == isolated_dir
    assert json.loads(created.read_text()) == base_payload

    api_server._cleanup_isolated_tuner_aos_config(created)
    assert not created.exists()


def test_evaluate_candidate_passes_isolated_aos_path(monkeypatch) -> None:
    captured_paths = []

    class _DummyRunner:
        async def run_all(self, speed_ms=0):
            return {}

        def get_summary(self):
            return {
                "session_summary": {
                    "total_pnl_pct": 0.2,
                    "total_pnl_dollars": 20.0,
                    "win_rate": 50.0,
                    "total_trades": 2,
                }
            }

    async def _fake_start_run(run_request):
        captured_paths.append(run_request.aos_config_path)
        run_key = f"{run_request.run_id}:{run_request.ticker}:{run_request.date}"
        api_server.active_runners[run_key] = _DummyRunner()
        return {"run_key": run_key}

    monkeypatch.setattr(api_server, "start_run", _fake_start_run)

    request = _base_request()
    result = asyncio.run(
        api_server._evaluate_adaptive_tuner_candidate(
            job_id="jobx",
            ticker="MU",
            dates=["2026-02-03", "2026-02-04"],
            trial_index=1,
            candidate={},
            request=request,
            aos_config_path="/tmp/isolated-aos.json",
        )
    )

    assert result["metrics"]["valid_days"] == 2
    assert captured_paths == ["/tmp/isolated-aos.json", "/tmp/isolated-aos.json"]


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

    # Momentum diversification options
    assert "momentum_diversification_enabled" in space
    assert "momentum_min_flow_score" in space
    assert "momentum_min_cvd" in space
    assert "momentum_min_directional_price_change_pct" in space
    assert "momentum_min_price_trend_efficiency" in space
    assert "momentum_min_last_bar_body_ratio" in space
    assert "momentum_min_last_bar_close_location" in space
    assert True in space["momentum_diversification_enabled"]


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
        "momentum_diversification_enabled": True,
        "momentum_route_enabled": True,
        "momentum_min_flow_score": 64.0,
        "momentum_min_directional_consistency": 0.44,
        "momentum_min_signed_aggression": 0.08,
        "momentum_min_imbalance": 0.06,
        "momentum_min_cvd": 1800.0,
        "momentum_min_directional_price_change_pct": 0.12,
        "momentum_min_price_trend_efficiency": 0.30,
        "momentum_min_last_bar_body_ratio": 0.42,
        "momentum_min_last_bar_close_location": 0.63,
        "momentum_min_delta_acceleration": 1200.0,
        "momentum_min_delta_price_divergence": -0.15,
        "momentum_route_flow_score_impulse": 70.0,
        "momentum_fail_fast_exit_enabled": True,
        "momentum_fail_fast_max_bars": 4,
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

    # Momentum diversification dims applied under adaptive config
    momentum_cfg = cfg["adaptive"]["momentum_diversification"]
    assert momentum_cfg["enabled"] is True
    assert momentum_cfg["route_enabled"] is True
    assert momentum_cfg["min_flow_score"] == 64.0
    assert momentum_cfg["min_directional_consistency"] == 0.44
    assert momentum_cfg["min_cvd"] == 1800.0
    assert momentum_cfg["min_directional_price_change_pct"] == 0.12
    assert momentum_cfg["min_price_trend_efficiency"] == 0.30
    assert momentum_cfg["min_last_bar_body_ratio"] == 0.42
    assert momentum_cfg["min_last_bar_close_location"] == 0.63
    assert momentum_cfg["fail_fast_exit_enabled"] is True
    assert momentum_cfg["fail_fast_max_bars"] == 4


def test_extract_profile_runtime_overrides_includes_momentum_diversification() -> None:
    runtime = api_server._extract_profile_runtime_overrides(
        {
            "strategy_selection_mode": "all_enabled",
            "max_active_strategies": 2,
            "momentum_diversification_enabled": True,
            "momentum_route_enabled": True,
            "momentum_min_flow_score": 62.0,
            "momentum_min_cvd": 1500.0,
            "momentum_fail_fast_exit_enabled": True,
            "momentum_fail_fast_max_bars": 3,
        }
    )
    assert "momentum_diversification" in runtime
    assert runtime["momentum_diversification"]["enabled"] is True
    assert runtime["momentum_diversification"]["route_enabled"] is True
    assert runtime["momentum_diversification"]["min_flow_score"] == 62.0
    assert runtime["momentum_diversification"]["min_cvd"] == 1500.0
    assert runtime["momentum_diversification"]["fail_fast_exit_enabled"] is True


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


def test_normalize_regime_strategy_map_sets() -> None:
    result = api_server._normalize_regime_strategy_map_sets(
        [
            None,
            {"TRENDING": ["MOMENTUM_FLOW", "invalid"], "MIXED": ["exhaustion_fade"]},
            {"TRENDING": ["momentum_flow"], "CHOPPY": []},
        ],
        enabled_strategies=["momentum_flow", "exhaustion_fade"],
    )
    assert result[0] is None
    assert isinstance(result[1], dict)
    assert result[1]["TRENDING"] == ["momentum_flow"]
    assert result[1]["MIXED"] == ["exhaustion_fade"]
    assert result[1]["CHOPPY"] == []


# ============ Expectancy Scoring & Regime-Conditional Map Tests ============


def test_expectancy_scoring_rewards_low_wr_high_rr() -> None:
    """40% WR with high per-trade PnL should score BETTER than old WR gate."""
    # Scenario: reversal strategy — 40% WR but 2.5:1 RR → positive expectancy
    day_results_reversal = [
        {"success": True, "pnl_pct": 0.15, "trades": 2, "win_rate_pct": 40.0},
        {"success": True, "pnl_pct": 0.10, "trades": 2, "win_rate_pct": 40.0},
        {"success": True, "pnl_pct": 0.08, "trades": 2, "win_rate_pct": 40.0},
    ]
    score_reversal = api_server._compute_tuner_score_robust(day_results_reversal)

    # Scenario: momentum strategy — 65% WR but same total PnL, more trades
    day_results_momentum = [
        {"success": True, "pnl_pct": 0.15, "trades": 4, "win_rate_pct": 65.0},
        {"success": True, "pnl_pct": 0.10, "trades": 4, "win_rate_pct": 65.0},
        {"success": True, "pnl_pct": 0.08, "trades": 4, "win_rate_pct": 65.0},
    ]
    score_momentum = api_server._compute_tuner_score_robust(day_results_momentum)

    # Both should be positive (not penalized to near-zero)
    assert score_reversal > 0, f"Reversal score {score_reversal} should be positive"
    assert score_momentum > 0, f"Momentum score {score_momentum} should be positive"
    # Reversal should not be dramatically worse (old code would ×0.3 it)
    assert score_reversal > score_momentum * 0.3, (
        f"Reversal {score_reversal} should not be crushed vs momentum {score_momentum}"
    )


def test_expectancy_scoring_penalizes_negative() -> None:
    """Negative per-trade expectancy should still get heavy penalty."""
    day_results = [
        {"success": True, "pnl_pct": -0.20, "trades": 3, "win_rate_pct": 30.0},
        {"success": True, "pnl_pct": -0.15, "trades": 2, "win_rate_pct": 25.0},
        {"success": True, "pnl_pct": -0.10, "trades": 2, "win_rate_pct": 35.0},
    ]
    score = api_server._compute_tuner_score_robust(day_results)
    # Score should be negative (base PnL is negative) and heavily penalized
    assert score < 0, f"Negative expectancy score {score} should be negative"


def test_l2_bonus_capped_at_10pct() -> None:
    """L2 bonus should be at most 10% and only applied when l2_avg_score > 0.3."""
    # Without L2 data
    day_results_no_l2 = [
        {"success": True, "pnl_pct": 0.10, "trades": 2, "win_rate_pct": 60.0},
        {"success": True, "pnl_pct": 0.12, "trades": 2, "win_rate_pct": 60.0},
        {"success": True, "pnl_pct": 0.08, "trades": 2, "win_rate_pct": 60.0},
    ]
    score_no_l2 = api_server._compute_tuner_score_robust(day_results_no_l2)

    # With L2 data on all days (max bonus)
    day_results_with_l2 = [
        {"success": True, "pnl_pct": 0.10, "trades": 2, "win_rate_pct": 60.0, "l2_avg_score": 0.5},
        {"success": True, "pnl_pct": 0.12, "trades": 2, "win_rate_pct": 60.0, "l2_avg_score": 0.6},
        {"success": True, "pnl_pct": 0.08, "trades": 2, "win_rate_pct": 60.0, "l2_avg_score": 0.7},
    ]
    score_with_l2 = api_server._compute_tuner_score_robust(day_results_with_l2)

    # L2 bonus should increase score but cap at +10%
    assert score_with_l2 > score_no_l2, "L2 bonus should increase score"
    assert score_with_l2 <= score_no_l2 * 1.101, (
        f"L2 bonus {score_with_l2} should be at most 10% above {score_no_l2}"
    )


def test_trade_scarcity_relaxed() -> None:
    """0.5-1.0 trades/day should get moderate penalty, not heavy penalty."""
    # 0.7 trades/day — should be moderate (0.65), not heavy (0.5 in old code)
    day_results = [
        {"success": True, "pnl_pct": 0.20, "trades": 1, "win_rate_pct": 100.0},
        {"success": True, "pnl_pct": 0.15, "trades": 0, "win_rate_pct": 0.0},
        {"success": True, "pnl_pct": 0.10, "trades": 1, "win_rate_pct": 100.0},
    ]
    score_sparse = api_server._compute_tuner_score_robust(day_results)

    # 2.0 trades/day — should have no scarcity penalty
    day_results_active = [
        {"success": True, "pnl_pct": 0.20, "trades": 2, "win_rate_pct": 100.0},
        {"success": True, "pnl_pct": 0.15, "trades": 2, "win_rate_pct": 100.0},
        {"success": True, "pnl_pct": 0.10, "trades": 2, "win_rate_pct": 100.0},
    ]
    score_active = api_server._compute_tuner_score_robust(day_results_active)

    # Sparse should be discounted but not crushed
    assert score_sparse > 0, f"Sparse score {score_sparse} should be positive"
    ratio = score_sparse / score_active if score_active != 0 else 0
    # With 0.65 factor, ratio should be ~0.65 (not 0.5)
    assert ratio > 0.55, f"Sparse/active ratio {ratio} too low — old heavy penalty still active?"
    assert ratio < 0.85, f"Sparse/active ratio {ratio} too high — penalty not applied?"


def test_regime_strategy_map_in_search_space() -> None:
    """Regime-strategy maps should be generated from strategy families."""
    request = _base_v2_request()
    config = {
        "strategy": "momentum_flow",
        "backup_strategy": "exhaustion_fade",
        "regime_filter": ["TRENDING", "MIXED"],
        "l2": {},
    }
    space = api_server._build_v2_search_space(request, config)

    assert "regime_strategy_maps" in space
    maps = space["regime_strategy_maps"]
    assert isinstance(maps, list)
    assert len(maps) >= 2

    # First option should be None (flat/backward compatible)
    assert maps[0] is None

    # Second option should have per-regime strategy assignments
    regime_map = maps[1]
    assert isinstance(regime_map, dict)
    assert "TRENDING" in regime_map
    assert "MIXED" in regime_map
    # Trending should include trend-follow family
    assert "momentum_flow" in regime_map["TRENDING"]
    # Mixed should include reversal family
    assert "exhaustion_fade" in regime_map["MIXED"]


def test_regime_strategy_map_injected_into_config() -> None:
    """_build_v2_candidate_config should store regime_strategy_map in config."""
    candidate = {
        "strategy_selection_mode": "all_enabled",
        "max_active_strategies": 3,
        "min_active_bars_before_switch": 0,
        "switch_cooldown_bars": 0,
        "flow_bias_enabled": True,
        "use_ohlcv_fallbacks": True,
        "enabled_strategies": ["momentum_flow"],
        "regime_filter": ["TRENDING", "MIXED"],
        "regime_strategy_map": {
            "TRENDING": ["momentum_flow"],
            "MIXED": ["exhaustion_fade"],
            "CHOPPY": [],
        },
    }
    cfg = api_server._build_v2_candidate_config(_ticker_config(), candidate, 2)

    assert "regime_strategy_map" in cfg
    assert cfg["regime_strategy_map"]["TRENDING"] == ["momentum_flow"]
    assert cfg["regime_strategy_map"]["MIXED"] == ["exhaustion_fade"]
    assert cfg["regime_strategy_map"]["CHOPPY"] == []
    assert cfg["adaptive"]["regime_preferences"]["TRENDING"] == ["momentum_flow"]
    assert cfg["adaptive"]["regime_preferences"]["MIXED"] == ["exhaustion_fade"]


def test_regime_strategy_map_none_clears_adaptive_preferences() -> None:
    ticker_cfg = _ticker_config()
    ticker_cfg["adaptive"]["regime_preferences"] = {
        "TRENDING": ["momentum_flow"],
        "MIXED": ["absorption_reversal"],
        "CHOPPY": ["absorption_reversal"],
    }
    ticker_cfg["regime_strategy_map"] = {
        "TRENDING": ["momentum_flow"],
        "MIXED": ["absorption_reversal"],
        "CHOPPY": ["absorption_reversal"],
    }
    candidate = {
        "strategy_selection_mode": "all_enabled",
        "max_active_strategies": 3,
        "regime_strategy_map": None,
    }
    cfg = api_server._build_v2_candidate_config(ticker_cfg, candidate, 2)
    assert "regime_preferences" not in cfg["adaptive"]
    assert "regime_strategy_map" not in cfg


def test_prepare_tuner_trial_ticker_config_disables_active_profile() -> None:
    cfg = api_server._prepare_tuner_trial_ticker_config(
        {
            "strategy": "momentum_flow",
            "active_adaptive_tuner_profile_id": "abc123",
        }
    )
    assert cfg["active_adaptive_tuner_profile_id"] == ""


def test_v2_candidate_key_with_regime_map() -> None:
    """Candidate key should differentiate candidates with different regime maps."""
    base = {
        "enabled_strategies": ["momentum_flow"],
        "regime_filter": ["TRENDING"],
        "l2_min_delta": 500,
        "l2_min_imbalance": 0.12,
        "l2_min_signed_aggression": 0.12,
        "l2_min_directional_consistency": 0.5,
        "base_threshold": 50,
        "min_confirming_sources": 2,
        "min_confidence": 60.0,
        "atr_stop_multiplier": 1.0,
        "rr_ratio": 2.0,
        "trading_hours": [9, 10],
        "adverse_flow_consistency": 0.45,
        "adverse_book_pressure": 0.15,
        "time_exit_bars": 25,
        "trailing_stop_pct": 0.8,
        "strategy_selection_mode": "all_enabled",
        "flow_bias_enabled": True,
    }
    # Without regime map
    c1 = {**base, "regime_strategy_map": None}
    # With regime map
    c2 = {**base, "regime_strategy_map": {"TRENDING": ["momentum_flow"], "MIXED": ["exhaustion_fade"]}}
    # Different regime map
    c3 = {**base, "regime_strategy_map": {"TRENDING": ["momentum_flow"], "MIXED": [], "CHOPPY": []}}

    key1 = api_server._v2_candidate_key(c1)
    key2 = api_server._v2_candidate_key(c2)
    key3 = api_server._v2_candidate_key(c3)

    assert key1 != key2, "None map and dict map should produce different keys"
    assert key2 != key3, "Different regime maps should produce different keys"
