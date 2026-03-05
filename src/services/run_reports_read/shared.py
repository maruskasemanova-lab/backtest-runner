import base64
import gzip
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.services.run_config_snapshot_service import (
    attach_resolved_config_snapshot_to_summary,
)

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RANGE_DATE_RE = re.compile(
    r"^(?P<start>\d{4}-\d{2}-\d{2})_to_(?P<end>\d{4}-\d{2}-\d{2})$"
)
_PROFILE_PLACEHOLDER_TOKENS = {"none", "null", "n/a", "na", "undefined", "-"}


@dataclass(frozen=True)
class RunReportsReadDeps:
    project_root: Path
    report_store: Any = None
    active_runners: Dict[str, Any] = field(default_factory=dict)
    source_mode: str = "run_reports_store"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def external_report_dir_name(
    *, run_key: str, updated_at: Any, fallback_index: int
) -> str:
    normalized_run_key = re.sub(
        r"[^A-Za-z0-9_-]+", "_", str(run_key or "").strip()
    ).strip("_")
    if not normalized_run_key:
        normalized_run_key = f"run_{max(1, int(fallback_index))}"

    timestamp_prefix = "19700101_000000"
    normalized_updated_at = normalize_iso_timestamp(updated_at)
    if normalized_updated_at:
        token = normalized_updated_at.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(token)
            timestamp_prefix = parsed.strftime("%Y%m%d_%H%M%S")
        except ValueError:
            pass

    return f"{timestamp_prefix}_supabase_{normalized_run_key}"


def active_report_dir_name(*, run_key: str) -> str:
    normalized_run_key = re.sub(
        r"[^A-Za-z0-9_-]+", "_", str(run_key or "").strip()
    ).strip("_")
    if not normalized_run_key:
        normalized_run_key = "run"
    return f"active_{normalized_run_key}"


def history_identity_key(payload: Dict[str, Any]) -> str:
    run_id = str(payload.get("run_id") or "").strip()
    ticker = str(payload.get("ticker") or "").strip().upper()
    date_label = str(payload.get("date") or "").strip()
    if not run_id or not ticker or not date_label:
        return ""
    return f"{run_id}:{ticker}:{date_label}"


def parse_report_saved_at(report_dir_name: str) -> Optional[str]:
    token = str(report_dir_name or "").strip()
    if len(token) < 15:
        return None
    head = token[:15]
    try:
        parsed = datetime.strptime(head, "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return parsed.isoformat(timespec="seconds")


def parse_run_day_from_label(date_label: Any) -> Optional[str]:
    token = str(date_label or "").strip()
    if not token:
        return None
    if _ISO_DATE_RE.fullmatch(token):
        return token
    return None


def normalize_profile_token(value: Any) -> Optional[str]:
    token = str(value).strip() if value is not None else ""
    if not token:
        return None
    if token.lower() in _PROFILE_PLACEHOLDER_TOKENS:
        return None
    return token


def first_profile_token(*values: Any) -> Optional[str]:
    for value in values:
        token = normalize_profile_token(value)
        if token:
            return token
    return None


def resolved_config_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = payload.get("resolved_config_snapshot", {})
    return snapshot if isinstance(snapshot, dict) else {}


def has_modern_resolved_config_snapshot(payload: Dict[str, Any]) -> bool:
    snapshot = resolved_config_snapshot(payload)
    if snapshot:
        return True
    return bool(str(payload.get("resolved_config_snapshot_id") or "").strip())


def has_modern_playback_snapshot(payload: Dict[str, Any]) -> bool:
    playback = payload.get("playback_snapshot", {})
    if not isinstance(playback, dict):
        return False
    encoding = str(playback.get("encoding") or "").strip().lower()
    if encoding != "gzip+base64":
        return False
    return bool(str(playback.get("payload_b64") or "").strip())


def is_supported_persisted_run_summary(payload: Dict[str, Any]) -> bool:
    return has_modern_resolved_config_snapshot(payload)


def resolve_config_payload_dict(payload: Dict[str, Any], *, key: str) -> Dict[str, Any]:
    direct = payload.get(key, {})
    snapshot = resolved_config_snapshot(payload)
    nested = snapshot.get(key, {})
    nested_payload = nested if isinstance(nested, dict) else {}
    if isinstance(direct, dict):
        if nested_payload:
            return {**nested_payload, **direct}
        return direct
    return nested_payload


def extract_profile_metadata(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    snapshot = resolved_config_snapshot(payload)
    report_meta = (
        payload.get("report_metadata", {})
        if isinstance(payload.get("report_metadata"), dict)
        else {}
    )
    snapshot_report_meta = (
        snapshot.get("report_metadata", {})
        if isinstance(snapshot.get("report_metadata"), dict)
        else {}
    )
    if snapshot_report_meta:
        report_meta = {**snapshot_report_meta, **report_meta}
    aos_applied = resolve_config_payload_dict(payload, key="aos_applied")
    execution_config = resolve_config_payload_dict(payload, key="execution_config")
    control_plane_snapshot = resolve_config_payload_dict(
        payload,
        key="control_plane_snapshot",
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
    adaptive_profile_id = first_profile_token(
        report_meta.get("adaptive_profile_id"),
        payload.get("adaptive_profile_id"),
        execution_config.get("adaptive_profile_id"),
        execution_config.get("active_adaptive_tuner_profile_id"),
        adaptive_meta.get("active_profile_id"),
        adaptive_meta.get("profile_id"),
    )
    adaptive_profile_name = first_profile_token(
        report_meta.get("adaptive_profile_name"),
        payload.get("adaptive_profile_name"),
        execution_config.get("adaptive_profile_name"),
        adaptive_meta.get("profile_name"),
    )
    strategy_combo_profile_id = first_profile_token(
        report_meta.get("strategy_combo_profile_id"),
        payload.get("strategy_combo_profile_id"),
        execution_config.get("strategy_combo_profile_id"),
        execution_config.get("active_strategy_combo_profile_id"),
        strategy_combo_meta.get("active_profile_id"),
        strategy_combo_meta.get("profile_id"),
    )
    strategy_combo_profile_name = first_profile_token(
        report_meta.get("strategy_combo_profile_name"),
        payload.get("strategy_combo_profile_name"),
        execution_config.get("strategy_combo_profile_name"),
        strategy_combo_meta.get("profile_name"),
    )
    unified_profile_id = first_profile_token(
        report_meta.get("unified_profile_id"),
        payload.get("unified_profile_id"),
        execution_config.get("unified_profile_id"),
        execution_config.get("active_unified_profile_id"),
        unified_meta.get("active_profile_id"),
        unified_meta.get("profile_id"),
    )
    unified_profile_name = first_profile_token(
        report_meta.get("unified_profile_name"),
        payload.get("unified_profile_name"),
        execution_config.get("unified_profile_name"),
        unified_meta.get("profile_name"),
    )
    config_fingerprint = first_profile_token(
        report_meta.get("config_fingerprint"),
        payload.get("config_fingerprint"),
        execution_config.get("config_fingerprint"),
        control_plane_snapshot.get("config_fingerprint"),
        control_plane_snapshot.get("execution_config_fingerprint"),
    )
    return {
        "unified_profile_id": unified_profile_id,
        "unified_profile_name": unified_profile_name,
        "adaptive_profile_id": adaptive_profile_id,
        "adaptive_profile_name": adaptive_profile_name,
        "strategy_combo_profile_id": strategy_combo_profile_id,
        "strategy_combo_profile_name": strategy_combo_profile_name,
        "config_fingerprint": config_fingerprint,
    }


def match_profile_filter(
    *,
    run_id: str,
    unified_profile_id: Optional[str],
    adaptive_profile_id: Optional[str],
    strategy_combo_profile_id: Optional[str],
    requested_profile_id: str,
) -> Optional[str]:
    _ = run_id
    requested = normalize_profile_token(requested_profile_id)
    if not requested:
        return None

    requested_lower = requested.lower()
    for current_raw in (
        unified_profile_id,
        adaptive_profile_id,
        strategy_combo_profile_id,
    ):
        current = normalize_profile_token(current_raw)
        if current and current.lower() == requested_lower:
            return "exact"
    return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed


def safe_optional_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def safe_int(value: Any, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return parsed


def safe_optional_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed


def normalize_iso_timestamp(value: Any) -> Optional[str]:
    token = str(value or "").strip()
    if not token:
        return None
    normalized = token.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.isoformat()


def normalize_iso_date(value: Any) -> Optional[str]:
    token = str(value or "").strip()
    if not token or not _ISO_DATE_RE.fullmatch(token):
        return None
    return token


def timestamp_lookup_keys(value: Any) -> List[str]:
    raw = str(value or "").strip()
    keys: List[str] = []
    if raw:
        keys.append(raw)
    normalized = normalize_iso_timestamp(raw)
    if normalized and normalized not in keys:
        keys.append(normalized)
    if normalized and normalized.endswith("+00:00"):
        z_key = normalized[:-6] + "Z"
        if z_key not in keys:
            keys.append(z_key)
    return keys


def day_from_timestamp(value: Any) -> Optional[str]:
    token = str(value or "").strip()
    if not token:
        return None
    if len(token) >= 10:
        direct = normalize_iso_date(token[:10])
        if direct:
            return direct
    normalized = normalize_iso_timestamp(token)
    if not normalized:
        return None
    return normalized[:10]


def parse_range_label(date_label: Any) -> Optional[Tuple[str, str]]:
    token = str(date_label or "").strip()
    if not token:
        return None
    matched = _RANGE_DATE_RE.fullmatch(token)
    if not matched:
        return None
    start = normalize_iso_date(matched.group("start"))
    end = normalize_iso_date(matched.group("end"))
    if not start or not end:
        return None
    if start > end:
        return None
    return (start, end)


def expand_day_range(start: str, end: str) -> List[str]:
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    days: List[str] = []
    cursor = start_date
    while cursor <= end_date:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def split_run_key(run_key: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    token = str(run_key or "").strip()
    if not token:
        return (None, None, None)
    parts = token.split(":")
    if len(parts) < 3:
        return (None, None, None)
    date_label = parts[-1]
    ticker = parts[-2]
    run_id = ":".join(parts[:-2])
    if not run_id or not ticker or not date_label:
        return (None, None, None)
    return (run_id, ticker, date_label)


def normalize_summary_ticker(value: Any) -> Optional[str]:
    token = str(value or "").strip().upper()
    if not token:
        return None
    return token


def extract_summary_date_range(
    *,
    summary_payload: Dict[str, Any],
    run_key: str,
    updated_at: Any,
) -> Tuple[Optional[str], Optional[str]]:
    start = normalize_iso_date(summary_payload.get("date_from"))
    end = normalize_iso_date(summary_payload.get("date_to"))
    if start and end:
        if start <= end:
            return start, end
        return end, start
    if start:
        return start, start
    if end:
        return end, end

    date_label = str(summary_payload.get("date") or "").strip()
    if date_label:
        range_from_label = parse_range_label(date_label)
        if range_from_label:
            return range_from_label
        day = parse_run_day_from_label(date_label)
        if day:
            return day, day

    _, _, run_key_date_label = split_run_key(run_key)
    if run_key_date_label:
        range_from_run_key = parse_range_label(run_key_date_label)
        if range_from_run_key:
            return range_from_run_key
        day = parse_run_day_from_label(run_key_date_label)
        if day:
            return day, day

    fallback_day = day_from_timestamp(updated_at)
    if fallback_day:
        return fallback_day, fallback_day
    return None, None


def collect_run_report_ticker_ranges(
    deps: RunReportsReadDeps, *, limit: int = 2000
) -> Dict[str, Dict[str, str]]:
    store = deps.report_store
    list_fn = getattr(store, "list_run_summaries", None)
    if not callable(list_fn):
        return {}

    try:
        rows = list_fn(limit=max(1, min(int(limit), 5000)))
    except Exception:
        return {}
    if not isinstance(rows, list):
        return {}

    ticker_ranges: Dict[str, Dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue

        run_key = str(row.get("run_key") or "").strip()
        summary = row.get("summary")
        summary_payload = summary if isinstance(summary, dict) else {}

        ticker = normalize_summary_ticker(summary_payload.get("ticker"))
        if not ticker:
            _, ticker_from_run_key, _ = split_run_key(run_key)
            ticker = normalize_summary_ticker(ticker_from_run_key)
        if not ticker:
            continue

        start, end = extract_summary_date_range(
            summary_payload=summary_payload,
            run_key=run_key,
            updated_at=row.get("updated_at"),
        )
        if not start or not end:
            continue

        current = ticker_ranges.get(ticker)
        if current is None:
            ticker_ranges[ticker] = {"start": start, "end": end}
            continue
        if start < str(current.get("start") or start):
            current["start"] = start
        if end > str(current.get("end") or end):
            current["end"] = end

    return ticker_ranges


def merge_available_data_with_run_report_ranges(
    summary: Dict[str, Any], run_report_ranges: Dict[str, Dict[str, str]]
) -> Dict[str, Any]:
    if not isinstance(summary, dict):
        return summary
    if not isinstance(run_report_ranges, dict) or not run_report_ranges:
        return summary

    merged_summary = dict(summary)
    merged_tickers = {
        str(item or "").strip().upper()
        for item in list(summary.get("tickers", []))
        if str(item or "").strip()
    }

    source_date_ranges = summary.get("date_ranges")
    date_ranges: Dict[str, Dict[str, Any]] = {}
    if isinstance(source_date_ranges, dict):
        for ticker, payload in source_date_ranges.items():
            ticker_token = normalize_summary_ticker(ticker)
            if not ticker_token:
                continue
            if isinstance(payload, dict):
                date_ranges[ticker_token] = dict(payload)
            else:
                date_ranges[ticker_token] = {}

    for ticker, payload in run_report_ranges.items():
        ticker_token = normalize_summary_ticker(ticker)
        if not ticker_token:
            continue
        start = normalize_iso_date(payload.get("start") if isinstance(payload, dict) else None)
        end = normalize_iso_date(payload.get("end") if isinstance(payload, dict) else None)
        if not start or not end:
            continue
        if start > end:
            start, end = end, start

        merged_tickers.add(ticker_token)
        target = date_ranges.setdefault(ticker_token, {})
        existing_start = normalize_iso_date(target.get("start"))
        existing_end = normalize_iso_date(target.get("end"))
        if not existing_start or start < existing_start:
            target["start"] = start
        if not existing_end or end > existing_end:
            target["end"] = end
        if "files" not in target or not isinstance(target.get("files"), list):
            target["files"] = []

    merged_summary["tickers"] = sorted(merged_tickers)
    merged_summary["date_ranges"] = date_ranges
    return merged_summary


def decode_playback_snapshot(summary_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    snapshot_meta = (
        summary_payload.get("playback_snapshot", {})
        if isinstance(summary_payload.get("playback_snapshot"), dict)
        else {}
    )
    if not snapshot_meta:
        return None
    if str(snapshot_meta.get("encoding") or "").strip().lower() != "gzip+base64":
        return None
    payload_b64 = str(snapshot_meta.get("payload_b64") or "").strip()
    if not payload_b64:
        return None
    try:
        compressed = base64.b64decode(payload_b64, validate=True)
        decoded = gzip.decompress(compressed)
        payload = json.loads(decoded.decode("utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def hydrate_summary_with_persisted_config_snapshot(
    *,
    summary_payload: Dict[str, Any],
    run_key: str,
    report_store: Any,
) -> Dict[str, Any]:
    payload = dict(summary_payload) if isinstance(summary_payload, dict) else {}
    embedded_snapshot = (
        payload.get("resolved_config_snapshot", {})
        if isinstance(payload.get("resolved_config_snapshot"), dict)
        else {}
    )
    if embedded_snapshot:
        return payload
    get_snapshot = getattr(report_store, "get_run_config_snapshot", None)
    if not callable(get_snapshot):
        return payload
    snapshot_id = str(payload.get("resolved_config_snapshot_id") or "").strip() or None
    try:
        row = get_snapshot(snapshot_id=snapshot_id, run_key=run_key)
    except Exception:
        return payload
    if not isinstance(row, dict):
        return payload
    snapshot_payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    resolved_snapshot_id = str(row.get("snapshot_id") or snapshot_id or "").strip()
    return attach_resolved_config_snapshot_to_summary(
        payload,
        snapshot_id=resolved_snapshot_id,
        snapshot_payload=snapshot_payload,
    )


def redact_playback_payload(summary_payload: Dict[str, Any]) -> Dict[str, Any]:
    summary_for_client = dict(summary_payload)
    playback_meta = summary_for_client.get("playback_snapshot")
    if isinstance(playback_meta, dict) and "payload_b64" in playback_meta:
        playback_meta = dict(playback_meta)
        playback_meta.pop("payload_b64", None)
        summary_for_client["playback_snapshot"] = playback_meta
    return summary_for_client
