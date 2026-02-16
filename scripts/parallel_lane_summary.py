#!/usr/bin/env python3
"""Combine two backtest reports into a synthetic parallel-lane summary.

Use case:
- lane A and lane B each run with 5k capital
- combined output approximates a 2x5k parallel portfolio
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class LaneTrade:
    lane: str
    entry_time: datetime
    exit_time: datetime
    pnl_dollars: float
    strategy: str
    side: str
    trade_id: Any


def _parse_iso(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.fromtimestamp(0)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _resolve_summary_path(path: Path) -> Path:
    if path.is_file():
        return path
    candidate = path / "session_summary.json"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"session summary not found at: {path}")


def _load_lane(path: Path, lane_name: str) -> Tuple[Dict[str, Any], List[LaneTrade]]:
    summary_path = _resolve_summary_path(path)
    payload = json.loads(summary_path.read_text())
    session_summary = payload.get("session_summary") or {}
    raw_trades = session_summary.get("trades") or []
    trades: List[LaneTrade] = []
    for trade in raw_trades:
        try:
            trades.append(
                LaneTrade(
                    lane=lane_name,
                    entry_time=_parse_iso(trade.get("entry_time")),
                    exit_time=_parse_iso(trade.get("exit_time")),
                    pnl_dollars=float(trade.get("pnl_dollars") or 0.0),
                    strategy=str(trade.get("strategy") or ""),
                    side=str(trade.get("side") or ""),
                    trade_id=trade.get("trade_id"),
                )
            )
        except Exception:
            continue
    return payload, trades


def _max_concurrent_positions(trades: List[LaneTrade]) -> int:
    events: List[Tuple[datetime, int, int]] = []
    # event tuple: (ts, order, delta); exits first when same timestamp
    for trade in trades:
        events.append((trade.entry_time, 1, +1))
        events.append((trade.exit_time, 0, -1))
    events.sort(key=lambda item: (item[0], item[1]))
    active = 0
    max_active = 0
    for _, _, delta in events:
        active += delta
        if active > max_active:
            max_active = active
    return max_active


def _overlap_count(a: List[LaneTrade], b: List[LaneTrade]) -> int:
    count = 0
    for ta in a:
        for tb in b:
            latest_start = max(ta.entry_time, tb.entry_time)
            earliest_end = min(ta.exit_time, tb.exit_time)
            if latest_start < earliest_end:
                count += 1
    return count


def _strategy_breakdown(trades: List[LaneTrade]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for trade in trades:
        out[trade.strategy] = out.get(trade.strategy, 0) + 1
    return dict(sorted(out.items(), key=lambda item: (-item[1], item[0])))


def build_summary(lane_a_payload: Dict[str, Any], lane_b_payload: Dict[str, Any], lane_a: List[LaneTrade], lane_b: List[LaneTrade]) -> Dict[str, Any]:
    combined = lane_a + lane_b
    combined_pnl = round(sum(t.pnl_dollars for t in combined), 4)
    return {
        "lane_a": {
            "run_id": lane_a_payload.get("run_id"),
            "trades": len(lane_a),
            "pnl_dollars": round(sum(t.pnl_dollars for t in lane_a), 4),
            "strategy_breakdown": _strategy_breakdown(lane_a),
        },
        "lane_b": {
            "run_id": lane_b_payload.get("run_id"),
            "trades": len(lane_b),
            "pnl_dollars": round(sum(t.pnl_dollars for t in lane_b), 4),
            "strategy_breakdown": _strategy_breakdown(lane_b),
        },
        "combined": {
            "trades": len(combined),
            "pnl_dollars": combined_pnl,
            "max_concurrent_positions": _max_concurrent_positions(combined),
            "cross_lane_overlap_count": _overlap_count(lane_a, lane_b),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic 2-lane parallel portfolio summary")
    parser.add_argument("--lane-a", required=True, help="Path to lane A report dir or session_summary.json")
    parser.add_argument("--lane-b", required=True, help="Path to lane B report dir or session_summary.json")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args()

    lane_a_payload, lane_a = _load_lane(Path(args.lane_a), "A")
    lane_b_payload, lane_b = _load_lane(Path(args.lane_b), "B")
    summary = build_summary(lane_a_payload, lane_b_payload, lane_a, lane_b)

    print(json.dumps(summary, indent=2))
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
