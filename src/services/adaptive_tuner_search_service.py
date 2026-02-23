from __future__ import annotations

import copy
import random
from datetime import datetime
from itertools import product
from typing import Any, Dict, List
from uuid import uuid4

from src.services.adaptive_tuner_core_service import (
    normalize_bool_options,
    normalize_clamped_int,
    normalize_int_options,
    normalize_mode_options,
    normalize_non_negative_int,
    normalize_strategy_selection_mode,
)


def candidate_key(candidate: Dict[str, Any]) -> tuple:
    return (
        normalize_strategy_selection_mode(candidate.get("strategy_selection_mode")),
        normalize_clamped_int(candidate.get("max_active_strategies"), 3, 1, 20),
        normalize_non_negative_int(
            candidate.get("min_active_bars_before_switch"), 0, 500
        ),
        normalize_non_negative_int(candidate.get("switch_cooldown_bars"), 0, 500),
        bool(candidate.get("flow_bias_enabled", True)),
        bool(candidate.get("use_ohlcv_fallbacks", True)),
    )


def build_adaptive_tuner_search_space(request: Any) -> Dict[str, List[Any]]:
    return {
        "strategy_selection_mode": normalize_mode_options(request.selection_modes),
        "max_active_strategies": normalize_int_options(
            request.max_active_options,
            default=[1, 2, 3, 4, 5],
            min_value=1,
            max_value=20,
        ),
        "min_active_bars_before_switch": normalize_int_options(
            request.min_active_bars_options,
            default=[0, 2, 4, 8, 12],
            min_value=0,
            max_value=500,
        ),
        "switch_cooldown_bars": normalize_int_options(
            request.switch_cooldown_bars_options,
            default=[0, 1, 2, 4, 8],
            min_value=0,
            max_value=500,
        ),
        "flow_bias_enabled": normalize_bool_options(
            request.flow_bias_options, default=[True, False]
        ),
        "use_ohlcv_fallbacks": normalize_bool_options(
            request.ohlcv_fallback_options, default=[True, False]
        ),
    }


def build_grid_candidates(
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


def build_random_candidates(
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
            "strategy_selection_mode": rng.choice(
                search_space["strategy_selection_mode"]
            ),
            "max_active_strategies": rng.choice(search_space["max_active_strategies"]),
            "min_active_bars_before_switch": rng.choice(
                search_space["min_active_bars_before_switch"]
            ),
            "switch_cooldown_bars": rng.choice(search_space["switch_cooldown_bars"]),
            "flow_bias_enabled": rng.choice(search_space["flow_bias_enabled"]),
            "use_ohlcv_fallbacks": rng.choice(search_space["use_ohlcv_fallbacks"]),
        }
        key = candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


def build_adaptive_candidate_config(
    ticker_config: Dict[str, Any],
    candidate: Dict[str, Any],
    adaptive_version: int,
) -> Dict[str, Any]:
    cfg = copy.deepcopy(ticker_config)
    cfg["strategy_selection_mode"] = normalize_strategy_selection_mode(
        candidate.get("strategy_selection_mode")
    )
    cfg["max_active_strategies"] = normalize_clamped_int(
        candidate.get("max_active_strategies"), default=3, min_value=1, max_value=20
    )

    adaptive_cfg = cfg.get("adaptive", {})
    if not isinstance(adaptive_cfg, dict):
        adaptive_cfg = {}
    adaptive_cfg["version"] = int(adaptive_version)
    adaptive_cfg["flow_bias_enabled"] = bool(candidate.get("flow_bias_enabled", True))
    adaptive_cfg["use_ohlcv_fallbacks"] = bool(
        candidate.get("use_ohlcv_fallbacks", True)
    )
    adaptive_cfg["min_active_bars_before_switch"] = normalize_non_negative_int(
        candidate.get("min_active_bars_before_switch"), default=0, max_value=500
    )
    adaptive_cfg["switch_cooldown_bars"] = normalize_non_negative_int(
        candidate.get("switch_cooldown_bars"), default=0, max_value=500
    )
    cfg["adaptive"] = adaptive_cfg
    return cfg


def compute_tuner_score(
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


def compute_tuner_score_robust(
    day_results: List[Dict[str, Any]],
) -> float:
    """Robust scoring that penalizes overfit by requiring consistency across days."""
    valid = [d for d in day_results if d.get("success")]
    if not valid:
        return -1_000_000.0

    n_days = len(valid)
    daily_pnl = [float(d.get("pnl_pct", 0.0)) for d in valid]
    daily_trades = [int(d.get("trades", 0)) for d in valid]

    total_trades = sum(daily_trades)
    if total_trades <= 0:
        return -1.0

    avg_pnl = sum(daily_pnl) / n_days

    mean_abs = max(abs(avg_pnl), 0.001)
    variance = sum((p - avg_pnl) ** 2 for p in daily_pnl) / n_days
    std_dev = variance**0.5
    cv = std_dev / mean_abs
    consistency = 1.0 / (1.0 + cv)

    daily_expectancy = []
    for d in valid:
        pnl = float(d.get("pnl_pct", 0.0))
        trades = max(int(d.get("trades", 0)), 1)
        daily_expectancy.append(pnl / trades)

    avg_expectancy = (
        sum(daily_expectancy) / len(daily_expectancy) if daily_expectancy else 0.0
    )
    if avg_expectancy < -0.05:
        quality_gate = 0.3
    elif avg_expectancy < 0.0:
        quality_gate = 0.6
    elif avg_expectancy < 0.02:
        quality_gate = 0.85
    else:
        quality_gate = 1.0

    positive_days = sum(1 for p in daily_pnl if p > 0)
    positive_ratio = positive_days / n_days
    day_penalty = 0.5 if positive_ratio < 0.50 else 1.0

    avg_trades_per_day = total_trades / n_days
    if avg_trades_per_day > 3.0:
        trade_norm = 1.0 - min(0.3, (avg_trades_per_day - 3.0) * 0.05)
    else:
        trade_norm = 1.0

    if avg_trades_per_day < 0.5:
        trade_scarcity = 0.25
    elif avg_trades_per_day < 1.0:
        trade_scarcity = 0.65
    else:
        trade_scarcity = 1.0

    l2_confirmed_days = sum(1 for d in valid if float(d.get("l2_avg_score", 0.0)) > 0.3)
    l2_ratio = l2_confirmed_days / n_days if n_days > 0 else 0.0
    l2_bonus = 1.0 + (l2_ratio * 0.10)

    score = (
        avg_pnl * consistency * quality_gate * day_penalty * trade_norm * trade_scarcity
    )
    score *= l2_bonus
    return round(score, 6)


def build_tuner_profile_entry(
    *,
    ticker: str,
    request: Any,
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
        "quick_max_days": normalize_clamped_int(
            request.quick_max_days, default=2, min_value=1, max_value=30
        ),
        "quick_trial_boost": normalize_clamped_int(
            request.quick_trial_boost, default=3, min_value=1, max_value=10
        ),
        "candidate": dict(best_candidate) if isinstance(best_candidate, dict) else {},
        "metrics": dict(metrics) if isinstance(metrics, dict) else {},
    }
