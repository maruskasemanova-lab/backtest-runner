import asyncio
from datetime import datetime, timezone

import session_runner as session_runner_module
from session_runner import RunConfig, SessionRunner
from src.services.session_runner_models import Err, Ok, StrategyBarResponse
from src.services.session_runner_payload_utils import (
    StrategyBarPayloadInput,
    StrategyBarPayloadBuildContext,
    StrategyBarPayloadBuilder,
    build_strategy_bar_payload,
)
from src.services.session_runner_payload_validator import StrategyBarPayloadValidator
from src.services.session_runner_marker_utils import resolve_signal_marker_snapshot
from src.services.session_runner_trade_utils import resolve_entry_marker_context


def test_strategy_bar_response_validates_nested_trade_payloads() -> None:
    model = StrategyBarResponse.model_validate(
        {
            "phase": "IN_POSITION",
            "regime": "TRENDING",
            "indicators": {
                "trend_efficiency": 0.42,
                "volatility": 0.31,
                "adx": 21.0,
                "atr": 0.64,
            },
            "intraday_levels": {
                "intraday_levels_enabled": True,
                "intraday_levels_entry_quality_enabled": True,
                "intraday_levels_min_levels_for_context": 2,
                "gate": "intraday_levels_entry_quality",
                "score": 3.0,
            },
            "l2_quality": {
                "has_l2": True,
                "coverage_ratio": 0.82,
                "trade_ticks": 17,
                "flags": ["book_sparse"],
            },
            "layer_scores": {
                "engine": "evidence_v1",
            },
            "signal_rejected": {
                "gate": "typed-reject",
                "reason": "insufficient_confluence",
            },
            "golden_setup": {
                "passed": True,
                "reason": "alignment_ok",
                "score": 8.5,
            },
            "intrabar_eval_trace": {
                "checkpoints": [
                    {
                        "s": 0,
                        "layer_scores": {"engine": "checkpoint_engine"},
                        "signal_rejected": {"gate": "checkpoint_gate"},
                        "candidate_diagnostics": {"score": 7},
                    }
                ]
            },
            "tcbbo_confirmation": {
                "confidence_boost": 5.0,
                "sweep_aligned": True,
                "net_premium": 325000.0,
                "trade_count": 14,
            },
            "context_risk": {
                "risk_pct": 0.3,
                "effective_rr": 4.0,
                "sl_reason": "capped_fixed_floor:0.3000",
                "tp_reason": "strategy_take_profit",
            },
            "signals": [
                {
                    "price": 100.1,
                    "signal": "BUY",
                    "strategy": "VWAPMagnet",
                    "confidence": 87,
                    "metadata": {
                        "candidate_diagnostics": {"score": 3},
                        "order_flow": {"signed_aggression": 0.14},
                        "level_context": {"passed": True},
                    },
                }
            ],
            "regime_update": {
                "regime": "TRENDING",
                "strategy": "VWAPMagnet",
                "strategies": ["VWAPMagnet", "adaptive"],
                "switch_guard": {
                    "cooldown_bars": 2,
                    "min_active_bars_before_switch": 5,
                },
            },
            "micro_confirmation": {
                "ready": False,
                "passed": False,
                "required_bars": 2,
                "confirm_bars": 1,
            },
            "intrabar_confirmation": {
                "ready": False,
                "passed": False,
                "reason": "awaiting_intrabar_coverage",
                "window_seconds": 12,
            },
            "position_opened": {
                "entry_price": 100.0,
                "side": "long",
                "strategy": "VWAPMagnet",
                "size": 10,
                "metadata": {
                    "context_risk": {"risk_pct": 0.3},
                    "break_even": {"armed": True, "stop_price": 100.04},
                },
            },
            "position_closed": {
                "exit_price": 100.2,
                "side": "long",
                "exit_reason": "time_exit",
                "pnl_pct": 0.42,
                "pnl_dollars": 4.2,
                "entry_price": 99.8,
                "entry_time": "2026-02-06T14:20:00+00:00",
                "size": 10.0,
                "strategy": "mean_reversion",
                "costs": {"total": 0.3},
                "entry_quality_diagnostics": {
                    "is_first_bar_stop_loss": False,
                    "near_confluence_score": 3,
                },
            },
            "break_even": {
                "armed": True,
                "trigger_rr": 1.0,
                "stop_price": 100.05,
            },
            "session_summary": {
                "run_id": "r0",
                "ticker": "MU",
                "date": "2026-02-06",
                "total_trades": 1,
                "total_pnl_pct": 0.5,
                "selection_warnings": ["missing tcbbo"],
                "success": True,
            },
        }
    )

    assert model.position_opened is not None
    assert model.position_opened.strategy == "VWAPMagnet"
    assert model.position_opened.metadata is not None
    assert model.position_opened.metadata.context_risk is not None
    assert model.position_opened.metadata.context_risk.risk_pct == 0.3
    assert model.position_opened.metadata.break_even is not None
    assert model.position_opened.metadata.break_even.stop_price == 100.04
    assert model.position_closed is not None
    assert model.position_closed.costs is not None
    assert model.position_closed.costs.total == 0.3
    assert model.position_closed.entry_quality_diagnostics is not None
    assert model.position_closed.entry_quality_diagnostics.near_confluence_score == 3
    assert model.regime_update is not None
    assert model.regime_update.strategies == ["VWAPMagnet", "adaptive"]
    assert model.regime_update.switch_guard is not None
    assert model.regime_update.switch_guard.cooldown_bars == 2
    assert model.regime_update.switch_guard.min_active_bars_before_switch == 5
    assert model.micro_confirmation is not None
    assert model.micro_confirmation.required_bars == 2
    assert model.intrabar_confirmation is not None
    assert model.intrabar_confirmation.reason == "awaiting_intrabar_coverage"
    assert model.break_even is not None
    assert model.break_even.stop_price == 100.05
    assert model.signals[0].metadata is not None
    assert model.signals[0].metadata.candidate_diagnostics is not None
    assert model.signals[0].metadata.candidate_diagnostics.score == 3
    assert model.signals[0].metadata.order_flow is not None
    assert model.signals[0].metadata.order_flow.signed_aggression == 0.14
    assert model.signals[0].metadata.level_context is not None
    assert model.signals[0].metadata.level_context.passed is True
    assert model.intraday_levels is not None
    assert model.intraday_levels.gate == "intraday_levels_entry_quality"
    assert model.l2_quality is not None
    assert model.l2_quality.coverage_ratio == 0.82
    assert model.layer_scores is not None
    assert model.layer_scores.engine == "evidence_v1"
    assert model.signal_rejected is not None
    assert model.signal_rejected.gate == "typed-reject"
    assert model.golden_setup is not None
    assert model.golden_setup.passed is True
    assert model.intrabar_eval_trace is not None
    assert model.intrabar_eval_trace.checkpoints[0].s == 0
    assert model.intrabar_eval_trace.checkpoints[0].layer_scores is not None
    assert model.intrabar_eval_trace.checkpoints[0].layer_scores.engine == "checkpoint_engine"
    assert model.intrabar_eval_trace.checkpoints[0].signal_rejected is not None
    assert model.intrabar_eval_trace.checkpoints[0].signal_rejected.gate == "checkpoint_gate"
    assert model.intrabar_eval_trace.checkpoints[0].candidate_diagnostics is not None
    assert model.intrabar_eval_trace.checkpoints[0].candidate_diagnostics.score == 7
    assert model.tcbbo_confirmation is not None
    assert model.tcbbo_confirmation.confidence_boost == 5.0
    assert model.context_risk is not None
    assert model.context_risk.risk_pct == 0.3
    assert model.context_risk.sl_reason == "capped_fixed_floor:0.3000"
    assert model.indicators.trend_efficiency == 0.42
    assert model.indicators.volatility == 0.31
    assert model.indicators.adx == 21.0
    assert model.indicators.atr == 0.64
    assert model.session_summary is not None
    assert model.session_summary.total_pnl_pct == 0.5
    assert model.session_summary.selection_warnings == ["missing tcbbo"]

    dumped = model.model_dump(mode="python", exclude_none=True, exclude_unset=True)

    assert dumped["signals"][0]["metadata"]["candidate_diagnostics"]["score"] == 3
    assert dumped["layer_scores"]["engine"] == "evidence_v1"
    assert dumped["signal_rejected"]["gate"] == "typed-reject"
    assert dumped["golden_setup"]["passed"] is True
    assert dumped["intrabar_eval_trace"]["checkpoints"][0]["candidate_diagnostics"]["score"] == 7
    assert dumped["indicators"]["trend_efficiency"] == 0.42
    assert dumped["regime_update"]["switch_guard"]["cooldown_bars"] == 2
    assert dumped["micro_confirmation"]["required_bars"] == 2
    assert dumped["intrabar_confirmation"]["window_seconds"] == 12
    assert dumped["position_closed"]["costs"]["total"] == 0.3
    assert (
        dumped["position_closed"]["entry_quality_diagnostics"]["near_confluence_score"]
        == 3
    )
    assert dumped["intraday_levels"]["intraday_levels_enabled"] is True
    assert dumped["l2_quality"]["flags"] == ["book_sparse"]
    assert dumped["tcbbo_confirmation"]["trade_count"] == 14
    assert dumped["context_risk"]["effective_rr"] == 4.0
    assert dumped["session_summary"]["selection_warnings"] == ["missing tcbbo"]


def test_to_utc_datetime_accepts_nanosecond_iso_strings() -> None:
    resolved = SessionRunner._to_utc_datetime("2026-02-24T15:00:00.123456789")

    assert resolved == datetime(2026, 2, 24, 15, 0, 0, 123456, tzinfo=timezone.utc)


def test_resolve_bar_runtime_context_accepts_nanosecond_timestamp_strings() -> None:
    runner = SessionRunner.__new__(SessionRunner)
    runner._trade_start_time = None
    runner._trade_end_time = None

    timestamp, warmup_only = runner._resolve_bar_runtime_context(
        {"timestamp": "2026-02-24T15:00:00.000000000"}
    )

    assert timestamp == datetime(2026, 2, 24, 15, 0, 0, tzinfo=timezone.utc)
    assert warmup_only is False


def test_typed_entry_marker_context_extracts_metadata_snapshots() -> None:
    response_model = StrategyBarResponse.model_validate(
        {
            "position_opened": {
                "entry_price": 100.0,
                "side": "long",
                "strategy": "VWAPMagnet",
                "metadata": {
                    "context_risk": {"risk_pct": 0.3, "effective_rr": 4.0},
                    "break_even": {"armed": True, "stop_price": 100.04},
                    "liquidity_sweep": {"detected": True, "atr": 1.25},
                    "sweep_triggered": True,
                },
            }
        }
    )

    assert response_model.position_opened is not None
    entry_context = resolve_entry_marker_context(
        response_model,
        response_model.position_opened,
    )

    assert entry_context.context_risk_payload == {
        "risk_pct": 0.3,
        "effective_rr": 4.0,
    }
    assert entry_context.break_even_payload == {
        "armed": True,
        "stop_price": 100.04,
    }
    assert entry_context.liquidity_sweep_payload == {
        "detected": True,
        "atr": 1.25,
    }
    assert entry_context.sweep_triggered is True


def test_resolve_signal_marker_snapshot_accepts_typed_signal_payload() -> None:
    signal = StrategyBarResponse.model_validate(
        {
            "signals": [
                {
                    "strategy_name": "VWAPMagnet",
                    "signal": "BUY",
                    "confidence": 72,
                    "reasoning": "typed-signal",
                    "stop_loss": 99.7,
                    "take_profit": 101.4,
                }
            ]
        }
    ).signals[0]

    snapshot = resolve_signal_marker_snapshot(signal, default_price=100.5)

    assert snapshot.price == 100.5
    assert snapshot.signal_type == "BUY"
    assert snapshot.strategy == "VWAPMagnet"
    assert snapshot.confidence == 72
    assert snapshot.reasoning == "typed-signal"
    assert snapshot.stop_loss == 99.7
    assert snapshot.take_profit == 101.4


def test_strategy_bar_payload_validator_accepts_explicit_payload_and_rejects_unknown_extra() -> None:
    validator = StrategyBarPayloadValidator()
    accepted = validator.validate(
        {
            "run_id": "r0",
            "ticker": "MU",
            "timestamp": "2026-02-06T14:30:00+00:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 10,
            "l2_schema_version": "l2fv-1.0",
            "l2_quality_flags": ["ok"],
            "l2_quality": {"has_l2": True},
            "tcbbo_has_data": True,
            "intrabar_quotes_1s": [{"s": 1, "bid": 100.1, "ask": 100.15}],
            "ref_ticker": "QQQ",
            "ref_open": 99.5,
        }
    )
    match accepted:
        case Ok(value=payload):
            assert payload["l2_schema_version"] == "l2fv-1.0"
            assert payload["intrabar_quotes_1s"] == [
                {"s": 1, "bid": 100.1, "ask": 100.15}
            ]
        case _:
            raise AssertionError("Expected payload validator to accept explicit fields")

    rejected = validator.validate(
        {
            "run_id": "r0",
            "ticker": "MU",
            "timestamp": "2026-02-06T14:30:00+00:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 10,
            "unexpected_runtime_field": "boom",
        }
    )
    match rejected:
        case Err(error=error_text):
            assert "unexpected_runtime_field" in error_text
        case _:
            raise AssertionError("Expected payload validator to reject unknown fields")


def test_strategy_bar_payload_validator_normalizes_array_like_values() -> None:
    class _FakeArray:
        def __init__(self, values):
            self._values = values

        def tolist(self):
            return list(self._values)

    class _FakeScalar:
        def __init__(self, value):
            self._value = value

        def item(self):
            return self._value

    validator = StrategyBarPayloadValidator()
    accepted = validator.validate(
        {
            "run_id": "r0",
            "ticker": "MU",
            "timestamp": "2026-02-06T14:30:00+00:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 10,
            "l2_quality": {
                "depth_curve": _FakeArray([0.1, 0.2, 0.3]),
                "coverage": _FakeScalar(0.82),
            },
        }
    )
    match accepted:
        case Ok(value=payload):
            assert payload["l2_quality"]["depth_curve"] == [0.1, 0.2, 0.3]
            assert payload["l2_quality"]["coverage"] == 0.82
        case _:
            raise AssertionError("Expected payload validator to normalize array-like values")


def test_process_decision_markers_accepts_typed_response_model() -> None:
    config = RunConfig(run_id="r0typed", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 32, tzinfo=timezone.utc)
    bar = {"close": 100.0}
    response = {
        "regime": "TRENDING",
        "intraday_levels": {"gate": "typed-levels", "score": 2.0},
        "tcbbo_confirmation": {"trade_count": 3, "has_data": True},
        "signals": [
            {
                "price": 100.0,
                "signal": "BUY",
                "strategy": "VWAPMagnet",
                "confidence": 81.0,
                "reasoning": "typed-path",
                "metadata": {
                    "candidate_diagnostics": {"score": 5},
                    "order_flow": {"signed_aggression": 0.22},
                },
            }
        ],
        "break_even": {
            "armed": True,
            "trigger_rr": 1.0,
            "stop_price": 100.05,
        },
        "position_opened": {
            "entry_price": 100.0,
            "side": "long",
            "strategy": "VWAPMagnet",
            "size": 10.0,
            "stop_loss": 99.7,
            "take_profit": 101.2,
            "reasoning": "typed-entry",
            "confidence": 88.0,
            "metadata": {},
        },
    }
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )

    markers = runner.get_markers()
    signal_marker = next(
        marker for marker in markers if marker["marker_type"] == "signal_generated"
    )
    entry_marker = next(
        marker for marker in markers if marker["marker_type"] == "entry_executed"
    )

    assert signal_marker["details"]["signed_aggression"] == 0.22
    assert signal_marker["details"]["intraday_levels"]["gate"] == "typed-levels"
    assert signal_marker["details"]["tcbbo_confirmation"]["trade_count"] == 3
    assert entry_marker["details"]["break_even"]["stop_price"] == 100.05


def test_strategy_bar_payload_input_validates_defaults_and_coercion() -> None:
    payload_input = StrategyBarPayloadInput(
        run_id="r0",
        ticker="MU",
        bar={
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 10,
            "l2_schema_version": "l2fv-1.0",
            "l2_quality_flags": ["ok"],
            "l2_quality": {"has_l2": True},
            "tcbbo_has_data": 1,
            "ignored_runtime_field": "ignore-me",
        },
        timestamp="2026-02-06T14:30:00+00:00",
        intrabar_quotes_1s=[{"s": "1", "bid": "100.1", "ask": 100.15}],
        current_bar_index="7",
        include_pending_entry=1,
    )

    assert payload_input.timestamp == "2026-02-06T14:30:00+00:00"
    assert payload_input.current_bar_index == 7
    assert payload_input.include_pending_entry is True
    assert payload_input.warmup_only is None
    assert payload_input.bar.open == 100.0
    assert payload_input.bar.l2_schema_version == "l2fv-1.0"
    assert payload_input.bar.l2_quality == {"has_l2": True}
    assert payload_input.bar.tcbbo_has_data is True
    assert "ignored_runtime_field" not in payload_input.bar.model_dump(mode="python")
    assert payload_input.intrabar_quotes_1s is not None
    assert payload_input.intrabar_quotes_1s[0].s == 1
    assert payload_input.intrabar_quotes_1s[0].bid == 100.1

    payload = build_strategy_bar_payload(
        payload_input=payload_input,
        l2_payload_keys=("l2_schema_version", "l2_quality_flags", "l2_quality"),
        tcbbo_payload_keys=("tcbbo_has_data",),
        ref_bars_map={
            "2026-02-06T14:30:00+00:00": {
                "open": 99.5,
                "high": 100.5,
                "low": 99.0,
                "close": 100.0,
                "volume": 1500,
            }
        },
    )
    assert payload["l2_schema_version"] == "l2fv-1.0"
    assert payload["l2_quality_flags"] == ["ok"]
    assert payload["l2_quality"] == {"has_l2": True}
    assert payload["tcbbo_has_data"] is True
    assert payload["intrabar_quotes_1s"] == [{"s": 1, "bid": 100.1, "ask": 100.15}]
    assert payload["ref_ticker"] == "QQQ"
    assert payload["ref_open"] == 99.5


def test_strategy_bar_payload_builder_uses_explicit_build_context() -> None:
    builder = StrategyBarPayloadBuilder(
        l2_payload_keys=("l2_quality_flags",),
        tcbbo_payload_keys=(),
        validate_strategy_bar_payload=lambda payload: session_runner_module.Ok(payload),
        logger=session_runner_module.logger,
    )
    payload = builder.build_live_payload(
        payload_input=StrategyBarPayloadInput(
            run_id="r1",
            ticker="MU",
            bar={
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 10,
                "l2_quality_flags": ["ok"],
            },
            timestamp="2026-02-06T14:30:00+00:00",
            current_bar_index=0,
        ),
        build_context=StrategyBarPayloadBuildContext(
            ref_bars_map={
                "2026-02-06T14:30:00+00:00": {
                    "ticker": "QQQ",
                    "open": 99.5,
                    "close": 100.0,
                }
            },
            should_attach_intrabar_quotes=True,
            intrabar_recalc_enabled=True,
            l2_manager_name="DummyL2",
            intrabar_quotes_1s=[{"s": 1, "bid": 100.1, "ask": 100.15}],
        ),
    )

    assert payload["l2_quality_flags"] == ["ok"]
    assert payload["intrabar_quotes_1s"] == [{"s": 1, "bid": 100.1, "ask": 100.15}]
    assert payload["ref_ticker"] == "QQQ"


def test_typed_response_model_drives_bar_analysis_and_market_context() -> None:
    config = RunConfig(run_id="r0typed2", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner.load_bars(
        [
            {
                "timestamp": datetime(2026, 2, 6, 14, 30, tzinfo=timezone.utc),
                "open": 99.5,
                "high": 100.5,
                "low": 99.0,
                "close": 100.0,
                "volume": 1500.0,
                "vwap": 99.8,
            }
        ]
    )

    response_model = StrategyBarResponse.model_validate(
        {
            "phase": "IN_POSITION",
            "regime": "TRENDING",
            "micro_regime": "BREAKOUT",
            "selection_warnings": [],
            "layer_scores": {"engine": "typed"},
            "signal_rejected": {"gate": "typed-reject"},
            "intrabar_eval_trace": {"checkpoints": [{"s": 0}]},
            "l2_quality": {"coverage_ratio": 0.82},
            "signals": [
                {
                    "price": 100.0,
                    "signal": "BUY",
                    "strategy": "VWAPMagnet",
                    "metadata": {"candidate_diagnostics": {"score": 9}},
                }
            ],
            "break_even": {"armed": True, "stop_price": 100.05},
        }
    )

    target: dict = {}
    runner._apply_response_analysis_to_bar(
        target,
        response_model,
        processed_bar_index=0,
        warmup_only=False,
    )
    context = runner._build_marker_market_context(
        bar=runner.bars[0],
        timestamp=runner.bars[0]["timestamp"],
        response=response_model,
    )

    assert target["layer_scores"]["engine"] == "typed"
    assert target["signal_rejected"]["gate"] == "typed-reject"
    assert target["candidate_diagnostics"]["score"] == 9
    assert context["decision_state"]["regime"] == "TRENDING"
    assert context["decision_state"]["micro_regime"] == "BREAKOUT"
    assert context["decision_state"]["selection_warnings"] == []
    assert context["l2"]["l2_quality"]["coverage_ratio"] == 0.82
    assert context["break_even"]["stop_price"] == 100.05


def test_session_end_marker_emitted_only_once() -> None:
    config = RunConfig(run_id="r1", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner.load_bars(
        [
            {
                "timestamp": datetime(2026, 2, 6, 15, 55, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.5,
                "close": 100.5,
                "volume": 1000.0,
            }
        ]
    )

    ts = datetime(2026, 2, 6, 15, 55, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "phase": "END_OF_DAY",
        "session_summary": {"total_pnl_pct": -0.35},
    }

    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )

    markers = runner.get_markers()
    session_end_count = sum(
        1 for marker in markers if marker["marker_type"] == "session_ended"
    )
    assert session_end_count == 1


def test_step_does_not_advance_on_strategy_api_error(monkeypatch) -> None:
    config = RunConfig(
        run_id="r0",
        ticker="MU",
        date="2026-02-06",
        strategy_api_url="http://strategy-api.test",
    )
    runner = SessionRunner(config)
    runner.load_bars(
        [
            {
                "timestamp": datetime(2026, 2, 6, 15, 0, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            }
        ]
    )

    class _ErrorResponse:
        status = 503

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {}

        async def text(self):
            return "strategy unavailable"

    class _ErrorSession:
        def __init__(self, *args, **kwargs):
            self.closed = False

        def post(self, url, **kwargs):
            return _ErrorResponse()

        async def close(self):
            self.closed = True

    monkeypatch.setattr(session_runner_module.httpx, "AsyncClient", _ErrorSession)

    first = asyncio.run(runner.step())
    second = asyncio.run(runner.step())

    assert first["success"] is False
    assert "API error 503" in first["error"]
    assert second["success"] is False
    assert runner.current_bar_index == 0
    assert runner.phase == "ERROR"
    assert runner.is_running is False

    markers = runner.get_markers()
    session_start_count = sum(
        1 for marker in markers if marker["marker_type"] == "session_started"
    )
    assert session_start_count == 1


def test_run_all_stops_after_strategy_api_error(monkeypatch) -> None:
    config = RunConfig(
        run_id="r0b",
        ticker="MU",
        date="2026-02-06",
        strategy_api_url="http://strategy-api.test",
    )
    runner = SessionRunner(config)
    runner.load_bars(
        [
            {
                "timestamp": datetime(2026, 2, 6, 15, 0, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            }
        ]
    )

    class _ErrorResponse:
        status = 503

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {}

        async def text(self):
            return "strategy unavailable"

    class _ErrorSession:
        def __init__(self, *args, **kwargs):
            self.closed = False

        def post(self, url, **kwargs):
            return _ErrorResponse()

        async def close(self):
            self.closed = True

    monkeypatch.setattr(session_runner_module.httpx, "AsyncClient", _ErrorSession)

    summary = asyncio.run(runner.run_all(speed_ms="max"))

    assert runner.is_running is False
    assert runner.current_bar_index == 0
    assert summary["phase"] == "ERROR"
    assert summary["processed_bars"] == 0


def test_step_recovers_when_strategy_session_is_lost(monkeypatch) -> None:
    config = RunConfig(
        run_id="r_recover_1",
        ticker="MU",
        date="2026-02-06",
        strategy_api_url="http://strategy-api.test",
    )
    runner = SessionRunner(config)
    runner._restart_session_date = "2026-02-06"
    runner._restart_session_config = {"regime_detection_minutes": 15}
    runner.load_bars(
        [
            {
                "timestamp": datetime(2026, 2, 6, 15, 0, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            }
        ]
    )

    class _Response:
        def __init__(self, status: int, *, text_payload: str = "", json_payload=None):
            self.status = status
            self._text_payload = text_payload
            self._json_payload = json_payload if json_payload is not None else {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return self._json_payload

        async def text(self):
            return self._text_payload

    class _RecoveringSession:
        def __init__(self, *args, **kwargs):
            self.closed = False
            self.calls = []
            self._bar_call_count = 0

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if str(url).endswith("/api/session/bar"):
                self._bar_call_count += 1
                if self._bar_call_count == 1:
                    return _Response(404, text_payload="Session not found")
                return _Response(
                    200,
                    json_payload={
                        "phase": "TRADING",
                        "action": "hold",
                        "signals": [],
                    },
                )
            if str(url).endswith("/api/session/config"):
                return _Response(200, text_payload='{"success":true}')
            return _Response(500, text_payload="unexpected endpoint")

        async def close(self):
            self.closed = True

    monkeypatch.setattr(session_runner_module.httpx, "AsyncClient", _RecoveringSession)

    result = asyncio.run(runner.step())

    assert result["success"] is True
    assert result["phase"] == "TRADING"
    assert runner.current_bar_index == 1
    assert runner.phase == "TRADING"
    session = runner._strategy_http_session
    assert session is not None
    calls = [entry[0] for entry in session.calls]
    assert calls.count("http://strategy-api.test/api/session/bar") == 2
    assert calls.count("http://strategy-api.test/api/session/config") == 1


def test_replay_historical_bars_only_replays_matching_session_date(monkeypatch) -> None:
    runner = SessionRunner(
        RunConfig(
            run_id="r_replay_1",
            ticker="MU",
            date="2026-02-06_to_2026-02-07",
            strategy_api_url="http://strategy-api.test",
        )
    )
    runner.load_bars(
        [
            {
                "timestamp": datetime(2026, 2, 6, 15, 0, tzinfo=timezone.utc),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            },
            {
                "timestamp": datetime(2026, 2, 7, 15, 0, tzinfo=timezone.utc),
                "open": 101.0,
                "high": 102.0,
                "low": 100.0,
                "close": 101.5,
                "volume": 1100.0,
            },
            {
                "timestamp": datetime(2026, 2, 6, 15, 1, tzinfo=timezone.utc),
                "open": 100.5,
                "high": 101.5,
                "low": 100.0,
                "close": 101.0,
                "volume": 1200.0,
            },
        ]
    )
    runner.current_bar_index = 3

    class _Response:
        def __init__(self, status: int):
            self.status = status

        async def json(self):
            return {}

        async def text(self):
            return ""

    class _ReplaySession:
        def __init__(self, *args, **kwargs):
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return _Response(200)

        async def close(self):
            return None

    monkeypatch.setattr(session_runner_module.httpx, "AsyncClient", _ReplaySession)

    replayed = asyncio.run(runner._replay_historical_bars("2026-02-06"))

    assert replayed is True
    session = runner._strategy_http_session
    assert session is not None
    payloads = [kwargs["json"] for url, kwargs in session.calls if url.endswith("/api/session/bar")]
    assert len(payloads) == 2
    assert [payload["timestamp"] for payload in payloads] == [
        "2026-02-06T15:00:00+00:00",
        "2026-02-06T15:01:00+00:00",
    ]


def test_replay_historical_bars_matches_session_date_in_utc(monkeypatch) -> None:
    runner = SessionRunner(
        RunConfig(
            run_id="r_replay_tz_1",
            ticker="MU",
            date="2026-02-06",
            strategy_api_url="http://strategy-api.test",
        )
    )
    runner.load_bars(
        [
            {
                "timestamp": "2026-02-06T00:30:00+02:00",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
            },
            {
                "timestamp": "2026-02-05T23:30:00-02:00",
                "open": 101.0,
                "high": 102.0,
                "low": 100.0,
                "close": 101.5,
                "volume": 1100.0,
            },
            {
                "timestamp": "2026-02-06T15:01:00+00:00",
                "open": 100.5,
                "high": 101.5,
                "low": 100.0,
                "close": 101.0,
                "volume": 1200.0,
            },
        ]
    )
    runner.current_bar_index = 3

    class _Response:
        def __init__(self, status: int):
            self.status = status

        async def json(self):
            return {}

        async def text(self):
            return ""

    class _ReplaySession:
        def __init__(self, *args, **kwargs):
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return _Response(200)

        async def close(self):
            return None

    monkeypatch.setattr(session_runner_module.httpx, "AsyncClient", _ReplaySession)

    replayed = asyncio.run(runner._replay_historical_bars("2026-02-06"))

    assert replayed is True
    session = runner._strategy_http_session
    assert session is not None
    payloads = [
        kwargs["json"] for url, kwargs in session.calls if url.endswith("/api/session/bar")
    ]
    assert [payload["timestamp"] for payload in payloads] == [
        "2026-02-05T23:30:00-02:00",
        "2026-02-06T15:01:00+00:00",
    ]


def test_session_end_marker_emitted_once_per_market_day() -> None:
    config = RunConfig(run_id="r1b", ticker="MU", date="2026-02-06_to_2026-02-07")
    runner = SessionRunner(config)

    ts_day1 = datetime(2026, 2, 6, 20, 55, tzinfo=timezone.utc)
    ts_day2 = datetime(2026, 2, 7, 20, 55, tzinfo=timezone.utc)
    bar = {"close": 100.5}

    response_day1 = {
        "phase": "END_OF_DAY",
        "session_summary": {"date": "2026-02-06", "total_pnl_pct": -0.35},
    }
    response_day2 = {
        "phase": "END_OF_DAY",
        "session_summary": {"date": "2026-02-07", "total_pnl_pct": 0.42},
    }

    asyncio.run(runner._process_decision_markers(response_day1, bar, ts_day1))
    asyncio.run(runner._process_decision_markers(response_day1, bar, ts_day1))
    asyncio.run(runner._process_decision_markers(response_day2, bar, ts_day2))

    markers = runner.get_markers()
    session_end_count = sum(
        1 for marker in markers if marker["marker_type"] == "session_ended"
    )
    assert session_end_count == 2


def test_session_end_summary_inherits_runner_selection_warnings_when_missing() -> None:
    config = RunConfig(run_id="r1c", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner.selection_warnings = ["missing micro_regime_preferences entry"]

    ts = datetime(2026, 2, 6, 20, 55, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "phase": "END_OF_DAY",
        "session_summary": {"date": "2026-02-06", "total_pnl_pct": -0.35},
    }
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )

    assert runner.session_summary is not None
    assert runner.session_summary["selection_warnings"] == [
        "missing micro_regime_preferences entry"
    ]


def test_signal_marker_includes_tcbbo_confirmation_and_market_context_snapshot() -> (
    None
):
    config = RunConfig(run_id="r_tcbbo_1", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    ts = datetime(2026, 2, 6, 15, 0, tzinfo=timezone.utc)
    bar = {
        "timestamp": ts,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000.0,
        "tcbbo_net_premium": 325000.0,
        "tcbbo_cumulative_net_premium": 920000.0,
        "tcbbo_sweep_count": 2,
        "tcbbo_sweep_premium": 180000.0,
        "tcbbo_trade_count": 14,
        "tcbbo_has_data": True,
    }
    runner.load_bars([bar])

    response = {
        "phase": "TRADING",
        "action": "signal_generated",
        "tcbbo_confirmation": {
            "enabled": True,
            "passed": True,
            "confidence_boost": 5.0,
            "sweep_aligned": True,
        },
        "signals": [
            {
                "signal": "BUY",
                "strategy": "momentum_flow",
                "confidence": 71.0,
                "price": 100.5,
                "reasoning": "TCBBO aligned",
                "metadata": {
                    "tcbbo_confirmation": {
                        "enabled": True,
                        "passed": True,
                        "confidence_boost": 5.0,
                        "sweep_aligned": True,
                    }
                },
            }
        ],
    }

    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )
    markers = runner.get_markers()
    assert len(markers) == 1
    marker = markers[0]

    tcbbo_payload = marker["details"].get("tcbbo_confirmation")
    assert isinstance(tcbbo_payload, dict)
    assert tcbbo_payload.get("confidence_boost") == 5.0
    assert tcbbo_payload.get("sweep_aligned") is True

    market_context = marker["details"].get("market_context")
    assert isinstance(market_context, dict)
    assert isinstance(market_context.get("tcbbo"), dict)
    assert market_context["tcbbo"].get("tcbbo_net_premium") == 325000.0
    assert market_context["tcbbo"].get("tcbbo_sweep_count") == 2


def test_summary_uses_recorded_trades_for_range_totals() -> None:
    config = RunConfig(
        run_id="r1c",
        ticker="MU",
        date="2026-02-01_to_2026-02-05",
        account_size_usd=10_000.0,
    )
    runner = SessionRunner(config)
    runner.current_bar_index = 123
    runner.session_summary = {
        "date": "2026-02-01",
        "total_trades": 1,
        "total_pnl_pct": 0.18,
        "win_rate": 100.0,
    }

    runner.perf_tracker.record_trade(
        strategy="MomentumFlow",
        regime="TRENDING",
        ticker="MU",
        date=config.date,
        side="short",
        entry_price=100.0,
        exit_price=99.0,
        entry_time="2026-02-01T15:00:00+00:00",
        exit_time="2026-02-01T15:05:00+00:00",
        pnl_pct=1.0,
        pnl_dollars=10.0,
        exit_reason="take_profit",
    )
    runner.perf_tracker.record_trade(
        strategy="Evidence:l2_flow_aggression",
        regime="TRENDING",
        ticker="MU",
        date=config.date,
        side="long",
        entry_price=100.0,
        exit_price=99.5,
        entry_time="2026-02-02T15:00:00+00:00",
        exit_time="2026-02-02T15:05:00+00:00",
        pnl_pct=-0.5,
        pnl_dollars=-5.0,
        exit_reason="stop_loss",
    )

    summary = runner.get_summary()["session_summary"]
    assert summary["total_trades"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1
    assert summary["total_pnl_dollars"] == 5.0
    assert summary["total_pnl_pct"] == 0.05
    assert summary["avg_pnl_pct"] == 0.025
    assert summary["bars_processed"] == 123


def test_summary_pnl_pct_sign_tracks_dollar_pnl() -> None:
    config = RunConfig(
        run_id="r1d",
        ticker="MU",
        date="2026-02-01_to_2026-02-05",
        account_size_usd=10_000.0,
    )
    runner = SessionRunner(config)

    # Intentional mismatch in trade-level percentages vs dollars.
    runner.perf_tracker.record_trade(
        strategy="MomentumFlow",
        regime="TRENDING",
        ticker="MU",
        date=config.date,
        side="long",
        entry_price=100.0,
        exit_price=101.0,
        entry_time="2026-02-01T15:00:00+00:00",
        exit_time="2026-02-01T15:05:00+00:00",
        pnl_pct=1.0,
        pnl_dollars=-20.0,
        exit_reason="manual_close",
    )
    runner.perf_tracker.record_trade(
        strategy="MomentumFlow",
        regime="TRENDING",
        ticker="MU",
        date=config.date,
        side="long",
        entry_price=100.0,
        exit_price=101.0,
        entry_time="2026-02-02T15:00:00+00:00",
        exit_time="2026-02-02T15:05:00+00:00",
        pnl_pct=1.0,
        pnl_dollars=-10.0,
        exit_reason="manual_close",
    )

    summary = runner.get_summary()["session_summary"]
    assert summary["total_pnl_dollars"] == -30.0
    assert summary["total_pnl_pct"] == -0.3
    assert summary["avg_pnl_pct"] == -0.15
    assert summary["success"] is False


def test_pattern_marker_skipped_for_evidence_engine() -> None:
    config = RunConfig(run_id="r2", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 10, 0, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "patterns_detected": [
            {"name": "Bullish Harami", "direction": "bullish", "strength": 72.0}
        ],
        "layer_scores": {"engine": "evidence_v1"},
    }

    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )
    markers = runner.get_markers()
    assert all(marker["marker_type"] != "pattern_detected" for marker in markers)


def test_pattern_marker_ignored_even_without_engine_hint() -> None:
    config = RunConfig(run_id="r3", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 10, 0, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "patterns_detected": [
            {"name": "Bullish Harami", "direction": "bullish", "strength": 72.0}
        ]
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    assert all(marker["marker_type"] != "pattern_detected" for marker in markers)


def test_summary_includes_report_context_when_provided() -> None:
    config = RunConfig(run_id="r3b", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner._report_metadata = {
        "unified_profile_id": "mu-unified-v1",
        "unified_profile_name": "MU Unified v1",
        "adaptive_profile_id": "c4bb2197e651",
        "adaptive_profile_name": "c4 adaptive",
        "strategy_combo_profile_id": "mu-combo-v1",
        "strategy_combo_profile_name": "MU Combo v1",
        "config_fingerprint": "cfg_exec123",
        "aos_applied_fingerprint": "cfg_aos456",
    }
    runner._control_plane_snapshot = {
        "config_fingerprint": "cfg_exec123",
        "aos_applied_fingerprint": "cfg_aos456",
        "unified_profile_id": "mu-unified-v1",
    }
    runner._aos_applied = {
        "adaptive_profile": {
            "active_profile_id": "c4bb2197e651",
            "enabled_strategies": ["momentum"],
        }
    }
    runner._execution_config = {"apply_aos_optimizations_on_start": True}
    runner._restart_session_config = {"strategy_selection_mode": "adaptive_top_n"}

    summary = runner.get_summary()
    assert summary["unified_profile_id"] == "mu-unified-v1"
    assert summary["unified_profile_name"] == "MU Unified v1"
    assert summary["adaptive_profile_id"] == "c4bb2197e651"
    assert summary["adaptive_profile_name"] == "c4 adaptive"
    assert summary["strategy_combo_profile_id"] == "mu-combo-v1"
    assert summary["strategy_combo_profile_name"] == "MU Combo v1"
    assert summary["report_metadata"]["adaptive_profile_id"] == "c4bb2197e651"
    assert (
        summary["aos_applied"]["adaptive_profile"]["active_profile_id"]
        == "c4bb2197e651"
    )
    assert summary["execution_config"]["apply_aos_optimizations_on_start"] is True
    assert summary["control_plane_snapshot"]["config_fingerprint"] == "cfg_exec123"
    assert summary["resolved_config_snapshot"]["run_key"] == "r3b:MU:2026-02-06"
    assert (
        summary["resolved_config_snapshot"]["control_plane_snapshot"][
            "aos_applied_fingerprint"
        ]
        == "cfg_aos456"
    )
    assert (
        summary["resolved_config_snapshot"]["report_metadata"]["adaptive_profile_id"]
        == "c4bb2197e651"
    )
    assert (
        summary["resolved_config_snapshot"]["session_config_snapshot"][
            "strategy_selection_mode"
        ]
        == "adaptive_top_n"
    )


def test_strategy_session_config_snapshot_falls_back_to_resolved_snapshot() -> None:
    config = RunConfig(run_id="r3c", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner._restart_session_config = None
    runner._resolved_config_snapshot = {
        "session_config_snapshot": {
            "regime_detection_minutes": 15,
            "l2_confirm_enabled": False,
        }
    }

    resolved = runner._resolve_strategy_session_config_snapshot()

    assert resolved["regime_detection_minutes"] == 15
    assert resolved["l2_confirm_enabled"] is False


def test_regime_explanation_does_not_claim_high_te_when_low() -> None:
    config = RunConfig(run_id="r4", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    response = StrategyBarResponse.model_validate(
        {
            "regime": "TRENDING",
            "micro_regime": "CHOPPY",
            "indicators": {
                "trend_efficiency": 0.04,
                "volatility": 0.28,
                "adx": 17.2,
                "atr": 0.51,
            },
        }
    )

    text = runner._generate_regime_explanation(response)
    assert "high trend efficiency" not in text.lower()
    assert "low" in text.lower()


def test_adaptive_strategy_selected_marker_keeps_all_active_strategies_as_alternatives() -> None:
    config = RunConfig(run_id="r4b", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 10, 5, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "action": "regime_detected",
        "regime": "TRENDING",
        "strategy": "adaptive",
        "strategies": ["adaptive", "momentum_flow", "mean_reversion"],
    }
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )
    markers = runner.get_markers()
    strategy_marker = next(
        marker for marker in markers if marker["marker_type"] == "strategy_selected"
    )

    assert strategy_marker["strategy"] == "adaptive"
    assert strategy_marker["details"]["active_strategies"] == [
        "adaptive",
        "momentum_flow",
        "mean_reversion",
    ]
    assert strategy_marker["details"]["alternative_strategies"] == [
        "adaptive",
        "momentum_flow",
        "mean_reversion",
    ]


def test_typed_regime_update_emits_strategy_switch_guard_and_regime_marker() -> None:
    config = RunConfig(run_id="r4c", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 10, 6, tzinfo=timezone.utc)
    bar = {"close": 100.75}
    response = {
        "regime": "TRENDING",
        "micro_regime": "TRANSITION",
        "indicators": {"trend_efficiency": 0.21},
        "regime_update": {
            "regime": "CHOPPY",
            "strategy": "adaptive",
            "strategies": ["adaptive", "mean_reversion"],
            "switch_guard": {"cooldown_bars": 2},
            "indicators": {"trend_efficiency": 0.08, "adx": 16.0},
        },
    }
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )

    markers = runner.get_markers()
    regime_marker = next(
        marker for marker in markers if marker["marker_type"] == "regime_detected"
    )
    strategy_marker = next(
        marker for marker in markers if marker["marker_type"] == "strategy_selected"
    )

    assert regime_marker["regime"] == "CHOPPY"
    assert "Intraday refresh:" in regime_marker["description"]
    assert strategy_marker["strategy"] == "adaptive"
    assert strategy_marker["details"]["switch_guard"]["cooldown_bars"] == 2
    assert strategy_marker["details"]["active_strategies"] == [
        "adaptive",
        "mean_reversion",
    ]


def test_selection_warnings_propagate_to_run_state() -> None:
    config = RunConfig(run_id="r5", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 10, 0, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response_with_warning = {
        "action": "regime_detected",
        "regime": "CHOPPY",
        "selection_warnings": [
            "missing micro_regime_preferences entry for micro_regime=CHOPPY"
        ],
    }

    asyncio.run(runner._process_decision_markers(response_with_warning, bar, ts))
    state = runner.get_state()
    assert state["selection_warnings"] == [
        "missing micro_regime_preferences entry for micro_regime=CHOPPY"
    ]

    response_without_warning = {
        "action": "regime_detected",
        "regime": "MIXED",
        "selection_warnings": [],
    }
    asyncio.run(runner._process_decision_markers(response_without_warning, bar, ts))
    state = runner.get_state()
    assert state["selection_warnings"] == []


def test_session_summary_preserves_selection_warnings() -> None:
    config = RunConfig(run_id="r6", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner.current_bar_index = 42
    runner.selection_warnings = [
        "missing micro_regime_preferences entry for micro_regime=CHOPPY",
    ]
    runner.session_summary = {
        "date": "2026-02-06",
        "selection_warnings": [
            "missing micro_regime_preferences entry for micro_regime=CHOPPY",
        ],
    }

    summary = runner.get_summary()["session_summary"]
    assert summary is not None
    assert summary["selection_warnings"] == [
        "missing micro_regime_preferences entry for micro_regime=CHOPPY"
    ]
    assert summary["bars_processed"] == 42


def test_data_warnings_are_merged_with_selection_warnings_and_l2_applied_in_state() -> None:
    config = RunConfig(run_id="r6b", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner.current_bar_index = 7
    runner._data_selection_warnings = ["[Data] TCBBO parquet file not found."]
    runner.selection_warnings = ["missing micro_regime_preferences entry"]
    runner._l2_applied = {
        "effective_l2_confirm_enabled": True,
        "tcbbo_gate_enabled": True,
        "tcbbo_available": False,
        "tcbbo_missing_reason": "tcbbo_file_not_found",
        "missing_l2_days_count": 1,
    }
    runner.session_summary = {
        "date": "2026-02-06",
        "selection_warnings": ["missing micro_regime_preferences entry"],
    }

    state = runner.get_state()
    assert state["selection_warnings"] == [
        "[Data] TCBBO parquet file not found.",
        "missing micro_regime_preferences entry",
    ]
    assert state["l2_applied"]["tcbbo_missing_reason"] == "tcbbo_file_not_found"

    summary = runner.get_summary()
    assert summary["l2_applied"]["tcbbo_gate_enabled"] is True
    assert summary["session_summary"]["selection_warnings"] == [
        "[Data] TCBBO parquet file not found.",
        "missing micro_regime_preferences entry",
    ]


def test_summary_persists_strategy_reset_diagnostics() -> None:
    config = RunConfig(run_id="r6c", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)
    runner.current_bar_index = 5
    runner._strategy_state_reset = False
    runner._strategy_state_reset_detail = {
        "success": False,
        "scope": "all",
        "http_status": 503,
        "error": "timeout",
    }
    runner._orchestrator_reset_scope = "all"
    runner.session_summary = {
        "date": "2026-02-06",
        "selection_warnings": [],
    }

    state = runner.get_state()
    assert state["strategy_state_reset"] is False
    assert state["strategy_state_reset_detail"]["http_status"] == 503
    assert state["orchestrator_reset_scope"] == "all"

    summary = runner.get_summary()
    assert summary["strategy_state_reset"] is False
    assert summary["strategy_state_reset_detail"]["error"] == "timeout"
    assert summary["orchestrator_reset_scope"] == "all"
    assert summary["session_summary"]["strategy_state_reset"] is False
    assert summary["session_summary"]["strategy_state_reset_detail"]["scope"] == "all"
    assert summary["session_summary"]["orchestrator_reset_scope"] == "all"


def test_signal_marker_enriches_level_context_from_signal_metadata() -> None:
    config = RunConfig(run_id="r7", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 0, tzinfo=timezone.utc)
    bar = {"close": 100.5}
    response = {
        "signals": [
            {
                "strategy": "VWAPMagnet",
                "signal": "BUY",
                "price": 100.5,
                "confidence": 72.0,
                "metadata": {
                    "level_context": {
                        "gate": "intraday_levels_entry_quality",
                        "passed": True,
                        "reason": "passed",
                    },
                    "order_flow": {
                        "signed_aggression": 0.16,
                    },
                },
            }
        ]
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    signal_marker = next(
        marker for marker in markers if marker["marker_type"] == "signal_generated"
    )
    assert signal_marker["details"]["level_context"]["passed"] is True
    assert signal_marker["details"]["flow_snapshot"]["signed_aggression"] == 0.16
    assert signal_marker["details"]["signed_aggression"] == 0.16


def test_signal_marker_includes_market_context_from_data() -> None:
    config = RunConfig(run_id="r7b", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    bars = [
        {
            "timestamp": datetime(2026, 2, 6, 13, 58, tzinfo=timezone.utc),
            "open": 99.6,
            "high": 100.2,
            "low": 99.4,
            "close": 100.0,
            "volume": 900.0,
            "vwap": 99.9,
        },
        {
            "timestamp": datetime(2026, 2, 6, 13, 59, tzinfo=timezone.utc),
            "open": 100.0,
            "high": 101.3,
            "low": 99.9,
            "close": 101.0,
            "volume": 1100.0,
            "vwap": 100.6,
        },
        {
            "timestamp": datetime(2026, 2, 6, 14, 0, tzinfo=timezone.utc),
            "open": 101.0,
            "high": 102.4,
            "low": 100.8,
            "close": 102.0,
            "volume": 1200.0,
            "vwap": 101.5,
            "l2_signed_aggression": 0.21,
            "l2_imbalance": 0.18,
            "l2_book_pressure": 0.11,
            "l2_quality_flags": ["book_sparse"],
        },
    ]
    runner.load_bars(bars)
    runner.current_bar_index = 2
    ts = bars[2]["timestamp"]
    bar = bars[2]
    runner.ref_bars_map = {
        ts.isoformat(): {
            "ticker": "QQQ",
            "open": 432.0,
            "high": 433.0,
            "low": 431.7,
            "close": 432.6,
            "volume": 1500000,
        }
    }
    response = {
        "action": "signal_generated",
        "regime": "TRENDING",
        "micro_regime": "TRENDING_UP",
        "signals": [
            {
                "strategy": "VWAPMagnet",
                "signal": "BUY",
                "price": 102.0,
                "confidence": 71.0,
                "reasoning": "Flow and momentum aligned",
            }
        ],
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    signal_marker = next(
        marker for marker in markers if marker["marker_type"] == "signal_generated"
    )
    context = signal_marker["details"]["market_context"]

    assert context["bar_ohlcv"]["close"] == 102.0
    assert context["candle"]["bar_return_pct"] > 0
    assert (
        abs(
            context["price_evolution"]["close_change_1_bar_pct"]
            - ((102.0 - 101.0) / 101.0 * 100.0)
        )
        < 1e-9
    )
    assert context["volume_context"]["volume_vs_avg_5_ratio"] > 1.0
    assert context["l2"]["l2_signed_aggression"] == 0.21
    assert context["reference_asset"]["ticker"] == "QQQ"
    assert context["decision_state"]["regime"] == "TRENDING"
    assert len(context["recent_bars"]) == 3


def test_exit_marker_includes_level_context_and_flow_diagnostics() -> None:
    config = RunConfig(run_id="r8", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 30, tzinfo=timezone.utc)
    bar = {"close": 100.2}
    response = {
        "position_closed": {
            "schema_version": 2,
            "exit_price": 100.2,
            "side": "long",
            "exit_reason": "time_exit",
            "pnl_pct": 0.42,
            "pnl_dollars": 4.2,
            "entry_price": 99.8,
            "entry_time": "2026-02-06T14:20:00+00:00",
            "size": 10.0,
            "bars_held": 10,
            "strategy": "mean_reversion",
            "level_context": {"passed": True, "reason": "passed"},
            "flow_snapshot": {"signed_aggression": 0.11, "book_pressure_avg": 0.05},
            "signal_metadata": {"level_context": {"passed": True}},
            "flow_strategy": True,
            "book_pressure_confirmed": True,
            "book_pressure_avg": 0.05,
            "book_pressure_trend": 0.01,
            "signed_aggression": 0.11,
            "entry_quality_diagnostics": {
                "is_first_bar_stop_loss": False,
                "near_confluence_score": 3,
            },
            "costs": {"total": 0.3},
            "cost_usd": 0.3,
        }
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    exit_marker = next(
        marker for marker in markers if marker["marker_type"] == "exit_executed"
    )

    assert exit_marker["details"]["level_context"]["passed"] is True
    assert exit_marker["details"]["flow_snapshot"]["signed_aggression"] == 0.11
    assert exit_marker["details"]["signal_metadata"]["level_context"]["passed"] is True
    assert exit_marker["details"]["flow_strategy"] is True
    assert exit_marker["details"]["book_pressure_confirmed"] is True
    assert exit_marker["details"]["book_pressure_avg"] == 0.05
    assert exit_marker["details"]["book_pressure_trend"] == 0.01
    assert exit_marker["details"]["signed_aggression"] == 0.11
    assert (
        exit_marker["details"]["entry_quality_diagnostics"]["near_confluence_score"]
        == 3
    )


def test_entry_marker_uses_context_risk_from_position_opened_metadata() -> None:
    config = RunConfig(run_id="r8b", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 31, tzinfo=timezone.utc)
    bar = {"close": 100.0}
    response = {
        "position_opened": {
            "entry_price": 100.0,
            "side": "long",
            "strategy": "VWAPMagnet",
            "size": 10.0,
            "stop_loss": 99.7,
            "take_profit": 101.2,
            "reasoning": "entry-opened",
            "confidence": 88.0,
            "metadata": {
                "risk_controls": {
                    "stop_loss_mode": "capped",
                    "fixed_stop_loss_pct": 0.3,
                    "effective_stop_loss": 99.7,
                    "strategy_stop_loss": 99.6,
                },
                "context_risk": {
                    "sl_reason": "capped_fixed_floor:0.3000",
                    "tp_reason": "strategy_take_profit",
                    "risk_pct": 0.3,
                    "effective_rr": 4.0,
                    "skip": False,
                    "skip_reason": "ok",
                },
            },
        }
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    entry_marker = next(
        marker for marker in markers if marker["marker_type"] == "entry_executed"
    )
    context_risk = entry_marker["details"].get("context_risk") or {}

    assert context_risk.get("sl_reason") == "capped_fixed_floor:0.3000"
    assert context_risk.get("tp_reason") == "strategy_take_profit"
    assert context_risk.get("risk_pct") == 0.3
    assert context_risk.get("effective_rr") == 4.0


def test_entry_marker_uses_response_break_even_when_metadata_missing() -> None:
    config = RunConfig(run_id="r8c", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 32, tzinfo=timezone.utc)
    bar = {"close": 100.0}
    response = {
        "break_even": {
            "armed": True,
            "trigger_rr": 1.0,
            "stop_price": 100.05,
        },
        "position_opened": {
            "entry_price": 100.0,
            "side": "long",
            "strategy": "VWAPMagnet",
            "size": 10.0,
            "stop_loss": 99.7,
            "take_profit": 101.2,
            "reasoning": "entry-opened",
            "confidence": 88.0,
            "metadata": {},
        },
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()
    entry_marker = next(
        marker for marker in markers if marker["marker_type"] == "entry_executed"
    )

    assert entry_marker["details"]["break_even"]["armed"] is True
    assert entry_marker["details"]["break_even"]["stop_price"] == 100.05


def test_closed_trade_cost_falls_back_to_costs_total_for_perf_tracker() -> None:
    config = RunConfig(run_id="r8d", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 33, tzinfo=timezone.utc)
    bar = {"close": 100.2}
    response = {
        "regime": "TRENDING",
        "position_closed": {
            "exit_price": 100.2,
            "side": "long",
            "exit_reason": "time_exit",
            "pnl_pct": 0.42,
            "pnl_dollars": 4.2,
            "entry_price": 99.8,
            "entry_time": "2026-02-06T14:20:00+00:00",
            "size": 10.0,
            "bars_held": 10,
            "strategy": "mean_reversion",
            "costs": {"total": 0.45},
        },
    }
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )
    trades = runner.perf_tracker.get_all_trades()

    assert len(trades) == 1
    assert trades[0].total_costs == 0.45
    assert trades[0].regime == "TRENDING"


def test_summary_includes_entry_timing_diagnostics() -> None:
    config = RunConfig(
        run_id="r9",
        ticker="MU",
        date="2026-02-01_to_2026-02-05",
        account_size_usd=10_000.0,
    )
    runner = SessionRunner(config)

    runner.perf_tracker.record_trade(
        strategy="VWAPMagnet",
        regime="MIXED",
        ticker="MU",
        date=config.date,
        side="long",
        entry_price=100.0,
        exit_price=99.8,
        entry_time="2026-02-01T15:00:00+00:00",
        exit_time="2026-02-01T15:01:00+00:00",
        pnl_pct=-0.2,
        pnl_dollars=-2.0,
        exit_reason="stop_loss",
        bars_held=1,
        entry_quality_diagnostics={
            "is_first_bar_stop_loss": True,
            "first_bar_stop_tags": [
                "tight_stop_distance",
                "missing_tested_level_confluence",
            ],
        },
    )
    runner.perf_tracker.record_trade(
        strategy="MeanReversion",
        regime="MIXED",
        ticker="MU",
        date=config.date,
        side="long",
        entry_price=100.0,
        exit_price=100.4,
        entry_time="2026-02-01T15:05:00+00:00",
        exit_time="2026-02-01T15:10:00+00:00",
        pnl_pct=0.4,
        pnl_dollars=4.0,
        exit_reason="take_profit",
        bars_held=5,
    )

    summary = runner.get_summary()["session_summary"] or {}
    diag = summary.get("entry_timing_diagnostics") or {}
    vwap_diag = summary.get("vwap_magnet_entry_timing_diagnostics") or {}

    assert diag["first_bar_stop_exits"] == 1
    assert diag["first_bar_stop_tag_counts"]["tight_stop_distance"] == 1
    assert vwap_diag["first_bar_stop_exits"] == 1
    assert vwap_diag["first_bar_stop_rate_pct"] == 100.0


def test_no_fill_marker_includes_insufficient_fill_reason() -> None:
    config = RunConfig(run_id="r10", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 35, tzinfo=timezone.utc)
    bar = {"open": 100.0, "close": 100.2}
    response = {
        "action": "insufficient_fill",
        "reason": "Position size after risk/fill constraints is zero.",
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()

    assert len(markers) == 1
    marker = markers[0]
    assert marker["marker_type"] == "execution_status"
    assert marker["title"] == "Signal Dropped (Insufficient Fill)"
    assert marker["details"]["execution_status"] == "no_fill"
    assert marker["details"]["execution_action"] == "insufficient_fill"
    assert (
        marker["details"]["reason"]
        == "Position size after risk/fill constraints is zero."
    )


def test_stale_pending_signal_drop_emits_explicit_no_fill_marker() -> None:
    config = RunConfig(run_id="r11", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 36, tzinfo=timezone.utc)
    bar = {"open": 100.1, "close": 100.1}
    response = {
        "stale_pending_signal_dropped": True,
        "stale_pending_signal_age_bars": 4,
        "pending_signal_ttl_bars": 3,
    }

    asyncio.run(runner._process_decision_markers(response, bar, ts))
    markers = runner.get_markers()

    assert len(markers) == 1
    marker = markers[0]
    assert marker["marker_type"] == "execution_status"
    assert marker["title"] == "Signal Dropped (Stale)"
    assert marker["details"]["execution_action"] == "stale_pending_signal_dropped"
    assert marker["details"]["execution_status"] == "no_fill"
    assert marker["details"]["stale_pending_signal_age_bars"] == 4
    assert marker["details"]["pending_signal_ttl_bars"] == 3
    assert (
        marker["details"]["reason"]
        == "Pending signal expired after 4 bars (ttl 3 bars)."
    )


def test_pending_micro_confirmation_emits_pending_execution_marker() -> None:
    config = RunConfig(run_id="r12", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 37, tzinfo=timezone.utc)
    bar = {"open": 100.3, "close": 100.25}
    response = {
        "action": "pending_micro_confirmation",
        "reason": "Awaiting consecutive close confirmation.",
        "micro_confirmation": {
            "ready": False,
            "passed": False,
            "required_bars": 2,
            "confirm_bars": 1,
        },
    }
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )
    markers = runner.get_markers()

    assert len(markers) == 1
    marker = markers[0]
    assert marker["marker_type"] == "execution_status"
    assert marker["title"] == "Signal Pending Confirmation"
    assert marker["details"]["execution_status"] == "pending"
    assert marker["details"]["execution_action"] == "pending_micro_confirmation"
    assert marker["details"]["reason"] == "Awaiting consecutive close confirmation."
    assert marker["details"]["micro_confirmation"]["required_bars"] == 2


def test_pending_intrabar_confirmation_emits_pending_execution_marker() -> None:
    config = RunConfig(run_id="r13", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 38, tzinfo=timezone.utc)
    bar = {"open": 100.35, "close": 100.31}
    response = {
        "action": "pending_intrabar_confirmation",
        "reason": "Awaiting intrabar flow confirmation.",
        "intrabar_confirmation": {
            "ready": False,
            "passed": False,
            "reason": "awaiting_intrabar_coverage",
        },
    }
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )
    markers = runner.get_markers()

    assert len(markers) == 1
    marker = markers[0]
    assert marker["marker_type"] == "execution_status"
    assert marker["title"] == "Signal Pending Intrabar Confirmation"
    assert marker["details"]["execution_status"] == "pending"
    assert marker["details"]["execution_action"] == "pending_intrabar_confirmation"
    assert marker["details"]["reason"] == "Awaiting intrabar flow confirmation."
    assert (
        marker["details"]["intrabar_confirmation"]["reason"]
        == "awaiting_intrabar_coverage"
    )


def test_intrabar_confirmation_failed_emits_no_fill_execution_marker() -> None:
    config = RunConfig(run_id="r14", ticker="MU", date="2026-02-06")
    runner = SessionRunner(config)

    ts = datetime(2026, 2, 6, 14, 39, tzinfo=timezone.utc)
    bar = {"open": 100.40, "close": 100.22}
    response = {
        "action": "intrabar_confirmation_failed",
        "reason": "Intrabar confirmation gate failed.",
        "intrabar_confirmation": {
            "ready": True,
            "passed": False,
            "reason": "intrabar_push_below_threshold",
        },
    }
    response_model = StrategyBarResponse.model_validate(response)

    asyncio.run(
        runner._process_decision_markers(
            response,
            bar,
            ts,
            response_model=response_model,
        )
    )
    markers = runner.get_markers()

    assert len(markers) == 1
    marker = markers[0]
    assert marker["marker_type"] == "execution_status"
    assert marker["title"] == "Signal Dropped (Intrabar Confirmation)"
    assert marker["details"]["execution_status"] == "no_fill"
    assert marker["details"]["execution_action"] == "intrabar_confirmation_failed"
    assert marker["details"]["reason"] == "Intrabar confirmation gate failed."
    assert marker["details"]["intrabar_confirmation"]["passed"] is False
