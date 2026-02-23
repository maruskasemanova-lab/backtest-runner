"""
Feature Extractor - Extract feature snapshots from backtest results.

Extracts PatternSnapshot objects from historical backtest runs by:
1. Loading backtest reports (JSON)
2. Extracting feature vectors at signal/decision points
3. Computing forward outcomes (PnL, bars held, etc.)
4. Creating labeled PatternSnapshot objects
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .models import (
    PatternInput,
    PatternSnapshot,
    PatternOutcome,
    DiscoveryConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of feature extraction."""

    snapshots: List[PatternSnapshot]
    total_bars_processed: int
    total_signals_found: int
    extraction_errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_signals_found == 0:
            return 0.0
        return len(self.snapshots) / self.total_signals_found


class FeatureExtractor:
    """
    Extract feature snapshots from backtest data.

    Works with:
    - Backtest reports (JSON files from reports/)
    - Session summaries (JSON files from reports/)
    - Raw bar data with L2 features
    """

    def __init__(
        self,
        lookback_bars: int = 20,
        forward_bars: int = 10,
        min_price_move_pct: float = 0.1,
    ):
        self.lookback_bars = lookback_bars
        self.forward_bars = forward_bars
        self.min_price_move_pct = min_price_move_pct

    def extract_from_report(
        self,
        report_path: Path,
        ticker: str,
    ) -> ExtractionResult:
        """
        Extract snapshots from a backtest report file.

        Args:
            report_path: Path to report JSON file
            ticker: Ticker symbol

        Returns:
            ExtractionResult with snapshots and statistics
        """
        snapshots = []
        errors = []
        total_bars = 0
        total_signals = 0

        try:
            with open(report_path, "r") as f:
                report = json.load(f)
        except Exception as e:
            errors.append(f"Failed to load report {report_path}: {e}")
            return ExtractionResult(
                snapshots=[],
                total_bars_processed=0,
                total_signals_found=0,
                extraction_errors=errors,
            )

        # Handle daily report format
        if "days" in report:
            for day_data in report["days"]:
                day_result = self._extract_from_day(day_data, ticker)
                snapshots.extend(day_result.snapshots)
                total_bars += day_result.total_bars_processed
                total_signals += day_result.total_signals_found
                errors.extend(day_result.extraction_errors)

        # Handle single session format
        elif "decisions" in report:
            day_result = self._extract_from_session(report, ticker)
            snapshots.extend(day_result.snapshots)
            total_bars += day_result.total_bars_processed
            total_signals += day_result.total_signals_found
            errors.extend(day_result.extraction_errors)

        # Handle session_summary format used by backtest-runner reports
        elif "markers" in report:
            day_result = self._extract_from_markers_report(report, ticker)
            snapshots.extend(day_result.snapshots)
            total_bars += day_result.total_bars_processed
            total_signals += day_result.total_signals_found
            errors.extend(day_result.extraction_errors)

        return ExtractionResult(
            snapshots=snapshots,
            total_bars_processed=total_bars,
            total_signals_found=total_signals,
            extraction_errors=errors,
        )

    def _extract_from_day(
        self,
        day_data: Dict[str, Any],
        ticker: str,
    ) -> ExtractionResult:
        """Extract snapshots from a single day's data."""
        snapshots = []
        errors = []
        total_bars = day_data.get("total_bars", 0)
        total_signals = 0

        decisions = day_data.get("decisions", [])
        trades = day_data.get("trades", [])

        # Create trade lookup by entry time
        trade_map = {}
        for trade in trades:
            entry_time = trade.get("entry_time")
            if entry_time:
                trade_map[entry_time] = trade

        # Extract from decisions
        for decision in decisions:
            marker_type = decision.get("marker_type", "")

            # Look for signal decisions
            if "signal" in marker_type.lower() or "entry" in marker_type.lower():
                total_signals += 1

                try:
                    snapshot = self._create_snapshot_from_decision(
                        decision, day_data, ticker, trade_map
                    )
                    if snapshot:
                        snapshots.append(snapshot)
                except Exception as e:
                    errors.append(f"Failed to extract snapshot from decision: {e}")

        return ExtractionResult(
            snapshots=snapshots,
            total_bars_processed=total_bars,
            total_signals_found=total_signals,
            extraction_errors=errors,
        )

    def _extract_from_session(
        self,
        session_data: Dict[str, Any],
        ticker: str,
    ) -> ExtractionResult:
        """Extract snapshots from a single session."""
        # Similar to _extract_from_day but for session format
        return self._extract_from_day(session_data, ticker)

    def _extract_from_markers_report(
        self,
        report: Dict[str, Any],
        ticker: str,
    ) -> ExtractionResult:
        """Extract snapshots from marker-based session_summary reports."""
        markers = report.get("markers", [])
        if not isinstance(markers, list) or not markers:
            return ExtractionResult(
                snapshots=[],
                total_bars_processed=int(report.get("total_bars", 0) or 0),
                total_signals_found=0,
                extraction_errors=[],
            )

        # Prefer executed entries for clean outcome labeling. Fallback to raw signals.
        entry_markers = [
            m
            for m in markers
            if isinstance(m, dict) and m.get("marker_type") == "entry_executed"
        ]
        signal_markers = [
            m
            for m in markers
            if isinstance(m, dict) and m.get("marker_type") == "signal_generated"
        ]
        candidate_markers = entry_markers if entry_markers else signal_markers

        regime_markers = [
            m
            for m in markers
            if isinstance(m, dict) and m.get("marker_type") == "regime_detected"
        ]

        decisions = [
            self._normalize_marker_decision(marker, regime_markers)
            for marker in candidate_markers
        ]

        session_summary = report.get("session_summary", {})
        trades = []
        if isinstance(session_summary, dict):
            trades = session_summary.get("trades", []) or []
        if not trades:
            trades = report.get("trades", []) or []

        pseudo_day = {
            "date": report.get("date")
            or (
                session_summary.get("date") if isinstance(session_summary, dict) else ""
            ),
            "run_id": report.get("run_id")
            or (
                session_summary.get("run_id")
                if isinstance(session_summary, dict)
                else ""
            ),
            "total_bars": report.get("total_bars", 0),
            "decisions": decisions,
            "trades": trades,
        }
        return self._extract_from_day(pseudo_day, ticker)

    def _normalize_marker_decision(
        self,
        marker: Dict[str, Any],
        regime_markers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Normalize marker payload to the decision schema used by extractor."""
        normalized = dict(marker)
        details = normalized.get("details", {})
        details = details if isinstance(details, dict) else {}
        metadata = details.get("metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}

        indicators = details.get("indicators", {})
        indicators = dict(indicators) if isinstance(indicators, dict) else {}

        metadata_indicators = metadata.get("indicators", {})
        if isinstance(metadata_indicators, dict):
            indicators.update(metadata_indicators)

        # If signal marker has no direct indicators, borrow latest known regime metrics.
        if not indicators:
            latest_regime = self._latest_regime_for_bar(
                regime_markers, marker.get("bar_index")
            )
            if latest_regime:
                regime_details = latest_regime.get("details", {})
                if isinstance(regime_details, dict):
                    regime_indicators = regime_details.get("indicators", {})
                    if isinstance(regime_indicators, dict):
                        indicators.update(regime_indicators)
                if not normalized.get("regime"):
                    normalized["regime"] = latest_regime.get("regime")

        # Layer scores often carry flow metrics in session summary format.
        layer_scores = metadata.get("layer_scores", {})
        if isinstance(layer_scores, dict):
            for key in (
                "flow_score",
                "signed_aggression",
                "book_pressure_avg",
                "book_pressure_trend",
            ):
                if key not in indicators and key in layer_scores:
                    indicators[key] = layer_scores.get(key)

        # Prefer explicit signal_type when side is missing.
        if not normalized.get("side"):
            signal_type = details.get("signal_type")
            if isinstance(signal_type, str):
                normalized["side"] = signal_type.lower()

        details["indicators"] = indicators
        normalized["details"] = details
        return normalized

    def _latest_regime_for_bar(
        self,
        regime_markers: List[Dict[str, Any]],
        bar_index: Any,
    ) -> Optional[Dict[str, Any]]:
        """Find most recent regime marker for the given bar index."""
        target_bar = self._safe_int(bar_index, -1)
        if target_bar < 0:
            return None

        best = None
        best_bar = -1
        for marker in regime_markers:
            marker_bar = self._safe_int(marker.get("bar_index"), -1)
            if 0 <= marker_bar <= target_bar and marker_bar >= best_bar:
                best = marker
                best_bar = marker_bar
        return best

    def _create_snapshot_from_decision(
        self,
        decision: Dict[str, Any],
        day_data: Dict[str, Any],
        ticker: str,
        trade_map: Dict[str, Any],
    ) -> Optional[PatternSnapshot]:
        """Create a PatternSnapshot from a decision marker."""

        timestamp_str = decision.get("timestamp")
        if not timestamp_str:
            return None

        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except:
            return None

        # Extract features from decision details
        details = decision.get("details", {})
        indicators = details.get("indicators", {})

        # Create PatternInput from available data
        features = PatternInput(
            momentum_z=self._safe_float(indicators.get("momentum_z", 0.0)),
            rsi_z=self._safe_float(indicators.get("rsi_z", 0.0)),
            volume_z=self._safe_float(indicators.get("volume_z", 0.0)),
            atr_z=self._safe_float(indicators.get("atr_z", 0.0)),
            l2_delta_z=self._safe_float(indicators.get("l2_delta_z", 0.0)),
            l2_aggression_z=self._safe_float(indicators.get("signed_aggression", 0.0)),
            l2_imbalance_z=self._safe_float(indicators.get("imbalance", 0.0)),
            l2_book_pressure_z=self._safe_float(
                indicators.get("book_pressure_avg", 0.0)
            ),
            l2_flow_score_z=self._safe_float(indicators.get("flow_score", 0.0)),
            regime=decision.get("regime", "MIXED") or "MIXED",
            trend_efficiency=self._safe_float(indicators.get("trend_efficiency", 0.5)),
            volatility_pct=0.5,  # Default
            hour_of_day=timestamp.hour,
            minute_of_hour=timestamp.minute,
            day_of_week=timestamp.weekday(),
            bar_body_ratio=self._safe_float(indicators.get("bar_body_ratio", 0.5)),
            close_location=self._safe_float(indicators.get("close_location", 0.5)),
            gap_pct=self._safe_float(indicators.get("gap_pct", 0.0)),
        )

        # Find matching trade for outcome
        outcome = self._compute_outcome(decision, trade_map, day_data)

        # Create snapshot
        snapshot_id = f"{ticker}:{timestamp_str}:{decision.get('bar_index', 0)}"

        return PatternSnapshot(
            snapshot_id=snapshot_id,
            ticker=ticker,
            timestamp=timestamp,
            bar_index=decision.get("bar_index", 0),
            features=features,
            regime=decision.get("regime", "MIXED") or "MIXED",
            strategy=decision.get("strategy", "") or "",
            signal_type=self._determine_signal_type(decision),
            outcome=outcome,
            run_id=day_data.get("run_id", ""),
            session_date=day_data.get("date", ""),
        )

    def _compute_outcome(
        self,
        decision: Dict[str, Any],
        trade_map: Dict[str, Any],
        day_data: Dict[str, Any],
    ) -> PatternOutcome:
        """Compute forward outcome from decision."""

        # Try to find matching trade
        timestamp_str = decision.get("timestamp", "")
        trade = trade_map.get(timestamp_str)

        if trade:
            return PatternOutcome(
                is_profitable=trade.get("pnl_pct", 0) > 0,
                pnl_pct=self._safe_float(trade.get("pnl_pct", 0.0)),
                pnl_dollars=self._safe_float(trade.get("pnl_dollars", 0.0)),
                bars_held=trade.get("bars_held", 0),
                max_favorable_excursion=self._safe_float(
                    trade.get("max_favorable_excursion", 0.0)
                ),
                max_adverse_excursion=self._safe_float(
                    trade.get("max_adverse_excursion", 0.0)
                ),
                exit_reason=trade.get("exit_reason", ""),
            )

        # No matching trade - compute from price data if available
        # This is a fallback for decisions that didn't result in trades
        return PatternOutcome(
            is_profitable=False,
            pnl_pct=0.0,
            pnl_dollars=0.0,
            bars_held=0,
            exit_reason="no_trade",
        )

    def _determine_signal_type(self, decision: Dict[str, Any]) -> str:
        """Determine signal type from decision."""
        side = decision.get("side", "")
        marker_type = decision.get("marker_type", "").lower()

        if "long" in marker_type or side == "long":
            return "long"
        elif "short" in marker_type or side == "short":
            return "short"
        return "unknown"

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float."""
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert value to int."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return default


def extract_snapshots_from_backtest(
    ticker: str,
    date_from: str,
    date_to: str,
    reports_dir: Path,
    config: DiscoveryConfig,
) -> List[PatternSnapshot]:
    """
    Extract feature snapshots from backtest reports.

    Args:
        ticker: Ticker symbol
        date_from: Start date YYYY-MM-DD
        date_to: End date YYYY-MM-DD
        reports_dir: Directory containing backtest reports
        config: Discovery configuration

    Returns:
        List of PatternSnapshot objects
    """
    extractor = FeatureExtractor(
        lookback_bars=config.lookback_bars,
        forward_bars=config.forward_bars,
    )

    all_snapshots = []

    # Find report files recursively for the ticker and date range
    ticker_lower = ticker.lower()
    for report_file in reports_dir.rglob("*.json"):
        file_hint = f"{report_file.parent.name}/{report_file.name}".lower()
        if ticker_lower not in file_hint:
            continue
        try:
            result = extractor.extract_from_report(report_file, ticker)
            all_snapshots.extend(result.snapshots)

            if result.extraction_errors:
                logger.warning(
                    f"Extraction errors in {report_file}: "
                    f"{len(result.extraction_errors)}"
                )
        except Exception as e:
            logger.error(f"Failed to process {report_file}: {e}")

    # Filter by date range
    start_date = datetime.strptime(date_from, "%Y-%m-%d").date()
    end_date = datetime.strptime(date_to, "%Y-%m-%d").date()

    filtered_snapshots = [
        s for s in all_snapshots if start_date <= s.timestamp.date() <= end_date
    ]

    # Deduplicate repeated replay runs to reduce bias in pattern support.
    unique_snapshots: Dict[Tuple[str, str, int, str, str], PatternSnapshot] = {}
    for snapshot in filtered_snapshots:
        key = (
            snapshot.ticker.upper(),
            snapshot.timestamp.isoformat(),
            int(snapshot.bar_index),
            snapshot.strategy or "",
            snapshot.signal_type or "",
        )
        unique_snapshots.setdefault(key, snapshot)
    deduped_snapshots = list(unique_snapshots.values())

    logger.info(
        f"Extracted {len(deduped_snapshots)} snapshots for {ticker} "
        f"from {date_from} to {date_to}"
    )

    return deduped_snapshots
