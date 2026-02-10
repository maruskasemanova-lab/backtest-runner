"""
Unified Backtest Runner API Server.
Orchestrates the look-ahead free data feeding and strategy evaluation.
"""
import asyncio
import copy
import json
import random
from datetime import datetime, timedelta
from itertools import product
from typing import Dict, Any, List, Optional, Union
from zoneinfo import ZoneInfo
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
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
connected_clients: List[WebSocket] = []
databento_svc = DatabentoService()
adaptive_tuner_jobs: Dict[str, Dict[str, Any]] = {}
adaptive_tuner_lock = asyncio.Lock()
STRATEGY_OVERRIDES_PATH = Path(__file__).parent / "strategy_overrides.json"
AOS_CONFIG_PATH = Path(__file__).parent / "aos_optimization" / "aos_config.json"
MARKET_TZ = ZoneInfo("America/New_York")


def _load_strategy_overrides() -> Dict[str, Any]:
    return load_json_file(STRATEGY_OVERRIDES_PATH, default={})


def _load_aos_config() -> Dict[str, Any]:
    """Load AOS optimization config from JSON file."""
    return load_json_file(AOS_CONFIG_PATH, default={"version": "1.0.0", "tickers": {}})


def _save_aos_config(config: Dict[str, Any]) -> bool:
    """Save AOS optimization config to JSON file."""
    ok = save_json_file(AOS_CONFIG_PATH, payload=config)
    if not ok:
        logger.error("Failed to save AOS config.")
    return ok


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

    # — 2. Win-rate quality gate —
    total_wins = sum(
        max(0, int(d.get("trades", 0)) * float(d.get("win_rate_pct", 0.0)) / 100.0)
        for d in valid
    )
    overall_wr = total_wins / total_trades if total_trades > 0 else 0.0
    if overall_wr < 0.40:
        quality_gate = 0.3  # heavy penalty for low win-rate
    elif overall_wr < 0.50:
        quality_gate = 0.7
    else:
        quality_gate = 1.0

    # — 3. Positive-day ratio —
    positive_days = sum(1 for p in daily_pnl if p > 0)
    positive_ratio = positive_days / n_days
    if positive_ratio < 0.50:
        # Profitable on fewer than half the days → likely noise
        day_penalty = 0.5
    else:
        day_penalty = 1.0

    # — 4. Trade-count normalization —
    # Penalize excessive trading (>2 trades/day average → diminishing returns)
    avg_trades_per_day = total_trades / n_days
    if avg_trades_per_day > 3.0:
        trade_norm = 1.0 - min(0.3, (avg_trades_per_day - 3.0) * 0.05)
    else:
        trade_norm = 1.0

    # — 5. Min-trade gate —
    # Too few trades = edge is too rare to be statistically reliable
    if avg_trades_per_day < 1.5:
        trade_scarcity = 0.5
    elif avg_trades_per_day < 1.0:
        trade_scarcity = 0.25
    else:
        trade_scarcity = 1.0

    # — Final robust score —
    score = avg_pnl * consistency * quality_gate * day_penalty * trade_norm * trade_scarcity
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


async def _apply_aos_optimizations(strategy_api_url: str, ticker: str) -> Dict[str, Any]:
    """Apply AOS optimizations (time filter, long_only, params) to strategy API."""
    aos_config = _load_aos_config()
    ticker_config = aos_config.get("tickers", {}).get(ticker.upper(), {})
    
    if not ticker_config:
        return {}
    
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
    if isinstance(ticker_config.get("l2"), dict):
        applied["l2"] = ticker_config.get("l2", {})
    if isinstance(ticker_config.get("adaptive"), dict):
        applied["adaptive"] = ticker_config.get("adaptive", {})
    
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
    time_exit_bars: int = 40,
    adverse_flow_exit_enabled: bool = True,
    adverse_flow_threshold: float = 0.12,
    adverse_flow_min_hold_bars: int = 3,
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
        "time_exit_bars": int(time_exit_bars),
        "adverse_flow_exit_enabled": int(bool(adverse_flow_exit_enabled)),
        "adverse_flow_threshold": float(adverse_flow_threshold),
        "adverse_flow_min_hold_bars": int(adverse_flow_min_hold_bars),
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


# ============ Pydantic Models ============
class StartRunRequest(BaseModel):
    run_id: str
    ticker: str
    date: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    data_file: Optional[str] = None  # If None, auto-discover from available data
    strategy_api_url: str = "http://localhost:8001"
    regime_detection_minutes: int = 15
    regime_refresh_bars: int = 12
    trailing_stop_pct: Optional[float] = None
    account_size_usd: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    max_position_notional_pct: float = 100.0
    max_fill_participation_rate: float = 0.20
    min_fill_ratio: float = 0.35
    enable_partial_take_profit: bool = True
    partial_take_profit_rr: float = 1.0
    partial_take_profit_fraction: float = 0.5
    time_exit_bars: int = 40
    adverse_flow_exit_enabled: bool = True
    adverse_flow_threshold: float = 0.12
    adverse_flow_min_hold_bars: int = 3
    stop_loss_mode: str = "strategy"
    fixed_stop_loss_pct: float = 0.0
    allow_mock_data: bool = False
    l2_only: bool = False
    l2_confirm_enabled: bool = False
    l2_min_delta: float = 0.0
    l2_min_imbalance: float = 0.0
    l2_min_iceberg_bias: float = 0.0
    l2_lookback_bars: int = 3
    l2_min_participation_ratio: float = 0.0
    l2_min_directional_consistency: float = 0.0
    l2_min_signed_aggression: float = 0.0
    strategy_selection_mode: Optional[str] = None
    max_active_strategies: Optional[int] = None
    intrabar_execution_recalc_1s: Optional[bool] = None
    cold_start_each_day: bool = False
    comparable_mode: bool = False
    # Whether runner should re-apply ticker defaults from strategy_overrides.json
    # during run start. Keep enabled by default for backward compatibility.
    apply_ticker_overrides_on_start: bool = True
    # Checkpoint: warm-start from a previous backtest's learning state
    checkpoint_path: Optional[str] = None
    auto_save_checkpoint: bool = True


class PlayRequest(BaseModel):
    # Accept strings like "max" / "10hz" as well as raw millisecond values.
    speed_ms: Optional[Union[int, str]] = 100


class AdaptiveTunerRequest(BaseModel):
    ticker: str
    date_from: str
    date_to: str
    strategy_api_url: str = "http://localhost:8001"
    method: str = "grid"  # grid | random | optuna
    n_trials: int = 16
    score_metric: str = "pnl_pct"  # pnl_pct | pnl_dollars | win_rate | trade_adjusted | robust
    seed: int = 42
    adaptive_version: int = 1  # 1 = flat search, 2 = multi-dimensional vector discovery
    persist_best: bool = False
    allow_mock_data: bool = False
    comparable_mode: bool = True
    l2_required: bool = False
    l2_confirm_enabled: bool = True
    l2_only: bool = False
    # Quick approximate mode: tune on sampled days and expand trial budget.
    quick_mode: bool = False
    quick_max_days: int = 2
    quick_trial_boost: int = 3
    # --- V1 search dimensions ---
    selection_modes: Optional[List[str]] = None
    max_active_options: Optional[List[int]] = None
    min_active_bars_options: Optional[List[int]] = None
    switch_cooldown_bars_options: Optional[List[int]] = None
    flow_bias_options: Optional[List[bool]] = None
    ohlcv_fallback_options: Optional[List[bool]] = None
    # --- V2 multi-dimensional vector search dimensions ---
    # Strategy dimension: sets of strategies to evaluate
    strategy_sets: Optional[List[List[str]]] = None
    # L2 threshold dimension
    l2_min_delta_options: Optional[List[float]] = None
    l2_min_imbalance_options: Optional[List[float]] = None
    l2_min_signed_aggression_options: Optional[List[float]] = None
    l2_min_directional_consistency_options: Optional[List[float]] = None
    l2_min_participation_ratio_options: Optional[List[float]] = None
    l2_lookback_bars_options: Optional[List[int]] = None
    # Regime dimension: sets of allowed regimes
    regime_filter_sets: Optional[List[List[str]]] = None
    # Evidence engine dimension
    base_threshold_options: Optional[List[float]] = None
    min_confirming_sources_options: Optional[List[int]] = None
    # Per-strategy parameter tuning dimension
    min_confidence_options: Optional[List[float]] = None
    atr_stop_multiplier_options: Optional[List[float]] = None
    rr_ratio_options: Optional[List[float]] = None
    # Time-of-day dimension: sets of allowed trading hours (list of lists of ints, e.g. [[9,10],[9,10,11,12,13,14,15]])
    time_window_sets: Optional[List[List[int]]] = None
    # Flow-informed exit thresholds (v2)
    adverse_flow_consistency_options: Optional[List[float]] = None
    adverse_book_pressure_options: Optional[List[float]] = None
    # Exit parameter dims (v2)
    time_exit_bars_options: Optional[List[int]] = None
    trailing_stop_pct_options: Optional[List[float]] = None
    # Neighborhood search: half candidates are baseline perturbations
    neighborhood_search: bool = False
    # V2 analysis options
    include_vector_analysis: bool = True
    min_trades_per_vector: int = 3


class AdaptiveTunerProfileApplyRequest(BaseModel):
    ticker: str
    profile_id: str


class StrategyComboCaptureRequest(BaseModel):
    ticker: str
    profile_name: Optional[str] = None
    strategy_api_url: str = "http://localhost:8001"
    set_active: bool = True


class StrategyComboApplyRequest(BaseModel):
    ticker: str
    profile_id: str
    strategy_api_url: str = "http://localhost:8001"
    apply_now: bool = True


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
) -> Dict[str, Any]:
    total_pnl_pct = 0.0
    total_pnl_dollars = 0.0
    total_win_rate_pct = 0.0
    total_trades = 0
    valid_days = 0
    day_results: List[Dict[str, Any]] = []
    for day_idx, date in enumerate(dates):
        run_id = f"adaptive-tuner-{job_id[:8]}-{trial_index}-{day_idx}"
        run_request = StartRunRequest(
            run_id=run_id,
            ticker=ticker,
            date=date,
            strategy_api_url=request.strategy_api_url,
            allow_mock_data=bool(request.allow_mock_data),
            comparable_mode=bool(request.comparable_mode),
            apply_ticker_overrides_on_start=False,
            l2_confirm_enabled=bool(request.l2_confirm_enabled),
            l2_only=bool(request.l2_only),
            intrabar_execution_recalc_1s=False,
            strategy_selection_mode=_normalize_strategy_selection_mode(
                candidate.get("strategy_selection_mode")
            ),
            max_active_strategies=_normalize_clamped_int(
                candidate.get("max_active_strategies"), default=3, min_value=1, max_value=20
            ),
        )
        run_key: Optional[str] = None
        try:
            start_result = await start_run(run_request)
            run_key = str(start_result.get("run_key", ""))
            runner = active_runners.get(run_key)
            if runner is None:
                raise RuntimeError(f"Runner not found for key {run_key}")
            await runner.run_all(speed_ms=0)
            summary_payload = runner.get_summary()
            session_summary = summary_payload.get("session_summary") if isinstance(summary_payload, dict) else None
            summary = session_summary if isinstance(session_summary, dict) else {}
            pnl_pct = float(summary.get("total_pnl_pct", 0.0) or 0.0)
            pnl_dollars = float(summary.get("total_pnl_dollars", 0.0) or 0.0)
            win_rate_pct = float(summary.get("win_rate", 0.0) or 0.0)
            trades = int(summary.get("total_trades", 0) or 0)
            total_pnl_pct += pnl_pct
            total_pnl_dollars += pnl_dollars
            total_win_rate_pct += win_rate_pct
            total_trades += trades
            valid_days += 1
            day_results.append(
                {
                    "date": date,
                    "success": True,
                    "pnl_pct": pnl_pct,
                    "pnl_dollars": pnl_dollars,
                    "win_rate_pct": win_rate_pct,
                    "trades": trades,
                }
            )
        except HTTPException as exc:
            day_results.append(
                {
                    "date": date,
                    "success": False,
                    "error": f"HTTP {exc.status_code}: {exc.detail}",
                }
            )
        except Exception as exc:
            day_results.append(
                {
                    "date": date,
                    "success": False,
                    "error": str(exc),
                }
            )
        finally:
            if run_key:
                active_runners.pop(run_key, None)

    avg_win_rate_pct = (total_win_rate_pct / valid_days) if valid_days > 0 else 0.0
    if str(request.score_metric or "").strip().lower() == "robust":
        score = _compute_tuner_score_robust(day_results)
    else:
        score = _compute_tuner_score(
            score_metric=request.score_metric,
            total_pnl_pct=total_pnl_pct,
            total_pnl_dollars=total_pnl_dollars,
            avg_win_rate_pct=avg_win_rate_pct,
            total_trades=total_trades,
            valid_days=valid_days,
        )
    return {
        "trial_index": trial_index,
        "candidate": candidate,
        "score": round(float(score), 6),
        "metrics": {
            "valid_days": valid_days,
            "total_days": len(dates),
            "total_trades": total_trades,
            "total_pnl_pct": round(total_pnl_pct, 4),
            "avg_pnl_pct": round((total_pnl_pct / valid_days), 4) if valid_days > 0 else 0.0,
            "total_pnl_dollars": round(total_pnl_dollars, 4),
            "avg_pnl_dollars": round((total_pnl_dollars / valid_days), 4) if valid_days > 0 else 0.0,
            "avg_win_rate_pct": round(avg_win_rate_pct, 4),
        },
        "day_results": day_results,
        "completed_at": datetime.utcnow().isoformat() + "Z",
    }


# ============ V2 Multi-Dimensional Vector Discovery ============


def _build_v2_search_space(
    request: AdaptiveTunerRequest,
    ticker_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build multi-dimensional search space from request options + AOS ticker config defaults."""
    # Extract existing ticker config values for defaults
    l2_cfg = ticker_config.get("l2", {}) if isinstance(ticker_config.get("l2"), dict) else {}
    existing_regime_filter = ticker_config.get("regime_filter", [])
    if not isinstance(existing_regime_filter, list):
        existing_regime_filter = ["TRENDING", "MIXED", "CHOPPY"]

    # Determine enabled strategies from ticker config
    enabled_strategies = []
    strategy_name = ticker_config.get("strategy", "")
    if isinstance(strategy_name, str) and strategy_name.strip():
        enabled_strategies.append(strategy_name.strip().lower())
    backup = ticker_config.get("backup_strategy", "")
    if isinstance(backup, str) and backup.strip():
        backup_lower = backup.strip().lower()
        if backup_lower not in enabled_strategies:
            enabled_strategies.append(backup_lower)
    if not enabled_strategies:
        enabled_strategies = ["momentum_flow"]

    # V1 adaptive dimensions (included in v2 for completeness)
    v1_space = _build_adaptive_tuner_search_space(request)

    return {
        # V1 dimensions
        **v1_space,
        # Strategy dimension
        "strategy_sets": _normalize_strategy_sets(
            request.strategy_sets, enabled_strategies
        ),
        # L2 threshold dimensions
        "l2_min_delta": _normalize_float_options(
            request.l2_min_delta_options,
            default=[float(l2_cfg.get("min_delta", 500)), 1000, 2000, 5000],
            min_value=0.0,
            max_value=100_000.0,
        ),
        "l2_min_imbalance": _normalize_float_options(
            request.l2_min_imbalance_options,
            default=[0.05, float(l2_cfg.get("min_imbalance", 0.12)), 0.20, 0.35],
            min_value=0.0,
            max_value=1.0,
        ),
        "l2_min_signed_aggression": _normalize_float_options(
            request.l2_min_signed_aggression_options,
            default=[0.05, float(l2_cfg.get("min_signed_aggression", 0.12)), 0.20, 0.35],
            min_value=0.0,
            max_value=1.0,
        ),
        "l2_min_directional_consistency": _normalize_float_options(
            request.l2_min_directional_consistency_options,
            default=[0.3, float(l2_cfg.get("min_directional_consistency", 0.5)), 0.7],
            min_value=0.0,
            max_value=1.0,
        ),
        # Regime dimension
        "regime_filter_sets": _normalize_regime_filter_sets(request.regime_filter_sets),
        # Evidence engine dimensions
        "base_threshold": _normalize_float_options(
            request.base_threshold_options,
            default=[45.0, 50.0, 55.0, 60.0, 65.0],
            min_value=0.0,
            max_value=100.0,
        ),
        "min_confirming_sources": _normalize_int_options(
            request.min_confirming_sources_options,
            default=[1, 2, 3],
            min_value=1,
            max_value=5,
        ),
        # Per-strategy parameter dimensions
        "min_confidence": _normalize_float_options(
            request.min_confidence_options,
            default=[50.0, 55.0, 60.0, 65.0],
            min_value=30.0,
            max_value=90.0,
        ),
        "atr_stop_multiplier": _normalize_float_options(
            request.atr_stop_multiplier_options,
            default=[0.7, 1.0, 1.3, 1.8],
            min_value=0.3,
            max_value=4.0,
        ),
        "rr_ratio": _normalize_float_options(
            request.rr_ratio_options,
            default=[1.5, 2.0, 2.5, 3.0],
            min_value=1.0,
            max_value=5.0,
        ),
        # Time-of-day dimension
        "time_window_sets": _normalize_time_window_sets(request.time_window_sets),
        # Flow exit dims
        "adverse_flow_consistency": _normalize_float_options(
            request.adverse_flow_consistency_options,
            default=[0.35, 0.45, 0.55],
            min_value=0.1,
            max_value=0.9,
        ),
        "adverse_book_pressure": _normalize_float_options(
            request.adverse_book_pressure_options,
            default=[0.10, 0.15, 0.22],
            min_value=0.05,
            max_value=0.5,
        ),
        # Exit param dims
        "time_exit_bars": _normalize_int_options(
            request.time_exit_bars_options,
            default=[15, 25, 35, 50],
            min_value=5,
            max_value=120,
        ),
        "trailing_stop_pct": _normalize_float_options(
            request.trailing_stop_pct_options,
            default=[0.4, 0.6, 0.8, 1.0, 1.3],
            min_value=0.1,
            max_value=3.0,
        ),
    }


def _v2_candidate_key(candidate: Dict[str, Any]) -> tuple:
    """Create a hashable key for v2 candidate deduplication."""
    strategy_key = tuple(sorted(candidate.get("enabled_strategies", [])))
    regime_key = tuple(sorted(candidate.get("regime_filter", [])))
    return (
        strategy_key,
        regime_key,
        candidate.get("l2_min_delta"),
        candidate.get("l2_min_imbalance"),
        candidate.get("l2_min_signed_aggression"),
        candidate.get("l2_min_directional_consistency"),
        candidate.get("base_threshold"),
        candidate.get("min_confirming_sources"),
        candidate.get("min_confidence"),
        candidate.get("atr_stop_multiplier"),
        candidate.get("rr_ratio"),
        tuple(sorted(candidate.get("trading_hours", []) or [])),
        candidate.get("adverse_flow_consistency"),
        candidate.get("adverse_book_pressure"),
        candidate.get("time_exit_bars"),
        candidate.get("trailing_stop_pct"),
        _normalize_strategy_selection_mode(candidate.get("strategy_selection_mode")),
        candidate.get("flow_bias_enabled"),
    )


def _build_v2_random_candidates(
    search_space: Dict[str, Any],
    *,
    n_trials: int,
    seed: int,
    neighborhood_search: bool = False,
) -> List[Dict[str, Any]]:
    """Build random candidates sampling across all v2 dimensions."""
    rng = random.Random(seed)
    attempts = 0
    max_attempts = max(500, n_trials * 30)
    candidates: List[Dict[str, Any]] = []
    seen = set()

    # Build baseline anchor (first value of each dimension)
    baseline = _build_v2_baseline_candidate(search_space)

    # If neighborhood_search, split: N/2 perturbed + N/2 random
    n_neighborhood = (n_trials // 2) if neighborhood_search else 0
    n_random = n_trials - n_neighborhood

    # --- Phase 1: neighborhood candidates (perturb 1-2 dims from baseline) ---
    perturbable_dims = [
        "l2_min_delta", "l2_min_imbalance", "l2_min_signed_aggression",
        "l2_min_directional_consistency", "base_threshold", "min_confirming_sources",
        "min_confidence", "atr_stop_multiplier", "rr_ratio",
        "adverse_flow_consistency", "adverse_book_pressure",
        "time_exit_bars", "trailing_stop_pct",
    ]
    list_dims = ["strategy_sets", "regime_filter_sets", "time_window_sets"]

    neighbor_attempts = 0
    while len(candidates) < n_neighborhood and neighbor_attempts < max_attempts:
        neighbor_attempts += 1
        candidate = dict(baseline)  # start from baseline
        # Pick 1 or 2 dims to perturb
        n_perturb = rng.choice([1, 1, 1, 2])  # bias toward single-dim changes
        dims_to_change = rng.sample(
            perturbable_dims + list_dims,
            min(n_perturb, len(perturbable_dims) + len(list_dims)),
        )
        for dim in dims_to_change:
            if dim == "strategy_sets":
                candidate["enabled_strategies"] = list(rng.choice(search_space["strategy_sets"]))
            elif dim == "regime_filter_sets":
                candidate["regime_filter"] = list(rng.choice(search_space["regime_filter_sets"]))
            elif dim == "time_window_sets":
                candidate["trading_hours"] = list(rng.choice(search_space["time_window_sets"]))
            elif dim in search_space:
                candidate[dim] = rng.choice(search_space[dim])
        key = _v2_candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)

    # --- Phase 2: random candidates (exploration) ---
    while len(candidates) < n_trials and attempts < max_attempts:
        attempts += 1
        strategy_set = rng.choice(search_space["strategy_sets"])
        regime_set = rng.choice(search_space["regime_filter_sets"])

        candidate = {
            # V1 adaptive dims
            "strategy_selection_mode": rng.choice(search_space["strategy_selection_mode"]),
            "max_active_strategies": rng.choice(search_space["max_active_strategies"]),
            "min_active_bars_before_switch": rng.choice(search_space["min_active_bars_before_switch"]),
            "switch_cooldown_bars": rng.choice(search_space["switch_cooldown_bars"]),
            "flow_bias_enabled": rng.choice(search_space["flow_bias_enabled"]),
            "use_ohlcv_fallbacks": rng.choice(search_space["use_ohlcv_fallbacks"]),
            # V2 strategy dim
            "enabled_strategies": list(strategy_set),
            # V2 L2 dims
            "l2_min_delta": rng.choice(search_space["l2_min_delta"]),
            "l2_min_imbalance": rng.choice(search_space["l2_min_imbalance"]),
            "l2_min_signed_aggression": rng.choice(search_space["l2_min_signed_aggression"]),
            "l2_min_directional_consistency": rng.choice(search_space["l2_min_directional_consistency"]),
            # V2 regime dim
            "regime_filter": list(regime_set),
            # V2 evidence dims
            "base_threshold": rng.choice(search_space["base_threshold"]),
            "min_confirming_sources": rng.choice(search_space["min_confirming_sources"]),
            # V2 per-strategy param dims
            "min_confidence": rng.choice(search_space["min_confidence"]),
            "atr_stop_multiplier": rng.choice(search_space["atr_stop_multiplier"]),
            "rr_ratio": rng.choice(search_space["rr_ratio"]),
            # V2 time-of-day dim
            "trading_hours": list(rng.choice(search_space["time_window_sets"])),
            # V2 flow exit dims
            "adverse_flow_consistency": rng.choice(search_space["adverse_flow_consistency"]),
            "adverse_book_pressure": rng.choice(search_space["adverse_book_pressure"]),
            # V2 exit dims
            "time_exit_bars": rng.choice(search_space["time_exit_bars"]),
            "trailing_stop_pct": rng.choice(search_space["trailing_stop_pct"]),
        }
        key = _v2_candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def _build_v2_baseline_candidate(
    search_space: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a baseline candidate using the first (default) value of each dimension."""
    def _first(key: str):
        vals = search_space.get(key, [])
        return vals[0] if vals else None

    return {
        "strategy_selection_mode": _first("strategy_selection_mode"),
        "max_active_strategies": _first("max_active_strategies"),
        "min_active_bars_before_switch": _first("min_active_bars_before_switch"),
        "switch_cooldown_bars": _first("switch_cooldown_bars"),
        "flow_bias_enabled": _first("flow_bias_enabled"),
        "use_ohlcv_fallbacks": _first("use_ohlcv_fallbacks"),
        "enabled_strategies": list(search_space["strategy_sets"][0]) if search_space.get("strategy_sets") else [],
        "l2_min_delta": _first("l2_min_delta"),
        "l2_min_imbalance": _first("l2_min_imbalance"),
        "l2_min_signed_aggression": _first("l2_min_signed_aggression"),
        "l2_min_directional_consistency": _first("l2_min_directional_consistency"),
        "regime_filter": list(search_space["regime_filter_sets"][0]) if search_space.get("regime_filter_sets") else [],
        "base_threshold": _first("base_threshold"),
        "min_confirming_sources": _first("min_confirming_sources"),
        "min_confidence": _first("min_confidence"),
        "atr_stop_multiplier": _first("atr_stop_multiplier"),
        "rr_ratio": _first("rr_ratio"),
        "trading_hours": list(search_space["time_window_sets"][0]) if search_space.get("time_window_sets") else [],
        "adverse_flow_consistency": _first("adverse_flow_consistency"),
        "adverse_book_pressure": _first("adverse_book_pressure"),
        "time_exit_bars": _first("time_exit_bars"),
        "trailing_stop_pct": _first("trailing_stop_pct"),
    }


def _build_v2_candidate_config(
    ticker_config: Dict[str, Any],
    candidate: Dict[str, Any],
    adaptive_version: int,
) -> Dict[str, Any]:
    """Apply all v2 candidate dimensions to ticker config."""
    # Start with v1 adaptive config
    cfg = _build_adaptive_candidate_config(ticker_config, candidate, adaptive_version)

    # -- Strategy dimension: set primary & backup strategies --
    enabled = candidate.get("enabled_strategies", [])
    if isinstance(enabled, list) and enabled:
        cfg["strategy"] = str(enabled[0])
        if len(enabled) > 1:
            cfg["backup_strategy"] = str(enabled[1])
        else:
            cfg["backup_strategy"] = ""

    # -- L2 dimension: inject L2 threshold overrides --
    l2_cfg = cfg.get("l2", {})
    if not isinstance(l2_cfg, dict):
        l2_cfg = {}
    l2_keys = [
        ("l2_min_delta", "min_delta"),
        ("l2_min_imbalance", "min_imbalance"),
        ("l2_min_signed_aggression", "min_signed_aggression"),
        ("l2_min_directional_consistency", "min_directional_consistency"),
    ]
    for candidate_key, config_key in l2_keys:
        val = candidate.get(candidate_key)
        if val is not None:
            try:
                l2_cfg[config_key] = float(val)
            except (TypeError, ValueError):
                pass
    cfg["l2"] = l2_cfg

    # -- Regime dimension: override regime_filter --
    regime_filter = candidate.get("regime_filter")
    if isinstance(regime_filter, list) and regime_filter:
        cfg["regime_filter"] = list(regime_filter)

    # -- Evidence dimension: store in adaptive config for strategy API to read --
    adaptive_cfg = cfg.get("adaptive", {})
    if not isinstance(adaptive_cfg, dict):
        adaptive_cfg = {}
    base_thresh = candidate.get("base_threshold")
    if base_thresh is not None:
        try:
            adaptive_cfg["evidence_base_threshold"] = float(base_thresh)
        except (TypeError, ValueError):
            pass
    min_sources = candidate.get("min_confirming_sources")
    if min_sources is not None:
        try:
            adaptive_cfg["evidence_min_confirming_sources"] = int(min_sources)
        except (TypeError, ValueError):
            pass
    cfg["adaptive"] = adaptive_cfg

    # -- Per-strategy parameter overrides (applied globally to all enabled strategies) --
    strategy_param_overrides: Dict[str, Any] = {}
    for param_key in ("min_confidence", "atr_stop_multiplier", "rr_ratio"):
        val = candidate.get(param_key)
        if val is not None:
            try:
                strategy_param_overrides[param_key] = float(val)
            except (TypeError, ValueError):
                pass
    if strategy_param_overrides:
        cfg["v2_strategy_param_overrides"] = strategy_param_overrides

    # -- Time-of-day dimension: inject trading_hours --
    trading_hours = candidate.get("trading_hours")
    if isinstance(trading_hours, list) and trading_hours:
        cfg["trading_hours"] = [int(h) for h in trading_hours]
        cfg["time_filter_enabled"] = True
    else:
        # No time restriction for this candidate
        cfg["time_filter_enabled"] = False

    # -- Flow exit thresholds --
    adv_consistency = candidate.get("adverse_flow_consistency")
    if adv_consistency is not None:
        cfg["adverse_flow_consistency_threshold"] = float(adv_consistency)
    adv_book = candidate.get("adverse_book_pressure")
    if adv_book is not None:
        cfg["adverse_book_pressure_threshold"] = float(adv_book)

    # -- Exit parameter dims --
    te_bars = candidate.get("time_exit_bars")
    if te_bars is not None:
        cfg["time_exit_bars"] = int(te_bars)
    ts_pct = candidate.get("trailing_stop_pct")
    if ts_pct is not None:
        # Store globally; strategies will read from v2_strategy_param_overrides
        overrides = cfg.get("v2_strategy_param_overrides", {})
        overrides["trailing_stop_pct"] = float(ts_pct)
        cfg["v2_strategy_param_overrides"] = overrides

    return cfg


async def _evaluate_v2_candidate(
    *,
    job_id: str,
    ticker: str,
    dates: List[str],
    trial_index: int,
    candidate: Dict[str, Any],
    request: AdaptiveTunerRequest,
) -> Dict[str, Any]:
    """Evaluate a v2 candidate — same as v1 but with enriched metrics and v2 config injection."""
    total_pnl_pct = 0.0
    total_pnl_dollars = 0.0
    total_win_rate_pct = 0.0
    total_trades = 0
    valid_days = 0
    day_results: List[Dict[str, Any]] = []

    for day_idx, date in enumerate(dates):
        run_id = f"adaptive-v2-{job_id[:8]}-{trial_index}-{day_idx}"
        run_request = StartRunRequest(
            run_id=run_id,
            ticker=ticker,
            date=date,
            strategy_api_url=request.strategy_api_url,
            allow_mock_data=bool(request.allow_mock_data),
            comparable_mode=bool(request.comparable_mode),
            apply_ticker_overrides_on_start=False,
            l2_confirm_enabled=bool(request.l2_confirm_enabled),
            l2_only=bool(request.l2_only),
            intrabar_execution_recalc_1s=False,
            strategy_selection_mode=_normalize_strategy_selection_mode(
                candidate.get("strategy_selection_mode")
            ),
            max_active_strategies=_normalize_clamped_int(
                candidate.get("max_active_strategies"), default=3, min_value=1, max_value=20
            ),
        )
        run_key: Optional[str] = None
        try:
            start_result = await start_run(run_request)
            run_key = str(start_result.get("run_key", ""))
            runner = active_runners.get(run_key)
            if runner is None:
                raise RuntimeError(f"Runner not found for key {run_key}")

            # Push per-strategy param overrides (v2) before running the backtest
            v2_param_overrides = {}
            for pkey in ("min_confidence", "atr_stop_multiplier", "rr_ratio", "trailing_stop_pct"):
                pval = candidate.get(pkey)
                if pval is not None:
                    try:
                        v2_param_overrides[pkey] = float(pval)
                    except (TypeError, ValueError):
                        pass
            if v2_param_overrides:
                enabled_strats = candidate.get("enabled_strategies", [])
                if isinstance(enabled_strats, list) and enabled_strats:
                    param_map = {
                        str(s).strip(): dict(v2_param_overrides) for s in enabled_strats if s
                    }
                    if param_map:
                        try:
                            await _apply_strategy_param_map(request.strategy_api_url, param_map)
                        except Exception:
                            pass  # best-effort

            await runner.run_all(speed_ms=0)
            summary_payload = runner.get_summary()
            session_summary = summary_payload.get("session_summary") if isinstance(summary_payload, dict) else None
            summary = session_summary if isinstance(session_summary, dict) else {}
            pnl_pct = float(summary.get("total_pnl_pct", 0.0) or 0.0)
            pnl_dollars = float(summary.get("total_pnl_dollars", 0.0) or 0.0)
            win_rate_pct = float(summary.get("win_rate", 0.0) or 0.0)
            trades = int(summary.get("total_trades", 0) or 0)
            total_pnl_pct += pnl_pct
            total_pnl_dollars += pnl_dollars
            total_win_rate_pct += win_rate_pct
            total_trades += trades
            valid_days += 1
            day_results.append({
                "date": date,
                "success": True,
                "pnl_pct": pnl_pct,
                "pnl_dollars": pnl_dollars,
                "win_rate_pct": win_rate_pct,
                "trades": trades,
            })
        except HTTPException as exc:
            day_results.append({
                "date": date,
                "success": False,
                "error": f"HTTP {exc.status_code}: {exc.detail}",
            })
        except Exception as exc:
            day_results.append({
                "date": date,
                "success": False,
                "error": str(exc),
            })
        finally:
            if run_key:
                active_runners.pop(run_key, None)

    avg_win_rate_pct = (total_win_rate_pct / valid_days) if valid_days > 0 else 0.0
    if str(request.score_metric or "").strip().lower() == "robust":
        # 3-fold temporal cross-validation: score = average of validation-fold scores
        # This prevents candidates from winning on lucky day subsets
        successful_results = [d for d in day_results if d.get("success")]
        n_successful = len(successful_results)
        if n_successful >= 3:
            fold_size = max(1, n_successful // 3)
            val_scores = []
            for fold_idx in range(3):
                fold_start = fold_idx * fold_size
                fold_end = fold_start + fold_size if fold_idx < 2 else n_successful
                val_fold = successful_results[fold_start:fold_end]
                if val_fold:
                    val_scores.append(_compute_tuner_score_robust(val_fold))
            score = sum(val_scores) / len(val_scores) if val_scores else -1_000_000.0
        else:
            # Too few days for CV — use direct score but with heavy penalty
            score = _compute_tuner_score_robust(day_results) * 0.5
    else:
        score = _compute_tuner_score(
            score_metric=request.score_metric,
            total_pnl_pct=total_pnl_pct,
            total_pnl_dollars=total_pnl_dollars,
            avg_win_rate_pct=avg_win_rate_pct,
            total_trades=total_trades,
            valid_days=valid_days,
        )
    return {
        "trial_index": trial_index,
        "candidate": candidate,
        "score": round(float(score), 6),
        "metrics": {
            "valid_days": valid_days,
            "total_days": len(dates),
            "total_trades": total_trades,
            "total_pnl_pct": round(total_pnl_pct, 4),
            "avg_pnl_pct": round((total_pnl_pct / valid_days), 4) if valid_days > 0 else 0.0,
            "total_pnl_dollars": round(total_pnl_dollars, 4),
            "avg_pnl_dollars": round((total_pnl_dollars / valid_days), 4) if valid_days > 0 else 0.0,
            "avg_win_rate_pct": round(avg_win_rate_pct, 4),
        },
        # V2 enriched metadata
        "vector_dimensions": {
            "enabled_strategies": candidate.get("enabled_strategies", []),
            "regime_filter": candidate.get("regime_filter", []),
            "l2_min_imbalance": candidate.get("l2_min_imbalance"),
            "l2_min_signed_aggression": candidate.get("l2_min_signed_aggression"),
            "base_threshold": candidate.get("base_threshold"),
            "min_confirming_sources": candidate.get("min_confirming_sources"),
        },
        "day_results": day_results,
        "completed_at": datetime.utcnow().isoformat() + "Z",
    }


def _analyze_vectors(
    trials: List[Dict[str, Any]],
    *,
    min_trades: int = 3,
) -> Dict[str, Any]:
    """Analyze trial results to discover dimension importance & surprising vectors."""
    if not trials:
        return {"dimension_importance": {}, "top_interactions": [], "surprising_vectors": []}

    # Filter to valid trials with sufficient trades
    valid_trials = [
        t for t in trials
        if isinstance(t, dict)
        and float(t.get("score", -1e12)) > -999_999
        and int(t.get("metrics", {}).get("total_trades", 0)) >= min_trades
    ]
    if len(valid_trials) < 2:
        return {"dimension_importance": {}, "top_interactions": [], "surprising_vectors": []}

    scores = [float(t["score"]) for t in valid_trials]
    overall_mean = sum(scores) / len(scores)
    total_variance = sum((s - overall_mean) ** 2 for s in scores) / len(scores)
    if total_variance < 1e-12:
        return {"dimension_importance": {}, "top_interactions": [], "surprising_vectors": []}

    # --- Dimension importance: variance explained by each dimension ---
    dimension_extractors = {
        "strategy_set": lambda c: str(sorted(c.get("enabled_strategies", []))),
        "l2_thresholds": lambda c: f"{c.get('l2_min_imbalance', 0):.3f}|{c.get('l2_min_signed_aggression', 0):.3f}",
        "regime_filter": lambda c: str(sorted(c.get("regime_filter", []))),
        "evidence_params": lambda c: f"{c.get('base_threshold', 50)}|{c.get('min_confirming_sources', 2)}",
        "v1_adaptive": lambda c: f"{c.get('strategy_selection_mode')}|{c.get('flow_bias_enabled')}",
    }

    dim_importance = {}
    for dim_name, extractor in dimension_extractors.items():
        groups: Dict[str, List[float]] = {}
        for trial in valid_trials:
            candidate = trial.get("candidate", {})
            group_key = extractor(candidate)
            groups.setdefault(group_key, []).append(float(trial["score"]))

        if len(groups) < 2:
            dim_importance[dim_name] = 0.0
            continue

        # Between-group variance (variance of group means)
        group_means = [sum(vals) / len(vals) for vals in groups.values()]
        between_var = sum((gm - overall_mean) ** 2 for gm in group_means) / len(group_means)
        dim_importance[dim_name] = round(min(1.0, between_var / total_variance), 4)

    # Normalize importance to sum to 1.0
    total_imp = sum(dim_importance.values())
    if total_imp > 0:
        dim_importance = {k: round(v / total_imp, 4) for k, v in dim_importance.items()}

    # --- Top interaction effects (pairwise) ---
    dim_names = list(dimension_extractors.keys())
    interactions = []
    for i in range(len(dim_names)):
        for j in range(i + 1, len(dim_names)):
            d1, d2 = dim_names[i], dim_names[j]
            ext1, ext2 = dimension_extractors[d1], dimension_extractors[d2]
            groups: Dict[str, List[float]] = {}
            for trial in valid_trials:
                candidate = trial.get("candidate", {})
                combo_key = f"{ext1(candidate)}||{ext2(candidate)}"
                groups.setdefault(combo_key, []).append(float(trial["score"]))
            if len(groups) < 2:
                continue
            group_means = [sum(v) / len(v) for v in groups.values()]
            between_var = sum((gm - overall_mean) ** 2 for gm in group_means) / len(group_means)
            effect = round(min(1.0, between_var / total_variance), 4) if total_variance > 0 else 0.0
            interactions.append({"dims": [d1, d2], "effect_size": effect})
    interactions.sort(key=lambda x: x["effect_size"], reverse=True)

    # --- Surprising vectors: high score from non-obvious configs ---
    score_std = (total_variance ** 0.5) if total_variance > 0 else 1.0
    threshold = overall_mean + score_std  # above 1 std is "surprising"
    surprising = []
    for trial in valid_trials:
        trial_score = float(trial["score"])
        if trial_score < threshold:
            continue
        candidate = trial.get("candidate", {})
        strategies = candidate.get("enabled_strategies", [])
        regime = candidate.get("regime_filter", [])

        # Build description
        desc_parts = []
        if strategies:
            desc_parts.append("+".join(strategies))
        if regime:
            desc_parts.append(f"regime={','.join(regime)}")
        l2_imb = candidate.get("l2_min_imbalance")
        if l2_imb is not None:
            desc_parts.append(f"l2_imb={l2_imb:.2f}")
        base_t = candidate.get("base_threshold")
        if base_t is not None:
            desc_parts.append(f"ev_thresh={base_t:.0f}")

        surprising.append({
            "description": " | ".join(desc_parts) if desc_parts else "unknown",
            "score": trial_score,
            "z_score": round((trial_score - overall_mean) / score_std, 2),
            "trial_index": trial.get("trial_index"),
            "candidate": candidate,
        })
    surprising.sort(key=lambda x: x["score"], reverse=True)

    # --- Strategy correlation / diversity scoring ---
    # Group strategies into families to detect correlated vs diversified vectors.
    STRATEGY_FAMILY = {
        "MomentumFlow": "trend-follow",
        "Momentum": "trend-follow",
        "Pullback": "trend-follow",
        "MeanReversion": "reversal",
        "AbsorptionReversal": "reversal",
        "ExhaustionFade": "reversal",
        "VWAPMagnet": "reversal",
        "VolumeProfile": "level-based",
        "GapLiquidity": "level-based",
        "Rotation": "sector",
        "IcebergDefense": "institutional",
    }
    for vec in surprising:
        strategies = vec.get("candidate", {}).get("enabled_strategies", [])
        families = set()
        for s in strategies:
            fam = STRATEGY_FAMILY.get(s)
            if fam:
                families.add(fam)
        n_families = len(families)
        n_strategies = max(len(strategies), 1)

        # Diversity score: 0.0 (all same family) to 1.0 (max diversity)
        if n_strategies <= 1:
            diversity = 0.5  # neutral for single-strategy vectors
        else:
            diversity = round(min(1.0, n_families / max(n_strategies, 1) * 1.5), 3)

        # Apply penalty/bonus to the score
        if n_families == 1 and n_strategies > 1:
            # All strategies in one family → correlation penalty
            vec["score"] = round(vec["score"] * 0.85, 4)
            vec["correlation_note"] = "Same-family penalty applied (×0.85)"
        elif n_families >= 3:
            # Good diversification → bonus
            vec["score"] = round(vec["score"] * 1.10, 4)
            vec["correlation_note"] = "Multi-family bonus applied (×1.10)"

        vec["diversity_score"] = diversity
        vec["n_families"] = n_families
        vec["strategy_families"] = sorted(families)

    # Re-sort after correlation adjustments
    surprising.sort(key=lambda x: x["score"], reverse=True)

    return {
        "dimension_importance": dim_importance,
        "top_interactions": interactions[:5],
        "surprising_vectors": surprising[:10],
        "stats": {
            "total_valid_trials": len(valid_trials),
            "overall_mean_score": round(overall_mean, 4),
            "score_std": round(score_std, 4),
        },
    }


async def _run_v2_adaptive_tuner_job(
    job_id: str,
    request: AdaptiveTunerRequest,
    dates: List[str],
) -> None:
    """Run a v2 multi-dimensional adaptive tuner job."""
    job = adaptive_tuner_jobs.get(job_id)
    if not job:
        return

    ticker = str(request.ticker or "").upper().strip()
    trial_budget = _resolve_tuner_trial_budget(
        requested_trials=request.n_trials,
        default_trials=32,
        quick_mode=bool(request.quick_mode),
        quick_trial_boost=request.quick_trial_boost,
        max_trials=400,
    )
    n_trials = trial_budget["effective"]

    async with adaptive_tuner_lock:
        original_config = _load_aos_config()
        original_ticker_config = copy.deepcopy(
            original_config.get("tickers", {}).get(ticker, {})
        )
        cfg_work = copy.deepcopy(original_config)
        if "tickers" not in cfg_work or not isinstance(cfg_work.get("tickers"), dict):
            cfg_work["tickers"] = {}

        search_space = _build_v2_search_space(request, original_ticker_config)

        # V2 only supports random and optuna (grid is infeasible)
        method = str(request.method or "random").strip().lower()
        if method == "grid":
            method = "random"
            job.setdefault("notes", []).append(
                "Grid search is not feasible for v2 multi-dimensional space; using random sampling."
            )
        method_used = method

        job["started_at"] = datetime.utcnow().isoformat() + "Z"
        job["status"] = "running"
        job["progress"] = {"completed_trials": 0, "total_trials": 0, "method": method}
        job["trials"] = []
        job["best_trial"] = None
        job["trial_budget"] = trial_budget
        job["search_space_summary"] = {
            "strategy_sets_count": len(search_space.get("strategy_sets", [])),
            "l2_options": {
                "min_delta": len(search_space.get("l2_min_delta", [])),
                "min_imbalance": len(search_space.get("l2_min_imbalance", [])),
                "min_signed_aggression": len(search_space.get("l2_min_signed_aggression", [])),
            },
            "regime_filter_sets_count": len(search_space.get("regime_filter_sets", [])),
            "evidence_options": {
                "base_threshold": len(search_space.get("base_threshold", [])),
                "min_confirming_sources": len(search_space.get("min_confirming_sources", [])),
            },
        }
        if bool(request.quick_mode) and trial_budget["boost"] > 1:
            job.setdefault("notes", []).append(
                "Quick mode trial boost applied: "
                f"{trial_budget['requested']} -> {trial_budget['effective']} "
                f"(x{trial_budget['boost']})."
            )

        try:
            optuna_module = None
            if method == "optuna":
                try:
                    import optuna as _optuna  # type: ignore
                    optuna_module = _optuna
                except Exception:
                    optuna_module = None
                    job.setdefault("notes", []).append(
                        "Optuna is not installed; fallback to random search."
                    )

            if optuna_module is None:
                # Random sampling
                method_used = "random"
                candidates = _build_v2_random_candidates(
                    search_space, n_trials=n_trials, seed=request.seed,
                    neighborhood_search=bool(request.neighborhood_search),
                )
                job["progress"]["total_trials"] = len(candidates)

                for idx, candidate in enumerate(candidates, start=1):
                    next_ticker_cfg = _build_v2_candidate_config(
                        original_ticker_config, candidate, request.adaptive_version
                    )
                    cfg_work["tickers"][ticker] = next_ticker_cfg
                    if not _save_aos_config(cfg_work):
                        raise RuntimeError("Failed to save temporary AOS config for v2 tuner trial")

                    result = await _evaluate_v2_candidate(
                        job_id=job_id,
                        ticker=ticker,
                        dates=dates,
                        trial_index=idx,
                        candidate=candidate,
                        request=request,
                    )
                    job["trials"].append(result)
                    current_best = job.get("best_trial")
                    if (
                        not isinstance(current_best, dict)
                        or float(result["score"]) > float(current_best.get("score", -1e12))
                    ):
                        job["best_trial"] = result
                    job["progress"]["completed_trials"] = idx
            else:
                # Optuna TPE sampling for v2
                method_used = "optuna"
                sampler = optuna_module.samplers.TPESampler(seed=request.seed)
                study = optuna_module.create_study(direction="maximize", sampler=sampler)
                job["progress"]["total_trials"] = n_trials

                for idx in range(1, n_trials + 1):
                    trial = study.ask()
                    ss_idx = trial.suggest_int("strategy_set_idx", 0, len(search_space["strategy_sets"]) - 1)
                    rf_idx = trial.suggest_int("regime_filter_idx", 0, len(search_space["regime_filter_sets"]) - 1)
                    candidate = {
                        "strategy_selection_mode": trial.suggest_categorical(
                            "strategy_selection_mode", search_space["strategy_selection_mode"]
                        ),
                        "max_active_strategies": trial.suggest_int(
                            "max_active_strategies",
                            min(search_space["max_active_strategies"]),
                            max(search_space["max_active_strategies"]),
                        ),
                        "min_active_bars_before_switch": trial.suggest_int(
                            "min_active_bars_before_switch",
                            min(search_space["min_active_bars_before_switch"]),
                            max(search_space["min_active_bars_before_switch"]),
                        ),
                        "switch_cooldown_bars": trial.suggest_int(
                            "switch_cooldown_bars",
                            min(search_space["switch_cooldown_bars"]),
                            max(search_space["switch_cooldown_bars"]),
                        ),
                        "flow_bias_enabled": trial.suggest_categorical(
                            "flow_bias_enabled", search_space["flow_bias_enabled"]
                        ),
                        "use_ohlcv_fallbacks": trial.suggest_categorical(
                            "use_ohlcv_fallbacks", search_space["use_ohlcv_fallbacks"]
                        ),
                        "enabled_strategies": list(search_space["strategy_sets"][ss_idx]),
                        "l2_min_delta": trial.suggest_categorical(
                            "l2_min_delta", search_space["l2_min_delta"]
                        ),
                        "l2_min_imbalance": trial.suggest_categorical(
                            "l2_min_imbalance", search_space["l2_min_imbalance"]
                        ),
                        "l2_min_signed_aggression": trial.suggest_categorical(
                            "l2_min_signed_aggression", search_space["l2_min_signed_aggression"]
                        ),
                        "l2_min_directional_consistency": trial.suggest_categorical(
                            "l2_min_directional_consistency", search_space["l2_min_directional_consistency"]
                        ),
                        "regime_filter": list(search_space["regime_filter_sets"][rf_idx]),
                        "base_threshold": trial.suggest_categorical(
                            "base_threshold", search_space["base_threshold"]
                        ),
                        "min_confirming_sources": trial.suggest_int(
                            "min_confirming_sources",
                            min(search_space["min_confirming_sources"]),
                            max(search_space["min_confirming_sources"]),
                        ),
                    }

                    next_ticker_cfg = _build_v2_candidate_config(
                        original_ticker_config, candidate, request.adaptive_version
                    )
                    cfg_work["tickers"][ticker] = next_ticker_cfg
                    if not _save_aos_config(cfg_work):
                        raise RuntimeError("Failed to save temporary AOS config for v2 tuner trial")

                    result = await _evaluate_v2_candidate(
                        job_id=job_id,
                        ticker=ticker,
                        dates=dates,
                        trial_index=idx,
                        candidate=candidate,
                        request=request,
                    )
                    score = float(result["score"])
                    study.tell(trial, score)
                    job["trials"].append(result)
                    current_best = job.get("best_trial")
                    if (
                        not isinstance(current_best, dict)
                        or score > float(current_best.get("score", -1e12))
                    ):
                        job["best_trial"] = result
                    job["progress"]["completed_trials"] = idx

            # --- Vector Analysis ---
            vector_analysis = {}
            if request.include_vector_analysis:
                vector_analysis = _analyze_vectors(
                    job.get("trials", []),
                    min_trades=max(1, request.min_trades_per_vector),
                )
                job["vector_analysis"] = vector_analysis

            # --- Save results ---
            best_trial = job.get("best_trial")
            final_config = copy.deepcopy(original_config)
            if "tickers" not in final_config or not isinstance(final_config.get("tickers"), dict):
                final_config["tickers"] = {}

            updated_ticker_cfg = copy.deepcopy(original_ticker_config)
            saved_profile = None
            if isinstance(best_trial, dict):
                saved_profile = _build_tuner_profile_entry(
                    ticker=ticker,
                    request=request,
                    method_used=method_used,
                    dates=dates,
                    best_trial=best_trial,
                )
                # Attach vector analysis to the profile
                if vector_analysis:
                    saved_profile["vector_analysis"] = vector_analysis

                existing_profiles = _normalize_tuner_profiles(
                    updated_ticker_cfg.get("adaptive_tuner_profiles", [])
                )
                existing_profiles.insert(0, saved_profile)
                updated_ticker_cfg["adaptive_tuner_profiles"] = existing_profiles[:30]

                if request.persist_best:
                    best_candidate = best_trial.get("candidate", {})
                    updated_ticker_cfg = _build_v2_candidate_config(
                        updated_ticker_cfg,
                        best_candidate if isinstance(best_candidate, dict) else {},
                        request.adaptive_version,
                    )
                    updated_ticker_cfg["active_adaptive_tuner_profile_id"] = saved_profile["profile_id"]
                    job.setdefault("notes", []).append(
                        "Best v2 vector candidate was persisted to aos_config.json."
                    )
                elif saved_profile:
                    updated_ticker_cfg["active_adaptive_tuner_profile_id"] = str(
                        updated_ticker_cfg.get("active_adaptive_tuner_profile_id", "")
                    ).strip() or saved_profile["profile_id"]

            final_config["tickers"][ticker] = updated_ticker_cfg
            if not _save_aos_config(final_config):
                raise RuntimeError("Failed to save final v2 AOS tuner result")

            job["status"] = "completed"
            job["method_used"] = method_used
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"
            job["summary"] = {
                "ticker": ticker,
                "date_from": dates[0] if dates else request.date_from,
                "date_to": dates[-1] if dates else request.date_to,
                "evaluated_days": len(dates),
                "source_effective_days": int(job.get("source_effective_days", len(dates)) or len(dates)),
                "trials": int(job["progress"].get("completed_trials", 0)),
                "best_score": float(best_trial.get("score", 0.0)) if isinstance(best_trial, dict) else None,
                "score_metric": request.score_metric,
                "adaptive_version": request.adaptive_version,
                "persist_best": bool(request.persist_best),
                "l2_required": bool(request.l2_required),
                "l2_only": bool(request.l2_only),
                "quick_mode": bool(request.quick_mode),
                "quick_max_days": _normalize_clamped_int(
                    request.quick_max_days, default=2, min_value=1, max_value=30
                ),
                "quick_trial_boost": trial_budget["boost"],
                "requested_trials": trial_budget["requested"],
                "effective_trial_budget": trial_budget["effective"],
            }
            if saved_profile:
                job["saved_profile"] = {
                    "profile_id": saved_profile.get("profile_id"),
                    "created_at": saved_profile.get("created_at"),
                }
        except Exception as exc:
            _save_aos_config(original_config)
            job["status"] = "failed"
            job["error"] = str(exc)
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"


async def _run_adaptive_tuner_job(
    job_id: str,
    request: AdaptiveTunerRequest,
    dates: List[str],
) -> None:
    job = adaptive_tuner_jobs.get(job_id)
    if not job:
        return

    ticker = str(request.ticker or "").upper().strip()
    search_space = _build_adaptive_tuner_search_space(request)
    method = str(request.method or "grid").strip().lower()
    if method not in {"grid", "random", "optuna"}:
        method = "grid"
    trial_budget = _resolve_tuner_trial_budget(
        requested_trials=request.n_trials,
        default_trials=16,
        quick_mode=bool(request.quick_mode),
        quick_trial_boost=request.quick_trial_boost,
        max_trials=400,
    )
    n_trials = trial_budget["effective"]

    async with adaptive_tuner_lock:
        original_config = _load_aos_config()
        original_ticker_config = copy.deepcopy(
            original_config.get("tickers", {}).get(ticker, {})
        )
        cfg_work = copy.deepcopy(original_config)
        if "tickers" not in cfg_work or not isinstance(cfg_work.get("tickers"), dict):
            cfg_work["tickers"] = {}

        job["started_at"] = datetime.utcnow().isoformat() + "Z"
        job["status"] = "running"
        job["progress"] = {"completed_trials": 0, "total_trials": 0, "method": method}
        job["trials"] = []
        job["best_trial"] = None
        job["trial_budget"] = trial_budget
        if bool(request.quick_mode) and trial_budget["boost"] > 1:
            job.setdefault("notes", []).append(
                "Quick mode trial boost applied: "
                f"{trial_budget['requested']} -> {trial_budget['effective']} "
                f"(x{trial_budget['boost']})."
            )

        try:
            optuna_module = None
            if method == "optuna":
                try:
                    import optuna as _optuna  # type: ignore
                    optuna_module = _optuna
                except Exception:
                    optuna_module = None
                    job.setdefault("notes", []).append(
                        "Optuna is not installed; fallback to random search."
                    )

            candidates: List[Dict[str, Any]] = []
            method_used = method
            if method == "grid":
                candidates = _build_grid_candidates(search_space)
                if len(candidates) > n_trials:
                    candidates = candidates[:n_trials]
            elif method == "random" or optuna_module is None:
                candidates = _build_random_candidates(
                    search_space, n_trials=n_trials, seed=request.seed
                )
                method_used = "random" if method == "optuna" else method
            else:
                # Optuna ask/tell loop will generate candidates on-the-fly.
                candidates = []
                method_used = "optuna"

            if method_used != "optuna":
                job["progress"]["total_trials"] = len(candidates)
                for idx, candidate in enumerate(candidates, start=1):
                    next_ticker_cfg = _build_adaptive_candidate_config(
                        original_ticker_config,
                        candidate,
                        request.adaptive_version,
                    )
                    cfg_work["tickers"][ticker] = next_ticker_cfg
                    if not _save_aos_config(cfg_work):
                        raise RuntimeError("Failed to save temporary AOS config for tuner trial")

                    result = await _evaluate_adaptive_tuner_candidate(
                        job_id=job_id,
                        ticker=ticker,
                        dates=dates,
                        trial_index=idx,
                        candidate=candidate,
                        request=request,
                    )
                    job["trials"].append(result)
                    current_best = job.get("best_trial")
                    if (
                        not isinstance(current_best, dict)
                        or float(result["score"]) > float(current_best.get("score", -1e12))
                    ):
                        job["best_trial"] = result
                    job["progress"]["completed_trials"] = idx
            else:
                assert optuna_module is not None
                sampler = optuna_module.samplers.TPESampler(seed=request.seed)
                study = optuna_module.create_study(direction="maximize", sampler=sampler)
                job["progress"]["total_trials"] = n_trials
                for idx in range(1, n_trials + 1):
                    trial = study.ask()
                    candidate = {
                        "strategy_selection_mode": trial.suggest_categorical(
                            "strategy_selection_mode", search_space["strategy_selection_mode"]
                        ),
                        "max_active_strategies": trial.suggest_int(
                            "max_active_strategies",
                            min(search_space["max_active_strategies"]),
                            max(search_space["max_active_strategies"]),
                        ),
                        "min_active_bars_before_switch": trial.suggest_int(
                            "min_active_bars_before_switch",
                            min(search_space["min_active_bars_before_switch"]),
                            max(search_space["min_active_bars_before_switch"]),
                        ),
                        "switch_cooldown_bars": trial.suggest_int(
                            "switch_cooldown_bars",
                            min(search_space["switch_cooldown_bars"]),
                            max(search_space["switch_cooldown_bars"]),
                        ),
                        "flow_bias_enabled": trial.suggest_categorical(
                            "flow_bias_enabled", search_space["flow_bias_enabled"]
                        ),
                        "use_ohlcv_fallbacks": trial.suggest_categorical(
                            "use_ohlcv_fallbacks", search_space["use_ohlcv_fallbacks"]
                        ),
                    }
                    next_ticker_cfg = _build_adaptive_candidate_config(
                        original_ticker_config,
                        candidate,
                        request.adaptive_version,
                    )
                    cfg_work["tickers"][ticker] = next_ticker_cfg
                    if not _save_aos_config(cfg_work):
                        raise RuntimeError("Failed to save temporary AOS config for tuner trial")

                    result = await _evaluate_adaptive_tuner_candidate(
                        job_id=job_id,
                        ticker=ticker,
                        dates=dates,
                        trial_index=idx,
                        candidate=candidate,
                        request=request,
                    )
                    score = float(result["score"])
                    study.tell(trial, score)
                    job["trials"].append(result)
                    current_best = job.get("best_trial")
                    if (
                        not isinstance(current_best, dict)
                        or score > float(current_best.get("score", -1e12))
                    ):
                        job["best_trial"] = result
                    job["progress"]["completed_trials"] = idx

            best_trial = job.get("best_trial")
            final_config = copy.deepcopy(original_config)
            if "tickers" not in final_config or not isinstance(final_config.get("tickers"), dict):
                final_config["tickers"] = {}

            updated_ticker_cfg = copy.deepcopy(original_ticker_config)
            saved_profile = None
            if isinstance(best_trial, dict):
                saved_profile = _build_tuner_profile_entry(
                    ticker=ticker,
                    request=request,
                    method_used=method_used,
                    dates=dates,
                    best_trial=best_trial,
                )
                existing_profiles = _normalize_tuner_profiles(
                    updated_ticker_cfg.get("adaptive_tuner_profiles", [])
                )
                existing_profiles.insert(0, saved_profile)
                updated_ticker_cfg["adaptive_tuner_profiles"] = existing_profiles[:30]

                if request.persist_best:
                    best_candidate = best_trial.get("candidate", {})
                    updated_ticker_cfg = _build_adaptive_candidate_config(
                        updated_ticker_cfg,
                        best_candidate if isinstance(best_candidate, dict) else {},
                        request.adaptive_version,
                    )
                    updated_ticker_cfg["active_adaptive_tuner_profile_id"] = saved_profile["profile_id"]
                    job.setdefault("notes", []).append(
                        "Best candidate was persisted to aos_config.json."
                    )
                elif saved_profile:
                    updated_ticker_cfg["active_adaptive_tuner_profile_id"] = str(
                        updated_ticker_cfg.get("active_adaptive_tuner_profile_id", "")
                    ).strip() or saved_profile["profile_id"]

            final_config["tickers"][ticker] = updated_ticker_cfg
            if not _save_aos_config(final_config):
                raise RuntimeError("Failed to save final AOS tuner result")

            job["status"] = "completed"
            job["method_used"] = method_used
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"
            job["summary"] = {
                "ticker": ticker,
                "date_from": dates[0] if dates else request.date_from,
                "date_to": dates[-1] if dates else request.date_to,
                "evaluated_days": len(dates),
                "source_effective_days": int(job.get("source_effective_days", len(dates)) or len(dates)),
                "trials": int(job["progress"].get("completed_trials", 0)),
                "best_score": float(best_trial.get("score", 0.0)) if isinstance(best_trial, dict) else None,
                "score_metric": request.score_metric,
                "adaptive_version": request.adaptive_version,
                "persist_best": bool(request.persist_best),
                "l2_required": bool(request.l2_required),
                "l2_only": bool(request.l2_only),
                "quick_mode": bool(request.quick_mode),
                "quick_max_days": _normalize_clamped_int(
                    request.quick_max_days, default=2, min_value=1, max_value=30
                ),
                "quick_trial_boost": trial_budget["boost"],
                "requested_trials": trial_budget["requested"],
                "effective_trial_budget": trial_budget["effective"],
            }
            if saved_profile:
                job["saved_profile"] = {
                    "profile_id": saved_profile.get("profile_id"),
                    "created_at": saved_profile.get("created_at"),
                }
        except Exception as exc:
            _save_aos_config(original_config)
            job["status"] = "failed"
            job["error"] = str(exc)
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"


# ============ API Endpoints ============

@app.get("/")
async def root():
    return {
        "name": "Unified Backtest Runner",
        "version": "1.0.0",
        "active_runs": len(active_runners)
    }


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/available-data")
async def get_available_data():
    """Get available tickers and date ranges from data files."""
    return databento_svc.get_available_data_summary(refresh=False)


@app.get("/api/strategy-overrides")
async def get_strategy_overrides():
    """Get optimized strategy parameters per ticker."""
    return _load_strategy_overrides()


@app.get("/api/strategy-overrides/{ticker}")
async def get_ticker_overrides(ticker: str):
    """Get optimized strategy parameters for a specific ticker."""
    overrides = _load_strategy_overrides()
    return overrides.get(ticker.upper(), {})


@app.get("/api/strategy-combos/{ticker}")
async def get_strategy_combos(ticker: str):
    """Get saved strategy-parameter combo profiles for a ticker."""
    return _build_strategy_combo_options_payload(ticker)


@app.post("/api/strategy-combos/capture")
async def capture_strategy_combo(request: StrategyComboCaptureRequest):
    """Capture current strategy API settings into a saved ticker combo profile."""
    ticker = str(request.ticker or "").upper().strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")

    profile_name = str(request.profile_name or "").strip()
    if not profile_name:
        profile_name = f"{ticker}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    strategies_payload = await _fetch_remote_strategies(request.strategy_api_url)
    strategy_params = _extract_strategy_params_for_profile(strategies_payload)
    if not strategy_params:
        raise HTTPException(400, "No strategy parameters available to capture.")

    config = _load_aos_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    profiles = _normalize_strategy_combo_profiles(ticker_cfg.get("strategy_combo_profiles", []))
    entry = _build_strategy_combo_profile_entry(
        ticker=ticker,
        profile_name=profile_name,
        strategy_params=strategy_params,
    )
    profiles.insert(0, entry)
    ticker_cfg["strategy_combo_profiles"] = profiles[:30]
    if request.set_active:
        ticker_cfg["active_strategy_combo_profile_id"] = entry["profile_id"]
    config["tickers"][ticker] = ticker_cfg
    if not _save_aos_config(config):
        raise HTTPException(500, "Failed to save strategy combo profile")

    return {
        "success": True,
        "ticker": ticker,
        "profile": entry,
        "active_profile_id": str(ticker_cfg.get("active_strategy_combo_profile_id", "")).strip()
        or None,
    }


@app.post("/api/strategy-combos/apply")
async def apply_strategy_combo(request: StrategyComboApplyRequest):
    """Set active strategy combo profile and optionally apply it to strategy API immediately."""
    ticker = str(request.ticker or "").upper().strip()
    profile_id = str(request.profile_id or "").strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")
    if not profile_id:
        raise HTTPException(400, "profile_id is required")

    config = _load_aos_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    profiles = _normalize_strategy_combo_profiles(ticker_cfg.get("strategy_combo_profiles", []))
    target_profile = next(
        (profile for profile in profiles if str(profile.get("profile_id")) == profile_id),
        None,
    )
    if not isinstance(target_profile, dict):
        raise HTTPException(404, f"Strategy combo profile not found: {profile_id}")

    ticker_cfg["strategy_combo_profiles"] = profiles
    ticker_cfg["active_strategy_combo_profile_id"] = profile_id
    config["tickers"][ticker] = ticker_cfg
    if not _save_aos_config(config):
        raise HTTPException(500, "Failed to save active strategy combo profile")

    apply_result: Dict[str, Any] = {}
    if request.apply_now:
        strategy_params = target_profile.get("strategy_params", {})
        if isinstance(strategy_params, dict):
            apply_result = await _apply_strategy_param_map(
                request.strategy_api_url,
                strategy_params,
            )

    return {
        "success": True,
        "ticker": ticker,
        "profile_id": profile_id,
        "profile_name": str(target_profile.get("profile_name") or profile_id),
        "apply_now": bool(request.apply_now),
        "apply_result": apply_result,
    }


@app.get("/api/data/files")
async def list_data_files():
    """List available data files."""
    return data_loader.list_available_files()


@app.get("/api/aos-config")
async def get_aos_config():
    """Get full AOS optimization config."""
    return _load_aos_config()


@app.get("/api/aos-config/{ticker}")
async def get_ticker_aos_config(ticker: str):
    """Get AOS config for a specific ticker."""
    config = _load_aos_config()
    ticker_config = config.get("tickers", {}).get(ticker.upper(), {})
    return ticker_config


class AOSUpdateRequest(BaseModel):
    ticker: str
    config: Dict[str, Any]


@app.post("/api/aos-config/update")
async def update_aos_config(request: AOSUpdateRequest):
    """Update AOS config for a specific ticker."""
    config = _load_aos_config()
    
    if "tickers" not in config:
        config["tickers"] = {}
    
    # Merge with existing config
    ticker_upper = request.ticker.upper()
    existing = config["tickers"].get(ticker_upper, {})
    existing.update(request.config)
    config["tickers"][ticker_upper] = existing
    
    # Save
    if _save_aos_config(config):
        logger.info(f"Updated AOS config for {ticker_upper}: {request.config}")
        return {"success": True, "config": existing}
    else:
        raise HTTPException(500, "Failed to save AOS config")


@app.get("/api/adaptive-tuner/options/{ticker}")
async def get_adaptive_tuner_options(ticker: str):
    """Get real coverage ranges and saved tuner profiles for a ticker."""
    return _build_adaptive_tuner_options_payload(ticker)


@app.post("/api/adaptive-tuner/profiles/apply")
async def apply_adaptive_tuner_profile(request: AdaptiveTunerProfileApplyRequest):
    """Apply a saved adaptive-tuner profile into active ticker AOS settings."""
    ticker = str(request.ticker or "").upper().strip()
    profile_id = str(request.profile_id or "").strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")
    if not profile_id:
        raise HTTPException(400, "profile_id is required")

    config = _load_aos_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    profiles = _normalize_tuner_profiles(ticker_cfg.get("adaptive_tuner_profiles", []))
    target_profile = next(
        (profile for profile in profiles if str(profile.get("profile_id")) == profile_id),
        None,
    )
    if not isinstance(target_profile, dict):
        raise HTTPException(404, f"Adaptive tuner profile not found: {profile_id}")

    best_candidate = target_profile.get("candidate", {})
    adaptive_version = _normalize_non_negative_int(
        target_profile.get("adaptive_version", 1),
        default=1,
        max_value=10,
    ) or 1
    safe_candidate = best_candidate if isinstance(best_candidate, dict) else {}
    if adaptive_version >= 2:
        updated_cfg = _build_v2_candidate_config(
            ticker_cfg, safe_candidate, adaptive_version=adaptive_version,
        )
    else:
        updated_cfg = _build_adaptive_candidate_config(
            ticker_cfg, safe_candidate, adaptive_version=adaptive_version,
        )
    updated_cfg["adaptive_tuner_profiles"] = profiles
    updated_cfg["active_adaptive_tuner_profile_id"] = profile_id
    config["tickers"][ticker] = updated_cfg

    if not _save_aos_config(config):
        raise HTTPException(500, "Failed to apply adaptive tuner profile")

    return {
        "success": True,
        "ticker": ticker,
        "profile_id": profile_id,
        "applied_candidate": best_candidate if isinstance(best_candidate, dict) else {},
    }


@app.post("/api/adaptive-tuner/run")
async def run_adaptive_tuner(request: AdaptiveTunerRequest):
    """Start an adaptive-tuner job (v1 or v2) and return a job id for polling."""
    ticker = str(request.ticker or "").upper().strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")
    version = _normalize_non_negative_int(request.adaptive_version, default=1, max_value=10)
    if version not in (1, 2):
        raise HTTPException(400, "Only adaptive versions 1 and 2 are supported by this tuner.")

    # Validate requested dates early and resolve L2-filtered dates if required.
    requested_dates = _iter_date_strings(request.date_from, request.date_to)
    if not requested_dates:
        raise HTTPException(400, "No dates to tune.")
    effective_dates = _resolve_l2_tuning_dates(
        ticker=ticker,
        date_from=request.date_from,
        date_to=request.date_to,
        l2_required=bool(request.l2_required),
    )
    if not effective_dates:
        raise HTTPException(
            400,
            "No eligible dates found for adaptive tuning in the requested range."
            " Check OHLCV/L2 coverage for this ticker.",
        )
    source_effective_dates = list(effective_dates)

    quick_mode = bool(request.quick_mode)
    quick_max_days = _normalize_clamped_int(
        request.quick_max_days, default=2, min_value=1, max_value=30
    )
    quick_trial_boost = _normalize_clamped_int(
        request.quick_trial_boost, default=3, min_value=1, max_value=10
    )
    if quick_mode:
        effective_dates = _sample_evenly_spaced_days(effective_dates, max_days=quick_max_days)
        if not effective_dates:
            raise HTTPException(
                400,
                "Quick mode could not find representative dates in requested range.",
            )

    job_id = uuid4().hex
    method = str(request.method or ("random" if version == 2 else "grid")).strip().lower()
    if method not in {"grid", "random", "optuna"}:
        method = "random" if version == 2 else "grid"

    adaptive_tuner_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "request": request.model_dump() if hasattr(request, "model_dump") else request.dict(),
        "progress": {"completed_trials": 0, "total_trials": 0, "method": method},
        "trials": [],
        "best_trial": None,
        "notes": [],
        "requested_date_from": request.date_from,
        "requested_date_to": request.date_to,
        "source_effective_dates": source_effective_dates,
        "source_effective_date_from": source_effective_dates[0] if source_effective_dates else None,
        "source_effective_date_to": source_effective_dates[-1] if source_effective_dates else None,
        "source_effective_days": len(source_effective_dates),
        "effective_dates": effective_dates,
        "effective_date_from": effective_dates[0] if effective_dates else None,
        "effective_date_to": effective_dates[-1] if effective_dates else None,
        "effective_days": len(effective_dates),
        "quick_mode": quick_mode,
        "quick_max_days": quick_max_days,
        "quick_trial_boost": quick_trial_boost,
        "adaptive_version": version,
    }
    if quick_mode:
        adaptive_tuner_jobs[job_id]["notes"].append(
            "Quick mode enabled: sampled "
            f"{len(effective_dates)}/{len(source_effective_dates)} days; "
            f"trial budget multiplier x{quick_trial_boost}."
        )

    if version == 2:
        asyncio.create_task(_run_v2_adaptive_tuner_job(job_id, request, effective_dates))
    else:
        asyncio.create_task(_run_adaptive_tuner_job(job_id, request, effective_dates))

    return {
        "job_id": job_id,
        "status": "queued",
        "ticker": ticker,
        "date_from": request.date_from,
        "date_to": request.date_to,
        "adaptive_version": version,
        "effective_days": len(effective_dates),
        "source_effective_days": len(source_effective_dates),
        "effective_date_from": effective_dates[0] if effective_dates else None,
        "effective_date_to": effective_dates[-1] if effective_dates else None,
        "l2_required": bool(request.l2_required),
        "quick_mode": quick_mode,
        "quick_max_days": quick_max_days,
        "quick_trial_boost": quick_trial_boost,
    }


@app.get("/api/adaptive-tuner/{job_id}")
async def get_adaptive_tuner_job(job_id: str):
    """Get current status and results of an adaptive tuner job."""
    job = adaptive_tuner_jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Adaptive tuner job not found: {job_id}")
    return job


@app.get("/api/adaptive-tuner")
async def list_adaptive_tuner_jobs(limit: int = 20):
    """List recent adaptive tuner jobs."""
    limit = max(1, min(100, int(limit)))
    jobs = list(adaptive_tuner_jobs.values())
    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jobs[:limit]


@app.post("/api/run/start")
async def start_run(request: StartRunRequest):
    """Start a new backtest run."""
    ticker = request.ticker.upper()
    comparable_mode = bool(request.comparable_mode)
    effective_cold_start_each_day = bool(request.cold_start_each_day or comparable_mode)

    # Resolve date range
    if request.date_from and request.date_to:
        range_start = request.date_from
        range_end = request.date_to
    elif request.date:
        range_start = request.date
        range_end = request.date
    else:
        raise HTTPException(400, "Either date or date_from/date_to must be provided")

    run_date_label = (
        f"{range_start}_to_{range_end}"
        if range_start != range_end or request.date_from or request.date_to
        else range_start
    )

    run_key = f"{request.run_id}:{ticker}:{run_date_label}"
    
    if run_key in active_runners:
        raise HTTPException(400, f"Run already exists: {run_key}")

    # Orchestrator state reset: cold start (full) or warm start (session-only).
    checkpoint_loaded = None
    use_checkpoint = bool(request.checkpoint_path) and not comparable_mode
    if use_checkpoint:
        # Warm start: reset only per-session state, then load checkpoint
        orchestrator_reset = await _reset_remote_orchestrator_state_scoped(
            request.strategy_api_url, scope="session"
        )
        checkpoint_loaded = await _load_remote_checkpoint(
            request.strategy_api_url, request.checkpoint_path
        )
    else:
        # Cold start (default): full reset for deterministic backtests
        orchestrator_reset = await _reset_remote_orchestrator_state(request.strategy_api_url)
        if comparable_mode and request.checkpoint_path:
            logger.info(
                "Comparable mode ignores checkpoint_path and always starts from a cold state."
            )

    # Defensive cleanup in strategy API for reruns with the same run_id+ticker.
    await _clear_remote_strategy_sessions(request.strategy_api_url, request.run_id, ticker)

    strategy_overrides_applied = bool(request.apply_ticker_overrides_on_start)
    # Apply per-ticker strategy overrides (best-effort) only when explicitly enabled.
    # Frontend-driven runs may disable this so manual FE edits are not overwritten.
    if strategy_overrides_applied:
        await _apply_strategy_overrides(request.strategy_api_url, ticker)
    # Apply AOS optimizations (time filter, long_only, params)
    aos_applied = await _apply_aos_optimizations(request.strategy_api_url, ticker)
    # Apply global trailing (best-effort, overrides per-ticker trailing)
    await _apply_global_trailing(request.strategy_api_url, request.trailing_stop_pct)

    # Load data
    data_file = request.data_file
    
    # Auto-discover data file(s) if not provided
    if not data_file:
        # Prefer centralized catalog (Data Manager + runner use the same inventory).
        databento_svc.scan_existing_files()
        data_files = databento_svc.get_files_for_range(
            ticker=ticker,
            start_date=range_start,
            end_date=range_end,
            schema_prefix="ohlcv-",
        )
        if not data_files:
            # Backward-compatible fallback only when centralized catalog has no
            # OHLCV entries for this ticker at all.
            catalog_rows = databento_svc.list_catalog(refresh=False, ticker=ticker)
            has_catalog_ohlcv = any(
                str(row.get("schema", "")).lower().startswith("ohlcv-")
                and row.get("status") == "ready"
                for row in catalog_rows
            )
            if not has_catalog_ohlcv:
                discovery = get_discovery()
                data_files = discovery.get_files_for_range(ticker, range_start, range_end)
    else:
        data_files = [data_file]

    if data_files:
        dfs = []
        skipped_files = []
        for file in data_files:
            try:
                if file.endswith('.parquet') or file.endswith('.parq'):
                    dfs.append(data_loader.load_parquet(file))
                else:
                    dfs.append(data_loader.load_csv(file))
            except FileNotFoundError as e:
                raise HTTPException(404, str(e))
            except Exception as e:
                logger.warning(f"Skipping invalid data file {file}: {e}")
                skipped_files.append(file)
                continue

        if not dfs:
            skipped_note = f" Skipped files: {', '.join(skipped_files)}" if skipped_files else ""
            raise HTTPException(400, f"No usable data files for the specified date/range.{skipped_note}")

        df = pd.concat(dfs, ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df = data_loader.filter_trading_range(df, range_start, range_end)
        if aos_applied.get("time_filter_enabled") and aos_applied.get("trading_hours"):
            df = data_loader.filter_trading_hours(df, aos_applied.get("trading_hours"))
    else:
        if not request.allow_mock_data:
            raise HTTPException(
                404,
                f"No data files found for {ticker} in range {range_start} to {range_end}. "
                "Backtest aborted to avoid mock-data contamination."
            )
        logger.warning(
            f"No data file found for {ticker} in range {range_start} to {range_end}, using mock data (allow_mock_data=True)"
        )
        df = data_loader.generate_mock_data(ticker=ticker, date=range_start)
    
    # Convert to list of bar dicts
    bars = list(data_loader.get_bars_iterator(df))
    
    if not bars:
        raise HTTPException(400, "No data available for the specified date/range")

    aos_l2_cfg = aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}

    def _pick_l2_float(request_value: Any, cfg_key: str) -> float:
        try:
            req = float(request_value)
        except (TypeError, ValueError):
            req = 0.0
        if abs(req) > 1e-12:
            return req
        try:
            return float(aos_l2_cfg.get(cfg_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    requested_l2_only = bool(request.l2_only or bool(aos_l2_cfg.get("l2_only", False)))
    requested_l2_confirm = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    l2_min_delta = _pick_l2_float(request.l2_min_delta, "min_delta")
    l2_min_imbalance = _pick_l2_float(request.l2_min_imbalance, "min_imbalance")
    l2_min_iceberg_bias = _pick_l2_float(request.l2_min_iceberg_bias, "min_iceberg_bias")
    l2_min_participation_ratio = _pick_l2_float(
        request.l2_min_participation_ratio, "min_participation_ratio"
    )
    l2_min_directional_consistency = _pick_l2_float(
        request.l2_min_directional_consistency, "min_directional_consistency"
    )
    l2_min_signed_aggression = _pick_l2_float(
        request.l2_min_signed_aggression, "min_signed_aggression"
    )
    requested_strategy_selection_mode = str(request.strategy_selection_mode or "").strip().lower()
    if requested_strategy_selection_mode not in {"adaptive_top_n", "all_enabled"}:
        requested_strategy_selection_mode = ""
    effective_strategy_selection_mode = (
        requested_strategy_selection_mode
        or str(aos_applied.get("strategy_selection_mode", "adaptive_top_n")).strip().lower()
        or "adaptive_top_n"
    )
    try:
        requested_max_active_strategies = (
            int(request.max_active_strategies) if request.max_active_strategies is not None else 0
        )
    except (TypeError, ValueError):
        requested_max_active_strategies = 0
    try:
        aos_max_active_strategies = int(aos_applied.get("max_active_strategies", 3))
    except (TypeError, ValueError):
        aos_max_active_strategies = 3
    effective_max_active_strategies = (
        requested_max_active_strategies or aos_max_active_strategies or 3
    )
    effective_max_active_strategies = max(1, min(20, effective_max_active_strategies))

    # Keep request value unless left at default and AOS provides an override.
    if int(request.l2_lookback_bars) != 3:
        l2_lookback_bars = max(1, int(request.l2_lookback_bars))
    else:
        try:
            l2_lookback_bars = max(1, int(aos_l2_cfg.get("lookback_bars", request.l2_lookback_bars)))
        except (TypeError, ValueError):
            l2_lookback_bars = max(1, int(request.l2_lookback_bars))

    # Optional L2 feature enrichment and filtering.
    l2_stats: Dict[str, Any] = {
        "requested_l2_only": requested_l2_only,
        "requested_l2_confirm_enabled": requested_l2_confirm,
        "aos_l2_config_applied": bool(aos_l2_cfg),
        "has_l2": False,
        "footprint_bars": 0,
        "icebergs": 0,
        "covered_minutes": 0,
        "bars_with_l2": 0,
        "bars_total": len(bars),
        "bars_after_filter": len(bars),
    }
    use_l2 = bool(requested_l2_only or requested_l2_confirm)
    l2_sessionized_by_market_day = bool(
        comparable_mode and (range_start != range_end or bool(request.date_from and request.date_to))
    )
    if use_l2:
        # Expand slightly to include last bar bucket in inclusive range.
        first_ts_utc = _to_utc_datetime(bars[0]["timestamp"])
        last_ts_utc = _to_utc_datetime(bars[-1]["timestamp"]) + timedelta(minutes=1)
        feature_map, build_stats = _build_l2_feature_map(
            ticker=ticker,
            start_dt_utc=first_ts_utc,
            end_dt_utc=last_ts_utc,
        )
        if l2_sessionized_by_market_day:
            build_stats.update(
                _normalize_l2_feature_map_for_market_day_sessions(
                    feature_map=feature_map,
                    bars=bars,
                )
            )
        l2_stats.update(build_stats)
        bars, attach_stats = _attach_l2_features(bars, feature_map, l2_only=requested_l2_only)
        l2_stats.update(attach_stats)
        # Guard against false positives where files exist but requested range has zero overlap.
        l2_stats["has_l2"] = bool(l2_stats.get("bars_with_l2", 0) > 0)

        if requested_l2_only and not bars:
            raise HTTPException(
                400,
                f"L2-only mode requested but no L2-aligned bars found for {ticker} "
                f"in range {range_start} to {range_end}.",
            )
        if requested_l2_confirm and not l2_stats.get("has_l2"):
            logger.warning(
                f"L2 confirmation requested for {ticker}, but no L2 data was found. "
                "Falling back to non-L2 confirmation for this run."
            )
    
    # Configure session defaults after strategy/AOS updates and after
    # we know whether L2 confirmation is actually feasible for this run.
    effective_l2_confirm = bool(requested_l2_confirm and l2_stats.get("has_l2"))
    effective_intrabar_execution_recalc_1s = (
        bool(request.intrabar_execution_recalc_1s)
        if request.intrabar_execution_recalc_1s is not None
        else bool(use_l2 and l2_stats.get("has_l2"))
    )
    await _configure_session(
        request.strategy_api_url,
        request.run_id,
        ticker,
        range_start,
        request.regime_detection_minutes,
        request.regime_refresh_bars,
        request.account_size_usd,
        risk_per_trade_pct=request.risk_per_trade_pct,
        max_position_notional_pct=request.max_position_notional_pct,
        max_fill_participation_rate=request.max_fill_participation_rate,
        min_fill_ratio=request.min_fill_ratio,
        enable_partial_take_profit=request.enable_partial_take_profit,
        partial_take_profit_rr=request.partial_take_profit_rr,
        partial_take_profit_fraction=request.partial_take_profit_fraction,
        time_exit_bars=request.time_exit_bars,
        adverse_flow_exit_enabled=request.adverse_flow_exit_enabled,
        adverse_flow_threshold=request.adverse_flow_threshold,
        adverse_flow_min_hold_bars=request.adverse_flow_min_hold_bars,
        stop_loss_mode=request.stop_loss_mode,
        fixed_stop_loss_pct=request.fixed_stop_loss_pct,
        l2_confirm_enabled=effective_l2_confirm,
        l2_min_delta=l2_min_delta,
        l2_min_imbalance=l2_min_imbalance,
        l2_min_iceberg_bias=l2_min_iceberg_bias,
        l2_lookback_bars=l2_lookback_bars,
        l2_min_participation_ratio=l2_min_participation_ratio,
        l2_min_directional_consistency=l2_min_directional_consistency,
        l2_min_signed_aggression=l2_min_signed_aggression,
        cold_start_each_day=effective_cold_start_each_day,
        strategy_selection_mode=effective_strategy_selection_mode,
        max_active_strategies=effective_max_active_strategies,
    )

    if not bars:
        raise HTTPException(400, "No data available for the specified date/range")

    # Load QQQ reference bars for cross-asset context (best-effort)
    ref_bars_map = {}
    if ticker.upper() != 'QQQ':
        try:
            databento_svc.scan_existing_files()
            qqq_files = databento_svc.get_files_for_range(
                ticker='QQQ', start_date=range_start, end_date=range_end,
                schema_prefix="ohlcv-",
            )
            if not qqq_files:
                discovery = get_discovery()
                qqq_files = discovery.get_files_for_range('QQQ', range_start, range_end)
            if qqq_files:
                qqq_dfs = []
                for f in qqq_files:
                    try:
                        if f.endswith('.parquet') or f.endswith('.parq'):
                            qqq_dfs.append(data_loader.load_parquet(f))
                        else:
                            qqq_dfs.append(data_loader.load_csv(f))
                    except Exception:
                        continue
                if qqq_dfs:
                    qqq_df = pd.concat(qqq_dfs, ignore_index=True)
                    qqq_df = data_loader.filter_trading_range(qqq_df, range_start, range_end)
                    for qqq_bar in data_loader.get_bars_iterator(qqq_df):
                        ts = qqq_bar.get('timestamp')
                        ts_key = (ts.isoformat() if hasattr(ts, 'isoformat')
                                  else str(ts))
                        qqq_bar['ticker'] = 'QQQ'
                        ref_bars_map[ts_key] = qqq_bar
                    logger.info(f"Loaded {len(ref_bars_map)} QQQ reference bars for cross-asset")
        except Exception as e:
            logger.debug(f"Could not load QQQ reference data: {e}")

    # Create runner
    config = RunConfig(
        run_id=request.run_id,
        ticker=ticker,
        date=run_date_label,
        date_from=range_start,
        date_to=range_end,
        strategy_api_url=request.strategy_api_url,
        account_size_usd=request.account_size_usd,
        regime_detection_minutes=request.regime_detection_minutes,
        intrabar_execution_recalc_1s=effective_intrabar_execution_recalc_1s,
    )

    runner = SessionRunner(config)
    runner.ref_bars_map = ref_bars_map
    if effective_intrabar_execution_recalc_1s:
        runner.l2_manager = l2_manager
    runner.load_bars(bars)
    
    # Register callbacks for broadcasting
    async def on_bar(bar):
        await broadcast({
            "type": "bar",
            "run_id": request.run_id,
            "ticker": ticker,
            "bar": bar
        })
    
    async def on_decision(marker):
        await broadcast({
            "type": "decision",
            "run_id": request.run_id,
            "ticker": ticker,
            "marker": marker
        })
    
    runner.on_bar(on_bar)
    runner.on_decision(on_decision)
    
    # Store checkpoint auto-save metadata on runner for use after run_all
    runner._checkpoint_auto_save = bool(request.auto_save_checkpoint and not comparable_mode)
    runner._checkpoint_strategy_url = request.strategy_api_url
    runner._checkpoint_loaded = checkpoint_loaded

    active_runners[run_key] = runner

    logger.info(f"Started run {run_key} with {len(bars)} bars")

    return {
        "success": True,
        "run_key": run_key,
        "ticker": ticker,
        "total_bars": len(bars),
        "strategy_state_reset": orchestrator_reset,
        "checkpoint_loaded": checkpoint_loaded,
        "strategy_overrides_applied": strategy_overrides_applied,
        "data_files": data_files,
        "aos_applied": aos_applied,
        "l2_applied": {
            **l2_stats,
            "effective_l2_confirm_enabled": effective_l2_confirm,
            "l2_min_delta": l2_min_delta,
            "l2_min_imbalance": l2_min_imbalance,
            "l2_min_iceberg_bias": l2_min_iceberg_bias,
            "l2_lookback_bars": l2_lookback_bars,
            "l2_min_participation_ratio": l2_min_participation_ratio,
            "l2_min_directional_consistency": l2_min_directional_consistency,
            "l2_min_signed_aggression": l2_min_signed_aggression,
            "sessionized_by_market_day": l2_sessionized_by_market_day,
        },
        "execution_config": {
            "account_size_usd": request.account_size_usd,
            "risk_per_trade_pct": request.risk_per_trade_pct,
            "max_position_notional_pct": request.max_position_notional_pct,
            "max_fill_participation_rate": request.max_fill_participation_rate,
            "min_fill_ratio": request.min_fill_ratio,
            "enable_partial_take_profit": request.enable_partial_take_profit,
            "partial_take_profit_rr": request.partial_take_profit_rr,
            "partial_take_profit_fraction": request.partial_take_profit_fraction,
            "time_exit_bars": request.time_exit_bars,
            "adverse_flow_exit_enabled": request.adverse_flow_exit_enabled,
            "adverse_flow_threshold": request.adverse_flow_threshold,
            "adverse_flow_min_hold_bars": request.adverse_flow_min_hold_bars,
            "stop_loss_mode": request.stop_loss_mode,
            "fixed_stop_loss_pct": request.fixed_stop_loss_pct,
            "intrabar_execution_recalc_1s": effective_intrabar_execution_recalc_1s,
            "cold_start_each_day": effective_cold_start_each_day,
            "comparable_mode": comparable_mode,
            "strategy_selection_mode": effective_strategy_selection_mode,
            "max_active_strategies": effective_max_active_strategies,
        },
        "first_bar": bars[0] if bars else None,
        "last_bar": bars[-1] if bars else None
    }


@app.get("/api/run/{run_id}/{ticker}/{date}/state")
async def get_run_state(run_id: str, ticker: str, date: str):
    """Get current state of a run."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    return runner.get_state()


@app.post("/api/run/{run_id}/{ticker}/{date}/step")
async def step_run(run_id: str, ticker: str, date: str):
    """Advance the run by one bar."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    result = await runner.step()
    
    return result


@app.post("/api/run/{run_id}/{ticker}/{date}/play")
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
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]

    # If we were paused, just resume.
    if runner.is_running and runner.is_paused:
        runner.resume()
        return {"success": True, "resumed": True, "speed_ms": runner.last_run_speed if hasattr(runner, "last_run_speed") else "unknown"}
    
    if runner.is_running:
        return {"success": False, "error": "Run already in progress"}

    # Ingest speed from body, query string, or default to max.
    raw_speed = None
    if request and request.speed_ms is not None:
        raw_speed = request.speed_ms
    elif speed_ms is not None:
        raw_speed = speed_ms
    else:
        # Best-effort fallback for odd clients sending raw JSON without schema
        try:
            if raw_request:
                payload = await raw_request.json()
                raw_speed = payload.get("speed_ms") if isinstance(payload, dict) else None
        except Exception:
            raw_speed = None
    if raw_speed is None:
        raw_speed = "max"

    # Normalize common aliases so downstream handling is consistent
    if isinstance(raw_speed, str):
        normalized = raw_speed.strip().lower()
        if normalized in {"instant", "max", "fast"}:
            raw_speed = "max"
        elif normalized.endswith("hz") and normalized[:-2].isdigit():
            raw_speed = f"{int(normalized[:-2])}hz"
        elif normalized in {"", "null", "none"}:
            raw_speed = "max"
    
    # Start in background with optional checkpoint auto-save on completion
    runner.last_run_speed = raw_speed  # cache for resume info

    async def _run_and_maybe_save():
        await runner.run_all(speed_ms=raw_speed)
        
        # Save reports
        try:
            reports_dir = Path(__file__).parent / "reports"
            run_date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_run_id = str(runner.config.run_id).replace(":", "_")
            out_dir = reports_dir / f"{run_date_str}_{runner.config.ticker}_{safe_run_id}"
            runner.save_reports(str(out_dir))
        except Exception as e:
            logger.error(f"Failed to auto-save reports: {e}")

        if getattr(runner, '_checkpoint_auto_save', False):
            url = getattr(runner, '_checkpoint_strategy_url', '')
            if url:
                await _save_remote_checkpoint(
                    url,
                    run_id=runner.config.run_id,
                    ticker=runner.config.ticker,
                    date_from=runner.config.date_from or runner.config.date,
                    date_to=runner.config.date_to or runner.config.date,
                )

    asyncio.create_task(_run_and_maybe_save())

    return {"success": True, "speed_ms": raw_speed}


@app.post("/api/run/{run_id}/{ticker}/{date}/pause")
async def pause_run(run_id: str, ticker: str, date: str):
    """Pause a running backtest."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    runner.pause()
    
    return {"success": True, "is_paused": True}


@app.post("/api/run/{run_id}/{ticker}/{date}/resume")
async def resume_run(run_id: str, ticker: str, date: str):
    """Resume a paused backtest."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    runner.resume()
    
    return {"success": True, "is_paused": False}


@app.post("/api/run/{run_id}/{ticker}/{date}/stop")
async def stop_run(run_id: str, ticker: str, date: str):
    """Stop a running backtest."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    runner.stop()
    
    return {"success": True, "stopped": True}


@app.get("/api/run/{run_id}/{ticker}/{date}/bars")
async def get_processed_bars(run_id: str, ticker: str, date: str):
    """Get all processed bars so far."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    return {
        "bars": runner.get_processed_bars(),
        "current_index": runner.current_bar_index,
        "total_bars": len(runner.bars)
    }


@app.get("/api/run/{run_id}/{ticker}/{date}/bar-details/{minute_key}")
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
    from datetime import timezone
    from src.l2_data_manager import L2DataManager
    from src.intrabar_frame_builder import IntrabarFrameBuilder
    
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    # Convert minute_key to datetime
    minute_start = datetime.fromtimestamp(minute_key, tz=timezone.utc)
    minute_end = minute_start.replace(second=59, microsecond=999999)
    
    # Get L2 data manager (reuse if possible)
    manager = L2DataManager()
    builder = IntrabarFrameBuilder(manager=manager)
    
    try:
        frames = builder.build_frames(ticker, minute_start, minute_end)
        
        if frames.empty:
            return {
                "minute_key": minute_key,
                "ticker": ticker,
                "frames": [],
                "stats": {"has_data": False, "seconds": 0}
            }
        
        # Convert to list of dicts for JSON serialization
        # Convert timestamps to ISO strings
        frames["ts_sec"] = frames["ts_sec"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        records = frames.to_dict(orient="records")
        
        return {
            "minute_key": minute_key,
            "ticker": ticker,
            "frames": records,
            "stats": {
                "has_data": True,
                "seconds": len(records),
                "coverage_ratio": float(frames["coverage_ratio"].iloc[0]) if "coverage_ratio" in frames.columns else 0.0,
                "total_trade_ticks": int(frames["trade_ticks_sec"].sum()) if "trade_ticks_sec" in frames.columns else 0,
                "total_book_updates": int(frames["book_updates_sec"].sum()) if "book_updates_sec" in frames.columns else 0,
            }
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to load bar details: {str(e)}")

@app.get("/api/run/{run_id}/{ticker}/{date}/markers")
async def get_markers(run_id: str, ticker: str, date: str, marker_type: Optional[str] = None):
    """Get all decision markers."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    
    if marker_type:
        try:
            mt = MarkerType(marker_type)
            return runner.tracker.get_markers(mt)
        except ValueError:
            raise HTTPException(400, f"Invalid marker type: {marker_type}")
    
    return runner.get_markers()


@app.get("/api/run/{run_id}/{ticker}/{date}/chart-annotations")
async def get_chart_annotations(run_id: str, ticker: str, date: str):
    """Get markers formatted for chart display."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    return runner.get_chart_annotations()


@app.get("/api/run/{run_id}/{ticker}/{date}/summary")
async def get_run_summary(run_id: str, ticker: str, date: str):
    """Get session summary."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    return runner.get_summary()


@app.delete("/api/run/{run_id}/{ticker}/{date}")
async def delete_run(run_id: str, ticker: str, date: str):
    """Delete a run from memory."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    runner.stop()
    await _clear_remote_strategy_sessions(
        runner.config.strategy_api_url,
        runner.config.run_id,
        runner.config.ticker,
    )
    del active_runners[run_key]
    
    return {"success": True, "deleted": run_key}


@app.get("/api/runs")
async def list_runs():
    """List all active runs."""
    runs = []
    for key, runner in active_runners.items():
        runs.append(runner.get_state())
    return runs


@app.get("/api/l2/footprint/{ticker}")
async def get_footprint_data(ticker: str, start_time: str, end_time: str, timeframe: str = "1min"):
    """Get L2 Footprint data for a specific time range."""
    # Parse times
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "Invalid timestamp format. Use ISO 8601.")
        
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")
    
    # Ensure data is loaded
    # Simple logic: try loading data for the dates involved. 
    # TODO: Optimize to avoid reloading if already in memory
    l2_manager.load_data(ticker, start_date, end_date) 
    
    # Get aggregated bars
    bars = l2_manager.get_footprint_bars(ticker, start_dt, end_dt, timeframe)
    
    return {"ticker": ticker, "timeframe": timeframe, "bars": bars}


@app.get("/api/l2/icebergs/{ticker}")
async def get_icebergs(ticker: str, start_time: str, end_time: str):
    """Get detected iceberg orders for a specific time range."""
    # Parse times
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "Invalid timestamp format. Use ISO 8601.")
        
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")
    
    # Ensure data is loaded
    l2_manager.load_data(ticker, start_date, end_date)
    
    # Run detection
    icebergs = l2_manager.detect_icebergs(ticker, start_dt, end_dt)
    
    return icebergs


# ============ Data Loader Endpoints ============

class DownloadRequest(BaseModel):
    ticker: str
    data_schema: str = "mbp-10"
    start_date: str
    end_date: str
    dataset: str = "XNAS.ITCH"
    convert_to_parquet: bool = True


class CostEstimateRequest(BaseModel):
    ticker: str
    data_schema: str = "mbp-10"
    start_date: str
    end_date: str
    dataset: str = "XNAS.ITCH"


class DeleteDataRequest(BaseModel):
    ticker: str
    data_schema: str
    start_date: str
    end_date: str


class DataSettingsRequest(BaseModel):
    ohlcv_data_dirs: Optional[List[str]] = None
    l2_data_dirs: Optional[List[str]] = None


class DatabentoApiKeyRequest(BaseModel):
    api_key: str


@app.get("/api/data-loader/catalog")
async def get_data_catalog(
    refresh: bool = False,
    ticker: Optional[str] = None,
    schema: Optional[str] = None,
    file_format: Optional[str] = None,
    source: Optional[str] = None,
    managed: Optional[bool] = None,
):
    """List unified data catalog entries with optional filters."""
    return databento_svc.list_catalog(
        refresh=refresh,
        ticker=ticker,
        schema=schema,
        file_format=file_format,
        source=source,
        managed=managed,
    )


@app.get("/api/data-loader/catalog/{ticker}")
async def get_ticker_catalog(ticker: str):
    """List catalog data for a specific ticker."""
    return databento_svc.list_catalog(ticker=ticker.upper())


@app.get("/api/data-loader/settings")
async def get_data_loader_settings():
    """Read centralized data manager settings."""
    return databento_svc.get_settings()


@app.put("/api/data-loader/settings")
async def update_data_loader_settings(request: DataSettingsRequest):
    """Update OHLCV/L2 data roots used by catalog discovery."""
    global data_loader, l2_manager
    try:
        settings = databento_svc.update_data_dirs(
            ohlcv_data_dirs=request.ohlcv_data_dirs,
            l2_data_dirs=request.l2_data_dirs,
        )
        # Recreate loaders so run execution + L2 charts use the same updated roots.
        data_loader = DataLoader()
        l2_manager = L2DataManager()
        l2_features.manager = l2_manager
        reset_discovery()
        return settings
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@app.put("/api/data-loader/api-key")
async def set_databento_api_key(request: DatabentoApiKeyRequest):
    """Set Databento API key for this system (persisted in settings)."""
    try:
        settings = databento_svc.set_api_key(request.api_key)
        return {"status": "ok", **settings}
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@app.get("/api/data-loader/schemas")
async def get_supported_schemas():
    """List supported Databento schemas."""
    return databento_svc.get_schemas()


@app.post("/api/data-loader/cost-estimate")
async def get_cost_estimate(request: CostEstimateRequest):
    """Get Databento cost estimate before downloading."""
    try:
        return databento_svc.get_cost_estimate(
            ticker=request.ticker.upper(),
            schema=request.data_schema,
            start=request.start_date,
            end=request.end_date,
            dataset=request.dataset,
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(400, f"Cost estimate failed: {e}")


@app.post("/api/data-loader/download")
async def start_download(request: DownloadRequest):
    """Start a data download from Databento (runs in background)."""
    ticker = request.ticker.upper()

    try:
        coverage = databento_svc.get_range_coverage(
            ticker=ticker,
            schema=request.data_schema,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Invalid date range: {e}")

    if coverage.get("fully_covered"):
        return {"status": "already_exists", "coverage": coverage}

    async def _broadcast(msg):
        await broadcast(msg)

    # Run download in background task
    async def _do_download():
        try:
            entry = await databento_svc.download(
                ticker=ticker,
                schema=request.data_schema,
                start_date=request.start_date,
                end_date=request.end_date,
                dataset=request.dataset,
                convert_to_parquet=request.convert_to_parquet,
                broadcast_fn=_broadcast,
            )
            logger.info(f"Download complete: {ticker} {request.data_schema} -> {entry.status}")
        except Exception as e:
            logger.error(f"Download failed: {e}")

    asyncio.create_task(_do_download())
    return {
        "status": "started",
        "ticker": ticker,
        "schema": request.data_schema,
        "days_total": coverage.get("total_days", 0),
        "days_to_download": len(coverage.get("missing_days", [])),
        "days_already_covered": len(coverage.get("covered_days", [])),
    }


@app.get("/api/data-loader/downloads/active")
async def get_active_downloads():
    """Get list of currently downloading jobs."""
    return databento_svc.get_active_downloads()


@app.delete("/api/data-loader/entry")
async def delete_data_entry(request: DeleteDataRequest):
    """Delete a downloaded data entry and its files."""
    existing = databento_svc.catalog.find(
        request.ticker.upper(), request.data_schema, request.start_date, request.end_date
    )
    if not existing:
        raise HTTPException(404, "Entry not found")
    if not bool(existing.get("managed", True)):
        raise HTTPException(
            403,
            "Refusing to delete unmanaged/external entry. Remove file manually if needed.",
        )
    success = databento_svc.delete_entry(
        request.ticker.upper(), request.data_schema, request.start_date, request.end_date
    )
    if not success:
        raise HTTPException(500, "Delete failed")
    return {"status": "deleted"}


@app.post("/api/data-loader/scan")
async def scan_existing_data():
    """Scan data directories and register untracked files."""
    from dataclasses import asdict
    entries = databento_svc.scan_existing_files()
    return {"scanned": len(entries), "entries": [asdict(e) for e in entries]}


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
