from typing import Any, Dict, Optional

from fastapi import HTTPException

from .shared import (
    RunReportsReadDeps,
    decode_playback_snapshot,
    has_modern_resolved_config_snapshot,
    hydrate_summary_with_persisted_config_snapshot,
    normalize_iso_date,
    redact_playback_payload,
    resolve_config_payload_dict,
    safe_optional_int,
    split_run_key,
)


def _load_summary_row(*, run_key: str, deps: RunReportsReadDeps) -> Optional[Dict[str, Any]]:
    report_store = deps.report_store
    summary_row: Optional[Dict[str, Any]] = None
    get_run_summary = getattr(report_store, "get_run_summary", None)
    if callable(get_run_summary):
        try:
            row = get_run_summary(run_key=run_key)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read run snapshot from report store: {exc}",
            ) from exc
        if isinstance(row, dict):
            summary_row = row
    else:
        list_run_summaries = getattr(report_store, "list_run_summaries", None)
        if callable(list_run_summaries):
            try:
                rows = list_run_summaries(limit=5000)
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to scan run snapshot from report store: {exc}",
                ) from exc
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("run_key") or "").strip() != run_key:
                        continue
                    summary_row = row
                    break
    return summary_row


def build_run_playback_snapshot_response(
    *,
    deps: RunReportsReadDeps,
    run_key: str,
) -> Dict[str, Any]:
    run_id, run_ticker, run_date_label = split_run_key(run_key)

    active_runner = deps.active_runners.get(run_key)
    if active_runner is not None:
        get_state = getattr(active_runner, "get_state", None)
        get_summary = getattr(active_runner, "get_summary", None)
        get_processed_bars = getattr(active_runner, "get_processed_bars", None)
        get_markers = getattr(active_runner, "get_markers", None)

        state_payload = get_state() if callable(get_state) else {}
        summary_payload = get_summary() if callable(get_summary) else {}
        bars_payload = get_processed_bars() if callable(get_processed_bars) else []
        markers_payload = get_markers() if callable(get_markers) else []

        if not isinstance(state_payload, dict):
            state_payload = {}
        if not isinstance(summary_payload, dict):
            summary_payload = {}
        if not isinstance(bars_payload, list):
            bars_payload = []
        if not isinstance(markers_payload, list):
            markers_payload = []

        summary_for_client = redact_playback_payload(summary_payload)
        return {
            "run_key": run_key,
            "source": "active_runner",
            "state": state_payload,
            "bars": bars_payload,
            "markers": markers_payload,
            "summary": summary_for_client,
            "snapshot_meta": summary_for_client.get("playback_snapshot", {}),
        }

    summary_row = _load_summary_row(run_key=run_key, deps=deps)
    if not isinstance(summary_row, dict):
        raise HTTPException(
            status_code=404,
            detail=f"Run snapshot not found for run_key={run_key}",
        )

    summary_payload = (
        summary_row.get("summary", {})
        if isinstance(summary_row.get("summary"), dict)
        else {}
    )
    summary_payload = hydrate_summary_with_persisted_config_snapshot(
        summary_payload=summary_payload,
        run_key=run_key,
        report_store=deps.report_store,
    )
    if not has_modern_resolved_config_snapshot(summary_payload):
        raise HTTPException(
            status_code=404,
            detail=(
                "Legacy run artifacts are no longer supported. "
                "Start a new run to persist modern playback and config snapshots."
            ),
        )
    decoded_snapshot = decode_playback_snapshot(summary_payload)
    bars_payload = (
        decoded_snapshot.get("bars", [])
        if isinstance(decoded_snapshot, dict)
        and isinstance(decoded_snapshot.get("bars"), list)
        else []
    )
    markers_payload = (
        decoded_snapshot.get("markers", [])
        if isinstance(decoded_snapshot, dict)
        and isinstance(decoded_snapshot.get("markers"), list)
        else (
            summary_payload.get("markers", [])
            if isinstance(summary_payload.get("markers"), list)
            else []
        )
    )
    if not bars_payload:
        raise HTTPException(
            status_code=404,
            detail=(
                "Playback snapshot is not available for this run. "
                "Run it again once with snapshot persistence enabled."
            ),
        )

    total_bars = safe_optional_int(summary_payload.get("total_bars"))
    if total_bars is None:
        total_bars = len(bars_payload)
    processed_bars = safe_optional_int(summary_payload.get("processed_bars"))
    if processed_bars is None:
        processed_bars = len(bars_payload)
    total_bars = max(0, int(total_bars))
    processed_bars = max(0, min(int(processed_bars), total_bars or len(bars_payload)))
    progress_pct = (
        (float(processed_bars) / float(total_bars)) * 100.0 if total_bars > 0 else 0.0
    )

    request_config = resolve_config_payload_dict(
        summary_payload,
        key="run_request_config",
    )
    date_from = normalize_iso_date(request_config.get("date_from"))
    date_to = normalize_iso_date(request_config.get("date_to"))
    state_payload: Dict[str, Any] = {
        "run_id": run_id or str(summary_payload.get("run_id") or "").strip(),
        "ticker": (run_ticker or str(summary_payload.get("ticker") or "").strip()).upper(),
        "date": run_date_label or str(summary_payload.get("date") or "").strip(),
        "date_from": date_from,
        "date_to": date_to,
        "current_bar_index": processed_bars,
        "total_bars": total_bars,
        "progress_pct": progress_pct,
        "phase": str(summary_payload.get("phase") or "COMPLETED"),
        "is_running": False,
        "is_paused": False,
        "markers_count": len(markers_payload),
        "is_snapshot": True,
        "snapshot_source_mode": deps.source_mode,
        "report_saved_at": summary_row.get("updated_at"),
    }

    summary_for_client = redact_playback_payload(summary_payload)
    return {
        "run_key": run_key,
        "source": "run_reports_store",
        "source_mode": deps.source_mode,
        "state": state_payload,
        "bars": bars_payload,
        "markers": markers_payload,
        "summary": summary_for_client,
        "snapshot_meta": summary_for_client.get("playback_snapshot", {}),
        "report_saved_at": summary_row.get("updated_at"),
    }
