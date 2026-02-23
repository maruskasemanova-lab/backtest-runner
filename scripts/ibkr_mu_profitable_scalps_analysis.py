#!/usr/bin/env python3
"""
Analyze profitable MU short scalps from IBKR-derived fixture and build a robust profile proposal.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List
from zoneinfo import ZoneInfo


NY_TZ = ZoneInfo("America/New_York")


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _enrich_trade(trade: Dict[str, Any]) -> Dict[str, Any]:
    entry_utc = datetime.fromisoformat(str(trade["entry_time_utc"]))
    exit_utc = datetime.fromisoformat(str(trade["exit_time_utc"]))
    qty = _safe_float(trade["quantity"])
    entry_price = _safe_float(trade["entry_price"])
    exit_price = _safe_float(trade["exit_price"])
    net_pnl = _safe_float(trade["net_pnl"])
    gross_pnl = (entry_price - exit_price) * qty
    ibkr_cost = gross_pnl - net_pnl
    hold_minutes = (exit_utc - entry_utc).total_seconds() / 60.0
    pnl_per_share = entry_price - exit_price
    entry_et = entry_utc.astimezone(NY_TZ)
    exit_et = exit_utc.astimezone(NY_TZ)
    return {
        "trade_id": int(_safe_float(trade["trade_id"])),
        "entry_date": str(trade["entry_date"]),
        "exit_date": str(trade["exit_date"]),
        "entry_time_utc": entry_utc.isoformat(),
        "exit_time_utc": exit_utc.isoformat(),
        "entry_time_et": entry_et.isoformat(timespec="seconds"),
        "exit_time_et": exit_et.isoformat(timespec="seconds"),
        "entry_hour_et": int(entry_et.hour),
        "holding_minutes": hold_minutes,
        "quantity": qty,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "gross_pnl": gross_pnl,
        "ibkr_cost": ibkr_cost,
        "net_pnl": net_pnl,
        "pnl_per_share": pnl_per_share,
        "is_profitable": bool(net_pnl > 0),
    }


def _build_hour_stats(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[int, Dict[str, float]] = defaultdict(
        lambda: {"count": 0.0, "wins": 0.0, "net_pnl": 0.0, "avg_hold": 0.0}
    )
    for row in rows:
        hour = int(row["entry_hour_et"])
        bucket = buckets[hour]
        bucket["count"] += 1.0
        bucket["wins"] += 1.0 if row["is_profitable"] else 0.0
        bucket["net_pnl"] += _safe_float(row["net_pnl"])
        bucket["avg_hold"] += _safe_float(row["holding_minutes"])

    output: List[Dict[str, Any]] = []
    for hour in sorted(buckets.keys()):
        bucket = buckets[hour]
        count = max(1.0, bucket["count"])
        output.append(
            {
                "hour_et": hour,
                "count": int(bucket["count"]),
                "wins": int(bucket["wins"]),
                "win_rate": round(bucket["wins"] / count, 4),
                "net_pnl": round(bucket["net_pnl"], 6),
                "avg_hold_minutes": round(bucket["avg_hold"] / count, 4),
            }
        )
    return output


def _summarize_group(name: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rows:
        return {"group": name, "count": 0}
    return {
        "group": name,
        "count": len(rows),
        "total_net_pnl": round(sum(_safe_float(row["net_pnl"]) for row in rows), 6),
        "avg_net_pnl": round(mean(_safe_float(row["net_pnl"]) for row in rows), 6),
        "median_net_pnl": round(median(_safe_float(row["net_pnl"]) for row in rows), 6),
        "avg_hold_minutes": round(
            mean(_safe_float(row["holding_minutes"]) for row in rows), 6
        ),
        "median_hold_minutes": round(
            median(_safe_float(row["holding_minutes"]) for row in rows), 6
        ),
        "avg_pnl_per_share": round(
            mean(_safe_float(row["pnl_per_share"]) for row in rows), 6
        ),
        "median_pnl_per_share": round(
            median(_safe_float(row["pnl_per_share"]) for row in rows), 6
        ),
        "avg_quantity": round(mean(_safe_float(row["quantity"]) for row in rows), 6),
        "median_quantity": round(
            median(_safe_float(row["quantity"]) for row in rows), 6
        ),
    }


def _build_profile(profile_id: str, profile_name: str) -> Dict[str, Any]:
    now = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return {
        "profile_id": profile_id,
        "profile_name": profile_name,
        "created_at": now,
        "updated_at": now,
        "source_note": (
            "Built from profitable MU IBKR live short scalp behavior (2026-01-27..2026-02-10), "
            "using broad constraints to avoid narrow date overfit."
        ),
        "strategy_profile": {
            "strategy_params": {
                "momentum": {
                    "enabled": True,
                    "allowed_regimes": ["TRENDING", "MIXED"],
                    "volume_threshold": 1.6,
                    "breakout_pct": 0.22,
                    "volume_stop_pct": 0.9,
                    "rr_ratio": 1.8,
                    "min_confidence": 58.0,
                    "trailing_stop_pct": 0.45,
                },
                "vwap_magnet": {
                    "enabled": True,
                    "allowed_regimes": ["TRENDING", "MIXED", "CHOPPY"],
                    "min_distance_pct": 0.3,
                    "max_distance_pct": 2.2,
                    "bars_since_vwap_threshold": 4,
                    "volume_confirm": True,
                    "volume_lookback": 20,
                    "volume_stop_pct": 0.8,
                    "trailing_stop_pct": 0.35,
                    "min_confidence": 56.0,
                },
                "pullback": {"enabled": False},
                "scalp_l2_intrabar": {"enabled": False},
            },
            "strategy_selection_mode": "all_enabled",
            "max_active_strategies": 2,
            "trading_hours": [10, 11, 12, 13],
            "time_filter_enabled": True,
            "long_only": False,
            "l2": {
                "min_delta": 900.0,
                "min_imbalance": 0.015,
                "min_signed_aggression": 0.015,
                "min_directional_consistency": 0.15,
            },
            "adaptive": {
                "version": 2,
                "flow_bias_enabled": True,
                "use_ohlcv_fallbacks": False,
                "min_active_bars_before_switch": 0,
                "switch_cooldown_bars": 6,
                "evidence_base_threshold": 45.0,
                "evidence_min_confirming_sources": 1,
                "regime_preferences": {
                    "TRENDING": ["momentum", "vwap_magnet"],
                    "MIXED": ["vwap_magnet", "momentum"],
                    "CHOPPY": ["vwap_magnet"],
                },
            },
            "adaptive_candidate": {
                "strategy_selection_mode": "all_enabled",
                "max_active_strategies": 2,
                "enabled_strategies": ["momentum", "vwap_magnet"],
                "regime_filter": ["TRENDING", "MIXED", "CHOPPY"],
                "trading_hours": [10, 11, 12, 13],
                "min_confidence": 56.0,
                "rr_ratio": 1.8,
                "trailing_stop_pct": 0.4,
                "l2_min_delta": 900.0,
                "l2_min_imbalance": 0.015,
                "l2_min_signed_aggression": 0.015,
                "l2_min_directional_consistency": 0.15,
                "adverse_flow_consistency": 0.28,
                "adverse_book_pressure": 0.10,
                "time_exit_bars": 8,
            },
        },
        "execution_profile": {
            "positioning": {
                "risk_per_trade_pct": 1.2,
                "max_position_notional_pct": 35.0,
                "max_fill_participation_rate": 0.12,
                "min_fill_ratio": 0.45,
                "enable_partial_take_profit": True,
                "partial_take_profit_rr": 0.7,
                "partial_take_profit_fraction": 0.6,
                "trailing_activation_pct": 0.10,
                "break_even_buffer_pct": 0.0,
                "break_even_min_hold_bars": 1,
                "trailing_enabled_in_choppy": False,
                "time_exit_bars": 8,
                "adverse_flow_exit_enabled": True,
                "adverse_flow_threshold": 0.10,
                "adverse_flow_min_hold_bars": 2,
                "adverse_flow_consistency_threshold": 0.28,
                "adverse_book_pressure_threshold": 0.10,
                "stop_loss_mode": "capped",
                "fixed_stop_loss_pct": 0.45,
            }
        },
    }


def _write_winners_csv(path: Path, winners: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "trade_id",
        "entry_date",
        "entry_time_et",
        "exit_time_et",
        "holding_minutes",
        "quantity",
        "entry_price",
        "exit_price",
        "pnl_per_share",
        "gross_pnl",
        "ibkr_cost",
        "net_pnl",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in winners:
            writer.writerow(
                {
                    "trade_id": row["trade_id"],
                    "entry_date": row["entry_date"],
                    "entry_time_et": row["entry_time_et"],
                    "exit_time_et": row["exit_time_et"],
                    "holding_minutes": round(_safe_float(row["holding_minutes"]), 2),
                    "quantity": round(_safe_float(row["quantity"]), 2),
                    "entry_price": round(_safe_float(row["entry_price"]), 4),
                    "exit_price": round(_safe_float(row["exit_price"]), 4),
                    "pnl_per_share": round(_safe_float(row["pnl_per_share"]), 4),
                    "gross_pnl": round(_safe_float(row["gross_pnl"]), 6),
                    "ibkr_cost": round(_safe_float(row["ibkr_cost"]), 6),
                    "net_pnl": round(_safe_float(row["net_pnl"]), 6),
                }
            )


def _write_winners_markdown(
    path: Path,
    winners: List[Dict[str, Any]],
    overall: Dict[str, Any],
    winners_summary: Dict[str, Any],
    losses_summary: Dict[str, Any],
    hour_stats: List[Dict[str, Any]],
) -> None:
    lines: List[str] = []
    lines.append("# MU Profitable Scalps (IBKR XML)")
    lines.append("")
    lines.append(
        "Source window: "
        f"{overall['first_entry_et']} -> {overall['last_entry_et']} (America/New_York)"
    )
    lines.append(
        f"Trades: {overall['total_trades']} | Winners: {overall['winner_count']} "
        f"| Win rate: {overall['win_rate']:.2%} | Total net PnL: ${overall['total_net_pnl']:.2f}"
    )
    lines.append("")
    lines.append("## Winners vs Losers")
    lines.append("")
    lines.append(
        f"- Winners: avg net ${winners_summary['avg_net_pnl']:.2f}, "
        f"median hold {winners_summary['median_hold_minutes']:.2f}m"
    )
    lines.append(
        f"- Losers: avg net ${losses_summary['avg_net_pnl']:.2f}, "
        f"median hold {losses_summary['median_hold_minutes']:.2f}m"
    )
    lines.append("")
    lines.append("## Hour Stats (ET)")
    lines.append("")
    lines.append("| Hour | Count | Wins | Win rate | Net PnL | Avg hold (m) |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for row in hour_stats:
        lines.append(
            f"| {row['hour_et']} | {row['count']} | {row['wins']} | {row['win_rate']:.2%} "
            f"| {row['net_pnl']:+.2f} | {row['avg_hold_minutes']:.2f} |"
        )
    lines.append("")
    lines.append("## Profitable Trades")
    lines.append("")
    lines.append(
        "| ID | Entry ET | Exit ET | Hold (m) | Qty | Entry | Exit | Gross | Cost | Net |"
    )
    lines.append("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in winners:
        lines.append(
            f"| {row['trade_id']} | {row['entry_time_et']} | {row['exit_time_et']} "
            f"| {row['holding_minutes']:.2f} | {row['quantity']:.0f} "
            f"| {row['entry_price']:.4f} | {row['exit_price']:.4f} "
            f"| {row['gross_pnl']:+.2f} | {row['ibkr_cost']:.3f} | {row['net_pnl']:+.2f} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def _upsert_unified_profile(
    *,
    aos_config_path: Path,
    ticker: str,
    profile_payload: Dict[str, Any],
) -> None:
    config = json.loads(aos_config_path.read_text())
    ticker_node = config.setdefault("tickers", {}).setdefault(ticker, {})
    unified_profiles = ticker_node.setdefault("unified_profiles", [])
    profile_id = str(profile_payload.get("profile_id", "")).strip()
    unified_profiles = [
        row
        for row in unified_profiles
        if str(row.get("profile_id", "")).strip() != profile_id
    ]
    unified_profiles.append(profile_payload)
    ticker_node["unified_profiles"] = unified_profiles
    aos_config_path.write_text(json.dumps(config, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze profitable MU short scalp trades from fixture."
    )
    parser.add_argument(
        "--fixture",
        default="tests/fixtures/ibkr_MU_short_scalps_2025-10-01_2026-02-13_from_xml.json",
        help="Path to generated MU short scalp fixture.",
    )
    parser.add_argument(
        "--ticker",
        default="MU",
        help="Ticker to tag in output profile metadata.",
    )
    parser.add_argument(
        "--csv-out",
        default="reports/ibkr_MU_profitable_scalps_from_xml.csv",
        help="Output CSV with profitable scalps.",
    )
    parser.add_argument(
        "--md-out",
        default="reports/ibkr_MU_profitable_scalps_from_xml.md",
        help="Output Markdown with profitable scalp summary.",
    )
    parser.add_argument(
        "--analysis-out",
        default="reports/ibkr_MU_profitable_scalps_analysis.json",
        help="Output JSON analysis.",
    )
    parser.add_argument(
        "--profile-out",
        default="aos_optimization/profiles/mu_ibkr_scalp_live_profile_v1.json",
        help="Output standalone unified profile JSON.",
    )
    parser.add_argument(
        "--aos-config",
        default="aos_optimization/aos_config.json",
        help="Path to AOS config (used when --apply-to-aos-config is enabled).",
    )
    parser.add_argument(
        "--apply-to-aos-config",
        action="store_true",
        help="Upsert generated unified profile into ticker.unified_profiles.",
    )
    parser.add_argument(
        "--profile-id",
        default="mu_ibkr_live_scalp_non_overfit_v1",
        help="Unified profile identifier.",
    )
    parser.add_argument(
        "--profile-name",
        default="MU IBKR Live Scalp Non-Overfit v1",
        help="Unified profile name.",
    )
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture not found: {fixture_path}")
    fixture = json.loads(fixture_path.read_text())
    trades_raw = fixture.get("short_round_trips", [])
    if not isinstance(trades_raw, list) or not trades_raw:
        raise SystemExit("Fixture has no short_round_trips.")

    enriched = [_enrich_trade(row) for row in trades_raw]
    enriched_sorted = sorted(enriched, key=lambda row: row["entry_time_utc"])
    winners = [row for row in enriched_sorted if row["is_profitable"]]
    losers = [row for row in enriched_sorted if not row["is_profitable"]]
    winners_sorted = sorted(winners, key=lambda row: row["net_pnl"], reverse=True)

    winners_summary = _summarize_group("winners", winners)
    losers_summary = _summarize_group("losers", losers)
    overall = _summarize_group("all", enriched_sorted)
    overall["winner_count"] = len(winners)
    overall["loser_count"] = len(losers)
    overall["win_rate"] = (
        (len(winners) / len(enriched_sorted)) if enriched_sorted else 0.0
    )
    overall["total_trades"] = len(enriched_sorted)
    overall["first_entry_et"] = enriched_sorted[0]["entry_time_et"]
    overall["last_entry_et"] = enriched_sorted[-1]["entry_time_et"]

    hour_stats = _build_hour_stats(enriched_sorted)
    top_winners = winners_sorted[:10]
    worst_losers = sorted(enriched_sorted, key=lambda row: row["net_pnl"])[:10]

    analysis_payload = {
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "fixture_path": str(fixture_path),
        "ticker": str(args.ticker).strip().upper(),
        "overall": overall,
        "winners_summary": winners_summary,
        "losers_summary": losers_summary,
        "hour_stats_et": hour_stats,
        "top_winners": top_winners,
        "worst_losers": worst_losers,
        "profitable_trades": winners_sorted,
        "non_overfit_takeaways": [
            "Most winners close quickly (median hold around 2 minutes); large losses come from prolonged holds.",
            "Open-hour and late-session entries produced outsized downside tails in this sample.",
            "Positive edge depended on adequate per-share move versus cost (reward-to-cost discipline matters).",
            "A robust profile should cap holding time, tighten adverse-flow exits, and restrict sessions to liquid mid-day windows.",
        ],
    }

    csv_out = Path(args.csv_out)
    md_out = Path(args.md_out)
    analysis_out = Path(args.analysis_out)
    profile_out = Path(args.profile_out)

    _write_winners_csv(csv_out, winners_sorted)
    _write_winners_markdown(
        md_out, winners_sorted, overall, winners_summary, losers_summary, hour_stats
    )
    analysis_out.parent.mkdir(parents=True, exist_ok=True)
    analysis_out.write_text(json.dumps(analysis_payload, indent=2))

    profile_payload = _build_profile(str(args.profile_id), str(args.profile_name))
    profile_out.parent.mkdir(parents=True, exist_ok=True)
    profile_out.write_text(json.dumps(profile_payload, indent=2))

    if args.apply_to_aos_config:
        _upsert_unified_profile(
            aos_config_path=Path(args.aos_config),
            ticker=str(args.ticker).strip().upper(),
            profile_payload=profile_payload,
        )

    print(f"Profitable scalps CSV: {csv_out}")
    print(f"Profitable scalps MD:  {md_out}")
    print(f"Analysis JSON:         {analysis_out}")
    print(f"Profile JSON:          {profile_out}")
    print(
        f"Winners: {len(winners_sorted)} / {len(enriched_sorted)} ({overall['win_rate']:.2%})"
    )


if __name__ == "__main__":
    main()
