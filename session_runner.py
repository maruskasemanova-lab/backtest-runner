"""
Session Runner - Orchestrates the connection between data source and strategy evaluator.
"""
import asyncio
import aiohttp
from datetime import datetime, time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging

from decision_tracker import DecisionTracker, MarkerType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SessionRunner")


@dataclass
class RunConfig:
    """Configuration for a backtest run."""
    run_id: str
    ticker: str
    date: str
    strategy_api_url: str = "http://localhost:8001"
    regime_detection_minutes: int = 15
    auto_close_eod: bool = True
    eod_close_time: time = field(default_factory=lambda: time(15, 55))


class SessionRunner:
    """Runs a trading session by feeding bars to the strategy evaluator."""
    
    def __init__(self, config: RunConfig):
        self.config = config
        self.tracker = DecisionTracker(
            run_id=config.run_id,
            ticker=config.ticker,
            date=config.date
        )
        
        # State
        self.current_bar_index = 0
        self.bars: List[Dict[str, Any]] = []
        self.is_running = False
        self.is_paused = False
        self.phase = "INITIALIZED"
        self.last_response: Optional[Dict[str, Any]] = None
        self.session_summary: Optional[Dict[str, Any]] = None
        
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
        logger.info(f"Loaded {len(bars)} bars for session")
    
    async def step(self) -> Dict[str, Any]:
        """Process the next bar and return the result."""
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
        
        # Notify callbacks
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
            marker = self.tracker.add_session_start(
                timestamp=timestamp,
                bar_index=0,
                price=bar['close']
            )
            await self._notify_decision(marker.to_dict())
        
        # Send to strategy API
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
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.config.strategy_api_url}/api/session/bar",
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return {
                            "success": False,
                            "error": f"API error {resp.status}: {error_text}",
                            "bar_index": self.current_bar_index
                        }
                    
                    result = await resp.json()
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "error": f"Connection error: {str(e)}",
                "bar_index": self.current_bar_index
            }
        
        # Update phase
        self.phase = result.get('phase', self.phase)
        
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
        
        # Regime detected
        if action == 'regime_detected' or 'regime' in response:
            regime = response.get('regime')
            if regime and self.phase == 'TRADING':
                # Only add marker once when transitioning to TRADING
                existing = [m for m in self.tracker.markers 
                           if m.marker_type == MarkerType.REGIME_DETECTED]
                if not existing:
                    explanation = self._generate_regime_explanation(response)
                    marker = self.tracker.add_regime_detected(
                        timestamp=timestamp,
                        bar_index=self.current_bar_index,
                        price=bar['close'],
                        regime=regime,
                        explanation=explanation,
                        indicators=response.get('indicators', {})
                    )
                    await self._notify_decision(marker.to_dict())
                    
                    # Also add strategy selected marker
                    strategy = response.get('strategy')
                    if strategy:
                        marker = self.tracker.add_strategy_selected(
                            timestamp=timestamp,
                            bar_index=self.current_bar_index,
                            price=bar['close'],
                            strategy=strategy,
                            regime=regime,
                            reasoning=f"Selected {strategy} strategy for {regime} regime"
                        )
                        await self._notify_decision(marker.to_dict())
        
        # Signals generated
        signals = response.get('signals', [])
        for signal in signals:
            marker = self.tracker.add_signal(
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
            marker = self.tracker.add_entry(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=pos.get('entry_price', bar['close']),
                side=pos.get('side', 'long'),
                strategy=pos.get('strategy', 'unknown'),
                size=pos.get('size', 1.0),
                stop_loss=pos.get('stop_loss', 0),
                take_profit=pos.get('take_profit', 0)
            )
            await self._notify_decision(marker.to_dict())
        
        # Trades closed
        if 'position_closed' in response:
            pos = response['position_closed']
            marker = self.tracker.add_exit(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=pos.get('exit_price', bar['close']),
                side=pos.get('side', 'long'),
                reason=pos.get('exit_reason', 'unknown'),
                pnl_pct=pos.get('pnl_pct', 0),
                pnl_dollars=pos.get('pnl_dollars', 0)
            )
            await self._notify_decision(marker.to_dict())
        
        # Session ended
        if response.get('phase') == 'END_OF_DAY' and 'session_summary' in response:
            self.session_summary = response['session_summary']
            marker = self.tracker.add_session_end(
                timestamp=timestamp,
                bar_index=self.current_bar_index,
                price=bar['close'],
                summary=self.session_summary
            )
            await self._notify_decision(marker.to_dict())
    
    def _generate_regime_explanation(self, response: Dict[str, Any]) -> str:
        """Generate human-readable explanation for regime detection."""
        regime = response.get('regime', 'UNKNOWN')
        indicators = response.get('indicators', {})
        
        explanations = {
            'TRENDING': "Market showing strong directional movement with high trend efficiency",
            'CHOPPY': "Market showing sideways movement with low trend efficiency and high volatility",
            'MIXED': "Market showing mixed signals - moderate trend with variable volatility"
        }
        
        base = explanations.get(regime, f"Detected {regime} regime")
        
        if indicators:
            details = []
            if 'trend_efficiency' in indicators:
                details.append(f"Trend Efficiency: {indicators['trend_efficiency']:.2f}")
            if 'volatility' in indicators:
                details.append(f"Volatility: {indicators['volatility']:.2f}%")
            if 'atr' in indicators:
                details.append(f"ATR: {indicators['atr']:.2f}")
            
            if details:
                base += f" ({', '.join(details)})"
        
        return base
    
    async def run_all(self, speed_ms: int = 100) -> Dict[str, Any]:
        """Run through all bars with specified delay."""
        self.is_running = True
        self.is_paused = False
        
        while self.current_bar_index < len(self.bars) and self.is_running:
            if self.is_paused:
                await asyncio.sleep(0.1)
                continue
            
            await self.step()
            
            if speed_ms > 0:
                await asyncio.sleep(speed_ms / 1000)
        
        self.is_running = False
        
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
            "current_bar_index": self.current_bar_index,
            "total_bars": len(self.bars),
            "progress_pct": (self.current_bar_index / len(self.bars) * 100) if self.bars else 0,
            "phase": self.phase,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "markers_count": len(self.tracker.markers)
        }
    
    def get_markers(self) -> List[Dict[str, Any]]:
        """Get all decision markers."""
        return self.tracker.get_markers()
    
    def get_chart_annotations(self) -> List[Dict[str, Any]]:
        """Get markers formatted for chart display."""
        return self.tracker.get_chart_annotations()
    
    def get_processed_bars(self) -> List[Dict[str, Any]]:
        """Get all bars processed so far."""
        return self.bars[:self.current_bar_index]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get session summary."""
        return {
            "run_id": self.config.run_id,
            "ticker": self.config.ticker,
            "date": self.config.date,
            "total_bars": len(self.bars),
            "processed_bars": self.current_bar_index,
            "phase": self.phase,
            "markers": self.tracker.get_markers(),
            "session_summary": self.session_summary
        }
