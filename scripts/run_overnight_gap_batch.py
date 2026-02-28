#!/usr/bin/env python3
"""
Run chunked multi-day backtests and simulate overnight gap trades from markers.

Key fix:
- Do not treat END_OF_DAY as final completion for multi-day chunks.
- Keep resuming playback until current_bar_index reaches total_bars - 1
  (or progress is effectively 100% / COMPLETED).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ChunkResult:
    chunk_idx: int
    date_from: str
    date_to: str
    run_id: str
    run_key: Optional[str]
    status: str
    error: Optional[str]
    total_bars: Optional[int]
    current_bar_index: Optional[int]
    progress_pct: Optional[float]
    phase: Optional[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run chunked backtests and simulate overnight gap strategy."
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8002")
    parser.add_argument(
        "--strategy-api-url",
        default="http://127.0.0.1:8001",
        help="Strategy API URL passed to each /api/run/start payload.",
    )
    parser.add_argument("--ticker", default="MU")
    parser.add_argument("--date-from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--date-to", required=True, help="YYYY-MM-DD")
    parser.add_argument("--chunk-days", type=int, default=10)
    parser.add_argument("--prefix", default="")
    parser.add_argument(
        "--speed-ms",
        default="max",
        help="Playback speed sent to /play endpoint (e.g. max, 0, 10hz, 50).",
    )
    parser.add_argument(
        "--cutoff-tz",
        default="Europe/Bratislava",
        help="Timezone for signal cutoff.",
    )
    parser.add_argument(
        "--cutoff-time",
        default="21:00",
        help="HH:MM cutoff in cutoff-tz; signals earlier than this are ignored.",
    )
    parser.add_argument(
        "--no-weekend-hold",
        action="store_true",
        help="Skip trades where next open is not the next calendar day.",
    )
    parser.add_argument(
        "--delete-runs",
        action="store_true",
        help="Delete run from memory after chunk completion (summary remains persisted).",
    )
    parser.add_argument(
        "--state-timeout-sec",
        type=int,
        default=2400,
        help="Max seconds to wait for one play/resume cycle.",
    )
    parser.add_argument(
        "--request-timeout-sec",
        type=int,
        default=60,
        help="HTTP request timeout in seconds.",
    )
    parser.add_argument(
        "--output-json",
        default="results_overnight_gap_batch.json",
    )
    parser.add_argument(
        "--output-csv",
        default="results_overnight_gap_batch_trades.csv",
    )

    # Requested config from the user scenario.
    parser.add_argument("--strategy-selection-mode", default="all_enabled")
    parser.add_argument("--max-active-strategies", type=int, default=1)
    parser.add_argument(
        "--context-aware-risk-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--context-risk-min-sl-pct", type=float, default=0.5)
    parser.add_argument("--include-extended-hours", action="store_true", default=False)
    parser.add_argument(
        "--l2-confirm-enabled",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--reason",
        default="overnight_gap_batch",
        help="Reason string passed to /api/run/start",
    )
    return parser.parse_args()


def req(
    method: str,
    url: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    timeout_sec: int = 60,
    retries: int = 3,
) -> requests.Response:
    last_err: Optional[BaseException] = None
    for i in range(retries):
        try:
            if method == "GET":
                return requests.get(url, timeout=timeout_sec)
            if method == "POST":
                return requests.post(url, json=payload, timeout=timeout_sec)
            if method == "DELETE":
                return requests.delete(url, timeout=timeout_sec)
            raise ValueError(f"Unsupported method: {method}")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if i < retries - 1:
                time.sleep(1.25 * (i + 1))
    if last_err:
        raise last_err
    raise RuntimeError("Request failed without exception")


def chunk_ranges(start: date, end: date, chunk_days: int) -> List[Tuple[date, date]]:
    out: List[Tuple[date, date]] = []
    cur = start
    step = timedelta(days=chunk_days - 1)
    while cur <= end:
        cend = min(end, cur + step)
        out.append((cur, cend))
        cur = cend + timedelta(days=1)
    return out


def state_is_fully_complete(state: Dict[str, Any]) -> bool:
    phase = str(state.get("phase") or "").upper()
    lifecycle = str(state.get("execution_lifecycle") or "").upper()
    if phase == "COMPLETED" or lifecycle == "COMPLETED":
        return True

    total_bars = int(state.get("total_bars") or 0)
    cur_bar = int(state.get("current_bar_index") or -1)
    progress = float(state.get("progress_pct") or 0.0)

    if total_bars > 0 and cur_bar >= total_bars - 1:
        return True
    if progress >= 99.999:
        return True
    return False


def poll_until_idle_or_complete(
    *,
    api_base: str,
    run_id: str,
    ticker: str,
    date_part: str,
    request_timeout_sec: int,
    state_timeout_sec: int,
) -> Dict[str, Any]:
    started = time.time()
    missing_state_hits = 0
    while True:
        if time.time() - started > state_timeout_sec:
            raise TimeoutError(f"state timeout for {run_id}")

        st = req(
            "GET",
            f"{api_base}/api/run/{run_id}/{ticker}/{date_part}/state",
            timeout_sec=request_timeout_sec,
            retries=3,
        )
        if st.status_code == 404:
            missing_state_hits += 1
            if missing_state_hits >= 5:
                summary_state = load_summary_as_state(
                    api_base=api_base,
                    run_id=run_id,
                    ticker=ticker,
                    date_part=date_part,
                    request_timeout_sec=request_timeout_sec,
                )
                if summary_state is not None and state_is_fully_complete(summary_state):
                    return summary_state
                raise RuntimeError(
                    f"state endpoint lost run {run_id} (404 repeated {missing_state_hits}x)"
                )
            time.sleep(1.0)
            continue
        if st.status_code != 200:
            missing_state_hits = 0
            time.sleep(1.0)
            continue
        missing_state_hits = 0
        state = st.json()

        if state_is_fully_complete(state):
            return state
        if not bool(state.get("is_running", False)):
            return state
        time.sleep(1.0)


def load_summary_as_state(
    *,
    api_base: str,
    run_id: str,
    ticker: str,
    date_part: str,
    request_timeout_sec: int,
) -> Optional[Dict[str, Any]]:
    sm = req(
        "GET",
        f"{api_base}/api/run/{run_id}/{ticker}/{date_part}/summary",
        timeout_sec=max(90, request_timeout_sec),
        retries=2,
    )
    if sm.status_code != 200:
        return None
    js = sm.json()
    total_bars = int(js.get("total_bars") or 0)
    processed_bars = int(js.get("processed_bars") or 0)
    current_bar_index = processed_bars - 1 if processed_bars > 0 else -1
    if total_bars > 0:
        progress_pct = max(0.0, min(100.0, (processed_bars / total_bars) * 100.0))
    else:
        progress_pct = float(js.get("progress_pct") or 100.0)
    return {
        "phase": js.get("phase") or "COMPLETED",
        "execution_lifecycle": "COMPLETED",
        "total_bars": total_bars,
        "current_bar_index": current_bar_index,
        "progress_pct": progress_pct,
        "is_running": False,
        "source": "summary_fallback",
    }


def run_chunk(
    *,
    api_base: str,
    strategy_api_url: str,
    ticker: str,
    date_from: str,
    date_to: str,
    run_id: str,
    speed_ms: Any,
    reason: str,
    strategy_selection_mode: str,
    max_active_strategies: int,
    context_aware_risk_enabled: bool,
    context_risk_min_sl_pct: float,
    include_extended_hours: bool,
    l2_confirm_enabled: bool,
    request_timeout_sec: int,
    state_timeout_sec: int,
    delete_runs: bool,
) -> ChunkResult:
    date_part = f"{date_from}_to_{date_to}"
    start_payload = {
        "run_id": run_id,
        "strategy_api_url": strategy_api_url,
        "ticker": ticker,
        "date_from": date_from,
        "date_to": date_to,
        "reason": reason,
        "strategy_selection_mode": strategy_selection_mode,
        "max_active_strategies": max_active_strategies,
        "context_aware_risk_enabled": context_aware_risk_enabled,
        "context_risk_min_sl_pct": context_risk_min_sl_pct,
        "include_extended_hours": include_extended_hours,
        "l2_confirm_enabled": l2_confirm_enabled,
    }

    start_resp = req(
        "POST",
        f"{api_base}/api/run/start",
        payload=start_payload,
        timeout_sec=max(90, request_timeout_sec),
        retries=3,
    )
    if start_resp.status_code != 200:
        return ChunkResult(
            chunk_idx=0,
            date_from=date_from,
            date_to=date_to,
            run_id=run_id,
            run_key=None,
            status="start_failed",
            error=f"HTTP {start_resp.status_code}: {start_resp.text[:300]}",
            total_bars=None,
            current_bar_index=None,
            progress_pct=None,
            phase=None,
        )

    start_js = start_resp.json()
    run_key = str(start_js.get("run_key") or "")

    last_cur = -1
    idle_cycles_without_progress = 0
    missing_state_hits = 0
    final_state: Dict[str, Any] = {}

    for _ in range(500):  # safety bound
        st = req(
            "GET",
            f"{api_base}/api/run/{run_id}/{ticker}/{date_part}/state",
            timeout_sec=request_timeout_sec,
            retries=3,
        )
        if st.status_code == 200:
            missing_state_hits = 0
            final_state = st.json()
            if state_is_fully_complete(final_state):
                break
        elif st.status_code == 404:
            missing_state_hits += 1
            if missing_state_hits >= 5:
                summary_state = load_summary_as_state(
                    api_base=api_base,
                    run_id=run_id,
                    ticker=ticker,
                    date_part=date_part,
                    request_timeout_sec=request_timeout_sec,
                )
                if summary_state is not None and state_is_fully_complete(summary_state):
                    final_state = summary_state
                    break
                return ChunkResult(
                    chunk_idx=0,
                    date_from=date_from,
                    date_to=date_to,
                    run_id=run_id,
                    run_key=run_key or None,
                    status="state_missing",
                    error=(
                        f"state endpoint lost run {run_id} "
                        f"(404 repeated {missing_state_hits}x)"
                    ),
                    total_bars=final_state.get("total_bars"),
                    current_bar_index=final_state.get("current_bar_index"),
                    progress_pct=final_state.get("progress_pct"),
                    phase=final_state.get("phase"),
                )
            time.sleep(1.0)
            continue
        else:
            missing_state_hits = 0
            time.sleep(1.0)
            continue

        # Resume (or start) playback for the next segment/day.
        play_resp = req(
            "POST",
            f"{api_base}/api/run/{run_id}/{ticker}/{date_part}/play",
            payload={"speed_ms": speed_ms},
            timeout_sec=request_timeout_sec,
            retries=3,
        )
        if play_resp.status_code >= 400:
            return ChunkResult(
                chunk_idx=0,
                date_from=date_from,
                date_to=date_to,
                run_id=run_id,
                run_key=run_key,
                status="play_failed",
                error=f"HTTP {play_resp.status_code}: {play_resp.text[:300]}",
                total_bars=final_state.get("total_bars"),
                current_bar_index=final_state.get("current_bar_index"),
                progress_pct=final_state.get("progress_pct"),
                phase=final_state.get("phase"),
            )

        try:
            final_state = poll_until_idle_or_complete(
                api_base=api_base,
                run_id=run_id,
                ticker=ticker,
                date_part=date_part,
                request_timeout_sec=request_timeout_sec,
                state_timeout_sec=state_timeout_sec,
            )
        except Exception as exc:  # noqa: BLE001
            return ChunkResult(
                chunk_idx=0,
                date_from=date_from,
                date_to=date_to,
                run_id=run_id,
                run_key=run_key or None,
                status="state_missing",
                error=str(exc),
                total_bars=final_state.get("total_bars"),
                current_bar_index=final_state.get("current_bar_index"),
                progress_pct=final_state.get("progress_pct"),
                phase=final_state.get("phase"),
            )
        if state_is_fully_complete(final_state):
            break

        cur_bar = int(final_state.get("current_bar_index") or -1)
        if cur_bar <= last_cur:
            idle_cycles_without_progress += 1
        else:
            idle_cycles_without_progress = 0
            last_cur = cur_bar
        if idle_cycles_without_progress >= 3:
            return ChunkResult(
                chunk_idx=0,
                date_from=date_from,
                date_to=date_to,
                run_id=run_id,
                run_key=run_key,
                status="stalled",
                error="No progress across multiple resume cycles.",
                total_bars=final_state.get("total_bars"),
                current_bar_index=final_state.get("current_bar_index"),
                progress_pct=final_state.get("progress_pct"),
                phase=final_state.get("phase"),
            )

    # Final summary fetch ensures persistence and acts as late fallback for completion.
    final_summary_state = load_summary_as_state(
        api_base=api_base,
        run_id=run_id,
        ticker=ticker,
        date_part=date_part,
        request_timeout_sec=request_timeout_sec,
    )
    if final_summary_state is not None and (
        state_is_fully_complete(final_summary_state)
        or not state_is_fully_complete(final_state)
    ):
        final_state = final_summary_state

    if delete_runs:
        _ = req(
            "DELETE",
            f"{api_base}/api/run/{run_id}/{ticker}/{date_part}",
            timeout_sec=request_timeout_sec,
            retries=2,
        )

    return ChunkResult(
        chunk_idx=0,
        date_from=date_from,
        date_to=date_to,
        run_id=run_id,
        run_key=run_key or None,
        status="completed" if state_is_fully_complete(final_state) else "incomplete",
        error=None,
        total_bars=final_state.get("total_bars"),
        current_bar_index=final_state.get("current_bar_index"),
        progress_pct=final_state.get("progress_pct"),
        phase=final_state.get("phase"),
    )


def parse_side(marker: Dict[str, Any]) -> str:
    title = str(marker.get("title") or "").upper()
    desc = str(marker.get("description") or "").upper()
    if "BUY" in title or "LONG" in title or "BUY" in desc:
        return "long"
    if "SELL" in title or "SHORT" in title or "SELL" in desc:
        return "short"
    return ""


def load_open_0930_map(ticker: str) -> Dict[str, float]:
    open_by_day: Dict[str, float] = {}
    for file_path in sorted((ROOT / "data").glob(f"{ticker}_ohlcv-1m_*.csv")):
        try:
            df = pd.read_csv(file_path)
        except Exception:  # noqa: BLE001
            continue
        lc = {c.lower(): c for c in df.columns}
        ts_col = lc.get("timestamp") or lc.get("ts_event") or lc.get("index")
        op_col = lc.get("open")
        if not ts_col or not op_col:
            continue
        ts = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
        op = pd.to_numeric(df[op_col], errors="coerce")
        dff = pd.DataFrame({"ts": ts, "open": op}).dropna()
        if dff.empty:
            continue
        et = dff["ts"].dt.tz_convert("US/Eastern")
        dff = dff.assign(et=et)
        dff = dff[dff["et"].dt.time == dtime(9, 30)].sort_values("et")
        for _, row in dff.iterrows():
            key = row["et"].date().isoformat()
            if key not in open_by_day:
                open_by_day[key] = float(row["open"])
    return open_by_day


def simulate_overnight(
    *,
    run_keys: List[str],
    ticker: str,
    cutoff_tz: str,
    cutoff_time: dtime,
    no_weekend_hold: bool,
) -> Dict[str, Any]:
    con = sqlite3.connect(str(ROOT / "data" / "saas_state.db"))
    cur = con.cursor()

    markers: List[Dict[str, Any]] = []
    missing_run_keys: List[str] = []
    for run_key in run_keys:
        cur.execute(
            "SELECT summary_json FROM run_summaries WHERE run_key = ?",
            (run_key,),
        )
        row = cur.fetchone()
        if not row:
            missing_run_keys.append(run_key)
            continue
        js = json.loads(row[0])
        ms = js.get("markers")
        if isinstance(ms, list):
            for m in ms:
                mm = dict(m)
                mm["_run_key"] = run_key
                markers.append(mm)

    open_by_day = load_open_0930_map(ticker)
    trading_days = sorted(open_by_day)
    next_day = {trading_days[i]: trading_days[i + 1] for i in range(len(trading_days) - 1)}
    tz_cutoff = ZoneInfo(cutoff_tz)

    selected: Dict[str, Dict[str, Any]] = {}
    signal_markers_total = 0
    signals_after_cutoff = 0

    for marker in markers:
        if marker.get("marker_type") != "signal_generated":
            continue
        signal_markers_total += 1

        ts = marker.get("timestamp")
        price = marker.get("price")
        if ts is None or price is None:
            continue
        try:
            t_utc = pd.to_datetime(ts, utc=True)
            signal_price = float(price)
        except Exception:  # noqa: BLE001
            continue
        if not np.isfinite(signal_price) or signal_price <= 0:
            continue

        t_local = t_utc.tz_convert(tz_cutoff)
        if t_local.time() < cutoff_time:
            continue
        signals_after_cutoff += 1

        side = parse_side(marker)
        if side not in ("long", "short"):
            continue

        t_et = t_utc.tz_convert("US/Eastern")
        day = t_et.date().isoformat()
        cand = {
            "signal_et_date": day,
            "timestamp_utc": t_utc.isoformat(),
            "timestamp_et": t_et.isoformat(),
            "timestamp_cutoff_tz": t_local.isoformat(),
            "side": side,
            "signal_price": signal_price,
            "title": marker.get("title"),
            "description": marker.get("description"),
            "run_key": marker.get("_run_key"),
        }
        if day not in selected or pd.to_datetime(cand["timestamp_utc"]) > pd.to_datetime(
            selected[day]["timestamp_utc"]
        ):
            selected[day] = cand

    trades: List[Dict[str, Any]] = []
    skipped_weekend_or_holiday = 0
    for day in sorted(selected):
        nd = next_day.get(day)
        if not nd:
            continue
        gap_days = (pd.to_datetime(nd).date() - pd.to_datetime(day).date()).days
        if no_weekend_hold and gap_days > 1:
            skipped_weekend_or_holiday += 1
            continue
        sig = selected[day]
        entry = float(sig["signal_price"])
        exit_open = float(open_by_day[nd])
        if sig["side"] == "long":
            ret = (exit_open - entry) / entry * 100.0
            pnl = exit_open - entry
        else:
            ret = (entry - exit_open) / entry * 100.0
            pnl = entry - exit_open
        trades.append(
            {
                **sig,
                "next_open_et_date": nd,
                "next_open_price": exit_open,
                "hold_calendar_days": int(gap_days),
                "overnight_return_pct": float(ret),
                "pnl_per_share_usd": float(pnl),
                "win": bool(ret > 0),
                "loss": bool(ret < 0),
                "flat": bool(abs(ret) < 1e-12),
            }
        )

    returns = [float(t["overnight_return_pct"]) for t in trades]
    n = len(returns)
    wins = sum(1 for r in returns if r > 0)
    losses = sum(1 for r in returns if r < 0)
    flats = n - wins - losses
    compounded = 0.0
    if returns:
        c = 1.0
        for r in returns:
            c *= 1.0 + r / 100.0
        compounded = (c - 1.0) * 100.0

    performance = {
        "trades": n,
        "wins": wins,
        "losses": losses,
        "flats": flats,
        "win_rate_pct": float((wins / n * 100.0) if n else 0.0),
        "sum_return_pct": float(np.sum(returns) if returns else 0.0),
        "avg_return_pct": float(np.mean(returns) if returns else 0.0),
        "median_return_pct": float(np.median(returns) if returns else 0.0),
        "compounded_return_pct": float(compounded),
        "max_win_pct": float(np.max(returns) if returns else 0.0),
        "max_loss_pct": float(np.min(returns) if returns else 0.0),
        "sum_pnl_per_share_usd": float(np.sum([t["pnl_per_share_usd"] for t in trades]) if trades else 0.0),
        "sum_pnl_usd_if_10k_per_trade": float(
            np.sum([(t["overnight_return_pct"] / 100.0) * 10000.0 for t in trades]) if trades else 0.0
        ),
    }
    for side in ("long", "short"):
        arr = [t for t in trades if t["side"] == side]
        rr = [float(t["overnight_return_pct"]) for t in arr]
        performance[f"{side}_trades"] = len(arr)
        performance[f"{side}_win_rate_pct"] = float(
            (sum(1 for x in arr if x["win"]) / len(arr) * 100.0) if arr else 0.0
        )
        performance[f"{side}_sum_return_pct"] = float(np.sum(rr) if rr else 0.0)

    monthly: List[Dict[str, Any]] = []
    by_month: Dict[str, List[Dict[str, Any]]] = {}
    for trade in trades:
        m = trade["signal_et_date"][:7]
        by_month.setdefault(m, []).append(trade)
    for month in sorted(by_month):
        arr = by_month[month]
        rr = [float(t["overnight_return_pct"]) for t in arr]
        cc = 1.0
        for r in rr:
            cc *= 1.0 + r / 100.0
        monthly.append(
            {
                "month": month,
                "trades": len(arr),
                "wins": int(sum(1 for t in arr if t["win"])),
                "losses": int(sum(1 for t in arr if t["loss"])),
                "win_rate_pct": float(sum(1 for t in arr if t["win"]) / len(arr) * 100.0),
                "sum_return_pct": float(np.sum(rr)),
                "avg_return_pct": float(np.mean(rr)),
                "compounded_return_pct": float((cc - 1.0) * 100.0),
                "sum_pnl_per_share_usd": float(np.sum([t["pnl_per_share_usd"] for t in arr])),
            }
        )

    return {
        "missing_run_keys": missing_run_keys,
        "scan_counts": {
            "markers_total": len(markers),
            "signal_markers_total": signal_markers_total,
            "signals_after_cutoff": signals_after_cutoff,
            "selected_day_signals": len(selected),
            "skipped_weekend_or_holiday": skipped_weekend_or_holiday,
            "trades_simulated": len(trades),
        },
        "performance": performance,
        "monthly": monthly,
        "trades": trades,
    }


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)
    cutoff_time = datetime.strptime(args.cutoff_time, "%H:%M").time()
    prefix = args.prefix.strip() or f"overnight-gap-{int(time.time())}"

    ranges = chunk_ranges(start, end, args.chunk_days)
    chunk_results: List[ChunkResult] = []
    run_keys: List[str] = []

    for idx, (dfrom, dto) in enumerate(ranges, start=1):
        run_id = f"{prefix}-{idx}"
        res = run_chunk(
            api_base=args.api_base,
            strategy_api_url=args.strategy_api_url,
            ticker=args.ticker,
            date_from=dfrom.isoformat(),
            date_to=dto.isoformat(),
            run_id=run_id,
            speed_ms=args.speed_ms,
            reason=args.reason,
            strategy_selection_mode=args.strategy_selection_mode,
            max_active_strategies=args.max_active_strategies,
            context_aware_risk_enabled=args.context_aware_risk_enabled,
            context_risk_min_sl_pct=args.context_risk_min_sl_pct,
            include_extended_hours=args.include_extended_hours,
            l2_confirm_enabled=args.l2_confirm_enabled,
            request_timeout_sec=args.request_timeout_sec,
            state_timeout_sec=args.state_timeout_sec,
            delete_runs=args.delete_runs,
        )
        res.chunk_idx = idx
        chunk_results.append(res)
        if res.run_key:
            run_keys.append(res.run_key)
        print(
            f"[{idx}/{len(ranges)}] {res.date_from}->{res.date_to} "
            f"status={res.status} progress={res.progress_pct} phase={res.phase}"
            ,
            flush=True,
        )
        if res.error:
            print(f"  error: {res.error}", flush=True)

    sim = simulate_overnight(
        run_keys=run_keys,
        ticker=args.ticker,
        cutoff_tz=args.cutoff_tz,
        cutoff_time=cutoff_time,
        no_weekend_hold=args.no_weekend_hold,
    )

    result = {
        "meta": {
            "created_utc": datetime.utcnow().isoformat() + "Z",
            "ticker": args.ticker,
            "requested_range": {"from": args.date_from, "to": args.date_to},
            "api_base": args.api_base,
            "strategy_api_url": args.strategy_api_url,
            "run_prefix": prefix,
            "chunk_days": args.chunk_days,
            "speed_ms": args.speed_ms,
            "cutoff_tz": args.cutoff_tz,
            "cutoff_time": args.cutoff_time,
            "no_weekend_hold": bool(args.no_weekend_hold),
            "config": {
                "strategy_selection_mode": args.strategy_selection_mode,
                "max_active_strategies": args.max_active_strategies,
                "context_aware_risk_enabled": args.context_aware_risk_enabled,
                "context_risk_min_sl_pct": args.context_risk_min_sl_pct,
                "include_extended_hours": args.include_extended_hours,
                "l2_confirm_enabled": args.l2_confirm_enabled,
            },
        },
        "chunk_reports": [cr.__dict__ for cr in chunk_results],
        "run_keys": run_keys,
        **sim,
    }

    out_json = ROOT / args.output_json
    out_csv = ROOT / args.output_csv
    out_json.write_text(json.dumps(result, indent=2))
    pd.DataFrame(result["trades"]).to_csv(out_csv, index=False)

    print(f"\nSaved JSON: {out_json}", flush=True)
    print(f"Saved CSV:  {out_csv}", flush=True)
    print("Performance:", json.dumps(result["performance"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
