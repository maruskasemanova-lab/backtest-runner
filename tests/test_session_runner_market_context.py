from __future__ import annotations

from datetime import datetime, timezone

from src.services.session_runner_market_context import MarketContextProvider


def _safe_float(value):
    if value is None:
        return None
    return float(value)


def test_market_context_provider_builds_recent_bars_lazily() -> None:
    bars = [
        {
            "timestamp": datetime(2026, 2, 6, 14, 30 + idx, tzinfo=timezone.utc),
            "open": 100.0 + idx,
            "high": 101.0 + idx,
            "low": 99.0 + idx,
            "close": 100.5 + idx,
            "volume": 1000 + idx * 100,
            "vwap": 100.25 + idx,
            "l2_signed_aggression": 0.1 * idx,
            "l2_imbalance": 0.2 * idx,
            "l2_book_pressure": 0.3 * idx,
        }
        for idx in range(6)
    ]

    provider = MarketContextProvider(bars=bars, safe_float=_safe_float)
    assert isinstance(provider._contexts[0], tuple)
    assert isinstance(provider._normalized_bars[0], tuple)
    assert not hasattr(provider, "_bars")
    context = provider.build_context(5)

    assert context["bar_index"] == 5
    assert context["total_bars"] == 6
    assert len(context["recent_bars"]) == 5
    assert context["recent_bars"][0]["timestamp"] == "2026-02-06T14:31:00+00:00"
    assert context["recent_bars"][-1]["close"] == 105.5
    assert context["bar_ohlcv"]["close"] == 105.5
    assert context["volume_context"]["avg_volume_5_bar"] is not None


def test_market_context_provider_returns_isolated_payloads_without_deepcopy() -> None:
    bars = [
        {
            "timestamp": datetime(2026, 2, 6, 14, 30 + idx, tzinfo=timezone.utc),
            "open": 100.0 + idx,
            "high": 101.0 + idx,
            "low": 99.0 + idx,
            "close": 100.5 + idx,
            "volume": 1000 + idx * 100,
            "vwap": 100.25 + idx,
        }
        for idx in range(3)
    ]

    provider = MarketContextProvider(bars=bars, safe_float=_safe_float)

    mutated = provider.build_context(2)
    mutated["bar_ohlcv"]["close"] = -1.0
    mutated["recent_bars"][0]["close"] = -2.0
    mutated["price_evolution"]["session_open_price"] = -3.0

    fresh = provider.build_context(2)

    assert fresh["bar_ohlcv"]["close"] == 102.5
    assert fresh["recent_bars"][0]["close"] == 100.5
    assert fresh["price_evolution"]["session_open_price"] == 100.5
