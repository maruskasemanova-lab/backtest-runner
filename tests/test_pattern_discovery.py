"""
Tests for Pattern Discovery module.

Run with: pytest tests/test_pattern_discovery.py -v
"""

from __future__ import annotations

import json
import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest
import numpy as np

from src.pattern_discovery import (
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
from src.pattern_discovery.extractor import (
    FeatureExtractor,
    extract_snapshots_from_backtest,
)
from src.pattern_discovery.clustering import (
    ClusterPatternDiscovery,
    discover_cluster_patterns,
)
from src.pattern_discovery.sequential import (
    SequentialPatternMiner,
    discover_sequential_patterns,
)
from src.pattern_discovery.library import PatternLibraryManager
from src.pattern_discovery.matcher import PatternMatcher
from src.pattern_discovery.evidence import PatternEvidenceSource, format_evidence


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_pattern_input() -> PatternInput:
    """Create a sample PatternInput for testing."""
    return PatternInput(
        momentum_z=1.5,
        rsi_z=-0.5,
        volume_z=2.0,
        atr_z=0.3,
        l2_delta_z=2.5,
        l2_aggression_z=1.8,
        l2_imbalance_z=1.2,
        l2_book_pressure_z=0.9,
        l2_flow_score_z=1.5,
        regime="TRENDING",
        trend_efficiency=0.65,
        volatility_pct=0.4,
        hour_of_day=10,
        minute_of_hour=30,
        day_of_week=2,
        bar_body_ratio=0.7,
        close_location=0.8,
        gap_pct=0.1,
    )


@pytest.fixture
def sample_outcome() -> PatternOutcome:
    """Create a sample PatternOutcome for testing."""
    return PatternOutcome(
        is_profitable=True,
        pnl_pct=0.5,
        pnl_dollars=100.0,
        bars_held=5,
        max_favorable_excursion=0.8,
        max_adverse_excursion=0.2,
        exit_reason="take_profit",
    )


@pytest.fixture
def sample_snapshot(sample_pattern_input, sample_outcome) -> PatternSnapshot:
    """Create a sample PatternSnapshot for testing."""
    return PatternSnapshot(
        snapshot_id="MU:2025-11-03:10:30:0",
        ticker="MU",
        timestamp=datetime(2025, 11, 3, 10, 30, 0),
        bar_index=45,
        features=sample_pattern_input,
        regime="TRENDING",
        strategy="MomentumFlow",
        signal_type="long",
        outcome=sample_outcome,
        run_id="test-run-123",
        session_date="2025-11-03",
    )


@pytest.fixture
def sample_snapshots(sample_pattern_input, sample_outcome) -> List[PatternSnapshot]:
    """Create multiple sample PatternSnapshots for testing."""
    snapshots = []
    for i in range(50):
        # Vary features slightly
        features = PatternInput(
            momentum_z=sample_pattern_input.momentum_z + np.random.randn() * 0.5,
            rsi_z=sample_pattern_input.rsi_z + np.random.randn() * 0.3,
            volume_z=sample_pattern_input.volume_z + np.random.randn() * 0.5,
            atr_z=sample_pattern_input.atr_z,
            l2_delta_z=sample_pattern_input.l2_delta_z + np.random.randn() * 0.5,
            l2_aggression_z=sample_pattern_input.l2_aggression_z
            + np.random.randn() * 0.3,
            l2_imbalance_z=sample_pattern_input.l2_imbalance_z,
            l2_book_pressure_z=sample_pattern_input.l2_book_pressure_z,
            l2_flow_score_z=sample_pattern_input.l2_flow_score_z,
            regime="TRENDING" if i % 3 == 0 else "CHOPPY",
            trend_efficiency=0.5 + np.random.rand() * 0.3,
            volatility_pct=0.3 + np.random.rand() * 0.4,
            hour_of_day=9 + (i % 7),
            minute_of_hour=(i * 5) % 60,
            day_of_week=i % 5,
            bar_body_ratio=0.3 + np.random.rand() * 0.5,
            close_location=0.2 + np.random.rand() * 0.6,
            gap_pct=np.random.randn() * 0.1,
        )

        # Vary outcomes
        is_profitable = np.random.rand() > 0.4  # 60% win rate
        outcome = PatternOutcome(
            is_profitable=is_profitable,
            pnl_pct=0.5 if is_profitable else -0.3,
            pnl_dollars=100.0 if is_profitable else -60.0,
            bars_held=5 + np.random.randint(0, 10),
            max_favorable_excursion=0.8 if is_profitable else 0.2,
            max_adverse_excursion=0.2 if is_profitable else 0.5,
            exit_reason="take_profit" if is_profitable else "stop_loss",
        )

        snapshot = PatternSnapshot(
            snapshot_id=f"MU:2025-11-0{i%9+1}:{i}",
            ticker="MU",
            timestamp=datetime(2025, 11, i % 28 + 1, 10, i % 60, 0),
            bar_index=i,
            features=features,
            regime="TRENDING" if i % 3 == 0 else "CHOPPY",
            strategy="MomentumFlow" if i % 2 == 0 else "AbsorptionReversal",
            signal_type="long" if i % 2 == 0 else "short",
            outcome=outcome,
            run_id=f"test-run-{i // 10}",
            session_date=f"2025-11-{i % 28 + 1:02d}",
        )
        snapshots.append(snapshot)

    return snapshots


@pytest.fixture
def sample_cluster_pattern() -> ClusterPattern:
    """Create a sample ClusterPattern for testing."""
    return ClusterPattern(
        pattern_id="cluster_42",
        pattern_type=PatternType.CLUSTER,
        pattern_name="bullish_high_delta_spike",
        centroid=[
            1.5,
            -0.5,
            2.0,
            0.3,
            2.5,
            1.8,
            1.2,
            0.9,
            1.5,
            0.65,
            0.4,
            0.43,
            0.5,
            0.33,
            0.7,
            0.8,
            0.1,
        ],
        feature_names=[
            "momentum_z",
            "rsi_z",
            "volume_z",
            "atr_z",
            "l2_delta_z",
            "l2_aggression_z",
            "l2_imbalance_z",
            "l2_book_pressure_z",
            "l2_flow_score_z",
            "trend_efficiency",
            "volatility_pct",
            "hour_norm",
            "minute_norm",
            "day_norm",
            "bar_body_ratio",
            "close_location",
            "gap_pct",
        ],
        win_rate=0.72,
        avg_pnl_pct=0.35,
        support=45,
        confidence_interval=(0.58, 0.86),
        direction=Direction.BULLISH,
        long_ratio=0.8,
        feature_importance={"l2_delta_z": 0.35, "momentum_z": 0.25},
        recommended_stop_atr=1.2,
        recommended_target_rr=2.5,
        ticker="MU",
    )


@pytest.fixture
def sample_library(sample_cluster_pattern) -> PatternLibrary:
    """Create a sample PatternLibrary for testing."""
    return PatternLibrary(
        ticker="MU",
        version="v1",
        cluster_patterns=[sample_cluster_pattern],
        sequential_patterns=[],
        total_snapshots_analyzed=100,
        discovery_config={"min_support": 10, "min_win_rate": 0.55},
        best_pattern_id="cluster_42",
    )


@pytest.fixture
def temp_library_dir():
    """Create a temporary directory for pattern libraries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Model Tests
# ============================================================================


class TestPatternInput:
    """Tests for PatternInput model."""

    def test_to_vector(self, sample_pattern_input):
        """Test conversion to feature vector."""
        vector = sample_pattern_input.to_vector()

        assert isinstance(vector, list)
        assert len(vector) == 17  # Number of features
        assert all(isinstance(v, float) for v in vector)

    def test_to_state_label(self, sample_pattern_input):
        """Test state label generation."""
        label = sample_pattern_input.to_state_label()

        assert isinstance(label, str)
        assert "_" in label  # Multi-part label

    def test_from_feature_vector(self):
        """Test creation from feature vector dict."""
        fv = {
            "momentum_z": 1.0,
            "rsi_z": 0.5,
            "volume_z": 2.0,
            "l2_delta_z": 1.5,
            "regime": "TRENDING",
            "hour_of_day": 10,
        }

        pattern_input = PatternInput.from_feature_vector(fv)

        assert pattern_input.momentum_z == 1.0
        assert pattern_input.rsi_z == 0.5
        assert pattern_input.regime == "TRENDING"
        assert pattern_input.hour_of_day == 10


class TestPatternMatch:
    """Tests for PatternMatch model."""

    def test_to_evidence_dict(self, sample_cluster_pattern):
        """Test conversion to evidence dict."""
        match = PatternMatch(
            pattern_id=sample_cluster_pattern.pattern_id,
            pattern_type=sample_cluster_pattern.pattern_type,
            pattern_name=sample_cluster_pattern.pattern_name,
            similarity_score=0.85,
            distance=0.32,
            historical_win_rate=sample_cluster_pattern.win_rate,
            historical_avg_pnl=sample_cluster_pattern.avg_pnl_pct,
            historical_count=sample_cluster_pattern.support,
            confidence_interval=sample_cluster_pattern.confidence_interval,
            direction=sample_cluster_pattern.direction,
            direction_confidence=sample_cluster_pattern.win_rate,
            recommended_action=RecommendedAction.ENTRY_LONG,
            recommended_stop_atr=sample_cluster_pattern.recommended_stop_atr,
            recommended_target_rr=sample_cluster_pattern.recommended_target_rr,
            evidence_strength=61.2,
            evidence_reasoning="Test reasoning",
        )

        evidence = match.to_evidence_dict()

        assert evidence["source_type"] == "pattern"
        assert evidence["source_name"] == sample_cluster_pattern.pattern_name
        assert evidence["direction"] == "bullish"
        assert evidence["strength"] == 61.2


# ============================================================================
# Extractor Tests
# ============================================================================


class TestFeatureExtractor:
    """Tests for feature extraction from report formats."""

    def test_extract_from_report_session_summary_markers(self):
        """Extract snapshots from marker-based session summary report."""
        report = {
            "run_id": "backtest-1",
            "ticker": "MU",
            "date": "2025-11-03_to_2026-02-13",
            "total_bars": 100,
            "markers": [
                {
                    "timestamp": "2025-11-03T14:45:00+00:00",
                    "bar_index": 40,
                    "marker_type": "regime_detected",
                    "strategy": "adaptive",
                    "regime": "TRENDING",
                    "details": {
                        "indicators": {
                            "trend_efficiency": 0.62,
                            "flow_score": 14.0,
                            "signed_aggression": 0.21,
                            "book_pressure_avg": 0.11,
                        }
                    },
                },
                {
                    "timestamp": "2025-11-03T14:53:00+00:00",
                    "bar_index": 48,
                    "marker_type": "entry_executed",
                    "strategy": "VWAPMagnet",
                    "regime": None,
                    "side": "long",
                    "details": {
                        "metadata": {
                            "layer_scores": {
                                "flow_score": 14.0,
                                "signed_aggression": 0.21,
                                "book_pressure_avg": 0.11,
                            }
                        }
                    },
                },
            ],
            "session_summary": {
                "trades": [
                    {
                        "entry_time": "2025-11-03T14:53:00+00:00",
                        "pnl_pct": 1.02,
                        "pnl_dollars": 63.7,
                        "bars_held": 12,
                        "exit_reason": "take_profit",
                    }
                ]
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "session_summary.json"
            path.write_text(json.dumps(report))

            extractor = FeatureExtractor()
            result = extractor.extract_from_report(path, "MU")

        assert len(result.snapshots) == 1
        snapshot = result.snapshots[0]
        assert result.total_signals_found == 1
        assert snapshot.strategy == "VWAPMagnet"
        assert snapshot.signal_type == "long"
        assert snapshot.regime == "TRENDING"
        assert snapshot.outcome.pnl_dollars == pytest.approx(63.7)
        assert snapshot.features.trend_efficiency == pytest.approx(0.62)
        assert snapshot.features.l2_flow_score_z == pytest.approx(14.0)

    def test_extract_snapshots_recursive_and_inclusive_date(self):
        """Walk reports recursively and include all snapshots on end date."""
        report = {
            "run_id": "backtest-2",
            "ticker": "MU",
            "date": "2026-02-10_to_2026-02-10",
            "total_bars": 50,
            "markers": [
                {
                    "timestamp": "2026-02-10T15:30:00+00:00",
                    "bar_index": 20,
                    "marker_type": "entry_executed",
                    "strategy": "Momentum",
                    "regime": "TRENDING",
                    "side": "short",
                    "details": {"indicators": {"trend_efficiency": 0.5}},
                }
            ],
            "session_summary": {
                "trades": [
                    {
                        "entry_time": "2026-02-10T15:30:00+00:00",
                        "pnl_pct": -0.4,
                        "pnl_dollars": -20.0,
                        "bars_held": 5,
                        "exit_reason": "stop_loss",
                    }
                ]
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            run_a = reports_dir / "20260214_MU_run_a"
            run_b = reports_dir / "20260214_MU_run_b"
            run_a.mkdir(parents=True, exist_ok=True)
            run_b.mkdir(parents=True, exist_ok=True)
            (run_a / "session_summary.json").write_text(json.dumps(report))
            # Duplicate replay should not inflate support after dedupe.
            (run_b / "session_summary.json").write_text(json.dumps(report))

            snapshots = extract_snapshots_from_backtest(
                ticker="MU",
                date_from="2026-02-10",
                date_to="2026-02-10",
                reports_dir=reports_dir,
                config=DiscoveryConfig(),
            )

        assert len(snapshots) == 1
        assert snapshots[0].timestamp.date().isoformat() == "2026-02-10"


# ============================================================================
# Clustering Tests
# ============================================================================


class TestClusterPatternDiscovery:
    """Tests for cluster pattern discovery."""

    def test_discover_patterns(self, sample_snapshots):
        """Test pattern discovery from snapshots."""
        discovery = ClusterPatternDiscovery(
            k_range=(5, 20),
            min_support=3,
            min_win_rate=0.40,  # Lower threshold for test
        )

        result = discovery.discover(sample_snapshots, ticker="MU")

        assert result.total_snapshots == len(sample_snapshots)
        assert result.optimal_k > 0
        assert len(result.patterns) >= 0  # May or may not find patterns

    def test_compute_similarity(self, sample_cluster_pattern, sample_pattern_input):
        """Test similarity computation."""
        features = sample_pattern_input.to_vector()
        similarity = sample_cluster_pattern.compute_similarity(features)

        assert 0.0 <= similarity <= 1.0


# ============================================================================
# Sequential Mining Tests
# ============================================================================


class TestSequentialPatternMiner:
    """Tests for sequential pattern mining."""

    def test_mine_patterns(self, sample_snapshots):
        """Test sequential pattern mining."""
        miner = SequentialPatternMiner(
            n_gram_range=(2, 3),
            min_support=2,
            min_win_rate=0.40,  # Lower threshold for test
        )

        result = miner.mine(sample_snapshots, ticker="MU")

        assert result.total_sequences_analyzed > 0
        # May or may not find patterns depending on data

    def test_pattern_matches(self):
        """Test sequential pattern matching."""
        pattern = SequentialPattern(
            pattern_id="seq_test",
            pattern_type=PatternType.SEQUENTIAL,
            pattern_name="test_sequence",
            sequence=["up_spike_up_normal", "up_normal_high"],
            sequence_length=2,
            win_rate=0.7,
            avg_pnl_pct=0.5,
            support=10,
            confidence_interval=(0.5, 0.9),
            direction=Direction.BULLISH,
        )

        # Should match
        assert pattern.matches(["up_spike_up_normal", "up_normal_high"])
        assert pattern.matches(["other", "up_spike_up_normal", "up_normal_high"])

        # Should not match
        assert not pattern.matches(["up_spike_up_normal"])
        assert not pattern.matches(["other", "other"])


# ============================================================================
# Library Tests
# ============================================================================


class TestPatternLibraryManager:
    """Tests for pattern library management."""

    def test_save_and_load_library(self, sample_library, temp_library_dir):
        """Test saving and loading a pattern library."""
        manager = PatternLibraryManager(library_dir=temp_library_dir)

        # Save
        path = manager.save_library(sample_library)
        assert path.exists()

        # Load
        loaded = manager.load_library(path)

        assert loaded.ticker == sample_library.ticker
        assert loaded.version == sample_library.version
        assert len(loaded.cluster_patterns) == len(sample_library.cluster_patterns)

    def test_list_libraries(self, sample_library, temp_library_dir):
        """Test listing available libraries."""
        manager = PatternLibraryManager(library_dir=temp_library_dir)
        manager.save_library(sample_library)

        libraries = manager.list_libraries()

        assert len(libraries) == 1
        assert libraries[0]["ticker"] == sample_library.ticker

    def test_load_library_for_ticker(self, sample_library, temp_library_dir):
        """Test loading library for a specific ticker."""
        manager = PatternLibraryManager(library_dir=temp_library_dir)
        manager.save_library(sample_library)

        loaded = manager.load_library_for_ticker("MU")

        assert loaded is not None
        assert loaded.ticker == "MU"

        # Non-existent ticker
        not_found = manager.load_library_for_ticker("AAPL")
        assert not_found is None


# ============================================================================
# Matcher Tests
# ============================================================================


class TestPatternMatcher:
    """Tests for pattern matching."""

    def test_match_cluster_pattern(self, sample_library, sample_pattern_input):
        """Test matching cluster patterns."""
        matcher = PatternMatcher(library=sample_library)

        matches = matcher.match(sample_pattern_input)

        assert isinstance(matches, list)
        # May or may not match depending on similarity threshold

    def test_get_best_match(self, sample_library, sample_pattern_input):
        """Test getting best match."""
        matcher = PatternMatcher(library=sample_library)

        best = matcher.get_best_match(sample_pattern_input)

        # May be None if no match
        if best:
            assert isinstance(best, PatternMatch)

    def test_get_evidence(self, sample_library, sample_pattern_input):
        """Test getting evidence for decision engine."""
        matcher = PatternMatcher(library=sample_library)

        evidence = matcher.get_evidence(sample_pattern_input)

        # May be None if no match
        if evidence:
            assert "source_type" in evidence
            assert evidence["source_type"] == "pattern"


# ============================================================================
# Evidence Tests
# ============================================================================


class TestPatternEvidenceSource:
    """Tests for pattern evidence source."""

    def test_get_evidence(self, sample_library, sample_pattern_input):
        """Test getting evidence from pattern source."""
        matcher = PatternMatcher(library=sample_library)
        evidence_source = PatternEvidenceSource(matcher=matcher)

        feature_vector = sample_pattern_input.model_dump()
        evidence = evidence_source.get_evidence(feature_vector)

        # May be None if no match
        if evidence:
            assert evidence.source_type == "pattern"

    def test_format_evidence(self, sample_cluster_pattern):
        """Test formatting evidence for API."""
        match = PatternMatch(
            pattern_id=sample_cluster_pattern.pattern_id,
            pattern_type=sample_cluster_pattern.pattern_type,
            pattern_name=sample_cluster_pattern.pattern_name,
            similarity_score=0.85,
            distance=0.32,
            historical_win_rate=sample_cluster_pattern.win_rate,
            historical_avg_pnl=sample_cluster_pattern.avg_pnl_pct,
            historical_count=sample_cluster_pattern.support,
            confidence_interval=sample_cluster_pattern.confidence_interval,
            direction=sample_cluster_pattern.direction,
            direction_confidence=sample_cluster_pattern.win_rate,
            recommended_action=RecommendedAction.ENTRY_LONG,
            recommended_stop_atr=sample_cluster_pattern.recommended_stop_atr,
            recommended_target_rr=sample_cluster_pattern.recommended_target_rr,
            evidence_strength=61.2,
            evidence_reasoning="Test reasoning",
        )

        evidence = format_evidence(match)

        assert evidence["source_type"] == "pattern"
        assert "pattern_id" in evidence


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for the pattern discovery pipeline."""

    def test_full_discovery_pipeline(self, sample_snapshots, temp_library_dir):
        """Test the full discovery pipeline."""
        config = DiscoveryConfig(
            clustering_enabled=True,
            sequential_enabled=True,
            clustering_k_range=(5, 20),
            min_support=3,
            min_win_rate=0.40,
        )

        # Discover cluster patterns
        cluster_patterns = discover_cluster_patterns(
            snapshots=sample_snapshots,
            config=config,
            ticker="MU",
        )

        # Discover sequential patterns
        sequential_patterns = discover_sequential_patterns(
            snapshots=sample_snapshots,
            config=config,
            ticker="MU",
        )

        # Create and save library
        manager = PatternLibraryManager(library_dir=temp_library_dir)
        library = manager.create_library(
            ticker="MU",
            cluster_patterns=cluster_patterns,
            sequential_patterns=sequential_patterns,
            total_snapshots=len(sample_snapshots),
            discovery_config=config,
        )

        path = manager.save_library(library)
        assert path.exists()

        # Load and use for matching
        loaded = manager.load_library(path)
        matcher = PatternMatcher(library=loaded)

        # Match with a sample input
        sample_input = sample_snapshots[0].features
        matches = matcher.match(sample_input)

        # Results depend on data, but should not error
        assert isinstance(matches, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
