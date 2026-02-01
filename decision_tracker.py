"""
Decision Tracker - Tracks all trading decisions with explanations for visualization.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import json


class MarkerType(str, Enum):
    """Types of decision markers."""
    REGIME_DETECTED = "regime_detected"
    STRATEGY_SELECTED = "strategy_selected"
    SIGNAL_GENERATED = "signal_generated"
    ENTRY_EXECUTED = "entry_executed"
    EXIT_EXECUTED = "exit_executed"
    STOP_LOSS_HIT = "stop_loss_hit"
    TAKE_PROFIT_HIT = "take_profit_hit"
    TRAILING_STOP_UPDATED = "trailing_stop_updated"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"


@dataclass
class DecisionMarker:
    """A single decision marker with explanation."""
    id: str
    timestamp: datetime
    bar_index: int
    marker_type: MarkerType
    title: str
    description: str
    price: float
    side: Optional[str] = None  # 'long' or 'short'
    strategy: Optional[str] = None
    regime: Optional[str] = None
    confidence: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "bar_index": self.bar_index,
            "marker_type": self.marker_type.value,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "side": self.side,
            "strategy": self.strategy,
            "regime": self.regime,
            "confidence": self.confidence,
            "details": self.details
        }


class DecisionTracker:
    """Tracks all trading decisions for a session."""
    
    def __init__(self, run_id: str, ticker: str, date: str):
        self.run_id = run_id
        self.ticker = ticker
        self.date = date
        self.markers: List[DecisionMarker] = []
        self._marker_counter = 0
    
    def _generate_id(self) -> str:
        """Generate unique marker ID."""
        self._marker_counter += 1
        return f"{self.run_id}:{self.ticker}:{self.date}:{self._marker_counter}"
    
    def add_regime_detected(
        self, 
        timestamp: datetime, 
        bar_index: int, 
        price: float,
        regime: str, 
        explanation: str,
        indicators: Dict[str, float]
    ) -> DecisionMarker:
        """Record regime detection decision."""
        marker = DecisionMarker(
            id=self._generate_id(),
            timestamp=timestamp,
            bar_index=bar_index,
            marker_type=MarkerType.REGIME_DETECTED,
            title=f"Regime: {regime}",
            description=explanation,
            price=price,
            regime=regime,
            details={
                "indicators": indicators,
                "detection_time_minutes": 15  # default
            }
        )
        self.markers.append(marker)
        return marker
    
    def add_strategy_selected(
        self,
        timestamp: datetime,
        bar_index: int,
        price: float,
        strategy: str,
        regime: str,
        reasoning: str
    ) -> DecisionMarker:
        """Record strategy selection decision."""
        marker = DecisionMarker(
            id=self._generate_id(),
            timestamp=timestamp,
            bar_index=bar_index,
            marker_type=MarkerType.STRATEGY_SELECTED,
            title=f"Strategy: {strategy}",
            description=reasoning,
            price=price,
            strategy=strategy,
            regime=regime,
            details={
                "alternative_strategies": [],
                "selection_criteria": reasoning
            }
        )
        self.markers.append(marker)
        return marker
    
    def add_signal(
        self,
        timestamp: datetime,
        bar_index: int,
        price: float,
        signal_type: str,  # 'BUY' or 'SELL'
        strategy: str,
        confidence: float,
        reasoning: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> DecisionMarker:
        """Record signal generation."""
        marker = DecisionMarker(
            id=self._generate_id(),
            timestamp=timestamp,
            bar_index=bar_index,
            marker_type=MarkerType.SIGNAL_GENERATED,
            title=f"Signal: {signal_type}",
            description=reasoning,
            price=price,
            side="long" if signal_type.upper() == "BUY" else "short",
            strategy=strategy,
            confidence=confidence,
            details={
                "signal_type": signal_type,
                "stop_loss": stop_loss,
                "take_profit": take_profit
            }
        )
        self.markers.append(marker)
        return marker
    
    def add_entry(
        self,
        timestamp: datetime,
        bar_index: int,
        price: float,
        side: str,
        strategy: str,
        size: float,
        stop_loss: float,
        take_profit: float
    ) -> DecisionMarker:
        """Record trade entry."""
        marker = DecisionMarker(
            id=self._generate_id(),
            timestamp=timestamp,
            bar_index=bar_index,
            marker_type=MarkerType.ENTRY_EXECUTED,
            title=f"Entry: {side.upper()}",
            description=f"Entered {side} position at ${price:.2f}",
            price=price,
            side=side,
            strategy=strategy,
            details={
                "size": size,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "risk_reward": abs(take_profit - price) / abs(price - stop_loss) if stop_loss != price else 0
            }
        )
        self.markers.append(marker)
        return marker
    
    def add_exit(
        self,
        timestamp: datetime,
        bar_index: int,
        price: float,
        side: str,
        reason: str,
        pnl_pct: float,
        pnl_dollars: float
    ) -> DecisionMarker:
        """Record trade exit."""
        marker_type = MarkerType.EXIT_EXECUTED
        if "stop" in reason.lower():
            marker_type = MarkerType.STOP_LOSS_HIT
        elif "profit" in reason.lower() or "take" in reason.lower():
            marker_type = MarkerType.TAKE_PROFIT_HIT
        
        marker = DecisionMarker(
            id=self._generate_id(),
            timestamp=timestamp,
            bar_index=bar_index,
            marker_type=marker_type,
            title=f"Exit: {reason}",
            description=f"Closed {side} position. PnL: {pnl_pct:+.2f}% (${pnl_dollars:+.2f})",
            price=price,
            side=side,
            details={
                "exit_reason": reason,
                "pnl_pct": pnl_pct,
                "pnl_dollars": pnl_dollars
            }
        )
        self.markers.append(marker)
        return marker
    
    def add_session_start(
        self,
        timestamp: datetime,
        bar_index: int,
        price: float
    ) -> DecisionMarker:
        """Record session start."""
        marker = DecisionMarker(
            id=self._generate_id(),
            timestamp=timestamp,
            bar_index=bar_index,
            marker_type=MarkerType.SESSION_STARTED,
            title="Session Started",
            description=f"Trading session started for {self.ticker}",
            price=price,
            details={
                "ticker": self.ticker,
                "date": self.date,
                "run_id": self.run_id
            }
        )
        self.markers.append(marker)
        return marker
    
    def add_session_end(
        self,
        timestamp: datetime,
        bar_index: int,
        price: float,
        summary: Dict[str, Any]
    ) -> DecisionMarker:
        """Record session end."""
        marker = DecisionMarker(
            id=self._generate_id(),
            timestamp=timestamp,
            bar_index=bar_index,
            marker_type=MarkerType.SESSION_ENDED,
            title="Session Ended",
            description=f"Trading session ended. Total PnL: {summary.get('total_pnl_pct', 0):+.2f}%",
            price=price,
            details=summary
        )
        self.markers.append(marker)
        return marker
    
    def get_markers(self, marker_type: Optional[MarkerType] = None) -> List[Dict[str, Any]]:
        """Get all markers, optionally filtered by type."""
        markers = self.markers
        if marker_type:
            markers = [m for m in markers if m.marker_type == marker_type]
        return [m.to_dict() for m in markers]
    
    def get_marker_by_id(self, marker_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific marker by ID."""
        for m in self.markers:
            if m.id == marker_id:
                return m.to_dict()
        return None
    
    def get_chart_annotations(self) -> List[Dict[str, Any]]:
        """Get markers formatted for chart annotations."""
        annotations = []
        for m in self.markers:
            color = self._get_marker_color(m.marker_type)
            shape = self._get_marker_shape(m.marker_type)
            position = self._get_marker_position(m)
            
            annotations.append({
                "time": int(m.timestamp.timestamp()),
                "position": position,
                "color": color,
                "shape": shape,
                "text": m.title,
                "id": m.id,
                "marker_type": m.marker_type.value
            })
        return annotations
    
    def _get_marker_color(self, marker_type: MarkerType) -> str:
        """Get color for marker type."""
        colors = {
            MarkerType.REGIME_DETECTED: "#3b82f6",  # blue
            MarkerType.STRATEGY_SELECTED: "#8b5cf6",  # purple
            MarkerType.SIGNAL_GENERATED: "#f59e0b",  # amber
            MarkerType.ENTRY_EXECUTED: "#22c55e",  # green
            MarkerType.EXIT_EXECUTED: "#64748b",  # slate
            MarkerType.STOP_LOSS_HIT: "#ef4444",  # red
            MarkerType.TAKE_PROFIT_HIT: "#22c55e",  # green
            MarkerType.TRAILING_STOP_UPDATED: "#06b6d4",  # cyan
            MarkerType.SESSION_STARTED: "#3b82f6",  # blue
            MarkerType.SESSION_ENDED: "#3b82f6",  # blue
        }
        return colors.get(marker_type, "#64748b")
    
    def _get_marker_shape(self, marker_type: MarkerType) -> str:
        """Get shape for marker type."""
        shapes = {
            MarkerType.REGIME_DETECTED: "circle",
            MarkerType.STRATEGY_SELECTED: "square",
            MarkerType.SIGNAL_GENERATED: "arrowUp",
            MarkerType.ENTRY_EXECUTED: "arrowUp",
            MarkerType.EXIT_EXECUTED: "arrowDown",
            MarkerType.STOP_LOSS_HIT: "arrowDown",
            MarkerType.TAKE_PROFIT_HIT: "arrowDown",
            MarkerType.TRAILING_STOP_UPDATED: "circle",
            MarkerType.SESSION_STARTED: "circle",
            MarkerType.SESSION_ENDED: "circle",
        }
        return shapes.get(marker_type, "circle")
    
    def _get_marker_position(self, marker: DecisionMarker) -> str:
        """Get position (aboveBar/belowBar) for marker."""
        if marker.marker_type in [MarkerType.ENTRY_EXECUTED, MarkerType.SIGNAL_GENERATED]:
            return "belowBar" if marker.side == "long" else "aboveBar"
        elif marker.marker_type in [MarkerType.EXIT_EXECUTED, MarkerType.STOP_LOSS_HIT, MarkerType.TAKE_PROFIT_HIT]:
            return "aboveBar" if marker.side == "long" else "belowBar"
        return "aboveBar"
    
    def to_json(self) -> str:
        """Serialize tracker to JSON."""
        return json.dumps({
            "run_id": self.run_id,
            "ticker": self.ticker,
            "date": self.date,
            "markers": [m.to_dict() for m in self.markers]
        }, default=str)
