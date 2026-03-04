"""Tests for config fingerprint utility."""

from src.services.config_fingerprint_utils import compute_config_fingerprint


def test_compute_config_fingerprint_returns_prefixed_hash() -> None:
    result = compute_config_fingerprint({"trading_config": {"a": 1}})
    assert result.startswith("cfg_")
    assert len(result) == 16  # "cfg_" + 12 hex chars


def test_compute_config_fingerprint_deterministic() -> None:
    config = {
        "trading_config": {"time_exit_bars": 12, "stop_loss_mode": "strategy"},
        "effective_risk_per_trade_pct": 1.0,
    }
    fp1 = compute_config_fingerprint(config)
    fp2 = compute_config_fingerprint(config)
    assert fp1 == fp2


def test_compute_config_fingerprint_changes_on_param_change() -> None:
    config_a = {
        "trading_config": {"time_exit_bars": 12, "context_aware_risk_enabled": True},
    }
    config_b = {
        "trading_config": {"time_exit_bars": 35, "context_aware_risk_enabled": False},
    }
    fp_a = compute_config_fingerprint(config_a)
    fp_b = compute_config_fingerprint(config_b)
    assert fp_a != fp_b


def test_compute_config_fingerprint_ignores_source_fields() -> None:
    config_base = {
        "trading_config": {"time_exit_bars": 12},
        "effective_time_exit_bars": 12,
    }
    config_with_source = {
        "trading_config": {"time_exit_bars": 12},
        "effective_time_exit_bars": 12,
        "time_exit_bars_source": "adaptive_profile",
    }
    fp_base = compute_config_fingerprint(config_base)
    fp_with_source = compute_config_fingerprint(config_with_source)
    assert fp_base == fp_with_source


def test_compute_config_fingerprint_ignores_positioning_cfg_requested() -> None:
    config_a = {
        "trading_config": {"l2_min_delta": 2200.0},
        "positioning_cfg_requested": True,
        "positioning_cfg": {"some": "data"},
    }
    config_b = {
        "trading_config": {"l2_min_delta": 2200.0},
    }
    assert compute_config_fingerprint(config_a) == compute_config_fingerprint(config_b)


def test_compute_config_fingerprint_handles_empty_config() -> None:
    result = compute_config_fingerprint({})
    assert result.startswith("cfg_")
    assert len(result) == 16


def test_compute_config_fingerprint_key_order_independent() -> None:
    config_a = {"trading_config": {"z": 1, "a": 2}}
    config_b = {"trading_config": {"a": 2, "z": 1}}
    assert compute_config_fingerprint(config_a) == compute_config_fingerprint(config_b)
