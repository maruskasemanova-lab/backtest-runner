"""
Session Runner - Orchestrates the connection between data source and strategy evaluator.
"""

import asyncio
import math
import os
import time as time_module
from datetime import datetime, time, timezone
from typing import Callable, Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import logging

import httpx
import orjson

from decision_tracker import DecisionTracker, MarkerType
from performance_tracker import PerformanceTracker
from strategy_api_auth_headers import build_strategy_api_headers
from src.services.session_runner_execution_state import ExecutionStateManager
from src.services.session_runner_market_context import MarketContextProvider
from src.services.session_runner_marker_utils import (
    apply_intraday_levels_details,
    enrich_signal_marker_details,
    resolve_execution_status_marker_price,
    resolve_intraday_levels_payload,
    resolve_signal_marker_snapshot,
    resolve_strategy_selection_options,
)
from src.services.session_runner_intrabar_utils import IntrabarQuoteProvider
from src.services.session_runner_bar_processing import StrategyBarProcessor
from src.services.session_runner_models import (
    StrategyBarResponse,
    StrategySignalPayload,
    dump_payload,
    dump_payload_or_none,
    ExecutionLifecycle,
)
from src.services.session_runner_payload_validator import (
    StrategyBarPayloadValidator,
)
from src.services.session_runner_response_utils import (
    PendingExecutionStatusMarker,
    build_pending_execution_status_marker,
    extract_candidate_diagnostics,
    extract_strategy_label,
    generate_regime_explanation,
)
from src.services.session_runner_strategy_recovery import (
    StrategySessionRecoveryHelper,
)
from src.services.session_runner_strategy_client import StrategyApiClient
from src.services.session_runner_summary_utils import (
    build_runner_state_payload,
    build_session_summary_payload,
    build_summary_payload,
    resolve_session_end_update,
)
from src.services.session_runner_trade_utils import (
    apply_entry_marker_details,
    build_exit_marker_kwargs,
    build_closed_trade_record_kwargs,
    build_exit_marker_details,
    resolve_entry_marker_context,
    resolve_entry_position_snapshot,
)

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

try:
    import polars as _pl
except Exception:  # pragma: no cover - polars may be unavailable in some envs
    _pl = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SessionRunner")
_PROFILE_PLACEHOLDER_TOKENS = {"none", "null", "n/a", "na", "undefined", "-"}
_ORJSON_OPTIONS = orjson.OPT_NAIVE_UTC | orjson.OPT_SERIALIZE_NUMPY


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
        self._data_selection_warnings: List[str] = []
        # Optional run-level metadata injected by start_run service for reports.
        self._report_metadata: Dict[str, Any] = {}
        self._aos_applied: Dict[str, Any] = {}
        self._execution_config: Dict[str, Any] = {}
        self._run_request_config: Dict[str, Any] = {}
        self._l2_applied: Dict[str, Any] = {}
        self._strategy_state_reset: Optional[bool] = None
        self._strategy_state_reset_detail: Optional[Dict[str, Any]] = None
        self._orchestrator_reset_scope: Optional[str] = None
        self._checkpoint_loaded: Optional[Any] = None
        self._context_risk_config: Optional[Any] = None
        self._context_risk_skip_count: int = 0
        self._session_end_marker_keys: Set[str] = set()
        self._session_start_marker_emitted: bool = False
        self._execution_state_manager = ExecutionStateManager()
        self._market_context_provider: Optional[MarketContextProvider] = None

        # Cross-asset reference bars (e.g. QQQ), keyed by ISO timestamp
        self.ref_bars_map: Dict[str, Dict[str, Any]] = {}
        self.l2_manager: Optional[Any] = None
        self._intrabar_quote_cache: Dict[int, Optional[List[Dict[str, float]]]] = {}
        self._strategy_http_session: Optional[Any] = None
        self._strategy_http_session_loop: Optional[asyncio.AbstractEventLoop] = None
        self._strategy_api_client = StrategyApiClient(
            strategy_api_url=self.config.strategy_api_url,
            headers_factory=self._strategy_api_headers,
            session_factory=lambda **kwargs: httpx.AsyncClient(**kwargs),
        )
        self._strategy_bar_processor = StrategyBarProcessor(
            strategy_api_client=self._strategy_api_client,
            recover_strategy_session=self._recover_strategy_session,
            on_session_state_change=self._sync_strategy_client_state,
            close_client=self.close_http_session,
            is_recoverable_strategy_error=self._is_recoverable_strategy_error,
        )
        self._strategy_bar_payload_validator = StrategyBarPayloadValidator()
        self._strategy_recovery_helper = StrategySessionRecoveryHelper(
            strategy_api_client=self._strategy_api_client,
            validate_strategy_bar_payload=self._strategy_bar_payload_validator.validate,
            on_session_state_change=self._sync_strategy_client_state,
            close_client=self.close_http_session,
            logger=logger,
        )
        self._intrabar_quote_provider = IntrabarQuoteProvider(
            ticker=self.config.ticker,
            to_utc_datetime=self._to_utc_datetime,
            logger=logger,
        )
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

        # Event callbacks + queue-based pub/sub fanout.
        self._on_bar_callbacks: List[Callable[[Dict[str, Any]], Any]] = []
        self._on_decision_callbacks: List[Callable[[Dict[str, Any]], Any]] = []
        self._bar_events_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._decision_events_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._bulk_playback_enabled: bool = self._env_flag(
            "BACKTEST_RUNNER_BULK_PLAYBACK_ENABLED",
            True,
        )
        self._bulk_trade_chunk_size: int = self._env_int(
            "BACKTEST_RUNNER_BULK_TRADE_CHUNK_SIZE",
            10_000,
            minimum=1,
        )
        self._bar_update_throttle_seconds: float = self._env_float(
            "BACKTEST_RUNNER_WS_THROTTLE_MS",
            100.0,
            minimum=0.0,
        ) / 1000.0
        self._bar_update_progress_step_pct: float = self._env_float(
            "BACKTEST_RUNNER_WS_PROGRESS_STEP_PCT",
            2.0,
            minimum=0.1,
            maximum=100.0,
        )
        self._last_bar_notify_at: Optional[float] = None
        self._last_bar_notify_progress_bucket: int = -1
        self._last_bar_notify_warmup_only: Optional[bool] = None
        self._bulk_payload_frame: Optional[Any] = None
        self._bulk_payload_frame_signature: Optional[tuple[Any, ...]] = None
        self._slow_chunk_log_ms: float = self._env_float(
            "BACKTEST_RUNNER_SLOW_CHUNK_LOG_MS",
            250.0,
            minimum=0.0,
        )
        self._intrabar_points_observed: int = 0
        self._intrabar_bars_observed: int = 0
        self._intrabar_sample_logged: bool = False

    def on_bar(self, callback: Callable[[Dict[str, Any]], Any]):
        """Register callback for bar updates."""
        self._on_bar_callbacks.append(callback)

    def on_decision(self, callback: Callable[[Dict[str, Any]], Any]):
        """Register callback for decision updates."""
        self._on_decision_callbacks.append(callback)

    def bar_events(self) -> asyncio.Queue[Dict[str, Any]]:
        return self._bar_events_queue

    def decision_events(self) -> asyncio.Queue[Dict[str, Any]]:
        return self._decision_events_queue

    @property
    def _position_active(self) -> bool:
        return bool(self._execution_state_manager.position_active)

    @_position_active.setter
    def _position_active(self, value: bool) -> None:
        self._execution_state_manager.position_active = bool(value)

    @property
    def _pending_entry(self) -> bool:
        return bool(self._execution_state_manager.pending_entry)

    @_pending_entry.setter
    def _pending_entry(self, value: bool) -> None:
        self._execution_state_manager.pending_entry = bool(value)

    @property
    def _execution_lifecycle(self) -> ExecutionLifecycle:
        return self._execution_state_manager.lifecycle

    @_execution_lifecycle.setter
    def _execution_lifecycle(self, value: ExecutionLifecycle) -> None:
        self._execution_state_manager.lifecycle = value

    @staticmethod
    def _drain_queue(queue: asyncio.Queue[Any]) -> None:
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _publish_event(
        self, queue: asyncio.Queue[Dict[str, Any]], payload: Dict[str, Any]
    ) -> None:
        await queue.put(self._to_json_safe(payload))

    async def _notify_bar(self, bar: Dict[str, Any]):
        """Notify all bar callbacks."""
        await self._publish_event(self._bar_events_queue, bar)
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
        await self._publish_event(self._decision_events_queue, marker)
        for cb in self._on_decision_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(marker)
                else:
                    cb(marker)
            except Exception as e:
                logger.error(f"Decision callback error: {e}")

    @staticmethod
    def _env_flag(name: str, default: bool) -> bool:
        token = str(os.getenv(name, "")).strip().lower()
        if not token:
            return bool(default)
        return token in {"1", "true", "yes", "on"}

    @staticmethod
    def _env_int(name: str, default: int, *, minimum: int) -> int:
        raw_value = os.getenv(name)
        if raw_value is None:
            return max(minimum, int(default))
        try:
            parsed = int(str(raw_value).strip())
        except (TypeError, ValueError):
            return max(minimum, int(default))
        return max(minimum, parsed)

    @staticmethod
    def _env_float(
        name: str,
        default: float,
        *,
        minimum: float,
        maximum: Optional[float] = None,
    ) -> float:
        raw_value = os.getenv(name)
        if raw_value is None:
            parsed = float(default)
        else:
            try:
                parsed = float(str(raw_value).strip())
            except (TypeError, ValueError):
                parsed = float(default)
        parsed = max(float(minimum), parsed)
        if maximum is not None:
            parsed = min(float(maximum), parsed)
        return parsed

    def _effective_trade_eval_mode(self) -> str:
        if not bool(getattr(self.config, "intrabar_execution_recalc_1s", False)):
            return "standard"
        return "intrabar_5s" if self._intrabar_eval_step_seconds() >= 5 else "intrabar_1s"

    def _bar_progress_pct_for_index(self, processed_bar_index: int) -> float:
        if not self.bars:
            return 0.0
        return ((int(processed_bar_index) + 1) / len(self.bars)) * 100.0

    def _mark_bar_notified(
        self, processed_bar_index: int, *, warmup_only: bool
    ) -> None:
        self._last_bar_notify_at = time_module.monotonic()
        self._last_bar_notify_warmup_only = bool(warmup_only)
        progress_pct = self._bar_progress_pct_for_index(processed_bar_index)
        if self._bar_update_progress_step_pct <= 0:
            self._last_bar_notify_progress_bucket = processed_bar_index
            return
        self._last_bar_notify_progress_bucket = int(
            progress_pct / self._bar_update_progress_step_pct
        )

    def _should_notify_bar_update(
        self, processed_bar_index: int, *, warmup_only: bool
    ) -> bool:
        if self._last_bar_notify_at is None:
            return True
        # Always emit the first trading bar after warmup so UI progress starts at 0%.
        if not bool(warmup_only) and self._last_bar_notify_warmup_only is True:
            return True
        if processed_bar_index >= max(0, len(self.bars) - 1):
            return True
        if self._bar_update_throttle_seconds <= 0:
            return True
        elapsed = time_module.monotonic() - self._last_bar_notify_at
        if elapsed >= self._bar_update_throttle_seconds:
            return True
        progress_pct = self._bar_progress_pct_for_index(processed_bar_index)
        progress_bucket = int(progress_pct / self._bar_update_progress_step_pct)
        return progress_bucket > self._last_bar_notify_progress_bucket

    async def _notify_bar_throttled(
        self,
        bar_payload: Dict[str, Any],
        *,
        processed_bar_index: int,
        warmup_only: bool,
    ) -> None:
        if not self._should_notify_bar_update(
            processed_bar_index,
            warmup_only=bool(warmup_only),
        ):
            return
        await self._notify_bar(bar_payload)
        self._mark_bar_notified(
            processed_bar_index,
            warmup_only=bool(warmup_only),
        )

    def _resolve_bar_runtime_context(
        self,
        bar: Dict[str, Any],
    ) -> tuple[datetime, bool]:
        timestamp = self._to_utc_datetime(bar["timestamp"])
        ts_utc = timestamp
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
        return timestamp, warmup_only

    async def _emit_session_start_marker_if_needed(
        self,
        *,
        bar: Dict[str, Any],
        timestamp: datetime,
        warmup_only: bool,
    ) -> None:
        if warmup_only or self._session_start_marker_emitted:
            return
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

    def _build_live_payload_unvalidated(
        self,
        *,
        bar: Dict[str, Any],
        timestamp: datetime,
        warmup_only: bool,
    ) -> tuple[Dict[str, Any], bool]:
        consume_pending_entry = self._execution_state_manager.consume_pending_entry()
        should_attach_intrabar_quotes = self._should_attach_intrabar_quotes(
            consume_pending_entry
        )
        intrabar_quotes = (
            self._load_intrabar_quotes(timestamp)
            if should_attach_intrabar_quotes
            else None
        )
        timestamp_token = (
            timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
        )
        if should_attach_intrabar_quotes and intrabar_quotes:
            quote_count = len(intrabar_quotes)
            self._intrabar_bars_observed += 1
            self._intrabar_points_observed += quote_count
            if not self._intrabar_sample_logged:
                self._intrabar_sample_logged = True
                logger.info(
                    "RUNNER_INTRABAR sample mode=%s step=%ss points=%d timestamp=%s",
                    self._effective_trade_eval_mode(),
                    self._intrabar_eval_step_seconds(),
                    quote_count,
                    timestamp_token,
                )
        payload: Dict[str, Any] = {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "timestamp": timestamp_token,
            "open": bar["open"],
            "high": bar["high"],
            "low": bar["low"],
            "close": bar["close"],
            "volume": bar["volume"],
            "vwap": bar.get("vwap"),
        }
        if warmup_only:
            payload["warmup_only"] = True

        for key in self.L2_PAYLOAD_KEYS:
            if key in bar:
                payload[key] = bar.get(key)
        for key in self.TCBBO_PAYLOAD_KEYS:
            if key in bar:
                payload[key] = bar.get(key)

        if intrabar_quotes:
            payload["intrabar_quotes_1s"] = [
                {
                    "s": quote.get("s"),
                    "bid": quote.get("bid"),
                    "ask": quote.get("ask"),
                }
                for quote in intrabar_quotes
                if isinstance(quote, dict)
            ]

        ref_bar = self.ref_bars_map.get(timestamp_token)
        if isinstance(ref_bar, dict):
            payload["ref_ticker"] = ref_bar.get("ticker", "QQQ")
            payload["ref_open"] = ref_bar.get("open")
            payload["ref_high"] = ref_bar.get("high")
            payload["ref_low"] = ref_bar.get("low")
            payload["ref_close"] = ref_bar.get("close")
            payload["ref_volume"] = ref_bar.get("volume")

        return payload, consume_pending_entry

    def _bulk_payload_signature(self) -> tuple[Any, ...]:
        trade_start = (
            self._trade_start_time.isoformat()
            if isinstance(self._trade_start_time, datetime)
            else None
        )
        trade_end = (
            self._trade_end_time.isoformat()
            if isinstance(self._trade_end_time, datetime)
            else None
        )
        return (
            len(self.bars),
            len(self.ref_bars_map),
            trade_start,
            trade_end,
            bool(self._should_attach_intrabar_quotes(False)),
        )

    def _refresh_bulk_payload_frame_if_needed(self) -> Optional[Any]:
        if _pl is None:
            self._bulk_payload_frame = None
            self._bulk_payload_frame_signature = None
            return None

        signature = self._bulk_payload_signature()
        if (
            self._bulk_payload_frame is not None
            and self._bulk_payload_frame_signature == signature
        ):
            return self._bulk_payload_frame

        build_started = time_module.perf_counter()
        should_attach_intrabar_quotes = bool(self._should_attach_intrabar_quotes(False))
        frame_intrabar_rows = 0
        frame_intrabar_points = 0
        rows: List[Dict[str, Any]] = []
        for bar in self.bars:
            timestamp, warmup_only = self._resolve_bar_runtime_context(bar)
            timestamp_token = (
                timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
            )
            row: Dict[str, Any] = {
                "run_id": self.config.run_id,
                "ticker": self.config.ticker,
                "timestamp": timestamp_token,
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
                "vwap": bar.get("vwap"),
                "warmup_only": bool(warmup_only),
            }
            for key in self.L2_PAYLOAD_KEYS:
                if key in bar:
                    row[key] = bar.get(key)
            for key in self.TCBBO_PAYLOAD_KEYS:
                if key in bar:
                    row[key] = bar.get(key)
            if should_attach_intrabar_quotes:
                intrabar_quotes = self._load_intrabar_quotes(timestamp)
                if intrabar_quotes:
                    quote_count = len(intrabar_quotes)
                    frame_intrabar_rows += 1
                    frame_intrabar_points += quote_count
                    self._intrabar_bars_observed += 1
                    self._intrabar_points_observed += quote_count
                    row["intrabar_quotes_1s"] = [
                        {
                            "s": quote.get("s"),
                            "bid": quote.get("bid"),
                            "ask": quote.get("ask"),
                        }
                        for quote in intrabar_quotes
                        if isinstance(quote, dict)
                    ]
            ref_bar = self.ref_bars_map.get(timestamp_token)
            if isinstance(ref_bar, dict):
                row["ref_ticker"] = ref_bar.get("ticker", "QQQ")
                row["ref_open"] = ref_bar.get("open")
                row["ref_high"] = ref_bar.get("high")
                row["ref_low"] = ref_bar.get("low")
                row["ref_close"] = ref_bar.get("close")
                row["ref_volume"] = ref_bar.get("volume")
            rows.append(row)

        try:
            self._bulk_payload_frame = _pl.DataFrame(
                rows,
                infer_schema_length=max(1, min(len(rows), 1_000)),
            )
            self._bulk_payload_frame_signature = signature
        except Exception:
            self._bulk_payload_frame = None
            self._bulk_payload_frame_signature = None

        build_ms = (time_module.perf_counter() - build_started) * 1000.0
        if build_ms >= self._slow_chunk_log_ms:
            avg_points = (
                frame_intrabar_points / frame_intrabar_rows
                if frame_intrabar_rows > 0
                else 0.0
            )
            logger.info(
                "RUNNER_PERF bulk_payload_frame mode=%s step=%ss rows=%d build_ms=%.1f intrabar_rows=%d avg_intrabar_points=%.2f",
                self._effective_trade_eval_mode(),
                self._intrabar_eval_step_seconds(),
                len(rows),
                build_ms,
                frame_intrabar_rows,
                avg_points,
            )
        return self._bulk_payload_frame

    async def _apply_strategy_response(
        self,
        *,
        bar: Dict[str, Any],
        timestamp: datetime,
        response_payload: Dict[str, Any],
        warmup_only: bool,
        notify_bar: bool,
        throttle_bar_update: bool,
    ) -> Dict[str, Any]:
        result = dict(response_payload or {})
        self.phase = result.get("phase", self.phase)
        self._update_execution_state(result)

        if warmup_only:
            resolved_warnings = self._extract_response_selection_warnings(result)
            if resolved_warnings is not None:
                self.selection_warnings = resolved_warnings
            result["warmup_only"] = True
        else:
            await self._process_decision_markers(
                result,
                bar,
                timestamp,
                response_model=None,
            )

        processed_bar_index = self.current_bar_index
        self.current_bar_index += 1
        final_result = {
            "success": True,
            "bar_index": processed_bar_index,
            "bar": bar,
            "phase": self.phase,
            "response": result,
            "total_bars": len(self.bars),
            "progress_pct": self._bar_progress_pct_for_index(processed_bar_index),
            "warmup_only": warmup_only,
        }
        self.last_response = final_result

        if isinstance(bar, dict):
            bar["bar_index"] = processed_bar_index
            bar["warmup_only"] = bool(warmup_only)
            self._apply_response_analysis_to_bar(
                bar,
                result,
                processed_bar_index=processed_bar_index,
                warmup_only=bool(warmup_only),
                include_debug_log=False,
            )

        if notify_bar:
            bar_payload = {
                **bar,
                "bar_index": processed_bar_index,
                "warmup_only": bool(warmup_only),
            }
            self._apply_response_analysis_to_bar(
                bar_payload,
                result,
                processed_bar_index=processed_bar_index,
                warmup_only=bool(warmup_only),
            )
            if throttle_bar_update:
                await self._notify_bar_throttled(
                    bar_payload,
                    processed_bar_index=processed_bar_index,
                    warmup_only=bool(warmup_only),
                )
            else:
                await self._notify_bar(bar_payload)
                self._mark_bar_notified(
                    processed_bar_index,
                    warmup_only=bool(warmup_only),
                )

        return final_result

    def load_bars(self, bars: List[Dict[str, Any]]):
        """Load bars for the session."""
        self.bars = bars
        self._market_context_provider = MarketContextProvider(
            bars=bars,
            safe_float=self._safe_float,
        )
        self.current_bar_index = 0
        self._progressive_wait_started_at = None
        self._session_end_marker_keys.clear()
        self._session_start_marker_emitted = False
        self.selection_warnings = []
        self._execution_state_manager.reset_flat()
        self._intrabar_quote_cache.clear()
        self._last_bar_notify_at = None
        self._last_bar_notify_progress_bucket = -1
        self._last_bar_notify_warmup_only = None
        self._bulk_payload_frame = None
        self._bulk_payload_frame_signature = None
        self._intrabar_points_observed = 0
        self._intrabar_bars_observed = 0
        self._intrabar_sample_logged = False
        self._drain_queue(self._bar_events_queue)
        self._drain_queue(self._decision_events_queue)
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
        self._execution_state_manager.reset_flat()
        self._intrabar_quote_cache.clear()
        self._last_bar_notify_at = None
        self._last_bar_notify_progress_bucket = -1
        self._last_bar_notify_warmup_only = None
        self._bulk_payload_frame = None
        self._bulk_payload_frame_signature = None
        self._intrabar_points_observed = 0
        self._intrabar_bars_observed = 0
        self._intrabar_sample_logged = False
        self._drain_queue(self._bar_events_queue)
        self._drain_queue(self._decision_events_queue)
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
            raw = str(value).strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            fractional_index = raw.find(".")
            if fractional_index >= 0:
                timezone_index = len(raw)
                for marker in ("+", "-"):
                    marker_index = raw.find(marker, fractional_index + 1)
                    if marker_index >= 0:
                        timezone_index = min(timezone_index, marker_index)
                fractional = raw[fractional_index + 1 : timezone_index]
                if len(fractional) > 6 and fractional.isdigit():
                    raw = (
                        f"{raw[:fractional_index + 1]}"
                        f"{fractional[:6]}"
                        f"{raw[timezone_index:]}"
                    )
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

    def _extract_response_selection_warnings(self, response: Any) -> Optional[List[str]]:
        if isinstance(response, StrategyBarResponse):
            if "selection_warnings" in response.model_fields_set:
                return self._normalize_selection_warnings(response.selection_warnings)
            regime_update = response.regime_update
            if (
                regime_update is not None
                and "selection_warnings" in regime_update.model_fields_set
            ):
                return self._normalize_selection_warnings(
                    regime_update.selection_warnings
                )
            return None

        response_payload = dump_payload(response)
        if not response_payload:
            return None
        if "selection_warnings" in response_payload:
            return self._normalize_selection_warnings(
                response_payload.get("selection_warnings")
            )
        regime_update = response_payload.get("regime_update")
        if isinstance(regime_update, dict) and "selection_warnings" in regime_update:
            return self._normalize_selection_warnings(
                regime_update.get("selection_warnings")
            )
        return None

    def _merged_selection_warnings(self) -> List[str]:
        return self._merge_selection_warnings(
            self._data_selection_warnings,
            self.selection_warnings,
        )

    def _merge_selection_warnings(self, *sources: Any) -> List[str]:
        merged: List[str] = []
        seen: Set[str] = set()
        for source in sources:
            for item in self._normalize_selection_warnings(source):
                if item in seen:
                    continue
                seen.add(item)
                merged.append(item)
        return merged

    def _apply_strategy_reset_metadata(self, target: Dict[str, Any]) -> None:
        if self._strategy_state_reset is not None:
            target["strategy_state_reset"] = bool(self._strategy_state_reset)
        if (
            isinstance(self._strategy_state_reset_detail, dict)
            and self._strategy_state_reset_detail
        ):
            target["strategy_state_reset_detail"] = self._to_json_safe(
                dict(self._strategy_state_reset_detail)
            )
        if self._orchestrator_reset_scope:
            target["orchestrator_reset_scope"] = str(self._orchestrator_reset_scope)

    @staticmethod
    def _to_json_safe(value: Any) -> Any:
        """Normalize values using orjson for fast, native serialization."""
        try:
            return orjson.loads(orjson.dumps(value, option=_ORJSON_OPTIONS))
        except TypeError:
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, dict):
                return {
                    str(key): SessionRunner._to_json_safe(item)
                    for key, item in value.items()
                }
            if isinstance(value, (list, tuple, set)):
                return [SessionRunner._to_json_safe(item) for item in value]
            if _np is not None:
                if isinstance(value, _np.ndarray):
                    return [SessionRunner._to_json_safe(item) for item in value.tolist()]
                if isinstance(value, _np.generic):
                    return value.item()
            item_method = getattr(value, "item", None)
            if callable(item_method):
                try:
                    return SessionRunner._to_json_safe(item_method())
                except Exception:
                    pass
            return str(value)

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
    def _extract_candidate_diagnostics(
        api_response: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        return extract_candidate_diagnostics(api_response)

    def _build_marker_market_context(
        self,
        bar: Dict[str, Any],
        timestamp: datetime,
        response: Any = None,
    ) -> Dict[str, Any]:
        if self._market_context_provider is not None:
            context = self._market_context_provider.build_context(self.current_bar_index)
        else:
            context = {
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
                    "open": self._safe_float(bar.get("open")),
                    "high": self._safe_float(bar.get("high")),
                    "low": self._safe_float(bar.get("low")),
                    "close": self._safe_float(bar.get("close")),
                    "volume": self._safe_float(bar.get("volume")),
                    "vwap": self._safe_float(bar.get("vwap")),
                },
                "candle": {},
                "price_evolution": {},
                "volume_context": {},
                "recent_bars": [],
            }

        bar_ohlcv = context.get("bar_ohlcv") if isinstance(context, dict) else {}
        open_px = self._safe_float(bar_ohlcv.get("open")) if isinstance(bar_ohlcv, dict) else self._safe_float(bar.get("open"))
        close_px = self._safe_float(bar_ohlcv.get("close")) if isinstance(bar_ohlcv, dict) else self._safe_float(bar.get("close"))

        is_typed_response = isinstance(response, StrategyBarResponse)
        response_payload = (
            {}
            if is_typed_response
            else dump_payload(response)
        )
        decision_state: Optional[Dict[str, Any]] = None
        if is_typed_response or response_payload:
            decision_state = {
                "phase": response.phase if is_typed_response else response_payload.get("phase"),
                "action": response.action if is_typed_response else response_payload.get("action"),
                "regime": response.regime if is_typed_response else response_payload.get("regime"),
                "micro_regime": (
                    response.micro_regime
                    if is_typed_response
                    else response_payload.get("micro_regime")
                ),
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
        if not l2_snapshot:
            l2_quality = (
                dump_payload_or_none(response.l2_quality)
                if is_typed_response
                else response_payload.get("l2_quality")
            )
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

        if decision_state is not None:
            context["decision_state"] = decision_state
        if l2_snapshot:
            context["l2"] = l2_snapshot
        if tcbbo_snapshot:
            context["tcbbo"] = tcbbo_snapshot
        if reference_context is not None:
            context["reference_asset"] = reference_context
        if is_typed_response or response_payload:
            break_even_payload = (
                dump_payload_or_none(response.break_even)
                if is_typed_response
                else response_payload.get("break_even")
            )
            if not isinstance(break_even_payload, dict):
                if is_typed_response and response.position_opened is not None:
                    opened_md = dump_payload(response.position_opened.metadata)
                else:
                    opened = response_payload.get("position_opened")
                    opened_md = (
                        opened.get("metadata")
                        if isinstance(opened, dict)
                        and isinstance(opened.get("metadata"), dict)
                        else {}
                    )
                if isinstance(opened_md.get("break_even"), dict):
                    break_even_payload = dict(opened_md.get("break_even") or {})
            if not isinstance(break_even_payload, dict):
                if is_typed_response and response.position_closed is not None:
                    break_even_payload = dump_payload_or_none(
                        response.position_closed.break_even
                    )
                else:
                    closed = response_payload.get("position_closed")
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
        self, response: Any
    ) -> Optional[PendingExecutionStatusMarker]:
        """Translate pending-signal execution outcomes into explicit decision-log markers."""
        return build_pending_execution_status_marker(
            response,
            safe_float=self._safe_float,
        )

    def _apply_response_analysis_to_bar(
        self,
        target: Dict[str, Any],
        api_response: Any,
        *,
        processed_bar_index: int,
        warmup_only: bool,
        include_debug_log: bool = False,
    ) -> None:
        if isinstance(api_response, StrategyBarResponse):
            layer_scores = dump_payload_or_none(api_response.layer_scores)
            signal_rejected = dump_payload_or_none(api_response.signal_rejected)
            golden_setup = dump_payload_or_none(api_response.golden_setup)
            intrabar_eval_trace = dump_payload_or_none(api_response.intrabar_eval_trace)
        else:
            response_payload = dump_payload(api_response)
            if not response_payload:
                return
            layer_scores = response_payload.get("layer_scores")
            signal_rejected = response_payload.get("signal_rejected")
            golden_setup = response_payload.get("golden_setup")
            intrabar_eval_trace = response_payload.get("intrabar_eval_trace")

        if isinstance(layer_scores, dict):
            target["layer_scores"] = layer_scores

        if isinstance(signal_rejected, dict):
            target["signal_rejected"] = signal_rejected

        if isinstance(golden_setup, dict):
            target["golden_setup"] = golden_setup

        if isinstance(intrabar_eval_trace, dict):
            target["intrabar_eval_trace"] = intrabar_eval_trace

        if include_debug_log and processed_bar_index <= 3:
            has_quotes = isinstance(intrabar_eval_trace, dict)
            checkpoint_count = (
                len(intrabar_eval_trace.get("checkpoints", []))
                if isinstance(intrabar_eval_trace, dict)
                else 0
            )
            logger.debug(
                "[INTRABAR-DEBUG] bar=%s has_trace=%s checkpoints=%s "
                "has_layer_scores=%s warmup=%s",
                processed_bar_index,
                has_quotes,
                checkpoint_count,
                isinstance(layer_scores, dict),
                warmup_only,
            )

        candidate_diagnostics = self._extract_candidate_diagnostics(api_response)
        if isinstance(candidate_diagnostics, dict):
            target["candidate_diagnostics"] = candidate_diagnostics

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
        return self._intrabar_quote_provider.resolve_eval_step_seconds(
            getattr(self.config, "intrabar_eval_step_seconds", 1)
        )

    def _apply_intrabar_eval_step(
        self, quotes: Optional[List[Dict[str, float]]]
    ) -> Optional[List[Dict[str, float]]]:
        return self._intrabar_quote_provider.apply_eval_step(
            quotes,
            raw_step_seconds=getattr(self.config, "intrabar_eval_step_seconds", 1),
        )

    def _load_intrabar_quotes(
        self, timestamp: datetime
    ) -> Optional[List[Dict[str, float]]]:
        return self._intrabar_quote_provider.load_quotes_for_timestamp(
            timestamp=timestamp,
            l2_manager=self.l2_manager,
            cache=self._intrabar_quote_cache,
            raw_step_seconds=getattr(self.config, "intrabar_eval_step_seconds", 1),
        )

    def _strategy_api_headers(self) -> Dict[str, str]:
        return build_strategy_api_headers(self.config.strategy_api_url)

    def _sync_strategy_client_state(self) -> None:
        self._strategy_http_session = self._strategy_api_client.session
        self._strategy_http_session_loop = self._strategy_api_client.session_loop

    async def _get_strategy_http_session(self) -> Any:
        session = await self._strategy_api_client.get_session()
        self._sync_strategy_client_state()
        return session

    async def close_http_session(self) -> None:
        await self._strategy_api_client.close()
        self._sync_strategy_client_state()

    @staticmethod
    def _is_recoverable_strategy_error(status: int, detail: str) -> bool:
        text = str(detail or "").lower()
        if status in {404, 409, 425, 429, 500, 502, 503, 504}:
            return True
        # Defensive fallback for HTML/plain text errors where status may not be enough.
        return "session not found" in text or "internal server error" in text

    def _resolve_strategy_session_date(self) -> str:
        return self._strategy_recovery_helper.resolve_session_date(
            restart_session_date=getattr(self, "_restart_session_date", ""),
            date_from=self.config.date_from,
            date=self.config.date,
        )

    def _resolve_strategy_session_config_snapshot(self) -> Dict[str, Any]:
        return self._strategy_recovery_helper.resolve_config_snapshot(
            getattr(self, "_restart_session_config", {})
        )

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
        return await self._strategy_recovery_helper.recover_session(
            run_id=self.config.run_id,
            ticker=self.config.ticker,
            reason=reason,
            detail=detail,
            session_date=session_date,
            config_snapshot=config_snapshot,
            current_bar_index=self.current_bar_index,
            bars=self.bars,
            l2_payload_keys=self.L2_PAYLOAD_KEYS,
            tcbbo_payload_keys=self.TCBBO_PAYLOAD_KEYS,
            ref_bars_map=self.ref_bars_map,
        )

    async def _replay_historical_bars(self, session_date: str) -> bool:
        """
        Replay all bars for the current session_date up to self.current_bar_index.
        This properly rebuilds the strategy API state (VWAP, intraday levels, positions) after a restart.
        """
        return await self._strategy_recovery_helper.replay_historical_bars(
            run_id=self.config.run_id,
            ticker=self.config.ticker,
            session_date=session_date,
            current_bar_index=self.current_bar_index,
            bars=self.bars,
            l2_payload_keys=self.L2_PAYLOAD_KEYS,
            tcbbo_payload_keys=self.TCBBO_PAYLOAD_KEYS,
            ref_bars_map=self.ref_bars_map,
        )

    def _update_execution_state(self, response: Dict[str, Any]) -> None:
        """Track whether next bar needs execution-level intrabar payload."""
        self._execution_state_manager.apply_response(response)

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
        return await self._apply_strategy_response(
            bar=bar,
            timestamp=result["timestamp"],
            response_payload=dict(result.get("response") or {}),
            warmup_only=bool(result.get("warmup_only", False)),
            notify_bar=bool(notify),
            throttle_bar_update=False,
        )

    async def _process_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        """Send bar to strategy evaluator and process response."""
        timestamp, warmup_only = self._resolve_bar_runtime_context(bar)
        await self._emit_session_start_marker_if_needed(
            bar=bar,
            timestamp=timestamp,
            warmup_only=warmup_only,
        )
        try:
            payload, consume_pending_entry = self._build_live_payload_unvalidated(
                bar=bar,
                timestamp=timestamp,
                warmup_only=warmup_only,
            )
        except Exception as exc:
            return {
                "success": False,
                "error": f"Payload build error: {str(exc)}",
                "bar_index": self.current_bar_index,
            }

        processed_result = await self._strategy_bar_processor.process(payload=payload)
        if not processed_result.success:
            if consume_pending_entry:
                self._pending_entry = True
            return {
                "success": False,
                "error": str(processed_result.error or "unknown error"),
                "bar_index": self.current_bar_index,
            }

        return {
            "success": True,
            "bar": bar,
            "timestamp": timestamp,
            "response": dict(processed_result.response_payload or {}),
            "warmup_only": warmup_only,
        }

    async def _process_decision_markers(
        self,
        response: Dict[str, Any],
        bar: Dict[str, Any],
        timestamp: datetime,
        *,
        response_model: Optional[StrategyBarResponse] = None,
    ):
        """Extract and record decision markers from API response."""
        response_view: Any = response_model or response
        resolved_warnings = self._extract_response_selection_warnings(response_view)
        if resolved_warnings is not None:
            self.selection_warnings = resolved_warnings

        intraday_levels_payload = resolve_intraday_levels_payload(response_view)
        market_context = self._build_marker_market_context(
            bar=bar,
            timestamp=timestamp,
            response=response_view,
        )

        await self._emit_regime_strategy_markers(
            response=response,
            response_view=response_view,
            bar=bar,
            timestamp=timestamp,
            intraday_levels_payload=intraday_levels_payload,
            market_context=market_context,
        )
        await self._emit_signal_markers(
            response=response,
            response_view=response_view,
            bar=bar,
            timestamp=timestamp,
            intraday_levels_payload=intraday_levels_payload,
            market_context=market_context,
        )
        await self._emit_pending_execution_status_marker(
            response=response_view,
            bar=bar,
            timestamp=timestamp,
            intraday_levels_payload=intraday_levels_payload,
            market_context=market_context,
        )
        should_continue = await self._emit_position_opened_marker(
            response=response,
            response_view=response_view,
            bar=bar,
            timestamp=timestamp,
            intraday_levels_payload=intraday_levels_payload,
            market_context=market_context,
        )
        if not should_continue:
            return
        await self._emit_position_closed_marker(
            response=response,
            response_view=response_view,
            bar=bar,
            timestamp=timestamp,
            intraday_levels_payload=intraday_levels_payload,
            market_context=market_context,
        )
        await self._emit_session_end_marker(
            response_view=response_view,
            bar=bar,
            timestamp=timestamp,
            market_context=market_context,
        )

    async def _emit_regime_strategy_markers(
        self,
        *,
        response: Dict[str, Any],
        response_view: Any,
        bar: Dict[str, Any],
        timestamp: datetime,
        intraday_levels_payload: Optional[Dict[str, Any]],
        market_context: Dict[str, Any],
    ) -> None:
        is_typed_response = isinstance(response_view, StrategyBarResponse)
        response_view_payload = {} if is_typed_response else dump_payload(response_view)
        response_indicators = (
            dump_payload_or_none(response_view.indicators) or {}
            if is_typed_response
            else response_view_payload.get("indicators", {})
        )
        action = response_view.action if is_typed_response else response_view_payload.get("action", "")
        if action == "regime_detected":
            regime = response_view.regime if is_typed_response else response_view_payload.get("regime")
            if regime:
                explanation = self._generate_regime_explanation(response_view)
                marker = self.decision_tracker.add_regime_detected(
                    timestamp=timestamp,
                    bar_index=self.current_bar_index,
                    price=bar["close"],
                    regime=regime,
                    explanation=explanation,
                    indicators=response_indicators,
                )
                marker.details = apply_intraday_levels_details(
                    marker.details,
                    intraday_levels_payload,
                )
                self._attach_market_context(marker, market_context)
                await self._notify_decision(marker.to_dict())

                strategy = self._extract_strategy_label(response_view)
                if strategy:
                    options = resolve_strategy_selection_options(
                        strategy,
                        (
                            response_view.strategies
                            if is_typed_response
                            else response_view_payload.get("strategies")
                        ),
                    )
                    marker = self.decision_tracker.add_strategy_selected(
                        timestamp=timestamp,
                        bar_index=self.current_bar_index,
                        price=bar["close"],
                        strategy=strategy,
                        regime=regime,
                        reasoning=f"Selected {strategy} strategy for {regime} regime",
                        alternative_strategies=options.alternative_strategies,
                        active_strategies=options.active_strategies,
                        selection_warnings=self.selection_warnings,
                    )
                    self._attach_market_context(marker, market_context)
                    await self._notify_decision(marker.to_dict())

        regime_update = (
            response_view.regime_update
            if is_typed_response
            else response_view_payload.get("regime_update")
        )
        if not regime_update:
            return

        regime_update_payload = dump_payload_or_none(regime_update) or {}
        regime = (
            regime_update.regime
            if is_typed_response and regime_update.regime
            else regime_update_payload.get("regime") or response_view_payload.get("regime")
        )
        regime_indicators = (
            dump_payload_or_none(regime_update.indicators) or response_indicators
            if is_typed_response
            else regime_update_payload.get("indicators") or response_indicators
        )
        if regime:
            update_payload = {
                "regime": regime,
                "micro_regime": (
                    response_view.micro_regime
                    if is_typed_response
                    else response_view_payload.get("micro_regime")
                ),
                "indicators": regime_indicators,
            }
            explanation = (
                f"Intraday refresh: {self._generate_regime_explanation(update_payload)}"
            )
            marker = self.decision_tracker.add_regime_detected(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=bar["close"],
                regime=regime,
                explanation=explanation,
                indicators=regime_indicators,
            )
            marker.details = apply_intraday_levels_details(
                marker.details,
                intraday_levels_payload,
            )
            self._attach_market_context(marker, market_context)
            await self._notify_decision(marker.to_dict())

        strategy = (
            regime_update.strategy
            if is_typed_response and regime_update.strategy
            else regime_update_payload.get("strategy") or self._extract_strategy_label(response_view)
        )
        if not (strategy and regime):
            return

        strategy_options_payload = (
            regime_update.strategies
            if is_typed_response and isinstance(regime_update.strategies, list)
            else (
                regime_update_payload.get("strategies")
                if isinstance(regime_update_payload.get("strategies"), list)
                else (
                    response_view.strategies
                    if is_typed_response
                    else response_view_payload.get("strategies")
                )
            )
        )
        options = resolve_strategy_selection_options(strategy, strategy_options_payload)
        marker = self.decision_tracker.add_strategy_selected(
            timestamp=timestamp,
            bar_index=self.current_bar_index,
            price=bar["close"],
            strategy=strategy,
            regime=regime,
            reasoning=f"Updated {strategy} after intraday regime refresh",
            alternative_strategies=options.alternative_strategies,
            active_strategies=options.active_strategies,
            selection_warnings=self.selection_warnings,
            switch_guard=(
                dump_payload_or_none(regime_update.switch_guard)
                if is_typed_response
                else (
                    regime_update_payload.get("switch_guard")
                    if isinstance(regime_update_payload.get("switch_guard"), dict)
                    else None
                )
            ),
        )
        self._attach_market_context(marker, market_context)
        await self._notify_decision(marker.to_dict())

    async def _emit_signal_markers(
        self,
        *,
        response: Dict[str, Any],
        response_view: Any,
        bar: Dict[str, Any],
        timestamp: datetime,
        intraday_levels_payload: Optional[Dict[str, Any]],
        market_context: Dict[str, Any],
    ) -> None:
        response_view_payload = (
            {}
            if isinstance(response_view, StrategyBarResponse)
            else dump_payload(response_view)
        )
        signals = (
            response_view.signals
            if isinstance(response_view, StrategyBarResponse)
            else response_view_payload.get("signals", [])
        )
        response_tcbbo_confirmation = (
            response_view.tcbbo_confirmation
            if isinstance(response_view, StrategyBarResponse)
            else response_view_payload.get("tcbbo_confirmation")
        )
        for signal in signals:
            signal_snapshot = resolve_signal_marker_snapshot(
                signal,
                default_price=bar["close"],
            )
            marker = self.decision_tracker.add_signal(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=signal_snapshot.price,
                signal_type=signal_snapshot.signal_type,
                strategy=signal_snapshot.strategy,
                confidence=signal_snapshot.confidence,
                reasoning=signal_snapshot.reasoning,
                stop_loss=signal_snapshot.stop_loss,
                take_profit=signal_snapshot.take_profit,
            )
            marker.details = enrich_signal_marker_details(
                marker.details,
                signal=signal,
                response_tcbbo_confirmation=response_tcbbo_confirmation,
                intraday_levels_payload=intraday_levels_payload,
            )
            self._attach_market_context(marker, market_context)
            await self._notify_decision(marker.to_dict())

    async def _emit_pending_execution_status_marker(
        self,
        *,
        response: Dict[str, Any],
        bar: Dict[str, Any],
        timestamp: datetime,
        intraday_levels_payload: Optional[Dict[str, Any]],
        market_context: Dict[str, Any],
    ) -> None:
        pending_execution_status = self._build_pending_execution_status_marker(response)
        if pending_execution_status is None:
            return

        marker = self.decision_tracker.add_execution_status(
            timestamp=timestamp,
            bar_index=self.current_bar_index,
            price=resolve_execution_status_marker_price(
                bar,
                safe_float=self._safe_float,
            ),
            title=pending_execution_status.title,
            description=pending_execution_status.description,
            strategy=pending_execution_status.strategy,
            confidence=pending_execution_status.confidence,
            details=apply_intraday_levels_details(
                dict(pending_execution_status.details),
                intraday_levels_payload,
            ),
        )
        self._attach_market_context(marker, market_context)
        await self._notify_decision(marker.to_dict())

    async def _emit_position_opened_marker(
        self,
        *,
        response: Dict[str, Any],
        response_view: Any,
        bar: Dict[str, Any],
        timestamp: datetime,
        intraday_levels_payload: Optional[Dict[str, Any]],
        market_context: Dict[str, Any],
    ) -> bool:
        response_view_payload = (
            {}
            if isinstance(response_view, StrategyBarResponse)
            else dump_payload(response_view)
        )
        position_source = (
            response_view.position_opened
            if isinstance(response_view, StrategyBarResponse)
            else response_view_payload.get("position_opened")
        )
        if position_source is None or (
            isinstance(position_source, dict) and not position_source
        ):
            return True

        entry_snapshot = resolve_entry_position_snapshot(
            position_source,
            default_entry_price=bar["close"],
        )
        entry_context = resolve_entry_marker_context(response_view, position_source)
        logger.info(
            f"DEBUG_SIGNAL_RECV: Bar {self.current_bar_index} Time {timestamp} "
            f"Strat {entry_snapshot.strategy} "
            f"Reasoning: {entry_context.reasoning[:100]}"
        )

        risk_adjustment = None
        resolved_stop_loss = entry_snapshot.stop_loss
        resolved_take_profit = entry_snapshot.take_profit
        if entry_context.context_risk_payload is None:
            ctx_cfg = self._context_risk_config
            if ctx_cfg is None and ContextRiskConfig is not None:
                ctx_cfg = ContextRiskConfig.from_execution_config(self._execution_config)
                self._context_risk_config = ctx_cfg

            if (
                ctx_cfg is not None
                and getattr(ctx_cfg, "enabled", False)
                and adjust_entry_risk is not None
                and intraday_levels_payload is not None
            ):
                try:
                    sweep_payload = entry_context.liquidity_sweep_payload or {}
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
                        entry_price=entry_snapshot.entry_price,
                        side=entry_snapshot.side,
                        original_sl=resolved_stop_loss,
                        original_tp=resolved_take_profit,
                        levels_payload=intraday_levels_payload,
                        config=ctx_cfg,
                        atr=atr_for_context,
                        is_sweep_trade=bool(
                            entry_context.sweep_triggered
                            or (
                                isinstance(sweep_payload, dict)
                                and sweep_payload.get("detected", False)
                            )
                        ),
                        strategy_key=str(entry_snapshot.strategy),
                    )
                    if risk_adjustment.skip:
                        self._context_risk_skip_count += 1
                        logger.info(
                            "Context-aware risk SKIP trade: %s (%s)",
                            entry_snapshot.strategy,
                            risk_adjustment.skip_reason,
                        )
                        skip_marker = self.decision_tracker.add_signal(
                            timestamp=timestamp,
                            bar_index=self.current_bar_index,
                            price=entry_snapshot.entry_price,
                            signal_type="SKIP",
                            strategy=entry_snapshot.strategy,
                            confidence=entry_context.confidence,
                            reasoning=f"Context-risk skip: {risk_adjustment.skip_reason}",
                            stop_loss=risk_adjustment.original_sl,
                            take_profit=risk_adjustment.original_tp,
                        )
                        skip_marker.details["context_risk"] = risk_adjustment.to_dict()
                        skip_marker.details = apply_intraday_levels_details(
                            skip_marker.details,
                            intraday_levels_payload,
                        )
                        self._attach_market_context(skip_marker, market_context)
                        await self._notify_decision(skip_marker.to_dict())
                        return False

                    resolved_stop_loss = risk_adjustment.adjusted_sl
                    resolved_take_profit = risk_adjustment.adjusted_tp
                    logger.info(
                        "Context-aware risk adjusted %s: SL %.2f→%.2f (%s), TP %.2f→%.2f (%s)",
                        entry_snapshot.strategy,
                        risk_adjustment.original_sl,
                        risk_adjustment.adjusted_sl,
                        risk_adjustment.sl_reason,
                        risk_adjustment.original_tp,
                        risk_adjustment.adjusted_tp,
                        risk_adjustment.tp_reason,
                    )
                except Exception as exc:
                    logger.warning("Context-aware risk adjustment error: %s", exc)

        marker = self.decision_tracker.add_entry(
            timestamp=timestamp,
            bar_index=self.current_bar_index,
            price=entry_snapshot.entry_price,
            side=entry_snapshot.side,
            strategy=entry_snapshot.strategy,
            size=entry_snapshot.size,
            stop_loss=resolved_stop_loss,
            take_profit=resolved_take_profit,
            reasoning=entry_context.reasoning,
            confidence=entry_context.confidence,
            metadata=entry_context.metadata,
        )
        marker.details = apply_entry_marker_details(
            marker.details,
            intraday_levels_payload=intraday_levels_payload,
            entry_context=entry_context,
            response_break_even=(
                response_view.break_even
                if isinstance(response_view, StrategyBarResponse)
                else response_view_payload.get("break_even")
            ),
            risk_adjustment=risk_adjustment,
        )
        marker.regime = (
            response_view.regime
            if isinstance(response_view, StrategyBarResponse)
            else response_view_payload.get("regime")
        ) or marker.regime
        self._attach_market_context(marker, market_context)
        await self._notify_decision(marker.to_dict())
        return True

    async def _emit_position_closed_marker(
        self,
        *,
        response: Dict[str, Any],
        response_view: Any,
        bar: Dict[str, Any],
        timestamp: datetime,
        intraday_levels_payload: Optional[Dict[str, Any]],
        market_context: Dict[str, Any],
    ) -> None:
        response_view_payload = (
            {}
            if isinstance(response_view, StrategyBarResponse)
            else dump_payload(response_view)
        )
        position_source = (
            response_view.position_closed
            if isinstance(response_view, StrategyBarResponse)
            else response_view_payload.get("position_closed")
        )
        if position_source is None or (
            isinstance(position_source, dict) and not position_source
        ):
            return

        marker = self.decision_tracker.add_exit(
            timestamp=timestamp,
            bar_index=self.current_bar_index,
            **build_exit_marker_kwargs(
                position_source,
                default_exit_price=bar["close"],
            ),
        )
        marker.details = build_exit_marker_details(
            marker.details,
            position_payload=position_source,
            intraday_levels_payload=intraday_levels_payload,
        )
        self._attach_market_context(marker, market_context)
        await self._notify_decision(marker.to_dict())

        exit_time = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(
            timestamp
        )
        self.perf_tracker.record_trade(
            **build_closed_trade_record_kwargs(
                position_source,
                response_view,
                ticker=self.config.ticker,
                date=self.config.date,
                exit_time=exit_time,
                default_exit_price=bar["close"],
            )
        )

    async def _emit_session_end_marker(
        self,
        *,
        response_view: Any,
        bar: Dict[str, Any],
        timestamp: datetime,
        market_context: Dict[str, Any],
    ) -> None:
        phase = (
            response_view.phase
            if isinstance(response_view, StrategyBarResponse)
            else dump_payload(response_view).get("phase")
        )
        session_summary_payload = (
            response_view.session_summary
            if isinstance(response_view, StrategyBarResponse)
            else dump_payload(response_view).get("session_summary")
        )
        session_summary = dump_payload_or_none(session_summary_payload) or {}
        if phase != "END_OF_DAY" or not session_summary:
            return

        session_end_update = resolve_session_end_update(
            session_summary_payload=session_summary,
            selection_warnings=list(self.selection_warnings),
            timestamp=timestamp,
            normalize_selection_warnings=self._normalize_selection_warnings,
        )
        self.session_summary = dict(session_end_update.session_summary)
        self.selection_warnings = list(session_end_update.selection_warnings)

        if session_end_update.marker_key in self._session_end_marker_keys:
            return

        marker = self.decision_tracker.add_session_end(
            timestamp=timestamp,
            bar_index=self.current_bar_index,
            price=bar["close"],
            summary=dict(self.session_summary),
        )
        self._attach_market_context(marker, market_context)
        self._session_end_marker_keys.add(session_end_update.marker_key)
        await self._notify_decision(marker.to_dict())

    @staticmethod
    def _extract_strategy_label(response: Any) -> Optional[str]:
        """Resolve selected strategy from possible response keys."""
        return extract_strategy_label(response)

    def _generate_regime_explanation(self, response: Any) -> str:
        """Generate human-readable explanation for regime detection."""
        return generate_regime_explanation(response)

    def _bulk_range_end(self, *, warmup_only: bool) -> int:
        if self.current_bar_index >= len(self.bars):
            return self.current_bar_index
        limit = len(self.bars)
        max_chunk_size = (
            limit if warmup_only else max(1, int(self._bulk_trade_chunk_size))
        )
        end_index = self.current_bar_index
        while end_index < limit:
            _, bar_warmup_only = self._resolve_bar_runtime_context(self.bars[end_index])
            if bool(bar_warmup_only) != bool(warmup_only):
                break
            if not warmup_only and (end_index - self.current_bar_index) >= max_chunk_size:
                break
            end_index += 1
        return end_index

    async def _process_bulk_range(
        self,
        *,
        start_index: int,
        end_index: int,
    ) -> Dict[str, Any]:
        if end_index <= start_index:
            return {"success": True, "processed_count": 0}

        chunk_started = time_module.perf_counter()
        prepare_started = chunk_started
        prepared: List[Dict[str, Any]] = []
        pending_entry_before_chunk = self._pending_entry
        for index in range(start_index, end_index):
            bar = self.bars[index]
            timestamp, warmup_only = self._resolve_bar_runtime_context(bar)
            self._execution_state_manager.consume_pending_entry()
            await self._emit_session_start_marker_if_needed(
                bar=bar,
                timestamp=timestamp,
                warmup_only=warmup_only,
            )
            prepared.append(
                {
                    "bar": bar,
                    "timestamp": timestamp,
                    "warmup_only": warmup_only,
                }
            )
        prepare_ms = (time_module.perf_counter() - prepare_started) * 1000.0

        strategy_started = time_module.perf_counter()
        payload_frame = self._refresh_bulk_payload_frame_if_needed()
        batch_result: Any
        if payload_frame is not None:
            batch_result = await self._strategy_bar_processor.process_batch_frame(
                payload_frame=payload_frame.slice(start_index, end_index - start_index),
            )
        else:
            payloads: List[Dict[str, Any]] = []
            try:
                for prepared_item in prepared:
                    payload, _consume_pending_entry = self._build_live_payload_unvalidated(
                        bar=prepared_item["bar"],
                        timestamp=prepared_item["timestamp"],
                        warmup_only=bool(prepared_item["warmup_only"]),
                    )
                    payloads.append(payload)
            except Exception as exc:
                self._pending_entry = pending_entry_before_chunk
                return {
                    "success": False,
                    "error": f"Bulk payload build error: {str(exc)}",
                    "bar_index": self.current_bar_index,
                }
            batch_result = await self._strategy_bar_processor.process_batch(payloads=payloads)
        strategy_ms = (time_module.perf_counter() - strategy_started) * 1000.0

        chunk_mode = "warmup" if bool(prepared and prepared[0].get("warmup_only")) else "trade"
        if getattr(batch_result, "fallback_to_single", False):
            self._pending_entry = pending_entry_before_chunk
            last_result: Optional[Dict[str, Any]] = None
            while self.current_bar_index < end_index:
                last_result = await self.step(notify=True)
                if not bool(last_result.get("success")):
                    return last_result
            total_ms = (time_module.perf_counter() - chunk_started) * 1000.0
            if total_ms >= self._slow_chunk_log_ms:
                processed_count = max(0, end_index - start_index)
                per_bar_ms = total_ms / processed_count if processed_count else 0.0
                logger.info(
                    "RUNNER_PERF bulk_chunk_fallback mode=%s bars=%d prepare_ms=%.1f strategy_ms=%.1f total_ms=%.1f per_bar_ms=%.3f eval_mode=%s step=%ss",
                    chunk_mode,
                    processed_count,
                    prepare_ms,
                    strategy_ms,
                    total_ms,
                    per_bar_ms,
                    self._effective_trade_eval_mode(),
                    self._intrabar_eval_step_seconds(),
                )
            return {
                "success": True,
                "processed_count": end_index - start_index,
                "last_result": last_result or {},
                "phase": self.phase,
            }
        if not batch_result.success:
            self._pending_entry = pending_entry_before_chunk
            return {
                "success": False,
                "error": str(batch_result.error or "unknown error"),
                "bar_index": self.current_bar_index,
            }

        response_payloads = list(batch_result.response_payloads or [])
        if len(response_payloads) != len(prepared):
            self._pending_entry = pending_entry_before_chunk
            return {
                "success": False,
                "error": (
                    "Strategy batch response size mismatch: "
                    f"expected {len(prepared)}, got {len(response_payloads)}"
                ),
                "bar_index": self.current_bar_index,
            }

        apply_started = time_module.perf_counter()
        last_result: Optional[Dict[str, Any]] = None
        for prepared_item, response_payload in zip(prepared, response_payloads):
            last_result = await self._apply_strategy_response(
                bar=prepared_item["bar"],
                timestamp=prepared_item["timestamp"],
                response_payload=response_payload,
                warmup_only=bool(prepared_item["warmup_only"]),
                notify_bar=True,
                throttle_bar_update=True,
            )
        apply_ms = (time_module.perf_counter() - apply_started) * 1000.0
        total_ms = (time_module.perf_counter() - chunk_started) * 1000.0
        if total_ms >= self._slow_chunk_log_ms:
            processed_count = len(prepared)
            per_bar_ms = total_ms / processed_count if processed_count else 0.0
            logger.info(
                "RUNNER_PERF bulk_chunk mode=%s bars=%d prepare_ms=%.1f strategy_ms=%.1f apply_ms=%.1f total_ms=%.1f per_bar_ms=%.3f eval_mode=%s step=%ss",
                chunk_mode,
                processed_count,
                prepare_ms,
                strategy_ms,
                apply_ms,
                total_ms,
                per_bar_ms,
                self._effective_trade_eval_mode(),
                self._intrabar_eval_step_seconds(),
            )

        return {
            "success": True,
            "processed_count": len(prepared),
            "last_result": last_result or {},
            "phase": self.phase,
        }

    async def bulk_warmup(self) -> Dict[str, Any]:
        """Process the current contiguous warmup segment in one strategy request."""
        end_index = self._bulk_range_end(warmup_only=True)
        return await self._process_bulk_range(
            start_index=self.current_bar_index,
            end_index=end_index,
        )

    async def bulk_trade(self) -> Dict[str, Any]:
        """Process the current trading segment in chunked strategy requests."""
        end_index = self._bulk_range_end(warmup_only=False)
        return await self._process_bulk_range(
            start_index=self.current_bar_index,
            end_index=end_index,
        )

    async def run_all(self, speed_ms=100) -> Dict[str, Any]:
        """Run through all bars with a simple, predictable delay per bar.

        - Strings like "10hz" are converted to milliseconds (100ms for 10hz).
        - "max"/0/None means no intentional delay.
        - Zero-delay playback uses chunked batch transport to reduce HTTP overhead.
        - Delayed playback stays bar-by-bar so pause/resume semantics remain exact.
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
        intrabar_quotes_required = bool(self._should_attach_intrabar_quotes(False))
        # Bulk mode prebuilds payload frames synchronously. In intrabar mode this
        # forces eager quote loading for many bars and can block the event loop.
        # Keep zero-delay bulk playback for standard bar mode only.
        use_bulk_playback = (
            bool(self._bulk_playback_enabled)
            and delay_seconds <= 0
            and not intrabar_quotes_required
        )
        logger.info(
            "Run playback config: eval_mode=%s intrabar_step=%ss bulk_enabled=%s bulk_active=%s intrabar_quotes_required=%s total_bars=%d",
            self._effective_trade_eval_mode(),
            self._intrabar_eval_step_seconds(),
            bool(self._bulk_playback_enabled),
            use_bulk_playback,
            intrabar_quotes_required,
            len(self.bars),
        )

        while self.is_running:
            if self.is_paused:
                await asyncio.sleep(0.05)
                continue

            if self.current_bar_index < len(self.bars):
                self._progressive_wait_started_at = None
                step_result: Dict[str, Any]
                if use_bulk_playback:
                    _, warmup_only = self._resolve_bar_runtime_context(
                        self.bars[self.current_bar_index]
                    )
                    step_result = (
                        await self.bulk_warmup()
                        if warmup_only
                        else await self.bulk_trade()
                    )
                else:
                    step_result = await self.step(notify=True)
                if not bool(step_result.get("success")):
                    self.phase = "ERROR"
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
        if self._intrabar_bars_observed > 0:
            avg_intrabar_points = self._intrabar_points_observed / max(
                1, self._intrabar_bars_observed
            )
            logger.info(
                "RUNNER_INTRABAR summary mode=%s step=%ss bars=%d avg_points=%.2f",
                self._effective_trade_eval_mode(),
                self._intrabar_eval_step_seconds(),
                self._intrabar_bars_observed,
                avg_intrabar_points,
            )
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
        return build_runner_state_payload(
            run_id=self.config.run_id,
            ticker=self.config.ticker,
            date=self.config.date,
            date_from=self.config.date_from,
            date_to=self.config.date_to,
            current_bar_index=self.current_bar_index,
            total_bars=len(self.bars),
            phase=self.phase,
            execution_lifecycle=self._execution_lifecycle.value,
            is_running=self.is_running,
            is_paused=self.is_paused,
            markers_count=len(self.decision_tracker.markers),
            selection_warnings=self._merged_selection_warnings(),
            l2_applied=(
                dict(self._l2_applied)
                if isinstance(self._l2_applied, dict) and self._l2_applied
                else {}
            ),
            progressive_loading_enabled=bool(self._progressive_loading_enabled),
            progressive_loading_complete=bool(self._progressive_loading_complete),
            progressive_loading_loaded_until=self._progressive_loading_loaded_until,
            progressive_loading_target_end=self._progressive_loading_target_end,
            progressive_loading_pending_chunks=int(self._progressive_loading_pending_chunks),
            progressive_loading_last_error=self._progressive_loading_last_error,
            apply_strategy_reset_metadata=self._apply_strategy_reset_metadata,
        )

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
        return build_summary_payload(
            run_id=self.config.run_id,
            ticker=self.config.ticker,
            date=self.config.date,
            total_bars=len(self.bars),
            processed_bars=self.current_bar_index,
            phase=self.phase,
            markers=self.decision_tracker.get_markers(),
            session_summary=summary,
            report_metadata=(
                dict(self._report_metadata)
                if isinstance(self._report_metadata, dict) and self._report_metadata
                else {}
            ),
            aos_applied=(
                dict(self._aos_applied)
                if isinstance(self._aos_applied, dict) and self._aos_applied
                else {}
            ),
            execution_config=(
                dict(self._execution_config)
                if isinstance(self._execution_config, dict) and self._execution_config
                else {}
            ),
            run_request_config=(
                dict(self._run_request_config)
                if isinstance(self._run_request_config, dict)
                and self._run_request_config
                else {}
            ),
            l2_applied=(
                dict(self._l2_applied)
                if isinstance(self._l2_applied, dict) and self._l2_applied
                else {}
            ),
            checkpoint_loaded=self._checkpoint_loaded,
            to_json_safe=self._to_json_safe,
            normalize_profile_token=_normalize_profile_token,
            apply_strategy_reset_metadata=self._apply_strategy_reset_metadata,
        )

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
        entry_timing_breakdown = (
            dict(overall.get("entry_timing_breakdown"))
            if isinstance(overall.get("entry_timing_breakdown"), dict)
            else self.perf_tracker.get_entry_timing_breakdown()
        )
        if entry_timing_breakdown:
            overall = {**overall, "entry_timing_breakdown": entry_timing_breakdown}
        return build_session_summary_payload(
            base_summary=base_summary,
            overall=overall,
            trades=self.perf_tracker.get_all_trades(),
            run_id=self.config.run_id,
            ticker=self.config.ticker,
            date=self.config.date,
            current_bar_index=self.current_bar_index,
            account_size_usd_default=self.config.account_size_usd,
            merged_selection_warnings=self._merged_selection_warnings(),
            data_selection_warnings=list(self._data_selection_warnings),
            last_response=self.last_response,
            normalize_selection_warnings=self._normalize_selection_warnings,
            merge_selection_warnings=self._merge_selection_warnings,
            apply_strategy_reset_metadata=self._apply_strategy_reset_metadata,
        )
