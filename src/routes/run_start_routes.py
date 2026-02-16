from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from src.models.run_requests import PrewarmRunRequest, StartRunRequest
from src.routes.context import ApiServices, get_api_services
from src.services.start_run_data_service import flush_start_run_data_cache

router = APIRouter()


def _request_to_dict(request: PrewarmRunRequest) -> Dict[str, Any]:
    if hasattr(request, "model_dump"):
        return dict(request.model_dump())
    return dict(request.dict())


def _preview_days(days: List[str], limit: int = 8) -> Dict[str, Any]:
    ordered = [str(day) for day in days if str(day).strip()]
    if len(ordered) <= limit:
        return {"count": len(ordered), "preview": ordered}
    return {
        "count": len(ordered),
        "preview": ordered[:limit],
        "remaining": len(ordered) - limit,
    }


def _classify_start_error(detail: str) -> str:
    text = str(detail or "").lower()
    if "no data available for the specified date/range" in text:
        return "no_ohlcv_data"
    if "no usable data files" in text:
        return "invalid_or_unreadable_data_files"
    if "no data files found" in text:
        return "missing_data_files"
    if "l2-only mode requested but missing l2 coverage" in text:
        return "missing_l2_coverage"
    if "l2-only mode requested but no l2-aligned bars found" in text:
        return "no_l2_aligned_bars"
    if "l2 confirmation requested but missing l2 coverage" in text:
        return "missing_l2_coverage"
    if "l2 confirmation requested but no l2 data was found" in text:
        return "no_l2_data"
    return "start_validation_error"


def _inclusive_day_span(start_date: str, end_date: str) -> int:
    try:
        start_dt = datetime.strptime(str(start_date), "%Y-%m-%d")
        end_dt = datetime.strptime(str(end_date), "%Y-%m-%d")
    except Exception:
        return 0
    return max(0, (end_dt - start_dt).days + 1)


def _safe_range_coverage(
    *,
    services: ApiServices,
    ticker: str,
    schema: str,
    range_start: str,
    range_end: str,
) -> Dict[str, Any]:
    try:
        payload = services.databento_svc.get_range_coverage(
            ticker=ticker,
            schema=schema,
            start_date=range_start,
            end_date=range_end,
        )
    except Exception as exc:  # pragma: no cover - defensive branch
        return {
            "schema": str(schema).lower(),
            "error": str(exc),
            "covered_days": [],
            "missing_days": [],
            "total_days": 0,
            "fully_covered": False,
        }

    covered_days = [str(day) for day in payload.get("covered_days", [])]
    missing_days = [str(day) for day in payload.get("missing_days", [])]
    return {
        **payload,
        "covered_days_meta": _preview_days(covered_days),
        "missing_days_meta": _preview_days(missing_days),
    }


@router.post("/api/run/start")
async def start_run_endpoint(
    request: StartRunRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Start a new backtest run."""
    return await services.start_run(request)


@router.post("/api/run/prewarm")
async def prewarm_run_endpoint(
    request: PrewarmRunRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Prewarm bars/L2/reference caches for the requested range."""
    return await services.prewarm_run(request)


@router.post("/api/run/prewarm/status")
async def prewarm_status_endpoint(
    request: PrewarmRunRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Check prewarm readiness/in-flight state without triggering heavy loads."""
    return await services.prewarm_status(request)


@router.post("/api/run/diagnose")
async def diagnose_run_start_endpoint(
    request: PrewarmRunRequest,
    probe_start: bool = Query(default=False),
    services: ApiServices = Depends(get_api_services),
):
    """
    Diagnose a specific run request (single day or range) before start.
    Always returns a structured payload; start validation errors are surfaced in `ok=false`.
    """
    resolved = await services.prewarm_status(request)
    ticker = str(resolved.get("ticker") or request.ticker or "").strip().upper()
    range_start = str(resolved.get("range_start") or "").strip()
    range_end = str(resolved.get("range_end") or "").strip()
    if not ticker or not range_start or not range_end:
        raise HTTPException(500, "Failed to resolve run range for diagnostics.")

    try:
        services.databento_svc.scan_existing_files()
    except Exception:
        pass

    ohlcv_coverage = _safe_range_coverage(
        services=services,
        ticker=ticker,
        schema="ohlcv-1m",
        range_start=range_start,
        range_end=range_end,
    )

    l2_schemas: List[str] = []
    try:
        entries = services.databento_svc.list_catalog(refresh=False, ticker=ticker)
    except Exception:
        entries = []
    for entry in entries:
        if str(entry.get("status", "")).lower() != "ready":
            continue
        schema = str(entry.get("schema", "")).lower().strip()
        if schema.startswith("mbp-"):
            l2_schemas.append(schema)
    l2_schemas = sorted(set(l2_schemas))
    if not l2_schemas:
        l2_schemas = ["mbp-10"]

    l2_coverage = [
        _safe_range_coverage(
            services=services,
            ticker=ticker,
            schema=schema,
            range_start=range_start,
            range_end=range_end,
        )
        for schema in l2_schemas
    ]

    def _covered_count(item: Dict[str, Any]) -> int:
        covered = item.get("covered_days", [])
        if not isinstance(covered, list):
            return 0
        return len(covered)

    best_l2_coverage = max(l2_coverage, key=_covered_count) if l2_coverage else None
    request_payload = _request_to_dict(request)
    requested_use_l2 = bool(
        resolved.get("use_l2")
        or resolved.get("l2_only")
        or resolved.get("l2_confirm_enabled")
    )
    ohlcv_ok = bool(ohlcv_coverage.get("fully_covered", False))
    l2_ok = (not requested_use_l2) or bool(
        isinstance(best_l2_coverage, dict) and best_l2_coverage.get("fully_covered", False)
    )

    def _coverage_payload() -> Dict[str, Any]:
        return {
            "ohlcv_1m": ohlcv_coverage,
            "l2_schemas": l2_coverage,
            "best_l2_schema": best_l2_coverage.get("schema") if isinstance(best_l2_coverage, dict) else None,
        }

    def _format_missing_from_meta(meta: Any) -> str:
        if not isinstance(meta, dict):
            return "unknown"
        preview = meta.get("preview")
        if not isinstance(preview, list) or not preview:
            return "none"
        remaining = int(meta.get("remaining", 0) or 0)
        if remaining > 0:
            return f"{', '.join(str(x) for x in preview)} (+{remaining} more)"
        return ", ".join(str(x) for x in preview)

    if not probe_start:
        ohlcv_probe: Dict[str, Any] | None = None
        should_probe_ohlcv = _inclusive_day_span(range_start, range_end) <= 7
        if should_probe_ohlcv:
            ohlcv_probe_payload = _request_to_dict(request)
            ohlcv_probe_payload["l2_only"] = False
            ohlcv_probe_payload["l2_confirm_enabled"] = False
            ohlcv_probe_request = PrewarmRunRequest(**ohlcv_probe_payload)
            try:
                ohlcv_probe_result = await services.prewarm_run(ohlcv_probe_request)
                ohlcv_probe = {
                    "ok": True,
                    "bars": int(ohlcv_probe_result.get("bars", 0) or 0),
                    "data_files_count": int(ohlcv_probe_result.get("data_files_count", 0) or 0),
                    "cache_hit": bool(ohlcv_probe_result.get("cache_hit", False)),
                }
            except HTTPException as exc:
                detail = str(exc.detail)
                error_kind = _classify_start_error(detail)
                ohlcv_probe = {
                    "ok": False,
                    "status_code": int(exc.status_code),
                    "error_kind": error_kind,
                    "error": detail,
                }
                if error_kind in {
                    "no_ohlcv_data",
                    "missing_data_files",
                    "invalid_or_unreadable_data_files",
                }:
                    return {
                        "ok": False,
                        "mode": "coverage_only",
                        "request": request_payload,
                        "resolved": resolved,
                        "status_code": int(exc.status_code),
                        "error_kind": error_kind,
                        "error": detail,
                        "coverage": _coverage_payload(),
                        "probe": {"ohlcv_probe": ohlcv_probe},
                    }

        if ohlcv_ok and l2_ok:
            return {
                "ok": True,
                "mode": "coverage_only",
                "request": request_payload,
                "resolved": resolved,
                "coverage": _coverage_payload(),
                "probe": {"ohlcv_probe": ohlcv_probe},
            }

        if not ohlcv_ok:
            missing = ohlcv_coverage.get("missing_days_meta", {})
            return {
                "ok": False,
                "mode": "coverage_only",
                "request": request_payload,
                "resolved": resolved,
                "status_code": 400,
                "error_kind": "no_ohlcv_data",
                "error": (
                    "No OHLCV coverage for one or more requested day(s). "
                    f"Missing: {_format_missing_from_meta(missing)}"
                ),
                "coverage": _coverage_payload(),
                "probe": {"ohlcv_probe": ohlcv_probe},
            }

        missing = best_l2_coverage.get("missing_days_meta", {}) if isinstance(best_l2_coverage, dict) else {}
        return {
            "ok": False,
            "mode": "coverage_only",
            "request": request_payload,
            "resolved": resolved,
            "status_code": 400,
            "error_kind": "missing_l2_coverage",
            "error": (
                "L2 coverage missing for one or more requested day(s) under current L2 settings."
                f" Missing: {_format_missing_from_meta(missing)}"
            ),
            "coverage": _coverage_payload(),
            "probe": {"ohlcv_probe": ohlcv_probe},
        }

    try:
        probe = await services.prewarm_run(request)
        probe_summary = {
            "bars": int(probe.get("bars", 0) or 0),
            "reference_bars": int(probe.get("reference_bars", 0) or 0),
            "data_files_count": int(probe.get("data_files_count", 0) or 0),
            "use_l2": bool(probe.get("use_l2", False)),
            "l2_only": bool(probe.get("l2_only", False)),
            "l2_confirm_enabled": bool(probe.get("l2_confirm_enabled", False)),
            "l2_guard_reason": probe.get("l2_guard_reason"),
            "l2": dict(probe.get("l2", {})),
            "cache_hit": bool(probe.get("cache_hit", False)),
        }
        return {
            "ok": True,
            "request": request_payload,
            "resolved": resolved,
            "coverage": _coverage_payload(),
            "probe": probe_summary,
        }
    except HTTPException as exc:
        detail = str(exc.detail)
        return {
            "ok": False,
            "request": request_payload,
            "resolved": resolved,
            "status_code": int(exc.status_code),
            "error_kind": _classify_start_error(detail),
            "error": detail,
            "coverage": _coverage_payload(),
        }


@router.post("/api/run/cache/flush")
async def flush_run_cache_endpoint(
    include_disk: bool = Query(default=False),
):
    """Flush cached run-start data (memory, optional disk)."""
    return flush_start_run_data_cache(include_disk=bool(include_disk))
