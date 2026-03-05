from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict


ToJsonSafe = Callable[[Any], Any]


def _json_object(value: Any, *, to_json_safe: ToJsonSafe) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized = to_json_safe(dict(value))
    return normalized if isinstance(normalized, dict) else {}


def _first_token(*values: Any) -> str | None:
    for value in values:
        token = str(value or "").strip()
        if token:
            return token
    return None


def build_resolved_config_snapshot(
    *,
    run_id: str,
    ticker: str,
    date_label: str,
    report_metadata: Dict[str, Any],
    control_plane_snapshot: Dict[str, Any],
    aos_applied: Dict[str, Any],
    execution_config: Dict[str, Any],
    run_request_config: Dict[str, Any],
    l2_applied: Dict[str, Any],
    session_config_snapshot: Dict[str, Any],
    to_json_safe: ToJsonSafe,
) -> Dict[str, Any]:
    report_meta_payload = _json_object(report_metadata, to_json_safe=to_json_safe)
    control_plane_payload = _json_object(
        control_plane_snapshot,
        to_json_safe=to_json_safe,
    )
    aos_payload = _json_object(aos_applied, to_json_safe=to_json_safe)
    execution_payload = _json_object(execution_config, to_json_safe=to_json_safe)
    request_payload = _json_object(run_request_config, to_json_safe=to_json_safe)
    l2_payload = _json_object(l2_applied, to_json_safe=to_json_safe)
    session_config_payload = _json_object(
        session_config_snapshot,
        to_json_safe=to_json_safe,
    )

    has_payload = any(
        (
            report_meta_payload,
            control_plane_payload,
            aos_payload,
            execution_payload,
            request_payload,
            l2_payload,
            session_config_payload,
        )
    )
    if not has_payload:
        return {}

    snapshot: Dict[str, Any] = {
        "schema_version": 1,
        "run_id": str(run_id or "").strip(),
        "ticker": str(ticker or "").strip().upper(),
        "date_label": str(date_label or "").strip(),
    }
    run_key = _first_token(
        (
            f"{snapshot['run_id']}:{snapshot['ticker']}:{snapshot['date_label']}"
            if snapshot["run_id"] and snapshot["ticker"] and snapshot["date_label"]
            else None
        )
    )
    if run_key:
        snapshot["run_key"] = run_key
    if report_meta_payload:
        snapshot["report_metadata"] = report_meta_payload
    if control_plane_payload:
        snapshot["control_plane_snapshot"] = control_plane_payload
    if aos_payload:
        snapshot["aos_applied"] = aos_payload
    if execution_payload:
        snapshot["execution_config"] = execution_payload
    if request_payload:
        snapshot["run_request_config"] = request_payload
    if l2_payload:
        snapshot["l2_applied"] = l2_payload
    if session_config_payload:
        snapshot["session_config_snapshot"] = session_config_payload

    config_fingerprint = _first_token(
        execution_payload.get("config_fingerprint"),
        control_plane_payload.get("config_fingerprint"),
        control_plane_payload.get("execution_config_fingerprint"),
        report_meta_payload.get("config_fingerprint"),
    )
    if config_fingerprint:
        snapshot["config_fingerprint"] = config_fingerprint

    aos_applied_fingerprint = _first_token(
        execution_payload.get("aos_applied_fingerprint"),
        control_plane_payload.get("aos_applied_fingerprint"),
        report_meta_payload.get("aos_applied_fingerprint"),
    )
    if aos_applied_fingerprint:
        snapshot["aos_applied_fingerprint"] = aos_applied_fingerprint

    return snapshot


def extract_session_config_snapshot(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    session_payload = payload.get("session_config_snapshot", {})
    if not isinstance(session_payload, dict) or not session_payload:
        return {}
    return dict(session_payload)


def resolve_session_config_snapshot(
    restart_session_config: Any = None,
    *,
    resolved_config_snapshot: Any = None,
    summary_payload: Any = None,
) -> Dict[str, Any]:
    if isinstance(restart_session_config, dict) and restart_session_config:
        return dict(restart_session_config)

    extracted = extract_session_config_snapshot(summary_payload)
    if extracted:
        return extracted

    if isinstance(summary_payload, dict):
        extracted = extract_session_config_snapshot(
            summary_payload.get("resolved_config_snapshot")
        )
        if extracted:
            return extracted

    extracted = extract_session_config_snapshot(resolved_config_snapshot)
    if extracted:
        return extracted

    return {}


def build_resolved_config_snapshot_id(
    *,
    run_key: str,
    snapshot: Dict[str, Any],
) -> str:
    serialized = json.dumps(
        {
            "run_key": str(run_key or "").strip(),
            "snapshot": snapshot if isinstance(snapshot, dict) else {},
        },
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"rcs_{digest[:24]}"


def attach_resolved_config_snapshot_to_summary(
    summary: Dict[str, Any],
    *,
    snapshot_id: Any = None,
    snapshot_payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(summary) if isinstance(summary, dict) else {}
    normalized_snapshot_id = str(snapshot_id or "").strip()
    if normalized_snapshot_id:
        payload["resolved_config_snapshot_id"] = normalized_snapshot_id
    if isinstance(snapshot_payload, dict) and snapshot_payload:
        payload["resolved_config_snapshot"] = dict(snapshot_payload)
    return payload
