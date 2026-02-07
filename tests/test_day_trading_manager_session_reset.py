import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.day_trading_manager import DayTradingManager  # noqa: E402


def test_clear_session_removes_cooldown_state() -> None:
    manager = DayTradingManager(regime_detection_minutes=5)
    session = manager.get_or_create_session("run-a", "MU", "2026-02-03")
    key = manager._get_session_key("run-a", "MU", "2026-02-03")

    assert session is not None
    manager.last_trade_bar_index[key] = 120

    assert manager.clear_session("run-a", "MU", "2026-02-03") is True
    assert key not in manager.sessions
    assert key not in manager.last_trade_bar_index


def test_clear_sessions_for_run_removes_sessions_and_defaults() -> None:
    manager = DayTradingManager(regime_detection_minutes=5)
    manager.get_or_create_session("run-a", "MU", "2026-02-03")
    manager.get_or_create_session("run-a", "MU", "2026-02-04")
    manager.get_or_create_session("run-b", "MU", "2026-02-03")

    key_a1 = manager._get_session_key("run-a", "MU", "2026-02-03")
    key_a2 = manager._get_session_key("run-a", "MU", "2026-02-04")
    key_b1 = manager._get_session_key("run-b", "MU", "2026-02-03")
    manager.last_trade_bar_index[key_a1] = 100
    manager.last_trade_bar_index[key_a2] = 200
    manager.last_trade_bar_index[key_b1] = 300

    manager.set_run_defaults("run-a", "MU", risk_per_trade_pct=1.5)
    manager.set_run_defaults("run-b", "MU", risk_per_trade_pct=2.0)

    removed = manager.clear_sessions_for_run("run-a", "MU")

    assert removed == 2
    assert key_a1 not in manager.sessions
    assert key_a2 not in manager.sessions
    assert key_b1 in manager.sessions
    assert key_a1 not in manager.last_trade_bar_index
    assert key_a2 not in manager.last_trade_bar_index
    assert key_b1 in manager.last_trade_bar_index
    assert ("run-a", "MU") not in manager.run_defaults
    assert ("run-b", "MU") in manager.run_defaults


def test_get_or_create_session_clears_stale_trade_index_for_replay() -> None:
    manager = DayTradingManager(regime_detection_minutes=5)
    key = manager._get_session_key("run-a", "MU", "2026-02-03")
    manager.last_trade_bar_index[key] = 999

    manager.get_or_create_session("run-a", "MU", "2026-02-03")

    assert key in manager.sessions
    assert key not in manager.last_trade_bar_index
