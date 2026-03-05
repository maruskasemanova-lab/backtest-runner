from __future__ import annotations

from src.services.start_run_control_plane_snapshot_service import (
    build_control_plane_snapshot,
)


def test_build_control_plane_snapshot_captures_profile_ids_and_fingerprints() -> None:
    snapshot = build_control_plane_snapshot(
        aos_applied={
            "trading_hours": [11, 9, 10],
            "time_filter_enabled": True,
            "strategy_selection_mode": "all_enabled",
            "max_active_strategies": 5,
            "unified_profile": {
                "active_profile_id": "u1",
                "profile_name": "Unified",
            },
            "adaptive_profile": {
                "active_profile_id": "a1",
                "profile_name": "Adaptive",
            },
        },
        execution_config={
            "config_fingerprint": "cfg_exec123",
            "effective_strategy_selection_mode": "all_enabled",
            "effective_max_active_strategies": 5,
        },
        apply_aos_optimizations_on_start=True,
        effective_reset_scope="session",
        comparable_mode=False,
    )

    assert snapshot["schema_version"] == 1
    assert snapshot["config_fingerprint"] == "cfg_exec123"
    assert snapshot["execution_config_fingerprint"] == "cfg_exec123"
    assert snapshot["aos_applied_fingerprint"].startswith("cfg_")
    assert snapshot["unified_profile_id"] == "u1"
    assert snapshot["adaptive_profile_id"] == "a1"
    assert snapshot["trading_hours"] == [9, 10, 11]
    assert snapshot["strategy_selection_mode"] == "all_enabled"
    assert snapshot["max_active_strategies"] == 5
