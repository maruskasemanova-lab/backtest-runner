from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys


_API_SERVER_PATH = Path(__file__).resolve().parents[1] / "api_server.py"
_PROJECT_ROOT = str(_API_SERVER_PATH.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_API_SERVER_SPEC = importlib.util.spec_from_file_location(
    "api_server_module", _API_SERVER_PATH
)
assert _API_SERVER_SPEC is not None and _API_SERVER_SPEC.loader is not None
api_server = importlib.util.module_from_spec(_API_SERVER_SPEC)
_API_SERVER_SPEC.loader.exec_module(api_server)


class _DummyDiscovery:
    def get_files_for_range(self, *args, **kwargs):
        return []


class _DummyRunner:
    def __init__(self, config):
        self.config = config
        self.is_running = False
        self.is_paused = False
        self.last_run_speed = None

    def load_bars(self, bars):
        self._bars = list(bars)

    def on_bar(self, _cb):
        return None

    def on_decision(self, _cb):
        return None

    def get_state(self):
        return {"phase": "IDLE"}


def _patch_start_run_dependencies(
    monkeypatch,
    apply_calls,
    *,
    apply_aos_result=None,
    configure_spy=None,
    aos_spy=None,
    remote_strategies=None,
    strategy_param_sync_calls=None,
):
    async def _noop_async(*args, **kwargs):
        return None

    async def _reset_full(*args, **kwargs):
        return {"success": True, "scope": "all"}

    async def _apply_aos(*args, **kwargs):
        if aos_spy is not None:
            aos_spy["args"] = list(args)
            aos_spy["kwargs"] = dict(kwargs)
        return dict(apply_aos_result or {})

    async def _configure(*args, **kwargs):
        if configure_spy is not None:
            configure_spy["kwargs"] = dict(kwargs)
        return None

    async def _record_apply(*args, **kwargs):
        apply_calls["count"] += 1
        return None

    async def _fetch_remote_strategies(*args, **kwargs):
        if isinstance(remote_strategies, dict):
            return dict(remote_strategies)
        return {
            "momentum_flow": {},
            "mean_reversion": {},
            "rotation": {},
        }

    async def _apply_strategy_param_map(*args, **kwargs):
        param_map = (
            args[1]
            if len(args) > 1
            else kwargs.get("strategy_params") or kwargs.get("param_map")
        )
        if strategy_param_sync_calls is not None and isinstance(param_map, dict):
            strategy_param_sync_calls.append(dict(param_map))
        return {"ok": True, "applied": True}

    monkeypatch.setattr(api_server, "SessionRunner", _DummyRunner)
    monkeypatch.setattr(api_server, "_reset_remote_orchestrator_state", _reset_full)
    monkeypatch.setattr(api_server, "_clear_remote_strategy_sessions", _noop_async)
    monkeypatch.setattr(api_server, "_configure_session", _configure)
    monkeypatch.setattr(api_server, "_apply_aos_optimizations", _apply_aos)
    monkeypatch.setattr(api_server, "_apply_strategy_overrides", _record_apply)
    monkeypatch.setattr(
        api_server, "_fetch_remote_strategies", _fetch_remote_strategies
    )
    monkeypatch.setattr(
        api_server, "_apply_strategy_param_map", _apply_strategy_param_map
    )
    monkeypatch.setattr(api_server, "get_discovery", lambda: _DummyDiscovery())
    monkeypatch.setattr(api_server.databento_svc, "scan_existing_files", lambda: None)
    monkeypatch.setattr(
        api_server.databento_svc, "get_files_for_range", lambda **kwargs: []
    )
    monkeypatch.setattr(api_server.databento_svc, "list_catalog", lambda **kwargs: [])


def test_start_run_applies_ticker_overrides_by_default(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    _patch_start_run_dependencies(monkeypatch, apply_calls)

    request = api_server.StartRunRequest(
        run_id="test-default-overrides",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        assert result["strategy_overrides_applied"] is True
        assert apply_calls["count"] == 1
        assert isinstance(result.get("start_timing"), dict)
        assert float(result["start_timing"].get("total_ms", -1)) >= 0
        assert isinstance(result["start_timing"].get("phases_ms"), dict)
        assert "load_run_bars" in result["start_timing"]["phases_ms"]
    finally:
        api_server.active_runners.clear()


def test_start_run_can_skip_ticker_overrides(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    _patch_start_run_dependencies(monkeypatch, apply_calls)

    request = api_server.StartRunRequest(
        run_id="test-skip-overrides",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
        apply_ticker_overrides_on_start=False,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        assert result["strategy_overrides_applied"] is False
        assert apply_calls["count"] == 0
    finally:
        api_server.active_runners.clear()


def test_start_run_uses_aos_strategy_selection_defaults(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    configure_spy = {}
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        apply_aos_result={
            "strategy_selection_mode": "all_enabled",
            "max_active_strategies": 9,
        },
        configure_spy=configure_spy,
    )

    request = api_server.StartRunRequest(
        run_id="test-selection-defaults",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        assert configure_spy["kwargs"]["strategy_selection_mode"] == "all_enabled"
        assert configure_spy["kwargs"]["max_active_strategies"] == 9
        assert result["execution_config"]["strategy_selection_mode"] == "all_enabled"
        assert result["execution_config"]["max_active_strategies"] == 9
    finally:
        api_server.active_runners.clear()


def test_start_run_strategy_selection_request_overrides_aos(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    configure_spy = {}
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        apply_aos_result={
            "strategy_selection_mode": "adaptive_top_n",
            "max_active_strategies": 3,
        },
        configure_spy=configure_spy,
    )

    request = api_server.StartRunRequest(
        run_id="test-selection-override",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
        strategy_selection_mode="all_enabled",
        max_active_strategies=12,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        assert configure_spy["kwargs"]["strategy_selection_mode"] == "all_enabled"
        assert configure_spy["kwargs"]["max_active_strategies"] == 12
        assert result["execution_config"]["strategy_selection_mode"] == "all_enabled"
        assert result["execution_config"]["max_active_strategies"] == 12
    finally:
        api_server.active_runners.clear()


def test_start_run_all_enabled_force_enables_remote_strategies(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    sync_calls = []
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        apply_aos_result={
            "strategy_selection_mode": "all_enabled",
            "max_active_strategies": 9,
        },
        strategy_param_sync_calls=sync_calls,
        remote_strategies={
            "momentum_flow": {},
            "mean_reversion": {},
            "rotation": {},
        },
    )

    request = api_server.StartRunRequest(
        run_id="test-all-enabled-force-enable",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        assert len(sync_calls) == 1
        enabled_payload = sync_calls[0]
        assert set(enabled_payload.keys()) == {
            "momentum_flow",
            "mean_reversion",
            "rotation",
        }
        assert all(
            isinstance(params, dict) and params.get("enabled") is True
            for params in enabled_payload.values()
        )
        sync_meta = result["execution_config"]["all_enabled_remote_sync"]
        assert isinstance(sync_meta, dict)
        assert sync_meta.get("attempted") is True
        assert sync_meta.get("applied") is True
        assert sync_meta.get("strategy_count") == 3
        assert (
            result["start_timing"]["context"]["all_enabled_remote_sync_attempted"]
            is True
        )
    finally:
        api_server.active_runners.clear()


def test_start_run_can_skip_aos_remote_sync(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    aos_spy = {}
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        apply_aos_result={
            "strategy_selection_mode": "adaptive_top_n",
            "max_active_strategies": 3,
        },
        aos_spy=aos_spy,
    )

    request = api_server.StartRunRequest(
        run_id="test-skip-aos-sync",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
        apply_aos_optimizations_on_start=False,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        assert aos_spy["kwargs"]["remote_sync"] is False
        assert result["execution_config"]["apply_aos_optimizations_on_start"] is False
        assert (
            result["start_timing"]["context"]["apply_aos_optimizations_on_start"]
            is False
        )
    finally:
        api_server.active_runners.clear()


def test_start_run_persists_effective_profile_identity(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        apply_aos_result={
            "unified_profile": {
                "active_profile_id": "mu-unified-v1",
                "profile_name": "MU Unified v1",
            },
            "adaptive_profile": {
                "active_profile_id": "None",
                "profile_id": "mu-adaptive-v1",
                "profile_name": "MU Adaptive v1",
            },
            "strategy_combo": {
                "active_profile_id": "mu-combo-v1",
                "profile_name": "MU Combo v1",
            },
            "strategy_selection_mode": "adaptive_top_n",
            "max_active_strategies": 3,
        },
    )

    request = api_server.StartRunRequest(
        run_id="test-profile-persist",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
        apply_aos_optimizations_on_start=False,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        execution = result["execution_config"]
        assert execution["unified_profile_id"] == "mu-unified-v1"
        assert execution["active_unified_profile_id"] == "mu-unified-v1"
        assert execution["adaptive_profile_id"] == "mu-adaptive-v1"
        assert execution["active_adaptive_tuner_profile_id"] == "mu-adaptive-v1"
        assert execution["strategy_combo_profile_id"] == "mu-combo-v1"
        assert execution["active_strategy_combo_profile_id"] == "mu-combo-v1"

        run_key = str(result["run_key"])
        runner = api_server.active_runners[run_key]
        assert runner._report_metadata["unified_profile_id"] == "mu-unified-v1"
        assert runner._report_metadata["adaptive_profile_id"] == "mu-adaptive-v1"
        assert runner._report_metadata["strategy_combo_profile_id"] == "mu-combo-v1"
    finally:
        api_server.active_runners.clear()


def test_start_run_applies_positioning_config_by_default(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    configure_spy = {}
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        apply_aos_result={
            "positioning": {
                "risk_per_trade_pct": 2.0,
                "trailing_activation_pct": 0.25,
                "break_even_buffer_pct": 0.01,
            }
        },
        configure_spy=configure_spy,
    )

    request = api_server.StartRunRequest(
        run_id="test-positioning-default",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        assert configure_spy["kwargs"]["risk_per_trade_pct"] == 2.0
        assert configure_spy["kwargs"]["trailing_activation_pct"] == 0.2
        assert configure_spy["kwargs"]["break_even_buffer_pct"] == 0.01
        assert (
            result["execution_config"]["risk_per_trade_pct_source"]
            == "positioning_config"
        )
        assert result["execution_config"]["trailing_activation_pct_source"] == "request"
        assert (
            result["execution_config"]["break_even_buffer_pct_source"]
            == "positioning_config"
        )
    finally:
        api_server.active_runners.clear()


def test_start_run_can_skip_positioning_config(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    configure_spy = {}
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        apply_aos_result={
            "positioning": {
                "risk_per_trade_pct": 2.0,
                "trailing_activation_pct": 0.25,
                "break_even_buffer_pct": 0.01,
            }
        },
        configure_spy=configure_spy,
    )

    request = api_server.StartRunRequest(
        run_id="test-positioning-skip",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
        apply_positioning_config_on_start=False,
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        assert configure_spy["kwargs"]["risk_per_trade_pct"] == 1.0
        assert configure_spy["kwargs"]["trailing_activation_pct"] == 0.2
        assert configure_spy["kwargs"]["break_even_buffer_pct"] == 0.03
        assert result["execution_config"]["positioning_config_enabled"] is False
        assert result["execution_config"]["risk_per_trade_pct_source"] == "request"
    finally:
        api_server.active_runners.clear()


def test_start_run_passes_momentum_diversification_override(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    configure_spy = {}
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        apply_aos_result={
            "adaptive": {
                "momentum_diversification": {
                    "enabled": True,
                    "min_flow_score": 58.0,
                }
            }
        },
        configure_spy=configure_spy,
    )

    request = api_server.StartRunRequest(
        run_id="test-momentum-diversification",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
        momentum_diversification_override={
            "enabled": True,
            "route_enabled": True,
            "min_flow_score": 66.0,
            "fail_fast_exit_enabled": True,
        },
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        raw_payload = configure_spy["kwargs"]["momentum_diversification_json"]
        payload = json.loads(raw_payload)
        assert payload["enabled"] is True
        assert payload["min_flow_score"] == 66.0
        assert payload["fail_fast_exit_enabled"] is True
        assert (
            result["execution_config"]["momentum_diversification_source"] == "request"
        )
        assert result["execution_config"]["momentum_diversification_applied"] is True
    finally:
        api_server.active_runners.clear()


def test_start_run_passes_momentum_diversification_multi_sleeve_override(monkeypatch):
    api_server.active_runners.clear()
    apply_calls = {"count": 0}
    configure_spy = {}
    _patch_start_run_dependencies(
        monkeypatch,
        apply_calls,
        configure_spy=configure_spy,
    )

    request = api_server.StartRunRequest(
        run_id="test-momentum-diversification-sleeves",
        ticker="QQQ",
        date="2026-01-20",
        strategy_api_url="http://localhost:8001",
        allow_mock_data=True,
        momentum_diversification_override={
            "enabled": True,
            "sleeves": [
                {
                    "sleeve_id": "Impulse",
                    "enabled": True,
                    "route_enabled": True,
                    "min_flow_score": 66.0,
                    "apply_to_strategies": ["momentum_flow"],
                    "allocation_weight": 0.65,
                },
                {
                    "sleeve_id": "Defensive",
                    "enabled": True,
                    "route_enabled": True,
                    "min_flow_score": 48.0,
                    "apply_to_strategies": ["absorption_reversal"],
                    "allocation_weight": 0.35,
                },
            ],
        },
    )

    try:
        result = asyncio.run(api_server.start_run(request))
        assert result["success"] is True
        raw_payload = configure_spy["kwargs"]["momentum_diversification_json"]
        payload = json.loads(raw_payload)
        assert payload["enabled"] is True
        assert isinstance(payload.get("sleeves"), list)
        assert len(payload["sleeves"]) == 2
        assert payload["sleeves"][0]["sleeve_id"] == "impulse"
        assert payload["sleeves"][0]["min_flow_score"] == 66.0
        assert payload["sleeves"][0]["allocation_weight"] == 0.65
        assert payload["sleeves"][1]["sleeve_id"] == "defensive"
        assert (
            result["execution_config"]["momentum_diversification_source"] == "request"
        )
        assert result["execution_config"]["momentum_diversification_applied"] is True
    finally:
        api_server.active_runners.clear()
