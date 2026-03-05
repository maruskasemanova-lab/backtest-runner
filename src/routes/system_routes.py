import re
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from src.routes.context import ApiServices, get_api_services
from src.runtime_mode import is_serverless_environment, stateful_run_api_supported
from src.services.run_reports_read import (
    RunReportsReadDeps,
    build_run_playback_snapshot_response,
    build_saved_run_history_response,
    collect_run_report_ticker_ranges,
    merge_available_data_with_run_report_ranges,
)

router = APIRouter()
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SAFE_RUN_KEY_RE = re.compile(r"^[A-Za-z0-9:_-]+$")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_reports_store(request: Request):
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    return getattr(state, "run_reports_store", None)


def _active_runners(request: Request) -> Dict[str, Any]:
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    services = getattr(state, "api_services", None) if state is not None else None
    active = getattr(services, "active_runners", None) if services is not None else None
    return active if isinstance(active, dict) else {}


def _run_reports_source_mode(request: Request) -> str:
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    explicit = str(getattr(state, "run_reports_source_mode", "") or "").strip()
    if explicit:
        return explicit
    return "run_reports_store"


def _build_run_reports_read_deps(request: Request) -> RunReportsReadDeps:
    return RunReportsReadDeps(
        project_root=_project_root(),
        report_store=_run_reports_store(request),
        active_runners=_active_runners(request),
        source_mode=_run_reports_source_mode(request),
    )


def _sanitize_segment(value: str, *, field: str) -> str:
    token = str(value or "").strip()
    if not token or not _SAFE_SEGMENT_RE.fullmatch(token):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field}. Allowed characters: letters, numbers, '_' and '-'.",
        )
    return token


def _sanitize_run_key(value: str) -> str:
    token = str(value or "").strip()
    if not token or len(token) > 512 or not _SAFE_RUN_KEY_RE.fullmatch(token):
        raise HTTPException(
            status_code=400,
            detail="Invalid run_key. Allowed characters: letters, numbers, ':', '_' and '-'.",
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
    request: Request,
    refresh: bool = Query(default=False),
    include_run_report_ranges: bool = Query(default=True),
    services: ApiServices = Depends(get_api_services),
):
    try:
        summary = services.databento_svc.get_available_data_summary(refresh=bool(refresh))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    deps = _build_run_reports_read_deps(request)
    run_report_ranges = (
        collect_run_report_ticker_ranges(deps)
        if bool(include_run_report_ranges)
        else {}
    )
    return merge_available_data_with_run_report_ranges(summary, run_report_ranges)


@router.get("/api/data/files")
async def list_data_files(services: ApiServices = Depends(get_api_services)):
    return services.data_loader.list_available_files()


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
    return build_saved_run_history_response(
        deps=_build_run_reports_read_deps(request),
        ticker=_sanitize_segment(ticker, field="ticker").upper(),
        limit=limit,
        run_id=run_id,
        run_id_contains=run_id_contains,
        unified_profile_id=unified_profile_id,
        adaptive_profile_id=adaptive_profile_id,
        include_multi_day=bool(include_multi_day),
        include_zero_trade_runs=bool(include_zero_trade_runs),
    )


@router.get("/api/reports/run-snapshot")
async def get_run_playback_snapshot(
    request: Request,
    run_key: str = Query(..., min_length=3, max_length=512),
) -> Dict[str, Any]:
    return build_run_playback_snapshot_response(
        deps=_build_run_reports_read_deps(request),
        run_key=_sanitize_run_key(run_key),
    )
