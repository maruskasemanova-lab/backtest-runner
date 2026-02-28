from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException


def is_options_flow_alpha_enabled(aos_applied: Dict[str, Any]) -> bool:
    if not isinstance(aos_applied, dict):
        return False
    positioning = aos_applied.get("positioning")
    if isinstance(positioning, dict):
        return bool(positioning.get("options_flow_alpha_enabled", False))
    return bool(aos_applied.get("options_flow_alpha_enabled", False))


def resolve_tcbbo_enrichment_reasons(
    *,
    execution_cfg: Dict[str, Any],
    aos_applied: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []
    if bool(execution_cfg.get("effective_tcbbo_gate_enabled", False)):
        reasons.append("tcbbo_gate")
    if is_options_flow_alpha_enabled(aos_applied):
        reasons.append("options_flow_alpha")
    return reasons


def load_initial_bars_with_progressive_retry(
    *,
    inputs: Any,
    deps: Any,
) -> Tuple[list[Any], list[str], str, Optional[Dict[str, Any]], list[tuple[str, str]]]:
    load_range_end = str(inputs.load_range_end)
    progressive_pending_chunks = list(inputs.progressive_pending_chunks)
    progressive_plan = (
        dict(inputs.progressive_plan)
        if isinstance(inputs.progressive_plan, dict)
        else None
    )

    while True:
        try:
            bars, data_files = deps.load_run_bars(
                request=inputs.request,
                ticker=inputs.ticker,
                range_start=inputs.load_range_start,
                range_end=load_range_end,
                data_loader=deps.data_loader,
                databento_svc=deps.databento_svc,
                get_discovery=deps.get_discovery,
                aos_applied=inputs.aos_applied,
                logger=deps.logger,
            )
            return (
                list(bars),
                list(data_files),
                load_range_end,
                progressive_plan,
                progressive_pending_chunks,
            )
        except HTTPException as exc:
            detail = str(getattr(exc, "detail", ""))
            status_code = int(getattr(exc, "status_code", 0) or 0)
            no_data_window = status_code in {400, 404} and (
                "No data available for the specified date/range" in detail
                or "No data files found" in detail
            )
            if not (
                bool(progressive_plan) and no_data_window and progressive_pending_chunks
            ):
                raise
            _, next_chunk_end = progressive_pending_chunks.pop(0)
            load_range_end = str(next_chunk_end)
            if isinstance(progressive_plan, dict):
                progressive_plan["initial_end"] = load_range_end
                progressive_plan["chunks"] = list(progressive_pending_chunks)
            deps.logger.info(
                "Progressive initial range expanded for %s to %s..%s after no-data window.",
                inputs.run_key,
                inputs.load_range_start,
                load_range_end,
            )


def merge_tcbbo_stats(
    *,
    l2_stats: Dict[str, Any],
    tcbbo_stats: Any,
    tcbbo_enrichment_reasons: List[str],
) -> Dict[str, Any]:
    merged = dict(l2_stats) if isinstance(l2_stats, dict) else {}
    normalized_tcbbo_stats = dict(tcbbo_stats) if isinstance(tcbbo_stats, dict) else {}
    if normalized_tcbbo_stats:
        normalized_tcbbo_stats.setdefault("tcbbo_enrichment_required", True)
        normalized_tcbbo_stats.setdefault(
            "tcbbo_enrichment_reasons", list(tcbbo_enrichment_reasons)
        )
        merged.update(normalized_tcbbo_stats)
    return merged


__all__ = [
    "is_options_flow_alpha_enabled",
    "load_initial_bars_with_progressive_retry",
    "merge_tcbbo_stats",
    "resolve_tcbbo_enrichment_reasons",
]

