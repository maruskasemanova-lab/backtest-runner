#!/usr/bin/env python3
"""
Pattern Discovery CLI - Run pattern discovery from command line.

Usage:
    python scripts/run_pattern_discovery.py --ticker MU --date-from 2025-11-02 --date-to 2026-02-10
    python scripts/run_pattern_discovery.py --ticker MU --match --features '{"momentum_z": 1.5}'
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pattern_discovery import (
    PatternInput,
    PatternMatch,
    PatternLibrary,
    DiscoveryConfig,
    MatchConfig,
    extract_snapshots_from_backtest,
    discover_cluster_patterns,
    discover_sequential_patterns,
    PatternLibraryManager,
    PatternMatcher,
    format_evidence,
)
from src.pattern_discovery.models import DiscoverRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_discovery(
    ticker: str,
    date_from: str,
    date_to: str,
    config: DiscoveryConfig,
    output_path: Optional[Path] = None,
    reports_dir: Path = Path("reports"),
) -> PatternLibrary:
    """
    Run pattern discovery on historical data.
    
    Args:
        ticker: Ticker symbol
        date_from: Start date YYYY-MM-DD
        date_to: End date YYYY-MM-DD
        config: Discovery configuration
        output_path: Optional output path for library
        reports_dir: Directory containing backtest reports
        
    Returns:
        PatternLibrary with discovered patterns
    """
    logger.info(f"Starting pattern discovery for {ticker}")
    logger.info(f"Date range: {date_from} to {date_to}")
    
    # Phase 1: Extract snapshots
    logger.info("Phase 1: Extracting feature snapshots...")
    snapshots = extract_snapshots_from_backtest(
        ticker=ticker,
        date_from=date_from,
        date_to=date_to,
        reports_dir=reports_dir,
        config=config,
    )
    
    if not snapshots:
        logger.error("No snapshots extracted. Check your date range and reports directory.")
        sys.exit(1)
    
    logger.info(f"Extracted {len(snapshots)} snapshots")
    
    # Phase 2: Cluster pattern discovery
    cluster_patterns = []
    if config.clustering_enabled:
        logger.info("Phase 2: Discovering cluster patterns...")
        cluster_patterns = discover_cluster_patterns(
            snapshots=snapshots,
            config=config,
            ticker=ticker,
        )
        logger.info(f"Found {len(cluster_patterns)} cluster patterns")
    
    # Phase 3: Sequential pattern mining
    sequential_patterns = []
    if config.sequential_enabled:
        logger.info("Phase 3: Mining sequential patterns...")
        sequential_patterns = discover_sequential_patterns(
            snapshots=snapshots,
            config=config,
            ticker=ticker,
        )
        logger.info(f"Found {len(sequential_patterns)} sequential patterns")
    
    # Phase 4: Create and save library
    logger.info("Phase 4: Creating pattern library...")
    manager = PatternLibraryManager()
    library = manager.create_library(
        ticker=ticker,
        cluster_patterns=cluster_patterns,
        sequential_patterns=sequential_patterns,
        total_snapshots=len(snapshots),
        discovery_config=config,
    )
    
    saved_path = manager.save_library(library, output_path)
    logger.info(f"Pattern library saved to: {saved_path}")
    
    # Print summary
    print_summary(library)
    
    return library


def print_summary(library: PatternLibrary):
    """Print a summary of the discovered patterns."""
    print("\n" + "=" * 60)
    print(f"PATTERN DISCOVERY SUMMARY - {library.ticker}")
    print("=" * 60)
    print(f"Version: {library.version}")
    print(f"Total snapshots analyzed: {library.total_snapshots_analyzed}")
    print(f"Cluster patterns: {len(library.cluster_patterns)}")
    print(f"Sequential patterns: {len(library.sequential_patterns)}")
    
    if library.cluster_patterns:
        print("\n--- Top Cluster Patterns ---")
        sorted_clusters = sorted(
            library.cluster_patterns,
            key=lambda p: p.win_rate * p.support,
            reverse=True
        )
        for i, p in enumerate(sorted_clusters[:5]):
            print(f"\n{i+1}. {p.pattern_name}")
            print(f"   ID: {p.pattern_id}")
            print(f"   Win Rate: {p.win_rate:.1%}")
            print(f"   Support: {p.support}")
            print(f"   Avg PnL: {p.avg_pnl_pct:.2f}%")
            print(f"   Direction: {p.direction.value}")
    
    if library.sequential_patterns:
        print("\n--- Top Sequential Patterns ---")
        sorted_seq = sorted(
            library.sequential_patterns,
            key=lambda p: p.win_rate * p.support,
            reverse=True
        )
        for i, p in enumerate(sorted_seq[:5]):
            print(f"\n{i+1}. {p.pattern_name}")
            print(f"   ID: {p.pattern_id}")
            print(f"   Sequence: {' -> '.join(p.sequence)}")
            print(f"   Win Rate: {p.win_rate:.1%}")
            print(f"   Support: {p.support}")
            print(f"   Direction: {p.direction.value}")
    
    print("\n" + "=" * 60)


def run_match(
    ticker: str,
    features: Dict[str, Any],
    recent_states: List[str],
    config: MatchConfig,
    library_path: Optional[Path] = None,
) -> List[PatternMatch]:
    """
    Run pattern matching on current features.
    
    Args:
        ticker: Ticker symbol
        features: Feature vector dict
        recent_states: List of recent state labels
        config: Match configuration
        library_path: Optional path to library file
        
    Returns:
        List of PatternMatch objects
    """
    # Load matcher
    if library_path:
        matcher = PatternMatcher.from_library_path(library_path, config)
    else:
        matcher = PatternMatcher.for_ticker(ticker, config=config)
    
    if not matcher:
        logger.error(f"No pattern library found for {ticker}")
        sys.exit(1)
    
    # Convert features
    pattern_input = PatternInput.from_feature_vector(features)
    
    # Match patterns
    matches = matcher.match(pattern_input, recent_states)
    
    return matches


def print_matches(matches: List[PatternMatch]):
    """Print pattern matches."""
    if not matches:
        print("No matching patterns found.")
        return
    
    print("\n" + "=" * 60)
    print(f"PATTERN MATCHES ({len(matches)} found)")
    print("=" * 60)
    
    for i, m in enumerate(matches):
        print(f"\n{i+1}. {m.pattern_name}")
        print(f"   Type: {m.pattern_type.value}")
        print(f"   Similarity: {m.similarity_score:.2f}")
        print(f"   Win Rate: {m.historical_win_rate:.1%}")
        print(f"   Support: {m.historical_count}")
        print(f"   Direction: {m.direction.value}")
        print(f"   Action: {m.recommended_action.value}")
        print(f"   Evidence Strength: {m.evidence_strength:.1f}")
        print(f"   Reasoning: {m.evidence_reasoning}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Pattern Discovery CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover patterns from backtest reports
  python scripts/run_pattern_discovery.py --ticker MU --date-from 2025-11-02 --date-to 2026-02-10
  
  # Match current features against patterns
  python scripts/run_pattern_discovery.py --ticker MU --match --features '{"momentum_z": 1.5, "l2_delta_z": 2.0}'
  
  # List available libraries
  python scripts/run_pattern_discovery.py --list-libraries
        """,
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--discover",
        action="store_true",
        help="Run pattern discovery",
    )
    mode_group.add_argument(
        "--match",
        action="store_true",
        help="Run pattern matching",
    )
    mode_group.add_argument(
        "--list-libraries",
        action="store_true",
        help="List available pattern libraries",
    )
    
    # Common arguments
    parser.add_argument(
        "--ticker",
        type=str,
        required=False,
        help="Ticker symbol",
    )
    
    # Discovery arguments
    parser.add_argument(
        "--date-from",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--date-to",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default="reports",
        help="Directory containing backtest reports",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for pattern library",
    )
    
    # Discovery config
    parser.add_argument(
        "--min-support",
        type=int,
        default=10,
        help="Minimum pattern support",
    )
    parser.add_argument(
        "--min-win-rate",
        type=float,
        default=0.55,
        help="Minimum win rate for patterns",
    )
    parser.add_argument(
        "--k-min",
        type=int,
        default=50,
        help="Minimum number of clusters",
    )
    parser.add_argument(
        "--k-max",
        type=int,
        default=200,
        help="Maximum number of clusters",
    )
    parser.add_argument(
        "--no-clustering",
        action="store_true",
        help="Disable clustering",
    )
    parser.add_argument(
        "--no-sequential",
        action="store_true",
        help="Disable sequential mining",
    )
    
    # Match arguments
    parser.add_argument(
        "--features",
        type=str,
        help="Feature vector as JSON string",
    )
    parser.add_argument(
        "--recent-states",
        type=str,
        default="[]",
        help="Recent states as JSON array",
    )
    parser.add_argument(
        "--library-path",
        type=str,
        help="Path to pattern library file",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.7,
        help="Minimum similarity threshold",
    )
    
    args = parser.parse_args()
    
    # List libraries mode
    if args.list_libraries:
        manager = PatternLibraryManager()
        libraries = manager.list_libraries()
        
        if not libraries:
            print("No pattern libraries found.")
            return
        
        print("\nAvailable Pattern Libraries:")
        print("-" * 60)
        for lib in libraries:
            print(f"\nTicker: {lib['ticker']}")
            print(f"  Version: {lib['version']}")
            print(f"  Path: {lib['path']}")
            print(f"  Patterns: {lib['total_patterns']}")
            print(f"  Snapshots: {lib['total_snapshots_analyzed']}")
            print(f"  Updated: {lib['updated_at']}")
        return
    
    # Discovery mode
    if args.discover:
        if not args.ticker:
            parser.error("--ticker is required for discovery")
        if not args.date_from or not args.date_to:
            parser.error("--date-from and --date-to are required for discovery")
        
        config = DiscoveryConfig(
            clustering_enabled=not args.no_clustering,
            sequential_enabled=not args.no_sequential,
            clustering_k_range=(args.k_min, args.k_max),
            min_support=args.min_support,
            min_win_rate=args.min_win_rate,
        )
        
        output_path = Path(args.output) if args.output else None
        
        run_discovery(
            ticker=args.ticker,
            date_from=args.date_from,
            date_to=args.date_to,
            config=config,
            output_path=output_path,
            reports_dir=Path(args.reports_dir),
        )
        return
    
    # Match mode
    if args.match:
        if not args.ticker:
            parser.error("--ticker is required for matching")
        if not args.features:
            parser.error("--features is required for matching")
        
        try:
            features = json.loads(args.features)
            recent_states = json.loads(args.recent_states)
        except json.JSONDecodeError as e:
            parser.error(f"Invalid JSON: {e}")
        
        config = MatchConfig(
            min_similarity=args.min_similarity,
        )
        
        library_path = Path(args.library_path) if args.library_path else None
        
        matches = run_match(
            ticker=args.ticker,
            features=features,
            recent_states=recent_states,
            config=config,
            library_path=library_path,
        )
        
        print_matches(matches)
        
        # Output as JSON for programmatic use
        print("\nJSON Output:")
        print(json.dumps(
            [m.model_dump() for m in matches],
            indent=2,
            default=str,
        ))
        return


if __name__ == "__main__":
    main()
