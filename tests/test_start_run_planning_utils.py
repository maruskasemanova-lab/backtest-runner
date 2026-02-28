from __future__ import annotations

from src.services import start_run_planning_utils as utils


def test_inclusive_day_span_counts_inclusive_days() -> None:
    assert utils.inclusive_day_span("2026-02-01", "2026-02-01") == 1
    assert utils.inclusive_day_span("2026-02-01", "2026-02-03") == 3


def test_run_l2_guard_reason_respects_limit() -> None:
    reason = utils.run_l2_guard_reason(
        requested_l2_only=True,
        requested_l2_confirm=False,
        range_start="2026-02-01",
        range_end="2026-02-10",
        run_l2_force=False,
        run_l2_max_days=5,
    )
    assert isinstance(reason, str)
    assert "BACKTEST_RUN_L2_MAX_DAYS=5" in reason

    no_reason = utils.run_l2_guard_reason(
        requested_l2_only=True,
        requested_l2_confirm=False,
        range_start="2026-02-01",
        range_end="2026-02-03",
        run_l2_force=False,
        run_l2_max_days=5,
    )
    assert no_reason is None


def test_prewarm_l2_guard_reason_uses_scope_specific_limits() -> None:
    ticker_scope_reason = utils.prewarm_l2_guard_reason(
        prewarm_scope="ticker",
        requested_l2_only=False,
        requested_l2_confirm=True,
        range_start="2026-02-01",
        range_end="2026-02-10",
        prewarm_ticker_scope_l2_force=False,
        prewarm_ticker_scope_l2_max_days=3,
        run_l2_force=False,
        run_l2_max_days=10,
    )
    assert isinstance(ticker_scope_reason, str)
    assert "BACKTEST_PREWARM_TICKER_SCOPE_L2_MAX_DAYS=3" in ticker_scope_reason

    range_scope_reason = utils.prewarm_l2_guard_reason(
        prewarm_scope="range",
        requested_l2_only=False,
        requested_l2_confirm=True,
        range_start="2026-02-01",
        range_end="2026-02-10",
        prewarm_ticker_scope_l2_force=False,
        prewarm_ticker_scope_l2_max_days=3,
        run_l2_force=False,
        run_l2_max_days=4,
    )
    assert isinstance(range_scope_reason, str)
    assert "BACKTEST_RUN_L2_MAX_DAYS=4" in range_scope_reason


def test_build_progressive_chunks_and_plan() -> None:
    chunks = utils.build_progressive_chunks(
        range_start="2026-02-01",
        range_end="2026-02-06",
        initial_days=2,
        chunk_days=2,
    )
    assert chunks == [("2026-02-03", "2026-02-04"), ("2026-02-05", "2026-02-06")]

    plan = utils.resolve_progressive_plan(
        range_start="2026-02-01",
        range_end="2026-02-06",
        comparable_mode=False,
        progressive_load_enabled=True,
        progressive_load_allow_comparable_mode=True,
        progressive_load_min_days=2,
        progressive_load_initial_days=2,
        progressive_load_chunk_days=2,
        progressive_load_comparable_initial_days=1,
        progressive_load_comparable_chunk_days=1,
    )
    assert isinstance(plan, dict)
    assert plan["initial_end"] == "2026-02-02"
    assert plan["chunks"] == chunks
