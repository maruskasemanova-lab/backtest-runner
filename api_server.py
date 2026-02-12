"""
Unified Backtest Runner API Server.
Orchestrates the look-ahead free data feeding and strategy evaluation.
"""
import asyncio
import copy
import json
import random
from datetime import datetime, timedelta, timezone
from itertools import product
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
import aiohttp
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
    normalize_strategy_key,
)
from src.aos_config import (
    load_aos_config,
    save_aos_config,
    load_positioning_config,
    save_positioning_config,
    get_ticker_positioning_config,
    POSITIONING_CONFIG_KEYS,
)
from src.session_config import (
    configure_session,
    clear_remote_strategy_sessions,
    reset_remote_orchestrator_state,
    load_remote_checkpoint,
    save_remote_checkpoint,
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
from src.models.run_requests import PlayRequest, StartRunRequest
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
        configure_session=_configure_session,
        broadcast=broadcast,
        run_config_cls=RunConfig,
        session_runner_cls=SessionRunner,
    )

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
    normalized = str(mode or "adaptive_top_n").strip().lower()
    return "all_enabled" if normalized == "all_enabled" else "adaptive_top_n"


def _normalize_non_negative_int(value: Any, default: int = 0, max_value: int = 10_000) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(0, min(max_value, parsed))


def _normalize_clamped_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(min_value, min(max_value, parsed))


def _normalize_bool_options(values: Optional[List[bool]], default: List[bool]) -> List[bool]:
    if not isinstance(values, list) or not values:
        return list(default)
    normalized = []
    seen = set()
    for value in values:
        current = bool(value)
        if current in seen:
            continue
        seen.add(current)
        normalized.append(current)
    return normalized or list(default)


def _normalize_int_options(
    values: Optional[List[int]],
    default: List[int],
    *,
    min_value: int,
    max_value: int,
) -> List[int]:
    if not isinstance(values, list) or not values:
        return list(default)
    normalized = []
    seen = set()
    for value in values:
        current = _normalize_clamped_int(value, default[0], min_value, max_value)
        if current in seen:
            continue
        seen.add(current)
        normalized.append(current)
    return normalized or list(default)


def _normalize_mode_options(values: Optional[List[str]]) -> List[str]:
    defaults = ["adaptive_top_n", "all_enabled"]
    if not isinstance(values, list) or not values:
        return defaults
    normalized = []
    seen = set()
    for value in values:
        mode = _normalize_strategy_selection_mode(value)
        if mode in seen:
            continue
        seen.add(mode)
        normalized.append(mode)
    return normalized or defaults


def _normalize_float_options(
    values: Optional[List[float]],
    default: List[float],
    *,
    min_value: float = 0.0,
    max_value: float = 1_000_000.0,
) -> List[float]:
    if not isinstance(values, list) or not values:
        return list(default)
    normalized = []
    seen = set()
    for value in values:
        try:
            current = float(value)
        except (TypeError, ValueError):
            current = default[0] if default else 0.0
        current = max(min_value, min(max_value, current))
        rounded = round(current, 6)
        if rounded in seen:
            continue
        seen.add(rounded)
        normalized.append(rounded)
    return normalized or list(default)


def _normalize_strategy_sets(
    raw_sets: Optional[List[List[str]]],
    enabled_strategies: List[str],
) -> List[List[str]]:
    """Normalize strategy sets for v2 search. Returns list of sorted strategy lists."""
    if not isinstance(raw_sets, list) or not raw_sets:
        # Default: each single strategy + the full enabled set
        defaults = [[s] for s in enabled_strategies]
        if len(enabled_strategies) > 1:
            defaults.append(sorted(enabled_strategies))
        return defaults or [["momentum_flow"]]
    normalized = []
    seen = set()
    for strategy_set in raw_sets:
        if not isinstance(strategy_set, list) or not strategy_set:
            continue
        cleaned = sorted(set(str(s).strip().lower() for s in strategy_set if str(s).strip()))
        if not cleaned:
            continue
        key = tuple(cleaned)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized or [[s] for s in enabled_strategies] or [["momentum_flow"]]


def _normalize_regime_filter_sets(
    raw_sets: Optional[List[List[str]]],
) -> List[List[str]]:
    """Normalize regime filter sets for v2 search."""
    valid_regimes = {"TRENDING", "CHOPPY", "MIXED"}
    defaults = [
        ["TRENDING"],
        ["TRENDING", "MIXED"],
        ["TRENDING", "MIXED", "CHOPPY"],
    ]
    if not isinstance(raw_sets, list) or not raw_sets:
        return defaults
    normalized = []
    seen = set()
    for regime_set in raw_sets:
        if not isinstance(regime_set, list) or not regime_set:
            continue
        cleaned = sorted(set(str(r).strip().upper() for r in regime_set if str(r).strip().upper() in valid_regimes))
        if not cleaned:
            continue
        key = tuple(cleaned)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized or defaults


def _normalize_time_window_sets(
    raw_sets: Optional[List[List[int]]],
) -> List[List[int]]:
    """Normalize time window sets for v2 search.

    Each set is a list of allowed trading hours (0-23).
    Default windows: morning-only, extended morning, full day.
    """
    defaults = [
        [9, 10],           # Morning momentum only
        [9, 10, 11, 12],   # Morning session
        [9, 10, 11, 12, 13, 14, 15],  # Full trading day (no filter)
    ]
    if not isinstance(raw_sets, list) or not raw_sets:
        return defaults
    normalized = []
    seen = set()
    for tw in raw_sets:
        if not isinstance(tw, list) or not tw:
            continue
        cleaned = sorted(set(
            h for h in (int(x) for x in tw if isinstance(x, (int, float)))
            if 0 <= h <= 23
        ))
        if not cleaned:
            continue
        key = tuple(cleaned)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized or defaults


def _normalize_regime_strategy_map_sets(
    raw_sets: Optional[List[Optional[Dict[str, List[str]]]]],
    enabled_strategies: List[str],
) -> List[Optional[Dict[str, List[str]]]]:
    """Normalize v2 regime->strategy map sets.

    Always includes ``None`` as the first option (flat mode).
    """
    defaults = _build_regime_strategy_map_options(enabled_strategies)
    if not isinstance(raw_sets, list) or not raw_sets:
        return defaults

    allowed = {
        str(name).strip().lower()
        for name in enabled_strategies
        if str(name).strip()
    }
    normalized: List[Optional[Dict[str, List[str]]]] = []
    seen_maps = set()
    has_flat_mode = False

    for raw_map in raw_sets:
        if raw_map is None:
            has_flat_mode = True
            continue
        if not isinstance(raw_map, dict):
            continue

        cleaned_map: Dict[str, List[str]] = {}
        for regime in ("TRENDING", "MIXED", "CHOPPY"):
            raw_values = raw_map.get(regime, [])
            cleaned_values: List[str] = []
            seen_values = set()
            if isinstance(raw_values, list):
                for value in raw_values:
                    strategy_key = str(value).strip().lower()
                    if not strategy_key or strategy_key in seen_values:
                        continue
                    if allowed and strategy_key not in allowed:
                        continue
                    seen_values.add(strategy_key)
                    cleaned_values.append(strategy_key)
            cleaned_map[regime] = cleaned_values

        if not any(cleaned_map.values()):
            continue

        map_key = json.dumps(cleaned_map, sort_keys=True)
        if map_key in seen_maps:
            continue
        seen_maps.add(map_key)
        normalized.append(cleaned_map)

    if not normalized and not has_flat_mode:
        return defaults
    # Keep backward-compatible flat mode available in every search.
    return [None] + normalized


def _iter_date_strings(date_from: str, date_to: str) -> List[str]:
    try:
        start_dt = datetime.strptime(date_from, "%Y-%m-%d")
        end_dt = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(400, f"Invalid date format: {exc}")
    if end_dt < start_dt:
        raise HTTPException(400, "date_to must be on or after date_from")
    dates: List[str] = []
    current = start_dt
    while current <= end_dt:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates


def _as_iso_day_set(days: List[str]) -> set:
    out = set()
    for day in days:
        value = str(day or "").strip()
        if not value:
            continue
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            continue
        out.add(value)
    return out


def _resolve_l2_tuning_dates(
    *,
    ticker: str,
    date_from: str,
    date_to: str,
    l2_required: bool,
) -> List[str]:
    requested_days = _iter_date_strings(date_from, date_to)
    if not l2_required:
        return requested_days

    ohlcv_cov = databento_svc.get_range_coverage(
        ticker=ticker,
        schema="ohlcv-1m",
        start_date=date_from,
        end_date=date_to,
    )
    l2_cov = databento_svc.get_range_coverage(
        ticker=ticker,
        schema="mbp-10",
        start_date=date_from,
        end_date=date_to,
    )
    ohlcv_days = _as_iso_day_set(ohlcv_cov.get("covered_days", []))
    l2_days = _as_iso_day_set(l2_cov.get("covered_days", []))
    overlap_days = sorted(ohlcv_days.intersection(l2_days))
    return overlap_days


def _sample_evenly_spaced_days(days: List[str], *, max_days: int) -> List[str]:
    """Pick a representative subset of ISO days while preserving chronology."""
    ordered_days = sorted(_as_iso_day_set(days))
    if not ordered_days:
        return []
    max_days = _normalize_clamped_int(max_days, default=2, min_value=1, max_value=30)
    if len(ordered_days) <= max_days:
        return ordered_days
    if max_days == 1:
        return [ordered_days[len(ordered_days) // 2]]

    picks = []
    for idx in range(max_days):
        # Spread picks across the full range and preserve endpoints.
        raw_index = round(idx * (len(ordered_days) - 1) / (max_days - 1))
        picks.append(ordered_days[int(raw_index)])
    return sorted(set(picks))


def _resolve_tuner_trial_budget(
    *,
    requested_trials: Any,
    default_trials: int,
    quick_mode: bool,
    quick_trial_boost: Any,
    max_trials: int = 400,
) -> Dict[str, int]:
    requested = _normalize_clamped_int(
        requested_trials, default=default_trials, min_value=1, max_value=max_trials
    )
    boost = 1
    if quick_mode:
        boost = _normalize_clamped_int(
            quick_trial_boost, default=3, min_value=1, max_value=10
        )
    effective = min(max_trials, requested * boost)
    return {"requested": requested, "boost": boost, "effective": effective}


def _covered_days_for_schema(ticker: str, schema: str) -> List[str]:
    ticker_upper = str(ticker or "").upper().strip()
    schema_lower = str(schema or "").lower().strip()
    if not ticker_upper or not schema_lower:
        return []

    entries = databento_svc.list_catalog(refresh=False, ticker=ticker_upper)
    days = set()
    for entry in entries:
        if str(entry.get("status", "")).lower() != "ready":
            continue
        if str(entry.get("schema", "")).lower() != schema_lower:
            continue

        preferred_file = databento_svc._preferred_entry_file(entry)
        preferred_path = databento_svc._resolve_entry_path(preferred_file)
        if not preferred_path or not preferred_path.exists():
            continue

        start_date = str(entry.get("start_date", "")).strip()
        end_date = str(entry.get("end_date", "")).strip()
        if schema_lower.startswith("ohlcv-"):
            start_date, end_date = databento_svc._effective_entry_range(entry)

        try:
            for day in databento_svc._iter_days(start_date, end_date):
                days.add(day)
        except Exception:
            continue

    return sorted(days)


def _range_summary_from_days(days: List[str]) -> Dict[str, Any]:
    day_list = sorted(_as_iso_day_set(days))
    if not day_list:
        return {"start": None, "end": None, "total_days": 0}
    return {
        "start": day_list[0],
        "end": day_list[-1],
        "total_days": len(day_list),
    }


def _normalize_tuner_profiles(raw_profiles: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_profiles, list):
        return []
    profiles = []
    for item in raw_profiles:
        if not isinstance(item, dict):
            continue
        profile_id = str(item.get("profile_id", "")).strip()
        candidate = item.get("candidate")
        if not profile_id or not isinstance(candidate, dict):
            continue
        profiles.append(dict(item))
    profiles.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
    return profiles


def _sanitize_strategy_params(params: Any) -> Dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    sanitized: Dict[str, Any] = {}
    for raw_key, value in params.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        if key == "allowed_regimes":
            if not isinstance(value, list):
                continue
            seen = set()
            regimes: List[str] = []
            for item in value:
                regime = str(item or "").strip().upper()
                if regime not in {"TRENDING", "CHOPPY", "MIXED"}:
                    continue
                if regime in seen:
                    continue
                seen.add(regime)
                regimes.append(regime)
            if regimes:
                sanitized[key] = regimes
            continue
        if isinstance(value, (bool, int, float, str)) or value is None:
            sanitized[key] = value
    return sanitized


def _extract_strategy_params_for_profile(strategies_payload: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(strategies_payload, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    skip_fields = {
        "display_name",
        "name",
        "open_positions",
        "total_signals",
        "last_signal",
        "regimes",
    }
    for raw_name, cfg in strategies_payload.items():
        strat_name = str(raw_name or "").strip()
        if not strat_name or not isinstance(cfg, dict):
            continue
        draft = {key: value for key, value in cfg.items() if key not in skip_fields}
        if "allowed_regimes" not in draft and isinstance(cfg.get("regimes"), list):
            draft["allowed_regimes"] = cfg.get("regimes")
        sanitized = _sanitize_strategy_params(draft)
        if sanitized:
            out[strat_name] = sanitized
    return out


def _normalize_strategy_combo_profiles(raw_profiles: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_profiles, list):
        return []
    profiles: List[Dict[str, Any]] = []
    for row in raw_profiles:
        if not isinstance(row, dict):
            continue
        profile_id = str(row.get("profile_id", "")).strip()
        profile_name = str(row.get("profile_name", "")).strip()
        strategy_params = row.get("strategy_params")
        if not profile_id or not isinstance(strategy_params, dict):
            continue
        normalized_strategy_params: Dict[str, Dict[str, Any]] = {}
        for raw_name, params in strategy_params.items():
            strat_name = str(raw_name or "").strip()
            if not strat_name:
                continue
            clean = _sanitize_strategy_params(params)
            if clean:
                normalized_strategy_params[strat_name] = clean
        if not normalized_strategy_params:
            continue
        profiles.append(
            {
                "profile_id": profile_id,
                "profile_name": profile_name or profile_id,
                "created_at": str(row.get("created_at", "")),
                "updated_at": str(row.get("updated_at", "")),
                "strategy_params": normalized_strategy_params,
            }
        )
    profiles.sort(
        key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
        reverse=True,
    )
    return profiles


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
    now = datetime.utcnow().isoformat() + "Z"
    best_candidate = best_trial.get("candidate", {})
    metrics = best_trial.get("metrics", {})
    return {
        "profile_id": uuid4().hex[:12],
        "created_at": now,
        "ticker": ticker,
        "adaptive_version": int(request.adaptive_version),
        "method": str(method_used or request.method or "grid"),
        "score_metric": str(request.score_metric or "pnl_pct"),
        "score": float(best_trial.get("score", 0.0) or 0.0),
        "date_from": dates[0] if dates else request.date_from,
        "date_to": dates[-1] if dates else request.date_to,
        "evaluated_days": len(dates),
        "l2_required": bool(request.l2_required),
        "l2_only": bool(request.l2_only),
        "quick_mode": bool(request.quick_mode),
        "quick_max_days": _normalize_clamped_int(
            request.quick_max_days, default=2, min_value=1, max_value=30
        ),
        "quick_trial_boost": _normalize_clamped_int(
            request.quick_trial_boost, default=3, min_value=1, max_value=10
        ),
        "candidate": dict(best_candidate) if isinstance(best_candidate, dict) else {},
        "metrics": dict(metrics) if isinstance(metrics, dict) else {},
    }


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
    cfg = copy.deepcopy(ticker_config)
    cfg["strategy_selection_mode"] = _normalize_strategy_selection_mode(
        candidate.get("strategy_selection_mode")
    )
    cfg["max_active_strategies"] = _normalize_clamped_int(
        candidate.get("max_active_strategies"), default=3, min_value=1, max_value=20
    )

    adaptive_cfg = cfg.get("adaptive", {})
    if not isinstance(adaptive_cfg, dict):
        adaptive_cfg = {}
    adaptive_cfg["version"] = int(adaptive_version)
    adaptive_cfg["flow_bias_enabled"] = bool(candidate.get("flow_bias_enabled", True))
    adaptive_cfg["use_ohlcv_fallbacks"] = bool(candidate.get("use_ohlcv_fallbacks", True))
    adaptive_cfg["min_active_bars_before_switch"] = _normalize_non_negative_int(
        candidate.get("min_active_bars_before_switch"), default=0, max_value=500
    )
    adaptive_cfg["switch_cooldown_bars"] = _normalize_non_negative_int(
        candidate.get("switch_cooldown_bars"), default=0, max_value=500
    )
    cfg["adaptive"] = adaptive_cfg
    return cfg


def _compute_tuner_score(
    score_metric: str,
    total_pnl_pct: float,
    total_pnl_dollars: float,
    avg_win_rate_pct: float,
    total_trades: int,
    valid_days: int,
) -> float:
    if valid_days <= 0:
        return -1_000_000.0
    avg_pnl_pct = total_pnl_pct / valid_days
    avg_pnl_dollars = total_pnl_dollars / valid_days
    trade_density = total_trades / valid_days
    metric = str(score_metric or "pnl_pct").strip().lower()
    if metric == "pnl_dollars":
        base = avg_pnl_dollars
    elif metric == "win_rate":
        base = avg_win_rate_pct
    elif metric == "trade_adjusted":
        base = avg_pnl_pct + min(5.0, trade_density * 0.2)
    else:
        base = avg_pnl_pct
    if total_trades <= 0:
        return base - 1.0
    return base


def _compute_tuner_score_robust(
    day_results: List[Dict[str, Any]],
) -> float:
    """Robust scoring that penalizes overfit by requiring consistency across days.

    Components:
    1. Consistency penalty: high day-to-day PnL variance = overfit
    2. Win-rate floor: < 40% overall → heavy penalty
    3. Positive-day ratio: must be profitable on ≥50% of days
    4. Trade-count normalization: don't reward raw trade count
    """
    valid = [d for d in day_results if d.get("success")]
    if not valid:
        return -1_000_000.0

    n_days = len(valid)
    daily_pnl = [float(d.get("pnl_pct", 0.0)) for d in valid]
    daily_trades = [int(d.get("trades", 0)) for d in valid]
    daily_wr = [float(d.get("win_rate_pct", 0.0)) for d in valid]

    total_trades = sum(daily_trades)
    if total_trades <= 0:
        return -1.0

    # — Average daily PnL (base metric) —
    avg_pnl = sum(daily_pnl) / n_days

    # — 1. Consistency factor (coefficient of variation penalty) —
    # Low CV = consistent across days = likely real edge
    # High CV = volatile across days = likely noise
    mean_abs = max(abs(avg_pnl), 0.001)
    variance = sum((p - avg_pnl) ** 2 for p in daily_pnl) / n_days
    std_dev = variance ** 0.5
    cv = std_dev / mean_abs  # coefficient of variation
    consistency = 1.0 / (1.0 + cv)  # 0→1, higher = more consistent

    # — 2. Expectancy-based quality gate —
    # Uses per-trade PnL as expectancy proxy.  This correctly values strategies
    # with low win-rate but high risk-reward (e.g. 40% WR / 2.5:1 RR).
    daily_expectancy = []
    for d in valid:
        pnl = float(d.get("pnl_pct", 0.0))
        trades = max(int(d.get("trades", 0)), 1)
        daily_expectancy.append(pnl / trades)

    avg_expectancy = (
        sum(daily_expectancy) / len(daily_expectancy) if daily_expectancy else 0.0
    )
    if avg_expectancy < -0.05:
        quality_gate = 0.3   # losing per trade → heavy penalty
    elif avg_expectancy < 0.0:
        quality_gate = 0.6   # marginal negative → moderate penalty
    elif avg_expectancy < 0.02:
        quality_gate = 0.85  # marginal positive → slight discount
    else:
        quality_gate = 1.0   # clearly positive expectancy → no penalty

    # — 3. Positive-day ratio —
    positive_days = sum(1 for p in daily_pnl if p > 0)
    positive_ratio = positive_days / n_days
    if positive_ratio < 0.50:
        # Profitable on fewer than half the days → likely noise
        day_penalty = 0.5
    else:
        day_penalty = 1.0

    # — 4. Trade-count normalization —
    # Penalize excessive trading (>3 trades/day average → diminishing returns)
    avg_trades_per_day = total_trades / n_days
    if avg_trades_per_day > 3.0:
        trade_norm = 1.0 - min(0.3, (avg_trades_per_day - 3.0) * 0.05)
    else:
        trade_norm = 1.0

    # — 5. Min-trade gate —
    # Relaxed thresholds: flow-based strategies may legitimately produce
    # fewer trades while still having positive expectancy.
    if avg_trades_per_day < 0.5:
        trade_scarcity = 0.25  # truly no signal → heavy penalty
    elif avg_trades_per_day < 1.0:
        trade_scarcity = 0.65  # sparse but possible for flow strategies
    else:
        trade_scarcity = 1.0   # 1+ trade/day is sufficient

    # — 6. L2-confirmation bonus —
    # Reward profiles where L2 order-flow features confirmed entries.
    # Capped at +10% to avoid creating a new overfit vector.
    l2_confirmed_days = sum(
        1 for d in valid if float(d.get("l2_avg_score", 0.0)) > 0.3
    )
    l2_ratio = l2_confirmed_days / n_days if n_days > 0 else 0.0
    l2_bonus = 1.0 + (l2_ratio * 0.10)  # up to +10%

    # — Final robust score —
    score = avg_pnl * consistency * quality_gate * day_penalty * trade_norm * trade_scarcity
    score *= l2_bonus
    return round(score, 6)


async def _apply_strategy_overrides(strategy_api_url: str, ticker: str) -> None:
    overrides = _load_strategy_overrides().get(ticker.upper())
    if not overrides:
        return
    async with aiohttp.ClientSession() as session:
        for strat_name, params in overrides.items():
            try:
                async with session.post(
                    f"{strategy_api_url}/api/strategies/update",
                    json={"strategy_name": strat_name, "params": params},
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"Override failed for {ticker}:{strat_name} (HTTP {resp.status})"
                        )
            except Exception as e:
                logger.warning(f"Override error for {ticker}:{strat_name}: {e}")


async def _fetch_remote_strategies(strategy_api_url: str) -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{strategy_api_url}/api/strategies") as resp:
            if resp.status != 200:
                raise HTTPException(
                    502,
                    f"Failed to fetch strategies from strategy API (HTTP {resp.status})",
                )
            payload = await resp.json()
    if not isinstance(payload, dict):
        raise HTTPException(502, "Strategy API /api/strategies returned invalid payload.")
    return payload


async def _apply_strategy_param_map(
    strategy_api_url: str, strategy_params: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    applied: List[str] = []
    failed: List[Dict[str, Any]] = []
    async with aiohttp.ClientSession() as session:
        for strat_name, params in strategy_params.items():
            clean_params = _sanitize_strategy_params(params)
            if not clean_params:
                continue
            try:
                async with session.post(
                    f"{strategy_api_url}/api/strategies/update",
                    json={"strategy_name": strat_name, "params": clean_params},
                ) as resp:
                    if resp.status == 200:
                        applied.append(strat_name)
                    else:
                        failed.append({"strategy": strat_name, "status": resp.status})
            except Exception as exc:
                failed.append({"strategy": strat_name, "error": str(exc)})
    return {
        "applied_strategies": applied,
        "failed_strategies": failed,
        "applied_count": len(applied),
        "failed_count": len(failed),
    }


async def _apply_active_strategy_combo(
    strategy_api_url: str, ticker: str, ticker_config: Dict[str, Any]
) -> Dict[str, Any]:
    profiles = _normalize_strategy_combo_profiles(ticker_config.get("strategy_combo_profiles", []))
    active_profile_id = str(ticker_config.get("active_strategy_combo_profile_id", "")).strip()
    if not active_profile_id:
        return {}
    target_profile = next(
        (profile for profile in profiles if str(profile.get("profile_id")) == active_profile_id),
        None,
    )
    if not isinstance(target_profile, dict):
        logger.warning(
            "Active strategy combo profile not found for %s: %s",
            ticker,
            active_profile_id,
        )
        return {
            "active_profile_id": active_profile_id,
            "applied_count": 0,
            "failed_count": 0,
            "missing_profile": True,
        }
    strategy_params = target_profile.get("strategy_params", {})
    if not isinstance(strategy_params, dict):
        return {
            "active_profile_id": active_profile_id,
            "profile_name": target_profile.get("profile_name"),
            "applied_count": 0,
            "failed_count": 0,
        }
    apply_result = await _apply_strategy_param_map(strategy_api_url, strategy_params)
    return {
        "active_profile_id": active_profile_id,
        "profile_name": target_profile.get("profile_name"),
        **apply_result,
    }


def _normalize_strategy_key(name: Any) -> str:
    text = str(name or "").strip().lower()
    if not text:
        return ""
    return text.replace("-", "_").replace(" ", "_")


def _resolve_active_adaptive_tuner_candidate(ticker_config: Dict[str, Any]) -> Dict[str, Any]:
    active_profile_id = str(ticker_config.get("active_adaptive_tuner_profile_id", "")).strip()
    if not active_profile_id:
        return {}
    profiles = _normalize_tuner_profiles(ticker_config.get("adaptive_tuner_profiles", []))
    target_profile = next(
        (profile for profile in profiles if str(profile.get("profile_id", "")).strip() == active_profile_id),
        None,
    )
    if not isinstance(target_profile, dict):
        return {}
    candidate = target_profile.get("candidate")
    if isinstance(candidate, dict):
        return candidate
    best_trial = target_profile.get("best_trial")
    if isinstance(best_trial, dict) and isinstance(best_trial.get("candidate"), dict):
        return best_trial.get("candidate", {})
    return {}


def _extract_profile_runtime_overrides(candidate: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(candidate, dict):
        return {}
    runtime: Dict[str, Any] = {}
    runtime["strategy_selection_mode"] = _normalize_strategy_selection_mode(
        candidate.get("strategy_selection_mode")
    )
    runtime["max_active_strategies"] = _normalize_clamped_int(
        candidate.get("max_active_strategies"), default=3, min_value=1, max_value=20
    )
    try:
        time_exit_bars = int(candidate.get("time_exit_bars"))
        if time_exit_bars > 0:
            runtime["time_exit_bars"] = time_exit_bars
    except (TypeError, ValueError):
        pass
    threshold_overrides = (
        ("adverse_flow_consistency", "adverse_flow_consistency_threshold"),
        ("adverse_book_pressure", "adverse_book_pressure_threshold"),
    )
    for candidate_key, runtime_key in threshold_overrides:
        raw = candidate.get(candidate_key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            runtime[runtime_key] = value
    for key in (
        "l2_min_delta",
        "l2_min_imbalance",
        "l2_min_signed_aggression",
        "l2_min_directional_consistency",
        "l2_min_participation_ratio",
        "l2_min_iceberg_bias",
    ):
        raw = candidate.get(key)
        if raw is None:
            continue
        try:
            runtime[key] = float(raw)
        except (TypeError, ValueError):
            continue

    momentum_runtime = _normalize_momentum_diversification_payload(
        candidate.get("momentum_diversification")
    )
    if not momentum_runtime:
        raw_momentum: Dict[str, Any] = {}
        momentum_keys = (
            "momentum_diversification_enabled",
            "momentum_route_enabled",
            "momentum_min_flow_score",
            "momentum_min_directional_consistency",
            "momentum_min_signed_aggression",
            "momentum_min_imbalance",
            "momentum_min_delta_acceleration",
            "momentum_min_delta_price_divergence",
            "momentum_route_flow_score_impulse",
            "momentum_fail_fast_exit_enabled",
            "momentum_fail_fast_max_bars",
        )
        key_map = {
            "momentum_diversification_enabled": "enabled",
            "momentum_route_enabled": "route_enabled",
            "momentum_min_flow_score": "min_flow_score",
            "momentum_min_directional_consistency": "min_directional_consistency",
            "momentum_min_signed_aggression": "min_signed_aggression",
            "momentum_min_imbalance": "min_imbalance",
            "momentum_min_delta_acceleration": "min_delta_acceleration",
            "momentum_min_delta_price_divergence": "min_delta_price_divergence",
            "momentum_route_flow_score_impulse": "route_flow_score_impulse",
            "momentum_fail_fast_exit_enabled": "fail_fast_exit_enabled",
            "momentum_fail_fast_max_bars": "fail_fast_max_bars",
        }
        for key in momentum_keys:
            if key not in candidate:
                continue
            raw_momentum[key_map[key]] = candidate.get(key)
        momentum_runtime = _normalize_momentum_diversification_payload(raw_momentum)
    if momentum_runtime:
        runtime["momentum_diversification"] = momentum_runtime
    return runtime


async def _apply_active_adaptive_tuner_profile(
    strategy_api_url: str,
    ticker_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Keep strategy API aligned with active adaptive tuner profile candidate.

    This avoids drift where stale strategy enabled flags from prior runs override
    the profile-selected strategy set.
    """
    candidate = _resolve_active_adaptive_tuner_candidate(ticker_config)
    if not candidate:
        return {}

    enabled_raw = candidate.get("enabled_strategies", [])
    enabled_strategies = [str(s).strip() for s in enabled_raw if str(s).strip()]
    if not enabled_strategies:
        return {"candidate_applied": False, "reason": "candidate has no enabled_strategies"}

    enabled_norm = {_normalize_strategy_key(s) for s in enabled_strategies}
    result: Dict[str, Any] = {
        "candidate_applied": True,
        "enabled_strategies": enabled_strategies,
        "runtime_overrides": _extract_profile_runtime_overrides(candidate),
    }

    try:
        remote = await _fetch_remote_strategies(strategy_api_url)
    except Exception as exc:
        return {
            **result,
            "candidate_applied": False,
            "error": f"failed to fetch remote strategies: {exc}",
        }

    # 1) Sync enabled/disabled flags for all remote strategies.
    enable_map: Dict[str, Dict[str, Any]] = {}
    for strategy_name in remote.keys():
        normalized = _normalize_strategy_key(strategy_name)
        enable_map[str(strategy_name)] = {"enabled": normalized in enabled_norm}
    enable_apply = await _apply_strategy_param_map(strategy_api_url, enable_map)
    result["enabled_sync"] = enable_apply

    # 2) Apply v2 per-strategy params to enabled strategies.
    v2_params: Dict[str, Any] = {}
    for key in ("min_confidence", "atr_stop_multiplier", "rr_ratio", "trailing_stop_pct"):
        raw = candidate.get(key)
        if raw is None:
            continue
        try:
            v2_params[key] = float(raw)
        except (TypeError, ValueError):
            continue
    if v2_params:
        param_map = {name: dict(v2_params) for name in enabled_strategies}
        param_apply = await _apply_strategy_param_map(strategy_api_url, param_map)
        result["v2_param_sync"] = param_apply

    return result


async def _apply_global_trailing(strategy_api_url: str, trailing_stop_pct: Optional[float]) -> None:
    if trailing_stop_pct is None:
        return
    if trailing_stop_pct <= 0:
        logger.warning("Global trailing_stop_pct ignored (must be > 0).")
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{strategy_api_url}/api/strategies") as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to fetch strategies for global trailing (HTTP {resp.status})")
                    return
                strategies = await resp.json()
            for name in strategies.keys():
                try:
                    async with session.post(
                        f"{strategy_api_url}/api/strategies/update",
                        json={"strategy_name": name, "params": {"trailing_stop_pct": trailing_stop_pct}},
                    ) as upd:
                        if upd.status != 200:
                            logger.warning(
                                f"Global trailing update failed for {name} (HTTP {upd.status})"
                            )
                except Exception as e:
                    logger.warning(f"Global trailing update error for {name}: {e}")
    except Exception as e:
        logger.warning(f"Global trailing update failed: {e}")


async def _apply_aos_optimizations(
    strategy_api_url: str,
    ticker: str,
    *,
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply AOS optimizations (time filter, long_only, params) to strategy API."""
    aos_config = _load_aos_config(aos_config_path)
    ticker_config = aos_config.get("tickers", {}).get(ticker.upper(), {})
    positioning_ticker_config = _get_ticker_positioning_config(ticker)
    if isinstance(ticker_config, dict):
        legacy_positioning = {}
        for key in POSITIONING_CONFIG_KEYS:
            if key in ticker_config:
                legacy_positioning[key] = ticker_config.get(key)
        if legacy_positioning:
            merged_positioning = dict(legacy_positioning)
            merged_positioning.update(positioning_ticker_config)
            positioning_ticker_config = merged_positioning
    
    if not ticker_config:
        return {"positioning": positioning_ticker_config} if positioning_ticker_config else {}
    
    applied = {}
    combo_applied = await _apply_active_strategy_combo(
        strategy_api_url=strategy_api_url,
        ticker=ticker,
        ticker_config=ticker_config,
    )
    if combo_applied:
        applied["strategy_combo"] = combo_applied

    # Get the strategy name from AOS config
    strategy_name = ticker_config.get("strategy")
    params = dict(ticker_config.get("params", {}))
    if "long_only" in ticker_config and "long_only" not in params:
        params["long_only"] = bool(ticker_config["long_only"])
    
    try:
        async with aiohttp.ClientSession() as session:
            if strategy_name and params:
                async with session.post(
                    f"{strategy_api_url}/api/strategies/update",
                    json={"strategy_name": strategy_name, "params": params},
                ) as resp:
                    if resp.status == 200:
                        applied["strategy"] = strategy_name
                        applied["params"] = params
                        logger.info(f"Applied AOS params for {ticker}: {params}")
                    else:
                        logger.warning(f"AOS update failed for {ticker}:{strategy_name} (HTTP {resp.status})")

    except Exception as e:
        logger.warning(f"AOS update error for {ticker}: {e}")

    # Apply active adaptive tuner profile strategy sync after base AOS params so
    # candidate-level per-strategy values win over legacy params from ticker_config.
    adaptive_profile_applied = await _apply_active_adaptive_tuner_profile(
        strategy_api_url=strategy_api_url,
        ticker_config=ticker_config,
    )
    if adaptive_profile_applied:
        applied["adaptive_profile"] = adaptive_profile_applied
    
    # Store time and directional filters for session to use
    applied["trading_hours"] = ticker_config.get("trading_hours")
    applied["long_only"] = bool(ticker_config.get("long_only", params.get("long_only", False)))
    applied["time_filter_enabled"] = bool(
        ticker_config.get("time_filter_enabled", bool(ticker_config.get("trading_hours")))
    )
    applied["strategy_selection_mode"] = str(
        ticker_config.get("strategy_selection_mode", "adaptive_top_n")
    ).strip().lower() or "adaptive_top_n"
    try:
        raw_max_active = int(ticker_config.get("max_active_strategies", 3))
    except (TypeError, ValueError):
        raw_max_active = 3
    applied["max_active_strategies"] = max(1, min(20, raw_max_active))
    try:
        applied["adverse_flow_consistency_threshold"] = float(
            ticker_config.get("adverse_flow_consistency_threshold", 0.45)
        )
    except (TypeError, ValueError):
        applied["adverse_flow_consistency_threshold"] = 0.45
    try:
        applied["adverse_book_pressure_threshold"] = float(
            ticker_config.get("adverse_book_pressure_threshold", 0.15)
        )
    except (TypeError, ValueError):
        applied["adverse_book_pressure_threshold"] = 0.15
    if isinstance(ticker_config.get("l2"), dict):
        applied["l2"] = ticker_config.get("l2", {})
    if isinstance(ticker_config.get("adaptive"), dict):
        applied["adaptive"] = ticker_config.get("adaptive", {})
    if positioning_ticker_config:
        applied["positioning"] = positioning_ticker_config
    
    return applied


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
    params = {
        "run_id": run_id,
        "ticker": ticker,
        "date": date,
        "regime_detection_minutes": int(regime_detection_minutes),
        "regime_refresh_bars": int(regime_refresh_bars),
        "account_size_usd": float(account_size_usd),
        "risk_per_trade_pct": float(risk_per_trade_pct),
        "max_position_notional_pct": float(max_position_notional_pct),
        "max_fill_participation_rate": float(max_fill_participation_rate),
        "min_fill_ratio": float(min_fill_ratio),
        "enable_partial_take_profit": int(bool(enable_partial_take_profit)),
        "partial_take_profit_rr": float(partial_take_profit_rr),
        "partial_take_profit_fraction": float(partial_take_profit_fraction),
        "trailing_activation_pct": float(trailing_activation_pct),
        "break_even_buffer_pct": float(break_even_buffer_pct),
        "break_even_min_hold_bars": int(break_even_min_hold_bars),
        "trailing_enabled_in_choppy": int(bool(trailing_enabled_in_choppy)),
        "time_exit_bars": int(time_exit_bars),
        "adverse_flow_exit_enabled": int(bool(adverse_flow_exit_enabled)),
        "adverse_flow_threshold": float(adverse_flow_threshold),
        "adverse_flow_min_hold_bars": int(adverse_flow_min_hold_bars),
        "adverse_flow_consistency_threshold": float(adverse_flow_consistency_threshold),
        "adverse_book_pressure_threshold": float(adverse_book_pressure_threshold),
        "stop_loss_mode": str(stop_loss_mode),
        "fixed_stop_loss_pct": float(fixed_stop_loss_pct),
        "l2_confirm_enabled": int(bool(l2_confirm_enabled)),
        "l2_min_delta": float(l2_min_delta),
        "l2_min_imbalance": float(l2_min_imbalance),
        "l2_min_iceberg_bias": float(l2_min_iceberg_bias),
        "l2_lookback_bars": int(l2_lookback_bars),
        "l2_min_participation_ratio": float(l2_min_participation_ratio),
        "l2_min_directional_consistency": float(l2_min_directional_consistency),
        "l2_min_signed_aggression": float(l2_min_signed_aggression),
        "cold_start_each_day": int(bool(cold_start_each_day)),
        "strategy_selection_mode": str(strategy_selection_mode),
        "max_active_strategies": int(max_active_strategies),
    }
    if momentum_diversification_json:
        params["momentum_diversification_json"] = str(momentum_diversification_json)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/session/config",
                params=params,
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        f"Session config failed (HTTP {resp.status}) for {run_id}:{ticker}:{date}"
                    )
    except Exception as e:
        logger.warning(f"Session config error for {run_id}:{ticker}:{date}: {e}")


async def _clear_remote_strategy_sessions(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
) -> None:
    """
    Best-effort cleanup of strategy API session state.

    This prevents sticky per-run state (phase/cooldown/session caches) from
    affecting subsequent replays with the same run_id+ticker.
    """
    normalized_ticker = ticker.upper()

    async def _clear_v2(session: aiohttp.ClientSession) -> bool:
        async with session.delete(
            f"{strategy_api_url}/api/session/run",
            params={"run_id": run_id, "ticker": normalized_ticker},
        ) as resp:
            if resp.status == 200:
                return True
            # Endpoint might not exist on older strategy API builds.
            if resp.status in (404, 405):
                return False
            logger.warning(
                f"Session run-clear failed (HTTP {resp.status}) for {run_id}:{normalized_ticker}"
            )
            return False

    async def _clear_legacy(session: aiohttp.ClientSession) -> None:
        try:
            async with session.get(f"{strategy_api_url}/api/sessions") as resp:
                if resp.status != 200:
                    logger.warning(
                        f"Session list failed (HTTP {resp.status}) for {run_id}:{normalized_ticker}"
                    )
                    return
                payload = await resp.json()
        except Exception as exc:
            logger.warning(f"Session list error for {run_id}:{normalized_ticker}: {exc}")
            return

        if not isinstance(payload, dict):
            return

        dates_to_clear: List[str] = []
        for session_state in payload.values():
            if not isinstance(session_state, dict):
                continue
            if session_state.get("run_id") != run_id:
                continue
            if str(session_state.get("ticker", "")).upper() != normalized_ticker:
                continue
            date_val = session_state.get("date")
            if isinstance(date_val, str) and date_val:
                dates_to_clear.append(date_val)

        for date_val in sorted(set(dates_to_clear)):
            try:
                async with session.delete(
                    f"{strategy_api_url}/api/session",
                    params={
                        "run_id": run_id,
                        "ticker": normalized_ticker,
                        "date": date_val,
                    },
                ) as resp:
                    if resp.status not in (200, 404):
                        logger.warning(
                            f"Legacy session clear failed (HTTP {resp.status}) "
                            f"for {run_id}:{normalized_ticker}:{date_val}"
                        )
            except Exception as exc:
                logger.warning(
                    f"Legacy session clear error for {run_id}:{normalized_ticker}:{date_val}: {exc}"
                )

    try:
        async with aiohttp.ClientSession() as session:
            used_v2 = await _clear_v2(session)
            if not used_v2:
                await _clear_legacy(session)
    except Exception as exc:
        logger.warning(f"Remote session cleanup error for {run_id}:{normalized_ticker}: {exc}")


async def _reset_remote_orchestrator_state(strategy_api_url: str) -> bool:
    """
    Best-effort full reset of remote strategy/orchestrator state.

    Returns True when a reset endpoint acknowledged the request, False when the
    endpoint is unavailable or reset failed.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": "all", "clear_sessions": "true"},
            ) as resp:
                if resp.status == 200:
                    return True
                if resp.status in (404, 405):
                    # Older strategy API builds do not expose this endpoint.
                    return False
                logger.warning(
                    f"Remote orchestrator reset failed (HTTP {resp.status}) at {strategy_api_url}"
                )
                return False
    except Exception as exc:
        logger.warning(f"Remote orchestrator reset error at {strategy_api_url}: {exc}")
        return False


async def _reset_remote_orchestrator_state_scoped(
    strategy_api_url: str, scope: str = "session"
) -> bool:
    """Reset remote orchestrator with a specific scope (session/learning/all)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": scope, "clear_sessions": "true"},
            ) as resp:
                return resp.status == 200
    except Exception as exc:
        logger.warning(f"Remote orchestrator scoped reset error: {exc}")
        return False


async def _load_remote_checkpoint(
    strategy_api_url: str, checkpoint_path: str
) -> Optional[Dict]:
    """Load a checkpoint on the remote strategy API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/load",
                params={"path": checkpoint_path},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(
                    f"Remote checkpoint load failed (HTTP {resp.status}): {checkpoint_path}"
                )
                return None
    except Exception as exc:
        logger.warning(f"Remote checkpoint load error: {exc}")
        return None


async def _save_remote_checkpoint(
    strategy_api_url: str,
    run_id: str = "",
    ticker: str = "",
    date_from: str = "",
    date_to: str = "",
) -> Optional[str]:
    """Auto-save checkpoint after a successful backtest run."""
    try:
        params = {
            k: v for k, v in {
                "run_id": run_id, "ticker": ticker,
                "date_from": date_from, "date_to": date_to,
            }.items() if v
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/save",
                params=params,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    path = result.get("path")
                    logger.info(f"Auto-saved checkpoint: {path}")
                    return path
                return None
    except Exception as exc:
        logger.warning(f"Checkpoint auto-save error: {exc}")
        return None


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
            feats["l2_book_pressure_delta"] = (
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
    return (
        _normalize_strategy_selection_mode(candidate.get("strategy_selection_mode")),
        _normalize_clamped_int(candidate.get("max_active_strategies"), 3, 1, 20),
        _normalize_non_negative_int(candidate.get("min_active_bars_before_switch"), 0, 500),
        _normalize_non_negative_int(candidate.get("switch_cooldown_bars"), 0, 500),
        bool(candidate.get("flow_bias_enabled", True)),
        bool(candidate.get("use_ohlcv_fallbacks", True)),
    )


def _build_adaptive_tuner_search_space(request: AdaptiveTunerRequest) -> Dict[str, List[Any]]:
    return {
        "strategy_selection_mode": _normalize_mode_options(request.selection_modes),
        "max_active_strategies": _normalize_int_options(
            request.max_active_options,
            default=[1, 2, 3, 4, 5],
            min_value=1,
            max_value=20,
        ),
        "min_active_bars_before_switch": _normalize_int_options(
            request.min_active_bars_options,
            default=[0, 2, 4, 8, 12],
            min_value=0,
            max_value=500,
        ),
        "switch_cooldown_bars": _normalize_int_options(
            request.switch_cooldown_bars_options,
            default=[0, 1, 2, 4, 8],
            min_value=0,
            max_value=500,
        ),
        "flow_bias_enabled": _normalize_bool_options(
            request.flow_bias_options, default=[True, False]
        ),
        "use_ohlcv_fallbacks": _normalize_bool_options(
            request.ohlcv_fallback_options, default=[True, False]
        ),
    }


def _build_grid_candidates(
    search_space: Dict[str, List[Any]],
    *,
    max_candidates: int = 600,
) -> List[Dict[str, Any]]:
    keys = [
        "strategy_selection_mode",
        "max_active_strategies",
        "min_active_bars_before_switch",
        "switch_cooldown_bars",
        "flow_bias_enabled",
        "use_ohlcv_fallbacks",
    ]
    all_values = [search_space[k] for k in keys]
    candidates: List[Dict[str, Any]] = []
    for values in product(*all_values):
        candidate = dict(zip(keys, values))
        candidates.append(candidate)
        if len(candidates) >= max_candidates:
            break
    return candidates


def _build_random_candidates(
    search_space: Dict[str, List[Any]],
    *,
    n_trials: int,
    seed: int,
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    attempts = 0
    max_attempts = max(200, n_trials * 20)
    candidates: List[Dict[str, Any]] = []
    seen = set()
    while len(candidates) < n_trials and attempts < max_attempts:
        attempts += 1
        candidate = {
            "strategy_selection_mode": rng.choice(search_space["strategy_selection_mode"]),
            "max_active_strategies": rng.choice(search_space["max_active_strategies"]),
            "min_active_bars_before_switch": rng.choice(search_space["min_active_bars_before_switch"]),
            "switch_cooldown_bars": rng.choice(search_space["switch_cooldown_bars"]),
            "flow_bias_enabled": rng.choice(search_space["flow_bias_enabled"]),
            "use_ohlcv_fallbacks": rng.choice(search_space["use_ohlcv_fallbacks"]),
        }
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


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
