#!/usr/bin/env python3
"""
MU Strategy Fine-Tuning Script

Systematic approach to tune MU ticker strategies:
1. Test each strategy individually
2. Walk-forward validation (train/val/test splits)
3. Regime-aware parameter optimization
4. Document results and find robust configuration

Usage:
    python scripts/tune_mu_strategies.py
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
RUNNER_API_URL = os.getenv("RUNNER_API_URL", "http://localhost:8002")
STRATEGY_API_URL = os.getenv("STRATEGY_API_URL", "http://localhost:8001")

# MU L2 data coverage
MU_DATE_FROM = "2025-11-03"
MU_DATE_TO = "2026-02-10"
MU_L2_DAYS = 46

# Walk-forward splits (chronological)
# Split 46 days into: Train (60%) = 28 days, Val (20%) = 9 days, Test (20%) = 9 days
SPLITS = {
    "train": {"from": "2025-11-03", "to": "2025-12-12"},  # ~28 days
    "val": {"from": "2025-12-15", "to": "2026-01-08"},    # ~9 days  
    "test": {"from": "2026-01-09", "to": "2026-02-10"},   # ~9 days (holdout)
}

# Strategies to test individually
STRATEGIES = [
    "momentum_flow",
    "absorption_reversal",
    "exhaustion_fade",
]

# Parameter grids for each strategy
PARAMETER_GRIDS = {
    "momentum_flow": {
        "min_signed_aggression": [0.04, 0.06, 0.08, 0.10, 0.12],
        "min_directional_consistency": [0.40, 0.50, 0.55, 0.60],
        "min_imbalance": [0.02, 0.03, 0.05, 0.08],
        "min_sweep_intensity": [0.05, 0.07, 0.10],
        "atr_stop_multiplier": [1.0, 1.2, 1.4, 1.6],
        "rr_ratio": [1.5, 2.0, 2.5],
        "trailing_stop_pct": [0.4, 0.5, 0.6, 0.8],
    },
    "absorption_reversal": {
        "min_absorption_rate": [0.3, 0.4, 0.5, 0.6],
        "min_delta_divergence": [0.2, 0.3, 0.4],
        "min_book_imbalance": [0.1, 0.15, 0.2],
        "atr_stop_multiplier": [1.2, 1.4, 1.6],
        "rr_ratio": [1.5, 2.0, 2.5],
    },
    "exhaustion_fade": {
        "min_exhaustion_signals": [2, 3, 4],
        "min_volume_spike": [1.5, 2.0, 2.5],
        "min_reversal_candle_size": [0.3, 0.4, 0.5],
        "atr_stop_multiplier": [1.0, 1.2, 1.4],
        "rr_ratio": [1.2, 1.5, 2.0],
    },
}

# L2 threshold combinations to test
L2_THRESHOLDS = [
    {"l2_min_delta": 2000, "l2_min_imbalance": 0.03, "l2_min_signed_aggression": 0.03, "l2_min_directional_consistency": 0.25},
    {"l2_min_delta": 3000, "l2_min_imbalance": 0.05, "l2_min_signed_aggression": 0.05, "l2_min_directional_consistency": 0.30},
    {"l2_min_delta": 5000, "l2_min_imbalance": 0.08, "l2_min_signed_aggression": 0.08, "l2_min_directional_consistency": 0.40},
]

# Regime filters to test
REGIME_FILTERS = [
    ["TRENDING"],
    ["TRENDING", "MIXED"],
    ["TRENDING", "MIXED", "CHOPPY"],
]


@dataclass
class TuningResult:
    """Result of a single tuning trial."""
    trial_id: str
    strategy: str
    params: Dict[str, Any]
    l2_thresholds: Dict[str, Any]
    regime_filter: List[str]
    date_from: str
    date_to: str
    total_trades: int = 0
    total_pnl_pct: float = 0.0
    win_rate: float = 0.0
    avg_pnl_per_trade: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0
    error: str = ""


@dataclass
class StrategyTuningReport:
    """Complete tuning report for a strategy."""
    strategy: str
    train_results: List[TuningResult] = field(default_factory=list)
    val_results: List[TuningResult] = field(default_factory=list)
    test_results: List[TuningResult] = field(default_factory=list)
    best_train: Optional[TuningResult] = None
    best_val: Optional[TuningResult] = None
    best_test: Optional[TuningResult] = None
    recommended_config: Dict[str, Any] = field(default_factory=dict)


async def run_backtest(
    client: httpx.AsyncClient,
    ticker: str,
    date_from: str,
    date_to: str,
    strategy: str,
    params: Dict[str, Any],
    l2_thresholds: Dict[str, Any],
    regime_filter: List[str],
) -> Dict[str, Any]:
    """Run a single backtest and return results."""
    
    run_config = {
        "ticker": ticker,
        "date_from": date_from,
        "date_to": date_to,
        "l2_only": True,
        "l2_confirm_enabled": True,
        "comparable_mode": True,
        "apply_ticker_overrides_on_start": False,
        "apply_aos_optimizations_on_start": False,
        "strategy_selection_mode": "all_enabled",
        "max_active_strategies": 1,
        "account_size_usd": 100,
        "risk_per_trade_pct": 2.0,
    }
    
    # Add strategy params
    for key, value in params.items():
        run_config[key] = value
    
    # Add L2 thresholds
    for key, value in l2_thresholds.items():
        run_config[key] = value
    
    # Add regime filter
    run_config["regime_filter"] = regime_filter
    
    try:
        # Start run
        start_response = await client.post(
            f"{RUNNER_API_URL}/api/run/start",
            json=run_config,
            timeout=30.0,
        )
        
        if start_response.status_code != 200:
            return {"error": f"Start failed: {start_response.text}"}
        
        start_data = start_response.json()
        run_id = start_data.get("run_id", "")
        
        if not run_id:
            return {"error": "No run_id returned"}
        
        # Play the run
        play_response = await client.post(
            f"{RUNNER_API_URL}/api/run/{run_id}/{ticker}/{date_from}/play",
            json={"speed": "max"},
            timeout=120.0,
        )
        
        if play_response.status_code != 200:
            return {"error": f"Play failed: {play_response.text}"}
        
        # Wait for completion (poll)
        for _ in range(60):  # Max 60 seconds wait
            await asyncio.sleep(1)
            
            summary_response = await client.get(
                f"{RUNNER_API_URL}/api/run/{run_id}/{ticker}/{date_from}/summary",
                timeout=10.0,
            )
            
            if summary_response.status_code == 200:
                summary = summary_response.json()
                if summary.get("completed", False):
                    return {
                        "total_trades": summary.get("total_trades", 0),
                        "total_pnl_pct": summary.get("total_pnl_pct", 0.0),
                        "win_rate": summary.get("win_rate", 0.0),
                        "avg_pnl_per_trade": summary.get("avg_pnl_pct", 0.0),
                        "max_drawdown": summary.get("max_drawdown_pct", 0.0),
                    }
        
        return {"error": "Timeout waiting for completion"}
        
    except Exception as e:
        return {"error": str(e)}


async def tune_strategy(
    client: httpx.AsyncClient,
    strategy: str,
    split: str,
) -> List[TuningResult]:
    """Tune a single strategy on a given split."""
    
    results = []
    date_from = SPLITS[split]["from"]
    date_to = SPLITS[split]["to"]
    
    param_grid = PARAMETER_GRIDS.get(strategy, {})
    
    # Generate parameter combinations (sample, don't exhaust)
    import itertools
    param_names = list(param_grid.keys())
    param_values = [param_grid[name][:2] for name in param_names]  # Limit to first 2 values
    
    combinations = list(itertools.product(*param_values))
    logger.info(f"Testing {len(combinations)} parameter combinations for {strategy} on {split}")
    
    trial_count = 0
    for combo in combinations[:20]:  # Limit to 20 trials per strategy per split
        params = dict(zip(param_names, combo))
        
        for l2_thresh in L2_THRESHOLDS[:2]:  # Limit L2 combinations
            for regime in REGIME_FILTERS[:2]:  # Limit regime combinations
                trial_count += 1
                trial_id = f"{strategy}_{split}_{trial_count}"
                
                logger.info(f"Running trial {trial_id}")
                
                backtest_result = await run_backtest(
                    client=client,
                    ticker="MU",
                    date_from=date_from,
                    date_to=date_to,
                    strategy=strategy,
                    params=params,
                    l2_thresholds=l2_thresh,
                    regime_filter=regime,
                )
                
                result = TuningResult(
                    trial_id=trial_id,
                    strategy=strategy,
                    params=params,
                    l2_thresholds=l2_thresh,
                    regime_filter=regime,
                    date_from=date_from,
                    date_to=date_to,
                )
                
                if "error" in backtest_result:
                    result.error = backtest_result["error"]
                    logger.warning(f"Trial {trial_id} error: {result.error}")
                else:
                    result.total_trades = backtest_result.get("total_trades", 0)
                    result.total_pnl_pct = backtest_result.get("total_pnl_pct", 0.0)
                    result.win_rate = backtest_result.get("win_rate", 0.0)
                    result.avg_pnl_per_trade = backtest_result.get("avg_pnl_per_trade", 0.0)
                    result.max_drawdown = backtest_result.get("max_drawdown", 0.0)
                    
                    logger.info(
                        f"Trial {trial_id}: trades={result.total_trades}, "
                        f"pnl={result.total_pnl_pct:.2f}%, wr={result.win_rate:.1f}%"
                    )
                
                results.append(result)
                
                # Small delay between trials
                await asyncio.sleep(0.5)
    
    return results


async def run_tuning():
    """Run the complete tuning process."""
    
    logger.info("=" * 60)
    logger.info("MU STRATEGY FINE-TUNING")
    logger.info("=" * 60)
    logger.info(f"Date range: {MU_DATE_FROM} to {MU_DATE_TO}")
    logger.info(f"L2 days available: {MU_L2_DAYS}")
    logger.info(f"Splits: train={SPLITS['train']}, val={SPLITS['val']}, test={SPLITS['test']}")
    logger.info(f"Strategies to test: {STRATEGIES}")
    
    async with httpx.AsyncClient() as client:
        # Check API availability
        try:
            health = await client.get(f"{RUNNER_API_URL}/health", timeout=5.0)
            if health.status_code != 200:
                logger.error(f"Runner API not healthy: {health.status_code}")
                return
        except Exception as e:
            logger.error(f"Cannot connect to Runner API: {e}")
            return
        
        logger.info("Runner API is healthy")
        
        reports = []
        
        for strategy in STRATEGIES:
            logger.info(f"\n{'='*60}")
            logger.info(f"TUNING STRATEGY: {strategy}")
            logger.info("=" * 60)
            
            report = StrategyTuningReport(strategy=strategy)
            
            # Train phase
            logger.info(f"\n--- TRAIN PHASE ({SPLITS['train']}) ---")
            train_results = await tune_strategy(client, strategy, "train")
            report.train_results = train_results
            
            if train_results:
                valid_results = [r for r in train_results if not r.error and r.total_trades > 0]
                if valid_results:
                    report.best_train = max(valid_results, key=lambda r: r.total_pnl_pct)
                    logger.info(f"Best train: {report.best_train.trial_id} pnl={report.best_train.total_pnl_pct:.2f}%")
            
            # Validation phase (only if we have a good train result)
            if report.best_train:
                logger.info(f"\n--- VALIDATION PHASE ({SPLITS['val']}) ---")
                val_results = await tune_strategy(client, strategy, "val")
                report.val_results = val_results
                
                if val_results:
                    valid_results = [r for r in val_results if not r.error and r.total_trades > 0]
                    if valid_results:
                        report.best_val = max(valid_results, key=lambda r: r.total_pnl_pct)
                        logger.info(f"Best val: {report.best_val.trial_id} pnl={report.best_val.total_pnl_pct:.2f}%")
            
            # Test phase (only if we have good val result)
            if report.best_val:
                logger.info(f"\n--- TEST PHASE ({SPLITS['test']}) ---")
                test_results = await tune_strategy(client, strategy, "test")
                report.test_results = test_results
                
                if test_results:
                    valid_results = [r for r in test_results if not r.error and r.total_trades > 0]
                    if valid_results:
                        report.best_test = max(valid_results, key=lambda r: r.total_pnl_pct)
                        logger.info(f"Best test: {report.best_test.trial_id} pnl={report.best_test.total_pnl_pct:.2f}%")
            
            # Build recommended config
            if report.best_val:
                report.recommended_config = {
                    "strategy": strategy,
                    "params": report.best_val.params,
                    "l2_thresholds": report.best_val.l2_thresholds,
                    "regime_filter": report.best_val.regime_filter,
                    "train_pnl": report.best_train.total_pnl_pct if report.best_train else 0,
                    "val_pnl": report.best_val.total_pnl_pct,
                    "test_pnl": report.best_test.total_pnl_pct if report.best_test else 0,
                }
            
            reports.append(report)
        
        # Generate final report
        logger.info("\n" + "=" * 60)
        logger.info("FINAL TUNING REPORT")
        logger.info("=" * 60)
        
        final_report = {
            "generated_at": datetime.utcnow().isoformat(),
            "ticker": "MU",
            "date_range": {"from": MU_DATE_FROM, "to": MU_DATE_TO},
            "splits": SPLITS,
            "strategies_tested": STRATEGIES,
            "strategy_reports": [],
        }
        
        for report in reports:
            strategy_report = {
                "strategy": report.strategy,
                "train_trials": len(report.train_results),
                "val_trials": len(report.val_results),
                "test_trials": len(report.test_results),
                "best_train": {
                    "trial_id": report.best_train.trial_id,
                    "pnl": report.best_train.total_pnl_pct,
                    "trades": report.best_train.total_trades,
                    "win_rate": report.best_train.win_rate,
                } if report.best_train else None,
                "best_val": {
                    "trial_id": report.best_val.trial_id,
                    "pnl": report.best_val.total_pnl_pct,
                    "trades": report.best_val.total_trades,
                    "win_rate": report.best_val.win_rate,
                } if report.best_val else None,
                "best_test": {
                    "trial_id": report.best_test.trial_id,
                    "pnl": report.best_test.total_pnl_pct,
                    "trades": report.best_test.total_trades,
                    "win_rate": report.best_test.win_rate,
                } if report.best_test else None,
                "recommended_config": report.recommended_config,
            }
            final_report["strategy_reports"].append(strategy_report)
            
            logger.info(f"\n{report.strategy}:")
            if report.best_train:
                logger.info(f"  Train: pnl={report.best_train.total_pnl_pct:.2f}%, trades={report.best_train.total_trades}, wr={report.best_train.win_rate:.1f}%")
            if report.best_val:
                logger.info(f"  Val:   pnl={report.best_val.total_pnl_pct:.2f}%, trades={report.best_val.total_trades}, wr={report.best_val.win_rate:.1f}%")
            if report.best_test:
                logger.info(f"  Test:  pnl={report.best_test.total_pnl_pct:.2f}%, trades={report.best_test.total_trades}, wr={report.best_test.win_rate:.1f}%")
        
        # Find best overall strategy
        best_strategy = None
        best_val_pnl = float("-inf")
        for report in reports:
            if report.best_val and report.best_val.total_pnl_pct > best_val_pnl:
                best_val_pnl = report.best_val.total_pnl_pct
                best_strategy = report
        
        if best_strategy:
            final_report["recommended_strategy"] = best_strategy.strategy
            final_report["recommended_config"] = best_strategy.recommended_config
            logger.info(f"\nRECOMMENDED: {best_strategy.strategy}")
            logger.info(f"Config: {json.dumps(best_strategy.recommended_config, indent=2)}")
        
        # Save report
        report_path = Path("reports/mu_tuning_report.json")
        with open(report_path, "w") as f:
            json.dump(final_report, f, indent=2, default=str)
        logger.info(f"\nReport saved to: {report_path}")
        
        return final_report


def main():
    """Main entry point."""
    logger.info("Starting MU Strategy Fine-Tuning...")
    asyncio.run(run_tuning())


if __name__ == "__main__":
    main()
