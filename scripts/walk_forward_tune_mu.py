#!/usr/bin/env python3
"""
Walk-Forward Tuning for MU with L2 Data

Splits:
- Train: 2025-11-03 to 2025-12-12 (~28 days) - Parameter optimization
- Validation: 2025-12-15 to 2026-01-08 (~9 days) - Model selection
- Test: 2026-01-09 to 2026-02-10 (~9 days) - Final evaluation (holdout)
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx


# Walk-forward splits
TRAIN_START = "2025-11-03"
TRAIN_END = "2025-12-12"
VAL_START = "2025-12-15"
VAL_END = "2026-01-08"
TEST_START = "2026-01-09"
TEST_END = "2026-02-10"

TICKER = "MU"
RUNNER_API_URL = "http://localhost:8000"


async def run_backtest(
    client: httpx.AsyncClient,
    date_from: str,
    date_to: str,
    config: dict,
    label: str = "",
) -> dict:
    """Run backtest and return results."""

    import uuid

    run_config = {
        "run_id": f"wf_{uuid.uuid4().hex[:12]}",
        "ticker": TICKER,
        "date_from": date_from,
        "date_to": date_to,
        "l2_only": True,
        "l2_confirm_enabled": True,
        "comparable_mode": True,
        "apply_ticker_overrides_on_start": False,
        "apply_aos_optimizations_on_start": False,
        "account_size_usd": 100,
        "risk_per_trade_pct": 2.0,
    }

    # Merge config
    for key, value in config.items():
        run_config[key] = value

    print(f"  Running backtest {label}: {date_from} to {date_to}")

    try:
        # Start run
        start_response = await client.post(
            f"{RUNNER_API_URL}/api/run/start",
            json=run_config,
            timeout=30.0,
        )

        if start_response.status_code != 200:
            print(f"  Start failed: {start_response.status_code}")
            return {
                "pnl_pct": 0,
                "trades": 0,
                "win_rate": 0,
                "sharpe": 0,
                "error": start_response.text[:200],
            }

        start_data = start_response.json()
        run_id = start_data.get("run_id", "")

        if not run_id:
            return {
                "pnl_pct": 0,
                "trades": 0,
                "win_rate": 0,
                "sharpe": 0,
                "error": "No run_id",
            }

        # Play the run
        play_response = await client.post(
            f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date_from}_to_{date_to}/play",
            json={"speed": "max"},
            timeout=120.0,
        )

        if play_response.status_code != 200:
            return {
                "pnl_pct": 0,
                "trades": 0,
                "win_rate": 0,
                "sharpe": 0,
                "error": f"Play failed: {play_response.text[:100]}",
            }

        # Poll for completion
        for _ in range(60):  # Max 60 seconds
            await asyncio.sleep(1)

            summary_response = await client.get(
                f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{date_from}/summary",
                timeout=10.0,
            )

            if summary_response.status_code == 200:
                summary = summary_response.json()
                if summary.get("completed", False):
                    return {
                        "pnl_pct": summary.get("total_pnl_pct", 0),
                        "trades": summary.get("total_trades", 0),
                        "win_rate": summary.get("win_rate", 0),
                        "sharpe": 0,  # Not in summary
                    }
            elif summary_response.status_code != 404:
                print(f"  Summary error: {summary_response.status_code}")

        return {
            "pnl_pct": 0,
            "trades": 0,
            "win_rate": 0,
            "sharpe": 0,
            "error": "Timeout",
        }

    except Exception as e:
        print(f"  Exception: {e}")
        return {"pnl_pct": 0, "trades": 0, "win_rate": 0, "sharpe": 0, "error": str(e)}


def calculate_score(train_result: dict, val_result: dict) -> float:
    """Calculate robust score combining train and validation."""
    train_pnl = train_result.get("pnl_pct", 0)
    val_pnl = val_result.get("pnl_pct", 0)
    train_trades = train_result.get("trades", 0)
    val_trades = val_result.get("trades", 0)

    # Need at least some trades
    if train_trades < 3 or val_trades < 1:
        return -999

    # Score: weighted PnL with trade count bonus
    # Penalize if validation is much worse than train (overfitting)
    overfit_penalty = 0
    if train_pnl > 0 and val_pnl < train_pnl * 0.5:
        overfit_penalty = (train_pnl - val_pnl) * 2

    score = (
        train_pnl * 0.4  # 40% weight on training
        + val_pnl * 0.6  # 60% weight on validation
        + min(train_trades, 20) * 0.02  # Bonus for trades
        + min(val_trades, 10) * 0.03
        - overfit_penalty
    )

    return score


def generate_candidates() -> list:
    """Generate parameter candidates to test."""
    candidates = []

    # Strategy combinations
    strategy_combos = [
        ["momentum_flow"],
        ["absorption_reversal"],
        ["momentum_flow", "absorption_reversal"],
        ["momentum"],
    ]

    # L2 delta thresholds
    l2_deltas = [3000, 5000, 7000]

    # L2 imbalance thresholds
    l2_imbalances = [0.03, 0.05, 0.08]

    # Regime filters
    regime_filters = [
        ["TRENDING"],
        ["TRENDING", "MIXED"],
        ["MIXED"],
    ]

    # Confidence thresholds
    confidences = [55, 60]

    # ATR multipliers
    atr_mults = [1.5, 1.8, 2.0]

    id_counter = 0
    for strategies in strategy_combos:
        for l2_delta in l2_deltas:
            for l2_imb in l2_imbalances:
                for regime in regime_filters:
                    for conf in confidences:
                        for atr in atr_mults:
                            id_counter += 1
                            candidates.append(
                                {
                                    "id": f"wf_{id_counter:03d}",
                                    "config": {
                                        "strategy_selection_mode": "all_enabled",
                                        "max_active_strategies": 2,
                                        "min_active_bars_before_switch": 8,
                                        "switch_cooldown_bars": 2,
                                        "flow_bias_enabled": True,
                                        "use_ohlcv_fallbacks": True,
                                        "enabled_strategies": strategies,
                                        "l2_min_delta": float(l2_delta),
                                        "l2_min_imbalance": l2_imb,
                                        "l2_min_signed_aggression": 0.1,
                                        "l2_min_directional_consistency": 0.4,
                                        "regime_filter": regime,
                                        "base_threshold": 55.0,
                                        "min_confirming_sources": 2,
                                        "min_confidence": float(conf),
                                        "atr_stop_multiplier": atr,
                                        "rr_ratio": 2.0,
                                        "trading_hours": [9, 10, 11, 12],
                                        "trailing_stop_pct": 0.5,
                                        "time_exit_bars": 35,
                                    },
                                }
                            )

    print(f"Generated {len(candidates)} candidates")
    return candidates


async def run_walk_forward_tuning():
    """Run walk-forward tuning."""
    print("=" * 80)
    print("WALK-FORWARD TUNING FOR MU")
    print("=" * 80)
    print(f"\nTrain:   {TRAIN_START} to {TRAIN_END}")
    print(f"Val:     {VAL_START} to {VAL_END}")
    print(f"Test:    {TEST_START} to {TEST_END} (holdout)")

    candidates = generate_candidates()

    results = []
    best_score = -999
    best_candidate = None

    print(f"\nEvaluating {len(candidates)} candidates...")

    async with httpx.AsyncClient() as client:
        # Check server health
        try:
            health = await client.get(f"{RUNNER_API_URL}/api/health", timeout=5.0)
            if health.status_code != 200:
                print("Server not healthy, exiting")
                return None
            print("Server is healthy\n")
        except Exception as e:
            print(f"Cannot connect to server: {e}")
            return None

        for i, candidate in enumerate(candidates):
            if (i + 1) % 10 == 0:
                print(f"\nProgress: {i+1}/{len(candidates)}")

            # Run on training period
            train_result = await run_backtest(
                client,
                TRAIN_START,
                TRAIN_END,
                candidate["config"],
                label=f"[{candidate['id']}] train",
            )

            # Skip if no trades in training
            if train_result["trades"] < 2:
                continue

            # Run on validation period
            val_result = await run_backtest(
                client,
                VAL_START,
                VAL_END,
                candidate["config"],
                label=f"[{candidate['id']}] val",
            )

            # Calculate score
            score = calculate_score(train_result, val_result)

            result = {
                "id": candidate["id"],
                "config": candidate["config"],
                "train": train_result,
                "val": val_result,
                "score": score,
            }
            results.append(result)

            if score > best_score:
                best_score = score
                best_candidate = result
                print(f"  New best: {candidate['id']} score={score:.4f}")

    # Sort by score
    results.sort(key=lambda x: x["score"], reverse=True)

    print("\n" + "=" * 80)
    print("TOP 10 CANDIDATES")
    print("=" * 80)

    for i, r in enumerate(results[:10]):
        print(f"\n{i+1}. {r['id']} (score: {r['score']:.4f})")
        print(
            f"   Train: PnL={r['train']['pnl_pct']:.2f}%, trades={r['train']['trades']}, WR={r['train']['win_rate']:.1f}%"
        )
        print(
            f"   Val:   PnL={r['val']['pnl_pct']:.2f}%, trades={r['val']['trades']}, WR={r['val']['win_rate']:.1f}%"
        )
        print(f"   Strategies: {r['config']['enabled_strategies']}")
        print(
            f"   L2 Delta: {r['config']['l2_min_delta']}, Imbalance: {r['config']['l2_min_imbalance']}"
        )

    # Test best candidate on holdout
    if best_candidate:
        print("\n" + "=" * 80)
        print("TESTING BEST CANDIDATE ON HOLDOUT")
        print("=" * 80)

        async with httpx.AsyncClient() as client:
            test_result = await run_backtest(
                client,
                TEST_START,
                TEST_END,
                best_candidate["config"],
                label="[BEST] test",
            )

        best_candidate["test"] = test_result

        print(f"\nBest Candidate: {best_candidate['id']}")
        print(
            f"  Train: PnL={best_candidate['train']['pnl_pct']:.2f}%, trades={best_candidate['train']['trades']}"
        )
        print(
            f"  Val:   PnL={best_candidate['val']['pnl_pct']:.2f}%, trades={best_candidate['val']['trades']}"
        )
        print(
            f"  Test:  PnL={test_result['pnl_pct']:.2f}%, trades={test_result['trades']}"
        )

    # Save results
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "splits": {
            "train": {"start": TRAIN_START, "end": TRAIN_END},
            "validation": {"start": VAL_START, "end": VAL_END},
            "test": {"start": TEST_START, "end": TEST_END},
        },
        "total_candidates": len(candidates),
        "evaluated_candidates": len(results),
        "results": results[:20],  # Top 20
        "best": best_candidate,
    }

    output_path = Path("reports/mu_walk_forward_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nResults saved to {output_path}")

    return best_candidate


async def main():
    best = await run_walk_forward_tuning()

    if best:
        print("\n" + "=" * 80)
        print("RECOMMENDED CONFIGURATION")
        print("=" * 80)
        print(json.dumps(best["config"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
