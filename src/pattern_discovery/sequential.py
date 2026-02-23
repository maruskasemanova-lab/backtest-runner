"""
Sequential Pattern Mining - Discover patterns through n-gram analysis.

Identifies sequences of market states that historically led to
profitable outcomes using n-gram frequency analysis.
"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .models import (
    SequentialPattern,
    Direction,
    PatternType,
    PatternSnapshot,
    DiscoveryConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class SequentialMiningResult:
    """Result of sequential pattern mining."""

    patterns: List[SequentialPattern]
    total_sequences_analyzed: int
    unique_ngrams_found: int
    filtered_patterns: int
    mining_errors: List[str] = field(default_factory=list)


class SequentialPatternMiner:
    """
    Discover sequential patterns through n-gram mining.

    Converts continuous feature vectors into discrete state labels,
    then mines frequent n-grams that precede profitable outcomes.
    """

    def __init__(
        self,
        n_gram_range: Tuple[int, int] = (2, 5),
        min_support: int = 5,
        min_win_rate: float = 0.60,  # Higher threshold for sequences
        min_confidence: float = 0.5,
    ):
        self.n_gram_range = n_gram_range
        self.min_support = min_support
        self.min_win_rate = min_win_rate
        self.min_confidence = min_confidence

    def mine(
        self,
        snapshots: List[PatternSnapshot],
        ticker: str = "",
    ) -> SequentialMiningResult:
        """
        Mine sequential patterns from snapshots.

        Args:
            snapshots: List of PatternSnapshot objects (must be ordered by time)
            ticker: Ticker symbol for pattern metadata

        Returns:
            SequentialMiningResult with discovered patterns
        """
        if len(snapshots) < self.min_support * 2:
            logger.warning(
                f"Insufficient snapshots for sequential mining: {len(snapshots)}"
            )
            return SequentialMiningResult(
                patterns=[],
                total_sequences_analyzed=0,
                unique_ngrams_found=0,
                filtered_patterns=0,
                mining_errors=["Insufficient data for sequential mining"],
            )

        # Group snapshots by session (run_id + date)
        sessions = self._group_by_session(snapshots)

        # Convert to state sequences
        state_sequences = []
        for session_key, session_snapshots in sessions.items():
            # Sort by bar_index
            sorted_snapshots = sorted(session_snapshots, key=lambda s: s.bar_index)
            state_sequence = [s.features.to_state_label() for s in sorted_snapshots]
            outcomes = [s.outcome for s in sorted_snapshots]
            directions = [s.signal_type for s in sorted_snapshots]
            state_sequences.append((state_sequence, outcomes, directions))

        # Mine n-grams
        all_patterns = []
        n_min, n_max = self.n_gram_range

        for n in range(n_min, n_max + 1):
            ngram_outcomes: Dict[Tuple[str, ...], List[PatternOutcome]] = defaultdict(
                list
            )
            ngram_directions: Dict[Tuple[str, ...], List[str]] = defaultdict(list)

            for state_seq, outcomes, directions in state_sequences:
                # Extract n-grams with their outcomes
                for i in range(len(state_seq) - n + 1):
                    ngram = tuple(state_seq[i : i + n])
                    # Outcome is for the bar AFTER the n-gram
                    if i + n < len(outcomes):
                        ngram_outcomes[ngram].append(outcomes[i + n])
                        ngram_directions[ngram].append(directions[i + n])

            # Create patterns from frequent n-grams
            for ngram, outcomes in ngram_outcomes.items():
                if len(outcomes) < self.min_support:
                    continue

                pattern = self._create_pattern(
                    ngram=ngram,
                    outcomes=outcomes,
                    directions=ngram_directions[ngram],
                    ticker=ticker,
                )

                if pattern and pattern.win_rate >= self.min_win_rate:
                    all_patterns.append(pattern)

        # Remove duplicate/subsumed patterns
        unique_patterns = self._remove_subsumed_patterns(all_patterns)

        # Sort by win rate * support
        unique_patterns.sort(
            key=lambda p: p.win_rate * math.log(p.support + 1), reverse=True
        )

        logger.info(
            f"Discovered {len(unique_patterns)} sequential patterns from "
            f"{len(snapshots)} snapshots"
        )

        return SequentialMiningResult(
            patterns=unique_patterns,
            total_sequences_analyzed=len(state_sequences),
            unique_ngrams_found=len(all_patterns),
            filtered_patterns=len(unique_patterns),
        )

    def _group_by_session(
        self,
        snapshots: List[PatternSnapshot],
    ) -> Dict[str, List[PatternSnapshot]]:
        """Group snapshots by session (run_id + date)."""
        sessions: Dict[str, List[PatternSnapshot]] = defaultdict(list)

        for snapshot in snapshots:
            session_key = f"{snapshot.run_id}:{snapshot.session_date}"
            sessions[session_key].append(snapshot)

        return sessions

    def _create_pattern(
        self,
        ngram: Tuple[str, ...],
        outcomes: List[PatternOutcome],
        directions: List[str],
        ticker: str,
    ) -> Optional[SequentialPattern]:
        """Create a SequentialPattern from n-gram data."""

        total_count = len(outcomes)
        win_count = sum(1 for o in outcomes if o.is_profitable)
        win_rate = win_count / total_count if total_count > 0 else 0.0

        pnl_values = [o.pnl_pct for o in outcomes]
        avg_pnl = np.mean(pnl_values) if pnl_values else 0.0

        # Compute confidence interval
        ci_low, ci_high = self._compute_win_rate_ci(win_count, total_count)

        # Determine dominant direction
        long_count = sum(1 for d in directions if d == "long")
        short_count = sum(1 for d in directions if d == "short")

        if long_count > short_count:
            direction = Direction.BULLISH
        elif short_count > long_count:
            direction = Direction.BEARISH
        else:
            direction = Direction.NEUTRAL

        # Generate pattern name
        pattern_name = self._generate_pattern_name(ngram, direction)

        return SequentialPattern(
            pattern_id=f"seq_{'_'.join(ngram)}",
            pattern_type=PatternType.SEQUENTIAL,
            pattern_name=pattern_name,
            sequence=list(ngram),
            sequence_length=len(ngram),
            win_rate=win_rate,
            avg_pnl_pct=avg_pnl,
            support=total_count,
            confidence_interval=(ci_low, ci_high),
            direction=direction,
            created_at=datetime.utcnow(),
            ticker=ticker,
        )

    def _compute_win_rate_ci(
        self,
        wins: int,
        total: int,
        confidence: float = 0.95,
    ) -> Tuple[float, float]:
        """Compute confidence interval for win rate."""
        if total == 0:
            return (0.0, 1.0)

        p = wins / total
        z = 1.96  # 95% confidence

        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator

        return (max(0.0, center - margin), min(1.0, center + margin))

    def _generate_pattern_name(
        self,
        ngram: Tuple[str, ...],
        direction: Direction,
    ) -> str:
        """Generate a human-readable pattern name."""

        # Summarize the sequence
        unique_states = set(ngram)

        # Look for key transitions
        has_spike_up = any("spike_up" in state for state in ngram)
        has_spike_down = any("spike_down" in state for state in ngram)
        has_high_vol = any("high" in state and "vol" in state for state in ngram)

        parts = []
        if has_spike_up:
            parts.append("delta_spike_up")
        if has_spike_down:
            parts.append("delta_spike_down")
        if has_high_vol:
            parts.append("high_vol")

        if not parts:
            parts = list(ngram[:2])  # Use first 2 states

        direction_str = direction.value if direction != Direction.NEUTRAL else "mixed"

        return f"{direction_str}_seq_{'_'.join(parts)}"

    def _remove_subsumed_patterns(
        self,
        patterns: List[SequentialPattern],
    ) -> List[SequentialPattern]:
        """Remove patterns that are subsumed by better patterns."""

        # Sort by win rate * support
        patterns.sort(key=lambda p: p.win_rate * math.log(p.support + 1), reverse=True)

        kept_patterns = []

        for pattern in patterns:
            # Check if this pattern is subsumed by any kept pattern
            is_subsumed = False

            for kept in kept_patterns:
                # A pattern is subsumed if:
                # 1. Its sequence is a suffix of another pattern's sequence
                # 2. And the other pattern has better or equal performance

                if self._is_suffix_of(pattern.sequence, kept.sequence):
                    if kept.win_rate >= pattern.win_rate:
                        is_subsumed = True
                        break

            if not is_subsumed:
                kept_patterns.append(pattern)

        return kept_patterns

    def _is_suffix_of(
        self,
        shorter: List[str],
        longer: List[str],
    ) -> bool:
        """Check if shorter is a suffix of longer."""
        if len(shorter) >= len(longer):
            return False
        return longer[-len(shorter) :] == shorter


def discover_sequential_patterns(
    snapshots: List[PatternSnapshot],
    config: DiscoveryConfig,
    ticker: str = "",
) -> List[SequentialPattern]:
    """
    Convenience function to discover sequential patterns.

    Args:
        snapshots: List of PatternSnapshot objects
        config: Discovery configuration
        ticker: Ticker symbol

    Returns:
        List of SequentialPattern objects
    """
    miner = SequentialPatternMiner(
        n_gram_range=config.n_gram_range,
        min_support=config.min_support,
        min_win_rate=config.min_win_rate,
    )

    result = miner.mine(snapshots, ticker)
    return result.patterns
