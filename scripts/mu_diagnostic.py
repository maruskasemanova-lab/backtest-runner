#!/usr/bin/env python3
"""
MU Diagnostic & Ablation Pipeline

Walk-forward splits (strict, no overlap):
- Tuning:  2025-11-03 to 2025-12-26 (parameter optimization)
- Buffer:  2025-12-29 to 2026-01-03 (gap, unused)
- Test:    2026-01-05 to 2026-02-10 (holdout, one-time)

Phases:
  0  Diagnostic  — classify each day's signal pipeline, sanity gate
  1  Ablation    — 5 variants (A-E) on tuning set only
  2  Test        — one-time holdout validation with config hash protection
  3  Apply       — write winning config to AOS

Usage:
  python3 scripts/mu_diagnostic.py phase0
  python3 scripts/mu_diagnostic.py phase1
  python3 scripts/mu_diagnostic.py phase2
  python3 scripts/mu_diagnostic.py phase3
  python3 scripts/mu_diagnostic.py all     # phases 0-3 sequentially
"""

import argparse
import asyncio
import copy
import hashlib
import json
import os
import random
import re
import sys
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx
import pandas as pd


# ── Constants ────────────────────────────────────────────────────────────────

TICKER = "MU"
RUNNER_API_URL = "http://localhost:8002"
STRATEGY_API_URL = "http://localhost:8001"
NY_TZ = ZoneInfo("America/New_York")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_L2_DIR = PROJECT_ROOT / "data" / "l2"
OHLCV_SCHEMA = "ohlcv-1m"
L2_SCHEMA = "mbp-10"

# Walk-forward splits
TUNING_START = "2025-11-03"
TUNING_END = "2025-12-26"
BUFFER_START = "2025-12-29"
BUFFER_END = "2026-01-03"
TEST_START = "2026-01-05"
TEST_END = "2026-02-10"

# Guardrail defaults
COOLDOWN_AFTER_WIN = 5
COOLDOWN_AFTER_LOSS = 25
MIN_EDGE_MARGIN = 5
FAST_MODE_CACHE_MAX_ROWS = 5_000_000
FAST_MODE_CACHE_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports" / "mu_diagnostic"
TEST_LOCK_FILE = REPORTS_DIR / "test_lock.json"


# ── Date helpers ─────────────────────────────────────────────────────────────

def iter_weekdays(start: str, end: str) -> List[str]:
    """Yield YYYY-MM-DD for each weekday in [start, end]."""
    dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    dates = []
    while dt <= end_dt:
        if dt.weekday() < 5:  # Mon-Fri
            dates.append(dt.strftime("%Y-%m-%d"))
        dt += timedelta(days=1)
    return dates


def summarize_days(days: List[str], max_items: int = 12) -> str:
    ordered = sorted({str(day) for day in days if str(day).strip()})
    if not ordered:
        return "-"
    if len(ordered) <= max_items:
        return ", ".join(ordered)
    return ", ".join(ordered[:max_items]) + f", ... (+{len(ordered) - max_items} more)"


def safe_text(value: Any, limit: int = 300) -> str:
    text = str(value or "").strip().replace("\n", " ").replace("\r", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def normalize_skip_reason(raw_reason: str) -> str:
    reason = str(raw_reason or "").strip().lower()
    if not reason:
        return "unknown"
    if "no aligned strategy signal" in reason:
        return "no_aligned_strategy_signal"
    if "regime filter" in reason or "choppy" in reason:
        return "regime_filter"
    if "threshold" in reason:
        return "threshold_gate"
    if "risk" in reason or "drawdown" in reason:
        return "risk_gate"
    if "cooldown" in reason:
        return "cooldown_gate"
    compact = re.sub(r"[^a-z0-9]+", "_", reason).strip("_")
    return compact or "unknown"


def _parse_l2_day_from_filename(path: Path) -> Optional[str]:
    match = re.match(rf"^{TICKER}_(\d{{4}}-\d{{2}}-\d{{2}})_\1\.parquet$", path.name)
    if not match:
        return None
    return match.group(1)


def get_available_l2_dates(start: str, end: str) -> List[str]:
    """Discover MU L2 days from local daily parquet files."""
    start_dt = datetime.strptime(start, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end, "%Y-%m-%d").date()
    days = set()
    if not LOCAL_L2_DIR.exists():
        return []
    for path in LOCAL_L2_DIR.glob(f"{TICKER}_*.parquet"):
        day = _parse_l2_day_from_filename(path)
        if not day:
            continue
        day_dt = datetime.strptime(day, "%Y-%m-%d").date()
        if start_dt <= day_dt <= end_dt:
            days.add(day)
    return sorted(days)


def _extract_ohlcv_days_from_csv(csv_path: Path, start: str, end: str) -> List[str]:
    start_day = datetime.strptime(start, "%Y-%m-%d").date()
    end_day = datetime.strptime(end, "%Y-%m-%d").date()
    days = set()
    for chunk in pd.read_csv(csv_path, usecols=["timestamp"], chunksize=300_000):
        ts = pd.to_datetime(chunk["timestamp"], utc=True, errors="coerce")
        ts = ts.dropna()
        if ts.empty:
            continue
        local_dates = ts.dt.tz_convert(NY_TZ).dt.date
        for day in local_dates:
            if start_day <= day <= end_day:
                days.add(day.isoformat())
    return sorted(days)


def _extract_ohlcv_days_from_parquet(parquet_path: Path, start: str, end: str) -> List[str]:
    start_day = datetime.strptime(start, "%Y-%m-%d").date()
    end_day = datetime.strptime(end, "%Y-%m-%d").date()
    df = pd.read_parquet(parquet_path, columns=["timestamp"])
    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dropna()
    if ts.empty:
        return []
    return sorted(
        {
            day.isoformat()
            for day in ts.dt.tz_convert(NY_TZ).dt.date
            if start_day <= day <= end_day
        }
    )


async def get_available_ohlcv_dates(
    client: httpx.AsyncClient,
    start: str,
    end: str,
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Resolve MU OHLCV days from catalog files and map timestamps to US trading day.

    We derive day keys in America/New_York to match runner day semantics.
    """
    details: Dict[str, Any] = {"files_scanned": [], "file_errors": []}
    try:
        resp = await client.get(
            f"{RUNNER_API_URL}/api/data-loader/catalog",
            params={"ticker": TICKER, "schema": OHLCV_SCHEMA},
            timeout=30.0,
        )
    except Exception as exc:
        details["file_errors"].append(f"catalog_request_failed: {type(exc).__name__}: {safe_text(exc)}")
        return [], details

    if resp.status_code != 200:
        details["file_errors"].append(
            f"catalog_http_{resp.status_code}: {safe_text(resp.text)}"
        )
        return [], details

    payload = resp.json()
    entries = payload if isinstance(payload, list) else payload.get("entries", [])
    covered = set()
    for row in entries:
        if str(row.get("status", "")).lower() != "ready":
            continue
        preferred = row.get("file_parquet") or row.get("file_csv")
        if not preferred:
            continue
        path = Path(str(preferred)).expanduser().resolve()
        if not path.exists():
            details["file_errors"].append(f"missing_file: {path}")
            continue
        try:
            if path.suffix.lower() in {".parquet", ".parq"}:
                days = _extract_ohlcv_days_from_parquet(path, start, end)
            else:
                days = _extract_ohlcv_days_from_csv(path, start, end)
            covered.update(days)
            details["files_scanned"].append(str(path))
        except Exception as exc:
            details["file_errors"].append(f"{path.name}: {type(exc).__name__}: {safe_text(exc)}")
    return sorted(covered), details


async def resolve_dataset_dates(
    client: httpx.AsyncClient,
    start: str,
    end: str,
    require_l2: bool = True,
) -> Dict[str, Any]:
    """
    Build date list from actual dataset overlap instead of plain calendar.

    Returns weekdays in split, OHLCV days, L2 days, and final usable dates.
    """
    weekdays = iter_weekdays(start, end)
    ohlcv_days, ohlcv_details = await get_available_ohlcv_dates(client, start, end)
    l2_days = get_available_l2_dates(start, end)

    weekday_set = set(weekdays)
    ohlcv_set = set(ohlcv_days)
    l2_set = set(l2_days)

    if require_l2:
        available = sorted(weekday_set.intersection(ohlcv_set).intersection(l2_set))
    else:
        available = sorted(weekday_set.intersection(ohlcv_set))

    missing_ohlcv = sorted(weekday_set - ohlcv_set)
    missing_l2 = sorted(weekday_set - l2_set) if require_l2 else []
    missing_overlap = (
        sorted(weekday_set - (ohlcv_set.intersection(l2_set)))
        if require_l2
        else sorted(weekday_set - ohlcv_set)
    )

    return {
        "weekdays": weekdays,
        "ohlcv_days": sorted(ohlcv_set),
        "l2_days": sorted(l2_set),
        "available_days": available,
        "missing_ohlcv_days": missing_ohlcv,
        "missing_l2_days": missing_l2,
        "missing_overlap_days": missing_overlap,
        "ohlcv_details": ohlcv_details,
    }


def init_funnel() -> Dict[str, Any]:
    return {
        "bars_processed": 0,
        "strategies_evaluated": 0,
        "candidates_generated": 0,
        "candidates_rejected": 0,
        "evidence_passed": 0,
        "trades_placed": 0,
        "trades_closed": 0,
        "actions": {},
        "reject_by_gate": {},
        "reject_by_reason": {},
        "no_candidate_by_reason": {},
        "first_bar_ts": None,
        "last_bar_ts": None,
    }


def update_funnel(funnel: Dict[str, Any], response: Dict[str, Any]) -> None:
    funnel["bars_processed"] += 1
    action = str(response.get("action", "") or "")
    if action:
        funnel["actions"][action] = int(funnel["actions"].get(action, 0)) + 1
    if action in {"trading", "regime_filter"}:
        funnel["strategies_evaluated"] += 1

    ts = response.get("bar_timestamp")
    if ts:
        if not funnel["first_bar_ts"]:
            funnel["first_bar_ts"] = ts
        funnel["last_bar_ts"] = ts

    signal_items = []
    maybe_signal = response.get("signal")
    if isinstance(maybe_signal, dict) and maybe_signal:
        signal_items.append(maybe_signal)
    maybe_signals = response.get("signals")
    if isinstance(maybe_signals, list):
        for item in maybe_signals:
            if isinstance(item, dict) and item:
                signal_items.append(item)
    if signal_items:
        funnel["candidates_generated"] += len(signal_items)

    rejected = response.get("signal_rejected")
    if isinstance(rejected, dict) and rejected:
        funnel["candidates_rejected"] += 1
        gate = str(rejected.get("gate", "unknown") or "unknown")
        funnel["reject_by_gate"][gate] = int(funnel["reject_by_gate"].get(gate, 0)) + 1
        normalized_reason = normalize_skip_reason(
            str(rejected.get("reasoning") or response.get("reason") or gate)
        )
        funnel["reject_by_reason"][normalized_reason] = int(
            funnel["reject_by_reason"].get(normalized_reason, 0) + 1
        )
        if rejected.get("has_pattern") is False:
            funnel["no_candidate_by_reason"][normalized_reason] = int(
                funnel["no_candidate_by_reason"].get(normalized_reason, 0) + 1
            )

    if signal_items and not rejected:
        funnel["evidence_passed"] += len(signal_items)

    if isinstance(response.get("position_opened"), dict):
        funnel["trades_placed"] += 1
        # Entry implies evidence passed.
        funnel["evidence_passed"] += max(0, 1 - len(signal_items))
    if isinstance(response.get("position_closed"), dict):
        funnel["trades_closed"] += 1

TUNING_DATES = iter_weekdays(TUNING_START, TUNING_END)
TEST_DATES = iter_weekdays(TEST_START, TEST_END)


# ── Orchestrator config (strategy API) ──────────────────────────────────────

async def set_orchestrator_config(
    client: httpx.AsyncClient,
    *,
    base_threshold: Optional[float] = None,
    min_confirming_sources: Optional[int] = None,
    min_margin_over_threshold: Optional[float] = None,
    single_source_min_margin: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Push orchestrator-level overrides to the strategy API.

    These directly control the ensemble combiner's threshold, margin, and
    confirming-sources requirements — the primary gates that blocked 90%+
    of MU signals in Phase 0.
    """
    body: Dict[str, Any] = {}
    if base_threshold is not None:
        body["base_threshold"] = base_threshold
    if min_confirming_sources is not None:
        body["min_confirming_sources"] = min_confirming_sources
    if min_margin_over_threshold is not None:
        body["min_margin_over_threshold"] = min_margin_over_threshold
    if single_source_min_margin is not None:
        body["single_source_min_margin"] = single_source_min_margin

    if not body:
        return {"skipped": True}

    resp = await client.post(
        f"{STRATEGY_API_URL}/api/orchestrator/config",
        json=body,
        timeout=10.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to set orchestrator config: {resp.status_code} {safe_text(resp.text)}"
        )
    return resp.json()


async def get_orchestrator_config(client: httpx.AsyncClient) -> Dict[str, Any]:
    """Read current orchestrator config from strategy API for verification."""
    resp = await client.get(
        f"{STRATEGY_API_URL}/api/orchestrator/config",
        timeout=10.0,
    )
    if resp.status_code == 200:
        return resp.json()
    return {}


# ── Runner L2 runtime tuning (fast mode) ─────────────────────────────────────

async def set_runner_l2_runtime(
    client: httpx.AsyncClient,
    *,
    iceberg_detection_enabled: Optional[bool] = None,
    cache_max_rows: Optional[int] = None,
    cache_max_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if iceberg_detection_enabled is not None:
        body["iceberg_detection_enabled"] = bool(iceberg_detection_enabled)
    if cache_max_rows is not None:
        body["cache_max_rows"] = int(cache_max_rows)
    if cache_max_bytes is not None:
        body["cache_max_bytes"] = int(cache_max_bytes)
    if not body:
        return {"skipped": True}
    resp = await client.post(
        f"{RUNNER_API_URL}/api/system/l2/runtime",
        json=body,
        timeout=10.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Failed to set runner L2 runtime: {resp.status_code} {safe_text(resp.text)}"
        )
    return resp.json()


async def get_runner_l2_runtime(client: httpx.AsyncClient) -> Dict[str, Any]:
    resp = await client.get(
        f"{RUNNER_API_URL}/api/system/l2/runtime",
        timeout=10.0,
    )
    if resp.status_code == 200:
        return resp.json()
    return {}


async def apply_fast_mode(client: httpx.AsyncClient) -> Dict[str, Any]:
    """
    Fast mode for diagnostic/ablation:
      - disable iceberg detection (expensive, non-core for threshold-gate diagnosis)
      - increase in-memory L2 cache limits to reduce repeated day reloads
    """
    return await set_runner_l2_runtime(
        client,
        iceberg_detection_enabled=False,
        cache_max_rows=FAST_MODE_CACHE_MAX_ROWS,
        cache_max_bytes=FAST_MODE_CACHE_MAX_BYTES,
    )


# ── AOS config builder ──────────────────────────────────────────────────────

def load_baseline_aos() -> Dict[str, Any]:
    """Load the current AOS config as the baseline."""
    aos_path = Path(__file__).resolve().parent.parent / "aos_optimization" / "aos_config.json"
    with open(aos_path) as f:
        return json.load(f)


def build_variant_aos(
    variant_id: str,
    *,
    # L2 overrides
    l2_min_delta: Optional[float] = None,
    l2_min_imbalance: Optional[float] = None,
    l2_min_signed_aggression: Optional[float] = None,
    l2_min_directional_consistency: Optional[float] = None,
    # Strategy-level override (flows through /api/strategies/update)
    min_confidence: Optional[float] = None,
    # Regime overrides
    regime_filter: Optional[List[str]] = None,
    # Strategy overrides
    enabled_strategies: Optional[List[str]] = None,
    long_only: Optional[bool] = None,
    # Trading hours
    trading_hours: Optional[List[int]] = None,
    # Exit overrides
    atr_stop_multiplier: Optional[float] = None,
    rr_ratio: Optional[float] = None,
    trailing_stop_pct: Optional[float] = None,
    time_exit_bars: Optional[int] = None,
) -> Dict[str, Any]:
    """Build an isolated AOS config for a variant.

    NOTE: base_threshold and min_confirming_sources are NOT in AOS config.
    They live in the orchestrator and must be set via POST /api/orchestrator/config.
    Use set_orchestrator_config() before running days with a variant.
    """
    aos = load_baseline_aos()
    mu = aos.get("tickers", {}).get("MU", {})
    if not mu:
        raise RuntimeError("MU not found in AOS config")

    mu = copy.deepcopy(mu)

    # L2 overrides
    l2 = mu.setdefault("l2", {})
    if l2_min_delta is not None:
        l2["min_delta"] = l2_min_delta
    if l2_min_imbalance is not None:
        l2["min_imbalance"] = l2_min_imbalance
    if l2_min_signed_aggression is not None:
        l2["min_signed_aggression"] = l2_min_signed_aggression
    if l2_min_directional_consistency is not None:
        l2["min_directional_consistency"] = l2_min_directional_consistency

    # Strategy-level confidence override (actually flows through to strategies)
    if min_confidence is not None:
        mu["min_confidence"] = min_confidence
        mu.setdefault("params", {})["min_confidence"] = min_confidence

    # Regime
    if regime_filter is not None:
        mu["regime_filter"] = regime_filter

    # Strategies
    if enabled_strategies is not None:
        # We'll set these in the active profile
        pass

    if long_only is not None:
        mu["long_only"] = long_only
        mu.setdefault("params", {})["long_only"] = long_only

    # Trading hours
    if trading_hours is not None:
        mu["trading_hours"] = trading_hours
        mu["time_filter_enabled"] = True

    # Exit params
    params = mu.setdefault("params", {})
    if atr_stop_multiplier is not None:
        params["atr_stop_multiplier"] = atr_stop_multiplier
    if rr_ratio is not None:
        params["rr_ratio"] = rr_ratio
    if trailing_stop_pct is not None:
        params["trailing_stop_pct"] = trailing_stop_pct
        mu["trailing_stop_pct"] = trailing_stop_pct

    # Build the full config with only MU
    result = copy.deepcopy(aos)
    result["tickers"] = {"MU": mu}

    return result


def write_temp_aos(config: Dict[str, Any], label: str = "") -> str:
    """Write AOS config to a temp file and return the path."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = REPORTS_DIR / "tmp_aos"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    safe_label = label.replace("/", "_").replace(" ", "_")[:30]
    path = tmp_dir / f"aos_{safe_label}_{uuid.uuid4().hex[:8]}.json"
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return str(path)


# ── Single-day runner (HTTP API) ─────────────────────────────────────────────

async def run_single_day(
    client: httpx.AsyncClient,
    date: str,
    *,
    aos_config_path: Optional[str] = None,
    run_label: str = "",
    l2_only: bool = True,
    l2_confirm_enabled: bool = True,
    comparable_mode: bool = True,
    diagnostic_mode: bool = False,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """Run a single-day backtest and return the summary."""
    run_id = f"diag_{uuid.uuid4().hex[:12]}"

    request_body = {
        "run_id": run_id,
        "ticker": TICKER,
        "date": date,
        "strategy_api_url": STRATEGY_API_URL,
        "l2_only": l2_only,
        "l2_confirm_enabled": l2_confirm_enabled,
        "comparable_mode": comparable_mode,
        "apply_ticker_overrides_on_start": False,
        "apply_positioning_config_on_start": False,
        "apply_aos_optimizations_on_start": True,
        "account_size_usd": 10000.0,
        "risk_per_trade_pct": 1.0,
    }

    if aos_config_path:
        request_body["aos_config_path"] = aos_config_path

    async def cleanup() -> None:
        try:
            await client.delete(
                f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date}",
                timeout=5.0,
            )
        except Exception:
            pass

    # Start the run (L2 data loading for MU can take >60s with 68 daily parquet files)
    try:
        resp = await client.post(
            f"{RUNNER_API_URL}/api/run/start",
            json=request_body,
            timeout=300.0,
        )
        if resp.status_code != 200:
            return {
                "date": date,
                "success": False,
                "stage": "start",
                "error": f"start failed: {resp.status_code} {safe_text(resp.text)}",
            }
        start_data = resp.json()
    except Exception as e:
        return {
            "date": date,
            "success": False,
            "stage": "start",
            "error": f"start exception: {type(e).__name__}: {safe_text(e)}",
        }

    run_key = start_data.get("run_key", "")
    diagnostic_funnel = init_funnel()
    step_errors: List[str] = []

    # Run session either with detailed stepping (for diagnostics) or play mode.
    if diagnostic_mode:
        total_bars = int(start_data.get("total_bars", 0) or 0)
        max_steps = max(total_bars + 5, 10)
        completed = False
        for _ in range(max_steps):
            try:
                step_resp = await client.post(
                    f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date}/step",
                    timeout=30.0,
                )
            except Exception as exc:
                step_errors.append(f"step exception: {type(exc).__name__}: {safe_text(exc)}")
                break

            if step_resp.status_code != 200:
                step_errors.append(f"step failed: {step_resp.status_code} {safe_text(step_resp.text)}")
                break

            step_payload = step_resp.json()
            if not step_payload.get("success", False):
                if step_payload.get("phase") == "COMPLETED":
                    completed = True
                    break
                step_errors.append(
                    f"step returned non-success: phase={step_payload.get('phase')} "
                    f"error={safe_text(step_payload.get('error'))}"
                )
                break

            update_funnel(diagnostic_funnel, step_payload.get("response") or {})

        if not completed and not step_errors:
            step_errors.append("step loop did not reach COMPLETED phase before max_steps")
        if step_errors:
            await cleanup()
            return {
                "date": date,
                "success": False,
                "stage": "step",
                "error": safe_text("; ".join(step_errors), limit=500),
            }
    else:
        # Brief pause to let run initialize
        await asyncio.sleep(0.3)
        try:
            play_resp = await client.post(
                f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date}/play",
                json={"speed_ms": "max"},
                timeout=15.0,
            )
            if play_resp.status_code != 200:
                await cleanup()
                return {
                    "date": date,
                    "success": False,
                    "stage": "play",
                    "error": f"play failed: {play_resp.status_code} {safe_text(play_resp.text)}",
                }
        except Exception as e:
            await cleanup()
            return {
                "date": date,
                "success": False,
                "stage": "play",
                "error": f"play exception: {type(e).__name__}: {safe_text(e)}",
            }

        poll_interval = 0.5
        elapsed = 0.0
        completed = False
        while elapsed < timeout_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            try:
                state_resp = await client.get(
                    f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date}/state",
                    timeout=10.0,
                )
                if state_resp.status_code == 200:
                    state = state_resp.json()
                    phase = state.get("phase", "")
                    if phase == "COMPLETED":
                        completed = True
                        break
                    if not state.get("is_running", True) and phase != "INITIALIZED":
                        completed = True
                        break
            except Exception:
                pass

        if not completed:
            await cleanup()
            return {"date": date, "success": False, "stage": "play", "error": "timeout"}

    # Get summary
    summary_data = {}
    try:
        summary_resp = await client.get(
            f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date}/summary",
            timeout=10.0,
        )
        if summary_resp.status_code == 200:
            summary_data = summary_resp.json()
        else:
            await cleanup()
            return {
                "date": date,
                "success": False,
                "stage": "summary",
                "error": f"summary failed: {summary_resp.status_code} {safe_text(summary_resp.text)}",
            }
    except Exception as e:
        await cleanup()
        return {
            "date": date,
            "success": False,
            "stage": "summary",
            "error": f"summary exception: {type(e).__name__}: {safe_text(e)}",
        }

    # Clean up the run
    await cleanup()

    # Extract metrics
    session = summary_data.get("session_summary") or {}
    markers = summary_data.get("markers", [])
    total_bars = summary_data.get("total_bars", 0)
    processed_bars = summary_data.get("processed_bars", 0)

    # Marker counts
    signal_count = sum(1 for m in markers if m.get("marker_type") == "signal_generated")
    entry_count = sum(1 for m in markers if m.get("marker_type") == "entry_executed")
    exit_count = sum(1 for m in markers if m.get("marker_type") == "exit_executed")
    regime_count = sum(1 for m in markers if m.get("marker_type") == "regime_detected")

    # Trade details for MFE/MAE
    trades = session.get("trades", [])
    mfe_values = []
    mae_values = []
    for trade in trades:
        entry_price = float(trade.get("entry_price", 0) or 0)
        if entry_price <= 0:
            continue
        side = str(trade.get("side", "")).lower()
        # MFE/MAE from trade-level data if available
        mfe = float(trade.get("mfe_pct", 0) or 0)
        mae = float(trade.get("mae_pct", 0) or 0)
        if mfe > 0:
            mfe_values.append(mfe)
        if mae != 0:
            mae_values.append(abs(mae))

    # Fallback when marker pipeline is sparse: use step funnel counts.
    step_signal_candidates = int(diagnostic_funnel.get("candidates_generated", 0))
    step_trades = int(diagnostic_funnel.get("trades_placed", 0))
    step_regime_actions = int((diagnostic_funnel.get("actions") or {}).get("regime_detected", 0))

    signal_count_effective = signal_count if signal_count > 0 else step_signal_candidates
    entry_count_effective = entry_count if entry_count > 0 else step_trades
    regime_count_effective = regime_count if regime_count > 0 else step_regime_actions

    aos_applied = start_data.get("aos_applied", {}) if isinstance(start_data.get("aos_applied"), dict) else {}
    adaptive_profile_meta = (
        aos_applied.get("adaptive_profile", {})
        if isinstance(aos_applied.get("adaptive_profile"), dict)
        else {}
    )
    strategy_combo_meta = (
        aos_applied.get("strategy_combo", {})
        if isinstance(aos_applied.get("strategy_combo"), dict)
        else {}
    )

    result = {
        "date": date,
        "success": True,
        "total_bars": total_bars,
        "processed_bars": processed_bars,
        "signals": signal_count_effective,
        "signals_markers": signal_count,
        "signals_step": step_signal_candidates,
        "entries": entry_count_effective,
        "entries_markers": entry_count,
        "entries_step": step_trades,
        "exits": exit_count,
        "regime_evaluations": regime_count_effective,
        "regime_evaluations_markers": regime_count,
        "total_trades": int(session.get("total_trades", 0) or 0) if session else step_trades,
        "winning_trades": int(session.get("winning_trades", 0) or 0),
        "losing_trades": int(session.get("losing_trades", 0) or 0),
        "win_rate": float(session.get("win_rate", 0) or 0),
        "pnl_pct": float(session.get("total_pnl_pct", 0) or 0),
        "pnl_dollars": float(session.get("total_pnl_dollars", 0) or 0),
        "l2_avg_score": float(session.get("l2_avg_confirmation_score", 0) or 0),
        "regime": session.get("regime"),
        "strategy": session.get("strategy"),
        "regime_breakdown": session.get("regime_trade_breakdown", {}),
        "mfe_avg": round(sum(mfe_values) / len(mfe_values), 4) if mfe_values else 0.0,
        "mae_avg": round(sum(mae_values) / len(mae_values), 4) if mae_values else 0.0,
        "trade_details": trades,
        "diagnostic_funnel": diagnostic_funnel,
        "l2_applied": start_data.get("l2_applied", {}),
        "execution_config": start_data.get("execution_config", {}),
        "aos_applied": aos_applied,
        "adaptive_profile_id": adaptive_profile_meta.get("active_profile_id") or adaptive_profile_meta.get("profile_id"),
        "adaptive_profile_name": adaptive_profile_meta.get("profile_name"),
        "strategy_combo_profile_id": strategy_combo_meta.get("active_profile_id"),
        "strategy_combo_profile_name": strategy_combo_meta.get("profile_name"),
        "run_key": run_key,
    }
    return result


async def run_days(
    dates: List[str],
    *,
    aos_config_path: Optional[str] = None,
    label: str = "",
    progress_prefix: str = "",
    diagnostic_mode: bool = False,
) -> List[Dict[str, Any]]:
    """Run multiple days sequentially and return results."""
    results = []
    if not dates:
        return results
    async with httpx.AsyncClient() as client:
        # Health check
        try:
            health = await client.get(f"{RUNNER_API_URL}/api/health", timeout=5.0)
            if health.status_code != 200:
                print(f"  ERROR: Runner API not healthy (status {health.status_code})")
                return []
        except Exception as e:
            print(f"  ERROR: Cannot connect to runner API: {e}")
            return []

        for i, date in enumerate(dates):
            prefix = f"  [{progress_prefix}] " if progress_prefix else "  "
            print(f"{prefix}{i+1}/{len(dates)} {date}", end="", flush=True)

            result = await run_single_day(
                client, date,
                aos_config_path=aos_config_path,
                run_label=label,
                diagnostic_mode=diagnostic_mode,
            )
            results.append(result)

            if result["success"]:
                trades = result["total_trades"]
                pnl = result["pnl_pct"]
                if diagnostic_mode:
                    funnel = result.get("diagnostic_funnel", {})
                    rej = int(funnel.get("candidates_rejected", 0))
                    print(f"  trades={trades} pnl={pnl:+.2f}% rejected={rej}")
                else:
                    print(f"  trades={trades} pnl={pnl:+.2f}%")
            else:
                stage = result.get("stage", "unknown")
                print(f"  FAILED[{stage}]: {result.get('error', 'unknown')}")

    return results


async def run_multi_day_probe(
    dates: List[str],
    *,
    aos_config_path: Optional[str] = None,
    stop_on_first_candidate: bool = True,
) -> Dict[str, Any]:
    """
    A/B probe: run one continuous multi-day session and inspect step-level funnel.

    This helps distinguish per-day cold-start artifacts from true gating/logic issues.
    """
    if not dates:
        return {"success": False, "error": "no dates for probe"}

    date_from = min(dates)
    date_to = max(dates)
    run_id = f"diag_multiday_{uuid.uuid4().hex[:10]}"
    funnel = init_funnel()

    request_body = {
        "run_id": run_id,
        "ticker": TICKER,
        "date_from": date_from,
        "date_to": date_to,
        "strategy_api_url": STRATEGY_API_URL,
        "l2_only": True,
        "l2_confirm_enabled": True,
        "comparable_mode": False,  # keep continuous state for A/B disambiguation
        "cold_start_each_day": False,
        "apply_ticker_overrides_on_start": False,
        "apply_positioning_config_on_start": False,
        "apply_aos_optimizations_on_start": True,
        "account_size_usd": 10000.0,
        "risk_per_trade_pct": 1.0,
    }
    if aos_config_path:
        request_body["aos_config_path"] = aos_config_path

    async with httpx.AsyncClient() as client:
        try:
            start_resp = await client.post(
                f"{RUNNER_API_URL}/api/run/start",
                json=request_body,
                timeout=60.0,
            )
        except Exception as exc:
            return {
                "success": False,
                "error": f"multi-day start exception: {type(exc).__name__}: {safe_text(exc)}",
            }
        if start_resp.status_code != 200:
            return {
                "success": False,
                "error": f"multi-day start failed: {start_resp.status_code} {safe_text(start_resp.text)}",
            }

        start_data = start_resp.json()
        total_bars = int(start_data.get("total_bars", 0) or 0)
        max_steps = max(total_bars + 5, 20)
        completed = False
        early_stop_reason = None

        try:
            for _ in range(max_steps):
                date_label = f"{date_from}_to_{date_to}"
                step_resp = await client.post(
                    f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date_label}/step",
                    timeout=30.0,
                )
                if step_resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"multi-day step failed: {step_resp.status_code} {safe_text(step_resp.text)}",
                    }
                step_data = step_resp.json()
                if not step_data.get("success", False):
                    if step_data.get("phase") == "COMPLETED":
                        completed = True
                        break
                    return {
                        "success": False,
                        "error": (
                            f"multi-day step non-success: phase={step_data.get('phase')} "
                            f"error={safe_text(step_data.get('error'))}"
                        ),
                    }

                update_funnel(funnel, step_data.get("response") or {})
                if stop_on_first_candidate and (
                    int(funnel.get("candidates_generated", 0)) > 0
                    or int(funnel.get("trades_placed", 0)) > 0
                ):
                    early_stop_reason = "first_candidate_or_trade"
                    break
        finally:
            try:
                date_label = f"{date_from}_to_{date_to}"
                await client.delete(
                    f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date_label}",
                    timeout=5.0,
                )
            except Exception:
                pass

    return {
        "success": True,
        "date_from": date_from,
        "date_to": date_to,
        "total_bars": total_bars,
        "completed": completed,
        "early_stop_reason": early_stop_reason,
        "diagnostic_funnel": funnel,
    }


# ── Metrics ──────────────────────────────────────────────────────────────────

def compute_day_metrics(day_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate metrics from day-level results."""
    valid = [d for d in day_results if d.get("success")]
    if not valid:
        return {"valid_days": 0, "total_days": len(day_results)}

    total_trades = sum(d["total_trades"] for d in valid)
    total_pnl_pct = sum(d["pnl_pct"] for d in valid)
    total_pnl_dollars = sum(d["pnl_dollars"] for d in valid)
    days_with_trades = sum(1 for d in valid if d["total_trades"] > 0)
    winning_days = sum(1 for d in valid if d["pnl_dollars"] > 0)

    pnl_values = [d["pnl_pct"] for d in valid]
    mean_pnl = total_pnl_pct / len(valid)
    if len(valid) > 1:
        variance = sum((p - mean_pnl) ** 2 for p in pnl_values) / (len(valid) - 1)
        std_pnl = variance ** 0.5
    else:
        std_pnl = 0.0

    # Max drawdown (day-level)
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for d in valid:
        running += d["pnl_dollars"]
        peak = max(peak, running)
        max_dd = max(max_dd, peak - running)

    # Participation = fraction of days with at least 1 trade
    participation = days_with_trades / len(valid) if valid else 0.0

    # Selectivity = avg trades per trading day (lower = more selective)
    selectivity = total_trades / days_with_trades if days_with_trades > 0 else 0.0

    return {
        "valid_days": len(valid),
        "total_days": len(day_results),
        "total_trades": total_trades,
        "days_with_trades": days_with_trades,
        "participation": round(participation, 4),
        "selectivity": round(selectivity, 2),
        "winning_days": winning_days,
        "total_pnl_pct": round(total_pnl_pct, 4),
        "total_pnl_dollars": round(total_pnl_dollars, 2),
        "mean_daily_pnl_pct": round(mean_pnl, 4),
        "std_daily_pnl_pct": round(std_pnl, 4),
        "max_drawdown_dollars": round(max_dd, 2),
        "win_rate_days": round(winning_days / len(valid) * 100, 1) if valid else 0.0,
    }


def compute_variant_score(metrics: Dict[str, Any]) -> float:
    """
    Score = PnL_z + 0.5*participation_z + 0.5*selectivity_z - drawdown_penalty

    Hard constraints (return -inf):
    - participation < 0.02
    - max_drawdown > 50% of account
    - total_trades < 1
    """
    participation = metrics.get("participation", 0)
    total_trades = metrics.get("total_trades", 0)
    max_dd = metrics.get("max_drawdown_dollars", 0)

    # Hard constraints
    if participation < 0.02:
        return float("-inf")
    if max_dd > 5000:  # 50% of $10k account
        return float("-inf")
    if total_trades < 1:
        return float("-inf")

    pnl = metrics.get("total_pnl_pct", 0)
    selectivity = metrics.get("selectivity", 0)
    std_pnl = metrics.get("std_daily_pnl_pct", 1)

    # Normalize (z-scores relative to self — will be re-normalized across variants)
    pnl_z = pnl / max(std_pnl, 0.01)
    participation_z = (participation - 0.3) / 0.2  # centered at 30%, scale 20%
    # Lower selectivity is better (fewer trades per day = more selective)
    selectivity_z = (2.0 - selectivity) / 1.0  # centered at 2 trades/day

    # Drawdown penalty: proportional to max drawdown as fraction of total PnL
    dd_penalty = 0.0
    if pnl > 0 and max_dd > 0:
        dd_ratio = max_dd / max(abs(metrics.get("total_pnl_dollars", 1)), 1)
        dd_penalty = max(0, dd_ratio - 1.0) * 2.0  # penalize if dd > total pnl

    score = pnl_z + 0.5 * participation_z + 0.5 * selectivity_z - dd_penalty
    return round(score, 4)


# ── Bootstrap CI ─────────────────────────────────────────────────────────────

def bootstrap_ci(
    day_results: List[Dict[str, Any]],
    metric_fn,
    n_boot: int = 1000,
    ci: float = 0.95,
) -> Tuple[float, float, float]:
    """Day-level bootstrap confidence interval. Returns (mean, ci_low, ci_high)."""
    if len(day_results) < 3:
        val = metric_fn(day_results)
        return (val, val, val)

    random.seed(42)
    boot_values = []
    for _ in range(n_boot):
        sample = random.choices(day_results, k=len(day_results))
        boot_values.append(metric_fn(sample))

    boot_values.sort()
    alpha = (1.0 - ci) / 2.0
    lo_idx = max(0, int(alpha * n_boot))
    hi_idx = min(n_boot - 1, int((1.0 - alpha) * n_boot))
    mean_val = sum(boot_values) / len(boot_values)
    return (round(mean_val, 4), round(boot_values[lo_idx], 4), round(boot_values[hi_idx], 4))


def pnl_metric(days):
    return sum(d.get("pnl_pct", 0) for d in days if d.get("success"))


def trades_metric(days):
    return sum(d.get("total_trades", 0) for d in days if d.get("success"))


# ── Phase 0: Diagnostic ─────────────────────────────────────────────────────

async def phase0_diagnostic() -> Dict[str, Any]:
    """Run baseline on tuning dates, classify each day's pipeline."""
    print("=" * 80)
    print("PHASE 0 — DIAGNOSTIC (baseline on tuning set)")
    print("=" * 80)
    print(f"Split: {TUNING_START} to {TUNING_END} ({len(TUNING_DATES)} weekdays)")
    print()

    async with httpx.AsyncClient() as client:
        try:
            fast_mode_result = await apply_fast_mode(client)
            runtime = fast_mode_result.get("runtime", {})
            print(
                "Fast mode ON:"
                f" icebergs={runtime.get('iceberg_detection_enabled')}"
                f" cache_rows={runtime.get('cache_max_rows')}"
                f" cache_bytes={runtime.get('cache_max_bytes')}"
            )
        except Exception as exc:
            print(f"WARNING: Could not apply fast mode on runner: {safe_text(exc)}")
        coverage = await resolve_dataset_dates(
            client,
            TUNING_START,
            TUNING_END,
            require_l2=True,
        )

    available_dates = coverage["available_days"]
    missing_ohlcv = coverage["missing_ohlcv_days"]
    missing_l2 = coverage["missing_l2_days"]
    missing_overlap = coverage["missing_overlap_days"]

    print(f"Dataset-driven dates: {len(available_dates)} / {len(coverage['weekdays'])} weekdays usable")
    if missing_ohlcv:
        print(f"  Missing OHLCV days ({len(missing_ohlcv)}): {summarize_days(missing_ohlcv)}")
    if missing_l2:
        print(f"  Missing L2 days ({len(missing_l2)}): {summarize_days(missing_l2)}")
    if not available_dates:
        print("\nERROR: No dates with OHLCV+L2 overlap in tuning split.")
        result = {
            "phase": 0,
            "status": "error",
            "reason": "no_dataset_overlap",
            "split": {"start": TUNING_START, "end": TUNING_END},
            "coverage": coverage,
            "valid_days": 0,
        }
        save_report("phase0_diagnostic.json", result)
        return result

    print()
    day_results = await run_days(
        available_dates,
        label="baseline",
        progress_prefix="P0",
        diagnostic_mode=True,
    )

    valid_days = [d for d in day_results if d.get("success")]
    if not valid_days:
        print("\nERROR: No valid days. Check server connection.")
        result = {
            "phase": 0,
            "status": "error",
            "reason": "no_successful_days",
            "split": {"start": TUNING_START, "end": TUNING_END},
            "coverage": coverage,
            "valid_days": 0,
            "day_results": day_results,
        }
        save_report("phase0_diagnostic.json", result)
        return result

    # Classify days
    days_no_signals = []
    days_signals_no_trades = []
    days_with_trades = []
    incomplete_days = []
    reject_by_gate: Counter = Counter()
    reject_by_reason: Counter = Counter()
    no_candidate_by_reason: Counter = Counter()
    bar_funnel_totals: Counter = Counter()

    for d in valid_days:
        funnel = d.get("diagnostic_funnel", {})
        candidates = int(funnel.get("candidates_generated", 0))
        trades_placed = int(funnel.get("trades_placed", 0))
        total_trades = int(d.get("total_trades", 0) or 0)
        effective_trades = max(total_trades, trades_placed)
        bars_processed = int(funnel.get("bars_processed", 0))
        expected_bars = int(d.get("total_bars", 0) or 0)
        if expected_bars > 0 and bars_processed < expected_bars:
            incomplete_days.append(
                {
                    "date": d["date"],
                    "bars_processed": bars_processed,
                    "total_bars": expected_bars,
                }
            )

        bar_funnel_totals["bars_processed"] += bars_processed
        bar_funnel_totals["strategies_evaluated"] += int(funnel.get("strategies_evaluated", 0))
        bar_funnel_totals["candidates_generated"] += candidates
        bar_funnel_totals["candidates_rejected"] += int(funnel.get("candidates_rejected", 0))
        bar_funnel_totals["evidence_passed"] += int(funnel.get("evidence_passed", 0))
        bar_funnel_totals["trades_placed"] += trades_placed

        reject_by_gate.update(funnel.get("reject_by_gate", {}))
        reject_by_reason.update(funnel.get("reject_by_reason", {}))
        no_candidate_by_reason.update(funnel.get("no_candidate_by_reason", {}))

        if candidates == 0 and effective_trades == 0:
            days_no_signals.append(d)
        elif candidates > 0 and effective_trades == 0:
            days_signals_no_trades.append(d)
        else:
            days_with_trades.append(d)

    # Day-level funnel summary
    total = len(valid_days)
    print(f"\n{'─' * 60}")
    print("SIGNAL FUNNEL (day-level)")
    print(f"{'─' * 60}")
    print(f"  Total valid days:           {total}")
    print(f"  Days with 0 signals:        {len(days_no_signals)} ({len(days_no_signals)/total*100:.0f}%)")
    print(f"  Days with signals, 0 trades: {len(days_signals_no_trades)} ({len(days_signals_no_trades)/total*100:.0f}%)")
    print(f"  Days with trades:           {len(days_with_trades)} ({len(days_with_trades)/total*100:.0f}%)")
    print(f"  Missing overlap days:       {len(missing_overlap)}")

    # Bar-level funnel summary
    print(f"\n{'─' * 60}")
    print("SIGNAL FUNNEL (bar-level)")
    print(f"{'─' * 60}")
    print(f"  Bars processed:             {bar_funnel_totals['bars_processed']}")
    print(f"  Strategies evaluated:       {bar_funnel_totals['strategies_evaluated']}")
    print(f"  Candidates generated:       {bar_funnel_totals['candidates_generated']}")
    print(f"  Candidates rejected:        {bar_funnel_totals['candidates_rejected']}")
    print(f"  Evidence passed:            {bar_funnel_totals['evidence_passed']}")
    print(f"  Trades placed:              {bar_funnel_totals['trades_placed']}")
    if reject_by_gate:
        top_gates = ", ".join(f"{k}:{v}" for k, v in reject_by_gate.most_common(6))
        print(f"  Top reject gates:           {top_gates}")
    if no_candidate_by_reason:
        top_no_candidate = ", ".join(
            f"{k}:{v}" for k, v in no_candidate_by_reason.most_common(6)
        )
        print(f"  No-candidate reasons:       {top_no_candidate}")
    if incomplete_days:
        print(f"  Incomplete day runs:        {len(incomplete_days)}")
        incomplete_tokens = [
            f"{row['date']}({row['bars_processed']}/{row['total_bars']})"
            for row in incomplete_days
        ]
        print(
            f"    {summarize_days(incomplete_tokens, max_items=8)}"
        )

    # Aggregate metrics
    metrics = compute_day_metrics(day_results)
    print(f"\n{'─' * 60}")
    print("AGGREGATE METRICS")
    print(f"{'─' * 60}")
    print(f"  Total trades:    {metrics['total_trades']}")
    print(f"  Total PnL:       {metrics['total_pnl_pct']:+.2f}% (${metrics['total_pnl_dollars']:+.2f})")
    print(f"  Participation:   {metrics['participation']*100:.0f}%")
    print(f"  Selectivity:     {metrics['selectivity']:.1f} trades/trading-day")
    print(f"  Max drawdown:    ${metrics['max_drawdown_dollars']:.2f}")

    # Signal candidate days (those with signals generated OR trades)
    candidate_days = len(days_signals_no_trades) + len(days_with_trades)

    # Sanity gate + A/B disambiguation
    abort = candidate_days < 2
    ab_probe = None
    if abort:
        print(f"\n*** ABORT_ABLATION: Only {candidate_days} days produce candidate signals.")
        print("    Investigate strategy logic before proceeding to Phase 1.")

        # A/B check: single-day cold-start vs one continuous multi-day run.
        print("\n  Running A/B probe: single-day vs one multi-day continuous session...")
        ab_probe = await run_multi_day_probe(available_dates, stop_on_first_candidate=True)
        if ab_probe.get("success"):
            probe_funnel = ab_probe.get("diagnostic_funnel", {})
            probe_candidates = int(probe_funnel.get("candidates_generated", 0))
            probe_trades = int(probe_funnel.get("trades_placed", 0))
            print(
                "  Multi-day probe:"
                f" candidates={probe_candidates}"
                f" trades={probe_trades}"
                f" early_stop={ab_probe.get('early_stop_reason')}"
            )
            if probe_candidates > 0 or probe_trades > 0:
                print("  Inference: per-day cold-start/reset likely suppresses candidates.")
            else:
                print("  Inference: issue is likely in gating/preconditions/feature mapping, not reset semantics.")
        else:
            print(f"  Multi-day probe failed: {ab_probe.get('error', 'unknown')}")
    else:
        print(f"\n  Sanity gate PASSED: {candidate_days} days with candidate signals (>= 2 required)")

    # Day-by-day table
    print(f"\n{'─' * 60}")
    print("DAY-BY-DAY RESULTS")
    print(f"{'─' * 60}")
    print(
        f"  {'Date':<12} {'Bars':>9} {'Cand':>5} {'Rej':>5} {'Pass':>5} "
        f"{'Trades':>6} {'PnL%':>8} {'Gate(top)'}"
    )
    for d in valid_days:
        funnel = d.get("diagnostic_funnel", {})
        cand = int(funnel.get("candidates_generated", 0))
        rej = int(funnel.get("candidates_rejected", 0))
        passed = int(funnel.get("evidence_passed", 0))
        bars_done = int(funnel.get("bars_processed", 0))
        bars_total = int(d.get("total_bars", 0) or 0)
        gate_counts = funnel.get("reject_by_gate", {}) or {}
        top_gate = sorted(gate_counts.items(), key=lambda x: (-x[1], x[0]))[0][0] if gate_counts else "-"
        if cand > 0 or rej > 0 or d["total_trades"] > 0:
            print(
                f"  {d['date']:<12} {bars_done:>4}/{bars_total:<4} {cand:>5} {rej:>5} {passed:>5} "
                f"{d['total_trades']:>6} {d['pnl_pct']:>+8.2f} {top_gate}"
            )

    result = {
        "phase": 0,
        "status": "abort" if abort else "pass",
        "split": {"start": TUNING_START, "end": TUNING_END},
        "coverage": coverage,
        "dates_used": available_dates,
        "funnel": {
            "total_valid_days": total,
            "days_no_signals": len(days_no_signals),
            "days_signals_no_trades": len(days_signals_no_trades),
            "days_with_trades": len(days_with_trades),
            "candidate_days": candidate_days,
            "bar_level": {
                "bars_processed": int(bar_funnel_totals["bars_processed"]),
                "strategies_evaluated": int(bar_funnel_totals["strategies_evaluated"]),
                "candidates_generated": int(bar_funnel_totals["candidates_generated"]),
                "candidates_rejected": int(bar_funnel_totals["candidates_rejected"]),
                "evidence_passed": int(bar_funnel_totals["evidence_passed"]),
                "trades_placed": int(bar_funnel_totals["trades_placed"]),
            },
            "reject_by_gate": dict(reject_by_gate),
            "reject_by_reason": dict(reject_by_reason),
            "no_candidate_by_reason": dict(no_candidate_by_reason),
        },
        "ab_probe": ab_probe,
        "metrics": metrics,
        "day_results": day_results,
    }

    save_report("phase0_diagnostic.json", result)
    return result


# ── Phase 1: Ablation ───────────────────────────────────────────────────────

def build_ablation_variants() -> Dict[str, Dict[str, Any]]:
    """
    Build 5 ablation variants.

    Each variant has:
      - "aos": full AOS config (L2 thresholds, min_confidence, regime_filter, etc.)
      - "orch": orchestrator overrides sent to POST /api/orchestrator/config
                (base_threshold, min_confirming_sources, margins)

    Phase 0 diagnosis:
      - threshold gate = 90.5% of rejections (base_threshold + dynamic penalties + margins)
      - mu_choppy_filter = 9.4% (hard-coded CHOPPY regime block)
      - ensemble scores land at 46-57, dynamic effective threshold at 45-60
      - margin requirements: 5 (multi-source), 10 (single-source) on top of threshold

    Variant design (isolation principle — one axis at a time):
      A = baseline (current settings, produces ~0 trades)
      B = lower base_threshold + margins only (orchestrator-level)
      C = B + lower min_confidence (strategy-level, generates more raw signals)
      D = B + C + relax L2 gates (data-level)
      E = D + allow CHOPPY regime + wider hours (regime/time-level)
    """
    baseline_aos = load_baseline_aos()
    # Orchestrator defaults: base_threshold=42, min_confirming=2,
    # min_margin=5, single_source_margin=10
    baseline_orch = {
        "base_threshold": 42.0,
        "min_confirming_sources": 2,
        "min_margin_over_threshold": 5.0,
        "single_source_min_margin": 10.0,
    }

    variants = {}

    # A: Baseline — current config, no changes
    variants["A_baseline"] = {
        "aos": baseline_aos,
        "orch": baseline_orch,
    }

    # B: Relax threshold + margins only (orchestrator-level)
    # Lower base_threshold from 42→30, margins from 5/10→2/5
    # Expected: ensemble scores of 46-57 now clear threshold of 30+dynamic(3-18)=33-48
    # With margin=2, a score of 50 vs threshold 48 passes
    variants["B_relax_thresh"] = {
        "aos": baseline_aos,
        "orch": {
            "base_threshold": 30.0,
            "min_confirming_sources": 2,
            "min_margin_over_threshold": 2.0,
            "single_source_min_margin": 5.0,
        },
    }

    # C: B + lower min_confidence (strategy-level)
    # More raw strategy signals feed into the ensemble → higher ensemble scores
    variants["C_thresh_conf"] = {
        "aos": build_variant_aos("C_thresh_conf", min_confidence=45.0),
        "orch": {
            "base_threshold": 30.0,
            "min_confirming_sources": 2,
            "min_margin_over_threshold": 2.0,
            "single_source_min_margin": 5.0,
        },
    }

    # D: C + relax L2 gates (data-level)
    # Lower L2 thresholds so more L2 confirmations pass
    variants["D_full_relax"] = {
        "aos": build_variant_aos(
            "D_full_relax",
            min_confidence=45.0,
            l2_min_delta=1500.0,
            l2_min_imbalance=0.03,
            l2_min_signed_aggression=0.03,
            l2_min_directional_consistency=0.2,
        ),
        "orch": {
            "base_threshold": 30.0,
            "min_confirming_sources": 1,
            "min_margin_over_threshold": 2.0,
            "single_source_min_margin": 5.0,
        },
    }

    # E: D + CHOPPY regime allowed + wider hours + moderate threshold
    # Recovers 544 mu_choppy_filter rejections; slightly higher threshold for safety
    variants["E_wide_net"] = {
        "aos": build_variant_aos(
            "E_wide_net",
            min_confidence=45.0,
            l2_min_delta=1500.0,
            l2_min_imbalance=0.03,
            l2_min_signed_aggression=0.03,
            l2_min_directional_consistency=0.2,
            regime_filter=["TRENDING", "MIXED", "CHOPPY"],
            trading_hours=[9, 10, 11, 12, 13, 14],
        ),
        "orch": {
            "base_threshold": 35.0,
            "min_confirming_sources": 1,
            "min_margin_over_threshold": 2.0,
            "single_source_min_margin": 5.0,
        },
    }

    return variants


async def phase1_ablation(
    phase0_result: Optional[Dict] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Run ablation variants on tuning set only."""
    # Check Phase 0 gate
    if phase0_result is None:
        phase0_path = REPORTS_DIR / "phase0_diagnostic.json"
        if phase0_path.exists():
            with open(phase0_path) as f:
                phase0_result = json.load(f)

    if phase0_result and phase0_result.get("status") == "abort" and not force:
        print("SKIPPING Phase 1: Phase 0 sanity gate failed (ABORT_ABLATION)")
        print("  Use --force to override after investigating the gating logic.")
        return {"phase": 1, "status": "aborted", "reason": "phase0_sanity_gate_failed"}

    if phase0_result and phase0_result.get("status") == "abort" and force:
        print("WARNING: Phase 0 sanity gate failed — proceeding with --force")
        print("  Ablation variants are specifically designed to relax the blocking gates.")

    tuning_dates = []
    if isinstance(phase0_result, dict):
        maybe_dates = phase0_result.get("dates_used", [])
        if isinstance(maybe_dates, list):
            tuning_dates = [str(day) for day in maybe_dates if str(day).strip()]
    tuning_coverage = None
    if not tuning_dates:
        async with httpx.AsyncClient() as client:
            tuning_coverage = await resolve_dataset_dates(
                client,
                TUNING_START,
                TUNING_END,
                require_l2=True,
            )
        tuning_dates = tuning_coverage.get("available_days", [])
    if not tuning_dates:
        print("ERROR: No tuning dates with OHLCV+L2 overlap.")
        return {"phase": 1, "status": "error", "reason": "no_tuning_dates"}

    async with httpx.AsyncClient() as client:
        try:
            fast_mode_result = await apply_fast_mode(client)
            runtime = fast_mode_result.get("runtime", {})
            print(
                "Fast mode ON:"
                f" icebergs={runtime.get('iceberg_detection_enabled')}"
                f" cache_rows={runtime.get('cache_max_rows')}"
                f" cache_bytes={runtime.get('cache_max_bytes')}"
            )
        except Exception as exc:
            print(f"WARNING: Could not apply fast mode on runner: {safe_text(exc)}")

    print("\n" + "=" * 80)
    print("PHASE 1 — ABLATION (5 variants on tuning set)")
    print("=" * 80)
    print(f"Dates: {min(tuning_dates)} to {max(tuning_dates)} ({len(tuning_dates)} days)")

    variants = build_ablation_variants()
    variant_results = {}

    for variant_id, variant_spec in variants.items():
        aos_config = variant_spec["aos"]
        orch_overrides = variant_spec.get("orch", {})

        print(f"\n{'─' * 60}")
        print(f"Variant: {variant_id}")
        if orch_overrides:
            orch_summary = ", ".join(f"{k}={v}" for k, v in orch_overrides.items())
            print(f"  Orchestrator: {orch_summary}")
        print(f"{'─' * 60}")

        # Write temp AOS config
        aos_path = write_temp_aos(aos_config, variant_id)

        try:
            # Push orchestrator overrides to the strategy API BEFORE running days.
            # This sets base_threshold, min_confirming_sources, and margin
            # requirements directly on the ensemble combiner/evidence engine.
            if orch_overrides:
                async with httpx.AsyncClient() as client:
                    orch_result = await set_orchestrator_config(client, **orch_overrides)
                    print(f"  Orchestrator config applied: {orch_result.get('updated', {})}")

            day_results = await run_days(
                tuning_dates,
                aos_config_path=aos_path,
                label=variant_id,
                progress_prefix=variant_id[:6],
            )

            metrics = compute_day_metrics(day_results)
            score = compute_variant_score(metrics)

            # Bootstrap CI on PnL
            valid_days = [d for d in day_results if d.get("success")]
            pnl_ci = bootstrap_ci(valid_days, pnl_metric) if valid_days else (0, 0, 0)

            variant_results[variant_id] = {
                "metrics": metrics,
                "score": score,
                "pnl_ci_95": {"mean": pnl_ci[0], "lo": pnl_ci[1], "hi": pnl_ci[2]},
                "orch_overrides": orch_overrides,
                "day_results": day_results,
            }

            print(f"\n  Score: {score:.4f}")
            print(f"  PnL:   {metrics['total_pnl_pct']:+.2f}% (${metrics['total_pnl_dollars']:+.2f})")
            print(f"  95% CI: [{pnl_ci[1]:+.2f}%, {pnl_ci[2]:+.2f}%]")
            print(f"  Trades: {metrics['total_trades']}, Participation: {metrics['participation']*100:.0f}%")

        finally:
            # Clean up temp file
            try:
                Path(aos_path).unlink(missing_ok=True)
            except Exception:
                pass

    # Comparison matrix
    print(f"\n{'=' * 80}")
    print("ABLATION COMPARISON MATRIX")
    print(f"{'=' * 80}")
    print(
        f"  {'Variant':<18} {'Score':>8} {'PnL%':>8} {'PnL$':>10} "
        f"{'Trades':>6} {'Part%':>5} {'Select':>6} {'MaxDD$':>8} {'CI_lo':>7} {'CI_hi':>7}"
    )
    print(f"  {'─'*18} {'─'*8} {'─'*8} {'─'*10} {'─'*6} {'─'*5} {'─'*6} {'─'*8} {'─'*7} {'─'*7}")

    ranked = sorted(variant_results.items(), key=lambda x: x[1]["score"], reverse=True)
    for variant_id, vr in ranked:
        m = vr["metrics"]
        ci = vr["pnl_ci_95"]
        print(
            f"  {variant_id:<18} {vr['score']:>8.4f} {m['total_pnl_pct']:>+8.2f} "
            f"{m['total_pnl_dollars']:>+10.2f} {m['total_trades']:>6} "
            f"{m['participation']*100:>5.0f} {m['selectivity']:>6.1f} "
            f"{m['max_drawdown_dollars']:>8.2f} {ci['lo']:>+7.2f} {ci['hi']:>+7.2f}"
        )

    # Select winner
    winner_id = ranked[0][0] if ranked else None
    winner_score = ranked[0][1]["score"] if ranked else float("-inf")

    if winner_score == float("-inf"):
        print("\n  No viable variant found (all failed hard constraints)")
        winner_id = None

    result = {
        "phase": 1,
        "status": "complete",
        "split": {"start": TUNING_START, "end": TUNING_END},
        "dates_used": tuning_dates,
        "coverage": tuning_coverage,
        "variants": {
            vid: {
                "metrics": vr["metrics"],
                "score": vr["score"],
                "pnl_ci_95": vr["pnl_ci_95"],
            }
            for vid, vr in variant_results.items()
        },
        "ranking": [vid for vid, _ in ranked],
        "winner": winner_id,
        "winner_score": winner_score if winner_id else None,
    }

    save_report("phase1_ablation.json", result)

    if winner_id:
        # Save winner's day results separately for Phase 2
        winner_day_results = variant_results[winner_id]["day_results"]
        save_report("phase1_winner_day_results.json", {
            "variant": winner_id,
            "day_results": winner_day_results,
        })
        # Save winner's AOS config + orchestrator overrides
        winner_variant = build_ablation_variants()[winner_id]
        save_report("phase1_winner_aos.json", winner_variant["aos"])
        save_report("phase1_winner_orch.json", winner_variant.get("orch", {}))

    return result


# ── Phase 2: Test ────────────────────────────────────────────────────────────

def compute_config_hash(config: Dict[str, Any]) -> str:
    """Deterministic hash of the config for test-set protection."""
    serialized = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


async def phase2_test(phase1_result: Optional[Dict] = None) -> Dict[str, Any]:
    """One-time holdout test with protection."""
    # Load Phase 1 result
    if phase1_result is None:
        phase1_path = REPORTS_DIR / "phase1_ablation.json"
        if not phase1_path.exists():
            print("ERROR: Phase 1 results not found. Run phase1 first.")
            return {"phase": 2, "status": "error", "reason": "no_phase1_results"}
        with open(phase1_path) as f:
            phase1_result = json.load(f)

    winner_id = phase1_result.get("winner")
    if not winner_id:
        print("SKIPPING Phase 2: No winner from Phase 1")
        return {"phase": 2, "status": "skipped", "reason": "no_winner"}

    # Load winner AOS config + orchestrator overrides
    winner_aos_path = REPORTS_DIR / "phase1_winner_aos.json"
    if not winner_aos_path.exists():
        print("ERROR: Winner AOS config not found")
        return {"phase": 2, "status": "error", "reason": "no_winner_aos"}
    with open(winner_aos_path) as f:
        winner_aos = json.load(f)

    winner_orch: Dict[str, Any] = {}
    winner_orch_path = REPORTS_DIR / "phase1_winner_orch.json"
    if winner_orch_path.exists():
        with open(winner_orch_path) as f:
            winner_orch = json.load(f)

    # Hash includes both AOS and orchestrator config for test-set protection
    config_hash = compute_config_hash({"aos": winner_aos, "orch": winner_orch})

    # Test-set protection: check lock
    if TEST_LOCK_FILE.exists():
        with open(TEST_LOCK_FILE) as f:
            lock = json.load(f)
        prev_hash = lock.get("config_hash", "")
        print(f"\nWARNING: Test set already used!")
        print(f"  Previous run: {lock.get('timestamp', '?')}")
        print(f"  Previous hash: {prev_hash}")
        print(f"  Current hash:  {config_hash}")
        if prev_hash == config_hash:
            print("  Same config — returning cached results.")
            cached_path = REPORTS_DIR / "phase2_test.json"
            if cached_path.exists():
                with open(cached_path) as f:
                    return json.load(f)
        else:
            print("  DIFFERENT config — test set is BURNED. Results may be biased.")
            print("  Proceeding anyway but marking as 'reused'.")

    print("\n" + "=" * 80)
    print(f"PHASE 2 — TEST (holdout, winner={winner_id})")
    print("=" * 80)
    async with httpx.AsyncClient() as client:
        try:
            fast_mode_result = await apply_fast_mode(client)
            runtime = fast_mode_result.get("runtime", {})
            print(
                "Fast mode ON:"
                f" icebergs={runtime.get('iceberg_detection_enabled')}"
                f" cache_rows={runtime.get('cache_max_rows')}"
                f" cache_bytes={runtime.get('cache_max_bytes')}"
            )
        except Exception as exc:
            print(f"WARNING: Could not apply fast mode on runner: {safe_text(exc)}")
        test_coverage = await resolve_dataset_dates(
            client,
            TEST_START,
            TEST_END,
            require_l2=True,
        )
    test_dates = test_coverage.get("available_days", [])
    if not test_dates:
        print("ERROR: No test dates with OHLCV+L2 overlap.")
        return {"phase": 2, "status": "error", "reason": "no_test_dates"}
    print(f"Dates: {min(test_dates)} to {max(test_dates)} ({len(test_dates)} days)")
    print(f"Config hash: {config_hash}")

    # Apply orchestrator overrides before running
    if winner_orch:
        async with httpx.AsyncClient() as client:
            orch_result = await set_orchestrator_config(client, **winner_orch)
            print(f"  Orchestrator config applied: {orch_result.get('updated', {})}")

    # Write temp AOS
    aos_path = write_temp_aos(winner_aos, f"test_{winner_id}")

    try:
        day_results = await run_days(
            test_dates,
            aos_config_path=aos_path,
            label=f"test_{winner_id}",
            progress_prefix="P2",
        )
    finally:
        try:
            Path(aos_path).unlink(missing_ok=True)
        except Exception:
            pass

    metrics = compute_day_metrics(day_results)
    valid_days = [d for d in day_results if d.get("success")]
    pnl_ci = bootstrap_ci(valid_days, pnl_metric) if valid_days else (0, 0, 0)

    # Write lock file
    lock_data = {
        "config_hash": config_hash,
        "variant": winner_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "reused": TEST_LOCK_FILE.exists(),
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TEST_LOCK_FILE, "w") as f:
        json.dump(lock_data, f, indent=2)

    # Print results
    print(f"\n{'─' * 60}")
    print("TEST RESULTS")
    print(f"{'─' * 60}")
    print(f"  Variant:       {winner_id}")
    print(f"  Total trades:  {metrics['total_trades']}")
    print(f"  Total PnL:     {metrics['total_pnl_pct']:+.2f}% (${metrics['total_pnl_dollars']:+.2f})")
    print(f"  Participation: {metrics['participation']*100:.0f}%")
    print(f"  Max drawdown:  ${metrics['max_drawdown_dollars']:.2f}")
    print(f"  95% CI:        [{pnl_ci[1]:+.2f}%, {pnl_ci[2]:+.2f}%]")

    # Compare tuning vs test
    phase1_winner_metrics = phase1_result.get("variants", {}).get(winner_id, {}).get("metrics", {})
    if phase1_winner_metrics:
        train_pnl = phase1_winner_metrics.get("total_pnl_pct", 0)
        test_pnl = metrics["total_pnl_pct"]
        print(f"\n  Tuning PnL:    {train_pnl:+.2f}%")
        print(f"  Test PnL:      {test_pnl:+.2f}%")
        degradation = ((train_pnl - test_pnl) / abs(train_pnl) * 100) if train_pnl != 0 else 0
        print(f"  Degradation:   {degradation:.0f}%")

    result = {
        "phase": 2,
        "status": "complete",
        "split": {"start": TEST_START, "end": TEST_END},
        "dates_used": test_dates,
        "coverage": test_coverage,
        "variant": winner_id,
        "config_hash": config_hash,
        "metrics": metrics,
        "pnl_ci_95": {"mean": pnl_ci[0], "lo": pnl_ci[1], "hi": pnl_ci[2]},
        "lock": lock_data,
        "day_results": day_results,
    }

    save_report("phase2_test.json", result)
    return result


# ── Phase 3: Apply ───────────────────────────────────────────────────────────

async def phase3_apply(phase2_result: Optional[Dict] = None) -> Dict[str, Any]:
    """Apply winning config to AOS if test passed."""
    if phase2_result is None:
        phase2_path = REPORTS_DIR / "phase2_test.json"
        if not phase2_path.exists():
            print("ERROR: Phase 2 results not found. Run phase2 first.")
            return {"phase": 3, "status": "error", "reason": "no_phase2_results"}
        with open(phase2_path) as f:
            phase2_result = json.load(f)

    variant_id = phase2_result.get("variant")
    test_metrics = phase2_result.get("metrics", {})
    test_pnl = test_metrics.get("total_pnl_pct", 0)

    print("\n" + "=" * 80)
    print(f"PHASE 3 — APPLY (variant={variant_id})")
    print("=" * 80)

    # Safety check: don't apply if test is clearly negative
    if test_pnl < -2.0:
        print(f"  WARNING: Test PnL is {test_pnl:+.2f}% — skipping auto-apply.")
        print("  Review results and apply manually if desired.")
        return {"phase": 3, "status": "skipped", "reason": f"negative_test_pnl={test_pnl}"}

    # Load winner AOS config
    winner_aos_path = REPORTS_DIR / "phase1_winner_aos.json"
    if not winner_aos_path.exists():
        print("ERROR: Winner AOS config not found")
        return {"phase": 3, "status": "error", "reason": "no_winner_aos"}

    with open(winner_aos_path) as f:
        winner_aos = json.load(f)

    # Extract the MU ticker config
    mu_config = winner_aos.get("tickers", {}).get("MU", {})
    if not mu_config:
        print("ERROR: No MU config in winner AOS")
        return {"phase": 3, "status": "error", "reason": "no_mu_config"}

    # Load orchestrator overrides
    winner_orch: Dict[str, Any] = {}
    winner_orch_path = REPORTS_DIR / "phase1_winner_orch.json"
    if winner_orch_path.exists():
        with open(winner_orch_path) as f:
            winner_orch = json.load(f)

    print(f"  Test PnL:      {test_pnl:+.2f}%")
    print(f"  Config hash:   {phase2_result.get('config_hash', '?')}")
    if winner_orch:
        print(f"  Orchestrator:  {winner_orch}")
    print()

    # Apply via API
    try:
        async with httpx.AsyncClient() as client:
            # Apply AOS config
            resp = await client.post(
                f"{RUNNER_API_URL}/api/aos-config/update",
                json={"ticker": TICKER, "config": mu_config},
                timeout=10.0,
            )
            if resp.status_code == 200:
                print("  AOS config updated successfully via API.")
            else:
                print(f"  AOS API update failed: {resp.status_code}")
                print(f"  Falling back to direct file write...")

            # Apply orchestrator overrides
            if winner_orch:
                orch_result = await set_orchestrator_config(client, **winner_orch)
                print(f"  Orchestrator config applied: {orch_result.get('updated', {})}")

            if resp.status_code == 200:
                return {"phase": 3, "status": "applied", "variant": variant_id,
                        "orch_overrides": winner_orch}
            else:
                print(f"  Falling back to direct file write...")
    except Exception as e:
        print(f"  API update failed: {e}")
        print(f"  Falling back to direct file write...")

    # Direct file write fallback
    aos_path = Path(__file__).resolve().parent.parent / "aos_optimization" / "aos_config.json"
    with open(aos_path) as f:
        full_config = json.load(f)

    full_config.setdefault("tickers", {})["MU"] = mu_config
    with open(aos_path, "w") as f:
        json.dump(full_config, f, indent=2)
    print("  AOS config written directly to file.")

    return {"phase": 3, "status": "applied", "variant": variant_id}


# ── Reporting ────────────────────────────────────────────────────────────────

def save_report(filename: str, data: Dict[str, Any]):
    """Save a JSON report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\n  Report saved: {path}")


# ── CLI ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="MU Diagnostic & Ablation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Phases:
  phase0   Diagnostic — classify signal pipeline on tuning set
  phase1   Ablation — 5 variants (A-E) on tuning set
  phase2   Test — one-time holdout validation
  phase3   Apply — write winning config to AOS
  all      Run phases 0-3 sequentially
        """,
    )
    parser.add_argument(
        "phase",
        choices=["phase0", "phase1", "phase2", "phase3", "all"],
        help="Which phase to run",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force Phase 1 to run even if Phase 0 ABORT_ABLATION triggered",
    )
    args = parser.parse_args()

    print(f"\nMU Diagnostic Pipeline — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Ticker: {TICKER}")
    print(f"Runner API: {RUNNER_API_URL}")
    print(f"Strategy API: {STRATEGY_API_URL}")
    print(f"Reports: {REPORTS_DIR}")
    print()

    if args.phase in ("phase0", "all"):
        p0 = await phase0_diagnostic()
        if args.phase == "phase0":
            return

        if p0.get("status") == "abort":
            print("\nPipeline stopped: Phase 0 sanity gate failed.")
            return

    if args.phase in ("phase1", "all"):
        p1 = await phase1_ablation(force=args.force)
        if args.phase == "phase1":
            return

        if p1.get("status") == "aborted":
            print("\nPipeline stopped: Phase 1 aborted (use --force to override).")
            return
        if not p1.get("winner"):
            print("\nPipeline stopped: No winner from Phase 1.")
            return

    if args.phase in ("phase2", "all"):
        p2 = await phase2_test()
        if args.phase == "phase2":
            return

    if args.phase in ("phase3", "all"):
        await phase3_apply()


if __name__ == "__main__":
    asyncio.run(main())
