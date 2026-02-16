"""
Pattern Discovery Engine - Experimental module for discovering recurring market patterns.

This module provides:
- Offline pattern discovery from historical backtest data
- Real-time pattern matching for trading decisions
- Integration with EvidenceDecisionEngine as an evidence source
- Pattern-aware adaptive tuning

Architecture:
- Standalone service (port 8003) communicating via API
- No modifications to existing backtest-runner or strategy-engine code
- Optional integration through configuration
"""

from .models import (
    PatternInput,
    PatternMatch,
    PatternSnapshot,
    PatternOutcome,
    ClusterPattern,
    SequentialPattern,
    PatternLibrary,
    DiscoveryConfig,
    MatchConfig,
    PatternType,
    Direction,
    RecommendedAction,
)
from .extractor import FeatureExtractor, extract_snapshots_from_backtest
from .clustering import ClusterPatternDiscovery, discover_cluster_patterns
from .sequential import SequentialPatternMiner, discover_sequential_patterns
from .library import PatternLibraryManager
from .matcher import PatternMatcher
from .evidence import PatternEvidenceSource, format_evidence

__all__ = [
    # Models
    "PatternInput",
    "PatternMatch",
    "PatternSnapshot",
    "PatternOutcome",
    "ClusterPattern",
    "SequentialPattern",
    "PatternLibrary",
    "DiscoveryConfig",
    "MatchConfig",
    "PatternType",
    "Direction",
    "RecommendedAction",
    # Extraction
    "FeatureExtractor",
    "extract_snapshots_from_backtest",
    # Discovery
    "ClusterPatternDiscovery",
    "discover_cluster_patterns",
    "SequentialPatternMiner",
    "discover_sequential_patterns",
    # Library
    "PatternLibraryManager",
    # Matching
    "PatternMatcher",
    # Evidence
    "PatternEvidenceSource",
    "format_evidence",
]

__version__ = "0.1.0"
