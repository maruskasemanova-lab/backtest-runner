from __future__ import annotations

from types import SimpleNamespace

from src.services.start_run_prewarm_utils import (
    PrewarmInflightRegistry,
    build_prewarm_cache_key,
    resolve_prewarm_request_state,
)


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
        "comparable_mode": False,
        "include_extended_hours": None,
        "aos_config_path": None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_build_prewarm_cache_key_canonicalizes_trading_hours() -> None:
    request = _build_request()
    key_a = build_prewarm_cache_key(
        request=request,
        prewarm_scope="range",
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        requested_l2_only=False,
        requested_l2_confirm=True,
        aos_applied={"time_filter_enabled": True, "trading_hours": [11, 9, 10]},
    )
    key_b = build_prewarm_cache_key(
        request=request,
        prewarm_scope="range",
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        requested_l2_only=False,
        requested_l2_confirm=True,
        aos_applied={"time_filter_enabled": True, "trading_hours": [9, 10, 11]},
    )

    assert key_a == key_b


def test_resolve_prewarm_request_state_merges_aos_l2_defaults() -> None:
    request = _build_request()
    state = resolve_prewarm_request_state(
        request=request,
        ticker="MU",
        databento_svc=SimpleNamespace(),
        get_discovery=lambda: SimpleNamespace(),
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
        resolve_request_range=lambda req: (req.date_from, req.date_to),
        build_l2_guard_reason=lambda **kwargs: None,
    )

    assert state.ticker == "MU"
    assert state.range_start == "2026-02-03"
    assert state.range_end == "2026-02-03"
    assert state.requested_l2_only is False
    assert state.requested_l2_confirm_raw is True
    assert state.requested_l2_confirm is True
    assert state.l2_guard_reason is None


def test_resolve_prewarm_request_state_uses_canonical_positioning_merge() -> None:
    request = _build_request()
    state = resolve_prewarm_request_state(
        request=request,
        ticker="MU",
        databento_svc=SimpleNamespace(),
        get_discovery=lambda: SimpleNamespace(),
        load_aos_config=lambda *args, **kwargs: {
            "tickers": {
                "MU": {
                    "risk_per_trade_pct": 0.35,
                    "trailing_stop_pct": 0.2,
                    "l2": {"confirm_enabled": False},
                }
            }
        },
        get_ticker_positioning_config=lambda ticker: {"trailing_stop_pct": 0.8},
        positioning_config_keys=("risk_per_trade_pct", "trailing_stop_pct"),
        resolve_request_range=lambda req: (req.date_from, req.date_to),
        build_l2_guard_reason=lambda **kwargs: None,
    )

    assert state.aos_applied["positioning"] == {
        "risk_per_trade_pct": 0.35,
        "trailing_stop_pct": 0.8,
    }


def test_resolve_prewarm_request_state_uses_active_unified_profile_runtime() -> None:
    request = _build_request()
    state = resolve_prewarm_request_state(
        request=request,
        ticker="MU",
        databento_svc=SimpleNamespace(),
        get_discovery=lambda: SimpleNamespace(),
        load_aos_config=lambda *args, **kwargs: {
            "tickers": {
                "MU": {
                    "trading_hours": [13, 14, 15],
                    "time_filter_enabled": False,
                    "active_unified_profile_id": "u1",
                    "unified_profiles": [
                        {
                            "profile_id": "u1",
                            "profile_name": "MU Unified",
                            "strategy_profile": {
                                "strategy_selection_mode": "all_enabled",
                                "max_active_strategies": 5,
                                "trading_hours": [9, 10],
                                "time_filter_enabled": True,
                                "l2": {"confirm_enabled": True},
                            },
                            "execution_profile": {
                                "positioning": {"risk_per_trade_pct": 0.8}
                            },
                        }
                    ],
                }
            }
        },
        get_ticker_positioning_config=lambda ticker: {"trailing_stop_pct": 0.6},
        positioning_config_keys=("risk_per_trade_pct", "trailing_stop_pct"),
        resolve_request_range=lambda req: (req.date_from, req.date_to),
        build_l2_guard_reason=lambda **kwargs: None,
    )

    assert state.aos_applied["trading_hours"] == [9, 10]
    assert state.aos_applied["time_filter_enabled"] is True
    assert state.aos_applied["strategy_selection_mode"] == "all_enabled"
    assert state.aos_applied["max_active_strategies"] == 5
    assert state.requested_l2_confirm is True
    assert state.aos_applied["positioning"] == {
        "trailing_stop_pct": 0.6,
        "risk_per_trade_pct": 0.8,
    }


def test_resolve_prewarm_request_state_uses_active_adaptive_profile_trading_hours() -> None:
    request = _build_request()
    state = resolve_prewarm_request_state(
        request=request,
        ticker="MU",
        databento_svc=SimpleNamespace(),
        get_discovery=lambda: SimpleNamespace(),
        load_aos_config=lambda *args, **kwargs: {
            "tickers": {
                "MU": {
                    "trading_hours": [13, 14, 15],
                    "time_filter_enabled": False,
                    "active_adaptive_tuner_profile_id": "p1",
                    "adaptive_tuner_profiles": [
                        {
                            "profile_id": "p1",
                            "candidate": {
                                "enabled_strategies": ["momentum"],
                                "trading_hours": [11, 12],
                                "time_filter_enabled": True,
                            },
                        }
                    ],
                }
            }
        },
        get_ticker_positioning_config=lambda ticker: {},
        resolve_request_range=lambda req: (req.date_from, req.date_to),
        build_l2_guard_reason=lambda **kwargs: None,
    )

    assert state.aos_applied["trading_hours"] == [11, 12]
    assert state.aos_applied["time_filter_enabled"] is True
    adaptive_profile = state.aos_applied.get("adaptive_profile")
    assert isinstance(adaptive_profile, dict)
    assert adaptive_profile["active_profile_id"] == "p1"
    assert adaptive_profile["candidate_applied"] is True


def test_prewarm_inflight_registry_reuses_pending_future_and_cleans_up_done_future():
    registry = PrewarmInflightRegistry()

    first_future, first_is_owner = registry.acquire("mu-cache-key")
    second_future, second_is_owner = registry.acquire("mu-cache-key")

    assert first_is_owner is True
    assert second_is_owner is False
    assert second_future is first_future
    assert registry.is_inflight("mu-cache-key") is True

    first_future.set_result({"success": True})

    assert registry.is_inflight("mu-cache-key") is False

    third_future, third_is_owner = registry.acquire("mu-cache-key")

    assert third_is_owner is True
    assert third_future is not first_future
