"""
Unified Backtest Runner API Server.
Orchestrates the look-ahead free data feeding and strategy evaluation.
"""

import asyncio
import copy
import os
import random
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from fastapi import FastAPI, WebSocket, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import logging
from pathlib import Path
from uuid import uuid4

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
from src.momentum_diversification import (
    normalize_momentum_diversification_payload,
    build_regime_strategy_map_options,
    MICRO_REGIMES,
    ROUTE_KEYS,
    STRATEGY_FAMILY_MAP,
)
from src.normalization import (
    normalize_unified_profiles,
)
from src.aos_config import POSITIONING_CONFIG_KEYS
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
from src.routes.tcbbo_routes import router as tcbbo_router
from src.routes.chart_preview_routes import router as chart_preview_router
from src.models.config_requests import (
    AdaptiveTunerProfileApplyRequest,
    StrategyComboCaptureRequest,
    StrategyComboApplyRequest,
    UnifiedProfileCaptureRequest,
    UnifiedProfileApplyRequest,
    AOSUpdateRequest,
    PositioningUpdateRequest,
)
from src.models.run_requests import PlayRequest, PrewarmRunRequest, StartRunRequest
from src.models.tuner_requests import AdaptiveTunerRequest
from src.services.live_trader_service import (
    read_jsonl_tail,
    parse_utc_iso,
    discover_live_trader_runs,
    live_trader_events_payload,
    live_trader_snapshot_payload,
)
from src.services.run_registry import RunRegistry
from src.services.config_write_service import (
    ConfigWriteDeps,
    capture_unified_profile as service_capture_unified_profile,
    apply_unified_profile as service_apply_unified_profile,
    capture_strategy_combo as service_capture_strategy_combo,
    apply_strategy_combo as service_apply_strategy_combo,
    apply_adaptive_tuner_profile as service_apply_adaptive_tuner_profile,
)
from src.services.run_control_service import (
    RunControlDeps,
    get_markers as service_get_markers,
    delete_run as service_delete_run,
)
from src.services.adaptive_tuner_orchestration_service import (
    AdaptiveTunerOrchestrationDeps,
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
)
from src.services.strategy_api_session_service import (
    apply_orchestrator_config as service_apply_orchestrator_config,
    clear_remote_strategy_sessions as service_clear_remote_strategy_sessions,
    configure_session as service_configure_session,
    load_remote_checkpoint as service_load_remote_checkpoint,
    reset_remote_orchestrator_state as service_reset_remote_orchestrator_state,
    reset_remote_orchestrator_state_scoped as service_reset_remote_orchestrator_state_scoped,
    save_remote_checkpoint as service_save_remote_checkpoint,
)
from src.services.profile_options_service import (
    build_adaptive_tuner_options_payload as service_build_adaptive_tuner_options_payload,
    build_strategy_combo_options_payload as service_build_strategy_combo_options_payload,
    build_unified_profile_options_payload as service_build_unified_profile_options_payload,
)
from src.services.ws_hub_service import WebSocketHub
from src.services.local_config_service import LocalConfigService
from src.security.network_policy import (
    StrategyApiPolicyError,
    cors_allow_origins_from_env,
    enforce_strategy_url_allowlist_only,
    should_allow_credentials,
)
from src.routes.v2_routes import router as v2_router
from src.services.saas_bootstrap_service import (
    bootstrap_saas_runtime,
    parse_bool_value as service_parse_bool_value,
    safe_env_float as service_safe_env_float,
    safe_env_int as service_safe_env_int,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BacktestRunner")

# ============ App Setup ============
app = FastAPI(
    title="Unified Backtest Runner",
    description="Walk-forward backtesting with strategy evaluation and decision visualization",
    version="1.0.0",
)
_default_router_lifespan = app.router.lifespan_context

_cors_allow_origins = cors_allow_origins_from_env(
    env_name="BACKTEST_CORS_ALLOW_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173",
)
_cors_allow_origin_regex = str(
    os.getenv("BACKTEST_CORS_ALLOW_ORIGIN_REGEX", "") or ""
).strip()
if not _cors_allow_origin_regex:
    _cors_regex_patterns: List[str] = []
    _cors_regex_seen: set[str] = set()
    for _origin in _cors_allow_origins:
        try:
            _parsed_origin = urlparse(str(_origin))
        except Exception:
            continue
        _host = str(_parsed_origin.hostname or "").strip().lower()
        if not _host.endswith(".netlify.app"):
            continue
        # Allow:
        # - canonical site: https://<site>.netlify.app
        # - preview deploy: https://<deploy-id>--<site>.netlify.app
        _escaped_host = re.escape(_host)
        _pattern = rf"https://(?:[a-z0-9-]+--)?{_escaped_host}"
        if _pattern in _cors_regex_seen:
            continue
        _cors_regex_seen.add(_pattern)
        _cors_regex_patterns.append(_pattern)
    _cors_allow_origin_regex = (
        rf"^(?:{'|'.join(_cors_regex_patterns)})$" if _cors_regex_patterns else None
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins or ["http://localhost:5173"],
    allow_origin_regex=_cors_allow_origin_regex,
    allow_credentials=should_allow_credentials(_cors_allow_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Global State ============
data_loader = DataLoader()
l2_manager = L2DataManager()
l2_features = L2FeatureService(manager=l2_manager, logger=logger)
active_runners: Dict[str, SessionRunner] = {}
run_registry = RunRegistry(active_runners)
databento_svc = DatabentoService()
l2_manager.databento_service = databento_svc
adaptive_tuner_jobs: Dict[str, Dict[str, Any]] = {}
MAX_PARALLEL_ADAPTIVE_TUNERS = 3
adaptive_tuner_slots = asyncio.Semaphore(MAX_PARALLEL_ADAPTIVE_TUNERS)
adaptive_tuner_merge_lock = asyncio.Lock()
MAX_WS_CLIENTS = max(1, int(os.getenv("BACKTEST_MAX_WS_CLIENTS", "250")))
ws_hub = WebSocketHub(max_clients=MAX_WS_CLIENTS, logger=logger)
connected_clients: List[WebSocket] = ws_hub.clients
STRATEGY_OVERRIDES_PATH = Path(__file__).parent / "strategy_overrides.json"
AOS_CONFIG_PATH = Path(__file__).parent / "aos_optimization" / "aos_config.json"
POSITIONING_CONFIG_PATH = (
    Path(__file__).parent / "aos_optimization" / "positioning_config.json"
)
ADAPTIVE_TUNER_AOS_DIR = (
    Path(__file__).parent / "aos_optimization" / ".adaptive_tuner_aos"
)
LIVE_TRADER_ARTIFACTS_DIR = (
    Path(__file__).resolve().parent.parent / "ibkr-realtime-trader" / "artifacts"
)
MARKET_TZ = ZoneInfo("America/New_York")
LIVE_RUN_ACTIVE_WINDOW_SECONDS = 180
_startup_prewarm_task: Optional[asyncio.Task] = None


STARTUP_PREWARM_ENABLED = service_parse_bool_value(
    os.getenv("BACKTEST_STARTUP_PREWARM_ENABLED"),
    True,
)
STARTUP_PREWARM_TICKERS = list(
    dict.fromkeys(
        token.strip().upper()
        for token in str(os.getenv("BACKTEST_STARTUP_PREWARM_TICKERS", "MU") or "").split(
            ","
        )
        if token.strip()
    )
)
STARTUP_PREWARM_L2_CONFIRM = service_parse_bool_value(
    os.getenv("BACKTEST_STARTUP_PREWARM_L2_CONFIRM"),
    False,
)


def _run_startup_prewarm_request_sync(request: PrewarmRunRequest) -> Dict[str, Any]:
    """Run startup prewarm outside the main event loop."""
    return asyncio.run(service_prewarm_run(request, _build_start_run_deps()))


def _refresh_runtime_data_services() -> None:
    """Recreate data services after settings changes and keep legacy globals in sync."""
    global data_loader, l2_manager
    data_loader = DataLoader()
    l2_manager = L2DataManager()
    l2_manager.databento_service = databento_svc
    l2_features.manager = l2_manager
    api_services.data_loader = data_loader
    api_services.l2_manager = l2_manager
    api_services.l2_features = l2_features


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
    build_strategy_combo_options_payload=lambda ticker: service_build_strategy_combo_options_payload(
        ticker=ticker,
        load_aos_config=_load_aos_config,
        normalize_strategy_combo_profiles=_normalize_strategy_combo_profiles,
    ),
    load_aos_config=lambda: _load_aos_config(),
    load_positioning_config=lambda: _load_positioning_config(),
    merge_positioning_into_aos_snapshot=(
        lambda aos_cfg, pos_cfg: _local_config_service().merge_positioning_into_aos_snapshot(
            aos_config=aos_cfg,
            positioning_config=pos_cfg,
        )
    ),
    get_ticker_positioning_config=lambda ticker: _get_ticker_positioning_config(ticker),
    positioning_config_keys=POSITIONING_CONFIG_KEYS,
    build_adaptive_tuner_options_payload=lambda ticker: service_build_adaptive_tuner_options_payload(
        ticker=ticker,
        load_aos_config=_load_aos_config,
        normalize_tuner_profiles=_normalize_tuner_profiles,
        covered_days_for_schema=lambda ticker_upper, schema: service_covered_days_for_schema(
            ticker_upper,
            schema,
            databento_svc,
        ),
        range_summary_from_days=service_range_summary_from_days,
    ),
    build_unified_profile_options_payload=lambda ticker: _build_unified_profile_options_payload(
        ticker
    ),
    build_config_write_deps=lambda: _build_config_write_deps(),
    build_run_control_deps=lambda: _build_run_control_deps(),
    build_adaptive_tuner_deps=lambda: _build_adaptive_tuner_deps(),
    start_run=lambda request: start_run(request),
    prewarm_run=lambda request: prewarm_run(request),
    prewarm_status=lambda request: prewarm_status(request),
    broadcast=lambda message: broadcast(message),
    refresh_runtime_data_services=_refresh_runtime_data_services,
    reset_discovery=reset_discovery,
)
app.state.api_services = api_services


_safe_env_int = service_safe_env_int
_safe_env_float = service_safe_env_float
_parse_bool_value = service_parse_bool_value


_saas_bootstrap = bootstrap_saas_runtime(
    logger=logger,
    project_root=Path(__file__).resolve().parent,
)
v2_services = _saas_bootstrap.v2_services
_run_reports_store = _saas_bootstrap.run_reports_store
_run_reports_source_mode = _saas_bootstrap.run_reports_source_mode
runtime_metrics = _saas_bootstrap.runtime_metrics
_supabase_user_settings_store = _saas_bootstrap.supabase_user_settings_store

if _supabase_user_settings_store is not None:
    logger.info("v2 user settings store: Supabase (external)")
else:
    logger.info("v2 user settings store: SQLite (local)")

if _run_reports_source_mode == "supabase_run_reports":
    logger.info("run reports store: Supabase (external)")
elif _run_reports_source_mode == "sqlite_run_reports":
    logger.info("run reports store: SQLite (local)")
else:
    logger.info("run reports store: Filesystem only")

app.state.v2_services = v2_services
app.state.run_reports_store = _run_reports_store
app.state.run_reports_source_mode = _run_reports_source_mode
app.state.runtime_metrics = runtime_metrics
app.state.connected_clients = connected_clients
app.state.max_ws_clients = MAX_WS_CLIENTS


@app.middleware("http")
async def _collect_http_runtime_metrics(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = int(getattr(response, "status_code", 500))
        return response
    except Exception:
        status_code = 500
        raise
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        runtime_metrics.record_http(duration_ms=elapsed_ms, status_code=status_code)


def _build_config_write_deps() -> ConfigWriteDeps:
    """Build deps lazily so monkeypatched globals in tests are respected."""
    return ConfigWriteDeps(
        load_aos_config=lambda: _load_aos_config(),
        save_aos_config=lambda cfg: _save_aos_config(cfg),
        load_positioning_config=lambda: _load_positioning_config(),
        save_positioning_config=lambda cfg: _save_positioning_config(cfg),
        get_ticker_positioning_config=_get_ticker_positioning_config,
        normalize_strategy_combo_profiles=_normalize_strategy_combo_profiles,
        normalize_unified_profiles=_normalize_unified_profiles,
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
        run_reports_store=_run_reports_store,
        save_remote_checkpoint=_save_remote_checkpoint,
        clear_remote_strategy_sessions=_clear_remote_strategy_sessions,
        configure_session=_configure_session,
        l2_manager=getattr(api_services, "l2_manager", None),
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
        apply_orchestrator_config=_apply_orchestrator_config,
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
        normalize_unified_profiles=_normalize_unified_profiles,
        normalize_tuner_profiles=_normalize_tuner_profiles,
        normalize_strategy_selection_mode=_normalize_strategy_selection_mode,
        normalize_clamped_int=_normalize_clamped_int,
        normalize_momentum_diversification_payload=_normalize_momentum_diversification_payload,
        load_aos_config=_load_aos_config,
        get_ticker_positioning_config=_get_ticker_positioning_config,
        positioning_config_keys=POSITIONING_CONFIG_KEYS,
        apply_strategy_param_map=_apply_strategy_param_map,
        apply_orchestrator_config=_apply_orchestrator_config,
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
        apply_strategy_param_map=_apply_strategy_param_map,
        fetch_remote_strategies=_fetch_remote_strategies,
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


@asynccontextmanager
async def _app_lifespan(_: FastAPI):
    async with _default_router_lifespan(_):
        global _startup_prewarm_task
        if _startup_prewarm_task is None or _startup_prewarm_task.done():
            _startup_prewarm_task = asyncio.create_task(_run_startup_prewarm())
        try:
            yield
        finally:
            task = _startup_prewarm_task
            _startup_prewarm_task = None
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


app.router.lifespan_context = _app_lifespan

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


def _local_config_service() -> LocalConfigService:
    return LocalConfigService(
        default_aos_path=AOS_CONFIG_PATH,
        default_positioning_path=POSITIONING_CONFIG_PATH,
        load_json_file=load_json_file,
        save_json_file=save_json_file,
        positioning_config_keys=POSITIONING_CONFIG_KEYS,
        logger=logger,
    )


def _resolve_aos_config_path(
    aos_config_path: Optional[Union[str, Path]] = None,
) -> Path:
    return _local_config_service().resolve_aos_config_path(aos_config_path)


def _load_aos_config(
    aos_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    return _local_config_service().load_aos_config(aos_config_path)


def _load_positioning_config(
    positioning_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    return _local_config_service().load_positioning_config(positioning_config_path)


def _save_positioning_config(
    config: Dict[str, Any],
    positioning_config_path: Optional[Union[str, Path]] = None,
) -> bool:
    return _local_config_service().save_positioning_config(
        config, positioning_config_path
    )


def _get_ticker_positioning_config(
    ticker: str,
    positioning_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _local_config_service().get_ticker_positioning_config(
        ticker=ticker,
        positioning_config=positioning_config,
    )


def _save_aos_config(
    config: Dict[str, Any],
    aos_config_path: Optional[Union[str, Path]] = None,
) -> bool:
    return _local_config_service().save_aos_config(config, aos_config_path)


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


def _cleanup_isolated_tuner_aos_config(
    aos_config_path: Optional[Union[str, Path]],
) -> None:
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


def _read_jsonl_tail(path: Path, limit: int = 200) -> List[Dict[str, Any]]:
    return read_jsonl_tail(path, limit=limit, logger=logger)


def _parse_utc_iso(value: Any) -> Optional[datetime]:
    return parse_utc_iso(value)


def _discover_live_trader_runs(
    limit: int = 20, active_only: bool = False
) -> List[Dict[str, Any]]:
    return discover_live_trader_runs(
        LIVE_TRADER_ARTIFACTS_DIR,
        limit=limit,
        active_only=active_only,
        active_window_seconds=LIVE_RUN_ACTIVE_WINDOW_SECONDS,
        logger=logger,
    )


_normalize_strategy_selection_mode = service_normalize_strategy_selection_mode
_normalize_non_negative_int = service_normalize_non_negative_int
_normalize_clamped_int = service_normalize_clamped_int
_normalize_bool_options = service_normalize_bool_options
_normalize_int_options = service_normalize_int_options
_normalize_mode_options = service_normalize_mode_options
_normalize_float_options = service_normalize_float_options
_normalize_strategy_sets = service_normalize_strategy_sets
_normalize_regime_filter_sets = service_normalize_regime_filter_sets
_normalize_time_window_sets = service_normalize_time_window_sets


def _normalize_regime_strategy_map_sets(
    raw_sets: Optional[List[Optional[Dict[str, List[str]]]]],
    enabled_strategies: List[str],
) -> List[Optional[Dict[str, List[str]]]]:
    return service_normalize_regime_strategy_map_sets(
        raw_sets,
        enabled_strategies,
        _build_regime_strategy_map_options,
    )


_iter_date_strings = service_iter_date_strings
_as_iso_day_set = service_as_iso_day_set


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


_sample_evenly_spaced_days = service_sample_evenly_spaced_days
_resolve_tuner_trial_budget = service_resolve_tuner_trial_budget


_normalize_tuner_profiles = service_normalize_tuner_profiles
_sanitize_strategy_params = service_sanitize_strategy_params
_extract_strategy_params_for_profile = service_extract_strategy_params_for_profile
_normalize_strategy_combo_profiles = service_normalize_strategy_combo_profiles
_normalize_unified_profiles = normalize_unified_profiles


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


def _build_unified_profile_options_payload(ticker: str) -> Dict[str, Any]:
    return service_build_unified_profile_options_payload(
        ticker=ticker,
        load_aos_config=_load_aos_config,
        normalize_unified_profiles=_normalize_unified_profiles,
        normalize_strategy_combo_profiles=_normalize_strategy_combo_profiles,
        normalize_tuner_profiles=_normalize_tuner_profiles,
        normalize_strategy_selection_mode=_normalize_strategy_selection_mode,
        normalize_clamped_int=_normalize_clamped_int,
        get_ticker_positioning_config=_get_ticker_positioning_config,
        parse_utc_iso=_parse_utc_iso,
    )


_build_tuner_profile_entry = service_build_tuner_profile_entry


_build_adaptive_candidate_config = service_build_adaptive_candidate_config
_compute_tuner_score = service_compute_tuner_score
_compute_tuner_score_robust = service_compute_tuner_score_robust


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


_normalize_strategy_key = service_normalize_strategy_key


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


async def _apply_global_trailing(
    strategy_api_url: str,
    trailing_stop_pct: Optional[float],
    **kwargs: Any,
) -> None:
    return await service_apply_global_trailing(
        strategy_api_url,
        trailing_stop_pct,
        _build_strategy_api_integration_deps(),
        **kwargs,
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
    intraday_levels_enabled: bool = True,
    intraday_levels_swing_left_bars: int = 2,
    intraday_levels_swing_right_bars: int = 2,
    intraday_levels_test_tolerance_pct: float = 0.08,
    intraday_levels_break_tolerance_pct: float = 0.05,
    intraday_levels_breakout_volume_lookback: int = 20,
    intraday_levels_breakout_volume_multiplier: float = 1.2,
    intraday_levels_volume_profile_bin_size_pct: float = 0.05,
    intraday_levels_value_area_pct: float = 0.70,
    intraday_levels_entry_quality_enabled: bool = True,
    intraday_levels_min_levels_for_context: int = 2,
    intraday_levels_entry_tolerance_pct: float = 0.10,
    intraday_levels_break_cooldown_bars: int = 6,
    intraday_levels_rotation_max_tests: int = 2,
    intraday_levels_rotation_volume_max_ratio: float = 0.95,
    intraday_levels_recent_bounce_lookback_bars: int = 6,
    intraday_levels_require_recent_bounce_for_mean_reversion: bool = True,
    intraday_levels_momentum_break_max_age_bars: int = 3,
    intraday_levels_momentum_min_room_pct: float = 0.30,
    intraday_levels_momentum_min_broken_ratio: float = 0.30,
    intraday_levels_min_confluence_score: int = 2,
    intraday_levels_memory_enabled: bool = True,
    intraday_levels_memory_min_tests: int = 2,
    intraday_levels_memory_max_age_days: int = 5,
    intraday_levels_memory_decay_after_days: int = 2,
    intraday_levels_memory_decay_weight: float = 0.50,
    intraday_levels_memory_max_levels: int = 12,
    intraday_levels_opening_range_enabled: bool = True,
    intraday_levels_opening_range_minutes: int = 30,
    intraday_levels_opening_range_break_tolerance_pct: float = 0.05,
    intraday_levels_poc_migration_enabled: bool = True,
    intraday_levels_poc_migration_interval_bars: int = 30,
    intraday_levels_poc_migration_trend_threshold_pct: float = 0.20,
    intraday_levels_poc_migration_range_threshold_pct: float = 0.10,
    intraday_levels_composite_profile_enabled: bool = True,
    intraday_levels_composite_profile_days: int = 3,
    intraday_levels_composite_profile_current_day_weight: float = 1.0,
    cold_start_each_day: bool = False,
    strategy_selection_mode: str = "adaptive_top_n",
    max_active_strategies: int = 3,
    momentum_diversification_json: Optional[str] = None,
    max_daily_trades: Optional[int] = None,
    mu_choppy_hard_block_enabled: Optional[bool] = None,
    regime_filter: Optional[list] = None,
    **extra_session_params: Any,
) -> None:
    session_kwargs = {
        key: value for key, value in locals().items() if key != "extra_session_params"
    }
    if extra_session_params:
        session_kwargs.update(extra_session_params)
    session_kwargs["deps"] = _build_strategy_api_integration_deps()
    return await service_configure_session(**session_kwargs)


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


async def _apply_orchestrator_config(
    strategy_api_url: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    return await service_apply_orchestrator_config(
        strategy_api_url,
        config,
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
) -> tuple[Dict[int, Dict[str, Any]], Dict[str, Any]]:
    return l2_features.build_feature_map(
        ticker=ticker,
        start_dt_utc=start_dt_utc,
        end_dt_utc=end_dt_utc,
    )


def _attach_l2_features(
    bars: List[Dict[str, Any]],
    feature_map: Dict[int, Dict[str, Any]],
    l2_only: bool = False,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return l2_features.attach_features(
        bars=bars,
        feature_map=feature_map,
        l2_only=l2_only,
    )


def _normalize_l2_feature_map_for_market_day_sessions(
    feature_map: Dict[int, Dict[str, Any]],
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
                0.0
                if prev_book_pressure is None
                else (book_pressure - prev_book_pressure)
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
    await ws_hub.broadcast(message)


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await ws_hub.handle_connection(websocket)


_candidate_key = service_candidate_key
_build_adaptive_tuner_search_space = service_build_adaptive_tuner_search_space
_build_grid_candidates = service_build_grid_candidates
_build_random_candidates = service_build_random_candidates


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
app.include_router(v2_router)
app.include_router(tcbbo_router)
app.include_router(chart_preview_router)


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


async def capture_strategy_combo(request: StrategyComboCaptureRequest):
    """Capture current strategy API settings into a saved ticker combo profile."""
    return await service_capture_strategy_combo(request, _build_config_write_deps())


async def capture_unified_profile(request: UnifiedProfileCaptureRequest):
    """Capture current strategy/execution settings into a unified profile."""
    return await service_capture_unified_profile(request, _build_config_write_deps())


async def apply_strategy_combo(request: StrategyComboApplyRequest):
    """Set active strategy combo profile and optionally apply it to strategy API immediately."""
    return await service_apply_strategy_combo(request, _build_config_write_deps())


async def apply_unified_profile(request: UnifiedProfileApplyRequest):
    """Set active unified profile and optionally apply strategy/execution settings."""
    return await service_apply_unified_profile(request, _build_config_write_deps())


async def get_ticker_positioning_config(ticker: str):
    """Get positioning config for one ticker."""
    return _get_ticker_positioning_config(ticker)


async def apply_adaptive_tuner_profile(request: AdaptiveTunerProfileApplyRequest):
    """Apply a saved adaptive-tuner profile into active ticker AOS settings."""
    return service_apply_adaptive_tuner_profile(request, _build_config_write_deps())


async def run_adaptive_tuner(request: AdaptiveTunerRequest):
    """Start an adaptive-tuner job (v1 or v2) and return a job id for polling."""
    try:
        request.strategy_api_url = enforce_strategy_url_allowlist_only(
            request.strategy_api_url
        )
    except StrategyApiPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await service_run_adaptive_tuner(request, _build_adaptive_tuner_deps())


async def start_run(request: StartRunRequest):
    """Start a new backtest run."""
    try:
        request.strategy_api_url = enforce_strategy_url_allowlist_only(
            request.strategy_api_url
        )
    except StrategyApiPolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await service_start_run(request, _build_start_run_deps())


async def prewarm_run(request: PrewarmRunRequest):
    """Prewarm run-start caches (bars/reference/L2) for a ticker/date range."""
    return await service_prewarm_run(request, _build_start_run_deps())


async def prewarm_status(request: PrewarmRunRequest):
    """Read-only prewarm status for a ticker/date payload key."""
    return await service_prewarm_status(request, _build_start_run_deps())


async def get_markers(
    run_id: str, ticker: str, date: str, marker_type: Optional[str] = None
):
    """Get all decision markers."""
    return service_get_markers(
        run_id, ticker, date, marker_type, _build_run_control_deps()
    )


async def delete_run(run_id: str, ticker: str, date: str):
    """Delete a run from memory."""
    return await service_delete_run(run_id, ticker, date, _build_run_control_deps())


# ============ Static Files (Frontend) ============
frontend_path = Path(__file__).parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount(
        "/", StaticFiles(directory=str(frontend_path), html=True), name="frontend"
    )


# ============ Main ============
if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8002, reload=True)
