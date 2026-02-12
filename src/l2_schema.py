"""
L2 Schema - Schema definitions for L2 order flow features.

This module centralizes L2 feature keys and validation to ensure
consistent handling across all components.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# Core L2 payload keys from order flow processing
L2_PAYLOAD_KEYS: Set[str] = {
    "delta",
    "imbalance",
    "iceberg_bias",
    "participation_ratio",
    "directional_consistency",
    "signed_aggression",
    "book_pressure",
    "flow_score",
}

# Extended L2 keys for advanced analysis
L2_EXTENDED_KEYS: Set[str] = {
    "delta_acceleration",
    "delta_price_divergence",
    "absorption_score",
    "momentum_flow_score",
    "iceberg_detected",
    "large_lot_ratio",
    "spread_pct",
    "volume_imbalance",
}

# All L2 keys
L2_ALL_KEYS: Set[str] = L2_PAYLOAD_KEYS | L2_EXTENDED_KEYS


def get_default_l2_feature_bucket() -> Dict[str, float]:
    """
    Get default L2 feature bucket with zero values.
    
    Returns:
        Dictionary with all L2 keys set to 0.0
    """
    return {key: 0.0 for key in L2_ALL_KEYS}


def validate_l2_features(features: Dict[str, Any]) -> Dict[str, float]:
    """
    Validate and normalize L2 features dictionary.
    
    Args:
        features: Raw features dictionary
        
    Returns:
        Validated features with only known keys and float values
    """
    result = get_default_l2_feature_bucket()
    
    for key in L2_ALL_KEYS:
        if key in features:
            try:
                result[key] = float(features[key])
            except (TypeError, ValueError):
                result[key] = 0.0
    
    return result


def has_l2_coverage(
    features: Dict[str, Any],
    required_keys: Optional[Set[str]] = None,
) -> bool:
    """
    Check if features have L2 coverage for required keys.
    
    Args:
        features: Features dictionary to check
        required_keys: Optional set of required keys (defaults to L2_PAYLOAD_KEYS)
        
    Returns:
        True if all required keys are present with non-zero values
    """
    if required_keys is None:
        required_keys = L2_PAYLOAD_KEYS
    
    for key in required_keys:
        if key not in features:
            return False
        try:
            if float(features.get(key, 0.0)) == 0.0:
                return False
        except (TypeError, ValueError):
            return False
    
    return True


@dataclass
class L2FeatureStats:
    """Statistics for L2 feature coverage."""
    
    total_bars: int = 0
    bars_with_l2: int = 0
    coverage_pct: float = 0.0
    feature_means: Dict[str, float] = field(default_factory=dict)
    feature_stds: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_bars": self.total_bars,
            "bars_with_l2": self.bars_with_l2,
            "coverage_pct": self.coverage_pct,
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
        }


def compute_l2_stats(
    feature_map: Dict[int, Dict[str, float]],
) -> L2FeatureStats:
    """
    Compute statistics for L2 feature coverage.
    
    Args:
        feature_map: Map of minute keys to feature dictionaries
        
    Returns:
        L2FeatureStats with coverage and distribution info
    """
    if not feature_map:
        return L2FeatureStats()
    
    total_bars = len(feature_map)
    bars_with_l2 = 0
    
    # Accumulate for means
    feature_sums: Dict[str, float] = {key: 0.0 for key in L2_ALL_KEYS}
    
    for minute_key, features in feature_map.items():
        if has_l2_coverage(features):
            bars_with_l2 += 1
        
        for key in L2_ALL_KEYS:
            if key in features:
                try:
                    feature_sums[key] += float(features[key])
                except (TypeError, ValueError):
                    pass
    
    coverage_pct = (bars_with_l2 / total_bars * 100) if total_bars > 0 else 0.0
    
    # Compute means
    feature_means = {
        key: (feature_sums[key] / total_bars) if total_bars > 0 else 0.0
        for key in L2_ALL_KEYS
    }
    
    return L2FeatureStats(
        total_bars=total_bars,
        bars_with_l2=bars_with_l2,
        coverage_pct=coverage_pct,
        feature_means=feature_means,
    )
