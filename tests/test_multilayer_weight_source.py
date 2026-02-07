import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ROOT = PROJECT_ROOT.parent / "market_regime_detection"
sys.path.insert(0, str(STRATEGY_ROOT))
sys.modules.pop("src", None)

from src.day_trading_manager import DayTradingManager  # noqa: E402


def test_effective_strategy_weight_resets_without_l2_coverage() -> None:
    manager = DayTradingManager(regime_detection_minutes=0)
    session = manager.get_or_create_session("weight-test", "MU", "2026-02-03", 0)
    ml = session.multi_layer
    assert ml is not None

    session.multilayer_base_pattern_weight = 0.45
    session.multilayer_base_strategy_weight = 0.55

    l2_weights = manager._resolve_multilayer_weights(
        session=session,
        ml_engine=ml,
        flow_metrics={"has_l2_coverage": True, "bars_with_l2": 8, "lookback_bars": 10},
    )
    assert l2_weights["strategy_weight"] == 1.0
    assert l2_weights["strategy_weight_source"] == "l2"

    no_l2_weights = manager._resolve_multilayer_weights(
        session=session,
        ml_engine=ml,
        flow_metrics={"has_l2_coverage": False, "bars_with_l2": 0, "lookback_bars": 10},
    )
    assert no_l2_weights["strategy_weight"] == 0.55
    assert no_l2_weights["strategy_weight_source"] == "fallback"

