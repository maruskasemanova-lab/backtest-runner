#!/usr/bin/env python3
"""Validate MU configuration on holdout period."""

import asyncio
import json
import httpx

HOLDOUT_START = "2026-01-09"
HOLDOUT_END = "2026-02-10"
TICKER = "MU"
RUNNER_API_URL = "http://localhost:8000"

# Best configuration from previous tuning
BEST_CONFIG = {
    "strategy_selection_mode": "all_enabled",
    "max_active_strategies": 2,
    "min_active_bars_before_switch": 8,
    "switch_cooldown_bars": 2,
    "flow_bias_enabled": True,
    "use_ohlcv_fallbacks": True,
    "enabled_strategies": ["absorption_reversal", "momentum_flow"],
    "l2_min_delta": 5000.0,
    "l2_min_imbalance": 0.05,
    "l2_min_signed_aggression": 0.1,
    "l2_min_directional_consistency": 0.4,
    "regime_filter": ["MIXED", "TRENDING"],
    "base_threshold": 55.0,
    "min_confirming_sources": 2,
    "min_confidence": 60.0,
    "atr_stop_multiplier": 1.8,
    "rr_ratio": 2.0,
    "trading_hours": [9, 10, 11, 12],
    "trailing_stop_pct": 0.5,
    "time_exit_bars": 35
}


async def run_holdout_test():
    """Run holdout validation."""
    print("=" * 80)
    print("HOLDOUT VALIDATION FOR MU")
    print("=" * 80)
    print(f"\nHoldout Period: {HOLDOUT_START} to {HOLDOUT_END}")
    print(f"Configuration: {BEST_CONFIG['enabled_strategies']}")
    
    async with httpx.AsyncClient() as client:
        # Check health
        try:
            health = await client.get(f"{RUNNER_API_URL}/api/health", timeout=5.0)
            if health.status_code != 200:
                print("Server not healthy")
                return
            print("Server is healthy\n")
        except Exception as e:
            print(f"Cannot connect: {e}")
            return
        
        # Start run
        run_config = {
            "run_id": "mu_holdout_validation",
            "ticker": TICKER,
            "date_from": HOLDOUT_START,
            "date_to": HOLDOUT_END,
            "l2_only": True,
            "l2_confirm_enabled": True,
            "comparable_mode": True,
            "apply_ticker_overrides_on_start": False,
            "apply_aos_optimizations_on_start": False,
            "account_size_usd": 100,
            "risk_per_trade_pct": 2.0,
        }
        
        # Merge config
        for key, value in BEST_CONFIG.items():
            run_config[key] = value
        
        print("Starting holdout backtest...")
        start_response = await client.post(
            f"{RUNNER_API_URL}/api/run/start",
            json=run_config,
            timeout=30.0,
        )
        
        if start_response.status_code != 200:
            print(f"Start failed: {start_response.status_code} - {start_response.text[:500]}")
            return
        
        start_data = start_response.json()
        run_id = start_data.get("run_id", "")
        print(f"Run ID: {run_id}")
        
        # Play
        play_response = await client.post(
            f"{RUNNER_API_URL}/api/run/{run_id}/{TICKER}/{HOLDOUT_START}/play",
            json={"speed": "max"},
            timeout=120.0,
        )
        
        if play_response.status_code != 200:
            print(f"Play failed: {play_response.text[:200]}")
            return
        
        print("Running backtest...")
        
        # Poll for completion
        for i in range(120):
            await asyncio.sleep(1)
            
            status_response = await client.get(
                f"{RUNNER_API_URL}/api/run/{run_id}/status",
                timeout=10.0,
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                state = status_data.get("state", "")
                
                if state == "COMPLETED":
                    # Get performance
                    perf_response = await client.get(
                        f"{RUNNER_API_URL}/api/run/{run_id}/performance",
                        timeout=10.0,
                    )
                    
                    if perf_response.status_code == 200:
                        perf = perf_response.json()
                        print("\n" + "=" * 80)
                        print("HOLDOUT RESULTS")
                        print("=" * 80)
                        print(f"PnL: {perf.get('total_pnl_pct', 0):.2f}%")
                        print(f"Trades: {perf.get('total_trades', 0)}")
                        print(f"Win Rate: {perf.get('win_rate_pct', 0):.1f}%")
                        print(f"Sharpe: {perf.get('sharpe_ratio', 0):.2f}")
                        
                        # Save results
                        result = {
                            "period": "holdout",
                            "date_from": HOLDOUT_START,
                            "date_to": HOLDOUT_END,
                            "config": BEST_CONFIG,
                            "results": perf
                        }
                        with open("reports/mu_holdout_validation.json", "w") as f:
                            json.dump(result, f, indent=2)
                        print(f"\nResults saved to reports/mu_holdout_validation.json")
                    break
                elif state in ["FAILED", "ERROR"]:
                    print(f"Run {state}")
                    break
            
            if (i + 1) % 10 == 0:
                print(f"  Waiting... ({i+1}s)")


if __name__ == "__main__":
    asyncio.run(run_holdout_test())
