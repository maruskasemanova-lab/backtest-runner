from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional


def inclusive_day_span(start_iso: str, end_iso: str) -> int:
    try:
        start_dt = datetime.strptime(str(start_iso), "%Y-%m-%d")
        end_dt = datetime.strptime(str(end_iso), "%Y-%m-%d")
    except Exception:
        return 0
    delta_days = (end_dt - start_dt).days
    return max(0, delta_days + 1)


def run_l2_guard_reason(
    *,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    range_start: str,
    range_end: str,
    run_l2_force: bool,
    run_l2_max_days: int,
) -> Optional[str]:
    if not bool(requested_l2_only or requested_l2_confirm):
        return None
    day_span = inclusive_day_span(range_start, range_end)
    if run_l2_force or run_l2_max_days <= 0 or day_span <= run_l2_max_days:
        return None
    return (
        "L2 request rejected: requested range "
        f"{range_start}..{range_end} covers {day_span} day(s), which exceeds "
        f"BACKTEST_RUN_L2_MAX_DAYS={run_l2_max_days}. "
        "Set BACKTEST_RUN_L2_FORCE=1 or increase BACKTEST_RUN_L2_MAX_DAYS "
        "to allow full-range L2."
    )


def prewarm_l2_guard_reason(
    *,
    prewarm_scope: str,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    range_start: str,
    range_end: str,
    prewarm_ticker_scope_l2_force: bool,
    prewarm_ticker_scope_l2_max_days: int,
    run_l2_force: bool,
    run_l2_max_days: int,
) -> Optional[str]:
    if not bool(requested_l2_only or requested_l2_confirm):
        return None
    day_span = inclusive_day_span(range_start, range_end)
    scope = str(prewarm_scope or "range").strip().lower()
    if scope == "ticker":
        if (
            prewarm_ticker_scope_l2_force
            or prewarm_ticker_scope_l2_max_days <= 0
            or day_span <= prewarm_ticker_scope_l2_max_days
        ):
            return None
        return (
            "L2 prewarm rejected for ticker scope: requested range "
            f"{range_start}..{range_end} covers {day_span} day(s), which exceeds "
            "BACKTEST_PREWARM_TICKER_SCOPE_L2_MAX_DAYS="
            f"{prewarm_ticker_scope_l2_max_days}. "
            "Set BACKTEST_PREWARM_TICKER_SCOPE_L2_FORCE=1 or increase "
            "BACKTEST_PREWARM_TICKER_SCOPE_L2_MAX_DAYS to allow full-range L2 prewarm."
        )
    if run_l2_force or run_l2_max_days <= 0 or day_span <= run_l2_max_days:
        return None
    return (
        "L2 prewarm rejected for range scope: requested range "
        f"{range_start}..{range_end} covers {day_span} day(s), which exceeds "
        f"BACKTEST_RUN_L2_MAX_DAYS={run_l2_max_days}. "
        "Set BACKTEST_RUN_L2_FORCE=1 or increase BACKTEST_RUN_L2_MAX_DAYS "
        "to allow full-range L2 prewarm."
    )


def parse_iso_day(value: Any) -> Optional[datetime]:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except Exception:
        return None


def format_iso_day(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def add_days_iso(value: str, days: int) -> Optional[str]:
    base = parse_iso_day(value)
    if base is None:
        return None
    return format_iso_day(base + timedelta(days=int(days)))


def build_progressive_chunks(
    *,
    range_start: str,
    range_end: str,
    initial_days: int,
    chunk_days: int,
) -> list[tuple[str, str]]:
    start_dt = parse_iso_day(range_start)
    end_dt = parse_iso_day(range_end)
    if start_dt is None or end_dt is None or start_dt > end_dt:
        return []

    initial_span = max(1, int(initial_days))
    chunk_span = max(1, int(chunk_days))
    initial_end_dt = min(end_dt, start_dt + timedelta(days=initial_span - 1))
    next_start_dt = initial_end_dt + timedelta(days=1)

    chunks: list[tuple[str, str]] = []
    while next_start_dt <= end_dt:
        chunk_end_dt = min(end_dt, next_start_dt + timedelta(days=chunk_span - 1))
        chunks.append((format_iso_day(next_start_dt), format_iso_day(chunk_end_dt)))
        next_start_dt = chunk_end_dt + timedelta(days=1)
    return chunks


def resolve_progressive_plan(
    *,
    range_start: str,
    range_end: str,
    comparable_mode: bool,
    progressive_load_enabled: bool,
    progressive_load_allow_comparable_mode: bool,
    progressive_load_min_days: int,
    progressive_load_initial_days: int,
    progressive_load_chunk_days: int,
    progressive_load_comparable_initial_days: int,
    progressive_load_comparable_chunk_days: int,
) -> Optional[Dict[str, Any]]:
    if not progressive_load_enabled:
        return None
    if comparable_mode and not progressive_load_allow_comparable_mode:
        return None

    day_span = inclusive_day_span(range_start, range_end)
    min_days = max(1, int(progressive_load_min_days))
    if day_span <= min_days:
        return None

    if comparable_mode:
        initial_days = max(1, int(progressive_load_comparable_initial_days))
        chunk_days = max(1, int(progressive_load_comparable_chunk_days))
    else:
        initial_days = max(1, int(progressive_load_initial_days))
        chunk_days = max(1, int(progressive_load_chunk_days))

    initial_end = add_days_iso(range_start, initial_days - 1) or range_end
    if initial_end > range_end:
        initial_end = range_end

    chunks = build_progressive_chunks(
        range_start=range_start,
        range_end=range_end,
        initial_days=initial_days,
        chunk_days=chunk_days,
    )
    if not chunks:
        return None

    return {
        "initial_start": range_start,
        "initial_end": initial_end,
        "target_end": range_end,
        "chunks": chunks,
        "day_span": day_span,
        "initial_days": initial_days,
        "chunk_days": chunk_days,
    }
