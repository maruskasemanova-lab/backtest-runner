import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException

from .history_rows import (
    aggregate_history_day_rows,
    build_history_day_rows,
    compute_calendar_metrics,
    report_has_closed_trades,
)
from .shared import (
    RunReportsReadDeps,
    active_report_dir_name,
    external_report_dir_name,
    extract_profile_metadata,
    first_profile_token,
    history_identity_key,
    hydrate_summary_with_persisted_config_snapshot,
    is_supported_persisted_run_summary,
    match_profile_filter,
    normalize_iso_timestamp,
    parse_report_saved_at,
    utc_now_iso,
)


def _load_profile_options_from_aos_config(
    *,
    project_root: Path,
    ticker: str,
    profiles_key: str,
    active_profile_key: str,
    source: str,
) -> List[Dict[str, Any]]:
    config_path = project_root / "aos_optimization" / "aos_config.json"
    if not config_path.exists() or not config_path.is_file():
        return []
    try:
        raw = config_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []

    tickers_payload = (
        payload.get("tickers", {}) if isinstance(payload.get("tickers"), dict) else {}
    )
    ticker_payload = (
        tickers_payload.get(ticker, {})
        if isinstance(tickers_payload.get(ticker), dict)
        else {}
    )
    active_profile_id = (
        str(ticker_payload.get(active_profile_key) or "").strip() or None
    )
    profiles = ticker_payload.get(profiles_key, [])
    if not isinstance(profiles, list):
        profiles = []

    collected: Dict[str, Dict[str, Any]] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("profile_id") or "").strip()
        if not profile_id:
            continue
        profile_name = (
            str(profile.get("profile_name") or "").strip()
            or str(profile.get("name") or "").strip()
            or None
        )
        created_at = normalize_iso_timestamp(profile.get("created_at"))
        existing = collected.get(profile_id)
        if existing is None:
            collected[profile_id] = {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "active": bool(active_profile_id and active_profile_id == profile_id),
                "latest_created_at": created_at,
                "source": source,
            }
            continue
        if not existing.get("profile_name") and profile_name:
            existing["profile_name"] = profile_name
        existing["active"] = bool(existing.get("active")) or bool(
            active_profile_id and active_profile_id == profile_id
        )
        existing_created_at = str(existing.get("latest_created_at") or "")
        if created_at and created_at > existing_created_at:
            existing["latest_created_at"] = created_at

    if active_profile_id and active_profile_id not in collected:
        collected[active_profile_id] = {
            "profile_id": active_profile_id,
            "profile_name": None,
            "active": True,
            "latest_created_at": None,
            "source": source,
        }

    options = list(collected.values())
    options.sort(key=lambda item: str(item.get("profile_id") or ""))
    options.sort(
        key=lambda item: str(item.get("latest_created_at") or ""), reverse=True
    )
    options.sort(key=lambda item: 0 if bool(item.get("active")) else 1)
    return options


def _merge_profile_options(
    history_options: List[Dict[str, Any]],
    aos_options: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for option in history_options + aos_options:
        if not isinstance(option, dict):
            continue
        profile_id = str(option.get("profile_id") or "").strip()
        if not profile_id:
            continue
        profile_name = str(option.get("profile_name") or "").strip() or None
        source = str(option.get("source") or "").strip() or "history"
        active = bool(option.get("active"))
        latest_created_at = str(option.get("latest_created_at") or "").strip() or None

        existing = merged.get(profile_id)
        if existing is None:
            merged[profile_id] = {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "active": active,
                "latest_created_at": latest_created_at,
                "sources": {source},
            }
            continue

        if not existing.get("profile_name") and profile_name:
            existing["profile_name"] = profile_name
        existing["active"] = bool(existing.get("active")) or active
        current_created = str(existing.get("latest_created_at") or "")
        if latest_created_at and latest_created_at > current_created:
            existing["latest_created_at"] = latest_created_at
        existing_sources = existing.get("sources")
        if isinstance(existing_sources, set):
            existing_sources.add(source)
        else:
            existing["sources"] = {source}

    options = []
    for item in merged.values():
        sources = (
            sorted(item.get("sources", set()))
            if isinstance(item.get("sources"), set)
            else []
        )
        options.append(
            {
                "profile_id": item.get("profile_id"),
                "profile_name": item.get("profile_name"),
                "active": bool(item.get("active")),
                "latest_created_at": item.get("latest_created_at"),
                "source": ",".join(sources) if sources else None,
            }
        )
    options.sort(key=lambda item: str(item.get("profile_id") or ""))
    options.sort(
        key=lambda item: str(item.get("latest_created_at") or ""), reverse=True
    )
    options.sort(key=lambda item: 0 if bool(item.get("active")) else 1)
    return options


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
    safe_ticker = str(ticker or "").strip().upper()
    run_id_exact_filter = str(run_id or "").strip().lower()
    run_id_filter = str(run_id_contains or "").strip().lower()
    requested_profile_id = (
        first_profile_token(unified_profile_id, adaptive_profile_id) or ""
    )

    day_rows: List[Dict[str, Any]] = []
    matched_reports = 0
    scanned_reports = 0
    skipped_invalid = 0
    run_latest_saved_at: Dict[str, Optional[str]] = {}
    history_profile_names: Dict[str, Set[str]] = {}
    seen_run_identity_keys: Set[str] = set()

    def process_history_payload(
        *,
        payload: Dict[str, Any],
        report_dir_name: str,
        report_saved_at: Optional[str],
        run_key: Optional[str],
    ) -> None:
        nonlocal matched_reports
        run_id_value = str(payload.get("run_id") or "").strip()
        if not run_id_value:
            return
        has_closed_trades = report_has_closed_trades(payload)
        if not has_closed_trades and not include_zero_trade_runs:
            return

        payload_ticker = str(payload.get("ticker") or "").strip().upper()
        if payload_ticker != safe_ticker:
            return
        normalized_saved_at = normalize_iso_timestamp(
            report_saved_at
        ) or parse_report_saved_at(report_dir_name)
        current_latest = str(run_latest_saved_at.get(run_id_value) or "")
        if normalized_saved_at and normalized_saved_at > current_latest:
            run_latest_saved_at[run_id_value] = normalized_saved_at
        elif run_id_value not in run_latest_saved_at:
            run_latest_saved_at[run_id_value] = normalized_saved_at

        profile_meta = extract_profile_metadata(payload)
        history_profile_id = (
            str(profile_meta.get("unified_profile_id") or "").strip()
            or str(profile_meta.get("adaptive_profile_id") or "").strip()
        )
        history_profile_name = (
            str(profile_meta.get("unified_profile_name") or "").strip()
            or str(profile_meta.get("adaptive_profile_name") or "").strip()
        )
        if history_profile_id:
            history_profile_names.setdefault(history_profile_id, set())
            if history_profile_name:
                history_profile_names[history_profile_id].add(history_profile_name)

        if run_id_exact_filter and run_id_value.lower() != run_id_exact_filter:
            return
        if run_id_filter and run_id_filter not in run_id_value.lower():
            return

        profile_match_mode = match_profile_filter(
            run_id=run_id_value,
            unified_profile_id=profile_meta.get("unified_profile_id"),
            adaptive_profile_id=profile_meta.get("adaptive_profile_id"),
            strategy_combo_profile_id=profile_meta.get("strategy_combo_profile_id"),
            requested_profile_id=requested_profile_id,
        )
        if requested_profile_id and profile_match_mode is None:
            return

        run_day_rows = build_history_day_rows(
            payload,
            report_dir_name=report_dir_name,
            report_saved_at=normalized_saved_at,
            run_key=run_key,
            include_multi_day=include_multi_day,
            profile_match_mode=profile_match_mode,
        )
        if not run_day_rows:
            return
        identity_key = history_identity_key(payload)
        if identity_key:
            if identity_key in seen_run_identity_keys:
                return
            seen_run_identity_keys.add(identity_key)
        day_rows.extend(run_day_rows)
        matched_reports += 1

    active_runner_items = sorted(
        deps.active_runners.items(),
        key=lambda item: str(item[0] or ""),
        reverse=True,
    )
    active_seen_at = utc_now_iso()
    for run_key, runner in active_runner_items:
        if matched_reports >= limit:
            break
        scanned_reports += 1
        get_summary = getattr(runner, "get_summary", None)
        if not callable(get_summary):
            skipped_invalid += 1
            continue
        try:
            payload = get_summary()
        except Exception:
            skipped_invalid += 1
            continue
        if not isinstance(payload, dict):
            skipped_invalid += 1
            continue
        process_history_payload(
            payload=payload,
            report_dir_name=active_report_dir_name(run_key=str(run_key or "")),
            report_saved_at=active_seen_at,
            run_key=str(run_key or ""),
        )

    source_mode = deps.source_mode
    source_path_hint = "run_reports_store"
    external_store = deps.report_store
    list_run_summaries = getattr(external_store, "list_run_summaries", None)

    if callable(list_run_summaries):
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
            if matched_reports >= limit:
                break
            scanned_reports += 1
            if not isinstance(row, dict):
                skipped_invalid += 1
                continue
            payload = row.get("summary")
            if not isinstance(payload, dict):
                skipped_invalid += 1
                continue
            payload = hydrate_summary_with_persisted_config_snapshot(
                summary_payload=payload,
                run_key=str(row.get("run_key") or ""),
                report_store=external_store,
            )
            if not is_supported_persisted_run_summary(payload):
                skipped_invalid += 1
                continue
            report_saved_at = normalize_iso_timestamp(row.get("updated_at"))
            report_dir_name = external_report_dir_name(
                run_key=str(row.get("run_key") or ""),
                updated_at=report_saved_at,
                fallback_index=index,
            )
            process_history_payload(
                payload=payload,
                report_dir_name=report_dir_name,
                report_saved_at=report_saved_at,
                run_key=str(row.get("run_key") or ""),
            )

    day_results = aggregate_history_day_rows(day_rows)
    split: Dict[str, Optional[str]]
    if day_results:
        split = {
            "start": day_results[0]["date"],
            "end": day_results[-1]["date"],
        }
    else:
        split = {"start": None, "end": None}

    history_profile_options = [
        {
            "profile_id": profile_id,
            "profile_name": sorted(names)[0] if names else None,
            "active": False,
            "latest_created_at": None,
            "source": "history",
        }
        for profile_id, names in history_profile_names.items()
    ]
    history_profile_options.sort(key=lambda item: str(item.get("profile_id") or ""))

    run_options = [
        {"run_id": current_run_id, "latest_saved_at": run_latest_saved_at.get(current_run_id)}
        for current_run_id in run_latest_saved_at.keys()
    ]
    run_options.sort(
        key=lambda item: (
            str(item.get("latest_saved_at") or ""),
            str(item.get("run_id") or ""),
        ),
        reverse=True,
    )

    adaptive_profile_options = _merge_profile_options(
        history_profile_options,
        _load_profile_options_from_aos_config(
            project_root=deps.project_root,
            ticker=safe_ticker,
            profiles_key="adaptive_tuner_profiles",
            active_profile_key="active_adaptive_tuner_profile_id",
            source="aos_config",
        ),
    )
    unified_profile_options = _merge_profile_options(
        history_profile_options,
        _load_profile_options_from_aos_config(
            project_root=deps.project_root,
            ticker=safe_ticker,
            profiles_key="unified_profiles",
            active_profile_key="active_unified_profile_id",
            source="aos_unified",
        ),
    )

    return {
        "source": "saved_run_history",
        "source_mode": source_mode,
        "source_path_hint": source_path_hint,
        "ticker": safe_ticker,
        "generated_at": utc_now_iso(),
        "filters": {
            "limit": limit,
            "run_id": run_id_exact_filter or None,
            "run_id_contains": run_id_filter or None,
            "unified_profile_id": requested_profile_id or None,
            "adaptive_profile_id": requested_profile_id or None,
            "include_multi_day": bool(include_multi_day),
            "include_zero_trade_runs": bool(include_zero_trade_runs),
        },
        "filter_options": {
            "run_ids": run_options,
            "unified_profiles": unified_profile_options,
            "adaptive_profiles": adaptive_profile_options,
        },
        "scanned_reports": scanned_reports,
        "matched_reports": matched_reports,
        "skipped_invalid_reports": skipped_invalid,
        "split": split,
        "metrics": compute_calendar_metrics(day_results),
        "day_results": day_results,
    }
