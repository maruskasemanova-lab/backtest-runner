from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys

from src.services.saas_service import SaaSStateStore


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


def _seed_primary_config_snapshots(
    *,
    monkeypatch,
    tmp_path: Path,
    aos_config: dict,
    positioning_config: dict,
) -> SaaSStateStore:
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))
    store.upsert_config_snapshot(
        config_key="aos_config",
        payload=aos_config,
        source="test_seed",
    )
    store.upsert_config_snapshot(
        config_key="positioning_config",
        payload=positioning_config,
        source="test_seed",
    )
    monkeypatch.setattr(api_server.v2_services, "store", store)
    monkeypatch.setattr(api_server.api_services, "state_store", store)
    monkeypatch.setattr(api_server.app.state, "saas_state_store", store, raising=False)
    return store


def test_capture_unified_profile_persists_strategy_and_execution(
    monkeypatch, tmp_path
) -> None:
    _seed_primary_config_snapshots(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        aos_config={
            "version": "1.0.0",
            "tickers": {
                "MU": {
                    "strategy_selection_mode": "adaptive_top_n",
                    "max_active_strategies": 3,
                    "trading_hours": [9, 10, 11],
                    "time_filter_enabled": True,
                    "active_strategy_combo_profile_id": "combo123",
                    "active_adaptive_tuner_profile_id": "p123",
                    "adaptive_tuner_profiles": [
                        {
                            "profile_id": "p123",
                            "candidate": {
                                "enabled_strategies": ["momentum"],
                                "strategy_selection_mode": "all_enabled",
                                "max_active_strategies": 5,
                            },
                        }
                    ],
                }
            },
        },
        positioning_config={
            "version": "1.0.0",
            "tickers": {
                "MU": {
                    "risk_per_trade_pct": 0.9,
                    "trailing_stop_pct": 0.7,
                }
            },
        },
    )

    async def _fake_fetch(_strategy_api_url: str):
        return {
            "momentum": {"enabled": True, "min_confidence": 57.0},
            "pullback": {"enabled": False},
        }

    monkeypatch.setattr(api_server, "_fetch_remote_strategies", _fake_fetch)

    request = api_server.UnifiedProfileCaptureRequest(
        ticker="MU",
        profile_name="MU Unified v1",
        strategy_api_url="http://localhost:8001",
        set_active=True,
    )
    result = asyncio.run(api_server.capture_unified_profile(request))

    assert result["success"] is True
    assert result["ticker"] == "MU"
    assert result["profile"]["profile_name"] == "MU Unified v1"
    assert result["active_profile_id"] == result["profile"]["profile_id"]
    assert "strategy_profile" in result["profile"]
    assert "execution_profile" in result["profile"]

    saved_aos = api_server._load_aos_config()
    mu_cfg = saved_aos["tickers"]["MU"]
    assert mu_cfg["active_unified_profile_id"] == result["profile"]["profile_id"]
    assert len(mu_cfg["unified_profiles"]) == 1
    unified_entry = mu_cfg["unified_profiles"][0]
    assert (
        unified_entry["strategy_profile"]["strategy_params"]["momentum"]["enabled"]
        is True
    )
    assert unified_entry["execution_profile"]["positioning"]["trailing_stop_pct"] == 0.7


def test_apply_unified_profile_sets_active_and_updates_positioning(
    monkeypatch, tmp_path
) -> None:
    _seed_primary_config_snapshots(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        aos_config={
            "version": "1.0.0",
            "tickers": {
                "MU": {
                    "unified_profiles": [
                        {
                            "profile_id": "unified123",
                            "profile_name": "MU Unified",
                            "strategy_profile": {
                                "strategy_params": {
                                    "momentum": {
                                        "enabled": True,
                                        "min_confidence": 58.0,
                                    }
                                },
                                "strategy_selection_mode": "all_enabled",
                                "max_active_strategies": 4,
                                "trading_hours": [9, 10],
                                "time_filter_enabled": True,
                                "active_strategy_combo_profile_id": "combo123",
                                "active_adaptive_tuner_profile_id": "p123",
                            },
                            "execution_profile": {
                                "positioning": {
                                    "risk_per_trade_pct": 0.8,
                                    "trailing_stop_pct": 0.6,
                                }
                            },
                        }
                    ]
                }
            },
        },
        positioning_config={"version": "1.0.0", "tickers": {"MU": {}}},
    )

    async def _fake_apply(_strategy_api_url: str, strategy_params):
        assert "momentum" in strategy_params
        return {
            "applied_strategies": ["momentum"],
            "failed_strategies": [],
            "applied_count": 1,
            "failed_count": 0,
        }

    monkeypatch.setattr(api_server, "_apply_strategy_param_map", _fake_apply)

    request = api_server.UnifiedProfileApplyRequest(
        ticker="MU",
        profile_id="unified123",
        strategy_api_url="http://localhost:8001",
        apply_now=True,
        apply_execution=True,
    )
    result = asyncio.run(api_server.apply_unified_profile(request))

    assert result["success"] is True
    assert result["profile_id"] == "unified123"
    assert result["apply_result"]["applied_count"] == 1
    assert result["applied_execution"] is True

    saved_aos = api_server._load_aos_config()
    mu_cfg = saved_aos["tickers"]["MU"]
    assert mu_cfg["active_unified_profile_id"] == "unified123"
    assert mu_cfg["strategy_selection_mode"] == "all_enabled"
    assert mu_cfg["max_active_strategies"] == 4
    assert mu_cfg["active_strategy_combo_profile_id"] == "combo123"
    assert mu_cfg["active_adaptive_tuner_profile_id"] == "p123"

    saved_positioning = api_server._load_positioning_config()
    mu_positioning = saved_positioning["tickers"]["MU"]
    assert mu_positioning["risk_per_trade_pct"] == 0.8
    assert mu_positioning["trailing_stop_pct"] == 0.6


def test_unified_profile_options_include_legacy_combo_adaptive_variants(
    monkeypatch, tmp_path
) -> None:
    _seed_primary_config_snapshots(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        aos_config={
            "version": "1.0.0",
            "tickers": {
                "MU": {
                    "strategy_selection_mode": "adaptive_top_n",
                    "max_active_strategies": 3,
                    "active_strategy_combo_profile_id": "combo-b",
                    "active_adaptive_tuner_profile_id": "tuned-a",
                    "strategy_combo_profiles": [
                        {
                            "profile_id": "combo-a",
                            "profile_name": "Combo A",
                            "strategy_params": {"momentum": {"enabled": True}},
                            "updated_at": "2026-02-11T10:00:00Z",
                        },
                        {
                            "profile_id": "combo-b",
                            "profile_name": "Combo B",
                            "strategy_params": {"pullback": {"enabled": True}},
                            "updated_at": "2026-02-12T10:00:00Z",
                        },
                    ],
                    "adaptive_tuner_profiles": [
                        {
                            "profile_id": "tuned-a",
                            "profile_name": "Tuned A",
                            "updated_at": "2026-02-13T10:00:00Z",
                            "candidate": {"strategy_selection_mode": "all_enabled"},
                        },
                        {
                            "profile_id": "tuned-b",
                            "profile_name": "Tuned B",
                            "updated_at": "2026-02-10T10:00:00Z",
                            "candidate": {
                                "strategy_selection_mode": "adaptive_top_n"
                            },
                        },
                    ],
                }
            },
        },
        positioning_config={
            "version": "1.0.0",
            "tickers": {"MU": {"risk_per_trade_pct": 0.9}},
        },
    )

    payload = api_server._build_unified_profile_options_payload("MU")
    assert payload["ticker"] == "MU"
    assert payload["active_profile_id"] == "legacy-unified-MU-combo-b-tuned-a"
    profiles = payload["profiles"]
    assert len(profiles) >= 4

    ids = {str(item.get("profile_id") or "") for item in profiles}
    assert "legacy-unified-MU-combo-a-tuned-a" in ids
    assert "legacy-unified-MU-combo-b-tuned-a" in ids
    assert "legacy-unified-MU-combo-a-tuned-b" in ids
    assert "legacy-unified-MU-combo-b-tuned-b" in ids

    active_row = next(
        item for item in profiles if item["profile_id"] == payload["active_profile_id"]
    )
    assert (
        active_row["strategy_profile"]["active_strategy_combo_profile_id"] == "combo-b"
    )
    assert (
        active_row["strategy_profile"]["active_adaptive_tuner_profile_id"] == "tuned-a"
    )
    assert active_row["execution_profile"]["positioning"]["risk_per_trade_pct"] == 0.9


def test_unified_profile_options_merge_legacy_top_level_positioning_keys(
    monkeypatch, tmp_path
) -> None:
    _seed_primary_config_snapshots(
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        aos_config={
            "version": "1.0.0",
            "tickers": {
                "MU": {
                    "risk_per_trade_pct": 0.45,
                    "trailing_stop_pct": 0.25,
                    "active_strategy_combo_profile_id": "combo-a",
                    "active_adaptive_tuner_profile_id": "tuned-a",
                    "strategy_combo_profiles": [
                        {
                            "profile_id": "combo-a",
                            "profile_name": "Combo A",
                            "created_at": "2026-02-10T10:00:00Z",
                            "updated_at": "2026-02-10T10:00:00Z",
                            "strategy_params": {"momentum": {"enabled": True}},
                        }
                    ],
                    "adaptive_tuner_profiles": [
                        {
                            "profile_id": "tuned-a",
                            "profile_name": "Tuned A",
                            "updated_at": "2026-02-10T10:00:00Z",
                            "candidate": {
                                "strategy_selection_mode": "adaptive_top_n",
                                "max_active_strategies": 3,
                            },
                        }
                    ],
                }
            },
        },
        positioning_config={"version": "1.0.0", "tickers": {"MU": {}}},
    )

    payload = api_server._build_unified_profile_options_payload("MU")
    active_row = next(
        item
        for item in payload["profiles"]
        if item["profile_id"] == payload["active_profile_id"]
    )

    assert active_row["execution_profile"]["positioning"] == {
        "risk_per_trade_pct": 0.45,
        "trailing_stop_pct": 0.25,
    }
