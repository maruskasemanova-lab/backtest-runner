"""
Performance Tracker - Tracks strategy performance per regime for adaptive selection.

This module provides comprehensive performance tracking for trading strategies
across different market regimes, enabling data-driven strategy selection.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json
from pathlib import Path


class Regime(Enum):
    """Market regime types."""
    TRENDING = "TRENDING"
    CHOPPY = "CHOPPY"
    MIXED = "MIXED"


@dataclass
class TradeRecord:
    """Single trade record with all relevant metrics."""
    trade_id: int
    strategy: str
    regime: str
    ticker: str
    date: str
    side: str  # 'long' or 'short'
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    pnl_pct: float
    pnl_dollars: float
    gross_pnl_pct: float
    total_costs: float
    exit_reason: str
    bars_held: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_id': self.trade_id,
            'strategy': self.strategy,
            'regime': self.regime,
            'ticker': self.ticker,
            'date': self.date,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'entry_time': self.entry_time,
            'exit_time': self.exit_time,
            'pnl_pct': round(self.pnl_pct, 4),
            'pnl_dollars': round(self.pnl_dollars, 4),
            'gross_pnl_pct': round(self.gross_pnl_pct, 4),
            'total_costs': round(self.total_costs, 4),
            'exit_reason': self.exit_reason,
            'bars_held': self.bars_held
        }


@dataclass
class StrategyPerformance:
    """Performance metrics for a strategy in a specific regime."""
    strategy: str
    regime: str
    
    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # PnL metrics
    total_pnl_pct: float = 0.0
    total_pnl_dollars: float = 0.0
    gross_pnl_pct: float = 0.0
    total_costs: float = 0.0
    
    # Trade lists for detailed analysis
    trades: List[TradeRecord] = field(default_factory=list)
    
    # Derived metrics (calculated on demand)
    _cached_win_rate: Optional[float] = None
    _cached_profit_factor: Optional[float] = None
    _cached_avg_win: Optional[float] = None
    _cached_avg_loss: Optional[float] = None
    _cached_max_drawdown: Optional[float] = None
    
    def add_trade(self, trade: TradeRecord):
        """Add a trade to this performance record."""
        self.trades.append(trade)
        self.total_trades += 1
        
        if trade.pnl_pct > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
            
        self.total_pnl_pct += trade.pnl_pct
        self.total_pnl_dollars += trade.pnl_dollars
        self.gross_pnl_pct += trade.gross_pnl_pct
        self.total_costs += trade.total_costs
        
        # Invalidate cache
        self._invalidate_cache()
    
    def _invalidate_cache(self):
        """Invalidate cached metrics."""
        self._cached_win_rate = None
        self._cached_profit_factor = None
        self._cached_avg_win = None
        self._cached_avg_loss = None
        self._cached_max_drawdown = None
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self._cached_win_rate is None:
            if self.total_trades == 0:
                self._cached_win_rate = 0.0
            else:
                self._cached_win_rate = (self.winning_trades / self.total_trades) * 100
        return self._cached_win_rate
    
    @property
    def profit_factor(self) -> float:
        """Calculate profit factor (gross wins / gross losses)."""
        if self._cached_profit_factor is None:
            total_wins = sum(t.pnl_pct for t in self.trades if t.pnl_pct > 0)
            total_losses = abs(sum(t.pnl_pct for t in self.trades if t.pnl_pct <= 0))
            
            if total_losses == 0:
                self._cached_profit_factor = float('inf') if total_wins > 0 else 0.0
            else:
                self._cached_profit_factor = total_wins / total_losses
        return self._cached_profit_factor
    
    @property
    def avg_win(self) -> float:
        """Calculate average winning trade."""
        if self._cached_avg_win is None:
            wins = [t.pnl_pct for t in self.trades if t.pnl_pct > 0]
            self._cached_avg_win = sum(wins) / len(wins) if wins else 0.0
        return self._cached_avg_win
    
    @property
    def avg_loss(self) -> float:
        """Calculate average losing trade."""
        if self._cached_avg_loss is None:
            losses = [t.pnl_pct for t in self.trades if t.pnl_pct <= 0]
            self._cached_avg_loss = sum(losses) / len(losses) if losses else 0.0
        return self._cached_avg_loss
    
    @property
    def avg_trade(self) -> float:
        """Calculate average trade PnL."""
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl_pct / self.total_trades
    
    @property
    def max_drawdown(self) -> float:
        """Calculate maximum drawdown percentage."""
        if self._cached_max_drawdown is None:
            if not self.trades:
                self._cached_max_drawdown = 0.0
            else:
                # Calculate running balance and find max drawdown
                balance = 0.0
                peak = 0.0
                max_dd = 0.0
                
                for trade in self.trades:
                    balance += trade.pnl_pct
                    if balance > peak:
                        peak = balance
                    dd = peak - balance
                    if dd > max_dd:
                        max_dd = dd
                
                self._cached_max_drawdown = max_dd
        return self._cached_max_drawdown
    
    @property
    def expectancy(self) -> float:
        """Calculate trade expectancy."""
        if self.total_trades == 0:
            return 0.0
        
        win_rate_pct = self.win_rate / 100
        loss_rate_pct = 1 - win_rate_pct
        
        return (win_rate_pct * self.avg_win) + (loss_rate_pct * self.avg_loss)
    
    @property
    def score(self) -> float:
        """
        Calculate overall strategy score for ranking.
        Combines multiple factors with weights.
        """
        if self.total_trades < 3:
            if self.total_trades == 0:
                return -10.0
            # Avoid overrating tiny samples; require early evidence of positive edge.
            base_score = 8.0 if self.total_pnl_pct > 0 else -6.0
            return round(base_score + (self.total_pnl_pct * 10) + (self.total_trades * 1.5), 2)
        
        # Weights for different factors
        win_rate_weight = 0.3
        profit_factor_weight = 0.3
        expectancy_weight = 0.25
        consistency_weight = 0.15
        
        # Normalize metrics to 0-100 scale
        win_rate_score = min(self.win_rate, 100)
        
        # Profit factor: 1.0 = break even, 2.0 = good, 3.0+ = excellent
        pf_score = min((self.profit_factor - 1) * 50, 100) if self.profit_factor > 1 else 0
        
        # Expectancy: scale to reasonable range (-1% to +1% per trade)
        exp_score = min(max(self.expectancy * 100 + 50, 0), 100)
        
        # Consistency: based on number of trades (more is better, up to 50)
        consistency_score = min(self.total_trades / 50 * 100, 100)
        
        total_score = (
            win_rate_score * win_rate_weight +
            pf_score * profit_factor_weight +
            exp_score * expectancy_weight +
            consistency_score * consistency_weight
        )
        
        return round(total_score, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'strategy': self.strategy,
            'regime': self.regime,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': round(self.win_rate, 2),
            'profit_factor': round(self.profit_factor, 2) if self.profit_factor != float('inf') else 'inf',
            'avg_win': round(self.avg_win, 4),
            'avg_loss': round(self.avg_loss, 4),
            'avg_trade': round(self.avg_trade, 4),
            'expectancy': round(self.expectancy, 4),
            'max_drawdown': round(self.max_drawdown, 4),
            'total_pnl_pct': round(self.total_pnl_pct, 4),
            'total_pnl_dollars': round(self.total_pnl_dollars, 4),
            'total_costs': round(self.total_costs, 4),
            'score': self.score
        }


class PerformanceTracker:
    """
    Main performance tracking class.
    
    Tracks strategy performance across different regimes and provides
    data-driven strategy selection recommendations.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize performance tracker.
        
        Args:
            storage_path: Optional path to persist performance data
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self._performance: Dict[Tuple[str, str], StrategyPerformance] = {}
        self._all_trades: List[TradeRecord] = []
        self._trade_counter = 0
        
        # Load existing data if available
        if self.storage_path and self.storage_path.exists():
            self.load()
    
    def _get_key(self, strategy: str, regime: str) -> Tuple[str, str]:
        """Generate key for performance dictionary."""
        return (strategy.lower(), regime.upper())
    
    def record_trade(
        self,
        strategy: str,
        regime: str,
        ticker: str,
        date: str,
        side: str,
        entry_price: float,
        exit_price: float,
        entry_time: str,
        exit_time: str,
        pnl_pct: float,
        pnl_dollars: float,
        gross_pnl_pct: float = 0.0,
        total_costs: float = 0.0,
        exit_reason: str = "unknown",
        bars_held: int = 0
    ) -> TradeRecord:
        """
        Record a completed trade.
        
        Returns:
            TradeRecord object
        """
        self._trade_counter += 1
        
        trade = TradeRecord(
            trade_id=self._trade_counter,
            strategy=strategy,
            regime=regime,
            ticker=ticker,
            date=date,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            entry_time=entry_time,
            exit_time=exit_time,
            pnl_pct=pnl_pct,
            pnl_dollars=pnl_dollars,
            gross_pnl_pct=gross_pnl_pct,
            total_costs=total_costs,
            exit_reason=exit_reason,
            bars_held=bars_held
        )
        
        # Add to all trades list
        self._all_trades.append(trade)
        
        # Add to strategy-regime performance
        key = self._get_key(strategy, regime)
        if key not in self._performance:
            self._performance[key] = StrategyPerformance(
                strategy=strategy,
                regime=regime
            )
        
        self._performance[key].add_trade(trade)
        
        # Auto-save if storage path is set
        if self.storage_path:
            self.save()
        
        return trade
    
    def get_performance(self, strategy: str, regime: str) -> Optional[StrategyPerformance]:
        """Get performance metrics for a strategy-regime pair."""
        key = self._get_key(strategy, regime)
        return self._performance.get(key)
    
    def get_best_strategy_for_regime(
        self,
        regime: str,
        min_trades: int = 2,
        min_win_rate: float = 30.0
    ) -> Optional[str]:
        """
        Get the best performing strategy for a given regime.
        
        Args:
            regime: Market regime (TRENDING, CHOPPY, MIXED)
            min_trades: Minimum number of trades required for consideration
            min_win_rate: Minimum win rate percentage required
            
        Returns:
            Name of best strategy or None if no suitable strategy found
        """
        candidates = []
        
        for key, perf in self._performance.items():
            if perf.regime.upper() == regime.upper():
                if perf.total_trades >= min_trades and perf.win_rate >= min_win_rate:
                    candidates.append(perf)
        
        if not candidates:
            # If no candidates meet criteria, return any strategy for this regime
            # with the most trades (exploration)
            for key, perf in self._performance.items():
                if perf.regime.upper() == regime.upper():
                    candidates.append(perf)
            
            if candidates:
                candidates.sort(key=lambda x: x.total_trades, reverse=True)
                return candidates[0].strategy
            return None
        
        # Sort by score (descending)
        candidates.sort(key=lambda x: x.score, reverse=True)
        
        return candidates[0].strategy
    
    def get_strategy_rankings(self, regime: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get ranked list of strategies.
        
        Args:
            regime: Optional filter by regime
            
        Returns:
            List of strategy performance dictionaries, sorted by score
        """
        performances = []
        
        for perf in self._performance.values():
            if regime is None or perf.regime.upper() == regime.upper():
                performances.append(perf)
        
        # Sort by score
        performances.sort(key=lambda x: x.score, reverse=True)
        
        return [p.to_dict() for p in performances]
    
    def get_regime_summary(self, regime: str) -> Dict[str, Any]:
        """Get summary statistics for a specific regime."""
        performances = [
            p for p in self._performance.values()
            if p.regime.upper() == regime.upper()
        ]
        
        if not performances:
            return {
                'regime': regime,
                'total_trades': 0,
                'strategies_tested': 0
            }
        
        total_trades = sum(p.total_trades for p in performances)
        total_wins = sum(p.winning_trades for p in performances)
        total_pnl = sum(p.total_pnl_pct for p in performances)
        
        return {
            'regime': regime,
            'total_trades': total_trades,
            'winning_trades': total_wins,
            'losing_trades': sum(p.losing_trades for p in performances),
            'win_rate': round((total_wins / total_trades) * 100, 2) if total_trades > 0 else 0,
            'total_pnl_pct': round(total_pnl, 4),
            'strategies_tested': len(performances),
            'best_strategy': max(performances, key=lambda x: x.score).strategy if performances else None
        }
    
    def get_all_trades(
        self,
        strategy: Optional[str] = None,
        regime: Optional[str] = None,
        ticker: Optional[str] = None
    ) -> List[TradeRecord]:
        """Get filtered list of all trades."""
        trades = self._all_trades
        
        if strategy:
            trades = [t for t in trades if t.strategy.lower() == strategy.lower()]
        if regime:
            trades = [t for t in trades if t.regime.upper() == regime.upper()]
        if ticker:
            trades = [t for t in trades if t.ticker.upper() == ticker.upper()]
        
        return trades
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall performance statistics."""
        if not self._all_trades:
            return {
                'total_trades': 0,
                'total_strategies': 0,
                'total_regimes': 0
            }
        
        total_trades = len(self._all_trades)
        winning_trades = sum(1 for t in self._all_trades if t.pnl_pct > 0)
        total_pnl = sum(t.pnl_pct for t in self._all_trades)
        total_costs = sum(t.total_costs for t in self._all_trades)
        
        strategies = set(t.strategy for t in self._all_trades)
        regimes = set(t.regime for t in self._all_trades)
        tickers = set(t.ticker for t in self._all_trades)
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': round((winning_trades / total_trades) * 100, 2),
            'total_pnl_pct': round(total_pnl, 4),
            'total_pnl_dollars': round(sum(t.pnl_dollars for t in self._all_trades), 4),
            'total_costs': round(total_costs, 4),
            'avg_trade_pnl': round(total_pnl / total_trades, 4),
            'total_strategies': len(strategies),
            'total_regimes': len(regimes),
            'tickers_tested': list(tickers),
            'date_range': {
                'first': min(t.date for t in self._all_trades),
                'last': max(t.date for t in self._all_trades)
            }
        }
    
    def save(self, filepath: Optional[str] = None):
        """Save performance data to file."""
        path = Path(filepath) if filepath else self.storage_path
        
        if not path:
            raise ValueError("No storage path specified")
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'version': '1.0',
            'saved_at': datetime.now().isoformat(),
            'overall_stats': self.get_overall_stats(),
            'performances': {
                f"{k[0]}_{k[1]}": v.to_dict()
                for k, v in self._performance.items()
            },
            'trades': [t.to_dict() for t in self._all_trades]
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self, filepath: Optional[str] = None):
        """Load performance data from file."""
        path = Path(filepath) if filepath else self.storage_path
        
        if not path or not path.exists():
            return
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Load trades
        self._all_trades = [TradeRecord(**t) for t in data.get('trades', [])]
        self._trade_counter = len(self._all_trades)
        
        # Load performances
        self._performance = {}
        for key_str, perf_data in data.get('performances', {}).items():
            # Parse key
            parts = key_str.rsplit('_', 1)
            if len(parts) == 2:
                strategy, regime = parts
                perf = StrategyPerformance(
                    strategy=perf_data['strategy'],
                    regime=perf_data['regime']
                )
                # Restore trade references
                perf.trades = [
                    t for t in self._all_trades
                    if t.strategy.lower() == strategy.lower() and 
                       t.regime.upper() == regime.upper()
                ]
                # Restore counters
                perf.total_trades = perf_data['total_trades']
                perf.winning_trades = perf_data['winning_trades']
                perf.losing_trades = perf_data['losing_trades']
                perf.total_pnl_pct = perf_data['total_pnl_pct']
                perf.total_pnl_dollars = perf_data['total_pnl_dollars']
                perf.total_costs = perf_data['total_costs']
                perf.gross_pnl_pct = perf_data.get('gross_pnl_pct', 0)
                
                self._performance[self._get_key(perf.strategy, perf.regime)] = perf
    
    def clear(self):
        """Clear all performance data."""
        self._performance = {}
        self._all_trades = []
        self._trade_counter = 0
    
    def export_csv(self, filepath: str):
        """Export all trades to CSV."""
        import csv
        
        if not self._all_trades:
            return
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self._all_trades[0].to_dict().keys())
            writer.writeheader()
            for trade in self._all_trades:
                writer.writerow(trade.to_dict())
    
    def print_summary(self):
        """Print formatted performance summary."""
        stats = self.get_overall_stats()
        
        print("\n" + "=" * 70)
        print("📊 PERFORMANCE TRACKER SUMMARY")
        print("=" * 70)
        
        print(f"\nOverall Statistics:")
        print(f"  Total Trades: {stats['total_trades']}")
        print(f"  Win Rate: {stats['win_rate']:.1f}%")
        print(f"  Total PnL: {stats['total_pnl_pct']:.2f}%")
        print(f"  Avg Trade: {stats['avg_trade_pnl']:.3f}%")
        print(f"  Strategies: {stats['total_strategies']}")
        print(f"  Regimes: {stats['total_regimes']}")
        
        if stats['total_trades'] > 0:
            print(f"\nDate Range: {stats['date_range']['first']} to {stats['date_range']['last']}")
            
            print(f"\nPerformance by Regime:")
            for regime in ['TRENDING', 'CHOPPY', 'MIXED']:
                summary = self.get_regime_summary(regime)
                if summary['total_trades'] > 0:
                    print(f"  {regime:10} | Trades: {summary['total_trades']:3} | "
                          f"Win Rate: {summary['win_rate']:5.1f}% | "
                          f"Best: {summary['best_strategy']}")
            
            print(f"\nTop Strategies by Score:")
            rankings = self.get_strategy_rankings()[:5]
            for i, r in enumerate(rankings, 1):
                pf = r['profit_factor']
                pf_str = f"{pf:.2f}" if isinstance(pf, (int, float)) else str(pf)
                print(f"  {i}. {r['strategy']:15} ({r['regime']:8}) | "
                      f"Score: {r['score']:6.1f} | "
                      f"Win Rate: {r['win_rate']:5.1f}% | "
                      f"PF: {pf_str}")
        
        print("=" * 70 + "\n")


# Convenience function for quick testing
def create_tracker(storage_path: Optional[str] = None) -> PerformanceTracker:
    """Create a new performance tracker instance."""
    return PerformanceTracker(storage_path=storage_path)


if __name__ == "__main__":
    # Example usage and testing
    tracker = create_tracker("performance_data.json")
    
    # Add some sample trades
    tracker.record_trade(
        strategy="mean_reversion",
        regime="CHOPPY",
        ticker="NVDA",
        date="2026-01-27",
        side="short",
        entry_price=150.0,
        exit_price=149.0,
        entry_time="10:00:00",
        exit_time="10:30:00",
        pnl_pct=0.66,
        pnl_dollars=0.66,
        exit_reason="take_profit"
    )
    
    tracker.record_trade(
        strategy="mean_reversion",
        regime="CHOPPY",
        ticker="NVDA",
        date="2026-01-27",
        side="short",
        entry_price=151.0,
        exit_price=150.5,
        entry_time="11:00:00",
        exit_time="11:20:00",
        pnl_pct=0.33,
        pnl_dollars=0.33,
        exit_reason="trailing_stop"
    )
    
    tracker.record_trade(
        strategy="momentum",
        regime="TRENDING",
        ticker="TSLA",
        date="2026-01-27",
        side="long",
        entry_price=250.0,
        exit_price=252.5,
        entry_time="10:15:00",
        exit_time="11:00:00",
        pnl_pct=1.0,
        pnl_dollars=1.0,
        exit_reason="take_profit"
    )
    
    # Print summary
    tracker.print_summary()
    
    # Get best strategy for CHOPPY regime
    best = tracker.get_best_strategy_for_regime("CHOPPY")
    print(f"\nBest strategy for CHOPPY regime: {best}")
