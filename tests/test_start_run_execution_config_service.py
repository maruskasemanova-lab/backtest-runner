import pytest

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


def test_resolve_execution_config_prefers_profile_regime_cadence_over_runtime_request() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-2b",
        ticker="MU",
        date="2026-02-10",
        regime_detection_minutes=19,
        regime_refresh_bars=9,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={
            "regime_detection_minutes": 23,
            "regime_refresh_bars": 11,
        },
        adaptive_profile_runtime={
            "regime_detection_minutes": 31,
            "regime_refresh_bars": 5,
        },
    )

    trading_config = result["trading_config"]
    assert trading_config["regime_detection_minutes"] == 31
    assert trading_config["regime_refresh_bars"] == 5
    assert result["effective_regime_detection_minutes"] == 31
    assert result["regime_detection_minutes_source"] == "adaptive_profile"
    assert result["effective_regime_refresh_bars"] == 5
    assert result["regime_refresh_bars_source"] == "adaptive_profile"


def test_resolve_execution_config_uses_aos_regime_cadence_when_profile_missing() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-2c",
        ticker="MU",
        date="2026-02-10",
        regime_detection_minutes=41,
        regime_refresh_bars=17,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={
            "regime_detection_minutes": 27,
            "regime_refresh_bars": 8,
        },
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["regime_detection_minutes"] == 27
    assert trading_config["regime_refresh_bars"] == 8
    assert result["regime_detection_minutes_source"] == "aos_applied"
    assert result["regime_refresh_bars_source"] == "aos_applied"


def test_resolve_execution_config_uses_default_regime_cadence_when_not_explicitly_set() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-2d",
        ticker="MU",
        date="2026-02-10",
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["regime_detection_minutes"] == 15
    assert trading_config["regime_refresh_bars"] == 12
    assert result["regime_detection_minutes_source"] == "default"
    assert result["regime_refresh_bars_source"] == "default"


def test_resolve_execution_config_keeps_explicit_request_regime_cadence_without_profile() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-2e",
        ticker="MU",
        date="2026-02-10",
        regime_detection_minutes=22,
        regime_refresh_bars=6,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    assert result["trading_config"]["regime_detection_minutes"] == 22
    assert result["trading_config"]["regime_refresh_bars"] == 6
    assert result["regime_detection_minutes_source"] == "request"
    assert result["regime_refresh_bars_source"] == "request"


def test_resolve_execution_config_includes_tcbbo_gate_payload() -> None:
    request = StartRunRequest(
        run_id="cfg-2f",
        ticker="MU",
        date="2026-02-10",
        tcbbo_gate_enabled=True,
        tcbbo_min_net_premium=250_000.0,
        tcbbo_sweep_boost=5.0,
        tcbbo_lookback_bars=7,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["tcbbo_gate_enabled"] is True
    assert trading_config["tcbbo_min_net_premium"] == 250_000.0
    assert trading_config["tcbbo_sweep_boost"] == 5.0
    assert trading_config["tcbbo_lookback_bars"] == 7
    assert result["effective_tcbbo_gate_enabled"] is True
    assert result["effective_tcbbo_min_net_premium"] == 250_000.0
    assert result["effective_tcbbo_sweep_boost"] == 5.0
    assert result["effective_tcbbo_lookback_bars"] == 7


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


def test_resolve_execution_config_includes_global_exit_and_risk_module_defaults() -> (
    None
):
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


def test_resolve_execution_config_includes_profile_runtime_trade_cap_and_mu_choppy_flag() -> (
    None
):
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


def test_resolve_execution_config_includes_intraday_levels_payload() -> None:
    request = StartRunRequest(
        run_id="cfg-6",
        ticker="MU",
        date="2026-02-10",
        intraday_levels_enabled=False,
        intraday_levels_swing_left_bars=0,
        intraday_levels_swing_right_bars=-2,
        intraday_levels_test_tolerance_pct=-0.5,
        intraday_levels_break_tolerance_pct=0.09,
        intraday_levels_breakout_volume_lookback=1,
        intraday_levels_breakout_volume_multiplier=0.5,
        intraday_levels_volume_profile_bin_size_pct=0.0,
        intraday_levels_value_area_pct=2.0,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["intraday_levels_enabled"] is False
    assert trading_config["intraday_levels_swing_left_bars"] == 1
    assert trading_config["intraday_levels_swing_right_bars"] == 1
    assert trading_config["intraday_levels_test_tolerance_pct"] == 0.0
    assert trading_config["intraday_levels_break_tolerance_pct"] == 0.09
    assert trading_config["intraday_levels_breakout_volume_lookback"] == 2
    assert trading_config["intraday_levels_breakout_volume_multiplier"] == 1.0
    assert trading_config["intraday_levels_volume_profile_bin_size_pct"] == 0.01
    assert trading_config["intraday_levels_value_area_pct"] == 0.95


def test_resolve_execution_config_includes_intraday_entry_quality_gate_payload() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-7",
        ticker="MU",
        date="2026-02-10",
        intraday_levels_entry_quality_enabled=False,
        intraday_levels_min_levels_for_context=0,
        intraday_levels_entry_tolerance_pct=0.0,
        intraday_levels_break_cooldown_bars=0,
        intraday_levels_rotation_max_tests=0,
        intraday_levels_rotation_volume_max_ratio=9.0,
        intraday_levels_recent_bounce_lookback_bars=0,
        intraday_levels_require_recent_bounce_for_mean_reversion=False,
        intraday_levels_momentum_break_max_age_bars=0,
        intraday_levels_momentum_min_room_pct=0.0,
        intraday_levels_momentum_min_broken_ratio=2.0,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["intraday_levels_entry_quality_enabled"] is False
    assert trading_config["intraday_levels_min_levels_for_context"] == 1
    assert trading_config["intraday_levels_entry_tolerance_pct"] == 0.01
    assert trading_config["intraday_levels_break_cooldown_bars"] == 1
    assert trading_config["intraday_levels_rotation_max_tests"] == 1
    assert trading_config["intraday_levels_rotation_volume_max_ratio"] == 2.0
    assert trading_config["intraday_levels_recent_bounce_lookback_bars"] == 1
    assert (
        trading_config["intraday_levels_require_recent_bounce_for_mean_reversion"]
        is False
    )
    assert trading_config["intraday_levels_momentum_break_max_age_bars"] == 1
    assert trading_config["intraday_levels_momentum_min_room_pct"] == 0.01
    assert trading_config["intraday_levels_momentum_min_broken_ratio"] == 1.0


def test_resolve_execution_config_includes_intraday_walking_forward_payload() -> None:
    request = StartRunRequest(
        run_id="cfg-8",
        ticker="MU",
        date="2026-02-10",
        intraday_levels_min_confluence_score=0,
        intraday_levels_memory_enabled=False,
        intraday_levels_memory_min_tests=0,
        intraday_levels_memory_max_age_days=0,
        intraday_levels_memory_decay_after_days=0,
        intraday_levels_memory_decay_weight=5.0,
        intraday_levels_memory_max_levels=0,
        intraday_levels_opening_range_enabled=False,
        intraday_levels_opening_range_minutes=1,
        intraday_levels_opening_range_break_tolerance_pct=0.0,
        intraday_levels_poc_migration_enabled=False,
        intraday_levels_poc_migration_interval_bars=0,
        intraday_levels_poc_migration_trend_threshold_pct=0.0,
        intraday_levels_poc_migration_range_threshold_pct=0.0,
        intraday_levels_composite_profile_enabled=False,
        intraday_levels_composite_profile_days=0,
        intraday_levels_composite_profile_current_day_weight=0.0,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["intraday_levels_min_confluence_score"] == 1
    assert trading_config["intraday_levels_memory_enabled"] is False
    assert trading_config["intraday_levels_memory_min_tests"] == 1
    assert trading_config["intraday_levels_memory_max_age_days"] == 1
    assert trading_config["intraday_levels_memory_decay_after_days"] == 1
    assert trading_config["intraday_levels_memory_decay_weight"] == 1.0
    assert trading_config["intraday_levels_memory_max_levels"] == 1
    assert trading_config["intraday_levels_opening_range_enabled"] is False
    assert trading_config["intraday_levels_opening_range_minutes"] == 5
    assert trading_config["intraday_levels_opening_range_break_tolerance_pct"] == 0.01
    assert trading_config["intraday_levels_poc_migration_enabled"] is False
    assert trading_config["intraday_levels_poc_migration_interval_bars"] == 1
    assert trading_config["intraday_levels_poc_migration_trend_threshold_pct"] == 0.01
    assert trading_config["intraday_levels_poc_migration_range_threshold_pct"] == 0.01
    assert trading_config["intraday_levels_composite_profile_enabled"] is False
    assert trading_config["intraday_levels_composite_profile_days"] == 1
    assert trading_config["intraday_levels_composite_profile_current_day_weight"] == 0.1


def test_resolve_execution_config_includes_extended_intraday_and_context_risk_payload() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-9",
        ticker="MU",
        date="2026-02-10",
        intraday_levels_spike_detection_enabled=False,
        intraday_levels_spike_min_wick_ratio=0.2,
        intraday_levels_prior_day_anchors_enabled=False,
        intraday_levels_gap_analysis_enabled=False,
        intraday_levels_gap_min_pct=-1.0,
        intraday_levels_gap_momentum_threshold_pct=0.0,
        intraday_levels_rvol_filter_enabled=False,
        intraday_levels_rvol_lookback_bars=0,
        intraday_levels_rvol_min_threshold=-1.0,
        intraday_levels_rvol_strong_threshold=0.0,
        intraday_levels_adaptive_window_enabled=False,
        intraday_levels_adaptive_window_min_bars=0,
        intraday_levels_adaptive_window_rvol_threshold=-1.0,
        intraday_levels_adaptive_window_atr_ratio_max=0.0,
        intraday_levels_micro_confirmation_enabled=True,
        intraday_levels_micro_confirmation_bars=0,
        intraday_levels_micro_confirmation_disable_for_sweep=True,
        intraday_levels_micro_confirmation_sweep_bars=-1,
        intraday_levels_micro_confirmation_require_intrabar=True,
        intraday_levels_micro_confirmation_intrabar_window_seconds=0,
        intraday_levels_micro_confirmation_intrabar_min_coverage_points=-2,
        intraday_levels_micro_confirmation_intrabar_min_move_pct=-1.0,
        intraday_levels_micro_confirmation_intrabar_min_push_ratio=2.0,
        intraday_levels_micro_confirmation_intrabar_max_spread_bps=-1.0,
        intraday_levels_confluence_sizing_enabled=True,
        liquidity_sweep_detection_enabled=True,
        sweep_min_aggression_z=-4.0,
        sweep_min_book_pressure_z=2.0,
        sweep_max_price_change_pct=-1.0,
        context_aware_risk_enabled=True,
        context_risk_sl_buffer_pct=-1.0,
        context_risk_min_sl_pct=-1.0,
        context_risk_min_room_pct=-1.0,
        context_risk_min_effective_rr=-1.0,
        context_risk_trailing_tighten_zone=2.0,
        context_risk_trailing_tighten_factor=2.0,
        context_risk_level_trail_enabled=False,
        context_risk_max_anchor_search_pct=0.0,
        context_risk_min_level_tests_for_sl=-5,
        sweep_atr_buffer_multiplier=-1.0,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["intraday_levels_spike_detection_enabled"] is False
    assert trading_config["intraday_levels_spike_min_wick_ratio"] == 0.4
    assert trading_config["intraday_levels_prior_day_anchors_enabled"] is False
    assert trading_config["intraday_levels_gap_analysis_enabled"] is False
    assert trading_config["intraday_levels_gap_min_pct"] == 0.0
    assert trading_config["intraday_levels_gap_momentum_threshold_pct"] == 0.1
    assert trading_config["intraday_levels_rvol_filter_enabled"] is False
    assert trading_config["intraday_levels_rvol_lookback_bars"] == 5
    assert trading_config["intraday_levels_rvol_min_threshold"] == 0.0
    assert trading_config["intraday_levels_rvol_strong_threshold"] == 0.1
    assert trading_config["intraday_levels_adaptive_window_enabled"] is False
    assert trading_config["intraday_levels_adaptive_window_min_bars"] == 1
    assert trading_config["intraday_levels_adaptive_window_rvol_threshold"] == 0.0
    assert trading_config["intraday_levels_adaptive_window_atr_ratio_max"] == 0.1
    assert trading_config["intraday_levels_micro_confirmation_enabled"] is True
    assert trading_config["intraday_levels_micro_confirmation_bars"] == 1
    assert (
        trading_config["intraday_levels_micro_confirmation_disable_for_sweep"] is True
    )
    assert trading_config["intraday_levels_micro_confirmation_sweep_bars"] == 0
    assert trading_config["intraday_levels_micro_confirmation_require_intrabar"] is True
    assert (
        trading_config["intraday_levels_micro_confirmation_intrabar_window_seconds"]
        == 1
    )
    assert (
        trading_config[
            "intraday_levels_micro_confirmation_intrabar_min_coverage_points"
        ]
        == 0
    )
    assert (
        trading_config["intraday_levels_micro_confirmation_intrabar_min_move_pct"]
        == 0.0
    )
    assert (
        trading_config["intraday_levels_micro_confirmation_intrabar_min_push_ratio"]
        == 1.0
    )
    assert (
        trading_config["intraday_levels_micro_confirmation_intrabar_max_spread_bps"]
        == 0.0
    )
    assert trading_config["intraday_levels_confluence_sizing_enabled"] is True
    assert trading_config["liquidity_sweep_detection_enabled"] is True
    assert trading_config["sweep_min_aggression_z"] == -4.0
    assert trading_config["sweep_min_book_pressure_z"] == 2.0
    assert trading_config["sweep_max_price_change_pct"] == 0.0

    assert trading_config["context_aware_risk_enabled"] is True
    assert trading_config["context_risk_sl_buffer_pct"] == 0.0
    assert trading_config["context_risk_min_sl_pct"] == 0.0
    assert trading_config["context_risk_min_room_pct"] == 0.0
    assert trading_config["context_risk_min_effective_rr"] == 0.0
    assert trading_config["context_risk_trailing_tighten_zone"] == 1.0
    assert trading_config["context_risk_trailing_tighten_factor"] == 1.0
    assert trading_config["context_risk_level_trail_enabled"] is False
    assert trading_config["context_risk_max_anchor_search_pct"] == 0.1
    assert trading_config["context_risk_min_level_tests_for_sl"] == 0
    assert trading_config["sweep_atr_buffer_multiplier"] == 0.0

    assert result["effective_intraday_levels_spike_detection_enabled"] is False
    assert result["effective_intraday_levels_micro_confirmation_enabled"] is True
    assert result["effective_intraday_levels_micro_confirmation_bars"] == 1
    assert (
        result["effective_intraday_levels_micro_confirmation_disable_for_sweep"] is True
    )
    assert result["effective_intraday_levels_micro_confirmation_sweep_bars"] == 0
    assert (
        result["effective_intraday_levels_micro_confirmation_require_intrabar"] is True
    )
    assert (
        result["effective_intraday_levels_micro_confirmation_intrabar_window_seconds"]
        == 1
    )
    assert (
        result[
            "effective_intraday_levels_micro_confirmation_intrabar_min_coverage_points"
        ]
        == 0
    )
    assert (
        result["effective_intraday_levels_micro_confirmation_intrabar_min_move_pct"]
        == 0.0
    )
    assert (
        result["effective_intraday_levels_micro_confirmation_intrabar_min_push_ratio"]
        == 1.0
    )
    assert (
        result["effective_intraday_levels_micro_confirmation_intrabar_max_spread_bps"]
        == 0.0
    )
    assert result["effective_intraday_levels_confluence_sizing_enabled"] is True
    assert result["effective_liquidity_sweep_detection_enabled"] is True
    assert result["effective_sweep_max_price_change_pct"] == 0.0
    assert result["requested_l2_confirm"] is True
    assert result["liquidity_sweep_l2_auto_enabled"] is True
    assert result["liquidity_sweep_l2_auto_source"] == "liquidity_sweep_guard"
    assert trading_config["l2_confirm_enabled"] is True
    assert result["context_aware_risk_enabled"] is True
    assert result["context_risk_min_sl_pct"] == 0.0
    assert result["sweep_atr_buffer_multiplier"] == 0.0


def test_resolve_execution_config_uses_positioning_profile_for_micro_confirmation_controls() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-9b",
        ticker="MU",
        date="2026-02-10",
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={
            "positioning": {
                "intraday_levels_micro_confirmation_enabled": True,
                "intraday_levels_micro_confirmation_bars": 3,
                "intraday_levels_micro_confirmation_disable_for_sweep": True,
                "intraday_levels_micro_confirmation_sweep_bars": 0,
                "intraday_levels_micro_confirmation_require_intrabar": True,
                "intraday_levels_micro_confirmation_intrabar_window_seconds": 10,
                "intraday_levels_micro_confirmation_intrabar_min_coverage_points": 4,
                "intraday_levels_micro_confirmation_intrabar_min_move_pct": 0.03,
                "intraday_levels_micro_confirmation_intrabar_min_push_ratio": 0.2,
                "intraday_levels_micro_confirmation_intrabar_max_spread_bps": 8.0,
            }
        },
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["intraday_levels_micro_confirmation_enabled"] is True
    assert trading_config["intraday_levels_micro_confirmation_bars"] == 3
    assert (
        trading_config["intraday_levels_micro_confirmation_disable_for_sweep"] is True
    )
    assert trading_config["intraday_levels_micro_confirmation_sweep_bars"] == 0
    assert trading_config["intraday_levels_micro_confirmation_require_intrabar"] is True
    assert (
        trading_config["intraday_levels_micro_confirmation_intrabar_window_seconds"]
        == 10
    )
    assert (
        trading_config[
            "intraday_levels_micro_confirmation_intrabar_min_coverage_points"
        ]
        == 4
    )
    assert (
        trading_config["intraday_levels_micro_confirmation_intrabar_min_move_pct"]
        == 0.03
    )
    assert (
        trading_config["intraday_levels_micro_confirmation_intrabar_min_push_ratio"]
        == 0.2
    )
    assert (
        trading_config["intraday_levels_micro_confirmation_intrabar_max_spread_bps"]
        == 8.0
    )


def test_resolve_execution_config_keeps_explicit_context_risk_and_be_proof_overrides() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-9b2",
        ticker="MU",
        date="2026-02-10",
        context_aware_risk_enabled=False,
        context_risk_min_sl_pct=0.50,
        break_even_activation_use_levels=True,
        break_even_activation_use_l2=True,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={
            "positioning": {
                "context_aware_risk_enabled": True,
                "context_risk_min_sl_pct": 0.55,
                "context_risk_min_room_pct": 0.10,
                "break_even_activation_use_levels": False,
                "break_even_activation_use_l2": False,
            }
        },
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["context_aware_risk_enabled"] is False
    assert trading_config["context_risk_min_sl_pct"] == 0.50
    assert trading_config["context_risk_min_room_pct"] == 0.10
    assert trading_config["break_even_activation_use_levels"] is False
    assert trading_config["break_even_activation_use_l2"] is False
    assert result["context_aware_risk_enabled"] is False
    assert result["context_risk_min_sl_pct"] == 0.50


def test_resolve_execution_config_keeps_explicit_context_risk_request_over_adaptive_profile() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-9b2b",
        ticker="MU",
        date="2026-02-10",
        context_aware_risk_enabled=False,
        context_risk_min_effective_rr=0.50,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={
            "context_aware_risk_enabled": True,
            "context_risk_min_effective_rr": 0.85,
        },
    )

    trading_config = result["trading_config"]
    assert trading_config["context_aware_risk_enabled"] is False
    assert trading_config["context_risk_min_effective_rr"] == 0.50
    assert result["context_aware_risk_enabled"] is False
    assert result["context_risk_min_effective_rr"] == 0.50


def test_resolve_execution_config_uses_positioning_profile_for_runtime_exit_formulas() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-9b3",
        ticker="MU",
        date="2026-02-10",
        break_even_activation_formula_enabled=False,
        break_even_activation_formula="",
        time_exit_formula_enabled=False,
        time_exit_formula="",
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={
            "positioning": {
                "break_even_activation_formula_enabled": True,
                "break_even_activation_formula": "mfe_r >= 1 and proof_passed",
                "time_exit_formula_enabled": True,
                "time_exit_formula": "time_exit_base and not quality_favorable",
            }
        },
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["break_even_activation_formula_enabled"] is True
    assert (
        trading_config["break_even_activation_formula"] == "mfe_r >= 1 and proof_passed"
    )
    assert trading_config["time_exit_formula_enabled"] is True
    assert (
        trading_config["time_exit_formula"]
        == "time_exit_base and not quality_favorable"
    )
    assert result["effective_break_even_activation_formula_enabled"] is True
    assert (
        result["break_even_activation_formula_enabled_source"] == "positioning_config"
    )
    assert (
        result["effective_break_even_activation_formula"]
        == "mfe_r >= 1 and proof_passed"
    )
    assert result["break_even_activation_formula_source"] == "positioning_config"


def test_resolve_execution_config_applies_unified_profile_intraday_overrides() -> None:
    request = StartRunRequest(
        run_id="cfg-9c",
        ticker="MU",
        date="2026-02-10",
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={
            "positioning": {
                "intraday_levels_entry_tolerance_pct": 0.08,
                "intraday_levels_micro_confirmation_enabled": True,
            }
        },
        adaptive_profile_runtime={
            "intraday_levels_entry_tolerance_pct": 0.12,
            "intraday_levels_micro_confirmation_enabled": False,
            "intraday_levels_memory_enabled": True,
        },
    )

    trading_config = result["trading_config"]
    assert trading_config["intraday_levels_entry_tolerance_pct"] == 0.12
    assert trading_config["intraday_levels_micro_confirmation_enabled"] is False
    assert trading_config["intraday_levels_memory_enabled"] is True


def test_resolve_execution_config_applies_broad_intraday_profile_overrides() -> None:
    request = StartRunRequest(
        run_id="cfg-9c2",
        ticker="MU",
        date="2026-02-10",
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={
            "intraday_levels_entry_quality_enabled": False,
            "intraday_levels_opening_range_enabled": False,
            "intraday_levels_opening_range_minutes": 7,
            "intraday_levels_rvol_filter_enabled": False,
            "intraday_levels_rvol_lookback_bars": 8,
            "intraday_levels_adaptive_window_enabled": False,
            "intraday_levels_adaptive_window_min_bars": 2,
            "intraday_levels_confluence_sizing_enabled": True,
            "liquidity_sweep_detection_enabled": True,
            "sweep_max_price_change_pct": 0.02,
        },
    )

    trading_config = result["trading_config"]
    assert trading_config["intraday_levels_entry_quality_enabled"] is False
    assert trading_config["intraday_levels_opening_range_enabled"] is False
    assert trading_config["intraday_levels_opening_range_minutes"] == 7
    assert trading_config["intraday_levels_rvol_filter_enabled"] is False
    assert trading_config["intraday_levels_rvol_lookback_bars"] == 8
    assert trading_config["intraday_levels_adaptive_window_enabled"] is False
    assert trading_config["intraday_levels_adaptive_window_min_bars"] == 2
    assert trading_config["intraday_levels_confluence_sizing_enabled"] is True
    assert trading_config["liquidity_sweep_detection_enabled"] is True
    assert trading_config["sweep_max_price_change_pct"] == 0.02
    assert trading_config["l2_confirm_enabled"] is True
    assert result["requested_l2_confirm"] is True
    assert result["liquidity_sweep_l2_auto_enabled"] is True
    assert result["liquidity_sweep_l2_auto_source"] == "liquidity_sweep_guard"


def test_resolve_execution_config_keeps_explicit_intraday_request_over_profile() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-9d",
        ticker="MU",
        date="2026-02-10",
        intraday_levels_entry_tolerance_pct=0.2,
        intraday_levels_micro_confirmation_enabled=True,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={
            "positioning": {
                "intraday_levels_entry_tolerance_pct": 0.08,
                "intraday_levels_micro_confirmation_enabled": False,
            }
        },
        adaptive_profile_runtime={
            "intraday_levels_entry_tolerance_pct": 0.12,
            "intraday_levels_micro_confirmation_enabled": False,
        },
    )

    trading_config = result["trading_config"]
    assert trading_config["intraday_levels_entry_tolerance_pct"] == 0.2
    assert trading_config["intraday_levels_micro_confirmation_enabled"] is True


def test_resolve_execution_config_forces_strategy_stop_mode_when_context_risk_enabled() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-10",
        ticker="MU",
        date="2026-02-10",
        context_aware_risk_enabled=True,
        stop_loss_mode="capped",
        fixed_stop_loss_pct=0.24,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    trading_config = result["trading_config"]
    assert trading_config["stop_loss_mode"] == "strategy"
    assert result["effective_stop_loss_mode"] == "strategy"
    assert result["stop_loss_mode_source"] == "context_risk_override"


def test_resolve_execution_config_keeps_manual_l2_when_sweep_enabled() -> None:
    request = StartRunRequest(
        run_id="cfg-10b",
        ticker="MU",
        date="2026-02-10",
        liquidity_sweep_detection_enabled=True,
        l2_confirm_enabled=True,
    )

    result = resolve_execution_config(
        request=request,
        aos_applied={},
        adaptive_profile_runtime={},
    )

    assert result["requested_l2_confirm"] is True
    assert result["liquidity_sweep_l2_auto_enabled"] is False
    assert result["liquidity_sweep_l2_auto_source"] == "already_enabled"


def test_resolve_execution_config_rejects_non_positive_fixed_stop_loss_for_fixed_mode() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-11",
        ticker="MU",
        date="2026-02-10",
        stop_loss_mode="fixed",
        fixed_stop_loss_pct=0.0,
    )

    with pytest.raises(ValueError, match="Fixed stop-loss % must be > 0"):
        resolve_execution_config(
            request=request,
            aos_applied={},
            adaptive_profile_runtime={},
        )


def test_resolve_execution_config_rejects_non_positive_fixed_stop_loss_from_positioning_config() -> (
    None
):
    request = StartRunRequest(
        run_id="cfg-12",
        ticker="MU",
        date="2026-02-10",
    )

    with pytest.raises(ValueError, match="Fixed stop-loss % must be > 0"):
        resolve_execution_config(
            request=request,
            aos_applied={
                "positioning": {"stop_loss_mode": "capped", "fixed_stop_loss_pct": 0.0}
            },
            adaptive_profile_runtime={},
        )
