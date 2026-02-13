from src.models.run_requests import StartRunRequest
from src.services.start_run_execution_config_service import resolve_execution_config


def test_resolve_execution_config_emits_trading_config_payload() -> None:
    request = StartRunRequest(
        run_id="cfg-1",
        ticker="NVDA",
        date="2026-02-10",
        risk_per_trade_pct=-3.0,
        max_fill_participation_rate=9.0,
        min_fill_ratio=-5.0,
        time_exit_bars=0,
        stop_loss_mode="invalid",
        strategy_selection_mode="all_enabled",
        max_active_strategies=99,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["risk_per_trade_pct"] == 0.1
    assert trading_config["max_fill_participation_rate"] == 1.0
    assert trading_config["min_fill_ratio"] == 0.01
    assert trading_config["time_exit_bars"] == 1
    assert trading_config["stop_loss_mode"] == "strategy"
    assert trading_config["strategy_selection_mode"] == "all_enabled"
    assert trading_config["max_active_strategies"] == 20


def test_resolve_execution_config_trading_config_respects_profile_overrides() -> None:
    request = StartRunRequest(
        run_id="cfg-2",
        ticker="MU",
        date="2026-02-10",
        strategy_selection_mode="adaptive_top_n",
        max_active_strategies=3,
        l2_confirm_enabled=False,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={"l2": {"confirm_enabled": True}},
        adaptive_profile_runtime={
            "strategy_selection_mode": "all_enabled",
            "max_active_strategies": 9,
            "l2_min_delta": 123.0,
        },
    )

    trading_config = result["trading_config"]
    assert trading_config["strategy_selection_mode"] == "all_enabled"
    assert trading_config["max_active_strategies"] == 9
    assert trading_config["l2_min_delta"] == 123.0
    assert trading_config["l2_confirm_enabled"] is True
