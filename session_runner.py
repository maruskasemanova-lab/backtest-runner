"""
Session Runner - Orchestrates the connection between data source and strategy evaluator.
"""

import asyncio
import aiohttp
import math
import os
import time as time_module
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import logging

from decision_tracker import DecisionTracker, MarkerType
from performance_tracker import PerformanceTracker
from strategy_api_auth_headers import build_strategy_api_headers

try:
    from src.services.context_aware_risk_service import (
        ContextRiskConfig,
        adjust_entry_risk,
    )
except ImportError:
    try:
        from context_aware_risk_service import ContextRiskConfig, adjust_entry_risk
    except ImportError:
        ContextRiskConfig = None  # type: ignore[assignment,misc]
        adjust_entry_risk = None  # type: ignore[assignment]

try:
    import numpy as _np
except Exception:  # pragma: no cover - numpy may be unavailable in some envs
    _np = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SessionRunner")
_PROFILE_PLACEHOLDER_TOKENS = {"none", "null", "n/a", "na", "undefined", "-"}


def _normalize_profile_token(value: Any) -> str:
    token = str(value).strip() if value is not None else ""
    if not token:
        return ""
    if token.lower() in _PROFILE_PLACEHOLDER_TOKENS:
        return ""
    return token


@dataclass
class RunConfig:
    """Configuration for a backtest run."""

    run_id: str
    ticker: str
    date: str
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    strategy_api_url: str = "http://localhost:8001"
    account_size_usd: float = 10_000.0
    regime_detection_minutes: int = 15
    intrabar_execution_recalc_1s: bool = False
    # Intrabar quote sampling step used during playback evaluation.
    # 1 => full 1s quotes, 5 => downsampled 5s checkpoints (faster).
    intrabar_eval_step_seconds: int = 1
    auto_close_eod: bool = True
    eod_close_time: time = field(default_factory=lambda: time(15, 55))


class SessionRunner:
    """Runs a trading session by feeding bars to the strategy evaluator."""

    L2_PAYLOAD_KEYS = (
        "l2_schema_version",
        "l2_delta",
        "l2_buy_volume",
        "l2_sell_volume",
        "l2_volume",
        "l2_imbalance",
        "l2_bid_depth_total",
        "l2_ask_depth_total",
        "l2_book_pressure",
        "l2_book_pressure_change",
        "l2_iceberg_buy_count",
        "l2_iceberg_sell_count",
        "l2_iceberg_bias",
        "l2_quality_coverage_ratio",
        "l2_quality_trade_ticks",
        "l2_quality_book_updates",
        "l2_quality_flags",
        "l2_quality",
        # Extended L2 features: previously computed but not transmitted
        "l2_cumulative_delta",
        "l2_signed_aggression",
        "l2_absorption_rate",
        "l2_delta_price_divergence",
        "l2_delta_acceleration",
    )

    TCBBO_PAYLOAD_KEYS = (
        "tcbbo_net_premium",
        "tcbbo_cumulative_net_premium",
        "tcbbo_call_buy_premium",
        "tcbbo_put_buy_premium",
        "tcbbo_call_sell_premium",
        "tcbbo_put_sell_premium",
        "tcbbo_sweep_count",
        "tcbbo_sweep_premium",
        "tcbbo_trade_count",
        "tcbbo_has_data",
    )

    def __init__(self, config: RunConfig):
        self.config = config
        self.decision_tracker = DecisionTracker(
            run_id=config.run_id, ticker=config.ticker, date=config.date
        )
        self.perf_tracker = PerformanceTracker()

        # State
        self.current_bar_index = 0
        self.bars: List[Dict[str, Any]] = []
        self.is_running = False
        self.is_paused = False
        self.last_run_speed = None  # remember requested speed for UI/resume
        self.phase = "INITIALIZED"
        self.last_response: Optional[Dict[str, Any]] = None
        self.session_summary: Optional[Dict[str, Any]] = None
        self.selection_warnings: List[str] = []
        # Optional run-level metadata injected by start_run service for reports.
        self._report_metadata: Dict[str, Any] = {}
        self._aos_applied: Dict[str, Any] = {}
        self._execution_config: Dict[str, Any] = {}
        self._context_risk_config: Optional[Any] = None
        self._context_risk_skip_count: int = 0
        self._session_end_marker_keys: Set[str] = set()
        self._session_start_marker_emitted: bool = False
        self._position_active: bool = False
        self._pending_entry: bool = False

        # Cross-asset reference bars (e.g. QQQ), keyed by ISO timestamp
        self.ref_bars_map: Dict[str, Dict[str, Any]] = {}
        self.l2_manager: Optional[Any] = None
        self._intrabar_quote_cache: Dict[int, Optional[List[Dict[str, float]]]] = {}
        self._strategy_http_session: Optional[aiohttp.ClientSession] = None
        # Optional progressive loader state (set by start_run service).
        self._progressive_loading_enabled: bool = False
        self._progressive_loading_complete: bool = True
        self._progressive_loading_loaded_until: Optional[str] = None
        self._progressive_loading_target_end: Optional[str] = None
        self._progressive_loading_pending_chunks: int = 0
        self._progressive_loading_last_error: Optional[str] = None
        self._progressive_wait_timeout_seconds: float = 90.0
        self._progressive_wait_started_at: Optional[float] = None
        self._progressive_loading_task: Optional[asyncio.Task] = None
        self._trade_start_time: Optional[datetime] = None
        self._trade_end_time: Optional[datetime] = None

        # Callbacks for real-time updates
        self._on_bar_callbacks: List[callable] = []
        self._on_decision_callbacks: List[callable] = []

    def on_bar(self, callback: callable):
        """Register callback for bar updates."""
        self._on_bar_callbacks.append(callback)

    def on_decision(self, callback: callable):
        """Register callback for decision updates."""
        self._on_decision_callbacks.append(callback)

    async def _notify_bar(self, bar: Dict[str, Any]):
        """Notify all bar callbacks."""
        for cb in self._on_bar_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(bar)
                else:
                    cb(bar)
            except Exception as e:
                logger.error(f"Bar callback error: {e}")

    async def _notify_decision(self, marker: Dict[str, Any]):
        """Notify all decision callbacks."""
        for cb in self._on_decision_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(marker)
                else:
                    cb(marker)
            except Exception as e:
                logger.error(f"Decision callback error: {e}")

    def load_bars(self, bars: List[Dict[str, Any]]):
        """Load bars for the session."""
        self.bars = bars
        self.current_bar_index = 0
        self._progressive_wait_started_at = None
        self._session_end_marker_keys.clear()
        self._session_start_marker_emitted = False
        self.selection_warnings = []
        self._position_active = False
        self._pending_entry = False
        self._intrabar_quote_cache.clear()
        logger.info(f"Loaded {len(bars)} bars for session")

    def reset_for_replay(self):
        """Reset runtime/session state so the same loaded bars can replay from the start."""
        self.current_bar_index = 0
        self.is_running = False
        self.is_paused = False
        self.last_run_speed = None
        self.phase = "INITIALIZED"
        self.last_response = None
        self.session_summary = None
        self.selection_warnings = []
        self._progressive_wait_started_at = None
        self._session_end_marker_keys.clear()
        self._session_start_marker_emitted = False
        self._position_active = False
        self._pending_entry = False
        self._intrabar_quote_cache.clear()
        self.decision_tracker = DecisionTracker(
            run_id=self.config.run_id,
            ticker=self.config.ticker,
            date=self.config.date,
        )
        self.perf_tracker = PerformanceTracker()

    @staticmethod
    def _to_utc_datetime(value: Any) -> datetime:
        """Normalize timestamp-like values to timezone-aware UTC datetime."""
        if isinstance(value, datetime):
            dt = value
        else:
            raw = str(value)
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _normalize_selection_warnings(raw_value: Any) -> List[str]:
        if not isinstance(raw_value, list):
            return []
        normalized: List[str] = []
        seen = set()
        for item in raw_value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    def _extract_response_selection_warnings(
        self, response: Dict[str, Any]
    ) -> Optional[List[str]]:
        if not isinstance(response, dict):
            return None
        if "selection_warnings" in response:
            return self._normalize_selection_warnings(
                response.get("selection_warnings")
            )
        regime_update = response.get("regime_update")
        if isinstance(regime_update, dict) and "selection_warnings" in regime_update:
            return self._normalize_selection_warnings(
                regime_update.get("selection_warnings")
            )
        return None

    @staticmethod
    def _to_json_safe(value: Any) -> Any:
        """Recursively normalize payload values to JSON-serializable primitives."""
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): SessionRunner._to_json_safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [SessionRunner._to_json_safe(v) for v in value]
        if _np is not None:
            if isinstance(value, _np.ndarray):
                return [SessionRunner._to_json_safe(v) for v in value.tolist()]
            if isinstance(value, _np.generic):
                return value.item()
        item_method = getattr(value, "item", None)
        if callable(item_method):
            try:
                return SessionRunner._to_json_safe(item_method())
            except Exception:
                pass
        return value

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(numeric):
            return None
        return numeric

    @staticmethod
    def _pct_change(
        current: Optional[float], baseline: Optional[float]
    ) -> Optional[float]:
        if current is None or baseline is None or baseline == 0:
            return None
        return ((current - baseline) / baseline) * 100.0

    @staticmethod
    def _average(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _stddev(values: List[float]) -> Optional[float]:
        if len(values) < 2:
            return None
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(max(variance, 0.0))

    def _build_marker_market_context(
        self,
        bar: Dict[str, Any],
        timestamp: datetime,
        response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        history_end = min(self.current_bar_index + 1, len(self.bars))
        history = self.bars[:history_end] if history_end > 0 else []

        open_px = self._safe_float(bar.get("open"))
        high_px = self._safe_float(bar.get("high"))
        low_px = self._safe_float(bar.get("low"))
        close_px = self._safe_float(bar.get("close"))
        volume = self._safe_float(bar.get("volume"))
        vwap = self._safe_float(bar.get("vwap"))

        candle_range = (
            high_px - low_px if high_px is not None and low_px is not None else None
        )
        candle_body = (
            close_px - open_px if close_px is not None and open_px is not None else None
        )
        upper_wick = (
            high_px - max(open_px, close_px)
            if high_px is not None and open_px is not None and close_px is not None
            else None
        )
        lower_wick = (
            min(open_px, close_px) - low_px
            if low_px is not None and open_px is not None and close_px is not None
            else None
        )
        close_location_pct = None
        if (
            candle_range is not None
            and candle_range > 0
            and close_px is not None
            and low_px is not None
        ):
            close_location_pct = ((close_px - low_px) / candle_range) * 100.0

        closes: List[float] = []
        highs: List[float] = []
        lows: List[float] = []
        volumes: List[float] = []
        for item in history:
            c_val = self._safe_float(item.get("close"))
            if c_val is not None:
                closes.append(c_val)
            h_val = self._safe_float(item.get("high"))
            if h_val is not None:
                highs.append(h_val)
            l_val = self._safe_float(item.get("low"))
            if l_val is not None:
                lows.append(l_val)
            v_val = self._safe_float(item.get("volume"))
            if v_val is not None:
                volumes.append(v_val)

        returns: List[float] = []
        if len(closes) >= 2:
            for idx in range(1, len(closes)):
                change = self._pct_change(closes[idx], closes[idx - 1])
                if change is not None:
                    returns.append(change)

        def _lookback_close_pct(lookback_bars: int) -> Optional[float]:
            if close_px is None or lookback_bars <= 0:
                return None
            if len(closes) <= lookback_bars:
                return None
            baseline = closes[-(lookback_bars + 1)]
            return self._pct_change(close_px, baseline)

        recent_bars: List[Dict[str, Any]] = []
        for item in history[-5:]:
            item_timestamp = item.get("timestamp")
            if isinstance(item_timestamp, datetime):
                ts_value = item_timestamp.isoformat()
            else:
                ts_value = str(item_timestamp)
            recent_bars.append(
                {
                    "timestamp": ts_value,
                    "open": self._safe_float(item.get("open")),
                    "high": self._safe_float(item.get("high")),
                    "low": self._safe_float(item.get("low")),
                    "close": self._safe_float(item.get("close")),
                    "volume": self._safe_float(item.get("volume")),
                    "vwap": self._safe_float(item.get("vwap")),
                    "l2_signed_aggression": self._safe_float(
                        item.get("l2_signed_aggression")
                    ),
                    "l2_imbalance": self._safe_float(item.get("l2_imbalance")),
                    "l2_book_pressure": self._safe_float(item.get("l2_book_pressure")),
                }
            )

        avg_volume_5 = self._average(volumes[-5:])
        avg_volume_20 = self._average(volumes[-20:])
        session_open = closes[0] if closes else None
        session_high = max(highs) if highs else None
        session_low = min(lows) if lows else None

        decision_state: Optional[Dict[str, Any]] = None
        if isinstance(response, dict):
            decision_state = {
                "phase": response.get("phase"),
                "action": response.get("action"),
                "regime": response.get("regime"),
                "micro_regime": response.get("micro_regime"),
                "selected_strategy": self._extract_strategy_label(response),
            }
            normalized_warnings = self._extract_response_selection_warnings(response)
            if normalized_warnings is not None:
                decision_state["selection_warnings"] = normalized_warnings

        l2_snapshot = {
            key: self._to_json_safe(bar.get(key))
            for key in self.L2_PAYLOAD_KEYS
            if key in bar
        }
        tcbbo_snapshot = {
            key: self._to_json_safe(bar.get(key))
            for key in self.TCBBO_PAYLOAD_KEYS
            if key in bar
        }
        if not l2_snapshot and isinstance(response, dict):
            l2_quality = response.get("l2_quality")
            if isinstance(l2_quality, dict):
                l2_snapshot["l2_quality"] = dict(l2_quality)

        ts_key = (
            timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
        )
        reference_bar = self.ref_bars_map.get(ts_key)
        reference_context = None
        if isinstance(reference_bar, dict):
            ref_open = self._safe_float(reference_bar.get("open"))
            ref_close = self._safe_float(reference_bar.get("close"))
            reference_context = {
                "ticker": reference_bar.get("ticker", "QQQ"),
                "open": ref_open,
                "high": self._safe_float(reference_bar.get("high")),
                "low": self._safe_float(reference_bar.get("low")),
                "close": ref_close,
                "volume": self._safe_float(reference_bar.get("volume")),
                "return_pct": self._pct_change(ref_close, ref_open),
            }

        context: Dict[str, Any] = {
            "timestamp": (
                timestamp.isoformat()
                if hasattr(timestamp, "isoformat")
                else str(timestamp)
            ),
            "bar_index": int(self.current_bar_index),
            "total_bars": int(len(self.bars)),
            "progress_pct": (
                ((self.current_bar_index + 1) / len(self.bars) * 100.0)
                if self.bars
                else 0.0
            ),
            "bar_ohlcv": {
                "open": open_px,
                "high": high_px,
                "low": low_px,
                "close": close_px,
                "volume": volume,
                "vwap": vwap,
            },
            "candle": {
                "range": candle_range,
                "body": candle_body,
                "body_to_range_ratio": (
                    (abs(candle_body) / candle_range)
                    if candle_body is not None and candle_range not in (None, 0)
                    else None
                ),
                "upper_wick": upper_wick,
                "lower_wick": lower_wick,
                "close_location_pct": close_location_pct,
                "bar_return_pct": self._pct_change(close_px, open_px),
                "close_to_vwap_pct": self._pct_change(close_px, vwap),
            },
            "price_evolution": {
                "close_change_1_bar_pct": _lookback_close_pct(1),
                "close_change_3_bar_pct": _lookback_close_pct(3),
                "close_change_5_bar_pct": _lookback_close_pct(5),
                "close_change_10_bar_pct": _lookback_close_pct(10),
                "close_change_20_bar_pct": _lookback_close_pct(20),
                "realized_volatility_5_bar_pct": self._stddev(returns[-5:]),
                "realized_volatility_20_bar_pct": self._stddev(returns[-20:]),
                "session_open_price": session_open,
                "session_high_so_far": session_high,
                "session_low_so_far": session_low,
                "distance_from_session_open_pct": self._pct_change(
                    close_px, session_open
                ),
                "distance_from_session_high_pct": self._pct_change(
                    close_px, session_high
                ),
                "distance_from_session_low_pct": self._pct_change(
                    close_px, session_low
                ),
            },
            "volume_context": {
                "avg_volume_5_bar": avg_volume_5,
                "avg_volume_20_bar": avg_volume_20,
                "volume_vs_avg_5_ratio": (
                    (volume / avg_volume_5)
                    if volume is not None and avg_volume_5 not in (None, 0)
                    else None
                ),
                "volume_vs_avg_20_ratio": (
                    (volume / avg_volume_20)
                    if volume is not None and avg_volume_20 not in (None, 0)
                    else None
                ),
            },
            "recent_bars": recent_bars,
        }
        if decision_state is not None:
            context["decision_state"] = decision_state
        if l2_snapshot:
            context["l2"] = l2_snapshot
        if tcbbo_snapshot:
            context["tcbbo"] = tcbbo_snapshot
        if reference_context is not None:
            context["reference_asset"] = reference_context
        if isinstance(response, dict):
            break_even_payload = response.get("break_even")
            if not isinstance(break_even_payload, dict):
                opened = response.get("position_opened")
                if isinstance(opened, dict):
                    opened_md = (
                        opened.get("metadata")
                        if isinstance(opened.get("metadata"), dict)
                        else {}
                    )
                    if isinstance(opened_md.get("break_even"), dict):
                        break_even_payload = dict(opened_md.get("break_even") or {})
            if not isinstance(break_even_payload, dict):
                closed = response.get("position_closed")
                if isinstance(closed, dict) and isinstance(
                    closed.get("break_even"), dict
                ):
                    break_even_payload = dict(closed.get("break_even") or {})
            if isinstance(break_even_payload, dict):
                context["break_even"] = self._to_json_safe(break_even_payload)
        return self._to_json_safe(context)

    def _attach_market_context(
        self, marker: Any, market_context: Dict[str, Any]
    ) -> None:
        marker.details["market_context"] = self._to_json_safe(market_context)

    def _build_pending_execution_status_marker(
        self,
        response: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Translate pending-signal execution outcomes into explicit decision-log markers."""
        if not isinstance(response, dict):
            return None

        action = str(response.get("action") or "").strip()
        reason = str(response.get("reason") or "").strip()
        details: Dict[str, Any] = {}

        action_templates = {
            "pending_micro_confirmation": {
                "status": "pending",
                "signal_type": "PENDING",
                "title": "Signal Pending Confirmation",
                "default_reason": "Awaiting consecutive close confirmation.",
            },
            "pending_intrabar_confirmation": {
                "status": "pending",
                "signal_type": "PENDING",
                "title": "Signal Pending Intrabar Confirmation",
                "default_reason": "Awaiting intrabar flow confirmation.",
            },
            "micro_confirmation_failed": {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Micro Confirmation)",
                "default_reason": "Consecutive close confirmation failed.",
            },
            "intrabar_confirmation_failed": {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Intrabar Confirmation)",
                "default_reason": "Intrabar flow confirmation failed.",
            },
            "consecutive_loss_cooldown": {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Cooldown)",
                "default_reason": "Consecutive-loss cooldown blocked entry.",
            },
            "regime_warmup": {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Regime Warmup)",
                "default_reason": "Regime warmup incomplete; pending signal discarded.",
            },
            "context_risk_skip": {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Context Risk)",
                "default_reason": "Context-aware risk guard skipped the pending signal.",
            },
            "insufficient_fill": {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Insufficient Fill)",
                "default_reason": "Position size after risk/fill constraints is zero.",
            },
        }

        template = action_templates.get(action)
        if template is None and bool(response.get("stale_pending_signal_dropped")):
            action = action or "stale_pending_signal_dropped"
            template = {
                "status": "no_fill",
                "signal_type": "NO_FILL",
                "title": "Signal Dropped (Stale)",
                "default_reason": "Pending signal expired before execution.",
            }
            stale_age = response.get("stale_pending_signal_age_bars")
            stale_ttl = response.get("pending_signal_ttl_bars")
            if stale_age is not None:
                details["stale_pending_signal_age_bars"] = stale_age
            if stale_ttl is not None:
                details["pending_signal_ttl_bars"] = stale_ttl
            if not reason and stale_age is not None and stale_ttl is not None:
                reason = f"Pending signal expired after {stale_age} bars (ttl {stale_ttl} bars)."

        if template is None:
            return None

        if not reason:
            reason = template["default_reason"]

        strategy = "pending_signal"
        confidence = 0.0

        signal_payload = response.get("signal")
        if isinstance(signal_payload, dict):
            strategy = (
                str(
                    signal_payload.get("strategy")
                    or signal_payload.get("strategy_name")
                    or strategy
                ).strip()
                or strategy
            )
            parsed_confidence = self._safe_float(signal_payload.get("confidence"))
            if parsed_confidence is not None:
                confidence = parsed_confidence

        opened_payload = response.get("position_opened")
        if isinstance(opened_payload, dict):
            strategy = (
                str(opened_payload.get("strategy") or strategy).strip() or strategy
            )
            parsed_confidence = self._safe_float(opened_payload.get("confidence"))
            if parsed_confidence is not None:
                confidence = parsed_confidence

        micro_confirmation = response.get("micro_confirmation")
        if isinstance(micro_confirmation, dict):
            details["micro_confirmation"] = dict(micro_confirmation)

        intrabar_confirmation = response.get("intrabar_confirmation")
        if isinstance(intrabar_confirmation, dict):
            details["intrabar_confirmation"] = dict(intrabar_confirmation)

        context_risk = response.get("context_risk")
        if isinstance(context_risk, dict):
            details["context_risk"] = dict(context_risk)

        details["execution_status"] = template["status"]
        details["execution_action"] = action or "pending_signal_update"
        details["reason"] = reason

        return {
            "title": template["title"],
            "description": reason,
            "signal_type": template["signal_type"],
            "strategy": strategy,
            "confidence": confidence,
            "details": details,
        }

    def _should_attach_intrabar_quotes(
        self, include_pending_entry: bool = False
    ) -> bool:
        # In intrabar mode, strategies may depend on 1s quotes before the first entry.
        # Keep gating tied to mode+availability only (no execution-state gate).
        _ = include_pending_entry
        return bool(self.config.intrabar_execution_recalc_1s) and bool(
            self.l2_manager is not None
        )

    def _intrabar_eval_step_seconds(self) -> int:
        raw = getattr(self.config, "intrabar_eval_step_seconds", 1)
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            parsed = 1
        return max(1, min(60, parsed))

    def _apply_intrabar_eval_step(
        self, quotes: Optional[List[Dict[str, float]]]
    ) -> Optional[List[Dict[str, float]]]:
        if not quotes:
            return None
        step = self._intrabar_eval_step_seconds()
        if step <= 1:
            return quotes

        last_index = len(quotes) - 1
        selected: List[Dict[str, float]] = []
        for idx, quote in enumerate(quotes):
            sec_raw = quote.get("s")
            try:
                sec = int(sec_raw)
            except (TypeError, ValueError):
                sec = -1
            include = idx == 0 or idx == last_index or (sec >= 0 and sec % step == 0)
            if not include:
                continue
            if selected:
                prev_sec = selected[-1].get("s")
                try:
                    if int(prev_sec) == sec:
                        continue
                except (TypeError, ValueError):
                    pass
            selected.append(quote)

        if not selected:
            return quotes
        return selected

    def _load_intrabar_quotes(
        self, timestamp: datetime
    ) -> Optional[List[Dict[str, float]]]:
        """
        Load compact 1-second bid/ask quotes for one minute.

        Returns cached payload format:
          [{"s": second, "bid": top_bid_px, "ask": top_ask_px}, ...]
        """
        if self.l2_manager is None:
            return None

        ts_utc = self._to_utc_datetime(timestamp)
        minute_start = ts_utc.replace(second=0, microsecond=0)
        minute_key = int(minute_start.timestamp())
        if minute_key in self._intrabar_quote_cache:
            cached_quotes = self._intrabar_quote_cache[minute_key]
            return self._apply_intrabar_eval_step(cached_quotes)

        minute_end = minute_start + timedelta(seconds=59, microseconds=999999)
        try:
            frames = self.l2_manager.get_intrabar_frames(
                ticker=self.config.ticker,
                start_time=minute_start,
                end_time=minute_end,
            )
        except Exception as exc:
            logger.debug(
                f"Intrabar quote load failed for {self.config.ticker} @ {minute_start}: {exc}"
            )
            self._intrabar_quote_cache[minute_key] = None
            return None

        if frames is None or len(frames) == 0:
            self._intrabar_quote_cache[minute_key] = None
            return None

        quote_rows: List[Dict[str, float]] = []
        for _, row in frames.iterrows():
            if not bool(row.get("has_book_coverage", False)):
                continue

            try:
                bid = float(row.get("top_bid_px", 0.0) or 0.0)
                ask = float(row.get("top_ask_px", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue

            if bid <= 0.0 and ask <= 0.0:
                continue

            ts_sec = row.get("ts_sec")
            try:
                sec_dt = self._to_utc_datetime(ts_sec)
                second = int(sec_dt.second)
            except Exception:
                continue

            quote_rows.append(
                {
                    "s": second,
                    "bid": round(bid, 6),
                    "ask": round(ask, 6),
                }
            )

        quote_rows.sort(key=lambda item: item["s"])
        cached = quote_rows if quote_rows else None
        self._intrabar_quote_cache[minute_key] = cached
        return self._apply_intrabar_eval_step(cached)

    def _strategy_api_headers(self) -> Dict[str, str]:
        return build_strategy_api_headers(self.config.strategy_api_url)

    async def _get_strategy_http_session(self) -> aiohttp.ClientSession:
        if (
            self._strategy_http_session is not None
            and not self._strategy_http_session.closed
        ):
            return self._strategy_http_session
        try:
            timeout_total = float(
                os.getenv("BACKTEST_STRATEGY_API_TIMEOUT_SECONDS", "6.0")
            )
        except (TypeError, ValueError):
            timeout_total = 6.0
        timeout = aiohttp.ClientTimeout(
            total=max(0.1, timeout_total),
            connect=3.0,
        )
        try:
            self._strategy_http_session = aiohttp.ClientSession(timeout=timeout)
        except TypeError:
            # Test doubles may not accept keyword args; fall back to defaults.
            self._strategy_http_session = aiohttp.ClientSession()
        return self._strategy_http_session

    async def close_http_session(self) -> None:
        session = self._strategy_http_session
        self._strategy_http_session = None
        if session is not None and not session.closed:
            await session.close()

    @staticmethod
    def _is_recoverable_strategy_error(status: int, detail: str) -> bool:
        text = str(detail or "").lower()
        if status in {404, 409, 425, 429, 500, 502, 503, 504}:
            return True
        # Defensive fallback for HTML/plain text errors where status may not be enough.
        return "session not found" in text or "internal server error" in text

    def _resolve_strategy_session_date(self) -> str:
        token = str(
            getattr(self, "_restart_session_date", "")
            or self.config.date_from
            or self.config.date
        ).strip()
        return token

    def _resolve_strategy_session_config_snapshot(self) -> Dict[str, Any]:
        snapshot = getattr(self, "_restart_session_config", {})
        if not isinstance(snapshot, dict):
            return {}
        return dict(snapshot)

    async def _recover_strategy_session(self, *, reason: str, detail: str = "") -> bool:
        """
        Re-send session configuration to strategy API and continue current bar.
        This makes runner resilient to strategy API process restarts/reloads.
        """
        session_date = self._resolve_strategy_session_date()
        if not session_date:
            logger.warning("Strategy session recovery skipped (missing session date).")
            return False

        config_snapshot = self._resolve_strategy_session_config_snapshot()
        if not config_snapshot:
            logger.warning(
                "Strategy session recovery skipped (missing config snapshot)."
            )
            return False

        headers = self._strategy_api_headers()
        post_kwargs: Dict[str, Any] = {
            "params": {
                "run_id": self.config.run_id,
                "ticker": self.config.ticker,
                "date": session_date,
            },
            "json": config_snapshot,
        }
        if headers:
            post_kwargs["headers"] = headers

        last_error = ""
        for attempt in range(3):
            session = await self._get_strategy_http_session()
            try:
                async with session.post(
                    f"{self.config.strategy_api_url}/api/session/config",
                    **post_kwargs,
                ) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        logger.warning(
                            "Strategy session recovered run_id=%s ticker=%s date=%s reason=%s",
                            self.config.run_id,
                            self.config.ticker,
                            session_date,
                            reason,
                        )
                        return await self._replay_historical_bars(session_date)
                    last_error = f"http_{resp.status}:{body[:200]}"
            except aiohttp.ClientError as exc:
                last_error = f"connection:{str(exc)}"
            await self.close_http_session()
            if attempt < 2:
                await asyncio.sleep(0.2 * (attempt + 1))

        logger.warning(
            "Strategy session recovery failed reason=%s detail=%s last_error=%s",
            reason,
            detail[:200],
            last_error[:300],
        )
        return False

    async def _replay_historical_bars(self, session_date: str) -> bool:
        """
        Replay all bars for the current session_date up to self.current_bar_index.
        This properly rebuilds the strategy API state (VWAP, intraday levels, positions) after a restart.
        """
        bars_to_replay = []
        for i in range(self.current_bar_index):
            bar = self.bars[i]
            ts = bar.get("timestamp", "")
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            if session_date in ts_str:
                bars_to_replay.append((i, bar, ts_str))

        if not bars_to_replay:
            return True

        logger.info(
            f"Replaying {len(bars_to_replay)} historical bars for session {session_date} to rebuild state."
        )
        headers = self._strategy_api_headers()

        # In a real batch optimization, the strategy API would accept a list.
        # Since we only have /api/session/bar, we must replay them sequentially.
        session = await self._get_strategy_http_session()
        try:
            for i, bar, ts_str in bars_to_replay:
                payload = {
                    "run_id": self.config.run_id,
                    "ticker": self.config.ticker,
                    "timestamp": ts_str,
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": bar["volume"],
                    "vwap": bar.get("vwap"),
                }
                for l2_key in self.L2_PAYLOAD_KEYS:
                    if l2_key in bar:
                        payload[l2_key] = bar.get(l2_key)
                for tcbbo_key in self.TCBBO_PAYLOAD_KEYS:
                    if tcbbo_key in bar:
                        payload[tcbbo_key] = bar.get(tcbbo_key)

                # Check for cross-asset ref bar
                ref_bar = self.ref_bars_map.get(ts_str)
                if ref_bar:
                    payload["ref_ticker"] = ref_bar.get("ticker", "QQQ")
                    payload["ref_open"] = ref_bar.get("open")
                    payload["ref_high"] = ref_bar.get("high")
                    payload["ref_low"] = ref_bar.get("low")
                    payload["ref_close"] = ref_bar.get("close")
                    payload["ref_volume"] = ref_bar.get("volume")

                payload = self._to_json_safe(payload)

                post_kwargs: Dict[str, Any] = {"json": payload}
                if headers:
                    post_kwargs["headers"] = headers

                async with session.post(
                    f"{self.config.strategy_api_url}/api/session/bar",
                    **post_kwargs,
                ) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        logger.error(
                            f"Failed to replay bar index {i}: HTTP {resp.status} {err}"
                        )
                        return False
            return True
        except Exception as e:
            logger.error(f"Error replaying historical bars: {e}")
            return False

    def _update_execution_state(self, response: Dict[str, Any]) -> None:
        """Track whether next bar needs execution-level intrabar payload."""
        action = str(response.get("action", "") or "")
        opened = "position_opened" in response
        closed = (
            "position_closed" in response
            or action.startswith("position_closed_")
            or action == "max_loss_stop"
            or action == "session_ended"
        )

        if opened:
            self._position_active = True
        if closed:
            self._position_active = False

        queued = bool(response.get("queued_for_next_bar")) or action == "signal_queued"
        if queued:
            self._pending_entry = True

        if response.get("phase") == "END_OF_DAY":
            self._position_active = False
            self._pending_entry = False

    async def step(self, notify: bool = True) -> Dict[str, Any]:
        """Process the next bar and return the result.

        Args:
            notify: Whether to notify callbacks (WebSocket) about this step.
                   Set to False when batch processing for performance.
        """
        if self.current_bar_index >= len(self.bars):
            progressive_waiting = bool(
                self._progressive_loading_enabled
                and not self._progressive_loading_complete
            )
            if progressive_waiting:
                return {
                    "success": True,
                    "waiting_for_data": True,
                    "phase": self.phase,
                    "bar_index": self.current_bar_index,
                    "total_bars": len(self.bars),
                    "progress_pct": (
                        (self.current_bar_index / len(self.bars) * 100)
                        if self.bars
                        else 0
                    ),
                }
            return {
                "success": False,
                "error": "No more bars to process",
                "phase": "COMPLETED",
            }

        bar = self.bars[self.current_bar_index]
        result = await self._process_bar(bar)

        if not bool(result.get("success")):
            self.last_response = result
            self.phase = "ERROR"
            self.is_running = False
            return result

        self.current_bar_index += 1
        self.last_response = result
        processed_bar_index = self.current_bar_index - 1

        # Persist UI-facing per-bar analysis onto the processed bar itself so
        # snapshot/poll-based consumers (/bars endpoint) can scrub historical
        # conditions, not only live WebSocket callbacks.
        if isinstance(bar, dict):
            bar["bar_index"] = processed_bar_index
            bar["warmup_only"] = bool(result.get("warmup_only", False))
            api_response = result.get("response") if isinstance(result, dict) else None
            if isinstance(api_response, dict):
                ls = api_response.get("layer_scores")
                if isinstance(ls, dict):
                    bar["layer_scores"] = ls
                sr = api_response.get("signal_rejected")
                if isinstance(sr, dict):
                    bar["signal_rejected"] = sr
                intrabar_eval_trace = api_response.get("intrabar_eval_trace")
                if isinstance(intrabar_eval_trace, dict):
                    bar["intrabar_eval_trace"] = intrabar_eval_trace
                cd = None
                pos = api_response.get("position_opened")
                if isinstance(pos, dict):
                    md = pos.get("metadata")
                    if isinstance(md, dict):
                        cd = md.get("candidate_diagnostics")
                if cd is None:
                    for sig in api_response.get("signals") or []:
                        if isinstance(sig, dict):
                            sig_md = sig.get("metadata")
                            if isinstance(sig_md, dict) and isinstance(
                                sig_md.get("candidate_diagnostics"), dict
                            ):
                                cd = sig_md["candidate_diagnostics"]
                                break
                if isinstance(cd, dict):
                    bar["candidate_diagnostics"] = cd

        # Notify callbacks if requested
        if notify:
            bar_payload = {
                **bar,
                "bar_index": processed_bar_index,
                "warmup_only": bool(result.get("warmup_only", False)),
            }
            # Attach live strategy analysis for the UI conditions panel.
            api_response = result.get("response") if isinstance(result, dict) else None
            if isinstance(api_response, dict):
                ls = api_response.get("layer_scores")
                if isinstance(ls, dict):
                    bar_payload["layer_scores"] = ls
                sr = api_response.get("signal_rejected")
                if isinstance(sr, dict):
                    bar_payload["signal_rejected"] = sr
                intrabar_eval_trace = api_response.get("intrabar_eval_trace")
                if isinstance(intrabar_eval_trace, dict):
                    bar_payload["intrabar_eval_trace"] = intrabar_eval_trace
                cd = None
                pos = api_response.get("position_opened")
                if isinstance(pos, dict):
                    md = pos.get("metadata")
                    if isinstance(md, dict):
                        cd = md.get("candidate_diagnostics")
                if cd is None:
                    for sig in api_response.get("signals") or []:
                        if isinstance(sig, dict):
                            sig_md = sig.get("metadata")
                            if isinstance(sig_md, dict) and isinstance(
                                sig_md.get("candidate_diagnostics"), dict
                            ):
                                cd = sig_md["candidate_diagnostics"]
                                break
                if isinstance(cd, dict):
                    bar_payload["candidate_diagnostics"] = cd
            await self._notify_bar(bar_payload)

        return result

    async def _process_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        """Send bar to strategy evaluator and process response."""
        timestamp = bar["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        ts_utc = self._to_utc_datetime(timestamp)
        trade_start_utc = (
            self._trade_start_time
            if isinstance(self._trade_start_time, datetime)
            else None
        )
        trade_end_utc = (
            self._trade_end_time if isinstance(self._trade_end_time, datetime) else None
        )
        warmup_only = bool(
            (trade_start_utc is not None and ts_utc < trade_start_utc)
            or (trade_end_utc is not None and ts_utc > trade_end_utc)
        )

        # First bar - add session start marker
        if not warmup_only and not self._session_start_marker_emitted:
            marker = self.decision_tracker.add_session_start(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=bar["close"],
            )
            self._attach_market_context(
                marker,
                self._build_marker_market_context(bar=bar, timestamp=timestamp),
            )
            self._session_start_marker_emitted = True
            await self._notify_decision(marker.to_dict())

        # Send to strategy API
        consume_pending_entry = self._pending_entry
        if consume_pending_entry:
            # Pending signal is consumed at this bar open (fill or reject).
            self._pending_entry = False
        payload = {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "timestamp": (
                timestamp.isoformat()
                if hasattr(timestamp, "isoformat")
                else str(timestamp)
            ),
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar["volume"],
            "vwap": bar.get("vwap"),
            "warmup_only": warmup_only,
        }
        for l2_key in self.L2_PAYLOAD_KEYS:
            if l2_key in bar:
                payload[l2_key] = bar.get(l2_key)
        for tcbbo_key in self.TCBBO_PAYLOAD_KEYS:
            if tcbbo_key in bar:
                payload[tcbbo_key] = bar.get(tcbbo_key)

        if self._should_attach_intrabar_quotes(
            include_pending_entry=consume_pending_entry
        ):
            intrabar_quotes = self._load_intrabar_quotes(timestamp)
            if intrabar_quotes:
                payload["intrabar_quotes_1s"] = intrabar_quotes

        # Attach cross-asset reference bar if available
        ts_key = (
            timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
        )
        ref_bar = self.ref_bars_map.get(ts_key)
        if ref_bar:
            payload["ref_ticker"] = ref_bar.get("ticker", "QQQ")
            payload["ref_open"] = ref_bar.get("open")
            payload["ref_high"] = ref_bar.get("high")
            payload["ref_low"] = ref_bar.get("low")
            payload["ref_close"] = ref_bar.get("close")
            payload["ref_volume"] = ref_bar.get("volume")
        payload = self._to_json_safe(payload)

        result: Optional[Dict[str, Any]] = None
        recovery_attempted = False
        for attempt in range(2):
            try:
                session = await self._get_strategy_http_session()
                post_kwargs: Dict[str, Any] = {"json": payload}
                headers = self._strategy_api_headers()
                if headers:
                    post_kwargs["headers"] = headers
                async with session.post(
                    f"{self.config.strategy_api_url}/api/session/bar",
                    **post_kwargs,
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        can_recover = (
                            not recovery_attempted
                            and attempt == 0
                            and self._is_recoverable_strategy_error(
                                resp.status, error_text
                            )
                        )
                        if can_recover:
                            recovery_attempted = True
                            recovered = await self._recover_strategy_session(
                                reason=f"http_{resp.status}",
                                detail=error_text,
                            )
                            if recovered:
                                continue
                            if resp.status in {502, 503, 504}:
                                await asyncio.sleep(0.2)
                                await self.close_http_session()
                                continue
                        if consume_pending_entry:
                            self._pending_entry = True
                        return {
                            "success": False,
                            "error": f"API error {resp.status}: {error_text}",
                            "bar_index": self.current_bar_index,
                        }

                    result = await resp.json()
                    break
            except aiohttp.ClientError as e:
                can_recover = not recovery_attempted and attempt == 0
                if can_recover:
                    recovery_attempted = True
                    recovered = await self._recover_strategy_session(
                        reason="connection_error",
                        detail=str(e),
                    )
                    if recovered:
                        continue
                    await asyncio.sleep(0.2)
                    await self.close_http_session()
                    continue
                if consume_pending_entry:
                    self._pending_entry = True
                return {
                    "success": False,
                    "error": f"Connection error: {str(e)}",
                    "bar_index": self.current_bar_index,
                }

        if result is None:
            if consume_pending_entry:
                self._pending_entry = True
            return {
                "success": False,
                "error": "Strategy response missing after recovery attempts",
                "bar_index": self.current_bar_index,
            }

        # Update phase
        self.phase = result.get("phase", self.phase)
        self._update_execution_state(result)

        # Process decision markers from response
        if warmup_only:
            resolved_warnings = self._extract_response_selection_warnings(result)
            if resolved_warnings is not None:
                self.selection_warnings = resolved_warnings
            result["warmup_only"] = True
        else:
            await self._process_decision_markers(result, bar, timestamp)

        return {
            "success": True,
            "bar_index": self.current_bar_index,
            "bar": bar,
            "phase": self.phase,
            "response": result,
            "total_bars": len(self.bars),
            "progress_pct": (self.current_bar_index + 1) / len(self.bars) * 100,
            "warmup_only": warmup_only,
        }

    async def _process_decision_markers(
        self, response: Dict[str, Any], bar: Dict[str, Any], timestamp: datetime
    ):
        """Extract and record decision markers from API response."""
        resolved_warnings = self._extract_response_selection_warnings(response)
        if resolved_warnings is not None:
            self.selection_warnings = resolved_warnings

        intraday_levels_payload = response.get("intraday_levels")
        if not isinstance(intraday_levels_payload, dict):
            intraday_levels_payload = None
        market_context = self._build_marker_market_context(
            bar=bar,
            timestamp=timestamp,
            response=response,
        )

        action = response.get("action", "")

        # Regime detected (allow one per day by relying on action flag)
        if action == "regime_detected":
            regime = response.get("regime")
            if regime:
                explanation = self._generate_regime_explanation(response)
                marker = self.decision_tracker.add_regime_detected(
                    timestamp=timestamp,
                    bar_index=self.current_bar_index,
                    price=bar["close"],
                    regime=regime,
                    explanation=explanation,
                    indicators=response.get("indicators", {}),
                )
                if intraday_levels_payload is not None:
                    marker.details["intraday_levels"] = dict(intraday_levels_payload)
                self._attach_market_context(marker, market_context)
                await self._notify_decision(marker.to_dict())

                # Also add strategy selected marker for this day
                strategy = self._extract_strategy_label(response)
                if strategy:
                    active_strategies = [
                        str(name).strip()
                        for name in (
                            response.get("strategies")
                            if isinstance(response.get("strategies"), list)
                            else []
                        )
                        if str(name).strip()
                    ]
                    strategy_token = str(strategy).strip()
                    if strategy_token.lower() == "adaptive":
                        alternative_strategies = list(active_strategies)
                    else:
                        alternative_strategies = [
                            name for name in active_strategies if name != strategy_token
                        ]
                    marker = self.decision_tracker.add_strategy_selected(
                        timestamp=timestamp,
                        bar_index=self.current_bar_index,
                        price=bar["close"],
                        strategy=strategy,
                        regime=regime,
                        reasoning=f"Selected {strategy} strategy for {regime} regime",
                        alternative_strategies=alternative_strategies,
                        active_strategies=active_strategies,
                        selection_warnings=self.selection_warnings,
                    )
                    self._attach_market_context(marker, market_context)
                    await self._notify_decision(marker.to_dict())

        # Intraday regime refresh (dynamic reclassification).
        regime_update = response.get("regime_update")
        if isinstance(regime_update, dict):
            regime = regime_update.get("regime") or response.get("regime")
            regime_indicators = regime_update.get("indicators") or response.get(
                "indicators", {}
            )
            if regime:
                update_payload = {
                    **response,
                    "regime": regime,
                    "indicators": regime_indicators,
                }
                explanation = f"Intraday refresh: {self._generate_regime_explanation(update_payload)}"
                marker = self.decision_tracker.add_regime_detected(
                    timestamp=timestamp,
                    bar_index=self.current_bar_index,
                    price=bar["close"],
                    regime=regime,
                    explanation=explanation,
                    indicators=regime_indicators,
                )
                if intraday_levels_payload is not None:
                    marker.details["intraday_levels"] = dict(intraday_levels_payload)
                self._attach_market_context(marker, market_context)
                await self._notify_decision(marker.to_dict())

            strategy = regime_update.get("strategy") or self._extract_strategy_label(
                response
            )
            if strategy and regime:
                active_strategies = [
                    str(name).strip()
                    for name in (
                        regime_update.get("strategies")
                        if isinstance(regime_update.get("strategies"), list)
                        else (
                            response.get("strategies")
                            if isinstance(response.get("strategies"), list)
                            else []
                        )
                    )
                    if str(name).strip()
                ]
                strategy_token = str(strategy).strip()
                if strategy_token.lower() == "adaptive":
                    alternative_strategies = list(active_strategies)
                else:
                    alternative_strategies = [
                        name for name in active_strategies if name != strategy_token
                    ]
                marker = self.decision_tracker.add_strategy_selected(
                    timestamp=timestamp,
                    bar_index=self.current_bar_index,
                    price=bar["close"],
                    strategy=strategy,
                    regime=regime,
                    reasoning=f"Updated {strategy} after intraday regime refresh",
                    alternative_strategies=alternative_strategies,
                    active_strategies=active_strategies,
                    selection_warnings=self.selection_warnings,
                    switch_guard=(
                        regime_update.get("switch_guard")
                        if isinstance(regime_update.get("switch_guard"), dict)
                        else None
                    ),
                )
                self._attach_market_context(marker, market_context)
                await self._notify_decision(marker.to_dict())

        # Signals generated
        signals = response.get("signals", [])
        response_tcbbo_confirmation = (
            response.get("tcbbo_confirmation")
            if isinstance(response.get("tcbbo_confirmation"), dict)
            else None
        )
        for signal in signals:
            marker = self.decision_tracker.add_signal(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=signal.get("price", bar["close"]),
                signal_type=signal.get("signal", "BUY"),
                strategy=signal.get("strategy", "unknown"),
                confidence=signal.get("confidence", 50),
                reasoning=signal.get("reasoning", ""),
                stop_loss=signal.get("stop_loss"),
                take_profit=signal.get("take_profit"),
            )
            if intraday_levels_payload is not None:
                marker.details["intraday_levels"] = dict(intraday_levels_payload)
            signal_metadata = signal.get("metadata") if isinstance(signal, dict) else {}
            if isinstance(signal_metadata, dict):
                marker.details["signal_metadata"] = dict(signal_metadata)
                level_context = signal_metadata.get("level_context")
                if isinstance(level_context, dict):
                    marker.details["level_context"] = dict(level_context)
                flow_snapshot = signal_metadata.get("order_flow")
                if isinstance(flow_snapshot, dict):
                    marker.details["flow_snapshot"] = dict(flow_snapshot)
                    marker.details["signed_aggression"] = flow_snapshot.get(
                        "signed_aggression"
                    )
                tcbbo_confirmation = signal_metadata.get("tcbbo_confirmation")
                if isinstance(tcbbo_confirmation, dict):
                    marker.details["tcbbo_confirmation"] = dict(tcbbo_confirmation)
            if "tcbbo_confirmation" not in marker.details and isinstance(
                response_tcbbo_confirmation, dict
            ):
                marker.details["tcbbo_confirmation"] = dict(response_tcbbo_confirmation)
            self._attach_market_context(marker, market_context)
            await self._notify_decision(marker.to_dict())

        pending_execution_status = self._build_pending_execution_status_marker(response)
        if pending_execution_status is not None:
            marker_price = self._safe_float(bar.get("open"))
            if marker_price is None:
                marker_price = self._safe_float(bar.get("close"))
            if marker_price is None:
                marker_price = 0.0
            marker_details = dict(pending_execution_status.get("details") or {})
            if intraday_levels_payload is not None:
                marker_details["intraday_levels"] = dict(intraday_levels_payload)
            marker = self.decision_tracker.add_execution_status(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=marker_price,
                title=str(pending_execution_status.get("title") or "Execution Status"),
                description=str(pending_execution_status.get("description") or ""),
                strategy=str(
                    pending_execution_status.get("strategy") or "pending_signal"
                ),
                confidence=float(pending_execution_status.get("confidence") or 0.0),
                details=marker_details,
            )
            self._attach_market_context(marker, market_context)
            await self._notify_decision(marker.to_dict())

        # Trades opened
        if "position_opened" in response:
            pos = response["position_opened"]
            # Get signal details if available
            signal_data = response.get("signal") or {}

            logger.info(
                f"DEBUG_SIGNAL_RECV: Bar {self.current_bar_index} Time {timestamp} "
                f"Strat {pos.get('strategy')} "
                f"Reasoning: {str(signal_data.get('reasoning', ''))[:100]}"
            )

            if not isinstance(signal_data, dict):
                signal_data = {}
            reasoning = pos.get("reasoning", signal_data.get("reasoning", ""))
            confidence = pos.get("confidence", signal_data.get("confidence", 50))
            metadata = pos.get("metadata", signal_data.get("metadata", {}))

            # --- Context-aware risk adjustment ---
            risk_adjustment = None
            context_risk_payload = response.get("context_risk")
            if not isinstance(context_risk_payload, dict):
                context_from_metadata = (
                    metadata.get("context_risk") if isinstance(metadata, dict) else None
                )
                context_risk_payload = (
                    dict(context_from_metadata)
                    if isinstance(context_from_metadata, dict)
                    else None
                )
            else:
                context_risk_payload = dict(context_risk_payload)

            # Backward-compatibility fallback for older strategy APIs that do not
            # adjust risk server-side yet.
            if context_risk_payload is None:
                ctx_cfg = self._context_risk_config
                if ctx_cfg is None and ContextRiskConfig is not None:
                    ctx_cfg = ContextRiskConfig.from_execution_config(
                        self._execution_config
                    )
                    self._context_risk_config = ctx_cfg

                if (
                    ctx_cfg is not None
                    and getattr(ctx_cfg, "enabled", False)
                    and adjust_entry_risk is not None
                    and intraday_levels_payload is not None
                ):
                    try:
                        sweep_payload = (
                            metadata.get("liquidity_sweep")
                            if isinstance(metadata, dict)
                            and isinstance(metadata.get("liquidity_sweep"), dict)
                            else {}
                        )
                        atr_for_context = None
                        if isinstance(sweep_payload, dict):
                            atr_for_context = sweep_payload.get("atr")
                        if atr_for_context is None and isinstance(market_context, dict):
                            atr_for_context = market_context.get("atr")
                            if atr_for_context is None:
                                mc_indicators = market_context.get("indicators")
                                if isinstance(mc_indicators, dict):
                                    atr_for_context = mc_indicators.get("atr")

                        risk_adjustment = adjust_entry_risk(
                            entry_price=pos.get("entry_price", bar["close"]),
                            side=pos.get("side", "long"),
                            original_sl=pos.get("stop_loss", 0),
                            original_tp=pos.get("take_profit", 0),
                            levels_payload=intraday_levels_payload,
                            config=ctx_cfg,
                            atr=atr_for_context,
                            is_sweep_trade=bool(
                                isinstance(metadata, dict)
                                and (
                                    metadata.get("sweep_triggered", False)
                                    or (
                                        isinstance(sweep_payload, dict)
                                        and sweep_payload.get("detected", False)
                                    )
                                )
                            ),
                            strategy_key=str(pos.get("strategy", "")),
                        )
                        if risk_adjustment.skip:
                            self._context_risk_skip_count += 1
                            logger.info(
                                "Context-aware risk SKIP trade: %s (%s)",
                                pos.get("strategy", "?"),
                                risk_adjustment.skip_reason,
                            )
                            # Record skip as a decision marker for UI visibility
                            skip_marker = self.decision_tracker.add_signal(
                                timestamp=timestamp,
                                bar_index=self.current_bar_index,
                                price=pos.get("entry_price", bar["close"]),
                                signal_type="SKIP",
                                strategy=pos.get("strategy", "unknown"),
                                confidence=confidence,
                                reasoning=f"Context-risk skip: {risk_adjustment.skip_reason}",
                                stop_loss=risk_adjustment.original_sl,
                                take_profit=risk_adjustment.original_tp,
                            )
                            skip_marker.details["context_risk"] = (
                                risk_adjustment.to_dict()
                            )
                            if intraday_levels_payload is not None:
                                skip_marker.details["intraday_levels"] = dict(
                                    intraday_levels_payload
                                )
                            self._attach_market_context(skip_marker, market_context)
                            await self._notify_decision(skip_marker.to_dict())
                            return  # Skip this trade

                        # Apply adjusted SL/TP
                        pos["stop_loss"] = risk_adjustment.adjusted_sl
                        pos["take_profit"] = risk_adjustment.adjusted_tp
                        logger.info(
                            "Context-aware risk adjusted %s: SL %.2f→%.2f (%s), TP %.2f→%.2f (%s)",
                            pos.get("strategy", "?"),
                            risk_adjustment.original_sl,
                            risk_adjustment.adjusted_sl,
                            risk_adjustment.sl_reason,
                            risk_adjustment.original_tp,
                            risk_adjustment.adjusted_tp,
                            risk_adjustment.tp_reason,
                        )
                    except Exception as exc:
                        logger.warning("Context-aware risk adjustment error: %s", exc)
            # --- End context-aware risk ---

            marker = self.decision_tracker.add_entry(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=pos.get("entry_price", bar["close"]),
                side=pos.get("side", "long"),
                strategy=pos.get("strategy", "unknown"),
                size=pos.get("size", 1.0),
                stop_loss=pos.get("stop_loss", 0),
                take_profit=pos.get("take_profit", 0),
                reasoning=reasoning,
                confidence=confidence,
                metadata=metadata,
            )
            if intraday_levels_payload is not None:
                marker.details["intraday_levels"] = dict(intraday_levels_payload)
            if context_risk_payload is not None:
                marker.details["context_risk"] = dict(context_risk_payload)
            elif risk_adjustment is not None:
                marker.details["context_risk"] = risk_adjustment.to_dict()
            if isinstance(metadata, dict) and isinstance(
                metadata.get("break_even"), dict
            ):
                marker.details["break_even"] = dict(metadata.get("break_even") or {})
            elif isinstance(response.get("break_even"), dict):
                marker.details["break_even"] = dict(response.get("break_even") or {})
            # Attach regime for UI context if available
            marker.regime = response.get("regime") or marker.regime
            self._attach_market_context(marker, market_context)
            await self._notify_decision(marker.to_dict())

        # Trades closed
        if "position_closed" in response:
            pos = response["position_closed"]
            marker = self.decision_tracker.add_exit(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=pos.get("exit_price", bar["close"]),
                side=pos.get("side", "long"),
                reason=pos.get("exit_reason", "unknown"),
                pnl_pct=pos.get("pnl_pct", 0),
                pnl_dollars=pos.get("pnl_dollars", 0),
                entry_price=pos.get("entry_price"),
                entry_time=pos.get("entry_time"),
                bars_held=pos.get("bars_held"),
                size=pos.get("size"),
                costs=pos.get("costs"),
                gross_pnl_pct=pos.get("gross_pnl_pct"),
                gross_pnl_dollars=(
                    pos.get("gross_pnl_dollars")
                    if pos.get("gross_pnl_dollars") is not None
                    else (
                        pos.get("gross_pnl_pct", 0)
                        * pos.get("entry_price", 0)
                        * pos.get("size", 1)
                        / 100
                        if pos.get("gross_pnl_pct") is not None
                        else None
                    )
                ),
                cost_usd=pos.get("cost_usd"),
                cost_pct=pos.get("cost_pct"),
                pnl_usd=pos.get("pnl_usd"),
                position_notional_usd=pos.get("position_notional_usd"),
                schema_version=pos.get("schema_version", 1),
            )
            if intraday_levels_payload is not None:
                marker.details["intraday_levels"] = dict(intraday_levels_payload)
            if isinstance(pos.get("level_context"), dict):
                marker.details["level_context"] = dict(pos.get("level_context") or {})
            if isinstance(pos.get("flow_snapshot"), dict):
                marker.details["flow_snapshot"] = dict(pos.get("flow_snapshot") or {})
            if isinstance(pos.get("signal_metadata"), dict):
                marker.details["signal_metadata"] = dict(
                    pos.get("signal_metadata") or {}
                )
                signal_be = pos.get("signal_metadata", {}).get("break_even")
                if isinstance(signal_be, dict):
                    marker.details["break_even"] = dict(signal_be)
            if isinstance(pos.get("break_even"), dict):
                marker.details["break_even"] = dict(pos.get("break_even") or {})
            if isinstance(pos.get("entry_quality_diagnostics"), dict):
                marker.details["entry_quality_diagnostics"] = dict(
                    pos.get("entry_quality_diagnostics") or {}
                )
            if "flow_strategy" in pos:
                marker.details["flow_strategy"] = bool(pos.get("flow_strategy"))
            if "book_pressure_confirmed" in pos:
                marker.details["book_pressure_confirmed"] = pos.get(
                    "book_pressure_confirmed"
                )
            if "book_pressure_avg" in pos:
                marker.details["book_pressure_avg"] = pos.get("book_pressure_avg")
            if "book_pressure_trend" in pos:
                marker.details["book_pressure_trend"] = pos.get("book_pressure_trend")
            if "signed_aggression" in pos:
                marker.details["signed_aggression"] = pos.get("signed_aggression")
            self._attach_market_context(marker, market_context)
            await self._notify_decision(marker.to_dict())

            # Record in Performance Tracker
            # Note: position_closed payload uses 'cost_usd', not 'total_costs'
            cost_usd = pos.get("cost_usd", 0.0) or 0.0
            # Fallback: extract from costs dict if cost_usd not present
            if cost_usd == 0.0 and "costs" in pos:
                cost_usd = pos["costs"].get("total", 0.0) or 0.0
            trade_regime = (
                pos.get("regime")
                or response.get("regime")
                or (
                    response.get("regime_update", {}).get("regime")
                    if isinstance(response.get("regime_update"), dict)
                    else None
                )
                or "unknown"
            )

            self.perf_tracker.record_trade(
                strategy=pos.get("strategy", "unknown"),
                regime=trade_regime,
                ticker=self.config.ticker,
                date=self.config.date,
                side=pos.get("side", "long"),
                entry_price=pos.get("entry_price", 0.0),
                exit_price=pos.get("exit_price", bar["close"]),
                entry_time=pos.get("entry_time", ""),
                exit_time=(
                    timestamp.isoformat()
                    if hasattr(timestamp, "isoformat")
                    else str(timestamp)
                ),
                pnl_pct=pos.get("pnl_pct", 0.0),
                pnl_dollars=pos.get("pnl_dollars", 0.0),
                gross_pnl_pct=pos.get("gross_pnl_pct", 0.0),
                total_costs=cost_usd,
                exit_reason=pos.get("exit_reason", "unknown"),
                bars_held=pos.get("bars_held", 0),
                flow_strategy=pos.get("flow_strategy", False),
                book_pressure_confirmed=pos.get("book_pressure_confirmed"),
                book_pressure_avg=pos.get("book_pressure_avg"),
                book_pressure_trend=pos.get("book_pressure_trend"),
                signed_aggression=pos.get("signed_aggression"),
                entry_quality_diagnostics=(
                    dict(pos.get("entry_quality_diagnostics", {}))
                    if isinstance(pos.get("entry_quality_diagnostics"), dict)
                    else None
                ),
            )

        # Session ended
        if response.get("phase") == "END_OF_DAY" and isinstance(
            response.get("session_summary"), dict
        ):
            self.session_summary = response["session_summary"]
            summary_warnings = self._normalize_selection_warnings(
                self.session_summary.get("selection_warnings")
            )
            if summary_warnings:
                self.selection_warnings = summary_warnings
            elif self.selection_warnings:
                self.session_summary["selection_warnings"] = list(
                    self.selection_warnings
                )
            marker_key = str(
                self.session_summary.get("date")
                or (
                    timestamp.date().isoformat()
                    if hasattr(timestamp, "date")
                    else timestamp
                )
            )
            if marker_key not in self._session_end_marker_keys:
                marker = self.decision_tracker.add_session_end(
                    timestamp=timestamp,
                    bar_index=self.current_bar_index,
                    price=bar["close"],
                    summary=dict(self.session_summary),
                )
                self._attach_market_context(marker, market_context)
                self._session_end_marker_keys.add(marker_key)
                await self._notify_decision(marker.to_dict())

    @staticmethod
    def _extract_strategy_label(response: Dict[str, Any]) -> Optional[str]:
        """Resolve selected strategy from possible response keys."""
        return (
            response.get("strategy")
            or response.get("selected_strategy")
            or (response.get("strategies") or [None])[0]
        )

    def _generate_regime_explanation(self, response: Dict[str, Any]) -> str:
        """Generate human-readable explanation for regime detection."""
        regime = response.get("regime", "UNKNOWN")
        micro_regime = response.get("micro_regime")
        indicators = response.get("indicators", {})

        def _as_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        trend_eff = _as_float(indicators.get("trend_efficiency"))
        volatility = _as_float(indicators.get("volatility"))
        adx = _as_float(indicators.get("adx"))

        if regime == "TRENDING":
            if trend_eff is None:
                base = "Market showing directional movement (trend context unavailable)"
            elif trend_eff >= 0.45:
                base = (
                    "Market showing directional movement with elevated trend efficiency"
                )
            elif trend_eff < 0.15:
                base = "Market tagged TRENDING, but measured trend efficiency is low (transition/noise risk)"
            else:
                base = "Market showing directional bias with moderate trend efficiency"
        elif regime == "CHOPPY":
            base = (
                "Market showing sideways/noisy movement with low directional efficiency"
            )
        elif regime == "MIXED":
            base = "Market showing mixed directional and mean-reverting behavior"
        else:
            base = f"Detected {regime} regime"

        if micro_regime and micro_regime != regime:
            base += f" (micro: {micro_regime})"

        # Highlight strong macro/micro disagreement.
        if regime == "TRENDING" and micro_regime in {"CHOPPY", "MIXED", "TRANSITION"}:
            base += " [macro/micro divergence]"
        elif regime == "CHOPPY" and micro_regime in {
            "TRENDING_UP",
            "TRENDING_DOWN",
            "BREAKOUT",
        }:
            base += " [macro/micro divergence]"
        elif micro_regime == "TRANSITION":
            base += " [transition/noisy trend]"

        if indicators:
            details = []
            if trend_eff is not None:
                details.append(f"Trend Efficiency: {trend_eff:.2f}")
            if volatility is not None:
                details.append(f"Volatility: {volatility:.2f}%")
            if adx is not None:
                details.append(f"ADX: {adx:.1f}")
            else:
                details.append("ADX: N/A")
            atr = _as_float(indicators.get("atr"))
            if atr is not None:
                details.append(f"ATR: {atr:.2f}")

            if details:
                base += f" ({', '.join(details)})"

        return base

    async def run_all(self, speed_ms=100) -> Dict[str, Any]:
        """Run through all bars with a simple, predictable delay per bar.

        - Strings like "10hz" are converted to milliseconds (100ms for 10hz).
        - "max"/0/None means no intentional delay (but we still yield to the loop).
        - Always notifies every processed bar so the UI progress moves smoothly.
        """
        self.is_running = True
        self.is_paused = False
        self.last_run_speed = speed_ms

        # Normalize speed to milliseconds delay
        delay_ms: float
        if isinstance(speed_ms, str):
            norm = speed_ms.strip().lower()
            if norm.endswith("hz") and norm[:-2].isdigit():
                hz = int(norm[:-2])
                delay_ms = 1000.0 / hz if hz > 0 else 0
            elif norm in {"max", "fast", "instant"}:
                delay_ms = 0
            else:
                try:
                    delay_ms = float(norm)
                except ValueError:
                    delay_ms = 100.0
        else:
            delay_ms = float(speed_ms) if speed_ms is not None else 100.0

        delay_seconds = max(delay_ms, 0) / 1000.0
        logger.info(
            f"Starting run_all with normalized delay {delay_seconds:.4f}s per bar (raw={speed_ms})"
        )

        while self.is_running:
            if self.is_paused:
                await asyncio.sleep(0.05)
                continue

            if self.current_bar_index < len(self.bars):
                self._progressive_wait_started_at = None
                step_result = await self.step(notify=True)
                if not bool(step_result.get("success")):
                    logger.error(
                        "Stopping run_all after step failure at bar_index=%s: %s",
                        step_result.get("bar_index", self.current_bar_index),
                        step_result.get("error", "unknown error"),
                    )
                    break

                # Yield to event loop; add delay when requested
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                else:
                    await asyncio.sleep(0)  # cooperative yield, no throttle
                continue

            # Dynamic run-range mode: wait for background chunks to append bars.
            if (
                self._progressive_loading_enabled
                and not self._progressive_loading_complete
            ):
                if self._progressive_wait_started_at is None:
                    self._progressive_wait_started_at = time_module.monotonic()
                waited = time_module.monotonic() - self._progressive_wait_started_at
                wait_timeout = max(
                    1.0, float(self._progressive_wait_timeout_seconds or 0)
                )
                if waited <= wait_timeout:
                    await asyncio.sleep(0.1)
                    continue

                timeout_msg = f"Timed out waiting for progressive data chunks after {wait_timeout:.1f}s"
                logger.warning("%s (run_id=%s)", timeout_msg, self.config.run_id)
                if not self._progressive_loading_last_error:
                    self._progressive_loading_last_error = timeout_msg
                self._progressive_loading_complete = True
                task = self._progressive_loading_task
                if task is not None and not task.done():
                    task.cancel()

            break

        self.is_running = False
        logger.info("run_all completed")
        return self.get_summary()

    def pause(self):
        """Pause the run."""
        self.is_paused = True

    def resume(self):
        """Resume the run."""
        self.is_paused = False

    def stop(self):
        """Stop the run."""
        self.is_running = False
        task = self._progressive_loading_task
        if task is not None and not task.done():
            task.cancel()
        self._progressive_loading_complete = True
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.close_http_session())
        except RuntimeError:
            # No running event loop (defensive; typically not expected in API runtime).
            pass

    def get_state(self) -> Dict[str, Any]:
        """Get current runner state."""
        state = {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "date": self.config.date,
            "date_from": self.config.date_from,
            "date_to": self.config.date_to,
            "current_bar_index": self.current_bar_index,
            "total_bars": len(self.bars),
            "progress_pct": (
                (self.current_bar_index / len(self.bars) * 100) if self.bars else 0
            ),
            "phase": self.phase,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "markers_count": len(self.decision_tracker.markers),
            "selection_warnings": list(self.selection_warnings),
        }
        if self._progressive_loading_enabled:
            state["data_loading"] = {
                "enabled": True,
                "complete": bool(self._progressive_loading_complete),
                "loaded_until": self._progressive_loading_loaded_until,
                "target_end": self._progressive_loading_target_end,
                "pending_chunks": int(self._progressive_loading_pending_chunks),
                "last_error": self._progressive_loading_last_error,
            }
        return state

    def get_markers(self) -> List[Dict[str, Any]]:
        """Get all decision markers."""
        return self.decision_tracker.get_markers()

    def get_chart_annotations(self) -> List[Dict[str, Any]]:
        """Get markers formatted for chart display."""
        return self.decision_tracker.get_chart_annotations()

    def get_processed_bars(self) -> List[Dict[str, Any]]:
        """Get all bars processed so far."""
        return self.bars[: self.current_bar_index]

    def get_summary(self) -> Dict[str, Any]:
        """Get session summary."""
        summary = self._build_session_summary()
        payload: Dict[str, Any] = {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "date": self.config.date,
            "total_bars": len(self.bars),
            "processed_bars": self.current_bar_index,
            "phase": self.phase,
            "markers": self.decision_tracker.get_markers(),
            "session_summary": summary,
        }
        if isinstance(self._report_metadata, dict) and self._report_metadata:
            payload["report_metadata"] = dict(self._report_metadata)
            report_profile_fields = {
                "unified_profile_id": _normalize_profile_token(
                    self._report_metadata.get("unified_profile_id")
                ),
                "unified_profile_name": _normalize_profile_token(
                    self._report_metadata.get("unified_profile_name")
                ),
                "adaptive_profile_id": _normalize_profile_token(
                    self._report_metadata.get("adaptive_profile_id")
                ),
                "adaptive_profile_name": _normalize_profile_token(
                    self._report_metadata.get("adaptive_profile_name")
                ),
                "strategy_combo_profile_id": _normalize_profile_token(
                    self._report_metadata.get("strategy_combo_profile_id")
                ),
                "strategy_combo_profile_name": _normalize_profile_token(
                    self._report_metadata.get("strategy_combo_profile_name")
                ),
            }
            for field, token in report_profile_fields.items():
                if token:
                    payload[field] = token
        if isinstance(self._aos_applied, dict) and self._aos_applied:
            payload["aos_applied"] = dict(self._aos_applied)
        if isinstance(self._execution_config, dict) and self._execution_config:
            payload["execution_config"] = dict(self._execution_config)
        return payload

    def _build_session_summary(self) -> Optional[Dict[str, Any]]:
        """
        Build a run-level summary that stays accurate for date ranges.

        Strategy API's session_summary can represent the most recent (or first)
        market day only, so we recompute core totals from recorded closed trades.
        """
        base_summary = (
            dict(self.session_summary) if isinstance(self.session_summary, dict) else {}
        )
        overall = self.perf_tracker.get_overall_stats()
        total_trades = int(overall.get("total_trades", 0) or 0)
        if total_trades <= 0:
            if base_summary:
                base_summary.setdefault("run_id", self.config.run_id)
                base_summary.setdefault("ticker", self.config.ticker)
                base_summary.setdefault("date", self.config.date)
                base_summary["bars_processed"] = self.current_bar_index
                base_summary.setdefault(
                    "selection_warnings",
                    list(self.selection_warnings),
                )
                return base_summary
            return None

        trades = self.perf_tracker.get_all_trades()
        pnl_pct_values = [float(t.pnl_pct) for t in trades]
        pnl_dollar_values = [float(t.pnl_dollars) for t in trades]
        total_pnl_dollars = float(overall.get("total_pnl_dollars", 0.0) or 0.0)
        total_costs = float(overall.get("total_costs", 0.0) or 0.0)
        account_size_usd = float(
            base_summary.get("account_size_usd", self.config.account_size_usd) or 0.0
        )
        if account_size_usd > 0:
            total_pnl_pct = (total_pnl_dollars / account_size_usd) * 100.0
        else:
            total_pnl_pct = float(overall.get("total_pnl_pct", 0.0) or 0.0)

        gross_wins = sum(x for x in pnl_dollar_values if x > 0)
        gross_losses = abs(sum(x for x in pnl_dollar_values if x <= 0))
        profit_factor_dollars = (
            (gross_wins / gross_losses) if gross_losses > 0 else float("inf")
        )

        running = 0.0
        peak = 0.0
        max_drawdown_dollars = 0.0
        for pnl in pnl_dollar_values:
            running += pnl
            peak = max(peak, running)
            max_drawdown_dollars = max(max_drawdown_dollars, peak - running)

        selection_warnings = self._normalize_selection_warnings(
            base_summary.get("selection_warnings")
        )
        if not selection_warnings and self.selection_warnings:
            selection_warnings = list(self.selection_warnings)
        entry_timing_breakdown = (
            dict(overall.get("entry_timing_breakdown"))
            if isinstance(overall.get("entry_timing_breakdown"), dict)
            else self.perf_tracker.get_entry_timing_breakdown()
        )
        vwap_diag_bucket = None
        if isinstance(entry_timing_breakdown, dict):
            by_strategy = (
                entry_timing_breakdown.get("first_bar_stop_by_strategy")
                if isinstance(
                    entry_timing_breakdown.get("first_bar_stop_by_strategy"), dict
                )
                else {}
            )
            vwap_diag_bucket = (
                by_strategy.get("vwap_magnet")
                or by_strategy.get("vwapmagnet")
                or by_strategy.get("vwap magnet")
            )

        merged = {
            "ticker": self.config.ticker,
            "date": self.config.date,
            "run_id": self.config.run_id,
            "regime": base_summary.get("regime")
            or (self.last_response or {}).get("regime"),
            "micro_regime": base_summary.get("micro_regime")
            or (self.last_response or {}).get("micro_regime"),
            "strategy": base_summary.get("strategy")
            or (self.last_response or {}).get("strategy"),
            "total_trades": total_trades,
            "winning_trades": int(overall.get("winning_trades", 0) or 0),
            "losing_trades": int(overall.get("losing_trades", 0) or 0),
            "win_rate": float(overall.get("win_rate", 0.0) or 0.0),
            "trades": [t.to_dict() for t in trades],
            "total_pnl_pct": round(total_pnl_pct, 4),
            "avg_pnl_pct": round(total_pnl_pct / total_trades, 4),
            "total_pnl_dollars": round(total_pnl_dollars, 4),
            "avg_pnl_dollars": round(total_pnl_dollars / total_trades, 4),
            "total_costs": round(total_costs, 4),
            "best_trade": round(max(pnl_pct_values), 4),
            "worst_trade": round(min(pnl_pct_values), 4),
            "profit_factor_dollars": (
                "inf"
                if profit_factor_dollars == float("inf")
                else round(profit_factor_dollars, 4)
            ),
            "max_drawdown_dollars": round(max_drawdown_dollars, 4),
            "bars_processed": self.current_bar_index,
            "pre_market_bars": base_summary.get("pre_market_bars", 0),
            "selection_warnings": selection_warnings,
            "regime_history": list(base_summary.get("regime_history", [])),
            "entry_timing_diagnostics": entry_timing_breakdown,
            "success": total_pnl_dollars > 0.0,
        }
        if isinstance(vwap_diag_bucket, dict):
            merged["vwap_magnet_entry_timing_diagnostics"] = dict(vwap_diag_bucket)
        return merged

    def save_reports(self, output_dir: str):
        """Save performance report and trades."""
        import json
        from pathlib import Path

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save performance data
        perf_path = out_path / "performance_data.json"
        self.perf_tracker.save(str(perf_path))
        logger.info(f"Saved performance data to {perf_path}")

        # Save trades CSV
        csv_path = out_path / "trades.csv"
        self.perf_tracker.export_csv(str(csv_path))
        logger.info(f"Saved trades CSV to {csv_path}")

        # Save session summary JSON
        summary_path = out_path / "session_summary.json"
        with open(summary_path, "w") as f:
            json.dump(self.get_summary(), f, indent=2, default=str)
        logger.info(f"Saved session summary to {summary_path}")
