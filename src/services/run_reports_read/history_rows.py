from typing import Any, Dict, List, Optional, Set

from .shared import (
    day_from_timestamp,
    expand_day_range,
    extract_profile_metadata,
    history_identity_key,
    normalize_iso_timestamp,
    parse_range_label,
    parse_report_saved_at,
    parse_run_day_from_label,
    resolve_config_payload_dict,
    resolved_config_snapshot,
    safe_float,
    safe_int,
    safe_optional_float,
    safe_optional_int,
    timestamp_lookup_keys,
)


def collect_strategy_names_from_trades(trades: Any) -> List[str]:
    if not isinstance(trades, list):
        return []
    names = []
    for item in trades:
        if not isinstance(item, dict):
            continue
        strategy = str(item.get("strategy") or "").strip()
        if strategy:
            names.append(strategy)
    return sorted(set(names))


def extract_entry_reason(marker: Dict[str, Any]) -> Optional[str]:
    details = (
        marker.get("details", {}) if isinstance(marker.get("details"), dict) else {}
    )
    reasoning = str(details.get("reasoning") or "").strip()
    if reasoning:
        return reasoning

    description = str(marker.get("description") or "").strip()
    if not description:
        return None
    marker_token = "Reason:"
    idx = description.find(marker_token)
    if idx < 0:
        return None
    reason = description[idx + len(marker_token) :].strip()
    confidence_token = "| Confidence:"
    confidence_idx = reason.find(confidence_token)
    if confidence_idx >= 0:
        reason = reason[:confidence_idx].strip()
    return reason or None


def extract_exit_reason(marker: Dict[str, Any]) -> Optional[str]:
    details = (
        marker.get("details", {}) if isinstance(marker.get("details"), dict) else {}
    )
    exit_reason = str(details.get("exit_reason") or "").strip()
    if exit_reason:
        return exit_reason
    title = str(marker.get("title") or "").strip()
    if title.lower().startswith("exit:"):
        value = title.split(":", 1)[1].strip()
        return value or None
    return None


def build_entry_reason_map(markers: Any) -> Dict[str, str]:
    if not isinstance(markers, list):
        return {}
    reasons: Dict[str, str] = {}
    for marker in markers:
        if not isinstance(marker, dict):
            continue
        if str(marker.get("marker_type") or "").strip() != "entry_executed":
            continue
        reason = extract_entry_reason(marker)
        if not reason:
            continue
        for key in timestamp_lookup_keys(marker.get("timestamp")):
            reasons[key] = reason
    return reasons


def build_exit_reason_map(markers: Any) -> Dict[str, str]:
    if not isinstance(markers, list):
        return {}
    reasons: Dict[str, str] = {}
    for marker in markers:
        if not isinstance(marker, dict):
            continue
        marker_type = str(marker.get("marker_type") or "").strip()
        if marker_type not in {
            "exit_executed",
            "stop_loss_hit",
            "take_profit_hit",
            "time_exit",
        }:
            continue
        reason = extract_exit_reason(marker)
        if not reason:
            continue
        for key in timestamp_lookup_keys(marker.get("timestamp")):
            reasons[key] = reason
    return reasons


def build_marker_strategy_names_by_day(markers: Any) -> Dict[str, List[str]]:
    if not isinstance(markers, list):
        return {}
    by_day: Dict[str, Set[str]] = {}
    for marker in markers:
        if not isinstance(marker, dict):
            continue
        day = day_from_timestamp(marker.get("timestamp"))
        if not day:
            continue
        strategy = str(marker.get("strategy") or "").strip()
        if not strategy:
            continue
        by_day.setdefault(day, set()).add(strategy)
    return {day: sorted(values) for day, values in by_day.items()}


def count_markers_by_day(markers: Any, *, marker_types: Set[str]) -> Dict[str, int]:
    if not isinstance(markers, list) or not marker_types:
        return {}
    counts: Dict[str, int] = {}
    normalized_types = {str(item).strip() for item in marker_types if str(item).strip()}
    if not normalized_types:
        return {}

    for marker in markers:
        if not isinstance(marker, dict):
            continue
        marker_type = str(marker.get("marker_type") or "").strip()
        if marker_type not in normalized_types:
            continue
        day = day_from_timestamp(marker.get("timestamp"))
        if not day:
            continue
        counts[day] = int(counts.get(day, 0)) + 1
    return counts


def resolve_profile_values(values: Set[str]) -> Optional[str]:
    if not values:
        return None
    if len(values) == 1:
        return sorted(values)[0]
    return None


def report_has_closed_trades(payload: Dict[str, Any]) -> bool:
    session_summary = payload.get("session_summary", {})
    if not isinstance(session_summary, dict):
        return False
    trades = session_summary.get("trades", [])
    if isinstance(trades, list) and len(trades) > 0:
        return True
    total_trades = safe_int(session_summary.get("total_trades"), 0)
    return total_trades > 0


def build_history_day_rows(
    payload: Dict[str, Any],
    *,
    report_dir_name: str,
    report_saved_at: Optional[str] = None,
    run_key: Optional[str] = None,
    include_multi_day: bool,
    profile_match_mode: Optional[str],
) -> List[Dict[str, Any]]:
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        return []
    ticker = str(payload.get("ticker") or "").strip().upper()
    date_label = str(payload.get("date") or "").strip()
    saved_at = normalize_iso_timestamp(report_saved_at) or parse_report_saved_at(
        report_dir_name
    )
    markers = (
        payload.get("markers", []) if isinstance(payload.get("markers"), list) else []
    )
    session_summary = payload.get("session_summary", {})
    if not isinstance(session_summary, dict):
        session_summary = {}
    trades = (
        session_summary.get("trades", [])
        if isinstance(session_summary.get("trades"), list)
        else []
    )
    execution_config = resolve_config_payload_dict(payload, key="execution_config")
    run_request_config = resolve_config_payload_dict(payload, key="run_request_config")
    if not run_request_config:
        report_metadata = (
            payload.get("report_metadata", {})
            if isinstance(payload.get("report_metadata"), dict)
            else {}
        )
        run_request_config = (
            report_metadata.get("run_request_config", {})
            if isinstance(report_metadata.get("run_request_config"), dict)
            else {}
        )
    aos_applied = resolve_config_payload_dict(payload, key="aos_applied")
    control_plane_snapshot = resolve_config_payload_dict(
        payload,
        key="control_plane_snapshot",
    )
    current_resolved_config_snapshot = resolved_config_snapshot(payload)
    resolved_config_snapshot_id = (
        str(payload.get("resolved_config_snapshot_id") or "").strip() or None
    )
    profile_meta = extract_profile_metadata(payload)
    entry_reasons = build_entry_reason_map(markers)
    exit_reasons = build_exit_reason_map(markers)
    marker_strategy_by_day = build_marker_strategy_names_by_day(markers)
    signal_markers_by_day = count_markers_by_day(markers, marker_types={"signal_generated"})
    regime_markers_by_day = count_markers_by_day(markers, marker_types={"regime_detected"})
    run_signals = sum(signal_markers_by_day.values())
    run_regime_evaluations = sum(regime_markers_by_day.values())
    run_processed_bars = safe_optional_int(payload.get("processed_bars"))
    if run_processed_bars is None:
        run_processed_bars = safe_optional_int(session_summary.get("bars_processed"))
    run_total_bars = safe_optional_int(payload.get("total_bars"))
    if run_total_bars is None:
        run_total_bars = safe_optional_int(session_summary.get("bars_processed"))
    run_total_trades = safe_optional_int(session_summary.get("total_trades"))
    if run_total_trades is None and trades:
        run_total_trades = len(trades)
    run_total_pnl_pct = safe_optional_float(session_summary.get("total_pnl_pct"))
    run_total_pnl_dollars = safe_optional_float(
        session_summary.get("total_pnl_dollars")
    )
    range_days: List[str] = []
    day_from_label = parse_run_day_from_label(date_label)
    if day_from_label:
        range_days = [day_from_label]
    elif include_multi_day:
        range_window = parse_range_label(date_label)
        if range_window:
            range_days = expand_day_range(range_window[0], range_window[1])

    grouped_trades: Dict[str, List[Dict[str, Any]]] = {}
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        entry_time = str(trade.get("entry_time") or "").strip() or None
        exit_time = str(trade.get("exit_time") or "").strip() or None
        trade_day = day_from_timestamp(exit_time) or day_from_timestamp(entry_time)
        if not trade_day:
            continue
        entry_reason = str(trade.get("entry_reason") or "").strip() or None
        if not entry_reason:
            for key in timestamp_lookup_keys(entry_time):
                if key in entry_reasons:
                    entry_reason = entry_reasons.get(key)
                    break
        exit_reason = str(trade.get("exit_reason") or "").strip() or None
        if not exit_reason:
            for key in timestamp_lookup_keys(exit_time):
                if key in exit_reasons:
                    exit_reason = exit_reasons.get(key)
                    break

        grouped_trades.setdefault(trade_day, []).append(
            {
                "trade_id": trade.get("trade_id"),
                "strategy": str(trade.get("strategy") or "").strip() or None,
                "side": str(trade.get("side") or "").strip() or None,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": safe_float(trade.get("entry_price"), 0.0),
                "exit_price": safe_float(trade.get("exit_price"), 0.0),
                "bars_held": safe_int(trade.get("bars_held"), 0),
                "pnl_pct": safe_float(trade.get("pnl_pct"), 0.0),
                "pnl_dollars": safe_float(trade.get("pnl_dollars"), 0.0),
                "entry_reason": entry_reason,
                "exit_reason": exit_reason,
                "run_id": run_id,
                "report_dir": report_dir_name,
            }
        )

    day_set: Set[str] = set(grouped_trades.keys())
    for day in range_days:
        day_set.add(day)

    rows: List[Dict[str, Any]] = []
    single_day_scope = bool(day_from_label) or len(range_days) == 1
    for day in sorted(day_set):
        day_trades = grouped_trades.get(day, [])
        day_strategy_names: Set[str] = set(
            name for name in collect_strategy_names_from_trades(day_trades) if name
        )
        for strategy_name in marker_strategy_by_day.get(day, []):
            if strategy_name:
                day_strategy_names.add(strategy_name)
        pnl_pct = sum(safe_float(item.get("pnl_pct"), 0.0) for item in day_trades)
        pnl_dollars = sum(
            safe_float(item.get("pnl_dollars"), 0.0) for item in day_trades
        )
        rows.append(
            {
                "date": day,
                "success": True,
                "ticker": ticker,
                "run_id": run_id,
                "run_key": str(run_key or "").strip() or history_identity_key(payload),
                "date_label": date_label,
                "report_dir": report_dir_name,
                "report_saved_at": saved_at,
                "profile_match_mode": profile_match_mode,
                "total_trades": len(day_trades),
                "pnl_pct": pnl_pct,
                "pnl_dollars": pnl_dollars,
                "signals": safe_int(signal_markers_by_day.get(day), 0),
                "regime_evaluations": safe_int(regime_markers_by_day.get(day), 0),
                "processed_bars": run_processed_bars if single_day_scope else None,
                "total_bars": run_total_bars if single_day_scope else None,
                "run_total_trades": run_total_trades,
                "run_total_pnl_pct": run_total_pnl_pct,
                "run_total_pnl_dollars": run_total_pnl_dollars,
                "run_signals": run_signals,
                "run_regime_evaluations": run_regime_evaluations,
                "run_processed_bars": run_processed_bars,
                "run_total_bars": run_total_bars,
                "trade_details": day_trades,
                "strategy_names": sorted(day_strategy_names),
                "execution_config": execution_config,
                "run_request_config": run_request_config,
                "aos_applied": aos_applied,
                "control_plane_snapshot": control_plane_snapshot,
                "resolved_config_snapshot": current_resolved_config_snapshot,
                "resolved_config_snapshot_id": resolved_config_snapshot_id,
                "unified_profile_id": profile_meta.get("unified_profile_id"),
                "unified_profile_name": profile_meta.get("unified_profile_name"),
                "adaptive_profile_id": profile_meta.get("adaptive_profile_id"),
                "adaptive_profile_name": profile_meta.get("adaptive_profile_name"),
                "strategy_combo_profile_id": profile_meta.get(
                    "strategy_combo_profile_id"
                ),
                "strategy_combo_profile_name": profile_meta.get(
                    "strategy_combo_profile_name"
                ),
                "config_fingerprint": profile_meta.get("config_fingerprint"),
            }
        )
    return rows


def aggregate_history_day_rows(day_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_day: Dict[str, Dict[str, Any]] = {}
    for row in day_rows:
        day = str(row.get("date") or "").strip()
        if not day:
            continue
        bucket = by_day.get(day)
        if bucket is None:
            bucket = {
                "date": day,
                "success": True,
                "total_trades": 0,
                "pnl_pct": 0.0,
                "pnl_dollars": 0.0,
                "signals": 0,
                "regime_evaluations": 0,
                "processed_bars": 0,
                "total_bars": 0,
                "processed_bars_known_runs": 0,
                "total_bars_known_runs": 0,
                "trade_details": [],
                "runs": [],
                "strategy_names": set(),
                "unified_profile_ids": set(),
                "unified_profile_names": set(),
                "adaptive_profile_ids": set(),
                "adaptive_profile_names": set(),
                "strategy_combo_profile_ids": set(),
                "strategy_combo_profile_names": set(),
                "profile_match_modes": set(),
                "config_fingerprints": set(),
            }
            by_day[day] = bucket

        bucket["total_trades"] += safe_int(row.get("total_trades"), 0)
        bucket["pnl_pct"] += safe_float(row.get("pnl_pct"), 0.0)
        bucket["pnl_dollars"] += safe_float(row.get("pnl_dollars"), 0.0)
        bucket["signals"] += safe_int(row.get("signals"), 0)
        bucket["regime_evaluations"] += safe_int(row.get("regime_evaluations"), 0)
        row_processed_bars = safe_optional_int(row.get("processed_bars"))
        row_total_bars = safe_optional_int(row.get("total_bars"))
        if row_processed_bars is not None:
            bucket["processed_bars"] += row_processed_bars
            bucket["processed_bars_known_runs"] += 1
        if row_total_bars is not None:
            bucket["total_bars"] += row_total_bars
            bucket["total_bars_known_runs"] += 1
        bucket["trade_details"].extend(
            item
            for item in (
                row.get("trade_details")
                if isinstance(row.get("trade_details"), list)
                else []
            )
            if isinstance(item, dict)
        )
        for name in row.get("strategy_names", []):
            token = str(name or "").strip()
            if token:
                bucket["strategy_names"].add(token)
        unified_profile_id = str(row.get("unified_profile_id") or "").strip()
        if unified_profile_id:
            bucket["unified_profile_ids"].add(unified_profile_id)
        unified_profile_name = str(row.get("unified_profile_name") or "").strip()
        if unified_profile_name:
            bucket["unified_profile_names"].add(unified_profile_name)
        adaptive_profile_id = str(row.get("adaptive_profile_id") or "").strip()
        if adaptive_profile_id:
            bucket["adaptive_profile_ids"].add(adaptive_profile_id)
        adaptive_profile_name = str(row.get("adaptive_profile_name") or "").strip()
        if adaptive_profile_name:
            bucket["adaptive_profile_names"].add(adaptive_profile_name)
        strategy_combo_profile_id = str(
            row.get("strategy_combo_profile_id") or ""
        ).strip()
        if strategy_combo_profile_id:
            bucket["strategy_combo_profile_ids"].add(strategy_combo_profile_id)
        strategy_combo_profile_name = str(
            row.get("strategy_combo_profile_name") or ""
        ).strip()
        if strategy_combo_profile_name:
            bucket["strategy_combo_profile_names"].add(strategy_combo_profile_name)
        profile_match_mode = str(row.get("profile_match_mode") or "").strip()
        if profile_match_mode:
            bucket["profile_match_modes"].add(profile_match_mode)
        config_fingerprint = str(row.get("config_fingerprint") or "").strip()
        if config_fingerprint:
            bucket["config_fingerprints"].add(config_fingerprint)

        bucket["runs"].append(
            {
                "run_id": row.get("run_id"),
                "run_key": row.get("run_key"),
                "ticker": row.get("ticker"),
                "date_label": row.get("date_label"),
                "report_dir": row.get("report_dir"),
                "report_saved_at": row.get("report_saved_at"),
                "total_trades": safe_int(row.get("total_trades"), 0),
                "pnl_pct": safe_float(row.get("pnl_pct"), 0.0),
                "pnl_dollars": safe_float(row.get("pnl_dollars"), 0.0),
                "signals": safe_int(row.get("signals"), 0),
                "regime_evaluations": safe_int(row.get("regime_evaluations"), 0),
                "processed_bars": safe_optional_int(row.get("processed_bars")),
                "total_bars": safe_optional_int(row.get("total_bars")),
                "run_total_trades": safe_optional_int(row.get("run_total_trades")),
                "run_total_pnl_pct": safe_optional_float(row.get("run_total_pnl_pct")),
                "run_total_pnl_dollars": safe_optional_float(
                    row.get("run_total_pnl_dollars")
                ),
                "run_signals": safe_optional_int(row.get("run_signals")),
                "run_regime_evaluations": safe_optional_int(
                    row.get("run_regime_evaluations")
                ),
                "run_processed_bars": safe_optional_int(row.get("run_processed_bars")),
                "run_total_bars": safe_optional_int(row.get("run_total_bars")),
                "strategy_names": (
                    row.get("strategy_names")
                    if isinstance(row.get("strategy_names"), list)
                    else []
                ),
                "unified_profile_id": row.get("unified_profile_id"),
                "unified_profile_name": row.get("unified_profile_name"),
                "adaptive_profile_id": row.get("adaptive_profile_id"),
                "adaptive_profile_name": row.get("adaptive_profile_name"),
                "strategy_combo_profile_id": row.get("strategy_combo_profile_id"),
                "strategy_combo_profile_name": row.get("strategy_combo_profile_name"),
                "profile_match_mode": row.get("profile_match_mode"),
                "aos_applied": (
                    row.get("aos_applied")
                    if isinstance(row.get("aos_applied"), dict)
                    else {}
                ),
                "control_plane_snapshot": (
                    row.get("control_plane_snapshot")
                    if isinstance(row.get("control_plane_snapshot"), dict)
                    else {}
                ),
                "resolved_config_snapshot": (
                    row.get("resolved_config_snapshot")
                    if isinstance(row.get("resolved_config_snapshot"), dict)
                    else {}
                ),
                "resolved_config_snapshot_id": row.get("resolved_config_snapshot_id"),
                "execution_config": (
                    row.get("execution_config")
                    if isinstance(row.get("execution_config"), dict)
                    else {}
                ),
                "run_request_config": (
                    row.get("run_request_config")
                    if isinstance(row.get("run_request_config"), dict)
                    else {}
                ),
            }
        )

    result: List[Dict[str, Any]] = []
    for day in sorted(by_day.keys()):
        bucket = by_day[day]
        runs = list(bucket.get("runs", []))
        runs.sort(
            key=lambda item: (
                str(item.get("report_saved_at") or ""),
                str(item.get("run_id") or ""),
            ),
            reverse=True,
        )
        trade_details = list(bucket.get("trade_details", []))
        trade_details.sort(
            key=lambda item: (
                str(item.get("exit_time") or item.get("entry_time") or ""),
                str(item.get("run_id") or ""),
                str(item.get("trade_id") or ""),
            )
        )
        unified_profile_ids = sorted(bucket.get("unified_profile_ids", set()))
        unified_profile_names = sorted(bucket.get("unified_profile_names", set()))
        adaptive_profile_ids = sorted(bucket.get("adaptive_profile_ids", set()))
        adaptive_profile_names = sorted(bucket.get("adaptive_profile_names", set()))
        strategy_combo_profile_ids = sorted(
            bucket.get("strategy_combo_profile_ids", set())
        )
        strategy_combo_profile_names = sorted(
            bucket.get("strategy_combo_profile_names", set())
        )
        profile_match_modes = sorted(bucket.get("profile_match_modes", set()))
        row: Dict[str, Any] = {
            "date": day,
            "success": True,
            "total_trades": safe_int(bucket.get("total_trades"), 0),
            "pnl_pct": safe_float(bucket.get("pnl_pct"), 0.0),
            "pnl_dollars": safe_float(bucket.get("pnl_dollars"), 0.0),
            "signals": safe_int(bucket.get("signals"), 0),
            "regime_evaluations": safe_int(bucket.get("regime_evaluations"), 0),
            "processed_bars": (
                safe_int(bucket.get("processed_bars"), 0)
                if safe_int(bucket.get("processed_bars_known_runs"), 0) > 0
                else None
            ),
            "total_bars": (
                safe_int(bucket.get("total_bars"), 0)
                if safe_int(bucket.get("total_bars_known_runs"), 0) > 0
                else None
            ),
            "trade_details": trade_details,
            "report_count": len(runs),
            "runs": runs,
            "strategy_names": sorted(bucket.get("strategy_names", set())),
            "unified_profile_ids": unified_profile_ids,
            "unified_profile_names": unified_profile_names,
            "adaptive_profile_ids": adaptive_profile_ids,
            "adaptive_profile_names": adaptive_profile_names,
            "strategy_combo_profile_ids": strategy_combo_profile_ids,
            "strategy_combo_profile_names": strategy_combo_profile_names,
            "profile_match_modes": profile_match_modes,
            "config_fingerprints": sorted(bucket.get("config_fingerprints", set())),
            "unified_profile_id": resolve_profile_values(set(unified_profile_ids)),
            "unified_profile_name": resolve_profile_values(set(unified_profile_names)),
            "adaptive_profile_id": resolve_profile_values(set(adaptive_profile_ids)),
            "adaptive_profile_name": resolve_profile_values(
                set(adaptive_profile_names)
            ),
            "strategy_combo_profile_id": resolve_profile_values(
                set(strategy_combo_profile_ids)
            ),
            "strategy_combo_profile_name": resolve_profile_values(
                set(strategy_combo_profile_names)
            ),
        }
        if len(runs) == 1:
            row["aos_applied"] = runs[0].get("aos_applied", {})
            row["control_plane_snapshot"] = runs[0].get("control_plane_snapshot", {})
            row["resolved_config_snapshot"] = runs[0].get(
                "resolved_config_snapshot",
                {},
            )
            row["resolved_config_snapshot_id"] = runs[0].get(
                "resolved_config_snapshot_id"
            )
            row["execution_config"] = runs[0].get("execution_config", {})
            row["run_request_config"] = runs[0].get("run_request_config", {})
            row["run_total_trades"] = safe_optional_int(runs[0].get("run_total_trades"))
            row["run_total_pnl_pct"] = safe_optional_float(
                runs[0].get("run_total_pnl_pct")
            )
            row["run_total_pnl_dollars"] = safe_optional_float(
                runs[0].get("run_total_pnl_dollars")
            )
            row["run_signals"] = safe_optional_int(runs[0].get("run_signals"))
            row["run_regime_evaluations"] = safe_optional_int(
                runs[0].get("run_regime_evaluations")
            )
            row["run_processed_bars"] = safe_optional_int(
                runs[0].get("run_processed_bars")
            )
            row["run_total_bars"] = safe_optional_int(runs[0].get("run_total_bars"))
        else:
            row["aos_applied"] = {}
            row["control_plane_snapshot"] = {}
            row["resolved_config_snapshot"] = {}
            row["resolved_config_snapshot_id"] = None
            row["execution_config"] = {}
            row["run_request_config"] = {}
            row["run_total_trades"] = None
            row["run_total_pnl_pct"] = None
            row["run_total_pnl_dollars"] = None
            row["run_signals"] = None
            row["run_regime_evaluations"] = None
            row["run_processed_bars"] = None
            row["run_total_bars"] = None
        result.append(row)
    return result


def compute_calendar_metrics(day_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_days = len(day_results)
    valid_days = sum(1 for item in day_results if item.get("success") is not False)
    failed_days = total_days - valid_days
    total_trades = sum(safe_int(item.get("total_trades"), 0) for item in day_results)
    total_pnl_pct = sum(
        safe_float(item.get("pnl_pct"), 0.0)
        for item in day_results
        if item.get("success") is not False
    )
    total_pnl_dollars = sum(
        safe_float(item.get("pnl_dollars"), 0.0)
        for item in day_results
        if item.get("success") is not False
    )
    return {
        "total_days": total_days,
        "valid_days": valid_days,
        "failed_days": failed_days,
        "total_trades": total_trades,
        "total_pnl_pct": total_pnl_pct,
        "total_pnl_dollars": total_pnl_dollars,
    }
