#!/usr/bin/env python3
"""
Scalp L2 research runner (MU).

Purpose:
- Run a small, repeatable parameter audit for scalp_l2_intrabar.
- Keep runs short and deterministic (single-day windows for heavy intrabar modes).
- Capture fee-aware outcomes from backtest-runner summary payloads.

Output:
- reports/scalp_l2_research_report.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


RUNNER_API = "http://127.0.0.1:8002"
STRATEGY_API = "http://127.0.0.1:8001"
TICKER = "MU"
SCALP_STRATEGY = "scalp_l2_intrabar"
SCALP_COMBO_PROFILE = "mu_scalp_intrabar_fee_v1"
REPORT_PATH = Path("reports/scalp_l2_research_report.json")


def _api_get(url: str, timeout: float = 120.0) -> Any:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _api_post(url: str, payload: Dict[str, Any], timeout: float = 120.0) -> Any:
    resp = requests.post(url, json=payload, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"POST {url} failed [{resp.status_code}]: {resp.text[:600]}")
    return resp.json()


def _api_delete(url: str, timeout: float = 120.0) -> Any:
    resp = requests.delete(url, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"DELETE {url} failed [{resp.status_code}]: {resp.text[:600]}")
    return resp.json()


def _parse_run_key(run_key: str) -> Tuple[str, str, str]:
    parts = str(run_key).split(":")
    if len(parts) < 3:
        raise ValueError(f"Invalid run_key: {run_key}")
    date = parts[-1]
    ticker = parts[-2]
    run_id = ":".join(parts[:-2])
    return run_id, ticker, date


def _fetch_strategies() -> Dict[str, Dict[str, Any]]:
    data = _api_get(f"{STRATEGY_API}/api/strategies")
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected /api/strategies response type")
    return data


def _apply_combo_profile(profile_id: str) -> Dict[str, Any]:
    payload = {
        "ticker": TICKER,
        "profile_id": profile_id,
        "strategy_api_url": STRATEGY_API,
        "apply_now": True,
    }
    return _api_post(f"{RUNNER_API}/api/strategy-combos/apply", payload, timeout=180.0)


def _update_strategy_params(strategy_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"strategy_name": strategy_name, "params": params}
    return _api_post(f"{STRATEGY_API}/api/strategies/update", payload, timeout=120.0)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_optional_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _entry_volume_ratio(markers: List[Dict[str, Any]], bars: List[Dict[str, Any]]) -> Optional[float]:
    if not markers or not bars:
        return None
    volumes = []
    for bar in bars:
        v = _safe_float(bar.get("volume"), 0.0)
        if v > 0:
            volumes.append(v)
    if not volumes:
        return None
    median_volume = statistics.median(volumes)
    if median_volume <= 0:
        return None

    volume_by_idx: Dict[int, float] = {}
    for idx, bar in enumerate(bars):
        volume_by_idx[idx] = _safe_float(bar.get("volume"), 0.0)

    entry_volumes = []
    for marker in markers:
        if str(marker.get("marker_type", "")).strip().lower() != "entry_executed":
            continue
        bar_index = marker.get("bar_index")
        if not isinstance(bar_index, int):
            continue
        v = volume_by_idx.get(bar_index, 0.0)
        if v > 0:
            entry_volumes.append(v)

    if not entry_volumes:
        return None
    return statistics.mean(entry_volumes) / median_volume


def _entry_l2_stats(markers: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """
    Aggregate L2/intrabar quality for executed entries.

    Turn-candidate heuristic (video-inspired):
    - clear directional margin + push,
    - decent participation,
    - controlled spread,
    - non-positive recent flow trend (deceleration / transition).
    """
    entries = [
        marker
        for marker in (markers or [])
        if str(marker.get("marker_type", "")).strip().lower() == "entry_executed"
    ]
    if not entries:
        return {
            "entry_avg_flow_score": None,
            "entry_avg_abs_signed_aggression": None,
            "entry_avg_abs_direction_margin": None,
            "entry_avg_participation_ratio": None,
            "entry_avg_spread_bps": None,
            "entry_avg_abs_push_ratio": None,
            "entry_window_5s_share": None,
            "entry_turn_candidate_share": None,
        }

    flow_scores: List[float] = []
    abs_signed: List[float] = []
    abs_margin: List[float] = []
    participation: List[float] = []
    spreads: List[float] = []
    abs_push: List[float] = []
    window_5s_hits = 0
    turn_candidates = 0

    for marker in entries:
        details = marker.get("details") if isinstance(marker.get("details"), dict) else {}
        metadata = details.get("metadata") if isinstance(details.get("metadata"), dict) else {}
        order_flow = metadata.get("order_flow") if isinstance(metadata.get("order_flow"), dict) else {}
        intrabar = metadata.get("intrabar_1s") if isinstance(metadata.get("intrabar_1s"), dict) else {}

        flow_score = _safe_optional_float(order_flow.get("flow_score"))
        signed_aggr = _safe_optional_float(order_flow.get("signed_aggression"))
        direction_margin = _safe_optional_float(order_flow.get("direction_margin"))
        flow_trend = _safe_optional_float(order_flow.get("flow_score_trend_3bar"))
        part = _safe_optional_float(order_flow.get("participation_ratio"))

        spread_bps = _safe_optional_float(intrabar.get("spread_bps_avg"))
        push_ratio = _safe_optional_float(intrabar.get("push_ratio"))
        w_long_push = _safe_optional_float(intrabar.get("window_long_push_ratio"))
        w_short_push = _safe_optional_float(intrabar.get("window_short_push_ratio"))
        trigger_source = str(intrabar.get("trigger_source") or "").strip().lower()
        if trigger_source == "window_5s":
            window_5s_hits += 1

        if flow_score is not None:
            flow_scores.append(flow_score)
        if signed_aggr is not None:
            abs_signed.append(abs(signed_aggr))
        if direction_margin is not None:
            abs_margin.append(abs(direction_margin))
        if part is not None:
            participation.append(part)
        if spread_bps is not None:
            spreads.append(spread_bps)

        push_vals = [val for val in [push_ratio, w_long_push, w_short_push] if val is not None]
        entry_abs_push = max((abs(val) for val in push_vals), default=0.0)
        abs_push.append(entry_abs_push)

        # Reversal/turn join heuristic.
        if (
            (direction_margin is not None and abs(direction_margin) >= 0.18)
            and entry_abs_push >= 0.45
            and (part is not None and part >= 0.06)
            and (spread_bps is not None and spread_bps <= 8.0)
            and (flow_trend is not None and flow_trend <= 0.5)
        ):
            turn_candidates += 1

    entry_count = len(entries)

    def _avg(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return float(sum(values) / len(values))

    return {
        "entry_avg_flow_score": _avg(flow_scores),
        "entry_avg_abs_signed_aggression": _avg(abs_signed),
        "entry_avg_abs_direction_margin": _avg(abs_margin),
        "entry_avg_participation_ratio": _avg(participation),
        "entry_avg_spread_bps": _avg(spreads),
        "entry_avg_abs_push_ratio": _avg(abs_push),
        "entry_window_5s_share": (window_5s_hits / entry_count) if entry_count > 0 else None,
        "entry_turn_candidate_share": (turn_candidates / entry_count) if entry_count > 0 else None,
    }


@dataclass
class Variant:
    name: str
    description: str
    run_overrides: Dict[str, Any] = field(default_factory=dict)
    strategy_overrides: Dict[str, Any] = field(default_factory=dict)


VARIANTS: List[Variant] = [
    Variant(
        name="baseline",
        description="Current scalp fee-aware baseline from combo profile.",
        run_overrides={
            "l2_min_imbalance": 0.02,
            "l2_min_directional_consistency": 0.25,
            "l2_min_signed_aggression": 0.02,
            "l2_lookback_bars": 3,
            "include_extended_hours": False,
        },
        strategy_overrides={},
    ),
    Variant(
        name="baseline_quick_be",
        description="Baseline entries with faster break-even/partials for scratch-style risk control.",
        run_overrides={
            "l2_min_imbalance": 0.02,
            "l2_min_directional_consistency": 0.25,
            "l2_min_signed_aggression": 0.02,
            "l2_lookback_bars": 3,
            "include_extended_hours": False,
            "partial_take_profit_rr": 0.75,
            "partial_take_profit_fraction": 0.50,
            "trailing_activation_pct": 0.12,
            "break_even_buffer_pct": 0.0,
            "break_even_min_hold_bars": 1,
            "time_exit_bars": 22,
            "adverse_flow_threshold": 0.11,
            "adverse_flow_min_hold_bars": 2,
        },
        strategy_overrides={},
    ),
    Variant(
        name="volume_guard_strict",
        description="Require stronger participation + intrabar coverage (filters thin/noisy flow).",
        run_overrides={
            "l2_min_imbalance": 0.02,
            "l2_min_directional_consistency": 0.25,
            "l2_min_signed_aggression": 0.02,
            "l2_lookback_bars": 3,
            "include_extended_hours": False,
        },
        strategy_overrides={
            "min_participation_ratio": 0.07,
            "min_intrabar_coverage_points": 6,
            "min_intrabar_window_move_pct": 0.02,
            "min_intrabar_window_push_ratio": 0.10,
        },
    ),
    Variant(
        name="spread_cost_strict",
        description="Tighter spread/cost filter to avoid fragile low-edge trades.",
        run_overrides={
            "l2_min_imbalance": 0.02,
            "l2_min_directional_consistency": 0.25,
            "l2_min_signed_aggression": 0.02,
            "l2_lookback_bars": 3,
            "include_extended_hours": False,
        },
        strategy_overrides={
            "max_intrabar_spread_bps": 6.0,
            "min_round_trip_cost_bps": 7.5,
            "min_reward_to_cost_ratio": 2.0,
            "spread_flow_score_penalty_per_bps": 0.55,
        },
    ),
    Variant(
        name="flow_signal_strict",
        description="Higher flow quality threshold (fewer, cleaner entries).",
        run_overrides={
            "l2_min_imbalance": 0.03,
            "l2_min_directional_consistency": 0.30,
            "l2_min_signed_aggression": 0.03,
            "l2_lookback_bars": 4,
            "include_extended_hours": False,
        },
        strategy_overrides={
            "min_flow_score": 52.0,
            "min_signed_aggression": 0.055,
            "min_directional_consistency": 0.62,
            "min_flow_signal_margin": 0.015,
        },
    ),
    Variant(
        name="flow_signal_loose",
        description="Looser flow thresholds (more activity, higher noise risk).",
        run_overrides={
            "l2_min_imbalance": 0.015,
            "l2_min_directional_consistency": 0.18,
            "l2_min_signed_aggression": 0.015,
            "l2_lookback_bars": 2,
            "include_extended_hours": False,
        },
        strategy_overrides={
            "min_flow_score": 44.0,
            "min_signed_aggression": 0.035,
            "min_directional_consistency": 0.50,
            "min_flow_signal_margin": 0.005,
            "min_intrabar_window_move_pct": 0.01,
        },
    ),
    Variant(
        name="flow_signal_balanced",
        description="Balanced flow thresholds between baseline and loose variant.",
        run_overrides={
            "l2_min_imbalance": 0.02,
            "l2_min_directional_consistency": 0.24,
            "l2_min_signed_aggression": 0.02,
            "l2_lookback_bars": 3,
            "include_extended_hours": False,
        },
        strategy_overrides={
            "min_flow_score": 46.5,
            "min_signed_aggression": 0.04,
            "min_directional_consistency": 0.54,
            "min_flow_signal_margin": 0.008,
            "min_intrabar_window_move_pct": 0.012,
        },
    ),
    Variant(
        name="micro_scratch_fast_be",
        description="Lower L2 gates + tiny R target + very fast break-even for quick scratch scalps.",
        run_overrides={
            "l2_min_imbalance": 0.012,
            "l2_min_directional_consistency": 0.16,
            "l2_min_signed_aggression": 0.012,
            "l2_lookback_bars": 2,
            "include_extended_hours": False,
            "partial_take_profit_rr": 0.55,
            "partial_take_profit_fraction": 0.65,
            "trailing_activation_pct": 0.08,
            "break_even_buffer_pct": 0.0,
            "break_even_min_hold_bars": 1,
            "time_exit_bars": 16,
            "adverse_flow_threshold": 0.10,
            "adverse_flow_min_hold_bars": 2,
        },
        strategy_overrides={
            "min_flow_score": 41.0,
            "min_signed_aggression": 0.028,
            "min_directional_consistency": 0.46,
            "min_imbalance": 0.015,
            "min_book_pressure": 0.01,
            "min_participation_ratio": 0.035,
            "min_flow_score_trend_3bar": -5.0,
            "min_intrabar_move_pct": 0.02,
            "min_intrabar_push_ratio": 0.07,
            "min_intrabar_coverage_points": 3,
            "min_intrabar_directional_consistency": 0.08,
            "min_intrabar_window_move_pct": 0.007,
            "min_intrabar_window_push_ratio": 0.04,
            "min_intrabar_window_directional_consistency": 0.05,
            "max_intrabar_micro_volatility_bps": 22.0,
            "max_intrabar_spread_bps": 9.0,
            "spread_penalty_floor_bps": 3.0,
            "spread_flow_score_penalty_per_bps": 0.30,
            "min_round_trip_cost_bps": 6.0,
            "spread_cost_multiplier": 1.0,
            "min_reward_to_cost_ratio": 1.2,
            "min_flow_signal_margin": 0.004,
            "max_abs_price_extension_pct": 1.4,
            "min_confidence": 48.0,
            "atr_stop_multiplier": 0.54,
            "min_stop_loss_pct": 0.04,
            "rr_ratio": 1.0,
            "trailing_stop_pct": 0.16,
        },
    ),
    Variant(
        name="turn_joiner_volume",
        description="Volume/participation-biased turn joiner with quick partials and early BE.",
        run_overrides={
            "l2_min_imbalance": 0.015,
            "l2_min_directional_consistency": 0.20,
            "l2_min_signed_aggression": 0.015,
            "l2_lookback_bars": 2,
            "include_extended_hours": False,
            "partial_take_profit_rr": 0.65,
            "partial_take_profit_fraction": 0.55,
            "trailing_activation_pct": 0.10,
            "break_even_buffer_pct": 0.0,
            "break_even_min_hold_bars": 1,
            "time_exit_bars": 20,
            "adverse_flow_threshold": 0.11,
            "adverse_flow_min_hold_bars": 2,
        },
        strategy_overrides={
            "min_flow_score": 44.0,
            "min_signed_aggression": 0.03,
            "min_directional_consistency": 0.50,
            "min_imbalance": 0.018,
            "min_book_pressure": 0.015,
            "min_participation_ratio": 0.06,
            "min_flow_score_trend_3bar": -4.0,
            "min_intrabar_move_pct": 0.025,
            "min_intrabar_push_ratio": 0.09,
            "min_intrabar_coverage_points": 4,
            "min_intrabar_directional_consistency": 0.10,
            "min_intrabar_window_move_pct": 0.009,
            "min_intrabar_window_push_ratio": 0.05,
            "min_intrabar_window_directional_consistency": 0.06,
            "max_intrabar_micro_volatility_bps": 20.0,
            "max_intrabar_spread_bps": 8.0,
            "spread_penalty_floor_bps": 3.5,
            "spread_flow_score_penalty_per_bps": 0.35,
            "min_round_trip_cost_bps": 6.0,
            "spread_cost_multiplier": 1.0,
            "min_reward_to_cost_ratio": 1.3,
            "min_flow_signal_margin": 0.006,
            "max_abs_price_extension_pct": 1.2,
            "min_confidence": 50.0,
            "atr_stop_multiplier": 0.58,
            "min_stop_loss_pct": 0.045,
            "rr_ratio": 1.05,
            "trailing_stop_pct": 0.18,
        },
    ),
    Variant(
        name="turn_joiner_tight_spread",
        description="Turn joiner focused on tight spread/slippage control with small target.",
        run_overrides={
            "l2_min_imbalance": 0.018,
            "l2_min_directional_consistency": 0.22,
            "l2_min_signed_aggression": 0.018,
            "l2_lookback_bars": 2,
            "include_extended_hours": False,
            "partial_take_profit_rr": 0.70,
            "partial_take_profit_fraction": 0.50,
            "trailing_activation_pct": 0.09,
            "break_even_buffer_pct": 0.0,
            "break_even_min_hold_bars": 1,
            "time_exit_bars": 18,
            "adverse_flow_threshold": 0.10,
            "adverse_flow_min_hold_bars": 2,
        },
        strategy_overrides={
            "min_flow_score": 43.0,
            "min_signed_aggression": 0.032,
            "min_directional_consistency": 0.52,
            "min_imbalance": 0.02,
            "min_book_pressure": 0.018,
            "min_participation_ratio": 0.05,
            "min_flow_score_trend_3bar": -3.5,
            "min_intrabar_move_pct": 0.022,
            "min_intrabar_push_ratio": 0.08,
            "min_intrabar_coverage_points": 4,
            "min_intrabar_directional_consistency": 0.10,
            "min_intrabar_window_move_pct": 0.008,
            "min_intrabar_window_push_ratio": 0.045,
            "min_intrabar_window_directional_consistency": 0.06,
            "max_intrabar_micro_volatility_bps": 19.0,
            "max_intrabar_spread_bps": 6.0,
            "spread_penalty_floor_bps": 2.8,
            "spread_flow_score_penalty_per_bps": 0.50,
            "min_round_trip_cost_bps": 5.5,
            "spread_cost_multiplier": 1.0,
            "min_reward_to_cost_ratio": 1.18,
            "min_flow_signal_margin": 0.006,
            "max_abs_price_extension_pct": 1.0,
            "min_confidence": 49.0,
            "atr_stop_multiplier": 0.56,
            "min_stop_loss_pct": 0.04,
            "rr_ratio": 0.95,
            "trailing_stop_pct": 0.14,
        },
    ),
    Variant(
        name="scratch_balanced_v2",
        description="Balanced scratch profile: faster BE and smaller TP, but less aggressive than tight-spread.",
        run_overrides={
            "l2_min_imbalance": 0.016,
            "l2_min_directional_consistency": 0.21,
            "l2_min_signed_aggression": 0.016,
            "l2_lookback_bars": 3,
            "include_extended_hours": False,
            "partial_take_profit_rr": 0.80,
            "partial_take_profit_fraction": 0.45,
            "trailing_activation_pct": 0.12,
            "break_even_buffer_pct": 0.0,
            "break_even_min_hold_bars": 1,
            "time_exit_bars": 22,
            "adverse_flow_threshold": 0.11,
            "adverse_flow_min_hold_bars": 2,
        },
        strategy_overrides={
            "min_flow_score": 45.0,
            "min_signed_aggression": 0.036,
            "min_directional_consistency": 0.53,
            "min_imbalance": 0.02,
            "min_book_pressure": 0.016,
            "min_participation_ratio": 0.045,
            "min_flow_score_trend_3bar": -3.0,
            "min_intrabar_move_pct": 0.024,
            "min_intrabar_push_ratio": 0.085,
            "min_intrabar_coverage_points": 4,
            "min_intrabar_directional_consistency": 0.10,
            "min_intrabar_window_move_pct": 0.009,
            "min_intrabar_window_push_ratio": 0.05,
            "min_intrabar_window_directional_consistency": 0.06,
            "max_intrabar_micro_volatility_bps": 19.5,
            "max_intrabar_spread_bps": 7.0,
            "spread_penalty_floor_bps": 3.2,
            "spread_flow_score_penalty_per_bps": 0.40,
            "min_round_trip_cost_bps": 6.0,
            "spread_cost_multiplier": 1.0,
            "min_reward_to_cost_ratio": 1.30,
            "min_flow_signal_margin": 0.007,
            "max_abs_price_extension_pct": 1.15,
            "min_confidence": 51.0,
            "atr_stop_multiplier": 0.60,
            "min_stop_loss_pct": 0.045,
            "rr_ratio": 1.10,
            "trailing_stop_pct": 0.17,
        },
    ),
]


def _build_run_payload(run_id: str, date_from: str, date_to: str, run_overrides: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "run_id": run_id,
        "ticker": TICKER,
        "date_from": date_from,
        "date_to": date_to,
        "strategy_api_url": STRATEGY_API,
        "comparable_mode": True,
        "apply_ticker_overrides_on_start": False,
        "apply_aos_optimizations_on_start": False,
        "l2_only": True,
        "l2_confirm_enabled": True,
        "strategy_selection_mode": "all_enabled",
        "max_active_strategies": 1,
        "intrabar_execution_recalc_1s": True,
        "include_extended_hours": False,
        "account_size_usd": 10000.0,
        "risk_per_trade_pct": 2.0,
    }
    payload.update(run_overrides or {})
    return payload


def _poll_run_completion(run_id: str, ticker: str, run_date: str, timeout_sec: int = 5400) -> Dict[str, Any]:
    state_url = f"{RUNNER_API}/api/run/{run_id}/{ticker}/{run_date}/state"
    start = time.time()
    while True:
        state = _api_get(state_url, timeout=120.0)
        current = int(state.get("current_bar_index") or 0)
        total = int(state.get("total_bars") or 0)
        is_running = bool(state.get("is_running"))
        is_paused = bool(state.get("is_paused"))
        if total > 0 and current >= total and (not is_running):
            return state
        if (time.time() - start) > timeout_sec:
            raise TimeoutError(
                f"Run timeout run_id={run_id} date={run_date} progress={current}/{total} running={is_running} paused={is_paused}"
            )
        time.sleep(2.0)


def _run_once(
    *,
    variant: Variant,
    date_from: str,
    date_to: str,
    trade_eval_mode: str,
    start_timeout_sec: float = 240.0,
) -> Dict[str, Any]:
    run_id = f"scalp-audit-{variant.name}-{uuid.uuid4().hex[:8]}"
    payload = _build_run_payload(run_id, date_from, date_to, variant.run_overrides)

    start_wall = time.time()
    start_data = _api_post(f"{RUNNER_API}/api/run/start", payload, timeout=start_timeout_sec)
    run_key = str(start_data.get("run_key") or "").strip()
    if not run_key:
        raise RuntimeError(f"Missing run_key for run_id={run_id}")
    parsed_run_id, ticker, run_date = _parse_run_key(run_key)

    play_payload = {"speed_ms": "max", "trade_eval_mode": trade_eval_mode}
    _ = _api_post(
        f"{RUNNER_API}/api/run/{parsed_run_id}/{ticker}/{run_date}/play",
        play_payload,
        timeout=120.0,
    )
    _poll_run_completion(parsed_run_id, ticker, run_date)
    elapsed_sec = time.time() - start_wall

    summary = _api_get(
        f"{RUNNER_API}/api/run/{parsed_run_id}/{ticker}/{run_date}/summary",
        timeout=120.0,
    )
    bars_payload = _api_get(
        f"{RUNNER_API}/api/run/{parsed_run_id}/{ticker}/{run_date}/bars",
        timeout=120.0,
    )
    markers = summary.get("markers") if isinstance(summary.get("markers"), list) else []
    bars = bars_payload.get("bars") if isinstance(bars_payload.get("bars"), list) else []

    session = summary.get("session_summary") or {}
    total_trades = int(session.get("total_trades") or 0)
    winning = int(session.get("winning_trades") or 0)
    win_rate = (winning / total_trades * 100.0) if total_trades > 0 else 0.0
    total_pnl_pct = _safe_float(session.get("total_pnl_pct"), 0.0)
    total_pnl_dollars = _safe_float(session.get("total_pnl_dollars"), 0.0)
    avg_pnl_pct = _safe_float(session.get("avg_pnl_pct"), 0.0)

    entry_vol_ratio = _entry_volume_ratio(markers, bars)
    entry_l2_stats = _entry_l2_stats(markers)

    result = {
        "variant": variant.name,
        "description": variant.description,
        "trade_eval_mode": trade_eval_mode,
        "date_from": date_from,
        "date_to": date_to,
        "run_key": run_key,
        "elapsed_sec": round(elapsed_sec, 2),
        "bars_total": int(summary.get("total_bars") or 0),
        "processed_bars": int(summary.get("processed_bars") or 0),
        "phase": str(summary.get("phase") or ""),
        "total_trades": total_trades,
        "winning_trades": winning,
        "losing_trades": int(session.get("losing_trades") or 0),
        "win_rate_pct": round(win_rate, 2),
        "total_pnl_pct": round(total_pnl_pct, 4),
        "total_pnl_dollars": round(total_pnl_dollars, 4),
        "avg_pnl_pct": round(avg_pnl_pct, 4),
        "entry_volume_ratio_vs_median": None if entry_vol_ratio is None else round(entry_vol_ratio, 4),
        "entry_avg_flow_score": None
        if entry_l2_stats["entry_avg_flow_score"] is None
        else round(float(entry_l2_stats["entry_avg_flow_score"]), 4),
        "entry_avg_abs_signed_aggression": None
        if entry_l2_stats["entry_avg_abs_signed_aggression"] is None
        else round(float(entry_l2_stats["entry_avg_abs_signed_aggression"]), 4),
        "entry_avg_abs_direction_margin": None
        if entry_l2_stats["entry_avg_abs_direction_margin"] is None
        else round(float(entry_l2_stats["entry_avg_abs_direction_margin"]), 4),
        "entry_avg_participation_ratio": None
        if entry_l2_stats["entry_avg_participation_ratio"] is None
        else round(float(entry_l2_stats["entry_avg_participation_ratio"]), 4),
        "entry_avg_spread_bps": None
        if entry_l2_stats["entry_avg_spread_bps"] is None
        else round(float(entry_l2_stats["entry_avg_spread_bps"]), 4),
        "entry_avg_abs_push_ratio": None
        if entry_l2_stats["entry_avg_abs_push_ratio"] is None
        else round(float(entry_l2_stats["entry_avg_abs_push_ratio"]), 4),
        "entry_window_5s_share": None
        if entry_l2_stats["entry_window_5s_share"] is None
        else round(float(entry_l2_stats["entry_window_5s_share"]), 4),
        "entry_turn_candidate_share": None
        if entry_l2_stats["entry_turn_candidate_share"] is None
        else round(float(entry_l2_stats["entry_turn_candidate_share"]), 4),
        "include_extended_hours": bool((summary.get("execution_config") or {}).get("include_extended_hours", False)),
        "execution_config": summary.get("execution_config") or {},
        "l2_applied": summary.get("aos_applied", {}).get("l2", {}),
    }

    # Cleanup run to keep registry manageable.
    _api_delete(f"{RUNNER_API}/api/run/{parsed_run_id}/{ticker}/{run_date}", timeout=120.0)
    return result


def _screen_score(row: Dict[str, Any]) -> float:
    # Profit-first, with anti-overfit penalties and preference for repeatable micro-scalp activity.
    pnl = _safe_float(row.get("total_pnl_pct"), 0.0)
    avg_pnl = _safe_float(row.get("avg_pnl_pct"), 0.0)
    trades = int(row.get("total_trades") or 0)
    if trades <= 0:
        return -999.0
    activity_bonus = min(0.12, 0.015 * trades)
    low_sample_penalty = 0.06 * max(0, 4 - trades)
    turn_share = _safe_float(row.get("entry_turn_candidate_share"), 0.0)
    turn_bonus = 0.03 * max(0.0, min(1.0, turn_share))
    return pnl + activity_bonus + (0.20 * avg_pnl) + turn_bonus - low_sample_penalty


def _robust_validation_score(screen_row: Optional[Dict[str, Any]], validation_row: Dict[str, Any]) -> float:
    """
    Prefer holdout edge, penalize train->holdout drift (anti-overfit bias).
    """
    val_pnl = _safe_float(validation_row.get("total_pnl_pct"), 0.0)
    val_avg_pnl = _safe_float(validation_row.get("avg_pnl_pct"), 0.0)
    val_trades = int(validation_row.get("total_trades") or 0)
    if val_trades <= 0:
        return -999.0
    activity_bonus = min(0.16, 0.018 * val_trades)
    low_sample_penalty = 0.08 * max(0, 4 - val_trades)
    turn_share = _safe_float(validation_row.get("entry_turn_candidate_share"), 0.0)
    turn_bonus = 0.04 * max(0.0, min(1.0, turn_share))
    base_score = val_pnl + activity_bonus + (0.20 * val_avg_pnl) + turn_bonus - low_sample_penalty

    if not isinstance(screen_row, dict):
        # No screen context: keep conservative score.
        return base_score

    scr_pnl = _safe_float(screen_row.get("total_pnl_pct"), 0.0)
    scr_trades = int(screen_row.get("total_trades") or 0)

    pnl_drift = abs(scr_pnl - val_pnl)
    trade_stability_penalty = 0.0
    if scr_trades > 0:
        ratio = val_trades / max(1, scr_trades)
        if ratio < 0.4:
            trade_stability_penalty += (0.4 - ratio) * 0.3
    else:
        trade_stability_penalty += 0.12

    sign_flip_penalty = 0.0
    if scr_pnl > 0 and val_pnl <= 0:
        sign_flip_penalty = 0.35

    return base_score - (0.35 * pnl_drift) - trade_stability_penalty - sign_flip_penalty


def run_research(
    screen_from: str,
    screen_to: str,
    validate_from: str,
    validate_to: str,
    *,
    selected_variant_names: Optional[List[str]] = None,
    finalist_count: int = 2,
    run_extended_hours_check: bool = True,
    force_validate_all_selected: bool = False,
    screen_trade_eval_mode: str = "standard",
    validate_trade_eval_mode: str = "intrabar_5s",
    start_timeout_sec: float = 240.0,
) -> Dict[str, Any]:
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    original_strategies = _fetch_strategies()
    original_scalp = dict(original_strategies.get(SCALP_STRATEGY, {}))

    report: Dict[str, Any] = {
        "meta": {
            "started_at_utc": started_at,
            "ticker": TICKER,
            "runner_api": RUNNER_API,
            "strategy_api": STRATEGY_API,
            "combo_profile": SCALP_COMBO_PROFILE,
            "screen_from": screen_from,
            "screen_to": screen_to,
            "validate_from": validate_from,
            "validate_to": validate_to,
        },
        "youtube_source_urls": [
            "https://www.youtube.com/shorts/N4hrWXLnRUI",
            "https://www.youtube.com/watch?v=XBcMiYK7qYY",
            "https://www.youtube.com/watch?v=p1W8Mjl4kWs",
            "https://www.youtube.com/watch?v=wH3ypUlgQXw",
            "https://www.youtube.com/shorts/CWO2ZAP7lO4",
            "https://www.youtube.com/watch?v=E8jZkhBOmEE&t=685s",
            "https://www.youtube.com/watch?v=wKhngxCVCcQ",
            "https://www.youtube.com/watch?v=AlsXNhTm4AA&t=345s",
            "https://www.youtube.com/watch?v=8v-Z5oyKVG0&t=373s",
        ],
        "screen_runs": [],
        "validation_runs": [],
        "winner_extended_hours_check": None,
        "errors": [],
    }

    if selected_variant_names:
        name_set = {str(name).strip() for name in selected_variant_names if str(name).strip()}
        variants = [v for v in VARIANTS if v.name in name_set]
        if not variants:
            raise RuntimeError(f"No matching variants selected: {sorted(name_set)}")
    else:
        variants = list(VARIANTS)

    try:
        # Keep strategy space deterministic: apply known combo profile before each variant.
        _apply_combo_profile(SCALP_COMBO_PROFILE)

        for variant in variants:
            _apply_combo_profile(SCALP_COMBO_PROFILE)
            if variant.strategy_overrides:
                _update_strategy_params(SCALP_STRATEGY, variant.strategy_overrides)
            row = _run_once(
                variant=variant,
                date_from=screen_from,
                date_to=screen_to,
                trade_eval_mode=screen_trade_eval_mode,
                start_timeout_sec=start_timeout_sec,
            )
            row["screen_score"] = round(_screen_score(row), 4)
            report["screen_runs"].append(row)

        if force_validate_all_selected:
            finalists = list(variants)
        else:
            sorted_screen = sorted(report["screen_runs"], key=lambda r: _safe_float(r.get("screen_score")), reverse=True)
            finalist_names = [
                r["variant"]
                for r in sorted_screen[: max(1, int(finalist_count))]
                if _safe_float(r.get("screen_score"), -999) > -999
            ]
            if "baseline" not in finalist_names:
                finalist_names = ["baseline"] + finalist_names
            finalists = []
            seen = set()
            for name in finalist_names:
                if name in seen:
                    continue
                seen.add(name)
                for v in variants:
                    if v.name == name:
                        finalists.append(v)
                        break

        for variant in finalists:
            _apply_combo_profile(SCALP_COMBO_PROFILE)
            if variant.strategy_overrides:
                _update_strategy_params(SCALP_STRATEGY, variant.strategy_overrides)
            row = _run_once(
                variant=variant,
                date_from=validate_from,
                date_to=validate_to,
                trade_eval_mode=validate_trade_eval_mode,
                start_timeout_sec=start_timeout_sec,
            )
            screen_match = next(
                (s for s in report["screen_runs"] if str(s.get("variant")) == str(row.get("variant"))),
                None,
            )
            row["robust_score"] = round(_robust_validation_score(screen_match, row), 4)
            report["validation_runs"].append(row)

        if run_extended_hours_check and report["validation_runs"]:
            winner = sorted(
                report["validation_runs"],
                key=lambda r: (_safe_float(r.get("robust_score"), -999), _safe_float(r.get("total_pnl_pct"), -999)),
                reverse=True,
            )[0]
            winner_name = winner.get("variant")
            winner_variant = next((v for v in variants if v.name == winner_name), None)
            if winner_variant is not None:
                _apply_combo_profile(SCALP_COMBO_PROFILE)
                if winner_variant.strategy_overrides:
                    _update_strategy_params(SCALP_STRATEGY, winner_variant.strategy_overrides)
                ext_variant = Variant(
                    name=f"{winner_variant.name}_extended_hours",
                    description="Winner variant with include_extended_hours=True",
                    run_overrides={**winner_variant.run_overrides, "include_extended_hours": True},
                    strategy_overrides=winner_variant.strategy_overrides,
                )
                report["winner_extended_hours_check"] = _run_once(
                    variant=ext_variant,
                    date_from=validate_from,
                    date_to=validate_to,
                    trade_eval_mode=validate_trade_eval_mode,
                    start_timeout_sec=start_timeout_sec,
                )

    except Exception as exc:
        report["errors"].append(str(exc))
    finally:
        # Restore baseline strategy profile as safety.
        try:
            _apply_combo_profile(SCALP_COMBO_PROFILE)
        except Exception as exc:
            report["errors"].append(f"combo_restore_failed: {exc}")
        try:
            if original_scalp:
                _update_strategy_params(SCALP_STRATEGY, original_scalp)
        except Exception as exc:
            report["errors"].append(f"strategy_restore_failed: {exc}")

    report["meta"]["finished_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run scalp L2 research experiments.")
    parser.add_argument("--screen-date", default="2026-02-10")
    parser.add_argument("--validate-date", default="2026-02-13")
    parser.add_argument("--screen-from", default="", help="Optional screen range start (YYYY-MM-DD).")
    parser.add_argument("--screen-to", default="", help="Optional screen range end (YYYY-MM-DD).")
    parser.add_argument("--validate-from", default="", help="Optional validate range start (YYYY-MM-DD).")
    parser.add_argument("--validate-to", default="", help="Optional validate range end (YYYY-MM-DD).")
    parser.add_argument("--output", default=str(REPORT_PATH))
    parser.add_argument(
        "--variants",
        default="",
        help="Comma-separated variant names to include (default: all).",
    )
    parser.add_argument(
        "--finalists",
        type=int,
        default=2,
        help="How many top screen variants to validate (baseline always included).",
    )
    parser.add_argument(
        "--skip-extended-check",
        action="store_true",
        help="Skip include_extended_hours winner check.",
    )
    parser.add_argument(
        "--force-validate-all-selected",
        action="store_true",
        help="Validate all selected variants regardless of screen score.",
    )
    parser.add_argument(
        "--screen-trade-mode",
        default="standard",
        help="Trade eval mode for screen runs (standard|intrabar_5s|intrabar_1s).",
    )
    parser.add_argument(
        "--validate-trade-mode",
        default="intrabar_5s",
        help="Trade eval mode for validation runs (standard|intrabar_5s|intrabar_1s).",
    )
    parser.add_argument(
        "--start-timeout-sec",
        type=float,
        default=600.0,
        help="Timeout for POST /api/run/start (larger windows can require >240s).",
    )
    args = parser.parse_args()

    selected_variants = [part.strip() for part in str(args.variants).split(",") if part.strip()]
    screen_from = str(args.screen_from or "").strip() or str(args.screen_date).strip()
    screen_to = str(args.screen_to or "").strip() or str(args.screen_date).strip()
    validate_from = str(args.validate_from or "").strip() or str(args.validate_date).strip()
    validate_to = str(args.validate_to or "").strip() or str(args.validate_date).strip()
    report = run_research(
        screen_from=screen_from,
        screen_to=screen_to,
        validate_from=validate_from,
        validate_to=validate_to,
        selected_variant_names=selected_variants if selected_variants else None,
        finalist_count=max(1, int(args.finalists)),
        run_extended_hours_check=not bool(args.skip_extended_check),
        force_validate_all_selected=bool(args.force_validate_all_selected),
        screen_trade_eval_mode=str(args.screen_trade_mode or "standard").strip().lower(),
        validate_trade_eval_mode=str(args.validate_trade_mode or "intrabar_5s").strip().lower(),
        start_timeout_sec=max(30.0, float(args.start_timeout_sec)),
    )
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote report: {out_path}")
    if report.get("errors"):
        print("Errors:")
        for e in report["errors"]:
            print(f"  - {e}")
    else:
        print("Completed without runtime errors.")

    screen_runs = report.get("screen_runs") or []
    val_runs = report.get("validation_runs") or []
    print(f"Screen runs: {len(screen_runs)} | Validation runs: {len(val_runs)}")
    if val_runs:
        top = sorted(
            val_runs,
            key=lambda r: (_safe_float(r.get("robust_score"), -999), _safe_float(r.get("total_pnl_pct"), -999)),
            reverse=True,
        )[0]
        print(
            f"Validation winner: {top.get('variant')} | robust={top.get('robust_score')} | "
            f"pnl={top.get('total_pnl_pct')}% | trades={top.get('total_trades')} | win={top.get('win_rate_pct')}%"
        )


if __name__ == "__main__":
    main()
