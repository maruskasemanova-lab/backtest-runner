import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.evidence_decision import EvidenceDecisionEngine  # noqa: E402
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


def _evaluate(engine: EvidenceDecisionEngine, confidence: float):
    return engine.evaluate(
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
        generate_signal_fn=lambda: _build_strategy_signal(confidence=confidence),
    )


def test_evidence_engine_accepts_high_confidence_strategy_signal() -> None:
    engine = EvidenceDecisionEngine(min_confirming_sources=1, base_threshold=58.0)
    # Warmup calibration applies a conservative confidence penalty.
    decision = _evaluate(engine, confidence=90.0)
    assert decision.execute is True
    assert not hasattr(decision, "patterns")
    assert not hasattr(decision, "pattern_score")
    assert not hasattr(decision, "pattern_confirmation")
    assert decision.signal is not None


def test_evidence_engine_rejects_low_confidence_strategy_signal() -> None:
    engine = EvidenceDecisionEngine(min_confirming_sources=1, base_threshold=68.0)
    decision = _evaluate(engine, confidence=60.0)
    assert decision.execute is False
    assert not hasattr(decision, "patterns")
    assert not hasattr(decision, "pattern_score")
    assert not hasattr(decision, "pattern_confirmation")
