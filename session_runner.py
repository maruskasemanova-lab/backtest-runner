"""
Session Runner - Orchestrates the connection between data source and strategy evaluator.
"""
import asyncio
import aiohttp
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import logging

from decision_tracker import DecisionTracker, MarkerType
from performance_tracker import PerformanceTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SessionRunner")


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
    
    def __init__(self, config: RunConfig):
        self.config = config
        self.decision_tracker = DecisionTracker(
            run_id=config.run_id,
            ticker=config.ticker,
            date=config.date
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
        # Optional run-level metadata injected by start_run service for reports.
        self._report_metadata: Dict[str, Any] = {}
        self._aos_applied: Dict[str, Any] = {}
        self._execution_config: Dict[str, Any] = {}
        self._session_end_marker_keys: Set[str] = set()
        self._position_active: bool = False
        self._pending_entry: bool = False

        # Cross-asset reference bars (e.g. QQQ), keyed by ISO timestamp
        self.ref_bars_map: Dict[str, Dict[str, Any]] = {}
        self.l2_manager: Optional[Any] = None
        self._intrabar_quote_cache: Dict[int, Optional[List[Dict[str, float]]]] = {}

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
        self._session_end_marker_keys.clear()
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
        self._session_end_marker_keys.clear()
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

    def _should_attach_intrabar_quotes(self, include_pending_entry: bool = False) -> bool:
        # In intrabar mode, strategies may depend on 1s quotes before the first entry.
        # Keep gating tied to mode+availability only (no execution-state gate).
        _ = include_pending_entry
        return bool(self.config.intrabar_execution_recalc_1s) and bool(self.l2_manager is not None)

    def _intrabar_eval_step_seconds(self) -> int:
        raw = getattr(self.config, "intrabar_eval_step_seconds", 1)
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            parsed = 1
        return max(1, min(60, parsed))

    def _apply_intrabar_eval_step(self, quotes: Optional[List[Dict[str, float]]]) -> Optional[List[Dict[str, float]]]:
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

    def _load_intrabar_quotes(self, timestamp: datetime) -> Optional[List[Dict[str, float]]]:
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
            logger.debug(f"Intrabar quote load failed for {self.config.ticker} @ {minute_start}: {exc}")
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
            return {
                "success": False,
                "error": "No more bars to process",
                "phase": "COMPLETED"
            }
        
        bar = self.bars[self.current_bar_index]
        result = await self._process_bar(bar)
        
        self.current_bar_index += 1
        self.last_response = result
        
        # Notify callbacks if requested
        if notify:
            await self._notify_bar({
                **bar,
                "bar_index": self.current_bar_index - 1
            })
        
        return result
    
    async def _process_bar(self, bar: Dict[str, Any]) -> Dict[str, Any]:
        """Send bar to strategy evaluator and process response."""
        timestamp = bar['timestamp']
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        # First bar - add session start marker
        if self.current_bar_index == 0:
            marker = self.decision_tracker.add_session_start(
                timestamp=timestamp,
                bar_index=0,
                price=bar['close']
            )
            await self._notify_decision(marker.to_dict())
        
        # Send to strategy API
        consume_pending_entry = self._pending_entry
        if consume_pending_entry:
            # Pending signal is consumed at this bar open (fill or reject).
            self._pending_entry = False
        payload = {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
            "open": bar['open'],
            "high": bar['high'],
            "low": bar['low'],
            "close": bar['close'],
            "volume": bar['volume'],
            "vwap": bar.get('vwap')
        }
        for l2_key in self.L2_PAYLOAD_KEYS:
            if l2_key in bar:
                payload[l2_key] = bar.get(l2_key)

        if self._should_attach_intrabar_quotes(include_pending_entry=consume_pending_entry):
            intrabar_quotes = self._load_intrabar_quotes(timestamp)
            if intrabar_quotes:
                payload["intrabar_quotes_1s"] = intrabar_quotes

        # Attach cross-asset reference bar if available
        ts_key = (timestamp.isoformat() if hasattr(timestamp, 'isoformat')
                  else str(timestamp))
        ref_bar = self.ref_bars_map.get(ts_key)
        if ref_bar:
            payload['ref_ticker'] = ref_bar.get('ticker', 'QQQ')
            payload['ref_open'] = ref_bar.get('open')
            payload['ref_high'] = ref_bar.get('high')
            payload['ref_low'] = ref_bar.get('low')
            payload['ref_close'] = ref_bar.get('close')
            payload['ref_volume'] = ref_bar.get('volume')

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.strategy_api_url}/api/session/bar",
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        if consume_pending_entry:
                            self._pending_entry = True
                        return {
                            "success": False,
                            "error": f"API error {resp.status}: {error_text}",
                            "bar_index": self.current_bar_index
                        }
                    
                    result = await resp.json()
        except aiohttp.ClientError as e:
            if consume_pending_entry:
                self._pending_entry = True
            return {
                "success": False,
                "error": f"Connection error: {str(e)}",
                "bar_index": self.current_bar_index
            }
        
        # Update phase
        self.phase = result.get('phase', self.phase)
        self._update_execution_state(result)
        
        # Process decision markers from response
        await self._process_decision_markers(result, bar, timestamp)
        
        return {
            "success": True,
            "bar_index": self.current_bar_index,
            "bar": bar,
            "phase": self.phase,
            "response": result,
            "total_bars": len(self.bars),
            "progress_pct": (self.current_bar_index + 1) / len(self.bars) * 100
        }
    
    async def _process_decision_markers(
        self, 
        response: Dict[str, Any], 
        bar: Dict[str, Any],
        timestamp: datetime
    ):
        """Extract and record decision markers from API response."""
        action = response.get('action', '')
        
        # Regime detected (allow one per day by relying on action flag)
        if action == 'regime_detected':
            regime = response.get('regime')
            if regime:
                explanation = self._generate_regime_explanation(response)
                marker = self.decision_tracker.add_regime_detected(
                    timestamp=timestamp,
                    bar_index=self.current_bar_index,
                    price=bar['close'],
                    regime=regime,
                    explanation=explanation,
                    indicators=response.get('indicators', {})
                )
                await self._notify_decision(marker.to_dict())

                # Also add strategy selected marker for this day
                strategy = self._extract_strategy_label(response)
                if strategy:
                    marker = self.decision_tracker.add_strategy_selected(
                        timestamp=timestamp,
                        bar_index=self.current_bar_index,
                        price=bar['close'],
                        strategy=strategy,
                        regime=regime,
                        reasoning=f"Selected {strategy} strategy for {regime} regime"
                    )
                    await self._notify_decision(marker.to_dict())

        # Intraday regime refresh (dynamic reclassification).
        regime_update = response.get('regime_update')
        if isinstance(regime_update, dict):
            regime = regime_update.get('regime') or response.get('regime')
            regime_indicators = regime_update.get('indicators') or response.get('indicators', {})
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
                    price=bar['close'],
                    regime=regime,
                    explanation=explanation,
                    indicators=regime_indicators
                )
                await self._notify_decision(marker.to_dict())

            strategy = (
                regime_update.get('strategy')
                or self._extract_strategy_label(response)
            )
            if strategy and regime:
                marker = self.decision_tracker.add_strategy_selected(
                    timestamp=timestamp,
                    bar_index=self.current_bar_index,
                    price=bar['close'],
                    strategy=strategy,
                    regime=regime,
                    reasoning=f"Updated {strategy} after intraday regime refresh"
                )
                await self._notify_decision(marker.to_dict())
        
        # Signals generated
        signals = response.get('signals', [])
        for signal in signals:
            marker = self.decision_tracker.add_signal(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=signal.get('price', bar['close']),
                signal_type=signal.get('signal', 'BUY'),
                strategy=signal.get('strategy', 'unknown'),
                confidence=signal.get('confidence', 50),
                reasoning=signal.get('reasoning', ''),
                stop_loss=signal.get('stop_loss'),
                take_profit=signal.get('take_profit')
            )
            await self._notify_decision(marker.to_dict())
        
        # Trades opened
        if 'position_opened' in response:
            pos = response['position_opened']
            # Get signal details if available
            signal_data = response.get('signal') or {}
            if not isinstance(signal_data, dict):
                signal_data = {}
            reasoning = pos.get('reasoning', signal_data.get('reasoning', ''))
            confidence = pos.get('confidence', signal_data.get('confidence', 50))
            metadata = pos.get('metadata', signal_data.get('metadata', {}))
            
            marker = self.decision_tracker.add_entry(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=pos.get('entry_price', bar['close']),
                side=pos.get('side', 'long'),
                strategy=pos.get('strategy', 'unknown'),
                size=pos.get('size', 1.0),
                stop_loss=pos.get('stop_loss', 0),
                take_profit=pos.get('take_profit', 0),
                reasoning=reasoning,
                confidence=confidence,
                metadata=metadata
            )
            # Attach regime for UI context if available
            marker.regime = response.get('regime') or marker.regime
            await self._notify_decision(marker.to_dict())
        
        # Trades closed
        if 'position_closed' in response:
            pos = response['position_closed']
            marker = self.decision_tracker.add_exit(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=pos.get('exit_price', bar['close']),
                side=pos.get('side', 'long'),
                reason=pos.get('exit_reason', 'unknown'),
                pnl_pct=pos.get('pnl_pct', 0),
                pnl_dollars=pos.get('pnl_dollars', 0),
                entry_price=pos.get('entry_price'),
                entry_time=pos.get('entry_time'),
                bars_held=pos.get('bars_held'),
                size=pos.get('size'),
                costs=pos.get('costs'),
                gross_pnl_pct=pos.get('gross_pnl_pct'),
                gross_pnl_dollars=(
                    pos.get('gross_pnl_dollars')
                    if pos.get('gross_pnl_dollars') is not None
                    else (
                        pos.get('gross_pnl_pct', 0) * pos.get('entry_price', 0) * pos.get('size', 1) / 100
                        if pos.get('gross_pnl_pct') is not None
                        else None
                    )
                ),
                cost_usd=pos.get('cost_usd'),
                cost_pct=pos.get('cost_pct'),
                pnl_usd=pos.get('pnl_usd'),
                position_notional_usd=pos.get('position_notional_usd'),
                schema_version=pos.get('schema_version', 1),
            )
            await self._notify_decision(marker.to_dict())

            # Record in Performance Tracker
            # Note: position_closed payload uses 'cost_usd', not 'total_costs'
            cost_usd = pos.get('cost_usd', 0.0) or 0.0
            # Fallback: extract from costs dict if cost_usd not present
            if cost_usd == 0.0 and 'costs' in pos:
                cost_usd = pos['costs'].get('total', 0.0) or 0.0
            
            self.perf_tracker.record_trade(
                strategy=pos.get('strategy', 'unknown'),
                regime=pos.get('regime', 'unknown'),
                ticker=self.config.ticker,
                date=self.config.date,
                side=pos.get('side', 'long'),
                entry_price=pos.get('entry_price', 0.0),
                exit_price=pos.get('exit_price', bar['close']),
                entry_time=pos.get('entry_time', ''),
                exit_time=timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                pnl_pct=pos.get('pnl_pct', 0.0),
                pnl_dollars=pos.get('pnl_dollars', 0.0),
                gross_pnl_pct=pos.get('gross_pnl_pct', 0.0),
                total_costs=cost_usd,
                exit_reason=pos.get('exit_reason', 'unknown'),
                bars_held=pos.get('bars_held', 0),
                flow_strategy=pos.get('flow_strategy', False),
                book_pressure_confirmed=pos.get('book_pressure_confirmed'),
                book_pressure_avg=pos.get('book_pressure_avg'),
                book_pressure_trend=pos.get('book_pressure_trend'),
                signed_aggression=pos.get('signed_aggression')
            )

        # Session ended
        if (
            response.get('phase') == 'END_OF_DAY'
            and isinstance(response.get('session_summary'), dict)
        ):
            self.session_summary = response['session_summary']
            marker_key = str(
                self.session_summary.get("date")
                or (timestamp.date().isoformat() if hasattr(timestamp, "date") else timestamp)
            )
            if marker_key not in self._session_end_marker_keys:
                marker = self.decision_tracker.add_session_end(
                    timestamp=timestamp,
                    bar_index=self.current_bar_index,
                    price=bar['close'],
                    summary=self.session_summary
                )
                self._session_end_marker_keys.add(marker_key)
                await self._notify_decision(marker.to_dict())

    @staticmethod
    def _extract_strategy_label(response: Dict[str, Any]) -> Optional[str]:
        """Resolve selected strategy from possible response keys."""
        return (
            response.get('strategy')
            or response.get('selected_strategy')
            or (response.get('strategies') or [None])[0]
        )
    
    def _generate_regime_explanation(self, response: Dict[str, Any]) -> str:
        """Generate human-readable explanation for regime detection."""
        regime = response.get('regime', 'UNKNOWN')
        micro_regime = response.get('micro_regime')
        indicators = response.get('indicators', {})

        def _as_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        trend_eff = _as_float(indicators.get('trend_efficiency'))
        volatility = _as_float(indicators.get('volatility'))
        adx = _as_float(indicators.get('adx'))

        if regime == 'TRENDING':
            if trend_eff is None:
                base = "Market showing directional movement (trend context unavailable)"
            elif trend_eff >= 0.45:
                base = "Market showing directional movement with elevated trend efficiency"
            elif trend_eff < 0.15:
                base = "Market tagged TRENDING, but measured trend efficiency is low (transition/noise risk)"
            else:
                base = "Market showing directional bias with moderate trend efficiency"
        elif regime == 'CHOPPY':
            base = "Market showing sideways/noisy movement with low directional efficiency"
        elif regime == 'MIXED':
            base = "Market showing mixed directional and mean-reverting behavior"
        else:
            base = f"Detected {regime} regime"

        if micro_regime and micro_regime != regime:
            base += f" (micro: {micro_regime})"

        # Highlight strong macro/micro disagreement.
        if regime == 'TRENDING' and micro_regime in {'CHOPPY', 'MIXED', 'TRANSITION'}:
            base += " [macro/micro divergence]"
        elif regime == 'CHOPPY' and micro_regime in {'TRENDING_UP', 'TRENDING_DOWN', 'BREAKOUT'}:
            base += " [macro/micro divergence]"
        elif micro_regime == 'TRANSITION':
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
            atr = _as_float(indicators.get('atr'))
            if atr is not None:
                details.append(f"ATR: {atr:.2f}")

            if details:
                base += f" ({', '.join(details)})"

        return base
    
    async def run_all(self, speed_ms = 100) -> Dict[str, Any]:
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
        logger.info(f"Starting run_all with normalized delay {delay_seconds:.4f}s per bar (raw={speed_ms})")

        while self.current_bar_index < len(self.bars) and self.is_running:
            if self.is_paused:
                await asyncio.sleep(0.05)
                continue

            await self.step(notify=True)

            # Yield to event loop; add delay when requested
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            else:
                await asyncio.sleep(0)  # cooperative yield, no throttle

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
    
    def get_state(self) -> Dict[str, Any]:
        """Get current runner state."""
        return {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "date": self.config.date,
            "date_from": self.config.date_from,
            "date_to": self.config.date_to,
            "current_bar_index": self.current_bar_index,
            "total_bars": len(self.bars),
            "progress_pct": (self.current_bar_index / len(self.bars) * 100) if self.bars else 0,
            "phase": self.phase,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "markers_count": len(self.decision_tracker.markers)
        }
    
    def get_markers(self) -> List[Dict[str, Any]]:
        """Get all decision markers."""
        return self.decision_tracker.get_markers()
    
    def get_chart_annotations(self) -> List[Dict[str, Any]]:
        """Get markers formatted for chart display."""
        return self.decision_tracker.get_chart_annotations()
    
    def get_processed_bars(self) -> List[Dict[str, Any]]:
        """Get all bars processed so far."""
        return self.bars[:self.current_bar_index]
    
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
            "session_summary": summary
        }
        if isinstance(self._report_metadata, dict) and self._report_metadata:
            payload["report_metadata"] = dict(self._report_metadata)
            adaptive_profile_id = str(self._report_metadata.get("adaptive_profile_id") or "").strip()
            adaptive_profile_name = str(self._report_metadata.get("adaptive_profile_name") or "").strip()
            if adaptive_profile_id:
                payload["adaptive_profile_id"] = adaptive_profile_id
            if adaptive_profile_name:
                payload["adaptive_profile_name"] = adaptive_profile_name
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
        base_summary = dict(self.session_summary) if isinstance(self.session_summary, dict) else {}
        overall = self.perf_tracker.get_overall_stats()
        total_trades = int(overall.get("total_trades", 0) or 0)
        if total_trades <= 0:
            if base_summary:
                base_summary.setdefault("run_id", self.config.run_id)
                base_summary.setdefault("ticker", self.config.ticker)
                base_summary.setdefault("date", self.config.date)
                base_summary["bars_processed"] = self.current_bar_index
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
        profit_factor_dollars = (gross_wins / gross_losses) if gross_losses > 0 else float("inf")

        running = 0.0
        peak = 0.0
        max_drawdown_dollars = 0.0
        for pnl in pnl_dollar_values:
            running += pnl
            peak = max(peak, running)
            max_drawdown_dollars = max(max_drawdown_dollars, peak - running)

        merged = {
            "ticker": self.config.ticker,
            "date": self.config.date,
            "run_id": self.config.run_id,
            "regime": base_summary.get("regime") or (self.last_response or {}).get("regime"),
            "micro_regime": base_summary.get("micro_regime") or (self.last_response or {}).get("micro_regime"),
            "strategy": base_summary.get("strategy") or (self.last_response or {}).get("strategy"),
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
                "inf" if profit_factor_dollars == float("inf") else round(profit_factor_dollars, 4)
            ),
            "max_drawdown_dollars": round(max_drawdown_dollars, 4),
            "bars_processed": self.current_bar_index,
            "pre_market_bars": base_summary.get("pre_market_bars", 0),
            "regime_history": list(base_summary.get("regime_history", [])),
            "success": total_pnl_dollars > 0.0,
        }
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
        with open(summary_path, 'w') as f:
            json.dump(self.get_summary(), f, indent=2, default=str)
        logger.info(f"Saved session summary to {summary_path}")
