import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.evidence_decision import EvidenceDecisionEngine  # noqa: E402
from src.feature_store import FeatureVector  # noqa: E402
from src.strategies.base_strategy import Regime, Signal, SignalType  # noqa: E402


def _sample_ohlcv() -> dict:
    return {
        "open": [100.0, 100.2, 100.1],
        "high": [100.3, 100.4, 100.5],
        "low": [99.8, 99.9, 99.95],
        "close": [100.2, 100.1, 100.3],
        "volume": [1000.0, 1100.0, 1200.0],
    }


def test_evidence_engine_never_uses_candlestick_fallback_signal() -> None:
    engine = EvidenceDecisionEngine(min_confirming_sources=1, base_threshold=1.0)

    signal = Signal(
        strategy_name="MomentumFlow",
        signal_type=SignalType.BUY,
        price=100.3,
        timestamp=datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc),
        confidence=78.0,
        stop_loss=99.8,
        take_profit=101.6,
        trailing_stop=False,
        reasoning="unit-test",
        metadata={"patterns": [{"name": "Evening Star"}]},
    )

    decision = engine.evaluate(
        ohlcv=_sample_ohlcv(),
        indicators={},
        regime=Regime.TRENDING,
        strategies={},
        active_strategy_names=[],
        current_price=100.3,
        timestamp=datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc),
        ticker="MU",
        generate_signal_fn=lambda: signal,
    )

    assert decision.execute is True
    assert decision.signal is not None
    assert decision.signal.strategy_name == "MomentumFlow"
    assert not hasattr(decision, "patterns")
    assert not hasattr(decision, "pattern_score")
    assert not hasattr(decision, "pattern_confirmation")
    assert not hasattr(decision, "primary_pattern")
    assert "patterns" not in (decision.signal.metadata or {})


def test_evidence_engine_requires_strategy_signal_for_execution() -> None:
    engine = EvidenceDecisionEngine(min_confirming_sources=1, base_threshold=1.0)
    fv = FeatureVector(
        l2_has_coverage=True,
        l2_signed_aggression=0.25,
        l2_aggression_z=2.0,
        l2_delta_price_divergence=0.9,
    )

    decision = engine.evaluate(
        ohlcv=_sample_ohlcv(),
        indicators={},
        regime=Regime.TRENDING,
        strategies={},
        active_strategy_names=[],
        current_price=100.3,
        timestamp=datetime(2026, 2, 3, 15, 0, tzinfo=timezone.utc),
        ticker="MU",
        generate_signal_fn=lambda: None,
        feature_vector=fv,
    )

    assert decision.signal is None
    assert decision.execute is False
    assert "no aligned strategy signal" in decision.reasoning
