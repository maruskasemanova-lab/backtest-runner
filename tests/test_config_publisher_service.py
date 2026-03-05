from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from src.normalization import normalize_tuner_profiles, normalize_unified_profiles
from src.services.config_domain import (
    TickerConfigRepositoryDeps,
    load_ticker_config_aggregate,
    resolve_effective_aos_state,
)
from src.services.config_publisher_service import publish_effective_aos_state
from src.services.config_publisher_service import (
    publish_active_adaptive_tuner_profile,
    publish_active_strategy_combo,
)
from src.services.strategy_api_types import StrategyApiIntegrationDeps


class _LoggerStub:
    def info(self, *args: Any, **kwargs: Any) -> None:
        return None

    def warning(self, *args: Any, **kwargs: Any) -> None:
        return None


def _build_deps(
    apply_calls: List[Dict[str, Dict[str, Any]]],
) -> StrategyApiIntegrationDeps:
    async def _apply_strategy_param_map(
        _url: str, payload: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        apply_calls.append(payload)
        return {"applied_count": len(payload), "failed_count": 0}

    async def _fetch_remote_strategies(_url: str) -> Dict[str, Any]:
        return {"Momentum": {}, "VWAPMagnet": {}, "Pullback": {}}

    async def _apply_orchestrator_config(
        _url: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {"updated": payload}

    deps = StrategyApiIntegrationDeps(
        load_strategy_overrides=lambda: {},
        sanitize_strategy_params=lambda value: value if isinstance(value, dict) else {},
        normalize_strategy_combo_profiles=lambda value: (
            value if isinstance(value, list) else []
        ),
        normalize_unified_profiles=normalize_unified_profiles,
        normalize_tuner_profiles=normalize_tuner_profiles,
        normalize_strategy_selection_mode=lambda _value: "all_enabled",
        normalize_clamped_int=lambda value, default=3, min_value=1, max_value=20: max(
            min_value, min(max_value, int(value if value is not None else default))
        ),
        normalize_momentum_diversification_payload=lambda value: (
            value if isinstance(value, dict) else {}
        ),
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
    
    async def _publish_combo(
        strategy_api_url: str, ticker: str, ticker_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await publish_active_strategy_combo(
            strategy_api_url=strategy_api_url,
            ticker=ticker,
            ticker_config=ticker_config,
            deps=deps,
        )

    async def _publish_adaptive(
        strategy_api_url: str,
        ticker_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await publish_active_adaptive_tuner_profile(
            strategy_api_url=strategy_api_url,
            ticker_config=ticker_config,
            deps=deps,
        )

    deps.apply_active_strategy_combo = _publish_combo
    deps.apply_active_adaptive_tuner_profile = _publish_adaptive
    return deps


def test_publish_effective_aos_state_publishes_unified_strategy_sync() -> None:
    calls: List[Dict[str, Dict[str, Any]]] = []
    deps = _build_deps(calls)
    deps.load_aos_config = lambda *_args, **_kwargs: {
        "tickers": {
            "MU": {
                "active_unified_profile_id": "u1",
                "unified_profiles": [
                    {
                        "profile_id": "u1",
                        "profile_name": "MU Unified",
                        "strategy_profile": {
                            "strategy_params": {
                                "momentum": {"enabled": True, "min_confidence": 58.0}
                            },
                            "trading_hours": [9, 10],
                        },
                    }
                ],
            }
        }
    }

    aggregate = load_ticker_config_aggregate(
        ticker="MU",
        deps=TickerConfigRepositoryDeps(
            load_aos_config=deps.load_aos_config,
            get_ticker_positioning_config=deps.get_ticker_positioning_config,
            normalize_strategy_combo_profiles=deps.normalize_strategy_combo_profiles,
            normalize_unified_profiles=deps.normalize_unified_profiles,
            normalize_tuner_profiles=deps.normalize_tuner_profiles,
            positioning_config_keys=deps.positioning_config_keys,
        ),
    )
    state = resolve_effective_aos_state(aggregate, deps)
    result = asyncio.run(
        publish_effective_aos_state(
            strategy_api_url="http://localhost:8001",
            ticker="MU",
            state=state,
            deps=deps,
        )
    )

    assert len(calls) == 1
    assert result["unified_profile"]["active_profile_id"] == "u1"
    assert result["unified_profile"]["strategy_sync"]["applied_count"] == 1


def test_publish_effective_aos_state_legacy_enriches_adaptive_and_strategy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: List[Dict[str, Dict[str, Any]]] = []
    deps = _build_deps(calls)
    deps.load_aos_config = lambda *_args, **_kwargs: {
        "tickers": {
            "MU": {
                "strategy": "vwap_magnet",
                "params": {"min_confidence": 42.0},
                "active_adaptive_tuner_profile_id": "p1",
                "adaptive_tuner_profiles": [
                    {
                        "profile_id": "p1",
                        "candidate": {
                            "enabled_strategies": ["Momentum"],
                            "trading_hours": [10, 11],
                            "time_filter_enabled": True,
                        },
                    }
                ],
            }
        }
    }

    class _Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _Session:
        def post(self, *args: Any, **kwargs: Any):
            return _Response()

    class _SessionContext:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "src.services.config_publisher_service.normalize_strategy_api_base_url",
        lambda value: value,
    )
    monkeypatch.setattr(
        "src.services.config_publisher_service.open_strategy_api_session",
        lambda **_kwargs: _SessionContext(),
    )

    aggregate = load_ticker_config_aggregate(
        ticker="MU",
        deps=TickerConfigRepositoryDeps(
            load_aos_config=deps.load_aos_config,
            get_ticker_positioning_config=deps.get_ticker_positioning_config,
            normalize_strategy_combo_profiles=deps.normalize_strategy_combo_profiles,
            normalize_unified_profiles=deps.normalize_unified_profiles,
            normalize_tuner_profiles=deps.normalize_tuner_profiles,
            positioning_config_keys=deps.positioning_config_keys,
        ),
    )
    state = resolve_effective_aos_state(aggregate, deps)
    result = asyncio.run(
        publish_effective_aos_state(
            strategy_api_url="http://localhost:8001",
            ticker="MU",
            state=state,
            deps=deps,
        )
    )

    assert result["strategy"] == "vwap_magnet"
    assert result["adaptive_profile"]["runtime_overrides"]["trading_hours"] == [10, 11]
    assert result["adaptive_profile"]["enabled_sync"]["applied_count"] == 3
    assert len(calls) == 1
