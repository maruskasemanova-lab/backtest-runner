from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any, Dict

from src.services.config_write_service import (
    ConfigWriteDeps,
    update_aos_config,
    update_positioning_config,
)


def _build_deps(*, aos_config: Dict[str, Any], positioning_config: Dict[str, Any]):
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

    deps = ConfigWriteDeps(
        load_aos_config=_load_aos,
        save_aos_config=_save_aos,
        load_positioning_config=_load_positioning,
        save_positioning_config=_save_positioning,
        get_ticker_positioning_config=lambda ticker, cfg=None, *_args, **_kwargs: dict(
            (cfg or {}).get("tickers", {}).get(str(ticker or "").upper(), {})
        )
        if isinstance((cfg or {}).get("tickers", {}), dict)
        else {},
        normalize_strategy_combo_profiles=lambda value: list(value or []),
        normalize_unified_profiles=lambda value: list(value or []),
        normalize_tuner_profiles=lambda value: list(value or []),
        build_strategy_combo_profile_entry=lambda **_kwargs: {},
        fetch_remote_strategies=lambda *_args, **_kwargs: None,
        extract_strategy_params_for_profile=lambda *_args, **_kwargs: {},
        apply_strategy_param_map=lambda *_args, **_kwargs: {},
        build_v2_candidate_config=lambda *args, **kwargs: {},
        build_adaptive_candidate_config=lambda *args, **kwargs: {},
        normalize_non_negative_int=lambda value, default=0, **_kwargs: default
        if value is None
        else int(value),
        positioning_config_keys=("risk_per_trade_pct", "trailing_stop_pct"),
        logger=SimpleNamespace(info=lambda *args, **kwargs: None),
    )
    return deps, saved_aos, saved_positioning


def test_update_aos_config_routes_legacy_positioning_keys_into_positioning_store():
    deps, saved_aos, saved_positioning = _build_deps(
        aos_config={"version": "1.0.0", "tickers": {"MU": {"existing_flag": True}}},
        positioning_config={"version": "1.0.0", "tickers": {}},
    )

    result = update_aos_config(
        SimpleNamespace(
            ticker="MU",
            config={
                "strategy_selection_mode": "all_enabled",
                "risk_per_trade_pct": 0.4,
                "positioning": {"trailing_stop_pct": 0.7},
            },
        ),
        deps,
    )

    saved_mu = saved_aos[0]["tickers"]["MU"]
    saved_pos = saved_positioning[0]["tickers"]["MU"]

    assert saved_mu["existing_flag"] is True
    assert saved_mu["strategy_selection_mode"] == "all_enabled"
    assert "risk_per_trade_pct" not in saved_mu
    assert "trailing_stop_pct" not in saved_mu
    assert saved_pos == {"risk_per_trade_pct": 0.4, "trailing_stop_pct": 0.7}
    assert result["config"]["positioning"] == saved_pos


def test_update_aos_config_without_positioning_does_not_create_empty_positioning_entry():
    deps, saved_aos, saved_positioning = _build_deps(
        aos_config={"version": "1.0.0", "tickers": {}},
        positioning_config={"version": "1.0.0", "tickers": {}},
    )

    result = update_aos_config(
        SimpleNamespace(
            ticker="MU",
            config={"strategy_selection_mode": "adaptive_top_n"},
        ),
        deps,
    )

    assert saved_aos[0]["tickers"]["MU"]["strategy_selection_mode"] == "adaptive_top_n"
    assert "MU" not in saved_positioning[0]["tickers"]
    assert "positioning" not in result["config"]


def test_update_positioning_config_can_persist_explicit_empty_payload():
    deps, _saved_aos, saved_positioning = _build_deps(
        aos_config={"version": "1.0.0", "tickers": {}},
        positioning_config={"version": "1.0.0", "tickers": {}},
    )

    result = update_positioning_config(
        SimpleNamespace(
            ticker="MU",
            config={},
        ),
        deps,
    )

    assert result["config"] == {}
    assert saved_positioning[0]["tickers"]["MU"] == {}
