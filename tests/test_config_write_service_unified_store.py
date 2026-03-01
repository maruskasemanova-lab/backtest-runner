from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace
from typing import Any, Dict, Optional

from src.normalization import (
    normalize_strategy_combo_profiles,
    normalize_tuner_profiles,
    normalize_unified_profiles,
)
from src.services.config_write_service import (
    ConfigWriteDeps,
    apply_unified_profile,
    capture_unified_profile,
)


def _build_deps(
    *,
    aos_config: Dict[str, Any],
    positioning_config: Dict[str, Any],
    load_unified_profile_state=None,
    save_unified_profile_state=None,
):
    saved_aos: list[Dict[str, Any]] = []
    saved_positioning: list[Dict[str, Any]] = []

    def _load_aos():
        return copy.deepcopy(aos_config)

    def _save_aos(cfg: Dict[str, Any]) -> bool:
        saved_aos.append(copy.deepcopy(cfg))
        return True

    def _load_positioning():
        return copy.deepcopy(positioning_config)

    def _save_positioning(cfg: Dict[str, Any]) -> bool:
        saved_positioning.append(copy.deepcopy(cfg))
        return True

    async def _fetch_remote_strategies(_url: str):
        return {"momentum": {"enabled": True, "min_confidence": 57.0}}

    def _extract_strategy_params(payload: Any) -> Dict[str, Dict[str, Any]]:
        if isinstance(payload, dict):
            return dict(payload)
        return {}

    async def _apply_strategy_param_map(_url: str, _params: Dict[str, Dict[str, Any]]):
        return {"applied_count": 1, "failed_count": 0}

    deps = ConfigWriteDeps(
        load_aos_config=_load_aos,
        save_aos_config=_save_aos,
        load_positioning_config=_load_positioning,
        save_positioning_config=_save_positioning,
        get_ticker_positioning_config=lambda ticker, *_args, **_kwargs: {},
        normalize_strategy_combo_profiles=normalize_strategy_combo_profiles,
        normalize_unified_profiles=normalize_unified_profiles,
        normalize_tuner_profiles=normalize_tuner_profiles,
        build_strategy_combo_profile_entry=lambda **_kwargs: {},
        fetch_remote_strategies=_fetch_remote_strategies,
        extract_strategy_params_for_profile=_extract_strategy_params,
        apply_strategy_param_map=_apply_strategy_param_map,
        build_v2_candidate_config=lambda *args, **kwargs: {},
        build_adaptive_candidate_config=lambda *args, **kwargs: {},
        normalize_non_negative_int=lambda value, default=0, **_kwargs: default
        if value is None
        else int(value),
        positioning_config_keys=("risk_per_trade_pct", "trailing_stop_pct"),
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
        load_unified_profile_state=load_unified_profile_state,
        save_unified_profile_state=save_unified_profile_state,
    )
    return deps, saved_aos, saved_positioning


def test_capture_unified_profile_uses_external_store_without_json_write() -> None:
    saved_state: Dict[str, Any] = {"profiles": [], "active_profile_id": None}

    def _load_state(_ticker: str):
        return list(saved_state["profiles"]), saved_state["active_profile_id"]

    def _save_state(_ticker: str, profiles, active_profile_id: Optional[str]):
        saved_state["profiles"] = list(profiles)
        saved_state["active_profile_id"] = active_profile_id

    deps, saved_aos, _saved_positioning = _build_deps(
        aos_config={
            "version": "1.0.0",
            "tickers": {
                "MU": {
                    "strategy_selection_mode": "all_enabled",
                    "max_active_strategies": 1,
                }
            },
        },
        positioning_config={"version": "1.0.0", "tickers": {"MU": {}}},
        load_unified_profile_state=_load_state,
        save_unified_profile_state=_save_state,
    )

    request = SimpleNamespace(
        ticker="MU",
        profile_name="MU DB profile",
        strategy_api_url="http://localhost:8001",
        set_active=True,
    )
    result = asyncio.run(capture_unified_profile(request, deps))

    assert result["success"] is True
    assert result["ticker"] == "MU"
    assert saved_aos == []
    assert len(saved_state["profiles"]) == 1
    assert saved_state["active_profile_id"] == saved_state["profiles"][0]["profile_id"]


def test_apply_unified_profile_uses_external_store_and_cleans_legacy_json_keys() -> None:
    external_profiles = [
        {
            "profile_id": "db-u1",
            "profile_name": "DB Unified",
            "strategy_profile": {
                "strategy_params": {"momentum": {"enabled": True}},
                "strategy_selection_mode": "all_enabled",
                "max_active_strategies": 2,
            },
            "execution_profile": {
                "positioning": {
                    "risk_per_trade_pct": 0.8,
                    "trailing_stop_pct": 0.6,
                }
            },
        }
    ]
    saved_state: Dict[str, Any] = {"profiles": list(external_profiles), "active_profile_id": None}

    def _load_state(_ticker: str):
        return list(saved_state["profiles"]), saved_state["active_profile_id"]

    def _save_state(_ticker: str, profiles, active_profile_id: Optional[str]):
        saved_state["profiles"] = list(profiles)
        saved_state["active_profile_id"] = active_profile_id

    deps, saved_aos, saved_positioning = _build_deps(
        aos_config={
            "version": "1.0.0",
            "tickers": {
                "MU": {
                    "unified_profiles": [{"profile_id": "stale"}],
                    "active_unified_profile_id": "stale",
                }
            },
        },
        positioning_config={"version": "1.0.0", "tickers": {"MU": {}}},
        load_unified_profile_state=_load_state,
        save_unified_profile_state=_save_state,
    )

    request = SimpleNamespace(
        ticker="MU",
        profile_id="db-u1",
        strategy_api_url="http://localhost:8001",
        apply_now=False,
        apply_execution=True,
    )
    result = asyncio.run(apply_unified_profile(request, deps))

    assert result["success"] is True
    assert result["profile_id"] == "db-u1"
    assert saved_state["active_profile_id"] == "db-u1"
    assert len(saved_aos) == 1
    saved_mu_cfg = saved_aos[0]["tickers"]["MU"]
    assert "unified_profiles" not in saved_mu_cfg
    assert "active_unified_profile_id" not in saved_mu_cfg
    assert saved_mu_cfg["strategy_selection_mode"] == "all_enabled"
    assert saved_mu_cfg["max_active_strategies"] == 2
    assert len(saved_positioning) == 1
    assert saved_positioning[0]["tickers"]["MU"]["risk_per_trade_pct"] == 0.8
    assert saved_positioning[0]["tickers"]["MU"]["trailing_stop_pct"] == 0.6
