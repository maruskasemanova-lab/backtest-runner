import asyncio
from typing import Any, Dict, List

from src.services.strategy_api_profiles_service import (
    apply_active_adaptive_tuner_profile,
    apply_aos_optimizations,
    extract_profile_runtime_overrides,
)
from src.services.strategy_api_types import StrategyApiIntegrationDeps


class _LoggerStub:
    def info(self, *args: Any, **kwargs: Any) -> None:
        return None

    def warning(self, *args: Any, **kwargs: Any) -> None:
        return None


def _build_deps(apply_calls: List[Dict[str, Dict[str, Any]]]) -> StrategyApiIntegrationDeps:
    async def _apply_strategy_param_map(_url: str, payload: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        apply_calls.append(payload)
        return {"applied_count": len(payload), "failed_count": 0}

    async def _fetch_remote_strategies(_url: str) -> Dict[str, Any]:
        return {"Momentum": {}, "VWAPMagnet": {}, "Pullback": {}}

    async def _apply_orchestrator_config(_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"updated": payload}

    return StrategyApiIntegrationDeps(
        load_strategy_overrides=lambda: {},
        sanitize_strategy_params=lambda value: value if isinstance(value, dict) else {},
        normalize_strategy_combo_profiles=lambda value: value if isinstance(value, list) else [],
        normalize_tuner_profiles=lambda value: value if isinstance(value, list) else [],
        normalize_strategy_selection_mode=lambda _value: "all_enabled",
        normalize_clamped_int=lambda value, default=3, min_value=1, max_value=20: max(
            min_value, min(max_value, int(value if value is not None else default))
        ),
        normalize_momentum_diversification_payload=lambda value: value if isinstance(value, dict) else {},
        load_aos_config=lambda *_args, **_kwargs: {},
        get_ticker_positioning_config=lambda *_args, **_kwargs: {},
        positioning_config_keys=(),
        apply_strategy_param_map=_apply_strategy_param_map,
        apply_orchestrator_config=_apply_orchestrator_config,
        fetch_remote_strategies=_fetch_remote_strategies,
        apply_active_strategy_combo=lambda *_args, **_kwargs: {},
        apply_active_adaptive_tuner_profile=lambda *_args, **_kwargs: {},
        logger=_LoggerStub(),
    )


def test_adaptive_v2_params_do_not_override_active_strategy_combo() -> None:
    calls: List[Dict[str, Dict[str, Any]]] = []
    deps = _build_deps(calls)
    ticker_config = {
        "active_adaptive_tuner_profile_id": "p1",
        "adaptive_tuner_profiles": [
            {
                "profile_id": "p1",
                "candidate": {
                    "enabled_strategies": ["momentum", "vwap_magnet"],
                    "min_confidence": 50,
                    "rr_ratio": 1.6,
                },
            }
        ],
        "active_strategy_combo_profile_id": "combo1",
        "strategy_combo_profiles": [
            {
                "profile_id": "combo1",
                "strategy_params": {
                    "momentum": {"min_confidence": 65, "breakout_pct": 0.2},
                    "vwap_magnet": {"min_distance_pct": 0.4},
                },
            }
        ],
    }

    result = asyncio.run(
        apply_active_adaptive_tuner_profile(
            strategy_api_url="http://localhost:8001",
            ticker_config=ticker_config,
            deps=deps,
        )
    )

    # Only enabled/disabled sync is sent; v2 fallback params are skipped.
    assert len(calls) == 1
    assert "v2_param_sync" not in result
    assert sorted(result.get("v2_param_sync_skipped_combo_strategies", [])) == [
        "momentum",
        "vwap_magnet",
    ]


def test_adaptive_v2_params_apply_when_no_strategy_combo_override() -> None:
    calls: List[Dict[str, Dict[str, Any]]] = []
    deps = _build_deps(calls)
    ticker_config = {
        "active_adaptive_tuner_profile_id": "p1",
        "adaptive_tuner_profiles": [
            {
                "profile_id": "p1",
                "candidate": {
                    "enabled_strategies": ["momentum", "vwap_magnet"],
                    "min_confidence": 50,
                    "rr_ratio": 1.6,
                },
            }
        ],
        "active_strategy_combo_profile_id": None,
        "strategy_combo_profiles": [],
    }

    result = asyncio.run(
        apply_active_adaptive_tuner_profile(
            strategy_api_url="http://localhost:8001",
            ticker_config=ticker_config,
            deps=deps,
        )
    )

    # 1) enabled sync, 2) v2 fallback params sync
    assert len(calls) == 2
    assert "v2_param_sync" in result
    v2_payload = calls[1]
    assert set(v2_payload.keys()) == {"momentum", "vwap_magnet"}
    assert v2_payload["momentum"]["min_confidence"] == 50.0
    assert v2_payload["momentum"]["rr_ratio"] == 1.6


def test_adaptive_v2_params_can_override_strategy_combo_when_opted_in() -> None:
    calls: List[Dict[str, Dict[str, Any]]] = []
    deps = _build_deps(calls)
    ticker_config = {
        "active_adaptive_tuner_profile_id": "p1",
        "adaptive_tuner_profiles": [
            {
                "profile_id": "p1",
                "candidate": {
                    "enabled_strategies": ["momentum", "vwap_magnet"],
                    "min_confidence": 50,
                    "rr_ratio": 1.6,
                    "override_combo_strategy_params": True,
                },
            }
        ],
        "active_strategy_combo_profile_id": "combo1",
        "strategy_combo_profiles": [
            {
                "profile_id": "combo1",
                "strategy_params": {
                    "momentum": {"min_confidence": 65},
                    "vwap_magnet": {"min_distance_pct": 0.4},
                },
            }
        ],
    }

    result = asyncio.run(
        apply_active_adaptive_tuner_profile(
            strategy_api_url="http://localhost:8001",
            ticker_config=ticker_config,
            deps=deps,
        )
    )

    assert len(calls) == 2
    assert result.get("v2_param_sync_override_combo") is True
    v2_payload = calls[1]
    assert set(v2_payload.keys()) == {"momentum", "vwap_magnet"}


def test_extract_runtime_overrides_includes_trading_hours() -> None:
    deps = _build_deps([])
    runtime = extract_profile_runtime_overrides(
        {
            "strategy_selection_mode": "all_enabled",
            "max_active_strategies": 2,
            "trading_hours": [16, "17", 17, 99, -1, "x"],
            "time_filter_enabled": True,
        },
        deps,
    )

    assert runtime["trading_hours"] == [16, 17]
    assert runtime["time_filter_enabled"] is True


def test_apply_aos_optimizations_prefers_adaptive_trading_hours() -> None:
    deps = _build_deps([])
    deps.load_aos_config = lambda *_args, **_kwargs: {
        "tickers": {
            "MU": {
                "strategy": "vwap_magnet",
                "params": {},
                "trading_hours": [15, 16, 17, 18, 19, 20],
                "time_filter_enabled": True,
                "active_adaptive_tuner_profile_id": "p1",
                "adaptive_tuner_profiles": [
                    {
                        "profile_id": "p1",
                        "candidate": {
                            "enabled_strategies": ["vwap_magnet"],
                            "trading_hours": [16, 17, 19],
                            "time_filter_enabled": True,
                        },
                    }
                ],
            }
        }
    }

    result = asyncio.run(
        apply_aos_optimizations(
            strategy_api_url="http://localhost:8001",
            ticker="MU",
            deps=deps,
            remote_sync=False,
        )
    )

    assert result["trading_hours"] == [16, 17, 19]
    assert result["trading_hours_source"] == "adaptive_profile"
    assert result["time_filter_enabled"] is True
