from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from .history_models import HistoryAccumulator, HistoryQuery
from .history_rows import build_history_day_rows, report_has_closed_trades
from .shared import (
    RunReportsReadDeps,
    active_report_dir_name,
    external_report_dir_name,
    extract_profile_metadata,
    history_identity_key,
    hydrate_summary_with_persisted_config_snapshot,
    is_supported_persisted_run_summary,
    match_profile_filter,
    normalize_iso_timestamp,
    parse_report_saved_at,
    utc_now_iso,
)


def process_history_payload(
    *,
    accumulator: HistoryAccumulator,
    query: HistoryQuery,
    payload: Dict[str, Any],
    report_dir_name: str,
    report_saved_at: Optional[str],
    run_key: Optional[str],
) -> None:
    run_id_value = str(payload.get("run_id") or "").strip()
    if not run_id_value:
        return
    has_closed_trades = report_has_closed_trades(payload)
    if not has_closed_trades and not query.include_zero_trade_runs:
        return

    payload_ticker = str(payload.get("ticker") or "").strip().upper()
    if payload_ticker != query.safe_ticker:
        return
    normalized_saved_at = normalize_iso_timestamp(
        report_saved_at
    ) or parse_report_saved_at(report_dir_name)
    accumulator.remember_run_saved_at(
        run_id=run_id_value,
        normalized_saved_at=normalized_saved_at,
    )

    profile_meta = extract_profile_metadata(payload)
    history_profile_id = (
        str(profile_meta.get("unified_profile_id") or "").strip()
        or str(profile_meta.get("adaptive_profile_id") or "").strip()
    )
    history_profile_name = (
        str(profile_meta.get("unified_profile_name") or "").strip()
        or str(profile_meta.get("adaptive_profile_name") or "").strip()
    )
    accumulator.remember_profile_name(
        profile_id=history_profile_id,
        profile_name=history_profile_name,
    )

    if query.run_id_exact_filter and run_id_value.lower() != query.run_id_exact_filter:
        return
    if query.run_id_contains_filter and query.run_id_contains_filter not in run_id_value.lower():
        return

    profile_match_mode = match_profile_filter(
        run_id=run_id_value,
        unified_profile_id=profile_meta.get("unified_profile_id"),
        adaptive_profile_id=profile_meta.get("adaptive_profile_id"),
        strategy_combo_profile_id=profile_meta.get("strategy_combo_profile_id"),
        requested_profile_id=query.requested_profile_id,
    )
    if query.requested_profile_id and profile_match_mode is None:
        return

    run_day_rows = build_history_day_rows(
        payload,
        report_dir_name=report_dir_name,
        report_saved_at=normalized_saved_at,
        run_key=run_key,
        include_multi_day=query.include_multi_day,
        profile_match_mode=profile_match_mode,
    )
    if not run_day_rows:
        return
    identity_key = history_identity_key(payload)
    if identity_key and accumulator.already_seen_identity(identity_key):
        return
    accumulator.note_matched_rows(run_day_rows)


def scan_active_runner_history(
    *,
    deps: RunReportsReadDeps,
    query: HistoryQuery,
    accumulator: HistoryAccumulator,
    limit: int,
) -> None:
    active_runner_items = sorted(
        deps.active_runners.items(),
        key=lambda item: str(item[0] or ""),
        reverse=True,
    )
    active_seen_at = utc_now_iso()
    for run_key, runner in active_runner_items:
        if accumulator.matched_reports >= limit:
            break
        get_summary = getattr(runner, "get_summary", None)
        if not callable(get_summary):
            accumulator.note_invalid_report()
            continue
        accumulator.note_scanned_report()
        try:
            payload = get_summary()
        except Exception:
            accumulator.skipped_invalid += 1
            continue
        if not isinstance(payload, dict):
            accumulator.skipped_invalid += 1
            continue
        process_history_payload(
            accumulator=accumulator,
            query=query,
            payload=payload,
            report_dir_name=active_report_dir_name(run_key=str(run_key or "")),
            report_saved_at=active_seen_at,
            run_key=str(run_key or ""),
        )


def scan_persisted_run_history(
    *,
    deps: RunReportsReadDeps,
    query: HistoryQuery,
    accumulator: HistoryAccumulator,
    limit: int,
) -> None:
    external_store = deps.report_store
    list_run_summaries = getattr(external_store, "list_run_summaries", None)
    if not callable(list_run_summaries):
        return

    try:
        rows = list_run_summaries(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read run reports store history: {exc}",
        ) from exc

    if not isinstance(rows, list):
        rows = []

    for index, row in enumerate(rows, start=1):
        if accumulator.matched_reports >= limit:
            break
        accumulator.note_scanned_report()
        if not isinstance(row, dict):
            accumulator.skipped_invalid += 1
            continue
        payload = row.get("summary")
        if not isinstance(payload, dict):
            accumulator.skipped_invalid += 1
            continue
        payload = hydrate_summary_with_persisted_config_snapshot(
            summary_payload=payload,
            run_key=str(row.get("run_key") or ""),
            report_store=external_store,
        )
        if not is_supported_persisted_run_summary(payload):
            accumulator.skipped_invalid += 1
            continue
        report_saved_at = normalize_iso_timestamp(row.get("updated_at"))
        report_dir_name = external_report_dir_name(
            run_key=str(row.get("run_key") or ""),
            updated_at=report_saved_at,
            fallback_index=index,
        )
        process_history_payload(
            accumulator=accumulator,
            query=query,
            payload=payload,
            report_dir_name=report_dir_name,
            report_saved_at=report_saved_at,
            run_key=str(row.get("run_key") or ""),
        )


def build_run_filter_options(
    run_latest_saved_at: Dict[str, Optional[str]],
) -> List[Dict[str, Optional[str]]]:
    run_options = [
        {"run_id": run_id, "latest_saved_at": run_latest_saved_at.get(run_id)}
        for run_id in run_latest_saved_at.keys()
    ]
    run_options.sort(
        key=lambda item: (
            str(item.get("latest_saved_at") or ""),
            str(item.get("run_id") or ""),
        ),
        reverse=True,
    )
    return run_options
