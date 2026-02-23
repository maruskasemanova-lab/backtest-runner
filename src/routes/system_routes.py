import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from src.routes.context import ApiServices, get_api_services
from src.runtime_mode import is_serverless_environment, stateful_run_api_supported

router = APIRouter()
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RANGE_DATE_RE = re.compile(
    r"^(?P<start>\d{4}-\d{2}-\d{2})_to_(?P<end>\d{4}-\d{2}-\d{2})$"
)
_PROFILE_PLACEHOLDER_TOKENS = {"none", "null", "n/a", "na", "undefined", "-"}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _diagnostic_cache_store(request: Request):
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    v2_services = getattr(state, "v2_services", None)
    store = getattr(v2_services, "store", None)
    return store


def _run_reports_store(request: Request):
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    return getattr(state, "run_reports_store", None)


def _run_reports_source_mode(request: Request) -> str:
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    explicit = str(getattr(state, "run_reports_source_mode", "") or "").strip()
    if explicit:
        return explicit
    store = getattr(state, "run_reports_store", None) if state is not None else None
    if store is None:
        return "filesystem_reports"
    return "run_reports_store"


def _external_report_dir_name(
    *, run_key: str, updated_at: Any, fallback_index: int
) -> str:
    normalized_run_key = re.sub(
        r"[^A-Za-z0-9_-]+", "_", str(run_key or "").strip()
    ).strip("_")
    if not normalized_run_key:
        normalized_run_key = f"run_{max(1, int(fallback_index))}"

    timestamp_prefix = "19700101_000000"
    normalized_updated_at = _normalize_iso_timestamp(updated_at)
    if normalized_updated_at:
        token = normalized_updated_at.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(token)
            timestamp_prefix = parsed.strftime("%Y%m%d_%H%M%S")
        except ValueError:
            pass

    return f"{timestamp_prefix}_supabase_{normalized_run_key}"


def _build_diagnostic_summary(
    *,
    ticker: str,
    profile: str,
    phase: int,
    payload: Dict[str, Any],
    from_cache: bool,
) -> Dict[str, Any]:
    top_level_sizes: Dict[str, Optional[int]] = {}
    for key, value in payload.items():
        if isinstance(value, (list, dict)):
            top_level_sizes[key] = len(value)
        else:
            top_level_sizes[key] = None

    return {
        "source": "diagnostic_summary",
        "ticker": ticker,
        "profile": profile,
        "phase": int(phase),
        "from_cache": bool(from_cache),
        "keys": sorted(payload.keys()),
        "top_level_sizes": top_level_sizes,
        "day_results_count": (
            len(payload.get("day_results", []))
            if isinstance(payload.get("day_results"), list)
            else 0
        ),
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def _sanitize_segment(value: str, *, field: str) -> str:
    token = str(value or "").strip()
    if not token or not _SAFE_SEGMENT_RE.fullmatch(token):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field}. Allowed characters: letters, numbers, '_' and '-'.",
        )
    return token


def _coerce_non_negative_int(value: Any, *, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail=f"{field} must be an integer >= 0."
        ) from exc
    if parsed < 0:
        raise HTTPException(status_code=400, detail=f"{field} must be >= 0.")
    return parsed


def _normalize_iso_date(value: Any) -> Optional[str]:
    token = str(value or "").strip()
    if not token or not _ISO_DATE_RE.fullmatch(token):
        return None
    return token


def _parse_report_saved_at(report_dir_name: str) -> Optional[str]:
    # Directory prefix format: YYYYMMDD_HHMMSS_<ticker>_<run_id>
    token = str(report_dir_name or "").strip()
    if len(token) < 15:
        return None
    head = token[:15]
    try:
        parsed = datetime.strptime(head, "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return parsed.isoformat(timespec="seconds")


def _parse_run_day_from_label(date_label: Any) -> Optional[str]:
    token = str(date_label or "").strip()
    if not token:
        return None
    if _ISO_DATE_RE.fullmatch(token):
        return token
    # Skip range labels like "2026-02-02_to_2026-02-05" for day calendar mode.
    return None


def _collect_strategy_names_from_trades(trades: Any) -> List[str]:
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


def _normalize_profile_token(value: Any) -> Optional[str]:
    token = str(value).strip() if value is not None else ""
    if not token:
        return None
    if token.lower() in _PROFILE_PLACEHOLDER_TOKENS:
        return None
    return token


def _first_profile_token(*values: Any) -> Optional[str]:
    for value in values:
        token = _normalize_profile_token(value)
        if token:
            return token
    return None


def _extract_profile_metadata(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    report_meta = (
        payload.get("report_metadata", {})
        if isinstance(payload.get("report_metadata"), dict)
        else {}
    )
    aos_applied = (
        payload.get("aos_applied", {})
        if isinstance(payload.get("aos_applied"), dict)
        else {}
    )
    execution_config = (
        payload.get("execution_config", {})
        if isinstance(payload.get("execution_config"), dict)
        else {}
    )
    if not aos_applied and isinstance(report_meta.get("aos_applied"), dict):
        aos_applied = report_meta.get("aos_applied", {})
    unified_meta = (
        aos_applied.get("unified_profile", {})
        if isinstance(aos_applied.get("unified_profile"), dict)
        else {}
    )
    adaptive_meta = (
        aos_applied.get("adaptive_profile", {})
        if isinstance(aos_applied.get("adaptive_profile"), dict)
        else {}
    )
    strategy_combo_meta = (
        aos_applied.get("strategy_combo", {})
        if isinstance(aos_applied.get("strategy_combo"), dict)
        else {}
    )
    adaptive_profile_id = _first_profile_token(
        report_meta.get("adaptive_profile_id"),
        payload.get("adaptive_profile_id"),
        execution_config.get("adaptive_profile_id"),
        execution_config.get("active_adaptive_tuner_profile_id"),
        adaptive_meta.get("active_profile_id"),
        adaptive_meta.get("profile_id"),
    )
    adaptive_profile_name = _first_profile_token(
        report_meta.get("adaptive_profile_name"),
        payload.get("adaptive_profile_name"),
        execution_config.get("adaptive_profile_name"),
        adaptive_meta.get("profile_name"),
    )
    strategy_combo_profile_id = _first_profile_token(
        report_meta.get("strategy_combo_profile_id"),
        payload.get("strategy_combo_profile_id"),
        execution_config.get("strategy_combo_profile_id"),
        execution_config.get("active_strategy_combo_profile_id"),
        strategy_combo_meta.get("active_profile_id"),
        strategy_combo_meta.get("profile_id"),
    )
    strategy_combo_profile_name = _first_profile_token(
        report_meta.get("strategy_combo_profile_name"),
        payload.get("strategy_combo_profile_name"),
        execution_config.get("strategy_combo_profile_name"),
        strategy_combo_meta.get("profile_name"),
    )
    unified_profile_id = _first_profile_token(
        report_meta.get("unified_profile_id"),
        payload.get("unified_profile_id"),
        execution_config.get("unified_profile_id"),
        execution_config.get("active_unified_profile_id"),
        unified_meta.get("active_profile_id"),
        unified_meta.get("profile_id"),
    )
    unified_profile_name = _first_profile_token(
        report_meta.get("unified_profile_name"),
        payload.get("unified_profile_name"),
        execution_config.get("unified_profile_name"),
        unified_meta.get("profile_name"),
    )
    return {
        "unified_profile_id": unified_profile_id,
        "unified_profile_name": unified_profile_name,
        "adaptive_profile_id": adaptive_profile_id,
        "adaptive_profile_name": adaptive_profile_name,
        "strategy_combo_profile_id": strategy_combo_profile_id,
        "strategy_combo_profile_name": strategy_combo_profile_name,
    }


def _match_profile_filter(
    *,
    run_id: str,
    unified_profile_id: Optional[str],
    adaptive_profile_id: Optional[str],
    strategy_combo_profile_id: Optional[str],
    requested_profile_id: str,
) -> Optional[str]:
    _ = run_id  # retained for backward-compatible signature
    requested = _normalize_profile_token(requested_profile_id)
    if not requested:
        return None

    requested_lower = requested.lower()
    for current_raw in (
        unified_profile_id,
        adaptive_profile_id,
        strategy_combo_profile_id,
    ):
        current = _normalize_profile_token(current_raw)
        if current and current.lower() == requested_lower:
            return "exact"
    return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed


def _safe_optional_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return parsed


def _safe_optional_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _normalize_iso_timestamp(value: Any) -> Optional[str]:
    token = str(value or "").strip()
    if not token:
        return None
    normalized = token.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.isoformat()


def _timestamp_lookup_keys(value: Any) -> List[str]:
    raw = str(value or "").strip()
    keys: List[str] = []
    if raw:
        keys.append(raw)
    normalized = _normalize_iso_timestamp(raw)
    if normalized and normalized not in keys:
        keys.append(normalized)
    if normalized and normalized.endswith("+00:00"):
        z_key = normalized[:-6] + "Z"
        if z_key not in keys:
            keys.append(z_key)
    return keys


def _day_from_timestamp(value: Any) -> Optional[str]:
    token = str(value or "").strip()
    if not token:
        return None
    if len(token) >= 10:
        direct = _normalize_iso_date(token[:10])
        if direct:
            return direct
    normalized = _normalize_iso_timestamp(token)
    if not normalized:
        return None
    return normalized[:10]


def _parse_range_label(date_label: Any) -> Optional[Tuple[str, str]]:
    token = str(date_label or "").strip()
    if not token:
        return None
    matched = _RANGE_DATE_RE.fullmatch(token)
    if not matched:
        return None
    start = _normalize_iso_date(matched.group("start"))
    end = _normalize_iso_date(matched.group("end"))
    if not start or not end:
        return None
    if start > end:
        return None
    return (start, end)


def _expand_day_range(start: str, end: str) -> List[str]:
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    days: List[str] = []
    cursor = start_date
    while cursor <= end_date:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def _extract_entry_reason(marker: Dict[str, Any]) -> Optional[str]:
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


def _extract_exit_reason(marker: Dict[str, Any]) -> Optional[str]:
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


def _build_entry_reason_map(markers: Any) -> Dict[str, str]:
    if not isinstance(markers, list):
        return {}
    reasons: Dict[str, str] = {}
    for marker in markers:
        if not isinstance(marker, dict):
            continue
        if str(marker.get("marker_type") or "").strip() != "entry_executed":
            continue
        reason = _extract_entry_reason(marker)
        if not reason:
            continue
        for key in _timestamp_lookup_keys(marker.get("timestamp")):
            reasons[key] = reason
    return reasons


def _build_exit_reason_map(markers: Any) -> Dict[str, str]:
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
        reason = _extract_exit_reason(marker)
        if not reason:
            continue
        for key in _timestamp_lookup_keys(marker.get("timestamp")):
            reasons[key] = reason
    return reasons


def _build_marker_strategy_names_by_day(markers: Any) -> Dict[str, List[str]]:
    if not isinstance(markers, list):
        return {}
    by_day: Dict[str, Set[str]] = {}
    for marker in markers:
        if not isinstance(marker, dict):
            continue
        day = _day_from_timestamp(marker.get("timestamp"))
        if not day:
            continue
        strategy = str(marker.get("strategy") or "").strip()
        if not strategy:
            continue
        by_day.setdefault(day, set()).add(strategy)
    return {day: sorted(values) for day, values in by_day.items()}


def _count_markers_by_day(markers: Any, *, marker_types: Set[str]) -> Dict[str, int]:
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
        day = _day_from_timestamp(marker.get("timestamp"))
        if not day:
            continue
        counts[day] = int(counts.get(day, 0)) + 1
    return counts


def _resolve_profile_values(values: Set[str]) -> Optional[str]:
    if not values:
        return None
    if len(values) == 1:
        return sorted(values)[0]
    return None


def _build_history_day_rows(
    payload: Dict[str, Any],
    *,
    report_dir_name: str,
    report_saved_at: Optional[str] = None,
    include_multi_day: bool,
    profile_match_mode: Optional[str],
) -> List[Dict[str, Any]]:
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id:
        return []
    ticker = str(payload.get("ticker") or "").strip().upper()
    date_label = str(payload.get("date") or "").strip()
    saved_at = _normalize_iso_timestamp(report_saved_at) or _parse_report_saved_at(
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
    execution_config = (
        payload.get("execution_config", {})
        if isinstance(payload.get("execution_config"), dict)
        else {}
    )
    aos_applied = (
        payload.get("aos_applied", {})
        if isinstance(payload.get("aos_applied"), dict)
        else {}
    )
    profile_meta = _extract_profile_metadata(payload)
    entry_reasons = _build_entry_reason_map(markers)
    exit_reasons = _build_exit_reason_map(markers)
    marker_strategy_by_day = _build_marker_strategy_names_by_day(markers)
    signal_markers_by_day = _count_markers_by_day(
        markers, marker_types={"signal_generated"}
    )
    regime_markers_by_day = _count_markers_by_day(
        markers, marker_types={"regime_detected"}
    )
    run_signals = sum(signal_markers_by_day.values())
    run_regime_evaluations = sum(regime_markers_by_day.values())
    run_processed_bars = _safe_optional_int(payload.get("processed_bars"))
    if run_processed_bars is None:
        run_processed_bars = _safe_optional_int(session_summary.get("bars_processed"))
    run_total_bars = _safe_optional_int(payload.get("total_bars"))
    if run_total_bars is None:
        run_total_bars = _safe_optional_int(session_summary.get("bars_processed"))
    run_total_trades = _safe_optional_int(session_summary.get("total_trades"))
    if run_total_trades is None and trades:
        run_total_trades = len(trades)
    run_total_pnl_pct = _safe_optional_float(session_summary.get("total_pnl_pct"))
    run_total_pnl_dollars = _safe_optional_float(
        session_summary.get("total_pnl_dollars")
    )
    range_days: List[str] = []
    day_from_label = _parse_run_day_from_label(date_label)
    if day_from_label:
        range_days = [day_from_label]
    elif include_multi_day:
        range_window = _parse_range_label(date_label)
        if range_window:
            range_days = _expand_day_range(range_window[0], range_window[1])

    grouped_trades: Dict[str, List[Dict[str, Any]]] = {}
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        entry_time = str(trade.get("entry_time") or "").strip() or None
        exit_time = str(trade.get("exit_time") or "").strip() or None
        trade_day = _day_from_timestamp(exit_time) or _day_from_timestamp(entry_time)
        if not trade_day:
            continue
        entry_reason = str(trade.get("entry_reason") or "").strip() or None
        if not entry_reason:
            for key in _timestamp_lookup_keys(entry_time):
                if key in entry_reasons:
                    entry_reason = entry_reasons.get(key)
                    break
        exit_reason = str(trade.get("exit_reason") or "").strip() or None
        if not exit_reason:
            for key in _timestamp_lookup_keys(exit_time):
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
                "entry_price": _safe_float(trade.get("entry_price"), 0.0),
                "exit_price": _safe_float(trade.get("exit_price"), 0.0),
                "bars_held": _safe_int(trade.get("bars_held"), 0),
                "pnl_pct": _safe_float(trade.get("pnl_pct"), 0.0),
                "pnl_dollars": _safe_float(trade.get("pnl_dollars"), 0.0),
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
            name for name in _collect_strategy_names_from_trades(day_trades) if name
        )
        for strategy_name in marker_strategy_by_day.get(day, []):
            if strategy_name:
                day_strategy_names.add(strategy_name)
        pnl_pct = sum(_safe_float(item.get("pnl_pct"), 0.0) for item in day_trades)
        pnl_dollars = sum(
            _safe_float(item.get("pnl_dollars"), 0.0) for item in day_trades
        )
        rows.append(
            {
                "date": day,
                "success": True,
                "ticker": ticker,
                "run_id": run_id,
                "date_label": date_label,
                "report_dir": report_dir_name,
                "report_saved_at": saved_at,
                "profile_match_mode": profile_match_mode,
                "total_trades": len(day_trades),
                "pnl_pct": pnl_pct,
                "pnl_dollars": pnl_dollars,
                "signals": _safe_int(signal_markers_by_day.get(day), 0),
                "regime_evaluations": _safe_int(regime_markers_by_day.get(day), 0),
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
                "aos_applied": aos_applied,
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
            }
        )
    return rows


def _aggregate_history_day_rows(day_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            }
            by_day[day] = bucket

        bucket["total_trades"] += _safe_int(row.get("total_trades"), 0)
        bucket["pnl_pct"] += _safe_float(row.get("pnl_pct"), 0.0)
        bucket["pnl_dollars"] += _safe_float(row.get("pnl_dollars"), 0.0)
        bucket["signals"] += _safe_int(row.get("signals"), 0)
        bucket["regime_evaluations"] += _safe_int(row.get("regime_evaluations"), 0)
        row_processed_bars = _safe_optional_int(row.get("processed_bars"))
        row_total_bars = _safe_optional_int(row.get("total_bars"))
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

        bucket["runs"].append(
            {
                "run_id": row.get("run_id"),
                "ticker": row.get("ticker"),
                "date_label": row.get("date_label"),
                "report_dir": row.get("report_dir"),
                "report_saved_at": row.get("report_saved_at"),
                "total_trades": _safe_int(row.get("total_trades"), 0),
                "pnl_pct": _safe_float(row.get("pnl_pct"), 0.0),
                "pnl_dollars": _safe_float(row.get("pnl_dollars"), 0.0),
                "signals": _safe_int(row.get("signals"), 0),
                "regime_evaluations": _safe_int(row.get("regime_evaluations"), 0),
                "processed_bars": _safe_optional_int(row.get("processed_bars")),
                "total_bars": _safe_optional_int(row.get("total_bars")),
                "run_total_trades": _safe_optional_int(row.get("run_total_trades")),
                "run_total_pnl_pct": _safe_optional_float(row.get("run_total_pnl_pct")),
                "run_total_pnl_dollars": _safe_optional_float(
                    row.get("run_total_pnl_dollars")
                ),
                "run_signals": _safe_optional_int(row.get("run_signals")),
                "run_regime_evaluations": _safe_optional_int(
                    row.get("run_regime_evaluations")
                ),
                "run_processed_bars": _safe_optional_int(row.get("run_processed_bars")),
                "run_total_bars": _safe_optional_int(row.get("run_total_bars")),
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
                "execution_config": (
                    row.get("execution_config")
                    if isinstance(row.get("execution_config"), dict)
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
            "total_trades": _safe_int(bucket.get("total_trades"), 0),
            "pnl_pct": _safe_float(bucket.get("pnl_pct"), 0.0),
            "pnl_dollars": _safe_float(bucket.get("pnl_dollars"), 0.0),
            "signals": _safe_int(bucket.get("signals"), 0),
            "regime_evaluations": _safe_int(bucket.get("regime_evaluations"), 0),
            "processed_bars": (
                _safe_int(bucket.get("processed_bars"), 0)
                if _safe_int(bucket.get("processed_bars_known_runs"), 0) > 0
                else None
            ),
            "total_bars": (
                _safe_int(bucket.get("total_bars"), 0)
                if _safe_int(bucket.get("total_bars_known_runs"), 0) > 0
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
            "unified_profile_id": _resolve_profile_values(set(unified_profile_ids)),
            "unified_profile_name": _resolve_profile_values(set(unified_profile_names)),
            "adaptive_profile_id": _resolve_profile_values(set(adaptive_profile_ids)),
            "adaptive_profile_name": _resolve_profile_values(
                set(adaptive_profile_names)
            ),
            "strategy_combo_profile_id": _resolve_profile_values(
                set(strategy_combo_profile_ids)
            ),
            "strategy_combo_profile_name": _resolve_profile_values(
                set(strategy_combo_profile_names)
            ),
        }
        if len(runs) == 1:
            row["aos_applied"] = runs[0].get("aos_applied", {})
            row["execution_config"] = runs[0].get("execution_config", {})
            row["run_total_trades"] = _safe_optional_int(
                runs[0].get("run_total_trades")
            )
            row["run_total_pnl_pct"] = _safe_optional_float(
                runs[0].get("run_total_pnl_pct")
            )
            row["run_total_pnl_dollars"] = _safe_optional_float(
                runs[0].get("run_total_pnl_dollars")
            )
            row["run_signals"] = _safe_optional_int(runs[0].get("run_signals"))
            row["run_regime_evaluations"] = _safe_optional_int(
                runs[0].get("run_regime_evaluations")
            )
            row["run_processed_bars"] = _safe_optional_int(
                runs[0].get("run_processed_bars")
            )
            row["run_total_bars"] = _safe_optional_int(runs[0].get("run_total_bars"))
        else:
            row["aos_applied"] = {}
            row["execution_config"] = {}
            row["run_total_trades"] = None
            row["run_total_pnl_pct"] = None
            row["run_total_pnl_dollars"] = None
            row["run_signals"] = None
            row["run_regime_evaluations"] = None
            row["run_processed_bars"] = None
            row["run_total_bars"] = None
        result.append(row)
    return result


def _compute_calendar_metrics(day_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_days = len(day_results)
    valid_days = sum(1 for item in day_results if item.get("success") is not False)
    failed_days = total_days - valid_days
    total_trades = sum(_safe_int(item.get("total_trades"), 0) for item in day_results)
    total_pnl_pct = sum(
        _safe_float(item.get("pnl_pct"), 0.0)
        for item in day_results
        if item.get("success") is not False
    )
    total_pnl_dollars = sum(
        _safe_float(item.get("pnl_dollars"), 0.0)
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


def _report_has_closed_trades(payload: Dict[str, Any]) -> bool:
    session_summary = payload.get("session_summary", {})
    if not isinstance(session_summary, dict):
        return False
    trades = session_summary.get("trades", [])
    if isinstance(trades, list) and len(trades) > 0:
        return True
    total_trades = _safe_int(session_summary.get("total_trades"), 0)
    return total_trades > 0


def _load_aos_adaptive_profile_options(ticker: str) -> List[Dict[str, Any]]:
    config_path = _project_root() / "aos_optimization" / "aos_config.json"
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
        str(ticker_payload.get("active_adaptive_tuner_profile_id") or "").strip()
        or None
    )
    profiles = ticker_payload.get("adaptive_tuner_profiles", [])
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
        created_at = _normalize_iso_timestamp(profile.get("created_at"))
        existing = collected.get(profile_id)
        if existing is None:
            collected[profile_id] = {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "active": bool(active_profile_id and active_profile_id == profile_id),
                "latest_created_at": created_at,
                "source": "aos_config",
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
            "source": "aos_config",
        }

    options = list(collected.values())
    options.sort(key=lambda item: str(item.get("profile_id") or ""))
    options.sort(
        key=lambda item: str(item.get("latest_created_at") or ""), reverse=True
    )
    options.sort(key=lambda item: 0 if bool(item.get("active")) else 1)
    return options


def _load_aos_unified_profile_options(ticker: str) -> List[Dict[str, Any]]:
    config_path = _project_root() / "aos_optimization" / "aos_config.json"
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
        str(ticker_payload.get("active_unified_profile_id") or "").strip() or None
    )
    profiles = ticker_payload.get("unified_profiles", [])
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
        created_at = _normalize_iso_timestamp(profile.get("created_at"))
        existing = collected.get(profile_id)
        if existing is None:
            collected[profile_id] = {
                "profile_id": profile_id,
                "profile_name": profile_name,
                "active": bool(active_profile_id and active_profile_id == profile_id),
                "latest_created_at": created_at,
                "source": "aos_unified",
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
            "source": "aos_unified",
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


def _merge_adaptive_profile_options(
    history_options: List[Dict[str, Any]],
    aos_options: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return _merge_profile_options(history_options, aos_options)


@router.get("/")
async def root(services: ApiServices = Depends(get_api_services)):
    return {
        "name": "Unified Backtest Runner",
        "version": "1.0.0",
        "active_runs": len(services.active_runners),
    }


@router.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "serverless_environment": bool(is_serverless_environment()),
        "stateful_run_api_supported": bool(stateful_run_api_supported()),
    }


@router.get("/api/system/l2/runtime")
async def get_l2_runtime(
    services: ApiServices = Depends(get_api_services),
) -> Dict[str, Any]:
    l2_features = services.l2_features
    l2_manager = services.l2_manager
    return {
        "iceberg_detection_enabled": bool(
            getattr(l2_features, "iceberg_detection_enabled", True)
        ),
        "cache_max_tickers": int(getattr(l2_manager, "max_cached_tickers", 0)),
        "cache_max_rows": int(getattr(l2_manager, "max_cached_rows", 0)),
        "cache_max_bytes": int(getattr(l2_manager, "max_cached_bytes", 0)),
    }


@router.post("/api/system/l2/runtime")
async def update_l2_runtime(
    body: Dict[str, Any] = Body(...),
    services: ApiServices = Depends(get_api_services),
) -> Dict[str, Any]:
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")

    l2_features = services.l2_features
    l2_manager = services.l2_manager
    updated: Dict[str, Any] = {}

    if "iceberg_detection_enabled" in body:
        enabled = bool(body.get("iceberg_detection_enabled"))
        setattr(l2_features, "iceberg_detection_enabled", enabled)
        updated["iceberg_detection_enabled"] = enabled

    if "cache_max_tickers" in body:
        value = _coerce_non_negative_int(
            body.get("cache_max_tickers"), field="cache_max_tickers"
        )
        setattr(l2_manager, "max_cached_tickers", value)
        updated["cache_max_tickers"] = value

    if "cache_max_rows" in body:
        value = _coerce_non_negative_int(
            body.get("cache_max_rows"), field="cache_max_rows"
        )
        setattr(l2_manager, "max_cached_rows", value)
        updated["cache_max_rows"] = value

    if "cache_max_bytes" in body:
        value = _coerce_non_negative_int(
            body.get("cache_max_bytes"), field="cache_max_bytes"
        )
        setattr(l2_manager, "max_cached_bytes", value)
        updated["cache_max_bytes"] = value

    runtime = await get_l2_runtime(services)
    return {"message": "L2 runtime updated", "updated": updated, "runtime": runtime}


@router.get("/api/available-data")
async def get_available_data(
    refresh: bool = Query(default=False),
    services: ApiServices = Depends(get_api_services),
):
    """Get available tickers and date ranges from data files."""
    try:
        return services.databento_svc.get_available_data_summary(refresh=bool(refresh))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/data/files")
async def list_data_files(services: ApiServices = Depends(get_api_services)):
    """List available data files."""
    return services.data_loader.list_available_files()


@router.get("/api/reports/diagnostic/{ticker}")
async def get_diagnostic_report(
    request: Request,
    ticker: str,
    phase: int = Query(default=0, ge=0, le=20),
    profile: str = Query(default="diagnostic", min_length=1, max_length=64),
    summary_only: bool = Query(default=False),
    refresh_cache: bool = Query(default=False),
) -> Any:
    """
    Read a diagnostic JSON report from reports/<ticker>_<profile>/phase<phase>_<profile>.json.
    Missing files are surfaced as explicit errors (no fallback behavior).
    When cache store is available in app state, payload is cached by file mtime.
    """
    safe_ticker = _sanitize_segment(ticker, field="ticker").upper()
    safe_profile = _sanitize_segment(profile, field="profile").lower()
    report_dir = _project_root() / "reports" / f"{safe_ticker.lower()}_{safe_profile}"
    report_file = report_dir / f"phase{phase}_{safe_profile}.json"

    if not report_file.exists():
        relative = report_file.relative_to(_project_root())
        raise HTTPException(
            status_code=404, detail=f"Diagnostic report not found: {relative}"
        )

    if not report_file.is_file():
        relative = report_file.relative_to(_project_root())
        raise HTTPException(
            status_code=400, detail=f"Diagnostic report path is not a file: {relative}"
        )

    store = _diagnostic_cache_store(request)
    payload: Optional[Dict[str, Any]] = None
    from_cache = False

    source_path = str(report_file.resolve())
    try:
        source_mtime_ns = int(report_file.stat().st_mtime_ns)
    except OSError:
        source_mtime_ns = 0

    cache_key: Optional[str] = None
    if store is not None and not refresh_cache:
        build_key = getattr(store, "diagnostic_cache_key", None)
        read_cache = getattr(store, "get_diagnostic_payload_cache", None)
        if callable(build_key) and callable(read_cache):
            try:
                cache_key = build_key(
                    ticker=safe_ticker, profile=safe_profile, phase=phase
                )
                cached = read_cache(
                    cache_key=cache_key,
                    source_path=source_path,
                    source_mtime_ns=source_mtime_ns,
                )
                if isinstance(cached, dict):
                    payload = cached
                    from_cache = True
            except Exception:
                payload = None
                from_cache = False

    if payload is None:
        try:
            raw = report_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to read diagnostic report: {exc}"
            ) from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=500, detail=f"Diagnostic report is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=500, detail="Diagnostic report root must be a JSON object."
            )
        payload = parsed

        write_cache = (
            getattr(store, "upsert_diagnostic_payload_cache", None)
            if store is not None
            else None
        )
        if callable(write_cache):
            try:
                if not cache_key:
                    build_key = getattr(store, "diagnostic_cache_key", None)
                    if callable(build_key):
                        cache_key = build_key(
                            ticker=safe_ticker, profile=safe_profile, phase=phase
                        )
                if cache_key:
                    write_cache(
                        cache_key=cache_key,
                        ticker=safe_ticker,
                        profile=safe_profile,
                        phase=phase,
                        source_path=source_path,
                        source_mtime_ns=source_mtime_ns,
                        payload=payload,
                    )
            except Exception:
                # Cache write is best-effort only.
                pass

    if summary_only:
        return _build_diagnostic_summary(
            ticker=safe_ticker,
            profile=safe_profile,
            phase=phase,
            payload=payload,
            from_cache=from_cache,
        )

    return payload


@router.get("/api/reports/history/{ticker}")
async def get_saved_run_history(
    request: Request,
    ticker: str,
    limit: int = Query(default=300, ge=1, le=5000),
    run_id: str = Query(default="", max_length=128),
    run_id_contains: str = Query(default="", max_length=128),
    unified_profile_id: str = Query(default="", max_length=128),
    adaptive_profile_id: str = Query(default="", max_length=128),
    include_multi_day: bool = Query(default=True),
    include_zero_trade_runs: bool = Query(default=False),
) -> Dict[str, Any]:
    """
    Read historical session summaries and aggregate day-level PnL/trade details
    for the diagnostics calendar.

    Source selection:
    - if run_reports_store is configured, use that store as authoritative source.
    - otherwise read local reports/*/session_summary.json artifacts.
    """
    safe_ticker = _sanitize_segment(ticker, field="ticker").upper()
    run_id_exact_filter = str(run_id or "").strip().lower()
    run_id_filter = str(run_id_contains or "").strip().lower()
    requested_profile_id = (
        _first_profile_token(unified_profile_id, adaptive_profile_id) or ""
    )

    day_rows: List[Dict[str, Any]] = []
    matched_reports = 0
    scanned_reports = 0
    skipped_invalid = 0
    run_latest_saved_at: Dict[str, Optional[str]] = {}
    history_profile_names: Dict[str, Set[str]] = {}

    def _process_history_payload(
        *,
        payload: Dict[str, Any],
        report_dir_name: str,
        report_saved_at: Optional[str],
    ) -> None:
        nonlocal matched_reports
        run_id_value = str(payload.get("run_id") or "").strip()
        if not run_id_value:
            return
        has_closed_trades = _report_has_closed_trades(payload)
        if not has_closed_trades and not include_zero_trade_runs:
            return

        payload_ticker = str(payload.get("ticker") or "").strip().upper()
        if payload_ticker != safe_ticker:
            return
        normalized_saved_at = _normalize_iso_timestamp(
            report_saved_at
        ) or _parse_report_saved_at(report_dir_name)
        current_latest = str(run_latest_saved_at.get(run_id_value) or "")
        if normalized_saved_at and normalized_saved_at > current_latest:
            run_latest_saved_at[run_id_value] = normalized_saved_at
        elif run_id_value not in run_latest_saved_at:
            run_latest_saved_at[run_id_value] = normalized_saved_at

        profile_meta = _extract_profile_metadata(payload)
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

        profile_match_mode = _match_profile_filter(
            run_id=run_id_value,
            unified_profile_id=profile_meta.get("unified_profile_id"),
            adaptive_profile_id=profile_meta.get("adaptive_profile_id"),
            strategy_combo_profile_id=profile_meta.get("strategy_combo_profile_id"),
            requested_profile_id=requested_profile_id,
        )
        if requested_profile_id and profile_match_mode is None:
            return

        run_day_rows = _build_history_day_rows(
            payload,
            report_dir_name=report_dir_name,
            report_saved_at=normalized_saved_at,
            include_multi_day=include_multi_day,
            profile_match_mode=profile_match_mode,
        )
        if not run_day_rows:
            return
        day_rows.extend(run_day_rows)
        matched_reports += 1

    source_mode = _run_reports_source_mode(request)
    source_path_hint = "run_reports_store"
    external_store = _run_reports_store(request)
    list_run_summaries = getattr(external_store, "list_run_summaries", None)
    used_run_reports_store = False

    if callable(list_run_summaries):
        used_run_reports_store = True
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
            report_saved_at = _normalize_iso_timestamp(row.get("updated_at"))
            report_dir_name = _external_report_dir_name(
                run_key=str(row.get("run_key") or ""),
                updated_at=report_saved_at,
                fallback_index=index,
            )
            _process_history_payload(
                payload=payload,
                report_dir_name=report_dir_name,
                report_saved_at=report_saved_at,
            )

    if not used_run_reports_store:
        source_mode = "filesystem_reports"
        source_path_hint = "reports/*/session_summary.json"
        reports_root = _project_root() / "reports"
        if reports_root.exists():
            report_files = sorted(
                reports_root.glob("*/session_summary.json"),
                key=lambda path: path.parent.name,
                reverse=True,
            )
            for report_file in report_files:
                if matched_reports >= limit:
                    break
                scanned_reports += 1
                report_dir_name = report_file.parent.name

                try:
                    raw = report_file.read_text(encoding="utf-8")
                    payload = json.loads(raw)
                except (OSError, json.JSONDecodeError):
                    skipped_invalid += 1
                    continue
                if not isinstance(payload, dict):
                    skipped_invalid += 1
                    continue

                _process_history_payload(
                    payload=payload,
                    report_dir_name=report_dir_name,
                    report_saved_at=None,
                )

    day_results = _aggregate_history_day_rows(day_rows)
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
        {"run_id": run_key, "latest_saved_at": run_latest_saved_at.get(run_key)}
        for run_key in run_latest_saved_at.keys()
    ]
    run_options.sort(
        key=lambda item: (
            str(item.get("latest_saved_at") or ""),
            str(item.get("run_id") or ""),
        ),
        reverse=True,
    )
    adaptive_profile_options = _merge_adaptive_profile_options(
        history_profile_options,
        _load_aos_adaptive_profile_options(safe_ticker),
    )
    unified_profile_options = _merge_profile_options(
        history_profile_options,
        _load_aos_unified_profile_options(safe_ticker),
    )

    return {
        "source": "saved_run_history",
        "source_mode": source_mode,
        "source_path_hint": source_path_hint,
        "ticker": safe_ticker,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
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
        "metrics": _compute_calendar_metrics(day_results),
        "day_results": day_results,
    }
