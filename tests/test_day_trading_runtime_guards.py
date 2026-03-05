from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.day_trading_manager import (
    BarData,
    DayTradingManager,
    SessionPhase,
)  # noqa: E402
from src.strategies.base_strategy import Signal, SignalType  # noqa: E402


def _bar(ts: datetime, close: float = 100.0) -> BarData:
    return BarData(
        timestamp=ts,
        open=close,
        high=close + 0.2,
        low=close - 0.2,
        close=close,
        volume=50_000.0,
        vwap=close,
    )


def _signal(ts: datetime, confidence: float = 85.0) -> Signal:
    return Signal(
        strategy_name="MomentumFlow",
        signal_type=SignalType.BUY,
        price=100.0,
        timestamp=ts,
        confidence=confidence,
        stop_loss=99.0,
        take_profit=103.0,
        trailing_stop=False,
        reasoning="unit-test",
    )


def test_pending_signal_ttl_drops_stale_signal() -> None:
    manager = DayTradingManager(
        regime_detection_minutes=0,
        max_trades_per_day=10,
        trade_cooldown_bars=0,
        pending_signal_ttl_bars=2,
    )
    session = manager.get_or_create_session("run", "MU", "2026-02-03")
    session.phase = SessionPhase.TRADING
    session.selected_strategy = None

    start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
    session.pending_signal = _signal(start)
    session.pending_signal_bar_index = 0
    session.bars = [_bar(start + timedelta(minutes=i)) for i in range(4)]

    result = manager._process_trading_bar(
        session, session.bars[-1], session.bars[-1].timestamp
    )

    assert result.get("stale_pending_signal_dropped") is True
    assert session.pending_signal is None
    assert session.active_position is None


def test_daily_loss_limit_counts_unrealized_pnl() -> None:
    manager = DayTradingManager(
        regime_detection_minutes=0,
        max_daily_loss=100.0,
        max_trades_per_day=10,
        trade_cooldown_bars=0,
        portfolio_drawdown_halt_pct=0.0,
    )
    session = manager.get_or_create_session("run", "MU", "2026-02-03")
    session.phase = SessionPhase.TRADING
    session.selected_strategy = None

    ts = datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc)
    loss_signal = _signal(ts)
    loss_signal.stop_loss = 0.0
    manager._open_position(
        session=session,
        signal=loss_signal,
        entry_price=100.0,
        entry_time=ts,
        signal_bar_index=0,
        entry_bar_index=0,
        entry_bar_volume=200_000.0,
    )
    assert session.active_position is not None

    down_bar = _bar(ts + timedelta(minutes=1), close=80.0)
    session.bars.append(down_bar)
    result = manager._process_trading_bar(session, down_bar, down_bar.timestamp)

    assert result.get("action") == "max_loss_stop"
    assert (
        result.get("max_daily_loss_trigger", {}).get("total_pnl_dollars", 0.0) < -100.0
    )
    assert session.phase == SessionPhase.END_OF_DAY


def test_consecutive_losses_do_not_trigger_bar_cooldown() -> None:
    manager = DayTradingManager(
        regime_detection_minutes=0,
        max_trades_per_day=10,
        trade_cooldown_bars=0,
        consecutive_loss_limit=2,
        consecutive_loss_cooldown_bars=5,
    )
    session = manager.get_or_create_session("run", "MU", "2026-02-03")
    session.phase = SessionPhase.TRADING
    session.selected_strategy = "momentum_flow"

    start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)
    for idx in range(2):
        ts = start + timedelta(minutes=idx)
        signal = _signal(ts)
        manager._open_position(
            session=session,
            signal=signal,
            entry_price=100.0,
            entry_time=ts,
            signal_bar_index=idx,
            entry_bar_index=idx,
            entry_bar_volume=200_000.0,
        )
        session.bars.append(_bar(ts, close=100.0))
        manager._close_position(
            session=session,
            exit_price=99.0,
            exit_time=ts,
            reason="unit_test_loss",
            bar_volume=200_000.0,
        )

    assert session.consecutive_losses == 2
    assert session.loss_cooldown_until_bar_index == -1

    probe_bar = _bar(start + timedelta(minutes=3), close=99.5)
    session.bars.append(probe_bar)
    result = manager._process_trading_bar(session, probe_bar, probe_bar.timestamp)

    assert result.get("action") != "consecutive_loss_cooldown"
    assert result.get("cooldown_bars_remaining") in (None, 0)


def test_daily_trade_limit_no_longer_blocks_entries() -> None:
    manager = DayTradingManager(
        regime_detection_minutes=0,
        max_trades_per_day=1,
        trade_cooldown_bars=0,
    )
    session = manager.get_or_create_session("run", "MU", "2026-02-03")
    session.phase = SessionPhase.TRADING
    session.selected_strategy = "momentum_flow"
    session.micro_regime = "TRENDING_UP"

    start = datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc)
    signal = _signal(start)
    manager._open_position(
        session=session,
        signal=signal,
        entry_price=100.0,
        entry_time=start,
        signal_bar_index=0,
        entry_bar_index=0,
        entry_bar_volume=200_000.0,
    )
    session.bars.append(_bar(start, close=100.0))
    manager._close_position(
        session=session,
        exit_price=101.0,
        exit_time=start,
        reason="unit_test_trade_cap_removed",
        bar_volume=200_000.0,
    )
    assert len(session.trades) == 1

    probe_bar = _bar(start + timedelta(minutes=1), close=100.5)
    session.bars.append(probe_bar)
    result = manager._process_trading_bar(session, probe_bar, probe_bar.timestamp)

    assert result.get("action") != "trade_limit_reached"
    assert "Max trades per day" not in str(result.get("reason", ""))


def test_unknown_micro_regime_blocks_new_signals() -> None:
    manager = DayTradingManager(
        regime_detection_minutes=0,
        max_trades_per_day=10,
        trade_cooldown_bars=0,
    )
    session = manager.get_or_create_session("run", "MU", "2026-02-03")
    session.phase = SessionPhase.TRADING
    session.micro_regime = "UNKNOWN"
    session.selected_strategy = "momentum_flow"

    ts = datetime(2026, 2, 3, 15, 10, tzinfo=timezone.utc)
    bar = _bar(ts)
    session.bars.append(bar)

    result = manager._process_trading_bar(session, bar, ts)

    assert result.get("action") == "regime_warmup"


def test_portfolio_drawdown_halt_closes_position_and_ends_session() -> None:
    manager = DayTradingManager(
        regime_detection_minutes=0,
        max_trades_per_day=10,
        trade_cooldown_bars=0,
        portfolio_drawdown_halt_pct=1.0,
    )
    session = manager.get_or_create_session("run", "MU", "2026-02-03")
    session.phase = SessionPhase.TRADING
    session.selected_strategy = None

    ts = datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc)
    signal = _signal(ts)
    signal.stop_loss = 0.0
    manager._open_position(
        session=session,
        signal=signal,
        entry_price=100.0,
        entry_time=ts,
        signal_bar_index=0,
        entry_bar_index=0,
        entry_bar_volume=200_000.0,
    )
    assert session.active_position is not None

    down_bar = _bar(ts + timedelta(minutes=1), close=90.0)
    session.bars.append(down_bar)
    result = manager._process_trading_bar(session, down_bar, down_bar.timestamp)

    assert result.get("action") == "portfolio_drawdown_halt"
    assert result.get("portfolio_drawdown", {}).get("halted") is True
    assert session.phase == SessionPhase.END_OF_DAY
