"""
Pattern Library Manager - Persistence and management of discovered patterns.

Handles saving/loading pattern libraries to/from JSON files,
versioning, and pattern library operations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    ClusterPattern,
    SequentialPattern,
    PatternLibrary,
    DiscoveryConfig,
)

logger = logging.getLogger(__name__)

# Default library directory
DEFAULT_LIBRARY_DIR = Path("pattern_library")


class PatternLibraryManager:
    """
    Manage pattern library persistence and operations.

    Features:
    - Save/load pattern libraries to JSON
    - Version management
    - Pattern lookup and filtering
    - Library statistics
    """

    def __init__(
        self,
        library_dir: Path = DEFAULT_LIBRARY_DIR,
    ):
        self.library_dir = Path(library_dir)
        self.library_dir.mkdir(parents=True, exist_ok=True)

    def save_library(
        self,
        library: PatternLibrary,
        path: Optional[Path] = None,
    ) -> Path:
        """
        Save pattern library to JSON file.

        Args:
            library: PatternLibrary to save
            path: Optional custom path (default: {ticker}_patterns_{version}.json)

        Returns:
            Path to saved file
        """
        if path is None:
            filename = f"{library.ticker}_patterns_{library.version}.json"
            path = self.library_dir / filename

        # Update timestamp
        library.updated_at = datetime.utcnow()

        # Serialize to JSON
        json_str = library.to_json()

        # Write to file
        with open(path, "w") as f:
            f.write(json_str)

        logger.info(f"Saved pattern library to {path}")
        return path

    def load_library(
        self,
        path: Path,
    ) -> PatternLibrary:
        """
        Load pattern library from JSON file.

        Args:
            path: Path to library file

        Returns:
            PatternLibrary object
        """
        with open(path, "r") as f:
            json_str = f.read()

        library = PatternLibrary.from_json(json_str)
        logger.info(f"Loaded pattern library from {path}")
        return library

    def load_library_for_ticker(
        self,
        ticker: str,
        version: Optional[str] = None,
    ) -> Optional[PatternLibrary]:
        """
        Load the latest (or specific) pattern library for a ticker.

        Args:
            ticker: Ticker symbol
            version: Optional version string

        Returns:
            PatternLibrary or None if not found
        """
        ticker = ticker.upper()

        if version:
            filename = f"{ticker}_patterns_{version}.json"
            path = self.library_dir / filename
            if path.exists():
                return self.load_library(path)
            return None

        # Find latest version
        pattern_files = list(self.library_dir.glob(f"{ticker}_patterns_*.json"))

        if not pattern_files:
            return None

        # Sort by modification time (latest first)
        pattern_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        return self.load_library(pattern_files[0])

    def list_libraries(
        self,
        ticker: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List available pattern libraries.

        Args:
            ticker: Optional ticker filter

        Returns:
            List of library metadata dicts
        """
        if ticker:
            pattern = f"{ticker.upper()}_patterns_*.json"
        else:
            pattern = "*_patterns_*.json"

        libraries = []
        for path in self.library_dir.glob(pattern):
            try:
                library = self.load_library(path)
                libraries.append(
                    {
                        "path": str(path),
                        "ticker": library.ticker,
                        "version": library.version,
                        "created_at": library.created_at.isoformat(),
                        "updated_at": library.updated_at.isoformat(),
                        "cluster_patterns": len(library.cluster_patterns),
                        "sequential_patterns": len(library.sequential_patterns),
                        "total_patterns": len(library.cluster_patterns)
                        + len(library.sequential_patterns),
                        "total_snapshots_analyzed": library.total_snapshots_analyzed,
                        "best_pattern_id": library.best_pattern_id,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to load library {path}: {e}")

        return libraries

    def create_library(
        self,
        ticker: str,
        cluster_patterns: List[ClusterPattern],
        sequential_patterns: List[SequentialPattern],
        total_snapshots: int,
        discovery_config: DiscoveryConfig,
        version: str = "v1",
    ) -> PatternLibrary:
        """
        Create a new pattern library.

        Args:
            ticker: Ticker symbol
            cluster_patterns: List of cluster patterns
            sequential_patterns: List of sequential patterns
            total_snapshots: Total snapshots analyzed
            discovery_config: Discovery configuration used
            version: Library version

        Returns:
            New PatternLibrary object
        """
        # Find best pattern
        all_patterns = list(cluster_patterns) + list(sequential_patterns)
        best_pattern = (
            max(all_patterns, key=lambda p: p.win_rate * p.support)
            if all_patterns
            else None
        )

        library = PatternLibrary(
            ticker=ticker.upper(),
            version=version,
            cluster_patterns=cluster_patterns,
            sequential_patterns=sequential_patterns,
            total_snapshots_analyzed=total_snapshots,
            discovery_config=discovery_config.model_dump(),
            best_pattern_id=best_pattern.pattern_id if best_pattern else "",
        )

        return library

    def get_library_stats(
        self,
        library: PatternLibrary,
    ) -> Dict[str, Any]:
        """
        Get statistics for a pattern library.

        Args:
            library: PatternLibrary to analyze

        Returns:
            Dict with statistics
        """
        cluster_patterns = library.cluster_patterns
        sequential_patterns = library.sequential_patterns

        stats = {
            "ticker": library.ticker,
            "version": library.version,
            "total_patterns": len(cluster_patterns) + len(sequential_patterns),
            "cluster_patterns": len(cluster_patterns),
            "sequential_patterns": len(sequential_patterns),
            "total_snapshots_analyzed": library.total_snapshots_analyzed,
            "cluster_stats": {},
            "sequential_stats": {},
        }

        if cluster_patterns:
            win_rates = [p.win_rate for p in cluster_patterns]
            supports = [p.support for p in cluster_patterns]
            pnls = [p.avg_pnl_pct for p in cluster_patterns]

            stats["cluster_stats"] = {
                "avg_win_rate": sum(win_rates) / len(win_rates),
                "max_win_rate": max(win_rates),
                "min_win_rate": min(win_rates),
                "avg_support": sum(supports) / len(supports),
                "total_support": sum(supports),
                "avg_pnl_pct": sum(pnls) / len(pnls),
                "direction_distribution": self._count_directions(cluster_patterns),
            }

        if sequential_patterns:
            win_rates = [p.win_rate for p in sequential_patterns]
            supports = [p.support for p in sequential_patterns]
            pnls = [p.avg_pnl_pct for p in sequential_patterns]
            lengths = [p.sequence_length for p in sequential_patterns]

            stats["sequential_stats"] = {
                "avg_win_rate": sum(win_rates) / len(win_rates),
                "max_win_rate": max(win_rates),
                "min_win_rate": min(win_rates),
                "avg_support": sum(supports) / len(supports),
                "total_support": sum(supports),
                "avg_pnl_pct": sum(pnls) / len(pnls),
                "avg_sequence_length": sum(lengths) / len(lengths),
                "direction_distribution": self._count_directions(sequential_patterns),
            }

        return stats

    def _count_directions(
        self,
        patterns: List[ClusterPattern | SequentialPattern],
    ) -> Dict[str, int]:
        """Count pattern directions."""
        counts = {"bullish": 0, "bearish": 0, "neutral": 0}
        for p in patterns:
            direction = (
                p.direction.value if hasattr(p.direction, "value") else str(p.direction)
            )
            if direction in counts:
                counts[direction] += 1
        return counts
