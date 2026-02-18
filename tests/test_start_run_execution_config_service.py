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


def test_resolve_execution_config_trading_config_prefers_request_overrides() -> None:
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
    assert trading_config["strategy_selection_mode"] == "adaptive_top_n"
    assert trading_config["max_active_strategies"] == 3
    assert trading_config["l2_min_delta"] == 123.0
    assert trading_config["l2_confirm_enabled"] is True


def test_resolve_execution_config_includes_effective_global_trailing_stop_pct() -> None:
    request = StartRunRequest(
        run_id="cfg-3",
        ticker="MU",
        date="2026-02-10",
        trailing_stop_pct=0.0,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={"positioning": {"trailing_stop_pct": 0.75}},
        adaptive_profile_runtime={"trailing_stop_pct": 0.63},
    )

    assert result["effective_trailing_stop_pct"] == 0.63
    assert result["trailing_stop_pct_source"] == "adaptive_profile"


def test_resolve_execution_config_includes_global_exit_and_risk_module_defaults() -> None:
    request = StartRunRequest(
        run_id="cfg-4",
        ticker="MU",
        date="2026-02-10",
        global_exit_rr_ratio=0.0,
        global_risk_atr_stop_multiplier=0.0,
        global_risk_volume_stop_pct=0.0,
        global_risk_min_stop_loss_pct=0.0,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={
            "positioning": {
                "global_exit_rr_ratio": 1.8,
                "global_risk_atr_stop_multiplier": 0.9,
                "global_risk_volume_stop_pct": 1.25,
                "global_risk_min_stop_loss_pct": 0.08,
            }
        },
        adaptive_profile_runtime={"global_exit_rr_ratio": 1.65},
    )

    assert result["effective_global_exit_rr_ratio"] == 1.65
    assert result["global_exit_rr_ratio_source"] == "adaptive_profile"
    assert result["effective_global_risk_atr_stop_multiplier"] == 0.9
    assert result["global_risk_atr_stop_multiplier_source"] == "positioning_config"
    assert result["effective_global_risk_volume_stop_pct"] == 1.25
    assert result["global_risk_volume_stop_pct_source"] == "positioning_config"
    assert result["effective_global_risk_min_stop_loss_pct"] == 0.08
    assert result["global_risk_min_stop_loss_pct_source"] == "positioning_config"


def test_resolve_execution_config_includes_profile_runtime_trade_cap_and_mu_choppy_flag() -> None:
    request = StartRunRequest(
        run_id="cfg-5",
        ticker="MU",
        date="2026-02-10",
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={
            "max_daily_trades": 0,
            "mu_choppy_hard_block_enabled": False,
        },
    )

    trading_config = result["trading_config"]
    assert trading_config["max_daily_trades"] == 0
    assert trading_config["mu_choppy_hard_block_enabled"] is False
    assert result["effective_max_daily_trades"] == 0
    assert result["max_daily_trades_source"] == "adaptive_profile"
    assert result["effective_mu_choppy_hard_block_enabled"] is False
    assert result["mu_choppy_hard_block_enabled_source"] == "adaptive_profile"
