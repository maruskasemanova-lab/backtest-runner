from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Dict, Optional

from fastapi import HTTPException
from src.services.start_run_time_window_service import (
    filter_bars_for_requested_time_window,
)


@dataclass(frozen=True)
class LoadPhaseInputs:
    request: Any
    ticker: str
    run_key: str
    range_start: str
    range_end: str
    load_range_start: str
    load_range_end: str
    comparable_mode: bool
    aos_applied: Dict[str, Any]
    execution_cfg: Dict[str, Any]
    progressive_plan: Optional[Dict[str, Any]]
    progressive_pending_chunks: list[tuple[str, str]]


@dataclass(frozen=True)
class LoadPhaseDeps:
    logger: Any
    data_loader: Any
    databento_svc: Any
    get_discovery: Callable[[], Any]
    load_run_bars: Callable[..., Any]
    enrich_bars_with_l2: Callable[..., Any]
    to_utc_datetime: Callable[[Any], Any]
    build_l2_feature_map: Callable[..., Any]
    normalize_l2_feature_map_for_market_day_sessions: Callable[..., Dict[str, Any]]
    attach_l2_features: Callable[..., Any]
    run_l2_guard_reason: Callable[..., Optional[str]]


@dataclass(frozen=True)
class LoadPhaseResult:
    bars: list[Any]
    data_files: list[str]
    l2_stats: Dict[str, Any]
    l2_sessionized_by_market_day: bool
    requested_l2_only_raw: bool
    requested_l2_confirm_raw: bool
    requested_l2_only: bool
    requested_l2_confirm: bool
    l2_guard_reason: Optional[str]
    use_l2: bool
    load_range_end: str
    progressive_plan: Optional[Dict[str, Any]]


def _is_options_flow_alpha_enabled(aos_applied: Dict[str, Any]) -> bool:
    if not isinstance(aos_applied, dict):
        return False
    positioning = aos_applied.get("positioning")
    if isinstance(positioning, dict):
        return bool(positioning.get("options_flow_alpha_enabled", False))
    return bool(aos_applied.get("options_flow_alpha_enabled", False))


def _resolve_tcbbo_enrichment_reasons(
    *,
    execution_cfg: Dict[str, Any],
    aos_applied: Dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    print(f"DEBUG: execution_cfg effective_tcbbo_gate_enabled={execution_cfg.get('effective_tcbbo_gate_enabled')}")
    if bool(execution_cfg.get("effective_tcbbo_gate_enabled", False)):
        reasons.append("tcbbo_gate")
    
    alpha_enabled = _is_options_flow_alpha_enabled(aos_applied)
    print(f"DEBUG: is_options_flow_alpha_enabled={alpha_enabled}")
    if alpha_enabled:
        reasons.append("options_flow_alpha")
    
    print(f"DEBUG: tcbbo_enrichment_reasons={reasons}")
    return reasons


async def run_start_load_phase(
    *,
    inputs: LoadPhaseInputs,
    deps: LoadPhaseDeps,
    record_phase_ms: Callable[[str, float], None],
) -> LoadPhaseResult:
    request = inputs.request
    ticker = inputs.ticker

    load_range_end = str(inputs.load_range_end)
    progressive_pending_chunks = list(inputs.progressive_pending_chunks)
    progressive_plan = (
        dict(inputs.progressive_plan)
        if isinstance(inputs.progressive_plan, dict)
        else None
    )

    phase_started = perf_counter()
    while True:
        try:
            bars, data_files = deps.load_run_bars(
                request=request,
                ticker=ticker,
                range_start=inputs.load_range_start,
                range_end=load_range_end,
                data_loader=deps.data_loader,
                databento_svc=deps.databento_svc,
                get_discovery=deps.get_discovery,
                aos_applied=inputs.aos_applied,
                logger=deps.logger,
            )
            break
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
    record_phase_ms("load_run_bars", phase_started)

    requested_l2_only_raw = bool(inputs.execution_cfg["requested_l2_only"])
    requested_l2_confirm_raw = bool(inputs.execution_cfg["requested_l2_confirm"])
    requested_l2_only = requested_l2_only_raw
    requested_l2_confirm = requested_l2_confirm_raw

    l2_guard_reason = deps.run_l2_guard_reason(
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        range_start=inputs.range_start,
        range_end=inputs.range_end,
    )
    if l2_guard_reason:
        deps.logger.warning(
            "%s run_id=%s ticker=%s range=%s..%s",
            l2_guard_reason,
            request.run_id,
            ticker,
            inputs.range_start,
            inputs.range_end,
        )
        raise HTTPException(400, l2_guard_reason)

    use_l2 = bool(requested_l2_only or requested_l2_confirm)

    phase_started = perf_counter()
    bars, l2_stats, l2_sessionized_by_market_day = deps.enrich_bars_with_l2(
        bars=bars,
        ticker=ticker,
        range_start=inputs.load_range_start,
        range_end=load_range_end,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        comparable_mode=inputs.comparable_mode,
        is_multi_day_request=bool(
            inputs.load_range_start != load_range_end
            or bool(request.date_from and request.date_to)
        ),
        aos_l2_config_applied=bool(
            isinstance(inputs.aos_applied.get("l2"), dict)
            and inputs.aos_applied.get("l2")
        ),
        to_utc_datetime=deps.to_utc_datetime,
        build_l2_feature_map=deps.build_l2_feature_map,
        normalize_l2_feature_map_for_market_day_sessions=(
            deps.normalize_l2_feature_map_for_market_day_sessions
        ),
        attach_l2_features=deps.attach_l2_features,
        logger=deps.logger,
    )
    record_phase_ms("enrich_bars_with_l2", phase_started)

    # TCBBO options flow enrichment (optional, non-blocking)
    tcbbo_stats: Dict[str, Any] = {}
    tcbbo_enrichment_reasons = _resolve_tcbbo_enrichment_reasons(
        execution_cfg=inputs.execution_cfg,
        aos_applied=inputs.aos_applied,
    )
    if tcbbo_enrichment_reasons:
        from src.services.start_run_data_service import enrich_bars_with_tcbbo

        phase_started = perf_counter()
        bars, tcbbo_stats = enrich_bars_with_tcbbo(
            bars=bars,
            ticker=ticker,
            range_start=inputs.load_range_start,
            range_end=load_range_end,
            logger=deps.logger,
        )
        record_phase_ms("enrich_bars_with_tcbbo", phase_started)
        if not isinstance(tcbbo_stats, dict):
            tcbbo_stats = {}
        tcbbo_stats.setdefault("tcbbo_enrichment_required", True)
        tcbbo_stats.setdefault(
            "tcbbo_enrichment_reasons", list(tcbbo_enrichment_reasons)
        )
    if tcbbo_stats:
        l2_stats.update(tcbbo_stats)

    bars = filter_bars_for_requested_time_window(
        bars=bars,
        request=request,
        to_utc_datetime=deps.to_utc_datetime,
    )

    return LoadPhaseResult(
        bars=list(bars),
        data_files=list(data_files),
        l2_stats=dict(l2_stats) if isinstance(l2_stats, dict) else {},
        l2_sessionized_by_market_day=bool(l2_sessionized_by_market_day),
        requested_l2_only_raw=requested_l2_only_raw,
        requested_l2_confirm_raw=requested_l2_confirm_raw,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        l2_guard_reason=l2_guard_reason,
        use_l2=use_l2,
        load_range_end=load_range_end,
        progressive_plan=progressive_plan,
    )
