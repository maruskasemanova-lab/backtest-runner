from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.services.run_config_snapshot_service import build_resolved_config_snapshot


NormalizeSelectionWarnings = Callable[[Any], List[str]]
MergeSelectionWarnings = Callable[..., List[str]]
ApplyStrategyResetMetadata = Callable[[Dict[str, Any]], None]
ToJsonSafe = Callable[[Any], Any]
NormalizeProfileToken = Callable[[Any], str]


@dataclass(frozen=True)
class SessionEndUpdate:
    session_summary: Dict[str, Any]
    selection_warnings: List[str]
    marker_key: str


def calculate_progress_pct(current_bar_index: int, total_bars: int) -> float:
    if total_bars <= 0:
        return 0.0
    return (current_bar_index / total_bars) * 100.0


def build_data_loading_payload(
    *,
    complete: bool,
    loaded_until: Optional[str],
    target_end: Optional[str],
    pending_chunks: int,
    last_error: Optional[str],
) -> Dict[str, Any]:
    return {
        "enabled": True,
        "complete": bool(complete),
        "loaded_until": loaded_until,
        "target_end": target_end,
        "pending_chunks": int(pending_chunks),
        "last_error": last_error,
    }


def resolve_session_end_update(
    *,
    session_summary_payload: Dict[str, Any],
    selection_warnings: List[str],
    timestamp: Any,
    normalize_selection_warnings: NormalizeSelectionWarnings,
) -> SessionEndUpdate:
    resolved_summary = dict(session_summary_payload)
    summary_warnings = normalize_selection_warnings(
        resolved_summary.get("selection_warnings")
    )
    if summary_warnings:
        next_selection_warnings = list(summary_warnings)
    else:
        next_selection_warnings = list(selection_warnings)
        if next_selection_warnings:
            resolved_summary["selection_warnings"] = list(next_selection_warnings)

    if isinstance(timestamp, datetime):
        timestamp_token = timestamp.date().isoformat()
    else:
        timestamp_token = str(timestamp)
    marker_key = str(resolved_summary.get("date") or timestamp_token)

    return SessionEndUpdate(
        session_summary=resolved_summary,
        selection_warnings=next_selection_warnings,
        marker_key=marker_key,
    )


def build_runner_state_payload(
    *,
    run_id: str,
    ticker: str,
    date: str,
    date_from: Optional[str],
    date_to: Optional[str],
    current_bar_index: int,
    total_bars: int,
    phase: str,
    execution_lifecycle: str,
    is_running: bool,
    is_paused: bool,
    markers_count: int,
    selection_warnings: List[str],
    l2_applied: Dict[str, Any],
    progressive_loading_enabled: bool,
    progressive_loading_complete: bool,
    progressive_loading_loaded_until: Optional[str],
    progressive_loading_target_end: Optional[str],
    progressive_loading_pending_chunks: int,
    progressive_loading_last_error: Optional[str],
    apply_strategy_reset_metadata: ApplyStrategyResetMetadata,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "ticker": ticker,
        "date": date,
        "date_from": date_from,
        "date_to": date_to,
        "current_bar_index": current_bar_index,
        "total_bars": total_bars,
        "progress_pct": calculate_progress_pct(current_bar_index, total_bars),
        "phase": phase,
        "execution_lifecycle": execution_lifecycle,
        "is_running": is_running,
        "is_paused": is_paused,
        "markers_count": markers_count,
        "selection_warnings": selection_warnings,
    }
    if l2_applied:
        payload["l2_applied"] = dict(l2_applied)
    apply_strategy_reset_metadata(payload)
    if progressive_loading_enabled:
        payload["data_loading"] = build_data_loading_payload(
            complete=progressive_loading_complete,
            loaded_until=progressive_loading_loaded_until,
            target_end=progressive_loading_target_end,
            pending_chunks=progressive_loading_pending_chunks,
            last_error=progressive_loading_last_error,
        )
    return payload


def apply_report_metadata_payload(
    payload: Dict[str, Any],
    *,
    report_metadata: Dict[str, Any],
    normalize_profile_token: NormalizeProfileToken,
) -> None:
    if not report_metadata:
        return
    payload["report_metadata"] = dict(report_metadata)
    report_profile_fields = {
        "unified_profile_id": normalize_profile_token(
            report_metadata.get("unified_profile_id")
        ),
        "unified_profile_name": normalize_profile_token(
            report_metadata.get("unified_profile_name")
        ),
        "adaptive_profile_id": normalize_profile_token(
            report_metadata.get("adaptive_profile_id")
        ),
        "adaptive_profile_name": normalize_profile_token(
            report_metadata.get("adaptive_profile_name")
        ),
        "strategy_combo_profile_id": normalize_profile_token(
            report_metadata.get("strategy_combo_profile_id")
        ),
        "strategy_combo_profile_name": normalize_profile_token(
            report_metadata.get("strategy_combo_profile_name")
        ),
    }
    for field, token in report_profile_fields.items():
        if token:
            payload[field] = token


def build_summary_payload(
    *,
    run_id: str,
    ticker: str,
    date: str,
    total_bars: int,
    processed_bars: int,
    phase: str,
    markers: List[Dict[str, Any]],
    session_summary: Optional[Dict[str, Any]],
    report_metadata: Dict[str, Any],
    control_plane_snapshot: Dict[str, Any],
    aos_applied: Dict[str, Any],
    execution_config: Dict[str, Any],
    run_request_config: Dict[str, Any],
    l2_applied: Dict[str, Any],
    session_config_snapshot: Dict[str, Any],
    checkpoint_loaded: Any,
    to_json_safe: ToJsonSafe,
    normalize_profile_token: NormalizeProfileToken,
    apply_strategy_reset_metadata: ApplyStrategyResetMetadata,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "ticker": ticker,
        "date": date,
        "total_bars": total_bars,
        "processed_bars": processed_bars,
        "phase": phase,
        "markers": markers,
        "session_summary": session_summary,
    }
    apply_report_metadata_payload(
        payload,
        report_metadata=report_metadata,
        normalize_profile_token=normalize_profile_token,
    )
    if control_plane_snapshot:
        payload["control_plane_snapshot"] = to_json_safe(dict(control_plane_snapshot))
    if aos_applied:
        payload["aos_applied"] = dict(aos_applied)
    if execution_config:
        payload["execution_config"] = dict(execution_config)
    if run_request_config:
        payload["run_request_config"] = to_json_safe(dict(run_request_config))
    if l2_applied:
        payload["l2_applied"] = dict(l2_applied)
    resolved_config_snapshot = build_resolved_config_snapshot(
        run_id=run_id,
        ticker=ticker,
        date_label=date,
        report_metadata=report_metadata,
        control_plane_snapshot=control_plane_snapshot,
        aos_applied=aos_applied,
        execution_config=execution_config,
        run_request_config=run_request_config,
        l2_applied=l2_applied,
        session_config_snapshot=session_config_snapshot,
        to_json_safe=to_json_safe,
    )
    if resolved_config_snapshot:
        payload["resolved_config_snapshot"] = resolved_config_snapshot
    apply_strategy_reset_metadata(payload)
    if checkpoint_loaded is not None:
        payload["checkpoint_loaded"] = to_json_safe(checkpoint_loaded)
    return payload


def _resolve_summary_selection_warnings(
    *,
    base_summary: Dict[str, Any],
    data_selection_warnings: List[str],
    merged_selection_warnings: List[str],
    normalize_selection_warnings: NormalizeSelectionWarnings,
    merge_selection_warnings: MergeSelectionWarnings,
) -> List[str]:
    selection_warnings = normalize_selection_warnings(
        base_summary.get("selection_warnings")
    )
    if not selection_warnings:
        return merged_selection_warnings
    if data_selection_warnings:
        return merge_selection_warnings(data_selection_warnings, selection_warnings)
    return selection_warnings


def _resolve_vwap_diag_bucket(
    entry_timing_breakdown: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    by_strategy = (
        entry_timing_breakdown.get("first_bar_stop_by_strategy")
        if isinstance(entry_timing_breakdown.get("first_bar_stop_by_strategy"), dict)
        else {}
    )
    bucket = (
        by_strategy.get("vwap_magnet")
        or by_strategy.get("vwapmagnet")
        or by_strategy.get("vwap magnet")
    )
    return dict(bucket) if isinstance(bucket, dict) else None


def build_session_summary_payload(
    *,
    base_summary: Dict[str, Any],
    overall: Dict[str, Any],
    trades: Sequence[Any],
    run_id: str,
    ticker: str,
    date: str,
    current_bar_index: int,
    account_size_usd_default: float,
    merged_selection_warnings: List[str],
    data_selection_warnings: List[str],
    last_response: Optional[Dict[str, Any]],
    normalize_selection_warnings: NormalizeSelectionWarnings,
    merge_selection_warnings: MergeSelectionWarnings,
    apply_strategy_reset_metadata: ApplyStrategyResetMetadata,
) -> Optional[Dict[str, Any]]:
    total_trades = int(overall.get("total_trades", 0) or 0)
    if total_trades <= 0:
        if not base_summary:
            return None
        base_summary.setdefault("run_id", run_id)
        base_summary.setdefault("ticker", ticker)
        base_summary.setdefault("date", date)
        base_summary["bars_processed"] = current_bar_index
        existing_warnings = normalize_selection_warnings(
            base_summary.get("selection_warnings")
        )
        if existing_warnings:
            base_summary["selection_warnings"] = merge_selection_warnings(
                data_selection_warnings,
                existing_warnings,
            )
        else:
            base_summary["selection_warnings"] = merged_selection_warnings
        apply_strategy_reset_metadata(base_summary)
        return base_summary

    pnl_pct_values = [float(trade.pnl_pct) for trade in trades]
    pnl_dollar_values = [float(trade.pnl_dollars) for trade in trades]
    total_pnl_dollars = float(overall.get("total_pnl_dollars", 0.0) or 0.0)
    total_costs = float(overall.get("total_costs", 0.0) or 0.0)
    account_size_usd = float(
        base_summary.get("account_size_usd", account_size_usd_default) or 0.0
    )
    if account_size_usd > 0:
        total_pnl_pct = (total_pnl_dollars / account_size_usd) * 100.0
    else:
        total_pnl_pct = float(overall.get("total_pnl_pct", 0.0) or 0.0)

    gross_wins = sum(value for value in pnl_dollar_values if value > 0)
    gross_losses = abs(sum(value for value in pnl_dollar_values if value <= 0))
    profit_factor_dollars = (
        (gross_wins / gross_losses) if gross_losses > 0 else float("inf")
    )

    running = 0.0
    peak = 0.0
    max_drawdown_dollars = 0.0
    for pnl in pnl_dollar_values:
        running += pnl
        peak = max(peak, running)
        max_drawdown_dollars = max(max_drawdown_dollars, peak - running)

    selection_warnings = _resolve_summary_selection_warnings(
        base_summary=base_summary,
        data_selection_warnings=data_selection_warnings,
        merged_selection_warnings=merged_selection_warnings,
        normalize_selection_warnings=normalize_selection_warnings,
        merge_selection_warnings=merge_selection_warnings,
    )
    entry_timing_breakdown = (
        dict(overall.get("entry_timing_breakdown"))
        if isinstance(overall.get("entry_timing_breakdown"), dict)
        else {}
    )
    vwap_diag_bucket = _resolve_vwap_diag_bucket(entry_timing_breakdown)

    payload = {
        "ticker": ticker,
        "date": date,
        "run_id": run_id,
        "regime": base_summary.get("regime") or (last_response or {}).get("regime"),
        "micro_regime": base_summary.get("micro_regime")
        or (last_response or {}).get("micro_regime"),
        "strategy": base_summary.get("strategy") or (last_response or {}).get("strategy"),
        "total_trades": total_trades,
        "winning_trades": int(overall.get("winning_trades", 0) or 0),
        "losing_trades": int(overall.get("losing_trades", 0) or 0),
        "win_rate": float(overall.get("win_rate", 0.0) or 0.0),
        "trades": [trade.to_dict() for trade in trades],
        "total_pnl_pct": round(total_pnl_pct, 4),
        "avg_pnl_pct": round(total_pnl_pct / total_trades, 4),
        "total_pnl_dollars": round(total_pnl_dollars, 4),
        "avg_pnl_dollars": round(total_pnl_dollars / total_trades, 4),
        "total_costs": round(total_costs, 4),
        "best_trade": round(max(pnl_pct_values), 4),
        "worst_trade": round(min(pnl_pct_values), 4),
        "profit_factor_dollars": (
            "inf"
            if profit_factor_dollars == float("inf")
            else round(profit_factor_dollars, 4)
        ),
        "max_drawdown_dollars": round(max_drawdown_dollars, 4),
        "bars_processed": current_bar_index,
        "pre_market_bars": base_summary.get("pre_market_bars", 0),
        "selection_warnings": selection_warnings,
        "regime_history": list(base_summary.get("regime_history", [])),
        "entry_timing_diagnostics": entry_timing_breakdown,
        "success": total_pnl_dollars > 0.0,
    }
    if vwap_diag_bucket is not None:
        payload["vwap_magnet_entry_timing_diagnostics"] = dict(vwap_diag_bucket)
    apply_strategy_reset_metadata(payload)
    return payload
