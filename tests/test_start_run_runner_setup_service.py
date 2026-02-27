from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import src.services.start_run_runner_setup_service as svc


class _DummyLogger:
    def info(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


class _DummyRunner:
    def __init__(self):
        self.bars = []
        self.ref_bars_map = {}
        self._progressive_loading_complete = False
        self._progressive_loading_loaded_until = "2025-10-04"
        self._progressive_loading_pending_chunks = 0
        self._progressive_loading_last_error = None


def _to_utc_datetime(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def _build_inputs(run_key: str) -> svc.RunnerSetupInputs:
    return svc.RunnerSetupInputs(
        request=SimpleNamespace(run_id="run-1"),
        run_key=run_key,
        run_date_label="2025-10-01_to_2025-10-31",
        ticker="MU",
        range_start="2025-10-01",
        range_end="2025-10-31",
        load_range_start="2025-10-01",
        load_range_end="2025-10-04",
        full_range_start="2025-10-01",
        full_range_end="2025-10-31",
        comparable_mode=False,
        bars=[],
        ref_bars_map={},
        session_config_snapshot={},
        effective_intrabar_execution_recalc_1s=False,
        effective_intrabar_eval_step_seconds=5,
        checkpoint_loaded=None,
        progressive_plan={"chunks": []},
        aos_applied={},
        requested_l2_only=False,
        requested_l2_confirm=False,
    )


def _build_deps(run_key: str, runner: _DummyRunner) -> svc.RunnerSetupDeps:
    async def _broadcast(_payload):
        return None

    return svc.RunnerSetupDeps(
        active_runners={run_key: runner},
        logger=_DummyLogger(),
        data_loader=None,
        databento_svc=None,
        l2_manager=None,
        get_discovery=lambda: None,
        broadcast=_broadcast,
        run_config_cls=None,
        session_runner_cls=None,
        to_utc_datetime=_to_utc_datetime,
        build_l2_feature_map=None,
        normalize_l2_feature_map_for_market_day_sessions=None,
        attach_l2_features=None,
        load_run_bars=None,
        enrich_bars_with_l2=None,
        load_reference_bars_map=None,
    )


def _chunk_bar(ts: str) -> dict:
    return {"timestamp": ts, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}


@pytest.mark.asyncio
async def test_append_remaining_chunks_marks_complete_only_after_all_chunks(monkeypatch):
    run_key = "run-1:MU:2025-10-01_to_2025-10-31"
    runner = _DummyRunner()
    deps = _build_deps(run_key, runner)
    inputs = _build_inputs(run_key)

    chunk_payloads = {
        ("2025-10-05", "2025-10-08"): (
            [_chunk_bar("2025-10-06T14:00:00+00:00")],
            {"2025-10-06T14:00:00+00:00": {"close": 1.0}},
        ),
        ("2025-10-09", "2025-10-12"): (
            [_chunk_bar("2025-10-09T14:00:00+00:00")],
            {"2025-10-09T14:00:00+00:00": {"close": 1.0}},
        ),
    }

    def _fake_load_chunk_payload(*, chunk_start, chunk_end, inputs, deps):
        return chunk_payloads[(chunk_start, chunk_end)]

    monkeypatch.setattr(svc, "_load_chunk_payload", _fake_load_chunk_payload)

    await svc._append_remaining_chunks(
        runner=runner,
        inputs=inputs,
        deps=deps,
        pending_chunks=[
            ("2025-10-05", "2025-10-08"),
            ("2025-10-09", "2025-10-12"),
        ],
    )

    assert len(runner.bars) == 2
    assert runner._progressive_loading_complete is True
    assert runner._progressive_loading_loaded_until == "2025-10-31"
    assert runner._progressive_loading_pending_chunks == 0
    assert runner._progressive_loading_last_error is None


@pytest.mark.asyncio
async def test_append_remaining_chunks_keeps_incomplete_state_when_runner_not_active(monkeypatch):
    run_key = "run-1:MU:2025-10-01_to_2025-10-31"
    runner = _DummyRunner()
    deps = _build_deps(run_key, runner)
    deps.active_runners[run_key] = _DummyRunner()
    inputs = _build_inputs(run_key)

    monkeypatch.setattr(
        svc,
        "_load_chunk_payload",
        lambda **kwargs: pytest.fail("chunk loader should not run after active-runner mismatch"),
    )

    await svc._append_remaining_chunks(
        runner=runner,
        inputs=inputs,
        deps=deps,
        pending_chunks=[
            ("2025-10-05", "2025-10-08"),
            ("2025-10-09", "2025-10-12"),
        ],
    )

    assert runner.bars == []
    assert runner._progressive_loading_complete is False
    assert runner._progressive_loading_loaded_until == "2025-10-04"
    assert runner._progressive_loading_pending_chunks == 2
    assert (
        runner._progressive_loading_last_error
        == "progressive_loading_aborted_runner_not_active"
    )


@pytest.mark.asyncio
async def test_append_remaining_chunks_records_cancellation_without_marking_complete(monkeypatch):
    run_key = "run-1:MU:2025-10-01_to_2025-10-31"
    runner = _DummyRunner()
    deps = _build_deps(run_key, runner)
    inputs = _build_inputs(run_key)
    call_count = {"value": 0}

    def _fake_load_chunk_payload(*, chunk_start, chunk_end, inputs, deps):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return ([_chunk_bar("2025-10-06T14:00:00+00:00")], {})
        raise asyncio.CancelledError()

    monkeypatch.setattr(svc, "_load_chunk_payload", _fake_load_chunk_payload)

    with pytest.raises(asyncio.CancelledError):
        await svc._append_remaining_chunks(
            runner=runner,
            inputs=inputs,
            deps=deps,
            pending_chunks=[
                ("2025-10-05", "2025-10-08"),
                ("2025-10-09", "2025-10-12"),
            ],
        )

    assert len(runner.bars) == 1
    assert runner._progressive_loading_complete is False
    assert runner._progressive_loading_loaded_until == "2025-10-08"
    assert runner._progressive_loading_pending_chunks == 1
    assert (
        runner._progressive_loading_last_error
        == "progressive_loading_cancelled_before_completion"
    )
