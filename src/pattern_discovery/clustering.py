"""
Clustering Pattern Discovery - Discover patterns through K-Means/GMM clustering.

Groups similar market states into clusters and identifies those with
statistically significant win rates and PnL characteristics.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .models import (
    ClusterPattern,
    Direction,
    PatternType,
    PatternSnapshot,
    DiscoveryConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ClusteringResult:
    """Result of clustering pattern discovery."""
    patterns: List[ClusterPattern]
    optimal_k: int
    silhouette_score: float
    total_snapshots: int
    filtered_patterns: int
    discovery_errors: List[str] = field(default_factory=list)


class ClusterPatternDiscovery:
    """
    Discover patterns through clustering of feature vectors.
    
    Uses K-Means or Gaussian Mixture Models to group similar market
    states, then filters clusters by performance metrics.
    """
    
    def __init__(
        self,
        k_range: Tuple[int, int] = (50, 200),
        min_support: int = 10,
        min_win_rate: float = 0.55,
        min_sharpe: float = 1.0,
        method: str = "kmeans",
        random_state: int = 42,
    ):
        self.k_range = k_range
        self.min_support = min_support
        self.min_win_rate = min_win_rate
        self.min_sharpe = min_sharpe
        self.method = method
        self.random_state = random_state
        
        # Feature names for importance tracking
        self.feature_names = [
            "momentum_z", "rsi_z", "volume_z", "atr_z",
            "l2_delta_z", "l2_aggression_z", "l2_imbalance_z",
            "l2_book_pressure_z", "l2_flow_score_z",
            "trend_efficiency", "volatility_pct",
            "hour_norm", "minute_norm", "day_norm",
            "bar_body_ratio", "close_location", "gap_pct",
        ]
    
    def discover(
        self,
        snapshots: List[PatternSnapshot],
        ticker: str = "",
    ) -> ClusteringResult:
        """
        Discover cluster patterns from snapshots.
        
        Args:
            snapshots: List of PatternSnapshot objects
            ticker: Ticker symbol for pattern metadata
            
        Returns:
            ClusteringResult with discovered patterns
        """
        if len(snapshots) < self.min_support * 2:
            logger.warning(
                f"Insufficient snapshots for clustering: {len(snapshots)} "
                f"(need at least {self.min_support * 2})"
            )
            return ClusteringResult(
                patterns=[],
                optimal_k=0,
                silhouette_score=0.0,
                total_snapshots=len(snapshots),
                filtered_patterns=0,
                discovery_errors=["Insufficient data for clustering"],
            )
        
        # Convert to feature matrix
        X = np.array([s.features.to_vector() for s in snapshots])
        
        # Find optimal k
        optimal_k, silhouette = self._find_optimal_k(X)
        
        # Fit final model
        labels, centroids = self._fit_model(X, optimal_k)
        
        # Create patterns from clusters
        patterns = []
        for cluster_id in range(optimal_k):
            cluster_mask = labels == cluster_id
            cluster_snapshots = [s for s, m in zip(snapshots, cluster_mask) if m]
            
            if len(cluster_snapshots) < self.min_support:
                continue
            
            pattern = self._create_pattern(
                cluster_id=cluster_id,
                centroid=centroids[cluster_id],
                snapshots=cluster_snapshots,
                ticker=ticker,
            )
            
            # Filter by performance
            if pattern.win_rate >= self.min_win_rate:
                patterns.append(pattern)
        
        logger.info(
            f"Discovered {len(patterns)} cluster patterns from "
            f"{len(snapshots)} snapshots (k={optimal_k}, silhouette={silhouette:.3f})"
        )
        
        return ClusteringResult(
            patterns=patterns,
            optimal_k=optimal_k,
            silhouette_score=silhouette,
            total_snapshots=len(snapshots),
            filtered_patterns=len(patterns),
        )
    
    def _find_optimal_k(self, X: np.ndarray) -> Tuple[int, float]:
        """Find optimal number of clusters using silhouette score."""
        from sklearn.metrics import silhouette_score
        
        k_min, k_max = self.k_range
        k_max = min(k_max, len(X) // self.min_support)
        
        if k_min >= k_max:
            return k_min, 0.0
        
        best_k = k_min
        best_score = -1.0
        
        # Sample k values to test
        k_values = list(range(k_min, min(k_max + 1, k_min + 20)))
        
        for k in k_values:
            try:
                if self.method == "gmm":
                    from sklearn.mixture import GaussianMixture
                    model = GaussianMixture(
                        n_components=k,
                        random_state=self.random_state,
                        n_init=3,
                    )
                    labels = model.fit_predict(X)
                else:
                    from sklearn.cluster import KMeans
                    model = KMeans(
                        n_clusters=k,
                        random_state=self.random_state,
                        n_init=10,
                    )
                    labels = model.fit_predict(X)
                
                # Compute silhouette score
                if len(np.unique(labels)) > 1:
                    score = silhouette_score(X, labels)
                    if score > best_score:
                        best_score = score
                        best_k = k
            except Exception as e:
                logger.debug(f"Failed to evaluate k={k}: {e}")
                continue
        
        return best_k, best_score
    
    def _fit_model(
        self,
        X: np.ndarray,
        k: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Fit clustering model and return labels and centroids."""
        if self.method == "gmm":
            from sklearn.mixture import GaussianMixture
            model = GaussianMixture(
                n_components=k,
                random_state=self.random_state,
                n_init=5,
            )
            labels = model.fit_predict(X)
            centroids = model.means_
        else:
            from sklearn.cluster import KMeans
            model = KMeans(
                n_clusters=k,
                random_state=self.random_state,
                n_init=10,
            )
            labels = model.fit_predict(X)
            centroids = model.cluster_centers_
        
        return labels, centroids
    
    def _create_pattern(
        self,
        cluster_id: int,
        centroid: np.ndarray,
        snapshots: List[PatternSnapshot],
        ticker: str,
    ) -> ClusterPattern:
        """Create a ClusterPattern from cluster data."""
        
        # Compute performance statistics
        outcomes = [s.outcome for s in snapshots]
        win_count = sum(1 for o in outcomes if o.is_profitable)
        total_count = len(outcomes)
        win_rate = win_count / total_count if total_count > 0 else 0.0
        
        pnl_values = [o.pnl_pct for o in outcomes]
        avg_pnl = np.mean(pnl_values) if pnl_values else 0.0
        
        # Compute confidence interval for win rate
        ci_low, ci_high = self._compute_win_rate_ci(win_count, total_count)
        
        # Determine dominant direction
        long_count = sum(1 for s in snapshots if s.signal_type == "long")
        short_count = sum(1 for s in snapshots if s.signal_type == "short")
        
        if long_count > short_count:
            direction = Direction.BULLISH
            long_ratio = long_count / total_count if total_count > 0 else 0.5
        elif short_count > long_count:
            direction = Direction.BEARISH
            long_ratio = long_count / total_count if total_count > 0 else 0.5
        else:
            direction = Direction.NEUTRAL
            long_ratio = 0.5
        
        # Compute feature importance (variance within cluster)
        feature_vectors = np.array([s.features.to_vector() for s in snapshots])
        feature_std = np.std(feature_vectors, axis=0)
        feature_importance = {}
        
        for i, name in enumerate(self.feature_names):
            if i < len(feature_std):
                # Lower variance = more defining feature
                importance = 1.0 / (1.0 + feature_std[i])
                feature_importance[name] = float(importance)
        
        # Generate pattern name
        pattern_name = self._generate_pattern_name(centroid, direction)
        
        # Compute recommended parameters
        favorable_excursions = [o.max_favorable_excursion for o in outcomes if o.max_favorable_excursion > 0]
        adverse_excursions = [o.max_adverse_excursion for o in outcomes if o.max_adverse_excursion > 0]
        
        avg_favorable = np.mean(favorable_excursions) if favorable_excursions else 1.0
        avg_adverse = np.mean(adverse_excursions) if adverse_excursions else 0.5
        
        # Stop ATR based on adverse excursion
        recommended_stop = max(0.5, min(3.0, avg_adverse * 2))
        # Target RR based on favorable/adverse ratio
        recommended_rr = max(1.0, min(5.0, avg_favorable / max(avg_adverse, 0.1)))
        
        return ClusterPattern(
            pattern_id=f"cluster_{cluster_id}",
            pattern_type=PatternType.CLUSTER,
            pattern_name=pattern_name,
            centroid=centroid.tolist(),
            feature_names=self.feature_names,
            win_rate=win_rate,
            avg_pnl_pct=avg_pnl,
            support=total_count,
            confidence_interval=(ci_low, ci_high),
            direction=direction,
            long_ratio=long_ratio,
            feature_importance=feature_importance,
            recommended_stop_atr=recommended_stop,
            recommended_target_rr=recommended_rr,
            created_at=datetime.utcnow(),
            ticker=ticker,
        )
    
    def _compute_win_rate_ci(
        self,
        wins: int,
        total: int,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Compute confidence interval for win rate using Wilson score."""
        if total == 0:
            return (0.0, 1.0)
        
        from scipy import stats
        
        p = wins / total
        n = total
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        
        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denominator
        
        ci_low = max(0.0, center - margin)
        ci_high = min(1.0, center + margin)
        
        return (ci_low, ci_high)
    
    def _generate_pattern_name(
        self,
        centroid: np.ndarray,
        direction: Direction,
    ) -> str:
        """Generate a human-readable pattern name from centroid."""
        
        # Map feature indices to names
        feature_map = {
            0: ("momentum", centroid[0]),
            4: ("delta", centroid[4]),
            5: ("aggression", centroid[5]),
            6: ("imbalance", centroid[6]),
            7: ("book_pressure", centroid[7]),
            8: ("flow_score", centroid[8]),
        }
        
        # Find dominant features
        dominant = []
        for idx, (name, value) in feature_map.items():
            if abs(value) > 1.0:  # Significant z-score
                if value > 0:
                    dominant.append(f"high_{name}")
                else:
                    dominant.append(f"low_{name}")
        
        # Build name
        if dominant:
            feature_part = "_".join(dominant[:3])
        else:
            feature_part = "neutral"
        
        direction_str = direction.value if direction != Direction.NEUTRAL else "mixed"
        
        return f"{direction_str}_{feature_part}"


def discover_cluster_patterns(
    snapshots: List[PatternSnapshot],
    config: DiscoveryConfig,
    ticker: str = "",
) -> List[ClusterPattern]:
    """
    Convenience function to discover cluster patterns.
    
    Args:
        snapshots: List of PatternSnapshot objects
        config: Discovery configuration
        ticker: Ticker symbol
        
    Returns:
        List of ClusterPattern objects
    """
    discovery = ClusterPatternDiscovery(
        k_range=config.clustering_k_range,
        min_support=config.min_support,
        min_win_rate=config.min_win_rate,
        min_sharpe=config.min_sharpe,
        method=config.clustering_method,
    )
    
    result = discovery.discover(snapshots, ticker)
    return result.patterns


def compute_pattern_similarity(
    pattern: ClusterPattern,
    features: List[float],
) -> float:
    """
    Compute similarity between a pattern and feature vector.
    
    Uses exponential decay of Euclidean distance.
    """
    if len(features) != len(pattern.centroid):
        return 0.0
    
    distance = math.sqrt(
        sum((a - b) ** 2 for a, b in zip(features, pattern.centroid))
    )
    
    # Exponential decay: similarity = exp(-distance)
    similarity = math.exp(-distance)
    
    return min(1.0, max(0.0, similarity))
