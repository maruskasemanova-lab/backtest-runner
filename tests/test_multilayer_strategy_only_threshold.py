import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config_io import extract_multilayer_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.multi_layer_decision import MultiLayerDecision  # noqa: E402
from src.strategies.base_strategy import Regime, Signal, SignalType  # noqa: E402


def _build_strategy_signal(confidence: float) -> Signal:
    return Signal(
        strategy_name="MomentumFlow",
        signal_type=SignalType.BUY,
        price=100.0,
        timestamp=datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc),
        confidence=confidence,
        stop_loss=99.0,
        take_profit=102.0,
        trailing_stop=False,
        reasoning="unit-test",
    )


def test_extract_multilayer_payload_keeps_strategy_only_threshold() -> None:
    payload = extract_multilayer_payload(
        {
            "multilayer": {
                "pattern_weight": 0.4,
                "strategy_weight": 0.6,
                "threshold": 58,
                "strategy_only_threshold": 68,
                "require_pattern": False,
            }
        }
    )
    assert payload["strategy_only_threshold"] == 68.0


def test_strategy_only_threshold_blocks_borderline_signal_without_pattern() -> None:
    ml = MultiLayerDecision(
        pattern_weight=0.45,
        strategy_weight=0.55,
        threshold=58.0,
        strategy_only_threshold=68.0,
        require_pattern=False,
    )
    ml.pattern_detector.detect = lambda ohlcv, indicators=None: []

    decision = ml.evaluate(
        ohlcv={
            "open": [100.0, 100.2, 100.1],
            "high": [100.3, 100.4, 100.5],
            "low": [99.8, 99.9, 99.95],
            "close": [100.2, 100.1, 100.3],
            "volume": [1000.0, 1100.0, 1200.0],
        },
        indicators={},
        regime=Regime.MIXED,
        strategies={},
        active_strategy_names=[],
        current_price=100.3,
        timestamp=datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc),
        generate_signal_fn=lambda: _build_strategy_signal(confidence=60.0),
    )

    assert decision.threshold == 68.0
    assert decision.pattern_threshold == 58.0
    assert decision.trade_gate_threshold == 68.0
    assert decision.threshold_used_reason == "no_pattern_confirmation"
    assert decision.combined_raw == decision.combined_score
    assert decision.combined_norm_0_100 is not None
    assert decision.execute is False


def test_strategy_only_threshold_disabled_falls_back_to_base_threshold() -> None:
    ml = MultiLayerDecision(
        pattern_weight=0.45,
        strategy_weight=0.55,
        threshold=58.0,
        strategy_only_threshold=0.0,
        require_pattern=False,
    )
    ml.pattern_detector.detect = lambda ohlcv, indicators=None: []

    decision = ml.evaluate(
        ohlcv={
            "open": [100.0, 100.2, 100.1],
            "high": [100.3, 100.4, 100.5],
            "low": [99.8, 99.9, 99.95],
            "close": [100.2, 100.1, 100.3],
            "volume": [1000.0, 1100.0, 1200.0],
        },
        indicators={},
        regime=Regime.MIXED,
        strategies={},
        active_strategy_names=[],
        current_price=100.3,
        timestamp=datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc),
        generate_signal_fn=lambda: _build_strategy_signal(confidence=60.0),
    )

    assert decision.threshold == 58.0
    assert decision.pattern_threshold == 58.0
    assert decision.trade_gate_threshold == 58.0
    assert decision.threshold_used_reason == "base_threshold"
    assert decision.combined_norm_0_100 is not None
    assert decision.execute is True
