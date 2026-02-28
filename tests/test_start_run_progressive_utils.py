from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import src.services.start_run_runner_setup_service as runner_setup_service
from src.services.start_run_progressive_utils import (
    finalize_progressive_loading,
    is_active_runner,
    update_progressive_chunk_state,
)


def test_is_active_runner_matches_exact_instance() -> None:
    runner = object()
    other = object()

    assert is_active_runner(active_runners={"run": runner}, run_key="run", runner=runner) is True
    assert is_active_runner(active_runners={"run": other}, run_key="run", runner=runner) is False


def test_update_progressive_chunk_state_sets_progress() -> None:
    runner = SimpleNamespace(
        _progressive_loading_loaded_until=None,
        _progressive_loading_pending_chunks=None,
    )

    update_progressive_chunk_state(
        runner=runner,
        chunk_end="2025-10-08",
        remaining_chunks=2,
    )

    assert runner._progressive_loading_loaded_until == "2025-10-08"
    assert runner._progressive_loading_pending_chunks == 2


def test_finalize_progressive_loading_marks_complete_and_preserves_abort_reason() -> None:
    runner = SimpleNamespace(
        _progressive_loading_complete=False,
        _progressive_loading_pending_chunks=3,
        _progressive_loading_loaded_until="2025-10-04",
        _progressive_loading_last_error=None,
    )

    finalize_progressive_loading(
        runner=runner,
        completion_status="completed",
        remaining_chunks=0,
        full_range_end="2025-10-31",
    )

    assert runner._progressive_loading_complete is True
    assert runner._progressive_loading_pending_chunks == 0
    assert runner._progressive_loading_loaded_until == "2025-10-31"

    runner = SimpleNamespace(
        _progressive_loading_complete=False,
        _progressive_loading_pending_chunks=3,
        _progressive_loading_loaded_until="2025-10-04",
        _progressive_loading_last_error=None,
    )
    finalize_progressive_loading(
        runner=runner,
        completion_status="aborted",
        remaining_chunks=2,
        full_range_end="2025-10-31",
        abort_reason="progressive_loading_aborted_runner_not_active",
    )

    assert runner._progressive_loading_complete is False
    assert runner._progressive_loading_pending_chunks == 2
    assert (
        runner._progressive_loading_last_error
        == "progressive_loading_aborted_runner_not_active"
    )


def test_append_remaining_chunks_runs_to_completion_without_asyncio_plugin(
    monkeypatch,
) -> None:
    class _DummyLogger:
        def info(self, *args, **kwargs):
            return None

        def exception(self, *args, **kwargs):
            return None

    class _DummyRunner:
        def __init__(self) -> None:
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

    async def _broadcast(_payload):
        return None

    runner = _DummyRunner()
    run_key = "run-1:MU:2025-10-01_to_2025-10-31"
    inputs = runner_setup_service.RunnerSetupInputs(
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
    deps = runner_setup_service.RunnerSetupDeps(
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

    monkeypatch.setattr(
        runner_setup_service,
        "_load_chunk_payload",
        lambda **kwargs: (
            [{"timestamp": "2025-10-06T14:00:00+00:00"}],
            {"2025-10-06T14:00:00+00:00": {"close": 1.0}},
        ),
    )

    asyncio.run(
        runner_setup_service._append_remaining_chunks(
            runner=runner,
            inputs=inputs,
            deps=deps,
            pending_chunks=[("2025-10-05", "2025-10-08")],
        )
    )

    assert runner._progressive_loading_complete is True
    assert runner._progressive_loading_loaded_until == "2025-10-31"
    assert runner._progressive_loading_pending_chunks == 0
    assert len(runner.bars) == 1
