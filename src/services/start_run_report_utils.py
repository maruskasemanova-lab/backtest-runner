from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

_PROFILE_PLACEHOLDER_TOKENS = {"none", "null", "n/a", "na", "undefined", "-"}


def normalize_profile_ref_token(value: Any) -> Optional[str]:
    token = str(value).strip() if value is not None else ""
    if not token:
        return None
    if token.lower() in _PROFILE_PLACEHOLDER_TOKENS:
        return None
    return token


def first_profile_ref_token(*values: Any) -> Optional[str]:
    for value in values:
        token = normalize_profile_ref_token(value)
        if token:
            return token
    return None


def extract_effective_profile_metadata(
    *,
    aos_applied: Dict[str, Any],
    execution_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    execution_payload = execution_config if isinstance(execution_config, dict) else {}
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
    return {
        "unified_profile_id": first_profile_ref_token(
            execution_payload.get("unified_profile_id"),
            execution_payload.get("active_unified_profile_id"),
            unified_meta.get("active_profile_id"),
            unified_meta.get("profile_id"),
        ),
        "unified_profile_name": first_profile_ref_token(
            execution_payload.get("unified_profile_name"),
            unified_meta.get("profile_name"),
        ),
        "adaptive_profile_id": first_profile_ref_token(
            execution_payload.get("adaptive_profile_id"),
            execution_payload.get("active_adaptive_tuner_profile_id"),
            adaptive_meta.get("active_profile_id"),
            adaptive_meta.get("profile_id"),
        ),
        "adaptive_profile_name": first_profile_ref_token(
            execution_payload.get("adaptive_profile_name"),
            adaptive_meta.get("profile_name"),
        ),
        "strategy_combo_profile_id": first_profile_ref_token(
            execution_payload.get("strategy_combo_profile_id"),
            execution_payload.get("active_strategy_combo_profile_id"),
            strategy_combo_meta.get("active_profile_id"),
            strategy_combo_meta.get("profile_id"),
        ),
        "strategy_combo_profile_name": first_profile_ref_token(
            execution_payload.get("strategy_combo_profile_name"),
            strategy_combo_meta.get("profile_name"),
        ),
    }


def summarize_days_preview(days: Any, limit: int = 3) -> str:
    if not isinstance(days, list):
        return ""
    normalized = [str(day).strip() for day in days if str(day or "").strip()]
    if not normalized:
        return ""
    if len(normalized) <= limit:
        return ", ".join(normalized)
    return f"{', '.join(normalized[:limit])}, ..."


def build_data_availability_warnings(
    *,
    execution_config: Dict[str, Any],
    l2_applied: Dict[str, Any],
) -> List[str]:
    warnings: List[str] = []

    l2_required = bool(
        l2_applied.get("effective_l2_confirm_enabled", False)
        or l2_applied.get("l2_requested", False)
    )
    missing_l2_days = (
        list(l2_applied.get("missing_l2_days", []))
        if isinstance(l2_applied.get("missing_l2_days"), list)
        else []
    )
    missing_l2_days_count = int(
        l2_applied.get("missing_l2_days_count", len(missing_l2_days)) or 0
    )
    has_l2 = bool(l2_applied.get("has_l2", False))
    if l2_required and (missing_l2_days_count > 0 or not has_l2):
        if missing_l2_days_count > 0:
            preview = summarize_days_preview(missing_l2_days)
            suffix = f" ({preview})" if preview else ""
            warnings.append(
                f"[Data] L2 coverage missing for {missing_l2_days_count} day(s){suffix}."
            )
        elif not has_l2:
            warnings.append("[Data] L2 requested, but no L2 data was loaded for this run.")

    tcbbo_enabled = bool(
        l2_applied.get("tcbbo_gate_enabled", execution_config.get("tcbbo_gate_enabled"))
    )
    tcbbo_required_by = (
        list(l2_applied.get("tcbbo_feature_required_by", []))
        if isinstance(l2_applied.get("tcbbo_feature_required_by"), list)
        else []
    )
    tcbbo_feature_required = bool(
        l2_applied.get("tcbbo_feature_required", tcbbo_enabled)
    )
    tcbbo_available = bool(l2_applied.get("tcbbo_available", False))
    if tcbbo_feature_required and not tcbbo_available:
        reason = str(l2_applied.get("tcbbo_missing_reason") or "").strip()
        reason_map = {
            "tcbbo_file_not_found": "TCBBO parquet file not found",
            "tcbbo_build_failed": "TCBBO parse/build failed",
            "tcbbo_no_feature_rows": "TCBBO file loaded but produced no minute features",
            "tcbbo_no_bar_overlap": "TCBBO data does not overlap loaded bars",
        }
        reason_text = reason_map.get(reason, "TCBBO data unavailable")
        files_found = int(l2_applied.get("tcbbo_files_found", 0) or 0)
        roots = (
            list(l2_applied.get("tcbbo_search_roots", []))
            if isinstance(l2_applied.get("tcbbo_search_roots"), list)
            else []
        )
        roots_preview = ", ".join(str(r) for r in roots[:2]) if roots else ""
        extra = []
        if files_found:
            extra.append(f"files_found={files_found}")
        if roots_preview:
            extra.append(f"search_roots={roots_preview}")
        extra_suffix = f" ({'; '.join(extra)})" if extra else ""
        message = f"[Data] {reason_text}.{extra_suffix}"
        if "options_flow_alpha" in tcbbo_required_by and not tcbbo_enabled:
            message += " OptionsFlowAlpha is enabled, but it will run without TCBBO flow inputs."
        elif "options_flow_alpha" in tcbbo_required_by and tcbbo_enabled:
            message += " OptionsFlowAlpha and TCBBO gate are both enabled."
        warnings.append(message)

    deduped: List[str] = []
    seen = set()
    for item in warnings:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def build_report_metadata(
    *,
    run_key: str,
    run_date_label: str,
    aos_applied: Dict[str, Any],
    execution_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    profile_meta = extract_effective_profile_metadata(
        aos_applied=aos_applied,
        execution_config=execution_config,
    )
    execution_payload = execution_config if isinstance(execution_config, dict) else {}
    control_plane_snapshot = (
        execution_payload.get("control_plane_snapshot", {})
        if isinstance(execution_payload.get("control_plane_snapshot"), dict)
        else {}
    )
    return {
        "run_key": str(run_key),
        "run_date_label": str(run_date_label),
        "config_fingerprint": first_profile_ref_token(
            execution_payload.get("config_fingerprint"),
            control_plane_snapshot.get("config_fingerprint"),
            control_plane_snapshot.get("execution_config_fingerprint"),
        ),
        "aos_applied_fingerprint": first_profile_ref_token(
            execution_payload.get("aos_applied_fingerprint"),
            control_plane_snapshot.get("aos_applied_fingerprint"),
        ),
        "unified_profile_id": profile_meta.get("unified_profile_id"),
        "unified_profile_name": profile_meta.get("unified_profile_name"),
        "adaptive_profile_id": profile_meta.get("adaptive_profile_id"),
        "adaptive_profile_name": profile_meta.get("adaptive_profile_name"),
        "strategy_combo_profile_id": profile_meta.get("strategy_combo_profile_id"),
        "strategy_combo_profile_name": profile_meta.get("strategy_combo_profile_name"),
    }


def build_run_request_config_snapshot(request: Any) -> Dict[str, Any]:
    payload: Dict[str, Any]
    try:
        payload = request.dict()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        return {}
    try:
        return json.loads(json.dumps(payload, default=str))
    except Exception:
        return payload
