from typing import Any, Dict, Optional

from .history_rows import (
    aggregate_history_day_rows,
    compute_calendar_metrics,
)
from .history_models import HistoryAccumulator, HistoryQuery
from .history_profile_options import build_history_profile_options
from .history_sources import (
    build_run_filter_options,
    scan_active_runner_history,
    scan_persisted_run_history,
)
from .shared import RunReportsReadDeps, first_profile_token, utc_now_iso


def build_saved_run_history_response(
    *,
    deps: RunReportsReadDeps,
    ticker: str,
    limit: int,
    run_id: str,
    run_id_contains: str,
    unified_profile_id: str,
    adaptive_profile_id: str,
    include_multi_day: bool,
    include_zero_trade_runs: bool,
) -> Dict[str, Any]:
    query = HistoryQuery(
        safe_ticker=str(ticker or "").strip().upper(),
        run_id_exact_filter=str(run_id or "").strip().lower(),
        run_id_contains_filter=str(run_id_contains or "").strip().lower(),
        requested_profile_id=(
            first_profile_token(unified_profile_id, adaptive_profile_id) or ""
        ),
        include_multi_day=bool(include_multi_day),
        include_zero_trade_runs=bool(include_zero_trade_runs),
    )
    accumulator = HistoryAccumulator()

    scan_active_runner_history(
        deps=deps,
        query=query,
        accumulator=accumulator,
        limit=limit,
    )
    scan_persisted_run_history(
        deps=deps,
        query=query,
        accumulator=accumulator,
        limit=limit,
    )

    day_results = aggregate_history_day_rows(accumulator.day_rows)
    split: Dict[str, Optional[str]]
    if day_results:
        split = {
            "start": day_results[0]["date"],
            "end": day_results[-1]["date"],
        }
    else:
        split = {"start": None, "end": None}

    run_options = build_run_filter_options(accumulator.run_latest_saved_at)
    profile_options = build_history_profile_options(
        project_root=deps.project_root,
        ticker=query.safe_ticker,
        history_profile_names=accumulator.history_profile_names,
    )

    return {
        "source": "saved_run_history",
        "source_mode": deps.source_mode,
        "source_path_hint": "run_reports_store",
        "ticker": query.safe_ticker,
        "generated_at": utc_now_iso(),
        "filters": {
            "limit": limit,
            "run_id": query.run_id_exact_filter or None,
            "run_id_contains": query.run_id_contains_filter or None,
            "unified_profile_id": query.requested_profile_id or None,
            "adaptive_profile_id": query.requested_profile_id or None,
            "include_multi_day": query.include_multi_day,
            "include_zero_trade_runs": query.include_zero_trade_runs,
        },
        "filter_options": {
            "run_ids": run_options,
            "unified_profiles": profile_options["unified_profiles"],
            "adaptive_profiles": profile_options["adaptive_profiles"],
        },
        "scanned_reports": accumulator.scanned_reports,
        "matched_reports": accumulator.matched_reports,
        "skipped_invalid_reports": accumulator.skipped_invalid,
        "split": split,
        "metrics": compute_calendar_metrics(day_results),
        "day_results": day_results,
    }
