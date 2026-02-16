"""
Pattern Matcher - Real-time pattern matching for trading decisions.

Matches current market state against discovered patterns and
returns pattern matches with evidence for decision making.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    PatternInput,
    PatternMatch,
    PatternLibrary,
    ClusterPattern,
    SequentialPattern,
    MatchConfig,
    Direction,
    PatternType,
    RecommendedAction,
)
from .library import PatternLibraryManager

logger = logging.getLogger(__name__)


@dataclass
class MatcherState:
    """State maintained by the pattern matcher."""
    recent_states: deque = field(default_factory=lambda: deque(maxlen=10))
    last_match_time: Optional[datetime] = None
    match_count: int = 0


class PatternMatcher:
    """
    Real-time pattern matching engine.
    
    Matches current feature vectors against pattern library
    and returns evidence for trading decisions.
    """
    
    def __init__(
        self,
        library: PatternLibrary,
        config: MatchConfig = None,
    ):
        self.library = library
        self.config = config or MatchConfig()
        self.state = MatcherState()
        
        # Pre-compute pattern lookup structures
        self._cluster_patterns = library.cluster_patterns
        self._sequential_patterns = library.sequential_patterns
    
    @classmethod
    def from_library_path(
        cls,
        library_path: Path,
        config: MatchConfig = None,
    ) -> "PatternMatcher":
        """Create matcher from library file path."""
        manager = PatternLibraryManager()
        library = manager.load_library(library_path)
        return cls(library=library, config=config)
    
    @classmethod
    def for_ticker(
        cls,
        ticker: str,
        version: Optional[str] = None,
        library_dir: Path = None,
        config: MatchConfig = None,
    ) -> Optional["PatternMatcher"]:
        """Create matcher for a ticker (loads latest library)."""
        manager = PatternLibraryManager(library_dir) if library_dir else PatternLibraryManager()
        library = manager.load_library_for_ticker(ticker, version)
        
        if library is None:
            logger.warning(f"No pattern library found for {ticker}")
            return None
        
        return cls(library=library, config=config)
    
    def match(
        self,
        features: PatternInput,
        recent_states: Optional[List[str]] = None,
    ) -> List[PatternMatch]:
        """
        Find matching patterns for current feature vector.
        
        Args:
            features: Current market state features
            recent_states: Optional list of recent state labels for sequential matching
            
        Returns:
            List of PatternMatch objects sorted by evidence strength
        """
        matches = []
        feature_vector = features.to_vector()
        
        # Update state
        current_state = features.to_state_label()
        self.state.recent_states.append(current_state)
        if recent_states:
            for state in recent_states[-10:]:
                self.state.recent_states.append(state)
        
        # 1. Match cluster patterns
        for pattern in self._cluster_patterns:
            match = self._match_cluster_pattern(pattern, feature_vector)
            if match:
                matches.append(match)
        
        # 2. Match sequential patterns
        recent_state_list = list(self.state.recent_states)
        for pattern in self._sequential_patterns:
            match = self._match_sequential_pattern(pattern, recent_state_list)
            if match:
                matches.append(match)
        
        # Apply filters
        matches = self._apply_filters(matches)
        
        # Sort by evidence strength
        matches.sort(key=lambda m: m.evidence_strength, reverse=True)
        
        # Limit results
        matches = matches[:self.config.max_matches]
        
        # Update state
        if matches:
            self.state.last_match_time = datetime.utcnow()
            self.state.match_count += 1
        
        return matches
    
    def _match_cluster_pattern(
        self,
        pattern: ClusterPattern,
        feature_vector: List[float],
    ) -> Optional[PatternMatch]:
        """Match a cluster pattern against feature vector."""
        
        # Compute similarity
        similarity = pattern.compute_similarity(feature_vector)
        
        # Check threshold
        if similarity < self.config.min_similarity:
            return None
        
        # Compute distance
        distance = math.sqrt(
            sum((a - b) ** 2 for a, b in zip(feature_vector, pattern.centroid))
        )
        
        # Determine recommended action
        action = self._get_recommended_action(pattern.direction, similarity)
        
        # Compute evidence strength
        evidence_strength = similarity * pattern.win_rate * 100
        
        # Generate reasoning
        reasoning = (
            f"Pattern '{pattern.pattern_name}' matched "
            f"(similarity: {similarity:.2f}, historical WR: {pattern.win_rate:.1%})"
        )
        
        return PatternMatch(
            pattern_id=pattern.pattern_id,
            pattern_type=PatternType.CLUSTER,
            pattern_name=pattern.pattern_name,
            similarity_score=similarity,
            distance=distance,
            historical_win_rate=pattern.win_rate,
            historical_avg_pnl=pattern.avg_pnl_pct,
            historical_count=pattern.support,
            confidence_interval=pattern.confidence_interval,
            direction=pattern.direction,
            direction_confidence=pattern.win_rate,
            recommended_action=action,
            recommended_stop_atr=pattern.recommended_stop_atr,
            recommended_target_rr=pattern.recommended_target_rr,
            evidence_strength=evidence_strength,
            evidence_reasoning=reasoning,
        )
    
    def _match_sequential_pattern(
        self,
        pattern: SequentialPattern,
        recent_states: List[str],
    ) -> Optional[PatternMatch]:
        """Match a sequential pattern against recent states."""
        
        # Check if pattern matches
        if not pattern.matches(recent_states):
            return None
        
        # Full match - similarity is 1.0
        similarity = 1.0
        distance = 0.0
        
        # Determine recommended action
        action = self._get_recommended_action(pattern.direction, similarity)
        
        # Compute evidence strength
        evidence_strength = similarity * pattern.win_rate * 100
        
        # Generate reasoning
        reasoning = (
            f"Sequential pattern '{pattern.pattern_name}' matched "
            f"(sequence: {' -> '.join(pattern.sequence)}, historical WR: {pattern.win_rate:.1%})"
        )
        
        return PatternMatch(
            pattern_id=pattern.pattern_id,
            pattern_type=PatternType.SEQUENTIAL,
            pattern_name=pattern.pattern_name,
            similarity_score=similarity,
            distance=distance,
            historical_win_rate=pattern.win_rate,
            historical_avg_pnl=pattern.avg_pnl_pct,
            historical_count=pattern.support,
            confidence_interval=pattern.confidence_interval,
            direction=pattern.direction,
            direction_confidence=pattern.win_rate,
            recommended_action=action,
            recommended_stop_atr=1.5,  # Default for sequential
            recommended_target_rr=2.0,
            evidence_strength=evidence_strength,
            evidence_reasoning=reasoning,
        )
    
    def _get_recommended_action(
        self,
        direction: Direction,
        similarity: float,
    ) -> RecommendedAction:
        """Determine recommended action from direction and similarity."""
        if similarity < 0.5:
            return RecommendedAction.NEUTRAL
        
        if direction == Direction.BULLISH:
            return RecommendedAction.ENTRY_LONG
        elif direction == Direction.BEARISH:
            return RecommendedAction.ENTRY_SHORT
        else:
            return RecommendedAction.NEUTRAL
    
    def _apply_filters(
        self,
        matches: List[PatternMatch],
    ) -> List[PatternMatch]:
        """Apply configuration filters to matches."""
        filtered = []
        
        for match in matches:
            # Win rate filter
            if match.historical_win_rate < self.config.min_win_rate:
                continue
            
            # Support filter
            if match.historical_count < self.config.min_support:
                continue
            
            # Direction filter
            if self.config.direction_filter == "bullish_only":
                if match.direction != Direction.BULLISH:
                    continue
            elif self.config.direction_filter == "bearish_only":
                if match.direction != Direction.BEARISH:
                    continue
            
            filtered.append(match)
        
        return filtered
    
    def get_best_match(
        self,
        features: PatternInput,
        recent_states: Optional[List[str]] = None,
    ) -> Optional[PatternMatch]:
        """Get the best matching pattern."""
        matches = self.match(features, recent_states)
        return matches[0] if matches else None
    
    def get_evidence(
        self,
        features: PatternInput,
        recent_states: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get evidence dict for EvidenceDecisionEngine."""
        best = self.get_best_match(features, recent_states)
        
        if best is None:
            return None
        
        return best.to_evidence_dict()
    
    def reset_state(self):
        """Reset matcher state."""
        self.state = MatcherState()


class MultiLibraryMatcher:
    """
    Pattern matcher that can work with multiple pattern libraries.
    
    Useful for cross-ticker pattern matching or ensemble approaches.
    """
    
    def __init__(
        self,
        libraries: Dict[str, PatternLibrary],
        config: MatchConfig = None,
    ):
        self.libraries = libraries
        self.config = config or MatchConfig()
        self.matchers = {
            ticker: PatternMatcher(lib, config)
            for ticker, lib in libraries.items()
        }
    
    def match(
        self,
        ticker: str,
        features: PatternInput,
        recent_states: Optional[List[str]] = None,
    ) -> List[PatternMatch]:
        """Match patterns for a specific ticker."""
        matcher = self.matchers.get(ticker)
        if matcher is None:
            return []
        return matcher.match(features, recent_states)
    
    def match_all(
        self,
        features: PatternInput,
        recent_states: Optional[List[str]] = None,
    ) -> Dict[str, List[PatternMatch]]:
        """Match patterns across all libraries."""
        results = {}
        for ticker, matcher in self.matchers.items():
            matches = matcher.match(features, recent_states)
            if matches:
                results[ticker] = matches
        return results
