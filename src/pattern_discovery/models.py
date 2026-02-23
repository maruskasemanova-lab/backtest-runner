"""
Pattern Discovery Models - Pydantic models for pattern discovery engine.

Core data structures:
- PatternInput: Feature vector input for pattern matching
- PatternMatch: Output from pattern matching
- PatternSnapshot: Historical feature snapshot with outcome label
- PatternLibrary: Collection of discovered patterns
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json

from pydantic import BaseModel, Field


class PatternType(str, Enum):
    """Type of pattern."""

    CLUSTER = "cluster"
    SEQUENTIAL = "sequential"


class Direction(str, Enum):
    """Trading direction."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class RecommendedAction(str, Enum):
    """Recommended trading action."""

    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    AVOID = "avoid"
    NEUTRAL = "neutral"


# ============================================================================
# Input Models
# ============================================================================


class PatternInput(BaseModel):
    """
    Feature vector input for pattern discovery.

    Extracted from FeatureVector in strategy-engine and normalized.
    All z-score features are already normalized (mean=0, std=1).
    """

    # === Market State (normalized z-score) ===
    momentum_z: float = Field(default=0.0, description="Composite momentum z-score")
    rsi_z: float = Field(default=0.0, description="RSI z-score")
    volume_z: float = Field(default=0.0, description="Volume z-score")
    atr_z: float = Field(default=0.0, description="ATR/volatility z-score")

    # === L2 Flow State ===
    l2_delta_z: float = Field(default=0.0, description="Order flow delta z-score")
    l2_aggression_z: float = Field(default=0.0, description="Signed aggression z-score")
    l2_imbalance_z: float = Field(default=0.0, description="Imbalance z-score")
    l2_book_pressure_z: float = Field(default=0.0, description="Book pressure z-score")
    l2_flow_score_z: float = Field(
        default=0.0, description="Composite flow score z-score"
    )

    # === Regime Context ===
    regime: str = Field(
        default="MIXED", description="Market regime: TRENDING|CHOPPY|MIXED"
    )
    trend_efficiency: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Trend efficiency 0-1"
    )
    volatility_pct: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Volatility percentile rank"
    )

    # === Time Context ===
    hour_of_day: int = Field(
        default=10, ge=0, le=23, description="Hour of day (market hours)"
    )
    minute_of_hour: int = Field(default=0, ge=0, le=59, description="Minute of hour")
    day_of_week: int = Field(
        default=1, ge=0, le=6, description="Day of week (0=Monday)"
    )

    # === Price Action Context ===
    bar_body_ratio: float = Field(
        default=0.5, ge=0.0, le=1.0, description="|close-open| / (high-low)"
    )
    close_location: float = Field(
        default=0.5, ge=0.0, le=1.0, description="(close-low) / (high-low)"
    )
    gap_pct: float = Field(default=0.0, description="Gap from previous close %")

    def to_vector(self) -> List[float]:
        """Convert to feature vector for ML operations."""
        return [
            self.momentum_z,
            self.rsi_z,
            self.volume_z,
            self.atr_z,
            self.l2_delta_z,
            self.l2_aggression_z,
            self.l2_imbalance_z,
            self.l2_book_pressure_z,
            self.l2_flow_score_z,
            self.trend_efficiency,
            self.volatility_pct,
            self.hour_of_day / 23.0,  # Normalize to 0-1
            self.minute_of_hour / 59.0,  # Normalize to 0-1
            self.day_of_week / 6.0,  # Normalize to 0-1
            self.bar_body_ratio,
            self.close_location,
            self.gap_pct,
        ]

    def to_state_label(self) -> str:
        """Generate discrete state label for sequential pattern mining."""
        # Discretize continuous features into states
        momentum_state = (
            "up"
            if self.momentum_z > 0.5
            else "down" if self.momentum_z < -0.5 else "neutral"
        )
        delta_state = (
            "spike_up"
            if self.l2_delta_z > 1.5
            else "spike_down" if self.l2_delta_z < -1.5 else "normal"
        )
        vol_state = (
            "high"
            if self.volume_z > 1.0
            else "low" if self.volume_z < -1.0 else "normal"
        )

        return f"{momentum_state}_{delta_state}_{vol_state}"

    @classmethod
    def from_feature_vector(cls, fv: Dict[str, Any]) -> "PatternInput":
        """Create PatternInput from FeatureVector dict representation."""
        return cls(
            momentum_z=float(fv.get("momentum_z", 0.0)),
            rsi_z=float(fv.get("rsi_z", 0.0)),
            volume_z=float(fv.get("volume_z", 0.0)),
            atr_z=float(fv.get("atr_z", 0.0)),
            l2_delta_z=float(fv.get("l2_delta_z", 0.0)),
            l2_aggression_z=float(fv.get("l2_aggression_z", 0.0)),
            l2_imbalance_z=float(fv.get("l2_imbalance_z", 0.0)),
            l2_book_pressure_z=float(fv.get("l2_book_pressure_z", 0.0)),
            l2_flow_score_z=float(fv.get("l2_flow_score_z", 0.0)),
            regime=str(fv.get("regime", "MIXED")),
            trend_efficiency=float(fv.get("trend_efficiency", 0.5)),
            volatility_pct=float(fv.get("volatility_pct", 0.5)),
            hour_of_day=int(fv.get("hour_of_day", 10)),
            minute_of_hour=int(fv.get("minute_of_hour", 0)),
            day_of_week=int(fv.get("day_of_week", 1)),
            bar_body_ratio=float(fv.get("bar_body_ratio", 0.5)),
            close_location=float(fv.get("close_location", 0.5)),
            gap_pct=float(fv.get("gap_pct", 0.0)),
        )


class MatchConfig(BaseModel):
    """Configuration for pattern matching."""

    min_similarity: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    max_matches: int = Field(
        default=3, ge=1, le=10, description="Maximum matches to return"
    )
    direction_filter: str = Field(
        default="any", description="Filter by direction: any|bullish_only|bearish_only"
    )
    min_win_rate: float = Field(
        default=0.50, ge=0.0, le=1.0, description="Minimum historical win rate"
    )
    min_support: int = Field(
        default=5, ge=1, description="Minimum pattern support count"
    )


# ============================================================================
# Output Models
# ============================================================================


class PatternMatch(BaseModel):
    """
    Output from pattern matching.

    Contains pattern identity, match quality, historical performance,
    and recommended action for trading decisions.
    """

    # === Pattern Identity ===
    pattern_id: str = Field(description="Unique pattern identifier")
    pattern_type: PatternType = Field(description="Type: cluster or sequential")
    pattern_name: str = Field(description="Human-readable pattern name")

    # === Match Quality ===
    similarity_score: float = Field(
        ge=0.0, le=1.0, description="How well current state matches pattern"
    )
    distance: float = Field(
        ge=0.0, description="Euclidean distance to pattern centroid"
    )

    # === Historical Performance ===
    historical_win_rate: float = Field(
        ge=0.0, le=1.0, description="Win rate when pattern occurred"
    )
    historical_avg_pnl: float = Field(description="Average PnL% when pattern occurred")
    historical_count: int = Field(ge=1, description="Number of historical occurrences")
    confidence_interval: Tuple[float, float] = Field(
        default=(0.0, 1.0), description="95% CI for win rate"
    )

    # === Direction Signal ===
    direction: Direction = Field(
        description="Trading direction: bullish|bearish|neutral"
    )
    direction_confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in direction"
    )

    # === Recommended Action ===
    recommended_action: RecommendedAction = Field(
        description="Recommended trading action"
    )
    recommended_stop_atr: float = Field(
        default=1.5, ge=0.1, description="ATR multiplier for stop"
    )
    recommended_target_rr: float = Field(
        default=2.0, ge=0.5, description="Risk-reward ratio for target"
    )

    # === Evidence for Decision Engine ===
    evidence_strength: float = Field(
        ge=0.0, le=100.0, description="Strength 0-100 for EvidenceSource"
    )
    evidence_reasoning: str = Field(
        default="", description="Human-readable explanation"
    )

    def to_evidence_dict(self) -> Dict[str, Any]:
        """Convert to evidence source dict for EvidenceDecisionEngine."""
        return {
            "source_type": "pattern",
            "source_name": self.pattern_name,
            "direction": self.direction.value,
            "strength": self.evidence_strength,
            "calibrated": self.historical_win_rate,
            "reasoning": self.evidence_reasoning,
        }


# ============================================================================
# Pattern Discovery Models
# ============================================================================


class PatternOutcome(BaseModel):
    """Outcome label for a pattern snapshot."""

    is_profitable: bool = Field(description="Whether the trade was profitable")
    pnl_pct: float = Field(description="PnL as percentage")
    pnl_dollars: float = Field(default=0.0, description="PnL in dollars")
    bars_held: int = Field(
        default=0, ge=0, description="Number of bars position was held"
    )
    max_favorable_excursion: float = Field(
        default=0.0, description="Maximum favorable excursion %"
    )
    max_adverse_excursion: float = Field(
        default=0.0, description="Maximum adverse excursion %"
    )
    exit_reason: str = Field(default="", description="Reason for exit")


class PatternSnapshot(BaseModel):
    """
    Historical feature snapshot with outcome label.

    Used for pattern discovery - captures the state at decision time
    and the subsequent outcome.
    """

    # === Identity ===
    snapshot_id: str = Field(description="Unique snapshot identifier")
    ticker: str = Field(description="Ticker symbol")
    timestamp: datetime = Field(description="Timestamp of the snapshot")
    bar_index: int = Field(ge=0, description="Bar index in the session")

    # === Features ===
    features: PatternInput = Field(description="Feature vector at snapshot time")

    # === Context ===
    regime: str = Field(default="MIXED", description="Market regime at snapshot time")
    strategy: str = Field(default="", description="Strategy that generated signal")
    signal_type: str = Field(default="", description="Type of signal: long|short")

    # === Outcome ===
    outcome: PatternOutcome = Field(description="Forward-looking outcome")

    # === Metadata ===
    run_id: str = Field(default="", description="Backtest run ID")
    session_date: str = Field(default="", description="Session date YYYY-MM-DD")


class ClusterPattern(BaseModel):
    """
    Pattern discovered through clustering.

    Represents a cluster of similar market states with
    associated historical performance statistics.
    """

    # === Identity ===
    pattern_id: str = Field(description="Unique pattern identifier")
    pattern_type: PatternType = Field(default=PatternType.CLUSTER)
    pattern_name: str = Field(description="Human-readable name")

    # === Cluster Properties ===
    centroid: List[float] = Field(description="Cluster centroid in feature space")
    feature_names: List[str] = Field(
        default_factory=list, description="Feature names for centroid"
    )

    # === Performance Statistics ===
    win_rate: float = Field(ge=0.0, le=1.0, description="Historical win rate")
    avg_pnl_pct: float = Field(description="Average PnL%")
    support: int = Field(ge=1, description="Number of samples in cluster")
    confidence_interval: Tuple[float, float] = Field(description="95% CI for win rate")

    # === Direction ===
    direction: Direction = Field(description="Dominant direction")
    long_ratio: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Ratio of long signals"
    )

    # === Feature Importance ===
    feature_importance: Dict[str, float] = Field(
        default_factory=dict, description="Feature importance scores"
    )

    # === Recommended Parameters ===
    recommended_stop_atr: float = Field(
        default=1.5, description="Recommended ATR stop multiplier"
    )
    recommended_target_rr: float = Field(
        default=2.0, description="Recommended risk-reward ratio"
    )

    # === Metadata ===
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ticker: str = Field(default="", description="Ticker this pattern was discovered on")

    def compute_similarity(self, features: List[float]) -> float:
        """Compute similarity score between features and cluster centroid."""
        import math

        if len(features) != len(self.centroid):
            return 0.0

        # Euclidean distance
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(features, self.centroid)))

        # Convert to similarity (inverse relationship)
        # Using exponential decay: similarity = exp(-distance)
        similarity = math.exp(-distance)

        return min(1.0, max(0.0, similarity))


class SequentialPattern(BaseModel):
    """
    Pattern discovered through sequential pattern mining.

    Represents a sequence of market states that historically
    led to profitable outcomes.
    """

    # === Identity ===
    pattern_id: str = Field(description="Unique pattern identifier")
    pattern_type: PatternType = Field(default=PatternType.SEQUENTIAL)
    pattern_name: str = Field(description="Human-readable name")

    # === Sequence Properties ===
    sequence: List[str] = Field(description="Sequence of state labels")
    sequence_length: int = Field(ge=2, description="Length of the sequence (n-gram)")

    # === Performance Statistics ===
    win_rate: float = Field(ge=0.0, le=1.0, description="Historical win rate")
    avg_pnl_pct: float = Field(description="Average PnL%")
    support: int = Field(ge=1, description="Number of occurrences")
    confidence_interval: Tuple[float, float] = Field(description="95% CI for win rate")

    # === Direction ===
    direction: Direction = Field(description="Dominant direction")

    # === Metadata ===
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ticker: str = Field(default="", description="Ticker this pattern was discovered on")

    def matches(self, recent_states: List[str]) -> bool:
        """Check if recent states match this pattern sequence."""
        if len(recent_states) < len(self.sequence):
            return False

        # Check if the end of recent_states matches our sequence
        return recent_states[-len(self.sequence) :] == self.sequence


# ============================================================================
# Pattern Library
# ============================================================================


class PatternLibrary(BaseModel):
    """
    Collection of discovered patterns for a ticker.

    Persisted to JSON and loaded for real-time matching.
    """

    # === Identity ===
    ticker: str = Field(description="Ticker symbol")
    version: str = Field(default="v1", description="Library version")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # === Patterns ===
    cluster_patterns: List[ClusterPattern] = Field(default_factory=list)
    sequential_patterns: List[SequentialPattern] = Field(default_factory=list)

    # === Statistics ===
    total_snapshots_analyzed: int = Field(default=0, ge=0)
    discovery_config: Dict[str, Any] = Field(default_factory=dict)

    # === Metadata ===
    best_pattern_id: str = Field(
        default="", description="ID of best performing pattern"
    )
    coverage_ratio: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Ratio of bars with pattern matches"
    )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "PatternLibrary":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)


# ============================================================================
# Discovery Configuration
# ============================================================================


class DiscoveryConfig(BaseModel):
    """Configuration for pattern discovery."""

    # === Clustering ===
    clustering_enabled: bool = Field(default=True)
    clustering_k_range: Tuple[int, int] = Field(
        default=(50, 200), description="Range of k values to try"
    )
    clustering_method: str = Field(
        default="kmeans", description="Clustering method: kmeans|gmm"
    )

    # === Sequential Mining ===
    sequential_enabled: bool = Field(default=True)
    n_gram_range: Tuple[int, int] = Field(
        default=(2, 5), description="N-gram length range"
    )

    # === Filtering ===
    min_support: int = Field(default=10, ge=1, description="Minimum pattern support")
    min_win_rate: float = Field(
        default=0.55, ge=0.0, le=1.0, description="Minimum win rate"
    )
    min_sharpe: float = Field(default=1.0, description="Minimum Sharpe ratio")

    # === Feature Extraction ===
    lookback_bars: int = Field(
        default=20, ge=1, description="Lookback bars for context"
    )
    forward_bars: int = Field(default=10, ge=1, description="Forward bars for outcome")

    # === Validation ===
    validation_split: float = Field(
        default=0.2, ge=0.0, le=0.5, description="Validation split ratio"
    )
    cross_validation_folds: int = Field(
        default=5, ge=2, le=10, description="Number of CV folds"
    )


# ============================================================================
# API Request/Response Models
# ============================================================================


class DiscoverRequest(BaseModel):
    """Request to start pattern discovery job."""

    ticker: str
    date_from: str
    date_to: str
    discovery_config: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    strategy_api_url: str = Field(default="http://localhost:8001")
    runner_api_url: str = Field(default="http://localhost:8002")


class DiscoverResponse(BaseModel):
    """Response from pattern discovery job start."""

    job_id: str
    status: str
    progress: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MatchRequest(BaseModel):
    """Request for real-time pattern matching."""

    ticker: str
    feature_vector: Dict[str, Any]
    recent_states: List[str] = Field(default_factory=list)
    config: MatchConfig = Field(default_factory=MatchConfig)


class MatchResponse(BaseModel):
    """Response from pattern matching."""

    matches: List[PatternMatch]
    best_match: Optional[PatternMatch] = None
    match_timestamp: datetime = Field(default_factory=datetime.utcnow)


class EvidenceResponse(BaseModel):
    """Response with pattern evidence."""

    source_type: str = Field(default="pattern")
    source_name: str
    direction: str
    strength: float
    calibrated: float
    reasoning: str
