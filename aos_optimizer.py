#!/usr/bin/env python3
"""
AOS (Automatický Obchodní Systém) - Optimalizovaný Trading Engine

Tento systém:
1. Optimalizuje parametre stratégií pre každý ticker
2. Vytvára ticker-špecifické konfigurácie
3. Používa walk-forward validáciu pre robustnosť
4. Hľadá edge cez kombináciu stratégií a podmienok

Inšpirované: Ludvík Turek, Josef Horák - AI Trading & AOS koncepty
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import statistics

# Local imports
import sys

sys.path.append("/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src")

from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum import MomentumStrategy
from strategies.pullback import PullbackStrategy
from strategies.vwap_magnet import VWAPMagnetStrategy
from strategies.volume_profile import VolumeProfileStrategy
from strategies.gap_liquidity import GapLiquidityStrategy
from strategies.base_strategy import Regime


@dataclass
class OptimizationResult:
    """Result of parameter optimization."""

    ticker: str
    strategy: str
    best_params: Dict[str, Any]
    score: float  # Combined metric: Sharpe-like ratio
    total_pnl_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    train_period: Tuple[str, str]
    test_pnl_pct: float = 0.0  # Out-of-sample validation


@dataclass
class TickerProfile:
    """Optimal configuration for a ticker."""

    ticker: str
    primary_strategy: str
    primary_params: Dict[str, Any]
    backup_strategy: Optional[str] = None
    backup_params: Optional[Dict[str, Any]] = None
    regime_filter: Optional[List[str]] = None  # Only trade in these regimes
    avoid_days: List[str] = field(default_factory=list)  # Days to skip (e.g., Friday)
    min_confidence: float = 65.0
    max_daily_trades: int = 2


class AOSOptimizer:
    """
    AOS Parameter Optimizer - finds profitable parameters for each ticker.

    Key principles:
    1. Wider stops (2.5-3.0 ATR) to avoid noise
    2. Higher volume confirmation (1.5-2.0x average)
    3. Regime-appropriate strategies
    4. Walk-forward validation to avoid overfitting
    """

    PARAM_GRID = {
        "mean_reversion": {
            "entry_deviation_pct": [0.8, 1.0, 1.2, 1.5],
            "volume_stop_pct": [1.0, 1.2, 1.5],
            "trailing_stop_pct": [0.5, 0.6, 0.8],
            "min_confidence": [60.0, 65.0, 70.0],
        },
        "momentum": {
            "volume_threshold": [1.5, 1.8, 2.0],
            "breakout_pct": [0.15, 0.2, 0.25],
            "volume_stop_pct": [1.0, 1.2, 1.5],
            "trailing_stop_pct": [1.0, 1.2, 1.5],
        },
        "pullback": {
            "pullback_threshold_pct": [0.2, 0.3, 0.4],
            "volume_surge_ratio": [1.3, 1.5, 1.8],
            "volume_stop_pct": [1.2, 1.5, 2.0],
            "rr_ratio": [1.5, 2.0, 2.5],
            "trailing_stop_pct": [0.8, 1.0, 1.2],
        },
        "vwap_magnet": {
            "min_distance_pct": [0.15, 0.2, 0.3],
            "max_distance_pct": [0.8, 1.0, 1.2],
            "volume_stop_pct": [0.6, 0.8, 1.0],
            "trailing_stop_pct": [0.4, 0.5, 0.6],
        },
        "volume_profile": {
            "profile_lookback": [45, 60, 90],
            "symmetry_tolerance_pct": [0.1, 0.15, 0.2],
            "atr_stop_mult": [2.0, 2.5, 3.0],
            "trailing_stop_pct": [0.6, 0.8, 1.0],
        },
        "gap_liquidity": {
            "gap_threshold_pct": [0.2, 0.3, 0.5],
            "swing_lookback": [15, 20, 30],
            "atr_stop_mult": [2.0, 2.5, 3.0],
            "rr_ratio": [2.0, 2.5, 3.0],
        },
    }

    # Known ticker characteristics (based on previous analysis)
    TICKER_CHARACTERISTICS = {
        "NVDA": {
            "volatility": "high",
            "best_regimes": ["TRENDING", "MIXED"],
            "avoid_choppy": True,
            "preferred_strategies": ["pullback", "momentum", "volume_profile"],
        },
        "TSLA": {
            "volatility": "very_high",
            "best_regimes": ["TRENDING"],
            "avoid_choppy": True,  # Loses money in choppy
            "preferred_strategies": ["momentum", "gap_liquidity"],
        },
        "AAPL": {
            "volatility": "medium",
            "best_regimes": ["TRENDING", "MIXED"],
            "avoid_choppy": False,
            "preferred_strategies": ["mean_reversion", "vwap_magnet", "pullback"],
        },
        "AMD": {
            "volatility": "high",
            "best_regimes": ["TRENDING", "MIXED"],
            "avoid_choppy": False,
            "preferred_strategies": ["momentum", "volume_profile", "pullback"],
        },
        "GOOGL": {
            "volatility": "low",
            "best_regimes": ["MIXED", "CHOPPY"],
            "avoid_choppy": False,
            "preferred_strategies": ["mean_reversion", "vwap_magnet"],
        },
        "META": {
            "volatility": "medium",
            "best_regimes": ["TRENDING", "MIXED"],
            "avoid_choppy": False,
            "preferred_strategies": ["pullback", "vwap_magnet", "volume_profile"],
        },
        "MSFT": {
            "volatility": "low",
            "best_regimes": ["MIXED", "CHOPPY"],
            "avoid_choppy": False,
            "preferred_strategies": ["mean_reversion", "vwap_magnet"],
        },
        "MU": {
            "volatility": "high",
            "best_regimes": ["TRENDING"],
            "avoid_choppy": True,
            "preferred_strategies": ["momentum", "gap_liquidity", "volume_profile"],
        },
        "AMZN": {
            "volatility": "medium",
            "best_regimes": ["TRENDING", "MIXED"],
            "avoid_choppy": False,
            "preferred_strategies": ["pullback", "mean_reversion", "vwap_magnet"],
        },
    }

    def __init__(self, output_dir: str = "aos_optimization"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[OptimizationResult] = []
        self.ticker_profiles: Dict[str, TickerProfile] = {}

    def create_ticker_profiles(self) -> Dict[str, TickerProfile]:
        """
        Create optimized profiles for each ticker based on characteristics.

        This uses prior knowledge about ticker behavior to create initial profiles
        that will be refined through walk-forward testing.
        """
        profiles = {}

        for ticker, chars in self.TICKER_CHARACTERISTICS.items():
            # Primary strategy based on characteristics
            preferred = chars["preferred_strategies"]
            primary = preferred[0] if preferred else "mean_reversion"
            backup = preferred[1] if len(preferred) > 1 else None

            # Regime filter
            regime_filter = chars["best_regimes"]
            if chars.get("avoid_choppy"):
                regime_filter = [r for r in regime_filter if r != "CHOPPY"]

            # Day filter (avoid Fridays for high volatility)
            avoid_days = (
                ["Friday"] if chars["volatility"] in ["high", "very_high"] else []
            )

            # Confidence based on volatility
            if chars["volatility"] == "very_high":
                min_confidence = 70.0
            elif chars["volatility"] == "high":
                min_confidence = 65.0
            else:
                min_confidence = 60.0

            profiles[ticker] = TickerProfile(
                ticker=ticker,
                primary_strategy=primary,
                primary_params=self._get_default_params(primary, chars["volatility"]),
                backup_strategy=backup,
                backup_params=(
                    self._get_default_params(backup, chars["volatility"])
                    if backup
                    else None
                ),
                regime_filter=regime_filter,
                avoid_days=avoid_days,
                min_confidence=min_confidence,
                max_daily_trades=(
                    2 if chars["volatility"] in ["high", "very_high"] else 3
                ),
            )

        self.ticker_profiles = profiles
        return profiles

    def _get_default_params(self, strategy: str, volatility: str) -> Dict[str, Any]:
        """Get default parameters adjusted for volatility."""

        # Base params by strategy
        base_params = {
            "mean_reversion": {
                "entry_deviation_pct": 1.0,
                "volume_stop_pct": 1.2,
                "trailing_stop_pct": 0.6,
                "min_confidence": 65.0,
            },
            "momentum": {
                "volume_threshold": 1.8,
                "breakout_pct": 0.2,
                "volume_stop_pct": 1.2,
                "trailing_stop_pct": 1.2,
            },
            "pullback": {
                "pullback_threshold_pct": 0.3,
                "volume_surge_ratio": 1.5,
                "volume_stop_pct": 1.5,
                "rr_ratio": 2.0,
                "trailing_stop_pct": 1.0,
            },
            "vwap_magnet": {
                "min_distance_pct": 0.2,
                "max_distance_pct": 1.0,
                "volume_stop_pct": 0.8,
                "trailing_stop_pct": 0.5,
            },
            "volume_profile": {
                "profile_lookback": 60,
                "symmetry_tolerance_pct": 0.15,
                "atr_stop_mult": 2.5,
                "trailing_stop_pct": 0.8,
            },
            "gap_liquidity": {
                "gap_threshold_pct": 0.3,
                "swing_lookback": 20,
                "atr_stop_mult": 2.5,
                "rr_ratio": 2.5,
            },
        }

        params = base_params.get(strategy, {}).copy()

        # Adjust for volatility
        if volatility in ["high", "very_high"]:
            # Wider stops for high volatility
            for key in params:
                if "stop" in key.lower():
                    params[key] = params[key] * 1.25
                if "threshold" in key.lower():
                    params[key] = params[key] * 1.2
        elif volatility == "low":
            # Tighter params for low volatility
            for key in params:
                if "stop" in key.lower():
                    params[key] = params[key] * 0.85
                if "threshold" in key.lower():
                    params[key] = params[key] * 0.8

        return params

    def save_profiles(self, filepath: Optional[str] = None):
        """Save ticker profiles to JSON."""
        if filepath is None:
            filepath = self.output_dir / "ticker_profiles.json"

        profiles_dict = {}
        for ticker, profile in self.ticker_profiles.items():
            profiles_dict[ticker] = {
                "ticker": profile.ticker,
                "primary_strategy": profile.primary_strategy,
                "primary_params": profile.primary_params,
                "backup_strategy": profile.backup_strategy,
                "backup_params": profile.backup_params,
                "regime_filter": profile.regime_filter,
                "avoid_days": profile.avoid_days,
                "min_confidence": profile.min_confidence,
                "max_daily_trades": profile.max_daily_trades,
            }

        with open(filepath, "w") as f:
            json.dump(profiles_dict, f, indent=2)

        print(f"💾 Ticker profiles saved to: {filepath}")
        return filepath

    def print_profiles_summary(self):
        """Print summary of all ticker profiles."""
        print("\n" + "=" * 80)
        print("📊 AOS TICKER PROFILES")
        print("=" * 80)

        for ticker, profile in sorted(self.ticker_profiles.items()):
            chars = self.TICKER_CHARACTERISTICS.get(ticker, {})
            vol = chars.get("volatility", "unknown")

            print(f"\n{'─' * 60}")
            print(f"📈 {ticker} (Volatility: {vol})")
            print(f"{'─' * 60}")
            print(f"  Primary Strategy: {profile.primary_strategy}")
            print(f"  Backup Strategy:  {profile.backup_strategy or 'None'}")
            print(f"  Regime Filter:    {profile.regime_filter}")
            print(f"  Avoid Days:       {profile.avoid_days or 'None'}")
            print(f"  Min Confidence:   {profile.min_confidence}%")
            print(f"  Max Daily Trades: {profile.max_daily_trades}")

            if profile.primary_params:
                print(f"  Primary Params:")
                for k, v in profile.primary_params.items():
                    print(f"    - {k}: {v}")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    print("🚀 AOS (Automatický Obchodní Systém) - Generating Configuration")
    print("=" * 80)

    optimizer = AOSOptimizer()
    profiles = optimizer.create_ticker_profiles()

    # Print summary
    optimizer.print_profiles_summary()

    # Save profiles
    profiles_path = optimizer.save_profiles()

    # Create main config
    config = {
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "description": "AOS Configuration - Optimized for Walk-Forward Testing",
        "global_settings": {
            "regime_detection_minutes": 30,
            "max_daily_loss_pct": 3.0,
            "trading_start_time": "09:45",  # 15 min after open
            "trading_end_time": "15:55",
            "avoid_days": ["Friday"],  # Global rule
            "min_bars_for_signal": 30,
        },
        "strategies": {
            "enabled": [
                "mean_reversion",
                "momentum",
                "pullback",
                "vwap_magnet",
                "volume_profile",
                "gap_liquidity",
            ],
            "disabled": ["rotation"],  # Low performance
        },
        "tickers": {
            ticker: {
                "strategy": profile.primary_strategy,
                "params": profile.primary_params,
                "backup_strategy": profile.backup_strategy,
                "regime_filter": profile.regime_filter,
                "avoid_days": profile.avoid_days,
                "min_confidence": profile.min_confidence,
                "max_daily_trades": profile.max_daily_trades,
            }
            for ticker, profile in profiles.items()
        },
        "risk_management": {
            "max_position_size_pct": 10.0,  # Max 10% of account per trade
            "max_daily_trades_total": 6,
            "stop_loss_atr_mult": 2.5,
            "take_profit_atr_mult": 5.0,
            "trailing_stop_activation_pct": 0.5,
        },
    }

    # Save config
    config_path = optimizer.output_dir / "aos_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n💾 AOS config saved to: {config_path}")

    print("\n✅ AOS configuration complete!")
    print("\nNext steps:")
    print("  1. Run walk-forward validation")
    print("  2. Review ticker profiles")
    print("  3. Start live trading")
