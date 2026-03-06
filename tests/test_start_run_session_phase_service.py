from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict

from src.services.start_run_session_phase_service import (
    SessionPhaseDeps,
    SessionPhaseInputs,
    run_start_session_phase,
)


class _Recorder:
    def __init__(self) -> None:
        self.configure_calls = []

    async def configure_session(self, *args, **kwargs) -> None:
        self.configure_calls.append((args, kwargs))


def _build_inputs(
    *,
    trade_eval_mode: Any = None,
    intrabar_execution_recalc_1s: Any = None,
    use_l2: bool = True,
    has_l2: bool = True,
    trading_config: Dict[str, Any] | None = None,
) -> SessionPhaseInputs:
    request = SimpleNamespace(
        run_id="run-1",
        strategy_api_url="http://localhost:8001",
        regime_filter=None,
        trade_eval_mode=trade_eval_mode,
        intrabar_execution_recalc_1s=intrabar_execution_recalc_1s,
    )
    return SessionPhaseInputs(
        request=request,
        run_key="run-1:MU:2026-02-10",
        ticker="MU",
        range_start="2026-02-10",
        comparable_mode=False,
        execution_cfg={
            "effective_strategy_selection_mode": "adaptive_top_n",
            "effective_max_active_strategies": 3,
            "trading_config": dict(trading_config or {}),
        },
        bars=[
            {
                "timestamp": "2026-02-10T14:30:00Z",
                "open": 100.0,
                "close": 100.2,
            }
        ],
        l2_stats={"has_l2": has_l2},
        requested_l2_confirm=False,
        use_l2=use_l2,
        effective_cold_start_each_day=False,
        momentum_diversification_json=None,
    )


def _run_phase(inputs: SessionPhaseInputs) -> Dict[str, Any]:
    recorder = _Recorder()

    async def _force_enable() -> Dict[str, Any]:
        return {"attempted": False, "applied": False}

    phase_timing = {}
    result = asyncio.run(
        run_start_session_phase(
            inputs=inputs,
            deps=SessionPhaseDeps(
                logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
                configure_session=recorder.configure_session,
                force_enable_all_remote_strategies=_force_enable,
                build_heatmap_memory_catalog=lambda **_kwargs: {
                    "summary": {"catalog_days": 1, "populated_days": 1},
                    "days": {"2026-02-10": {"zones": []}},
                },
            ),
            record_phase_ms=lambda key, _started: phase_timing.setdefault(key, 0.0),
        )
    )
    return {"result": result, "configure_calls": list(recorder.configure_calls)}


def test_session_phase_trade_eval_mode_intrabar_5s_has_priority() -> None:
    payload = _run_phase(
        _build_inputs(
            trade_eval_mode="intrabar_5s",
            intrabar_execution_recalc_1s=False,
            use_l2=False,
            has_l2=False,
        )
    )
    result = payload["result"]

    assert result.effective_trade_eval_mode == "intrabar_5s"
    assert result.effective_intrabar_execution_recalc_1s is True
    assert result.effective_intrabar_eval_step_seconds == 5


def test_session_phase_trade_eval_mode_standard_disables_intrabar() -> None:
    payload = _run_phase(
        _build_inputs(
            trade_eval_mode="standard",
            intrabar_execution_recalc_1s=True,
            use_l2=True,
            has_l2=True,
        )
    )
    result = payload["result"]

    assert result.effective_trade_eval_mode == "standard"
    assert result.effective_intrabar_execution_recalc_1s is False
    assert result.effective_intrabar_eval_step_seconds == 1


def test_session_phase_falls_back_to_explicit_legacy_intrabar_flag() -> None:
    payload = _run_phase(
        _build_inputs(
            trade_eval_mode=None,
            intrabar_execution_recalc_1s=True,
            use_l2=False,
            has_l2=False,
        )
    )
    result = payload["result"]

    assert result.effective_trade_eval_mode == "intrabar_1s"
    assert result.effective_intrabar_execution_recalc_1s is True
    assert result.effective_intrabar_eval_step_seconds == 1


def test_session_phase_falls_back_to_l2_auto_intrabar_behavior() -> None:
    payload = _run_phase(
        _build_inputs(
            trade_eval_mode=None,
            intrabar_execution_recalc_1s=None,
            use_l2=True,
            has_l2=True,
        )
    )
    result = payload["result"]

    assert result.effective_trade_eval_mode == "intrabar_1s"
    assert result.effective_intrabar_execution_recalc_1s is True
    assert result.effective_intrabar_eval_step_seconds == 1


def test_session_phase_includes_heatmap_summary_and_configure_payload() -> None:
    payload = _run_phase(_build_inputs())
    result = payload["result"]
    configure_calls = payload["configure_calls"]

    assert result.session_config_snapshot["heatmap_memory_summary"] == {
        "catalog_days": 1,
        "populated_days": 1,
    }
    assert len(configure_calls) == 1
    _, kwargs = configure_calls[0]
    assert kwargs["heatmap_memory_catalog"]["days"]["2026-02-10"]["zones"] == []


def test_session_phase_forwards_trade_audit_config() -> None:
    payload = _run_phase(
        _build_inputs(
            trading_config={
                "trade_audit_level": "core",
                "trade_audit_fields": ["outcome", "raw.signal_metadata"],
            }
        )
    )
    _, kwargs = payload["configure_calls"][0]

    assert kwargs["trade_audit_level"] == "core"
    assert kwargs["trade_audit_fields"] == ["outcome", "raw.signal_metadata"]
