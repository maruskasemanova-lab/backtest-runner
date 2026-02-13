"""
Unified Backtest Runner API Server.
Orchestrates the look-ahead free data feeding and strategy evaluation.
"""
import asyncio
import copy
import json
import os
import random
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from zoneinfo import ZoneInfo
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import logging
from pathlib import Path
from uuid import uuid4
import pandas as pd

from data_loader import DataLoader
from session_runner import SessionRunner, RunConfig
from decision_tracker import MarkerType
from available_data import get_discovery, reset_discovery
from src.config_io import (
    load_json_file,
    save_json_file,
)
from src.l2_data_manager import L2DataManager
from src.l2_feature_service import L2FeatureService
from src.databento_service import DatabentoService
from src.time_utils import to_utc_datetime, epoch_minute_key, format_iso_utc
from src.l2_schema import L2_PAYLOAD_KEYS, get_default_l2_feature_bucket
from src.momentum_diversification import (
    normalize_momentum_diversification_payload,
    build_regime_strategy_map_options,
    MICRO_REGIMES,
    ROUTE_KEYS,
    STRATEGY_FAMILY_MAP,
)
from src.normalization import (
    normalize_strategy_selection_mode,
    normalize_clamped_int,
    normalize_strategy_sets,
    normalize_regime_filter_sets,
    sanitize_strategy_params,
    normalize_strategy_combo_profiles,
    normalize_tuner_profiles,
    normalize_time_window_sets,
)
from src.aos_config import (
    load_aos_config,
    save_aos_config,
    load_positioning_config,
    save_positioning_config,
    get_ticker_positioning_config,
    POSITIONING_CONFIG_KEYS,
)
from src.tuner_scoring import (
    compute_tuner_score,
    compute_tuner_score_robust,
)
from src.routes.context import ApiServices
from src.routes.system_routes import router as system_router
from src.routes.l2_routes import router as l2_router
from src.routes.data_loader_routes import router as data_loader_router
from src.routes.live_trader_routes import router as live_trader_router
from src.routes.config_read_routes import router as config_read_router
from src.routes.config_write_routes import router as config_write_router
from src.routes.run_routes import router as run_router
from src.routes.adaptive_tuner_routes import router as adaptive_tuner_router
from src.routes.run_start_routes import router as run_start_router
from src.models.config_requests import (
    AdaptiveTunerProfileApplyRequest,
    StrategyComboCaptureRequest,
    StrategyComboApplyRequest,
    AOSUpdateRequest,
    PositioningUpdateRequest,
)
from src.models.run_requests import PlayRequest, PrewarmRunRequest, StartRunRequest
from src.models.tuner_requests import AdaptiveTunerRequest
from src.services.live_trader_service import (
    sanitize_live_run_id,
    live_artifact_file,
    read_jsonl_tail,
    parse_utc_iso,
    extract_runtime_summary,
    infer_live_run_status,
    discover_live_trader_runs,
    live_trader_events_payload,
    live_trader_snapshot_payload,
)
from src.services.run_registry import RunRegistry
from src.services.config_write_service import (
    ConfigWriteDeps,
    capture_strategy_combo as service_capture_strategy_combo,
    apply_strategy_combo as service_apply_strategy_combo,
    update_aos_config as service_update_aos_config,
    update_positioning_config as service_update_positioning_config,
    apply_adaptive_tuner_profile as service_apply_adaptive_tuner_profile,
)
from src.services.run_control_service import (
    RunControlDeps,
    get_run_state as service_get_run_state,
    step_run as service_step_run,
    play_run as service_play_run,
    pause_run as service_pause_run,
    resume_run as service_resume_run,
    stop_run as service_stop_run,
    restart_run as service_restart_run,
    get_processed_bars as service_get_processed_bars,
    get_bar_details as service_get_bar_details,
    get_markers as service_get_markers,
    get_chart_annotations as service_get_chart_annotations,
    get_run_summary as service_get_run_summary,
    delete_run as service_delete_run,
    list_runs as service_list_runs,
)
from src.services.adaptive_tuner_orchestration_service import (
    AdaptiveTunerOrchestrationDeps,
    get_adaptive_tuner_job as service_get_adaptive_tuner_job,
    list_adaptive_tuner_jobs as service_list_adaptive_tuner_jobs,
    run_adaptive_tuner as service_run_adaptive_tuner,
)
from src.services.start_run_service import (
    StartRunDeps,
    get_prewarm_status as service_prewarm_status,
    prewarm_run_data as service_prewarm_run,
    start_run as service_start_run,
)
from src.services.adaptive_tuner_worker_service import (
    AdaptiveTunerWorkerDeps,
    run_adaptive_tuner_job as service_run_adaptive_tuner_job,
    run_v2_adaptive_tuner_job as service_run_v2_adaptive_tuner_job,
)
from src.services.adaptive_tuner_runtime_service import (
    AdaptiveTunerRuntimeDeps,
    evaluate_adaptive_tuner_candidate as service_evaluate_adaptive_tuner_candidate,
    evaluate_v2_candidate as service_evaluate_v2_candidate,
    persist_tuner_result_to_primary_aos as service_persist_tuner_result_to_primary_aos,
)
from src.services.adaptive_tuner_v2_service import (
    AdaptiveTunerV2Deps,
    analyze_vectors as service_analyze_vectors,
    build_v2_baseline_candidate as service_build_v2_baseline_candidate,
    build_v2_candidate_config as service_build_v2_candidate_config,
    build_v2_random_candidates as service_build_v2_random_candidates,
    build_v2_search_space as service_build_v2_search_space,
    v2_candidate_key as service_v2_candidate_key,
)
from src.services.adaptive_tuner_core_service import (
    as_iso_day_set as service_as_iso_day_set,
    covered_days_for_schema as service_covered_days_for_schema,
    extract_strategy_params_for_profile as service_extract_strategy_params_for_profile,
    iter_date_strings as service_iter_date_strings,
    normalize_strategy_combo_profiles as service_normalize_strategy_combo_profiles,
    normalize_bool_options as service_normalize_bool_options,
    normalize_clamped_int as service_normalize_clamped_int,
    normalize_float_options as service_normalize_float_options,
    normalize_int_options as service_normalize_int_options,
    normalize_mode_options as service_normalize_mode_options,
    normalize_non_negative_int as service_normalize_non_negative_int,
    normalize_regime_filter_sets as service_normalize_regime_filter_sets,
    normalize_regime_strategy_map_sets as service_normalize_regime_strategy_map_sets,
    normalize_strategy_selection_mode as service_normalize_strategy_selection_mode,
    normalize_strategy_sets as service_normalize_strategy_sets,
    normalize_tuner_profiles as service_normalize_tuner_profiles,
    normalize_time_window_sets as service_normalize_time_window_sets,
    range_summary_from_days as service_range_summary_from_days,
    sanitize_strategy_params as service_sanitize_strategy_params,
    resolve_l2_tuning_dates as service_resolve_l2_tuning_dates,
    resolve_tuner_trial_budget as service_resolve_tuner_trial_budget,
    sample_evenly_spaced_days as service_sample_evenly_spaced_days,
)
from src.services.adaptive_tuner_search_service import (
    build_adaptive_candidate_config as service_build_adaptive_candidate_config,
    build_adaptive_tuner_search_space as service_build_adaptive_tuner_search_space,
    build_grid_candidates as service_build_grid_candidates,
    build_random_candidates as service_build_random_candidates,
    build_tuner_profile_entry as service_build_tuner_profile_entry,
    candidate_key as service_candidate_key,
    compute_tuner_score as service_compute_tuner_score,
    compute_tuner_score_robust as service_compute_tuner_score_robust,
)
from src.services.strategy_api_types import StrategyApiIntegrationDeps
from src.services.strategy_api_updates_service import (
    apply_global_trailing as service_apply_global_trailing,
    apply_strategy_overrides as service_apply_strategy_overrides,
    apply_strategy_param_map as service_apply_strategy_param_map,
    fetch_remote_strategies as service_fetch_remote_strategies,
)
from src.services.strategy_api_profiles_service import (
    apply_active_adaptive_tuner_profile as service_apply_active_adaptive_tuner_profile,
    apply_active_strategy_combo as service_apply_active_strategy_combo,
    apply_aos_optimizations as service_apply_aos_optimizations,
    extract_profile_runtime_overrides as service_extract_profile_runtime_overrides,
    normalize_strategy_key as service_normalize_strategy_key,
    resolve_active_adaptive_tuner_candidate as service_resolve_active_adaptive_tuner_candidate,
)
from src.services.strategy_api_session_service import (
    clear_remote_strategy_sessions as service_clear_remote_strategy_sessions,
    configure_session as service_configure_session,
    load_remote_checkpoint as service_load_remote_checkpoint,
    reset_remote_orchestrator_state as service_reset_remote_orchestrator_state,
    reset_remote_orchestrator_state_scoped as service_reset_remote_orchestrator_state_scoped,
    save_remote_checkpoint as service_save_remote_checkpoint,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BacktestRunner")

# ============ App Setup ============
app = FastAPI(
    title="Unified Backtest Runner",
    description="Walk-forward backtesting with strategy evaluation and decision visualization",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Global State ============
data_loader = DataLoader()
l2_manager = L2DataManager()
l2_features = L2FeatureService(manager=l2_manager, logger=logger)
active_runners: Dict[str, SessionRunner] = {}
run_registry = RunRegistry(active_runners)
connected_clients: List[WebSocket] = []
databento_svc = DatabentoService()
adaptive_tuner_jobs: Dict[str, Dict[str, Any]] = {}
MAX_PARALLEL_ADAPTIVE_TUNERS = 3
adaptive_tuner_slots = asyncio.Semaphore(MAX_PARALLEL_ADAPTIVE_TUNERS)
adaptive_tuner_merge_lock = asyncio.Lock()
STRATEGY_OVERRIDES_PATH = Path(__file__).parent / "strategy_overrides.json"
AOS_CONFIG_PATH = Path(__file__).parent / "aos_optimization" / "aos_config.json"
POSITIONING_CONFIG_PATH = Path(__file__).parent / "aos_optimization" / "positioning_config.json"
ADAPTIVE_TUNER_AOS_DIR = Path(__file__).parent / "aos_optimization" / ".adaptive_tuner_aos"
LIVE_TRADER_ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "ibkr-realtime-trader" / "artifacts"
MARKET_TZ = ZoneInfo("America/New_York")
LIVE_RUN_ACTIVE_WINDOW_SECONDS = 180
_startup_prewarm_task: Optional[asyncio.Task] = None


def _parse_bool_env(raw_value: Optional[str], default: bool) -> bool:
    if raw_value is None:
        return bool(default)
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _parse_startup_prewarm_tickers(raw_value: Optional[str]) -> List[str]:
    if not raw_value:
        return []
    tickers: List[str] = []
    seen = set()
    for token in str(raw_value).split(","):
        candidate = token.strip().upper()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        tickers.append(candidate)
    return tickers


STARTUP_PREWARM_ENABLED = _parse_bool_env(
    os.getenv("BACKTEST_STARTUP_PREWARM_ENABLED"),
    True,
)
STARTUP_PREWARM_TICKERS = _parse_startup_prewarm_tickers(
    os.getenv("BACKTEST_STARTUP_PREWARM_TICKERS", "MU")
)
STARTUP_PREWARM_L2_CONFIRM = _parse_bool_env(
    os.getenv("BACKTEST_STARTUP_PREWARM_L2_CONFIRM"),
    True,
)


def _run_startup_prewarm_request_sync(request: PrewarmRunRequest) -> Dict[str, Any]:
    """Run startup prewarm outside the main event loop."""
    return asyncio.run(service_prewarm_run(request, _build_start_run_deps()))


def _refresh_runtime_data_services() -> None:
    """Recreate data services after settings changes and keep legacy globals in sync."""
    global data_loader, l2_manager
    data_loader = DataLoader()
    l2_manager = L2DataManager()
    l2_features.manager = l2_manager
    api_services.data_loader = data_loader
    api_services.l2_manager = l2_manager
    api_services.l2_features = l2_features


async def _broadcast_with_api_services(message: Dict[str, Any]) -> None:
    await broadcast(message)


api_services = ApiServices(
    data_loader=data_loader,
    l2_manager=l2_manager,
    l2_features=l2_features,
    active_runners=active_runners,
    databento_svc=databento_svc,
    logger=logger,
    get_live_trader_artifacts_dir=lambda: LIVE_TRADER_ARTIFACTS_DIR,
    live_run_active_window_seconds=LIVE_RUN_ACTIVE_WINDOW_SECONDS,
    load_strategy_overrides=lambda: _load_strategy_overrides(),
    build_strategy_combo_options_payload=lambda ticker: _build_strategy_combo_options_payload(ticker),
    load_aos_config=lambda: _load_aos_config(),
    load_positioning_config=lambda: _load_positioning_config(),
    merge_positioning_into_aos_snapshot=(
        lambda aos_cfg, pos_cfg: _merge_positioning_into_aos_snapshot(aos_cfg, pos_cfg)
    ),
    get_ticker_positioning_config=lambda ticker: _get_ticker_positioning_config(ticker),
    positioning_config_keys=POSITIONING_CONFIG_KEYS,
    build_adaptive_tuner_options_payload=lambda ticker: _build_adaptive_tuner_options_payload(ticker),
    build_config_write_deps=lambda: _build_config_write_deps(),
    build_run_control_deps=lambda: _build_run_control_deps(),
    build_adaptive_tuner_deps=lambda: _build_adaptive_tuner_deps(),
    start_run=lambda request: start_run(request),
    prewarm_run=lambda request: prewarm_run(request),
    prewarm_status=lambda request: prewarm_status(request),
    broadcast=_broadcast_with_api_services,
    refresh_runtime_data_services=_refresh_runtime_data_services,
    reset_discovery=reset_discovery,
)
app.state.api_services = api_services


def _build_config_write_deps() -> ConfigWriteDeps:
    """Build deps lazily so monkeypatched globals in tests are respected."""
    return ConfigWriteDeps(
        load_aos_config=lambda: _load_aos_config(),
        save_aos_config=lambda cfg: _save_aos_config(cfg),
        load_positioning_config=lambda: _load_positioning_config(),
        save_positioning_config=lambda cfg: _save_positioning_config(cfg),
        get_ticker_positioning_config=_get_ticker_positioning_config,
        normalize_strategy_combo_profiles=_normalize_strategy_combo_profiles,
        normalize_tuner_profiles=_normalize_tuner_profiles,
        build_strategy_combo_profile_entry=_build_strategy_combo_profile_entry,
        fetch_remote_strategies=_fetch_remote_strategies,
        extract_strategy_params_for_profile=_extract_strategy_params_for_profile,
        apply_strategy_param_map=_apply_strategy_param_map,
        build_v2_candidate_config=_build_v2_candidate_config,
        build_adaptive_candidate_config=_build_adaptive_candidate_config,
        normalize_non_negative_int=_normalize_non_negative_int,
        positioning_config_keys=POSITIONING_CONFIG_KEYS,
        logger=logger,
    )


def _build_run_control_deps() -> RunControlDeps:
    return RunControlDeps(
        run_registry=run_registry,
        active_runners=active_runners,
        marker_type_enum=MarkerType,
        logger=logger,
        reports_dir=Path(__file__).parent / "reports",
        save_remote_checkpoint=_save_remote_checkpoint,
        clear_remote_strategy_sessions=_clear_remote_strategy_sessions,
        configure_session=_configure_session,
    )


def _build_adaptive_tuner_deps() -> AdaptiveTunerOrchestrationDeps:
    return AdaptiveTunerOrchestrationDeps(
        adaptive_tuner_jobs=adaptive_tuner_jobs,
        max_parallel_adaptive_tuners=MAX_PARALLEL_ADAPTIVE_TUNERS,
        normalize_non_negative_int=_normalize_non_negative_int,
        normalize_clamped_int=_normalize_clamped_int,
        iter_date_strings=_iter_date_strings,
        resolve_l2_tuning_dates=_resolve_l2_tuning_dates,
        sample_evenly_spaced_days=_sample_evenly_spaced_days,
        run_v1_job=_run_adaptive_tuner_job,
        run_v2_job=_run_v2_adaptive_tuner_job,
        create_task=asyncio.create_task,
        uuid4_factory=uuid4,
    )


def _build_adaptive_tuner_worker_deps() -> AdaptiveTunerWorkerDeps:
    return AdaptiveTunerWorkerDeps(
        adaptive_tuner_jobs=adaptive_tuner_jobs,
        adaptive_tuner_slots=adaptive_tuner_slots,
        max_parallel_adaptive_tuners=MAX_PARALLEL_ADAPTIVE_TUNERS,
        normalize_clamped_int=_normalize_clamped_int,
        resolve_tuner_trial_budget=_resolve_tuner_trial_budget,
        create_isolated_tuner_aos_config_locked=_create_isolated_tuner_aos_config_locked,
        cleanup_isolated_tuner_aos_config=_cleanup_isolated_tuner_aos_config,
        load_aos_config=_load_aos_config,
        save_aos_config=_save_aos_config,
        build_v2_search_space=_build_v2_search_space,
        build_v2_random_candidates=_build_v2_random_candidates,
        build_v2_candidate_config=_build_v2_candidate_config,
        build_adaptive_tuner_search_space=_build_adaptive_tuner_search_space,
        build_grid_candidates=_build_grid_candidates,
        build_random_candidates=_build_random_candidates,
        build_adaptive_candidate_config=_build_adaptive_candidate_config,
        prepare_tuner_trial_ticker_config=_prepare_tuner_trial_ticker_config,
        evaluate_v2_candidate=_evaluate_v2_candidate,
        evaluate_adaptive_tuner_candidate=_evaluate_adaptive_tuner_candidate,
        analyze_vectors=_analyze_vectors,
        persist_tuner_result_to_primary_aos=_persist_tuner_result_to_primary_aos,
    )


def _build_adaptive_tuner_runtime_deps() -> AdaptiveTunerRuntimeDeps:
    return AdaptiveTunerRuntimeDeps(
        active_runners=active_runners,
        start_run=start_run,
        start_run_request_cls=StartRunRequest,
        normalize_strategy_selection_mode=_normalize_strategy_selection_mode,
        normalize_clamped_int=_normalize_clamped_int,
        compute_tuner_score=_compute_tuner_score,
        compute_tuner_score_robust=_compute_tuner_score_robust,
        apply_strategy_param_map=_apply_strategy_param_map,
        adaptive_tuner_merge_lock=adaptive_tuner_merge_lock,
        load_aos_config=_load_aos_config,
        save_aos_config=_save_aos_config,
        build_tuner_profile_entry=_build_tuner_profile_entry,
        normalize_tuner_profiles=_normalize_tuner_profiles,
        build_v2_candidate_config=_build_v2_candidate_config,
        build_adaptive_candidate_config=_build_adaptive_candidate_config,
    )


def _build_adaptive_tuner_v2_deps() -> AdaptiveTunerV2Deps:
    return AdaptiveTunerV2Deps(
        build_adaptive_tuner_search_space=_build_adaptive_tuner_search_space,
        normalize_momentum_diversification_payload=_normalize_momentum_diversification_payload,
        normalize_strategy_sets=_normalize_strategy_sets,
        normalize_float_options=_normalize_float_options,
        normalize_regime_filter_sets=_normalize_regime_filter_sets,
        normalize_int_options=_normalize_int_options,
        normalize_time_window_sets=_normalize_time_window_sets,
        normalize_bool_options=_normalize_bool_options,
        normalize_regime_strategy_map_sets=_normalize_regime_strategy_map_sets,
        normalize_strategy_selection_mode=_normalize_strategy_selection_mode,
        build_adaptive_candidate_config=_build_adaptive_candidate_config,
        strategy_family_map=STRATEGY_FAMILY_MAP,
        random_factory=random.Random,
    )


def _build_strategy_api_integration_deps() -> StrategyApiIntegrationDeps:
    return StrategyApiIntegrationDeps(
        load_strategy_overrides=_load_strategy_overrides,
        sanitize_strategy_params=_sanitize_strategy_params,
        normalize_strategy_combo_profiles=_normalize_strategy_combo_profiles,
        normalize_tuner_profiles=_normalize_tuner_profiles,
        normalize_strategy_selection_mode=_normalize_strategy_selection_mode,
        normalize_clamped_int=_normalize_clamped_int,
        normalize_momentum_diversification_payload=_normalize_momentum_diversification_payload,
        load_aos_config=_load_aos_config,
        get_ticker_positioning_config=_get_ticker_positioning_config,
        positioning_config_keys=POSITIONING_CONFIG_KEYS,
        apply_strategy_param_map=_apply_strategy_param_map,
        fetch_remote_strategies=_fetch_remote_strategies,
        apply_active_strategy_combo=_apply_active_strategy_combo,
        apply_active_adaptive_tuner_profile=_apply_active_adaptive_tuner_profile,
        logger=logger,
    )


def _build_start_run_deps() -> StartRunDeps:
    return StartRunDeps(
        active_runners=active_runners,
        logger=logger,
        data_loader=data_loader,
        databento_svc=databento_svc,
        l2_manager=l2_manager,
        get_discovery=get_discovery,
        reset_remote_orchestrator_state_scoped=_reset_remote_orchestrator_state_scoped,
        load_remote_checkpoint=_load_remote_checkpoint,
        reset_remote_orchestrator_state=_reset_remote_orchestrator_state,
        clear_remote_strategy_sessions=_clear_remote_strategy_sessions,
        apply_strategy_overrides=_apply_strategy_overrides,
        apply_aos_optimizations=_apply_aos_optimizations,
        normalize_momentum_diversification_payload=_normalize_momentum_diversification_payload,
        apply_global_trailing=_apply_global_trailing,
        to_utc_datetime=_to_utc_datetime,
        build_l2_feature_map=_build_l2_feature_map,
        normalize_l2_feature_map_for_market_day_sessions=_normalize_l2_feature_map_for_market_day_sessions,
        attach_l2_features=_attach_l2_features,
        load_aos_config=_load_aos_config,
        get_ticker_positioning_config=_get_ticker_positioning_config,
        configure_session=_configure_session,
        broadcast=broadcast,
        run_config_cls=RunConfig,
        session_runner_cls=SessionRunner,
    )


async def _run_startup_prewarm() -> None:
    if not STARTUP_PREWARM_ENABLED:
        logger.info("Startup prewarm disabled (BACKTEST_STARTUP_PREWARM_ENABLED=0).")
        return
    if not STARTUP_PREWARM_TICKERS:
        logger.info("Startup prewarm skipped (no tickers configured).")
        return

    logger.info(
        "Startup prewarm scheduled for tickers=%s (l2_confirm=%s)",
        STARTUP_PREWARM_TICKERS,
        STARTUP_PREWARM_L2_CONFIRM,
    )
    for ticker in STARTUP_PREWARM_TICKERS:
        started_at = datetime.utcnow()
        try:
            request = PrewarmRunRequest(
                ticker=ticker,
                prewarm_scope="ticker",
                allow_mock_data=False,
                l2_only=False,
                l2_confirm_enabled=bool(STARTUP_PREWARM_L2_CONFIRM),
                comparable_mode=False,
            )
            result = await asyncio.to_thread(_run_startup_prewarm_request_sync, request)
            elapsed_s = (datetime.utcnow() - started_at).total_seconds()
            logger.info(
                "Startup prewarm ready ticker=%s scope=%s range=%s..%s bars=%s cache_hit=%s elapsed=%.2fs",
                ticker,
                result.get("prewarm_scope"),
                result.get("range_start"),
                result.get("range_end"),
                result.get("bars"),
                result.get("cache_hit"),
                elapsed_s,
            )
        except Exception:
            logger.exception("Startup prewarm failed for ticker=%s", ticker)


@app.on_event("startup")
async def _on_startup() -> None:
    global _startup_prewarm_task
    if _startup_prewarm_task is not None and not _startup_prewarm_task.done():
        return
    _startup_prewarm_task = asyncio.create_task(_run_startup_prewarm())


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    global _startup_prewarm_task
    task = _startup_prewarm_task
    _startup_prewarm_task = None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

# Strategy family taxonomy - imported from src.momentum_diversification
# Backward-compatible alias
# STRATEGY_FAMILY_MAP is now imported from src.momentum_diversification

# Positioning config keys - imported from src.aos_config
# Backward-compatible alias  
# POSITIONING_CONFIG_KEYS is now imported from src.aos_config

# Momentum diversification keys - imported from src.momentum_diversification
# Backward-compatible aliases
MOMENTUM_DIVERSIFICATION_MICRO_KEYS = MICRO_REGIMES
MOMENTUM_DIVERSIFICATION_ROUTE_KEYS = ROUTE_KEYS

# Backward-compatible aliases for functions now in src modules
_normalize_momentum_diversification_payload = normalize_momentum_diversification_payload
_build_regime_strategy_map_options = build_regime_strategy_map_options


def _load_strategy_overrides() -> Dict[str, Any]:
    return load_json_file(STRATEGY_OVERRIDES_PATH, default={})


def _resolve_aos_config_path(aos_config_path: Optional[Union[str, Path]] = None) -> Path:
    if aos_config_path is None:
        return AOS_CONFIG_PATH
    raw = str(aos_config_path).strip()
    if not raw:
        return AOS_CONFIG_PATH
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def _load_aos_config(aos_config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Load AOS optimization config from JSON file."""
    path = _resolve_aos_config_path(aos_config_path)
    return load_json_file(path, default={"version": "1.0.0", "tickers": {}})


def _resolve_positioning_config_path(
    positioning_config_path: Optional[Union[str, Path]] = None,
) -> Path:
    if positioning_config_path is None:
        return POSITIONING_CONFIG_PATH
    raw = str(positioning_config_path).strip()
    if not raw:
        return POSITIONING_CONFIG_PATH
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def _load_positioning_config(
    positioning_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    path = _resolve_positioning_config_path(positioning_config_path)
    return load_json_file(path, default={"version": "1.0.0", "tickers": {}})


def _save_positioning_config(
    config: Dict[str, Any],
    positioning_config_path: Optional[Union[str, Path]] = None,
) -> bool:
    path = _resolve_positioning_config_path(positioning_config_path)
    ok = save_json_file(path, payload=config)
    if not ok:
        logger.error(f"Failed to save positioning config: {path}")
    return ok


def _get_ticker_positioning_config(
    ticker: str,
    positioning_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg = positioning_config if isinstance(positioning_config, dict) else _load_positioning_config()
    tickers = cfg.get("tickers", {}) if isinstance(cfg, dict) else {}
    if not isinstance(tickers, dict):
        return {}
    raw = tickers.get(str(ticker or "").upper(), {})
    return dict(raw) if isinstance(raw, dict) else {}


def _merge_positioning_into_aos_snapshot(
    aos_config: Dict[str, Any],
    positioning_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    merged = copy.deepcopy(aos_config if isinstance(aos_config, dict) else {})
    tickers = merged.get("tickers")
    if not isinstance(tickers, dict):
        tickers = {}
        merged["tickers"] = tickers
    pos_cfg = positioning_config if isinstance(positioning_config, dict) else _load_positioning_config()
    pos_tickers = pos_cfg.get("tickers", {}) if isinstance(pos_cfg, dict) else {}
    if not isinstance(pos_tickers, dict):
        pos_tickers = {}
    for ticker, ticker_cfg in list(tickers.items()):
        if not isinstance(ticker_cfg, dict):
            continue
        legacy = {}
        for key in POSITIONING_CONFIG_KEYS:
            if key in ticker_cfg:
                legacy[key] = ticker_cfg.get(key)
        if legacy:
            current = pos_tickers.get(ticker, {})
            if not isinstance(current, dict):
                current = {}
            merged_legacy = dict(legacy)
            merged_legacy.update(current)
            pos_tickers[ticker] = merged_legacy
    for ticker, p_cfg in pos_tickers.items():
        if not isinstance(p_cfg, dict):
            continue
        base = tickers.get(ticker, {})
        if not isinstance(base, dict):
            base = {}
        overlay = dict(base)
        overlay["positioning"] = dict(p_cfg)
        tickers[ticker] = overlay
    return merged


def _save_aos_config(
    config: Dict[str, Any],
    aos_config_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Save AOS optimization config to JSON file."""
    path = _resolve_aos_config_path(aos_config_path)
    ok = save_json_file(path, payload=config)
    if not ok:
        logger.error(f"Failed to save AOS config: {path}")
    return ok


def _create_isolated_tuner_aos_config(
    job_id: str,
    *,
    snapshot: Optional[Dict[str, Any]] = None,
) -> Path:
    """Create per-job AOS config snapshot so tuner trials do not collide."""
    ADAPTIVE_TUNER_AOS_DIR.mkdir(parents=True, exist_ok=True)
    path = ADAPTIVE_TUNER_AOS_DIR / f"aos_config_{job_id}.json"
    source = snapshot if isinstance(snapshot, dict) else _load_aos_config()
    if not _save_aos_config(source, path):
        raise RuntimeError("Failed to create isolated tuner AOS config snapshot.")
    return path


def _cleanup_isolated_tuner_aos_config(aos_config_path: Optional[Union[str, Path]]) -> None:
    if aos_config_path is None:
        return
    path = _resolve_aos_config_path(aos_config_path)
    if path == AOS_CONFIG_PATH:
        return
    try:
        path.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning(f"Failed to clean isolated tuner AOS config {path}: {exc}")


async def _create_isolated_tuner_aos_config_locked(job_id: str) -> Path:
    """Take a lock-protected primary snapshot and materialize isolated tuner config."""
    async with adaptive_tuner_merge_lock:
        snapshot = _load_aos_config()
    return _create_isolated_tuner_aos_config(job_id, snapshot=snapshot)


def _sanitize_live_run_id(run_id: str) -> str:
    return sanitize_live_run_id(run_id)


def _live_artifact_file(stream: str, run_id: str) -> Path:
    return live_artifact_file(LIVE_TRADER_ARTIFACTS_DIR, stream, run_id)


def _read_jsonl_tail(path: Path, limit: int = 200) -> List[Dict[str, Any]]:
    return read_jsonl_tail(path, limit=limit, logger=logger)


def _parse_utc_iso(value: Any) -> Optional[datetime]:
    return parse_utc_iso(value)


def _extract_runtime_summary(run_id: str) -> Optional[Dict[str, Any]]:
    return extract_runtime_summary(run_id, LIVE_TRADER_ARTIFACTS_DIR, logger=logger)


def _infer_live_run_status(updated_at: Any, runtime_summary: Optional[Dict[str, Any]]) -> str:
    return infer_live_run_status(
        updated_at,
        runtime_summary,
        active_window_seconds=LIVE_RUN_ACTIVE_WINDOW_SECONDS,
    )


def _discover_live_trader_runs(limit: int = 20, active_only: bool = False) -> List[Dict[str, Any]]:
    return discover_live_trader_runs(
        LIVE_TRADER_ARTIFACTS_DIR,
        limit=limit,
        active_only=active_only,
        active_window_seconds=LIVE_RUN_ACTIVE_WINDOW_SECONDS,
        logger=logger,
    )


def _normalize_strategy_selection_mode(mode: Any) -> str:
    return service_normalize_strategy_selection_mode(mode)


def _normalize_non_negative_int(value: Any, default: int = 0, max_value: int = 10_000) -> int:
    return service_normalize_non_negative_int(
        value,
        default=default,
        max_value=max_value,
    )


def _normalize_clamped_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    return service_normalize_clamped_int(
        value,
        default=default,
        min_value=min_value,
        max_value=max_value,
    )


def _normalize_bool_options(values: Optional[List[bool]], default: List[bool]) -> List[bool]:
    return service_normalize_bool_options(values, default)


def _normalize_int_options(
    values: Optional[List[int]],
    default: List[int],
    *,
    min_value: int,
    max_value: int,
) -> List[int]:
    return service_normalize_int_options(
        values,
        default,
        min_value=min_value,
        max_value=max_value,
    )


def _normalize_mode_options(values: Optional[List[str]]) -> List[str]:
    return service_normalize_mode_options(values)


def _normalize_float_options(
    values: Optional[List[float]],
    default: List[float],
    *,
    min_value: float = 0.0,
    max_value: float = 1_000_000.0,
) -> List[float]:
    return service_normalize_float_options(
        values,
        default,
        min_value=min_value,
        max_value=max_value,
    )


def _normalize_strategy_sets(
    raw_sets: Optional[List[List[str]]],
    enabled_strategies: List[str],
) -> List[List[str]]:
    return service_normalize_strategy_sets(raw_sets, enabled_strategies)


def _normalize_regime_filter_sets(
    raw_sets: Optional[List[List[str]]],
) -> List[List[str]]:
    return service_normalize_regime_filter_sets(raw_sets)


def _normalize_time_window_sets(
    raw_sets: Optional[List[List[int]]],
) -> List[List[int]]:
    return service_normalize_time_window_sets(raw_sets)


def _normalize_regime_strategy_map_sets(
    raw_sets: Optional[List[Optional[Dict[str, List[str]]]]],
    enabled_strategies: List[str],
) -> List[Optional[Dict[str, List[str]]]]:
    return service_normalize_regime_strategy_map_sets(
        raw_sets,
        enabled_strategies,
        _build_regime_strategy_map_options,
    )


def _iter_date_strings(date_from: str, date_to: str) -> List[str]:
    return service_iter_date_strings(date_from, date_to)


def _as_iso_day_set(days: List[str]) -> set:
    return service_as_iso_day_set(days)


def _resolve_l2_tuning_dates(
    *,
    ticker: str,
    date_from: str,
    date_to: str,
    l2_required: bool,
) -> List[str]:
    return service_resolve_l2_tuning_dates(
        ticker=ticker,
        date_from=date_from,
        date_to=date_to,
        l2_required=l2_required,
        databento_svc=databento_svc,
    )


def _sample_evenly_spaced_days(days: List[str], *, max_days: int) -> List[str]:
    return service_sample_evenly_spaced_days(days, max_days=max_days)


def _resolve_tuner_trial_budget(
    *,
    requested_trials: Any,
    default_trials: int,
    quick_mode: bool,
    quick_trial_boost: Any,
    max_trials: int = 400,
) -> Dict[str, int]:
    return service_resolve_tuner_trial_budget(
        requested_trials=requested_trials,
        default_trials=default_trials,
        quick_mode=quick_mode,
        quick_trial_boost=quick_trial_boost,
        max_trials=max_trials,
    )


def _covered_days_for_schema(ticker: str, schema: str) -> List[str]:
    return service_covered_days_for_schema(ticker, schema, databento_svc)


def _range_summary_from_days(days: List[str]) -> Dict[str, Any]:
    return service_range_summary_from_days(days)


def _normalize_tuner_profiles(raw_profiles: Any) -> List[Dict[str, Any]]:
    return service_normalize_tuner_profiles(raw_profiles)


def _sanitize_strategy_params(params: Any) -> Dict[str, Any]:
    return service_sanitize_strategy_params(params)


def _extract_strategy_params_for_profile(strategies_payload: Any) -> Dict[str, Dict[str, Any]]:
    return service_extract_strategy_params_for_profile(strategies_payload)


def _normalize_strategy_combo_profiles(raw_profiles: Any) -> List[Dict[str, Any]]:
    return service_normalize_strategy_combo_profiles(raw_profiles)


def _build_strategy_combo_profile_entry(
    *,
    ticker: str,
    profile_name: str,
    strategy_params: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "profile_id": uuid4().hex[:12],
        "profile_name": str(profile_name or "").strip() or f"{ticker}-combo",
        "created_at": now,
        "updated_at": now,
        "strategy_params": strategy_params,
    }


def _build_strategy_combo_options_payload(ticker: str) -> Dict[str, Any]:
    ticker_upper = str(ticker or "").upper().strip()
    if not ticker_upper:
        raise HTTPException(400, "ticker is required")
    aos_cfg = _load_aos_config()
    ticker_cfg = aos_cfg.get("tickers", {}).get(ticker_upper, {})
    profiles = _normalize_strategy_combo_profiles(ticker_cfg.get("strategy_combo_profiles", []))
    active_profile_id = str(
        ticker_cfg.get("active_strategy_combo_profile_id", "")
    ).strip() or None
    return {
        "ticker": ticker_upper,
        "profiles": profiles,
        "active_profile_id": active_profile_id,
    }


def _build_tuner_profile_entry(
    *,
    ticker: str,
    request: "AdaptiveTunerRequest",
    method_used: str,
    dates: List[str],
    best_trial: Dict[str, Any],
) -> Dict[str, Any]:
    return service_build_tuner_profile_entry(
        ticker=ticker,
        request=request,
        method_used=method_used,
        dates=dates,
        best_trial=best_trial,
    )


def _build_adaptive_tuner_options_payload(ticker: str) -> Dict[str, Any]:
    ticker_upper = str(ticker or "").upper().strip()
    if not ticker_upper:
        raise HTTPException(400, "ticker is required")

    ohlcv_days = _covered_days_for_schema(ticker_upper, "ohlcv-1m")
    l2_days = _covered_days_for_schema(ticker_upper, "mbp-10")
    overlap_days = sorted(set(ohlcv_days).intersection(set(l2_days)))

    ohlcv_range = _range_summary_from_days(ohlcv_days)
    l2_range = _range_summary_from_days(l2_days)
    overlap_range = _range_summary_from_days(overlap_days)

    aos_cfg = _load_aos_config()
    ticker_cfg = aos_cfg.get("tickers", {}).get(ticker_upper, {})
    profiles = _normalize_tuner_profiles(ticker_cfg.get("adaptive_tuner_profiles", []))
    active_profile_id = str(
        ticker_cfg.get("active_adaptive_tuner_profile_id", "")
    ).strip() or None

    default_from = overlap_range.get("start") or ohlcv_range.get("start")
    default_to = overlap_range.get("end") or ohlcv_range.get("end")

    return {
        "ticker": ticker_upper,
        "ohlcv_range": ohlcv_range,
        "l2_range": l2_range,
        "l2_overlap_range": overlap_range,
        "l2_overlap_days": overlap_days,
        "default_date_from": default_from,
        "default_date_to": default_to,
        "has_l2_overlap": bool(overlap_days),
        "profiles": profiles,
        "active_profile_id": active_profile_id,
    }


def _build_adaptive_candidate_config(
    ticker_config: Dict[str, Any],
    candidate: Dict[str, Any],
    adaptive_version: int,
) -> Dict[str, Any]:
    return service_build_adaptive_candidate_config(
        ticker_config,
        candidate,
        adaptive_version,
    )


def _compute_tuner_score(
    score_metric: str,
    total_pnl_pct: float,
    total_pnl_dollars: float,
    avg_win_rate_pct: float,
    total_trades: int,
    valid_days: int,
) -> float:
    return service_compute_tuner_score(
        score_metric,
        total_pnl_pct,
        total_pnl_dollars,
        avg_win_rate_pct,
        total_trades,
        valid_days,
    )


def _compute_tuner_score_robust(
    day_results: List[Dict[str, Any]],
) -> float:
    return service_compute_tuner_score_robust(day_results)


async def _apply_strategy_overrides(strategy_api_url: str, ticker: str) -> None:
    return await service_apply_strategy_overrides(
        strategy_api_url,
        ticker,
        _build_strategy_api_integration_deps(),
    )


async def _fetch_remote_strategies(strategy_api_url: str) -> Dict[str, Any]:
    return await service_fetch_remote_strategies(
        strategy_api_url,
        _build_strategy_api_integration_deps(),
    )


async def _apply_strategy_param_map(
    strategy_api_url: str, strategy_params: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    return await service_apply_strategy_param_map(
        strategy_api_url,
        strategy_params,
        _build_strategy_api_integration_deps(),
    )


async def _apply_active_strategy_combo(
    strategy_api_url: str, ticker: str, ticker_config: Dict[str, Any]
) -> Dict[str, Any]:
    return await service_apply_active_strategy_combo(
        strategy_api_url,
        ticker,
        ticker_config,
        _build_strategy_api_integration_deps(),
    )


def _normalize_strategy_key(name: Any) -> str:
    return service_normalize_strategy_key(name)


def _resolve_active_adaptive_tuner_candidate(ticker_config: Dict[str, Any]) -> Dict[str, Any]:
    return service_resolve_active_adaptive_tuner_candidate(
        ticker_config,
        _build_strategy_api_integration_deps(),
    )


def _extract_profile_runtime_overrides(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return service_extract_profile_runtime_overrides(
        candidate,
        _build_strategy_api_integration_deps(),
    )


async def _apply_active_adaptive_tuner_profile(
    strategy_api_url: str,
    ticker_config: Dict[str, Any],
) -> Dict[str, Any]:
    return await service_apply_active_adaptive_tuner_profile(
        strategy_api_url,
        ticker_config,
        _build_strategy_api_integration_deps(),
    )


async def _apply_global_trailing(strategy_api_url: str, trailing_stop_pct: Optional[float]) -> None:
    return await service_apply_global_trailing(
        strategy_api_url,
        trailing_stop_pct,
        _build_strategy_api_integration_deps(),
    )


async def _apply_aos_optimizations(
    strategy_api_url: str,
    ticker: str,
    *,
    remote_sync: bool = True,
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    return await service_apply_aos_optimizations(
        strategy_api_url,
        ticker,
        _build_strategy_api_integration_deps(),
        remote_sync=remote_sync,
        aos_config_path=aos_config_path,
    )


async def _configure_session(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
    date: str,
    regime_detection_minutes: int,
    regime_refresh_bars: int,
    account_size_usd: float,
    risk_per_trade_pct: float = 1.0,
    max_position_notional_pct: float = 100.0,
    max_fill_participation_rate: float = 0.20,
    min_fill_ratio: float = 0.35,
    enable_partial_take_profit: bool = True,
    partial_take_profit_rr: float = 1.0,
    partial_take_profit_fraction: float = 0.5,
    trailing_activation_pct: float = 0.15,
    break_even_buffer_pct: float = 0.03,
    break_even_min_hold_bars: int = 2,
    trailing_enabled_in_choppy: bool = False,
    time_exit_bars: int = 40,
    adverse_flow_exit_enabled: bool = True,
    adverse_flow_threshold: float = 0.12,
    adverse_flow_min_hold_bars: int = 3,
    adverse_flow_consistency_threshold: float = 0.45,
    adverse_book_pressure_threshold: float = 0.15,
    stop_loss_mode: str = "strategy",
    fixed_stop_loss_pct: float = 0.0,
    l2_confirm_enabled: bool = False,
    l2_min_delta: float = 0.0,
    l2_min_imbalance: float = 0.0,
    l2_min_iceberg_bias: float = 0.0,
    l2_lookback_bars: int = 3,
    l2_min_participation_ratio: float = 0.0,
    l2_min_directional_consistency: float = 0.0,
    l2_min_signed_aggression: float = 0.0,
    cold_start_each_day: bool = False,
    strategy_selection_mode: str = "adaptive_top_n",
    max_active_strategies: int = 3,
    momentum_diversification_json: Optional[str] = None,
) -> None:
    return await service_configure_session(
        strategy_api_url=strategy_api_url,
        run_id=run_id,
        ticker=ticker,
        date=date,
        regime_detection_minutes=regime_detection_minutes,
        regime_refresh_bars=regime_refresh_bars,
        account_size_usd=account_size_usd,
        risk_per_trade_pct=risk_per_trade_pct,
        max_position_notional_pct=max_position_notional_pct,
        max_fill_participation_rate=max_fill_participation_rate,
        min_fill_ratio=min_fill_ratio,
        enable_partial_take_profit=enable_partial_take_profit,
        partial_take_profit_rr=partial_take_profit_rr,
        partial_take_profit_fraction=partial_take_profit_fraction,
        trailing_activation_pct=trailing_activation_pct,
        break_even_buffer_pct=break_even_buffer_pct,
        break_even_min_hold_bars=break_even_min_hold_bars,
        trailing_enabled_in_choppy=trailing_enabled_in_choppy,
        time_exit_bars=time_exit_bars,
        adverse_flow_exit_enabled=adverse_flow_exit_enabled,
        adverse_flow_threshold=adverse_flow_threshold,
        adverse_flow_min_hold_bars=adverse_flow_min_hold_bars,
        adverse_flow_consistency_threshold=adverse_flow_consistency_threshold,
        adverse_book_pressure_threshold=adverse_book_pressure_threshold,
        stop_loss_mode=stop_loss_mode,
        fixed_stop_loss_pct=fixed_stop_loss_pct,
        l2_confirm_enabled=l2_confirm_enabled,
        l2_min_delta=l2_min_delta,
        l2_min_imbalance=l2_min_imbalance,
        l2_min_iceberg_bias=l2_min_iceberg_bias,
        l2_lookback_bars=l2_lookback_bars,
        l2_min_participation_ratio=l2_min_participation_ratio,
        l2_min_directional_consistency=l2_min_directional_consistency,
        l2_min_signed_aggression=l2_min_signed_aggression,
        cold_start_each_day=cold_start_each_day,
        strategy_selection_mode=strategy_selection_mode,
        max_active_strategies=max_active_strategies,
        momentum_diversification_json=momentum_diversification_json,
        deps=_build_strategy_api_integration_deps(),
    )


async def _clear_remote_strategy_sessions(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
) -> None:
    return await service_clear_remote_strategy_sessions(
        strategy_api_url,
        run_id,
        ticker,
        _build_strategy_api_integration_deps(),
    )


async def _reset_remote_orchestrator_state(strategy_api_url: str) -> bool:
    return await service_reset_remote_orchestrator_state(
        strategy_api_url,
        _build_strategy_api_integration_deps(),
    )


async def _reset_remote_orchestrator_state_scoped(
    strategy_api_url: str, scope: str = "session"
) -> bool:
    return await service_reset_remote_orchestrator_state_scoped(
        strategy_api_url,
        scope,
        _build_strategy_api_integration_deps(),
    )


async def _load_remote_checkpoint(
    strategy_api_url: str, checkpoint_path: str
) -> Optional[Dict]:
    return await service_load_remote_checkpoint(
        strategy_api_url,
        checkpoint_path,
        _build_strategy_api_integration_deps(),
    )


async def _save_remote_checkpoint(
    strategy_api_url: str,
    run_id: str = "",
    ticker: str = "",
    date_from: str = "",
    date_to: str = "",
) -> Optional[str]:
    return await service_save_remote_checkpoint(
        strategy_api_url,
        run_id,
        ticker,
        date_from,
        date_to,
        _build_strategy_api_integration_deps(),
    )


def _to_utc_datetime(value: Any) -> datetime:
    return l2_features.to_utc_datetime(value)


def _build_l2_feature_map(
    ticker: str,
    start_dt_utc: datetime,
    end_dt_utc: datetime,
) -> tuple[Dict[int, Dict[str, float]], Dict[str, Any]]:
    return l2_features.build_feature_map(
        ticker=ticker,
        start_dt_utc=start_dt_utc,
        end_dt_utc=end_dt_utc,
    )


def _attach_l2_features(
    bars: List[Dict[str, Any]],
    feature_map: Dict[int, Dict[str, float]],
    l2_only: bool = False,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return l2_features.attach_features(
        bars=bars,
        feature_map=feature_map,
        l2_only=l2_only,
    )


def _normalize_l2_feature_map_for_market_day_sessions(
    feature_map: Dict[int, Dict[str, float]],
    bars: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Normalize day-scoped L2 fields per ET market day using the bar timeline.

    This keeps the single-pass L2 build fast while removing cross-day carryover
    (e.g., cumulative delta, delta acceleration, book pressure change) so
    multi-day range runs remain comparable to isolated day-by-day cold runs.
    """
    if not feature_map or not bars:
        return {"sessionized_days": 0, "sessionized_minutes": 0}

    day_to_minute_keys: Dict[str, set[int]] = {}
    for bar in bars:
        ts_raw = bar.get("timestamp")
        if ts_raw is None:
            continue
        try:
            ts_utc = _to_utc_datetime(ts_raw)
        except Exception:
            continue
        minute_key = int(ts_utc.timestamp() // 60)
        if minute_key not in feature_map:
            continue
        day_key = ts_utc.astimezone(MARKET_TZ).date().isoformat()
        day_to_minute_keys.setdefault(day_key, set()).add(minute_key)

    sessionized_minutes = 0
    for minute_keys in day_to_minute_keys.values():
        ordered_keys = sorted(minute_keys)
        running_cumulative = 0.0
        prev_delta = 0.0
        prev_book_pressure: Optional[float] = None
        for minute_key in ordered_keys:
            feats = feature_map.get(minute_key)
            if not isinstance(feats, dict):
                continue
            delta = float(feats.get("l2_delta", 0.0) or 0.0)
            book_pressure = float(feats.get("l2_book_pressure", 0.0) or 0.0)

            running_cumulative += delta
            feats["l2_cumulative_delta"] = running_cumulative
            feats["l2_delta_acceleration"] = delta - prev_delta
            feats["l2_book_pressure_change"] = (
                0.0 if prev_book_pressure is None else (book_pressure - prev_book_pressure)
            )

            prev_delta = delta
            prev_book_pressure = book_pressure
            sessionized_minutes += 1

    return {
        "sessionized_days": len(day_to_minute_keys),
        "sessionized_minutes": sessionized_minutes,
    }


# ============ WebSocket Management ============
async def broadcast(message: Dict[str, Any]):
    """Broadcast message to all connected WebSocket clients."""
    if not connected_clients:
        return
    
    message_text = json.dumps(message, default=str)
    disconnected = []
    
    for client in connected_clients:
        try:
            await client.send_text(message_text)
        except Exception:
            disconnected.append(client)
    
    for client in disconnected:
        connected_clients.remove(client)


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                
                # Handle client commands
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg.get("type") == "subscribe":
                    run_id = msg.get("run_id")
                    await websocket.send_json({
                        "type": "subscribed",
                        "run_id": run_id
                    })
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(connected_clients)}")


def _candidate_key(candidate: Dict[str, Any]) -> tuple:
    return service_candidate_key(candidate)


def _build_adaptive_tuner_search_space(request: AdaptiveTunerRequest) -> Dict[str, List[Any]]:
    return service_build_adaptive_tuner_search_space(request)


def _build_grid_candidates(
    search_space: Dict[str, List[Any]],
    *,
    max_candidates: int = 600,
) -> List[Dict[str, Any]]:
    return service_build_grid_candidates(
        search_space,
        max_candidates=max_candidates,
    )


def _build_random_candidates(
    search_space: Dict[str, List[Any]],
    *,
    n_trials: int,
    seed: int,
) -> List[Dict[str, Any]]:
    return service_build_random_candidates(
        search_space,
        n_trials=n_trials,
        seed=seed,
    )


async def _evaluate_adaptive_tuner_candidate(
    *,
    job_id: str,
    ticker: str,
    dates: List[str],
    trial_index: int,
    candidate: Dict[str, Any],
    request: AdaptiveTunerRequest,
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    return await service_evaluate_adaptive_tuner_candidate(
        job_id=job_id,
        ticker=ticker,
        dates=dates,
        trial_index=trial_index,
        candidate=candidate,
        request=request,
        deps=_build_adaptive_tuner_runtime_deps(),
        aos_config_path=aos_config_path,
    )


# ============ V2 Multi-Dimensional Vector Discovery ============


def _build_v2_search_space(
    request: AdaptiveTunerRequest,
    ticker_config: Dict[str, Any],
) -> Dict[str, Any]:
    return service_build_v2_search_space(
        request,
        ticker_config,
        _build_adaptive_tuner_v2_deps(),
    )


def _v2_candidate_key(candidate: Dict[str, Any]) -> tuple:
    return service_v2_candidate_key(candidate, _build_adaptive_tuner_v2_deps())


def _build_v2_random_candidates(
    search_space: Dict[str, Any],
    *,
    n_trials: int,
    seed: int,
    neighborhood_search: bool = False,
) -> List[Dict[str, Any]]:
    return service_build_v2_random_candidates(
        search_space,
        n_trials=n_trials,
        seed=seed,
        neighborhood_search=neighborhood_search,
        deps=_build_adaptive_tuner_v2_deps(),
    )


def _build_v2_baseline_candidate(
    search_space: Dict[str, Any],
) -> Dict[str, Any]:
    return service_build_v2_baseline_candidate(
        search_space,
        _build_adaptive_tuner_v2_deps(),
    )


def _build_v2_candidate_config(
    ticker_config: Dict[str, Any],
    candidate: Dict[str, Any],
    adaptive_version: int,
) -> Dict[str, Any]:
    return service_build_v2_candidate_config(
        ticker_config,
        candidate,
        adaptive_version,
        _build_adaptive_tuner_v2_deps(),
    )


def _prepare_tuner_trial_ticker_config(ticker_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Isolate trial settings from currently active adaptive tuner profile."""
    cfg = copy.deepcopy(ticker_cfg)
    cfg["active_adaptive_tuner_profile_id"] = ""
    return cfg


async def _evaluate_v2_candidate(
    *,
    job_id: str,
    ticker: str,
    dates: List[str],
    trial_index: int,
    candidate: Dict[str, Any],
    request: AdaptiveTunerRequest,
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    return await service_evaluate_v2_candidate(
        job_id=job_id,
        ticker=ticker,
        dates=dates,
        trial_index=trial_index,
        candidate=candidate,
        request=request,
        deps=_build_adaptive_tuner_runtime_deps(),
        aos_config_path=aos_config_path,
    )


def _analyze_vectors(
    trials: List[Dict[str, Any]],
    *,
    min_trades: int = 3,
) -> Dict[str, Any]:
    return service_analyze_vectors(
        trials,
        min_trades=min_trades,
        deps=_build_adaptive_tuner_v2_deps(),
    )


async def _persist_tuner_result_to_primary_aos(
    *,
    ticker: str,
    request: "AdaptiveTunerRequest",
    method_used: str,
    dates: List[str],
    best_trial: Optional[Dict[str, Any]],
    vector_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return await service_persist_tuner_result_to_primary_aos(
        ticker=ticker,
        request=request,
        method_used=method_used,
        dates=dates,
        best_trial=best_trial,
        deps=_build_adaptive_tuner_runtime_deps(),
        vector_analysis=vector_analysis,
    )


async def _run_v2_adaptive_tuner_job(
    job_id: str,
    request: AdaptiveTunerRequest,
    dates: List[str],
) -> None:
    return await service_run_v2_adaptive_tuner_job(
        job_id,
        request,
        dates,
        _build_adaptive_tuner_worker_deps(),
    )

async def _run_adaptive_tuner_job(
    job_id: str,
    request: AdaptiveTunerRequest,
    dates: List[str],
) -> None:
    return await service_run_adaptive_tuner_job(
        job_id,
        request,
        dates,
        _build_adaptive_tuner_worker_deps(),
    )


# ============ API Endpoints ============

app.include_router(system_router)
app.include_router(l2_router)
app.include_router(data_loader_router)
app.include_router(live_trader_router)
app.include_router(config_read_router)
app.include_router(config_write_router)
app.include_router(run_router)
app.include_router(adaptive_tuner_router)
app.include_router(run_start_router)


async def list_live_trader_runs(limit: int = 20, active_only: bool = False):
    """Backward-compatible helper for direct test invocation."""
    runs = _discover_live_trader_runs(limit=limit, active_only=active_only)
    return {
        "artifacts_dir": str(LIVE_TRADER_ARTIFACTS_DIR),
        "count": len(runs),
        "active_only": bool(active_only),
        "runs": runs,
    }


async def get_live_trader_events(
    run_id: str,
    stream: str = "decisions",
    limit: int = 200,
):
    """Backward-compatible helper for direct test invocation."""
    return live_trader_events_payload(
        LIVE_TRADER_ARTIFACTS_DIR,
        run_id,
        stream=stream,
        limit=limit,
        logger=logger,
    )


async def get_live_trader_snapshot(run_id: str, tail_limit: int = 200):
    """Backward-compatible helper for direct test invocation."""
    return live_trader_snapshot_payload(
        LIVE_TRADER_ARTIFACTS_DIR,
        run_id,
        tail_limit=tail_limit,
        active_window_seconds=LIVE_RUN_ACTIVE_WINDOW_SECONDS,
        logger=logger,
    )


async def get_strategy_overrides():
    """Get optimized strategy parameters per ticker."""
    return _load_strategy_overrides()


async def get_ticker_overrides(ticker: str):
    """Get optimized strategy parameters for a specific ticker."""
    overrides = _load_strategy_overrides()
    return overrides.get(ticker.upper(), {})


async def get_strategy_combos(ticker: str):
    """Get saved strategy-parameter combo profiles for a ticker."""
    return _build_strategy_combo_options_payload(ticker)


async def capture_strategy_combo(request: StrategyComboCaptureRequest):
    """Capture current strategy API settings into a saved ticker combo profile."""
    return await service_capture_strategy_combo(request, _build_config_write_deps())


async def apply_strategy_combo(request: StrategyComboApplyRequest):
    """Set active strategy combo profile and optionally apply it to strategy API immediately."""
    return await service_apply_strategy_combo(request, _build_config_write_deps())


async def get_aos_config():
    """Get full AOS optimization config."""
    aos_config = _load_aos_config()
    positioning_config = _load_positioning_config()
    return _merge_positioning_into_aos_snapshot(aos_config, positioning_config)


async def get_ticker_aos_config(ticker: str):
    """Get AOS config for a specific ticker."""
    config = _load_aos_config()
    ticker_config = config.get("tickers", {}).get(ticker.upper(), {})
    if not isinstance(ticker_config, dict):
        ticker_config = {}
    positioning_cfg = _get_ticker_positioning_config(ticker)
    legacy_positioning = {}
    for key in POSITIONING_CONFIG_KEYS:
        if key in ticker_config:
            legacy_positioning[key] = ticker_config.get(key)
    if legacy_positioning:
        merged_positioning = dict(legacy_positioning)
        merged_positioning.update(positioning_cfg)
        positioning_cfg = merged_positioning
    if positioning_cfg:
        payload = dict(ticker_config)
        payload["positioning"] = positioning_cfg
        return payload
    return ticker_config


async def update_aos_config(request: AOSUpdateRequest):
    """Update AOS config for a specific ticker."""
    return service_update_aos_config(request, _build_config_write_deps())


async def get_positioning_config():
    """Get full positioning config file."""
    return _load_positioning_config()


async def get_ticker_positioning_config(ticker: str):
    """Get positioning config for one ticker."""
    return _get_ticker_positioning_config(ticker)


async def update_positioning_config(request: PositioningUpdateRequest):
    """Update positioning config for a specific ticker."""
    return service_update_positioning_config(request, _build_config_write_deps())


async def get_adaptive_tuner_options(ticker: str):
    """Get real coverage ranges and saved tuner profiles for a ticker."""
    return _build_adaptive_tuner_options_payload(ticker)


async def apply_adaptive_tuner_profile(request: AdaptiveTunerProfileApplyRequest):
    """Apply a saved adaptive-tuner profile into active ticker AOS settings."""
    return service_apply_adaptive_tuner_profile(request, _build_config_write_deps())


async def run_adaptive_tuner(request: AdaptiveTunerRequest):
    """Start an adaptive-tuner job (v1 or v2) and return a job id for polling."""
    return await service_run_adaptive_tuner(request, _build_adaptive_tuner_deps())


async def get_adaptive_tuner_job(job_id: str):
    """Get current status and results of an adaptive tuner job."""
    return service_get_adaptive_tuner_job(job_id, _build_adaptive_tuner_deps())


async def list_adaptive_tuner_jobs(limit: int = 20):
    """List recent adaptive tuner jobs."""
    return service_list_adaptive_tuner_jobs(_build_adaptive_tuner_deps(), limit)


async def start_run(request: StartRunRequest):
    """Start a new backtest run."""
    return await service_start_run(request, _build_start_run_deps())


async def prewarm_run(request: PrewarmRunRequest):
    """Prewarm run-start caches (bars/reference/L2) for a ticker/date range."""
    return await service_prewarm_run(request, _build_start_run_deps())


async def prewarm_status(request: PrewarmRunRequest):
    """Read-only prewarm status for a ticker/date payload key."""
    return await service_prewarm_status(request, _build_start_run_deps())


async def get_run_state(run_id: str, ticker: str, date: str):
    """Get current state of a run."""
    return service_get_run_state(run_id, ticker, date, _build_run_control_deps())


async def step_run(run_id: str, ticker: str, date: str):
    """Advance the run by one bar."""
    return await service_step_run(run_id, ticker, date, _build_run_control_deps())


async def play_run(
    run_id: str,
    ticker: str,
    date: str,
    request: Optional[PlayRequest] = Body(default=None),
    speed_ms: Optional[Union[int, str]] = None,
    raw_request: Request = None,
):
    """Start or resume auto-advancing through bars.
    - Accepts JSON body `{ "speed_ms": ... }` but also query param `speed_ms`.
    - Defaults to max speed when not provided.
    - If paused, simply resumes without restarting.
    """
    return await service_play_run(
        run_id,
        ticker,
        date,
        _build_run_control_deps(),
        request=request,
        speed_ms=speed_ms,
        raw_request=raw_request,
    )


async def pause_run(run_id: str, ticker: str, date: str):
    """Pause a running backtest."""
    return service_pause_run(run_id, ticker, date, _build_run_control_deps())


async def resume_run(run_id: str, ticker: str, date: str):
    """Resume a paused backtest."""
    return service_resume_run(run_id, ticker, date, _build_run_control_deps())


async def stop_run(run_id: str, ticker: str, date: str):
    """Stop a running backtest."""
    return service_stop_run(run_id, ticker, date, _build_run_control_deps())


async def restart_run(run_id: str, ticker: str, date: str):
    """Restart an existing run from bar zero using already loaded bars."""
    return await service_restart_run(run_id, ticker, date, _build_run_control_deps())


async def get_processed_bars(run_id: str, ticker: str, date: str):
    """Get all processed bars so far."""
    return service_get_processed_bars(run_id, ticker, date, _build_run_control_deps())


async def get_bar_details(run_id: str, ticker: str, date: str, minute_key: int):
    """Get 1-second intrabar frames for a specific minute bar.
    
    Args:
        run_id: The backtest run ID
        ticker: Stock ticker symbol
        date: Date in YYYY-MM-DD format
        minute_key: Unix timestamp of the minute bar start (in seconds)
    
    Returns:
        1-second frames with book/trade features for frontend visualization
    """
    return service_get_bar_details(run_id, ticker, date, minute_key, _build_run_control_deps())

async def get_markers(run_id: str, ticker: str, date: str, marker_type: Optional[str] = None):
    """Get all decision markers."""
    return service_get_markers(run_id, ticker, date, marker_type, _build_run_control_deps())


async def get_chart_annotations(run_id: str, ticker: str, date: str):
    """Get markers formatted for chart display."""
    return service_get_chart_annotations(run_id, ticker, date, _build_run_control_deps())


async def get_run_summary(run_id: str, ticker: str, date: str):
    """Get session summary."""
    return service_get_run_summary(run_id, ticker, date, _build_run_control_deps())


async def delete_run(run_id: str, ticker: str, date: str):
    """Delete a run from memory."""
    return await service_delete_run(run_id, ticker, date, _build_run_control_deps())


async def list_runs():
    """List all active runs."""
    return service_list_runs(_build_run_control_deps())


# ============ Static Files (Frontend) ============
frontend_path = Path(__file__).parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


# ============ Main ============
if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )
