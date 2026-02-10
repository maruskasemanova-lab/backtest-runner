import wfo_optimizer


def test_param_grids_include_flow_strategy_families() -> None:
    grids = wfo_optimizer.PARAM_GRIDS
    assert "momentum_flow" in grids
    assert "absorption_reversal" in grids
    assert "exhaustion_fade" in grids
