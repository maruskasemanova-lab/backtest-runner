"""
Pattern Evidence Source - Integration with EvidenceDecisionEngine.

Provides pattern matching results as an evidence source for the
strategy engine's EvidenceDecisionEngine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    PatternInput,
    PatternMatch,
    PatternLibrary,
    MatchConfig,
    Direction,
)
from .matcher import PatternMatcher
from .library import PatternLibraryManager

logger = logging.getLogger(__name__)


@dataclass
class EvidenceSource:
    """
    Evidence source for EvidenceDecisionEngine.
    
    Mirrors the EvidenceSource structure from strategy-engine
    for compatibility.
    """
    source_type: str
    source_name: str
    direction: str
    strength: float  # 0-100
    calibrated: float  # 0-1 P(profitable)
    reasoning: str = ""


class PatternEvidenceSource:
    """
    Pattern discovery as an evidence source.
    
    Integrates with EvidenceDecisionEngine by providing
    evidence from pattern matching results.
    """
    
    def __init__(
        self,
        matcher: PatternMatcher,
        enabled: bool = True,
        min_evidence_strength: float = 30.0,
    ):
        self.matcher = matcher
        self.enabled = enabled
        self.min_evidence_strength = min_evidence_strength
        self._last_evidence: Optional[EvidenceSource] = None
    
    @classmethod
    def from_library_path(
        cls,
        library_path: Path,
        config: MatchConfig = None,
        enabled: bool = True,
        min_evidence_strength: float = 30.0,
    ) -> "PatternEvidenceSource":
        """Create evidence source from library file path."""
        matcher = PatternMatcher.from_library_path(library_path, config)
        return cls(
            matcher=matcher,
            enabled=enabled,
            min_evidence_strength=min_evidence_strength,
        )
    
    @classmethod
    def for_ticker(
        cls,
        ticker: str,
        version: Optional[str] = None,
        library_dir: Path = None,
        config: MatchConfig = None,
        enabled: bool = True,
        min_evidence_strength: float = 30.0,
    ) -> Optional["PatternEvidenceSource"]:
        """Create evidence source for a ticker."""
        matcher = PatternMatcher.for_ticker(ticker, version, library_dir, config)
        if matcher is None:
            return None
        return cls(
            matcher=matcher,
            enabled=enabled,
            min_evidence_strength=min_evidence_strength,
        )
    
    def get_evidence(
        self,
        feature_vector: Dict[str, Any],
        recent_states: Optional[List[str]] = None,
    ) -> Optional[EvidenceSource]:
        """
        Get evidence from pattern matching.
        
        Args:
            feature_vector: Feature vector dict (from FeatureVector)
            recent_states: Optional list of recent state labels
            
        Returns:
            EvidenceSource or None if no match
        """
        if not self.enabled:
            return None
        
        # Convert dict to PatternInput
        features = PatternInput.from_feature_vector(feature_vector)
        
        # Get best match
        best_match = self.matcher.get_best_match(features, recent_states)
        
        if best_match is None:
            return None
        
        # Check minimum evidence strength
        if best_match.evidence_strength < self.min_evidence_strength:
            return None
        
        # Create evidence source
        evidence = EvidenceSource(
            source_type="pattern",
            source_name=best_match.pattern_name,
            direction=best_match.direction.value,
            strength=best_match.evidence_strength,
            calibrated=best_match.historical_win_rate,
            reasoning=best_match.evidence_reasoning,
        )
        
        self._last_evidence = evidence
        return evidence
    
    def get_all_evidence(
        self,
        feature_vector: Dict[str, Any],
        recent_states: Optional[List[str]] = None,
        max_evidence: int = 3,
    ) -> List[EvidenceSource]:
        """
        Get all matching evidence sources.
        
        Args:
            feature_vector: Feature vector dict
            recent_states: Optional recent state labels
            max_evidence: Maximum number of evidence sources to return
            
        Returns:
            List of EvidenceSource objects
        """
        if not self.enabled:
            return []
        
        features = PatternInput.from_feature_vector(feature_vector)
        matches = self.matcher.match(features, recent_states)
        
        evidence_list = []
        for match in matches[:max_evidence]:
            if match.evidence_strength >= self.min_evidence_strength:
                evidence = EvidenceSource(
                    source_type="pattern",
                    source_name=match.pattern_name,
                    direction=match.direction.value,
                    strength=match.evidence_strength,
                    calibrated=match.historical_win_rate,
                    reasoning=match.evidence_reasoning,
                )
                evidence_list.append(evidence)
        
        return evidence_list
    
    def get_last_evidence(self) -> Optional[EvidenceSource]:
        """Get the last computed evidence."""
        return self._last_evidence
    
    def reset(self):
        """Reset the evidence source state."""
        self.matcher.reset_state()
        self._last_evidence = None


def format_evidence(
    match: PatternMatch,
) -> Dict[str, Any]:
    """
    Format a pattern match as evidence dict.
    
    This is the format expected by EvidenceDecisionEngine.
    
    Args:
        match: PatternMatch object
        
    Returns:
        Dict with evidence fields
    """
    return {
        "source_type": "pattern",
        "pattern_id": match.pattern_id,
        "source_name": match.pattern_name,
        "direction": match.direction.value,
        "strength": match.evidence_strength,
        "calibrated": match.historical_win_rate,
        "reasoning": match.evidence_reasoning,
    }


def format_evidence_for_api(
    match: PatternMatch,
) -> Dict[str, Any]:
    """
    Format evidence for API response.
    
    Args:
        match: PatternMatch object
        
    Returns:
        Dict with API-compatible evidence fields
    """
    return {
        "source_type": "pattern",
        "source_name": match.pattern_name,
        "direction": match.direction.value,
        "strength": round(match.evidence_strength, 2),
        "calibrated": round(match.historical_win_rate, 4),
        "reasoning": match.evidence_reasoning,
        "pattern_id": match.pattern_id,
        "pattern_type": match.pattern_type.value,
        "similarity_score": round(match.similarity_score, 4),
        "historical_count": match.historical_count,
        "recommended_action": match.recommended_action.value,
    }


class EvidenceAggregator:
    """
    Aggregate multiple pattern evidence sources.
    
    Combines evidence from multiple pattern matches into
    a single evidence score.
    """
    
    def __init__(
        self,
        combination_method: str = "weighted_average",
        min_evidence_count: int = 1,
    ):
        self.combination_method = combination_method
        self.min_evidence_count = min_evidence_count
    
    def aggregate(
        self,
        evidence_list: List[EvidenceSource],
    ) -> Optional[EvidenceSource]:
        """
        Aggregate multiple evidence sources into one.
        
        Args:
            evidence_list: List of EvidenceSource objects
            
        Returns:
            Aggregated EvidenceSource or None
        """
        if len(evidence_list) < self.min_evidence_count:
            return None
        
        if not evidence_list:
            return None
        
        if len(evidence_list) == 1:
            return evidence_list[0]
        
        if self.combination_method == "weighted_average":
            return self._weighted_average(evidence_list)
        elif self.combination_method == "max":
            return self._max_strength(evidence_list)
        elif self.combination_method == "voting":
            return self._voting(evidence_list)
        else:
            return evidence_list[0]
    
    def _weighted_average(
        self,
        evidence_list: List[EvidenceSource],
    ) -> EvidenceSource:
        """Compute weighted average of evidence."""
        total_weight = sum(e.strength for e in evidence_list)
        
        if total_weight == 0:
            return evidence_list[0]
        
        # Weighted average of calibrated values
        weighted_calibrated = sum(
            e.calibrated * e.strength for e in evidence_list
        ) / total_weight
        
        # Weighted average of strength
        avg_strength = total_weight / len(evidence_list)
        
        # Determine direction by voting
        direction_votes = {}
        for e in evidence_list:
            direction_votes[e.direction] = direction_votes.get(e.direction, 0) + e.strength
        
        dominant_direction = max(direction_votes, key=direction_votes.get)
        
        # Combine reasoning
        top_reasons = sorted(evidence_list, key=lambda e: e.strength, reverse=True)[:2]
        reasoning = " | ".join(e.reasoning for e in top_reasons)
        
        return EvidenceSource(
            source_type="pattern_aggregated",
            source_name=f"aggregated_{len(evidence_list)}_patterns",
            direction=dominant_direction,
            strength=avg_strength,
            calibrated=weighted_calibrated,
            reasoning=reasoning,
        )
    
    def _max_strength(
        self,
        evidence_list: List[EvidenceSource],
    ) -> EvidenceSource:
        """Return evidence with maximum strength."""
        return max(evidence_list, key=lambda e: e.strength)
    
    def _voting(
        self,
        evidence_list: List[EvidenceSource],
    ) -> EvidenceSource:
        """Combine evidence through voting."""
        # Count votes for each direction
        direction_votes: Dict[str, List[EvidenceSource]] = {}
        for e in evidence_list:
            if e.direction not in direction_votes:
                direction_votes[e.direction] = []
            direction_votes[e.direction].append(e)
        
        # Find winning direction
        winning_direction = max(
            direction_votes,
            key=lambda d: sum(e.strength for e in direction_votes[d])
        )
        
        winning_evidence = direction_votes[winning_direction]
        
        # Average strength and calibrated for winning direction
        avg_strength = sum(e.strength for e in winning_evidence) / len(winning_evidence)
        avg_calibrated = sum(e.calibrated for e in winning_evidence) / len(winning_evidence)
        
        return EvidenceSource(
            source_type="pattern_voting",
            source_name=f"voting_{len(winning_evidence)}_patterns",
            direction=winning_direction,
            strength=avg_strength,
            calibrated=avg_calibrated,
            reasoning=f"Voting result from {len(evidence_list)} patterns",
        )
