from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List

from src.models.tuner_requests import AdaptiveTunerRequest
from src.services import adaptive_tuner_runtime_service as svc


def _build_request(**overrides: Any) -> AdaptiveTunerRequest:
    payload = {
        "ticker": "MU",
        "date_from": "2026-02-03",
        "date_to": "2026-02-04",
        "strategy_api_url": "inprocess",
        "score_metric": "pnl_pct",
        "adaptive_version": 1,
    }
    payload.update(overrides)
    return AdaptiveTunerRequest(**payload)


def _build_deps() -> svc.AdaptiveTunerRuntimeDeps:
    async def _unexpected_start_run(_request: Any) -> Dict[str, Any]:
        raise AssertionError("start_run should not be called in parallel day mode test")

    return svc.AdaptiveTunerRuntimeDeps(
        active_runners={},
        start_run=_unexpected_start_run,
        start_run_request_cls=SimpleNamespace,
        normalize_strategy_selection_mode=lambda value: str(
            value or "adaptive_top_n"
        ).strip().lower(),
        normalize_clamped_int=lambda value, default, min_value, max_value: max(
            min_value,
            min(max_value, int(value if value is not None else default)),
        ),
        compute_tuner_score=lambda **kwargs: float(kwargs.get("total_pnl_pct", 0.0)),
        compute_tuner_score_robust=lambda day_results: float(len(day_results)),
        apply_strategy_param_map=lambda *_args, **_kwargs: asyncio.sleep(0),
        apply_orchestrator_config=lambda *_args, **_kwargs: asyncio.sleep(0),
        adaptive_tuner_merge_lock=SimpleNamespace(),
        load_aos_config=lambda: {},
        save_aos_config=lambda _cfg: True,
        build_tuner_profile_entry=lambda **kwargs: kwargs,
        normalize_tuner_profiles=lambda value: value,
        build_v2_candidate_config=lambda cfg, _cand, _version: cfg,
        build_adaptive_candidate_config=lambda cfg, _cand, _version: cfg,
    )


def test_evaluate_adaptive_candidate_parallel_path(monkeypatch) -> None:
    deps = _build_deps()
    captured_payloads: List[Dict[str, Any]] = []

    async def _fake_parallel(
        day_payloads: List[Dict[str, Any]],
        *,
        max_workers: int,
    ) -> List[Dict[str, Any]]:
        assert max_workers == 2
        captured_payloads.extend(day_payloads)
        return [
            {
                "date": "2026-02-03",
                "success": True,
                "pnl_pct": 0.4,
                "pnl_dollars": 40.0,
                "win_rate_pct": 60.0,
                "trades": 3,
            },
            {
                "date": "2026-02-04",
                "success": True,
                "pnl_pct": 0.6,
                "pnl_dollars": 60.0,
                "win_rate_pct": 70.0,
                "trades": 5,
            },
        ]

    monkeypatch.setattr(svc, "_resolve_day_parallel_workers", lambda **_kwargs: 2)
    monkeypatch.setattr(svc, "_evaluate_tuner_days_parallel", _fake_parallel)

    result = asyncio.run(
        svc.evaluate_adaptive_tuner_candidate(
            job_id="job12345",
            ticker="MU",
            dates=["2026-02-03", "2026-02-04"],
            trial_index=1,
            candidate={"max_active_strategies": 4},
            request=_build_request(),
            deps=deps,
            aos_config_path="/tmp/tuner-aos.json",
        )
    )

    assert result["metrics"]["valid_days"] == 2
    assert result["metrics"]["total_trades"] == 8
    assert result["metrics"]["total_pnl_pct"] == 1.0
    assert len(captured_payloads) == 2
    assert captured_payloads[0]["run_request"]["aos_config_path"] == "/tmp/tuner-aos.json"


def test_evaluate_v2_candidate_parallel_path(monkeypatch) -> None:
    deps = _build_deps()
    captured_payloads: List[Dict[str, Any]] = []

    async def _fake_parallel(
        day_payloads: List[Dict[str, Any]],
        *,
        max_workers: int,
    ) -> List[Dict[str, Any]]:
        assert max_workers == 2
        captured_payloads.extend(day_payloads)
        return [
            {
                "date": "2026-02-03",
                "success": True,
                "pnl_pct": 0.3,
                "pnl_dollars": 30.0,
                "win_rate_pct": 55.0,
                "trades": 2,
                "regime_breakdown": {"TRENDING": 2},
                "l2_avg_score": 0.42,
            },
            {
                "date": "2026-02-04",
                "success": False,
                "error": "boom",
            },
        ]

    monkeypatch.setattr(svc, "_resolve_day_parallel_workers", lambda **_kwargs: 2)
    monkeypatch.setattr(svc, "_evaluate_tuner_days_parallel", _fake_parallel)

    candidate = {
        "enabled_strategies": ["momentum_flow", "pullback"],
        "min_confidence": 0.7,
        "atr_stop_multiplier": 1.8,
        "rr_ratio": 2.2,
        "trailing_stop_pct": 0.6,
        "base_threshold": 55.0,
        "min_confirming_sources": 2,
    }
    result = asyncio.run(
        svc.evaluate_v2_candidate(
            job_id="jobv2",
            ticker="MU",
            dates=["2026-02-03", "2026-02-04"],
            trial_index=3,
            candidate=candidate,
            request=_build_request(adaptive_version=2),
            deps=deps,
            aos_config_path="/tmp/tuner-aos-v2.json",
        )
    )

    assert result["metrics"]["valid_days"] == 1
    assert result["metrics"]["total_trades"] == 2
    assert result["metrics"]["total_pnl_pct"] == 0.3
    assert len(captured_payloads) == 2
    assert captured_payloads[0]["v2_param_map"]["momentum_flow"]["rr_ratio"] == 2.2
    assert captured_payloads[0]["v2_orchestrator_payload"]["base_threshold"] == 55.0
