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
    flow_strategy: bool = False
    book_pressure_confirmed: Optional[bool] = None
    book_pressure_avg: Optional[float] = None
    book_pressure_trend: Optional[float] = None
    signed_aggression: Optional[float] = None
    entry_quality_diagnostics: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "strategy": self.strategy,
            "regime": self.regime,
            "ticker": self.ticker,
            "date": self.date,
            "side": self.side,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "pnl_pct": round(self.pnl_pct, 4),
            "pnl_dollars": round(self.pnl_dollars, 4),
            "gross_pnl_pct": round(self.gross_pnl_pct, 4),
            "total_costs": round(self.total_costs, 4),
            "exit_reason": self.exit_reason,
            "bars_held": self.bars_held,
            "flow_strategy": self.flow_strategy,
            "book_pressure_confirmed": self.book_pressure_confirmed,
            "book_pressure_avg": (
                round(self.book_pressure_avg, 6)
                if self.book_pressure_avg is not None
                else None
            ),
            "book_pressure_trend": (
                round(self.book_pressure_trend, 6)
                if self.book_pressure_trend is not None
                else None
            ),
            "signed_aggression": (
                round(self.signed_aggression, 6)
                if self.signed_aggression is not None
                else None
            ),
            "entry_quality_diagnostics": (
                dict(self.entry_quality_diagnostics)
                if isinstance(self.entry_quality_diagnostics, dict)
                else None
            ),
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
                self._cached_profit_factor = float("inf") if total_wins > 0 else 0.0
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
            return round(
                base_score + (self.total_pnl_pct * 10) + (self.total_trades * 1.5), 2
            )

        # Weights for different factors
        win_rate_weight = 0.3
        profit_factor_weight = 0.3
        expectancy_weight = 0.25
        consistency_weight = 0.15

        # Normalize metrics to 0-100 scale
        win_rate_score = min(self.win_rate, 100)

        # Profit factor: 1.0 = break even, 2.0 = good, 3.0+ = excellent
        pf_score = (
            min((self.profit_factor - 1) * 50, 100) if self.profit_factor > 1 else 0
        )

        # Expectancy: scale to reasonable range (-1% to +1% per trade)
        exp_score = min(max(self.expectancy * 100 + 50, 0), 100)

        # Consistency: based on number of trades (more is better, up to 50)
        consistency_score = min(self.total_trades / 50 * 100, 100)

        total_score = (
            win_rate_score * win_rate_weight
            + pf_score * profit_factor_weight
            + exp_score * expectancy_weight
            + consistency_score * consistency_weight
        )

        return round(total_score, 2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy": self.strategy,
            "regime": self.regime,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "profit_factor": (
                round(self.profit_factor, 2)
                if self.profit_factor != float("inf")
                else "inf"
            ),
            "avg_win": round(self.avg_win, 4),
            "avg_loss": round(self.avg_loss, 4),
            "avg_trade": round(self.avg_trade, 4),
            "expectancy": round(self.expectancy, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "total_pnl_pct": round(self.total_pnl_pct, 4),
            "total_pnl_dollars": round(self.total_pnl_dollars, 4),
            "total_costs": round(self.total_costs, 4),
            "score": self.score,
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
        bars_held: int = 0,
        flow_strategy: bool = False,
        book_pressure_confirmed: Optional[bool] = None,
        book_pressure_avg: Optional[float] = None,
        book_pressure_trend: Optional[float] = None,
        signed_aggression: Optional[float] = None,
        entry_quality_diagnostics: Optional[Dict[str, Any]] = None,
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
            bars_held=bars_held,
            flow_strategy=flow_strategy,
            book_pressure_confirmed=book_pressure_confirmed,
            book_pressure_avg=book_pressure_avg,
            book_pressure_trend=book_pressure_trend,
            signed_aggression=signed_aggression,
            entry_quality_diagnostics=(
                dict(entry_quality_diagnostics)
                if isinstance(entry_quality_diagnostics, dict)
                else None
            ),
        )

        # Add to all trades list
        self._all_trades.append(trade)

        # Add to strategy-regime performance
        key = self._get_key(strategy, regime)
        if key not in self._performance:
            self._performance[key] = StrategyPerformance(
                strategy=strategy, regime=regime
            )

        self._performance[key].add_trade(trade)

        # Auto-save if storage path is set
        if self.storage_path:
            self.save()

        return trade

    def get_strategy_rankings(
        self, regime: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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
            p for p in self._performance.values() if p.regime.upper() == regime.upper()
        ]

        if not performances:
            return {"regime": regime, "total_trades": 0, "strategies_tested": 0}

        total_trades = sum(p.total_trades for p in performances)
        total_wins = sum(p.winning_trades for p in performances)
        total_pnl = sum(p.total_pnl_pct for p in performances)

        return {
            "regime": regime,
            "total_trades": total_trades,
            "winning_trades": total_wins,
            "losing_trades": sum(p.losing_trades for p in performances),
            "win_rate": (
                round((total_wins / total_trades) * 100, 2) if total_trades > 0 else 0
            ),
            "total_pnl_pct": round(total_pnl, 4),
            "strategies_tested": len(performances),
            "best_strategy": (
                max(performances, key=lambda x: x.score).strategy
                if performances
                else None
            ),
        }

    @staticmethod
    def _extract_trade_hour(entry_time: str) -> int:
        """Best-effort extraction of trade entry hour (0-23)."""
        if not entry_time:
            return -1
        try:
            return datetime.fromisoformat(str(entry_time).replace("Z", "+00:00")).hour
        except Exception:
            parts = str(entry_time).split(":")
            if parts and parts[0].isdigit():
                hour = int(parts[0])
                if 0 <= hour <= 23:
                    return hour
        return -1

    def get_hourly_summary(self) -> Dict[str, Dict[str, float]]:
        """Aggregate performance by entry hour."""
        buckets: Dict[int, List[TradeRecord]] = {}
        for trade in self._all_trades:
            hour = self._extract_trade_hour(trade.entry_time)
            if hour < 0:
                continue
            buckets.setdefault(hour, []).append(trade)

        out: Dict[str, Dict[str, float]] = {}
        for hour in sorted(buckets.keys()):
            trades = buckets[hour]
            wins = sum(1 for t in trades if t.pnl_pct > 0)
            total = len(trades)
            pnl = sum(t.pnl_pct for t in trades)
            out[f"{hour:02d}:00"] = {
                "trades": float(total),
                "win_rate": round((wins / total) * 100, 2) if total > 0 else 0.0,
                "total_pnl_pct": round(pnl, 4),
                "avg_pnl_pct": round((pnl / total), 4) if total > 0 else 0.0,
            }
        return out

    def get_weekday_summary(self) -> Dict[str, Dict[str, float]]:
        """Aggregate performance by weekday."""
        labels = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        buckets: Dict[int, List[TradeRecord]] = {}
        for trade in self._all_trades:
            try:
                day_idx = datetime.strptime(trade.date, "%Y-%m-%d").weekday()
            except Exception:
                continue
            buckets.setdefault(day_idx, []).append(trade)

        out: Dict[str, Dict[str, float]] = {}
        for idx in sorted(buckets.keys()):
            trades = buckets[idx]
            wins = sum(1 for t in trades if t.pnl_pct > 0)
            total = len(trades)
            pnl = sum(t.pnl_pct for t in trades)
            out[labels[idx]] = {
                "trades": float(total),
                "win_rate": round((wins / total) * 100, 2) if total > 0 else 0.0,
                "total_pnl_pct": round(pnl, 4),
                "avg_pnl_pct": round((pnl / total), 4) if total > 0 else 0.0,
            }
        return out

    def get_all_trades(
        self,
        strategy: Optional[str] = None,
        regime: Optional[str] = None,
        ticker: Optional[str] = None,
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

    @staticmethod
    def _summarize_trade_subset(trades: List[TradeRecord]) -> Dict[str, Any]:
        """Aggregate a subset of trades into comparable summary stats."""
        total = len(trades)
        if total == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl_pct": 0.0,
                "total_pnl_dollars": 0.0,
                "avg_pnl_pct": 0.0,
            }
        winning = sum(1 for t in trades if t.pnl_pct > 0)
        total_pnl_pct = sum(t.pnl_pct for t in trades)
        total_pnl_dollars = sum(t.pnl_dollars for t in trades)
        return {
            "total_trades": total,
            "win_rate": round((winning / total) * 100, 2),
            "total_pnl_pct": round(total_pnl_pct, 4),
            "total_pnl_dollars": round(total_pnl_dollars, 4),
            "avg_pnl_pct": round(total_pnl_pct / total, 4),
        }

    def get_flow_breakdown(self) -> Dict[str, Any]:
        """
        Flow-specific performance split:
        - all flow trades
        - flow trades with book-pressure confirmation
        - flow trades without book-pressure confirmation
        """
        flow_trades = [
            t
            for t in self._all_trades
            if t.flow_strategy or ("flow" in t.strategy.lower())
        ]
        with_book = [
            t
            for t in flow_trades
            if (t.book_pressure_confirmed is True)
            or (t.book_pressure_confirmed is None and t.book_pressure_avg is not None)
        ]
        without_book = [
            t
            for t in flow_trades
            if (t.book_pressure_confirmed is False)
            or (t.book_pressure_confirmed is None and t.book_pressure_avg is None)
        ]

        return {
            "flow_trades": self._summarize_trade_subset(flow_trades),
            "with_book_pressure": self._summarize_trade_subset(with_book),
            "without_book_pressure": self._summarize_trade_subset(without_book),
        }

    def get_entry_timing_breakdown(self) -> Dict[str, Any]:
        """Summarize fast stop-outs (<= 1 bar) with diagnostic tag counts."""
        if not self._all_trades:
            return {
                "total_trades": 0,
                "stop_exits": 0,
                "first_bar_stop_exits": 0,
                "first_bar_stop_rate_pct": 0.0,
                "first_bar_stop_share_of_trades_pct": 0.0,
                "first_bar_stop_by_strategy": {},
                "first_bar_stop_tag_counts": {},
            }

        def _is_stop_exit(trade: TradeRecord) -> bool:
            reason = str(trade.exit_reason or "").strip().lower()
            return (
                reason in {"stop_loss", "trailing_stop", "breakeven_stop"}
                or "stop" in reason
            )

        stop_trades = [t for t in self._all_trades if _is_stop_exit(t)]
        first_bar_stop_trades: List[TradeRecord] = []
        tag_counts: Dict[str, int] = {}
        per_strategy: Dict[str, Dict[str, Any]] = {}

        for trade in self._all_trades:
            strategy_key = str(trade.strategy or "unknown").strip().lower() or "unknown"
            bucket = per_strategy.setdefault(
                strategy_key,
                {
                    "total_trades": 0,
                    "stop_exits": 0,
                    "first_bar_stop_exits": 0,
                    "first_bar_stop_rate_pct": 0.0,
                    "first_bar_stop_share_of_trades_pct": 0.0,
                },
            )
            bucket["total_trades"] += 1

            if _is_stop_exit(trade):
                bucket["stop_exits"] += 1

            diag = (
                trade.entry_quality_diagnostics
                if isinstance(trade.entry_quality_diagnostics, dict)
                else {}
            )
            is_first_bar_stop = bool(
                diag.get("is_first_bar_stop_loss", False)
                or (_is_stop_exit(trade) and int(trade.bars_held or 0) <= 1)
            )
            if not is_first_bar_stop:
                continue

            first_bar_stop_trades.append(trade)
            bucket["first_bar_stop_exits"] += 1
            for tag in (
                diag.get("first_bar_stop_tags", [])
                if isinstance(diag.get("first_bar_stop_tags"), list)
                else []
            ):
                tag_key = str(tag).strip().lower()
                if not tag_key:
                    continue
                tag_counts[tag_key] = int(tag_counts.get(tag_key, 0)) + 1

        for bucket in per_strategy.values():
            total = int(bucket.get("total_trades", 0))
            stop_exits = int(bucket.get("stop_exits", 0))
            first_bar = int(bucket.get("first_bar_stop_exits", 0))
            bucket["first_bar_stop_rate_pct"] = (
                round((first_bar / stop_exits) * 100.0, 2) if stop_exits > 0 else 0.0
            )
            bucket["first_bar_stop_share_of_trades_pct"] = (
                round((first_bar / total) * 100.0, 2) if total > 0 else 0.0
            )

        stop_total = len(stop_trades)
        first_bar_total = len(first_bar_stop_trades)
        return {
            "total_trades": len(self._all_trades),
            "stop_exits": stop_total,
            "first_bar_stop_exits": first_bar_total,
            "first_bar_stop_rate_pct": (
                round((first_bar_total / stop_total) * 100.0, 2)
                if stop_total > 0
                else 0.0
            ),
            "first_bar_stop_share_of_trades_pct": (
                round((first_bar_total / len(self._all_trades)) * 100.0, 2)
                if self._all_trades
                else 0.0
            ),
            "first_bar_stop_by_strategy": per_strategy,
            "first_bar_stop_tag_counts": dict(
                sorted(tag_counts.items(), key=lambda item: (-int(item[1]), item[0]))
            ),
        }

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall performance statistics."""
        if not self._all_trades:
            return {
                "total_trades": 0,
                "total_strategies": 0,
                "total_regimes": 0,
                "flow_breakdown": self.get_flow_breakdown(),
                "entry_timing_breakdown": self.get_entry_timing_breakdown(),
            }

        total_trades = len(self._all_trades)
        winning_trades = sum(1 for t in self._all_trades if t.pnl_pct > 0)
        total_pnl = sum(t.pnl_pct for t in self._all_trades)
        total_costs = sum(t.total_costs for t in self._all_trades)

        strategies = set(t.strategy for t in self._all_trades)
        regimes = set(t.regime for t in self._all_trades)
        tickers = set(t.ticker for t in self._all_trades)

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": round((winning_trades / total_trades) * 100, 2),
            "total_pnl_pct": round(total_pnl, 4),
            "total_pnl_dollars": round(sum(t.pnl_dollars for t in self._all_trades), 4),
            "total_costs": round(total_costs, 4),
            "avg_trade_pnl": round(total_pnl / total_trades, 4),
            "total_strategies": len(strategies),
            "total_regimes": len(regimes),
            "tickers_tested": list(tickers),
            "flow_breakdown": self.get_flow_breakdown(),
            "entry_timing_breakdown": self.get_entry_timing_breakdown(),
            "date_range": {
                "first": min(t.date for t in self._all_trades),
                "last": max(t.date for t in self._all_trades),
            },
        }

    def save(self, filepath: Optional[str] = None):
        """Save performance data to file."""
        path = Path(filepath) if filepath else self.storage_path

        if not path:
            raise ValueError("No storage path specified")

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "overall_stats": self.get_overall_stats(),
            "performances": {
                f"{k[0]}_{k[1]}": v.to_dict() for k, v in self._performance.items()
            },
            "trades": [t.to_dict() for t in self._all_trades],
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, filepath: Optional[str] = None):
        """Load performance data from file."""
        path = Path(filepath) if filepath else self.storage_path

        if not path or not path.exists():
            return

        with open(path, "r") as f:
            data = json.load(f)

        # Load trades
        self._all_trades = [TradeRecord(**t) for t in data.get("trades", [])]
        self._trade_counter = len(self._all_trades)

        # Load performances
        self._performance = {}
        for key_str, perf_data in data.get("performances", {}).items():
            # Parse key
            parts = key_str.rsplit("_", 1)
            if len(parts) == 2:
                strategy, regime = parts
                perf = StrategyPerformance(
                    strategy=perf_data["strategy"], regime=perf_data["regime"]
                )
                # Restore trade references
                perf.trades = [
                    t
                    for t in self._all_trades
                    if t.strategy.lower() == strategy.lower()
                    and t.regime.upper() == regime.upper()
                ]
                # Restore counters
                perf.total_trades = perf_data["total_trades"]
                perf.winning_trades = perf_data["winning_trades"]
                perf.losing_trades = perf_data["losing_trades"]
                perf.total_pnl_pct = perf_data["total_pnl_pct"]
                perf.total_pnl_dollars = perf_data["total_pnl_dollars"]
                perf.total_costs = perf_data["total_costs"]
                perf.gross_pnl_pct = perf_data.get("gross_pnl_pct", 0)

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

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self._all_trades[0].to_dict().keys())
            writer.writeheader()
            for trade in self._all_trades:
                writer.writerow(trade.to_dict())


if __name__ == "__main__":
    # Example usage and testing
    example_storage_path = Path("analysis/runtime/performance_data.json")
    example_storage_path.parent.mkdir(parents=True, exist_ok=True)
    tracker = PerformanceTracker(storage_path=str(example_storage_path))

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
        exit_reason="take_profit",
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
        exit_reason="trailing_stop",
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
        exit_reason="take_profit",
    )

    # Print overall stats snapshot
    print(tracker.get_overall_stats())
