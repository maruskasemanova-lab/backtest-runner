from __future__ import annotations

from types import SimpleNamespace

from src.momentum_diversification import normalize_momentum_diversification_payload
from src.normalization import (
    normalize_strategy_combo_profiles,
    normalize_tuner_profiles,
    normalize_unified_profiles,
)
from src.services.adaptive_tuner_core_service import (
    normalize_clamped_int,
    normalize_strategy_selection_mode,
)
from src.services.config_domain import (
    TickerConfigRepositoryDeps,
    build_effective_ticker_config,
    build_ticker_display_payload,
    resolve_effective_aos_applied_snapshot,
    load_ticker_config_aggregate,
    resolve_local_aos_applied_snapshot,
)


def _profile_deps():
    return SimpleNamespace(
        normalize_strategy_combo_profiles=normalize_strategy_combo_profiles,
        normalize_unified_profiles=normalize_unified_profiles,
        normalize_tuner_profiles=normalize_tuner_profiles,
        normalize_strategy_selection_mode=normalize_strategy_selection_mode,
        normalize_clamped_int=normalize_clamped_int,
        normalize_momentum_diversification_payload=(
            normalize_momentum_diversification_payload
        ),
    )


def test_load_ticker_config_aggregate_merges_legacy_positioning_keys() -> None:
    deps = TickerConfigRepositoryDeps(
        load_aos_config=lambda *_args, **_kwargs: {
            "tickers": {
                "MU": {
                    "strategy_selection_mode": "all_enabled",
                    "max_active_strategies": 5,
                    "risk_per_trade_pct": 0.6,
                    "trailing_stop_pct": 0.7,
                    "adaptive_tuner_profiles": [{"profile_id": "p1", "candidate": {}}],
                    "active_adaptive_tuner_profile_id": "p1",
                }
            }
        },
        get_ticker_positioning_config=lambda *_args, **_kwargs: {
            "trailing_stop_pct": 0.9,
            "max_fill_participation_rate": 0.2,
        },
        normalize_strategy_combo_profiles=lambda value: list(value or []),
        normalize_unified_profiles=lambda value: list(value or []),
        normalize_tuner_profiles=lambda value: list(value or []),
        positioning_config_keys=("risk_per_trade_pct", "trailing_stop_pct"),
    )

    aggregate = load_ticker_config_aggregate(ticker="MU", deps=deps)

    assert aggregate.ticker == "MU"
    assert aggregate.positioning == {
        "risk_per_trade_pct": 0.6,
        "trailing_stop_pct": 0.9,
        "max_fill_participation_rate": 0.2,
    }
    assert aggregate.active_adaptive_tuner_profile_id == "p1"


def test_build_ticker_display_payload_preserves_ticker_shape_and_adds_positioning() -> None:
    deps = TickerConfigRepositoryDeps(
        load_aos_config=lambda *_args, **_kwargs: {
            "tickers": {"MU": {"strategy_selection_mode": "adaptive_top_n"}}
        },
        get_ticker_positioning_config=lambda *_args, **_kwargs: {
            "risk_per_trade_pct": 0.5
        },
        normalize_strategy_combo_profiles=lambda value: list(value or []),
        normalize_unified_profiles=lambda value: list(value or []),
        normalize_tuner_profiles=lambda value: list(value or []),
        positioning_config_keys=(),
    )

    aggregate = load_ticker_config_aggregate(ticker="MU", deps=deps)
    payload = build_ticker_display_payload(aggregate)

    assert payload["strategy_selection_mode"] == "adaptive_top_n"
    assert payload["positioning"]["risk_per_trade_pct"] == 0.5


def test_resolve_local_aos_applied_snapshot_uses_merged_positioning() -> None:
    deps = TickerConfigRepositoryDeps(
        load_aos_config=lambda *_args, **_kwargs: {
            "tickers": {
                "MU": {
                    "trading_hours": [9, 10],
                    "time_filter_enabled": True,
                    "strategy_selection_mode": "all_enabled",
                    "max_active_strategies": 4,
                    "adverse_flow_consistency_threshold": 0.2,
                    "adverse_book_pressure_threshold": 0.1,
                    "risk_per_trade_pct": 0.7,
                }
            }
        },
        get_ticker_positioning_config=lambda *_args, **_kwargs: {
            "trailing_stop_pct": 0.6
        },
        normalize_strategy_combo_profiles=lambda value: list(value or []),
        normalize_unified_profiles=lambda value: list(value or []),
        normalize_tuner_profiles=lambda value: list(value or []),
        positioning_config_keys=("risk_per_trade_pct", "trailing_stop_pct"),
    )

    aggregate = load_ticker_config_aggregate(ticker="MU", deps=deps)
    applied = resolve_local_aos_applied_snapshot(aggregate)

    assert applied["trading_hours"] == [9, 10]
    assert applied["strategy_selection_mode"] == "all_enabled"
    assert applied["max_active_strategies"] == 4
    assert applied["positioning"]["risk_per_trade_pct"] == 0.7
    assert applied["positioning"]["trailing_stop_pct"] == 0.6


def test_build_effective_ticker_config_rehydrates_active_profile_refs() -> None:
    deps = TickerConfigRepositoryDeps(
        load_aos_config=lambda *_args, **_kwargs: {
            "tickers": {
                "MU": {
                    "active_unified_profile_id": "u1",
                    "active_adaptive_tuner_profile_id": "p1",
                    "unified_profiles": [{"profile_id": "u1", "strategy_profile": {}}],
                    "adaptive_tuner_profiles": [
                        {"profile_id": "p1", "candidate": {"enabled_strategies": ["momentum"]}}
                    ],
                }
            }
        },
        get_ticker_positioning_config=lambda *_args, **_kwargs: {},
        normalize_strategy_combo_profiles=lambda value: list(value or []),
        normalize_unified_profiles=normalize_unified_profiles,
        normalize_tuner_profiles=normalize_tuner_profiles,
        positioning_config_keys=(),
    )

    aggregate = load_ticker_config_aggregate(ticker="MU", deps=deps)
    ticker_config = build_effective_ticker_config(aggregate)

    assert ticker_config["active_unified_profile_id"] == "u1"
    assert ticker_config["active_adaptive_tuner_profile_id"] == "p1"
    assert ticker_config["adaptive_tuner_profiles"][0]["candidate"]["enabled_strategies"] == [
        "momentum"
    ]


def test_resolve_effective_aos_applied_snapshot_prefers_unified_runtime() -> None:
    deps = TickerConfigRepositoryDeps(
        load_aos_config=lambda *_args, **_kwargs: {
            "tickers": {
                "MU": {
                    "trading_hours": [13, 14, 15],
                    "time_filter_enabled": False,
                    "active_unified_profile_id": "u1",
                    "unified_profiles": [
                        {
                            "profile_id": "u1",
                            "strategy_profile": {
                                "strategy_selection_mode": "all_enabled",
                                "max_active_strategies": 5,
                                "trading_hours": [10, 9],
                                "time_filter_enabled": True,
                            },
                            "execution_profile": {
                                "positioning": {"risk_per_trade_pct": 0.8}
                            },
                        }
                    ],
                }
            }
        },
        get_ticker_positioning_config=lambda *_args, **_kwargs: {
            "trailing_stop_pct": 0.6
        },
        normalize_strategy_combo_profiles=lambda value: list(value or []),
        normalize_unified_profiles=normalize_unified_profiles,
        normalize_tuner_profiles=normalize_tuner_profiles,
        positioning_config_keys=("risk_per_trade_pct", "trailing_stop_pct"),
    )

    aggregate = load_ticker_config_aggregate(ticker="MU", deps=deps)
    applied = resolve_effective_aos_applied_snapshot(aggregate, _profile_deps())

    assert applied["trading_hours"] == [9, 10]
    assert applied["time_filter_enabled"] is True
    assert applied["strategy_selection_mode"] == "all_enabled"
    assert applied["positioning"] == {
        "trailing_stop_pct": 0.6,
        "risk_per_trade_pct": 0.8,
    }
