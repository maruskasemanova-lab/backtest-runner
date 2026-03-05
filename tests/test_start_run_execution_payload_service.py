from __future__ import annotations

from src.services.start_run_execution_payload_service import (
    _apply_control_plane_snapshot,
)


def test_apply_control_plane_snapshot_enriches_execution_payload() -> None:
    payload: dict = {}
    _apply_control_plane_snapshot(
        execution_config_payload=payload,
        execution_cfg={"config_fingerprint": "cfg_exec123"},
        control_plane_snapshot={
            "config_fingerprint": "cfg_exec123",
            "aos_applied_fingerprint": "cfg_aos456",
        },
    )

    assert payload["config_fingerprint"] == "cfg_exec123"
    assert payload["aos_applied_fingerprint"] == "cfg_aos456"
    assert payload["control_plane_snapshot"]["config_fingerprint"] == "cfg_exec123"
