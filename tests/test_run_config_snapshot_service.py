from __future__ import annotations

from src.services.run_config_snapshot_service import (
    attach_resolved_config_snapshot_to_summary,
    build_resolved_config_snapshot,
    build_resolved_config_snapshot_id,
    resolve_session_config_snapshot,
)


def test_build_resolved_config_snapshot_persists_control_plane_payloads() -> None:
    snapshot = build_resolved_config_snapshot(
        run_id="run-1",
        ticker="mu",
        date_label="2026-02-11",
        report_metadata={
            "adaptive_profile_id": "adaptive-alpha",
            "config_fingerprint": "cfg_exec123",
        },
        control_plane_snapshot={
            "config_fingerprint": "cfg_exec123",
            "aos_applied_fingerprint": "cfg_aos456",
        },
        aos_applied={"time_filter_enabled": True},
        execution_config={"config_fingerprint": "cfg_exec123"},
        run_request_config={"trade_eval_mode": "intrabar_5s"},
        l2_applied={"effective_l2_confirm_enabled": True},
        session_config_snapshot={
            "regime_detection_minutes": 15,
            "strategy_selection_mode": "adaptive_top_n",
        },
        to_json_safe=lambda value: value,
    )

    assert snapshot["schema_version"] == 1
    assert snapshot["run_key"] == "run-1:MU:2026-02-11"
    assert snapshot["config_fingerprint"] == "cfg_exec123"
    assert snapshot["aos_applied_fingerprint"] == "cfg_aos456"
    assert snapshot["control_plane_snapshot"]["config_fingerprint"] == "cfg_exec123"
    assert snapshot["run_request_config"]["trade_eval_mode"] == "intrabar_5s"
    assert snapshot["session_config_snapshot"]["regime_detection_minutes"] == 15


def test_resolve_session_config_snapshot_prefers_direct_then_nested_snapshot() -> None:
    assert resolve_session_config_snapshot({"l2_confirm_enabled": False}) == {
        "l2_confirm_enabled": False
    }

    assert resolve_session_config_snapshot(
        summary_payload={
            "resolved_config_snapshot": {
                "session_config_snapshot": {
                    "strategy_selection_mode": "adaptive_top_n",
                    "max_active_strategies": 3,
                }
            }
        }
    ) == {
        "strategy_selection_mode": "adaptive_top_n",
        "max_active_strategies": 3,
    }


def test_resolved_config_snapshot_id_and_attach_helper_are_stable() -> None:
    snapshot = {
        "schema_version": 1,
        "run_key": "run-1:MU:2026-02-11",
        "config_fingerprint": "cfg_exec123",
    }
    snapshot_id = build_resolved_config_snapshot_id(
        run_key="run-1:MU:2026-02-11",
        snapshot=snapshot,
    )
    enriched = attach_resolved_config_snapshot_to_summary(
        {"run_id": "run-1"},
        snapshot_id=snapshot_id,
        snapshot_payload=snapshot,
    )

    assert snapshot_id.startswith("rcs_")
    assert enriched["resolved_config_snapshot_id"] == snapshot_id
    assert enriched["resolved_config_snapshot"]["config_fingerprint"] == "cfg_exec123"
