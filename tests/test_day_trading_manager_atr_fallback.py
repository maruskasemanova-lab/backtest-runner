import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.day_trading_manager import BarData, DayTradingManager  # noqa: E402


def test_atr_is_available_for_short_windows() -> None:
    manager = DayTradingManager(regime_detection_minutes=0)
    start = datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)

    bars = []
    price = 100.0
    for i in range(6):
        price += 0.25
        bars.append(
            BarData(
                timestamp=start + timedelta(minutes=i),
                open=price - 0.10,
                high=price + 0.30,
                low=price - 0.35,
                close=price,
                volume=10_000.0 + i * 100.0,
                vwap=price - 0.02,
            )
        )

    indicators = manager._calculate_indicators(bars)

    assert "atr" in indicators
    assert len(indicators["atr"]) == len(bars)
    assert indicators["atr"][-1] > 0
    assert manager._latest_indicator_value({}, "atr", bars) > 0
