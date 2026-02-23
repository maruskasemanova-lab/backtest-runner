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
