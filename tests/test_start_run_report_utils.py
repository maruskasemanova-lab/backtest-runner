from datetime import datetime

from src.services.start_run_report_utils import (
    build_data_availability_warnings,
    build_report_metadata,
    build_run_request_config_snapshot,
    extract_effective_profile_metadata,
    first_profile_ref_token,
    normalize_profile_ref_token,
    summarize_days_preview,
)


def test_normalize_profile_ref_token_filters_placeholders() -> None:
    assert normalize_profile_ref_token("  profile-1  ") == "profile-1"
    assert normalize_profile_ref_token("") is None
    assert normalize_profile_ref_token("None") is None
    assert normalize_profile_ref_token("n/a") is None


def test_first_profile_ref_token_returns_first_valid_token() -> None:
    assert (
        first_profile_ref_token(" ", "none", "adaptive-1", "fallback")
        == "adaptive-1"
    )
    assert first_profile_ref_token(None, "", "na") is None


def test_extract_effective_profile_metadata_prefers_execution_config() -> None:
    metadata = extract_effective_profile_metadata(
        aos_applied={
            "unified_profile": {"profile_id": "u-fallback"},
            "adaptive_profile": {"profile_id": "a-fallback"},
            "strategy_combo": {"profile_id": "s-fallback"},
        },
        execution_config={
            "unified_profile_id": "u-active",
            "adaptive_profile_id": "a-active",
            "strategy_combo_profile_id": "s-active",
        },
    )

    assert metadata["unified_profile_id"] == "u-active"
    assert metadata["adaptive_profile_id"] == "a-active"
    assert metadata["strategy_combo_profile_id"] == "s-active"


def test_summarize_days_preview_compacts_long_lists() -> None:
    assert summarize_days_preview(["2026-01-01", "2026-01-02"]) == "2026-01-01, 2026-01-02"
    assert (
        summarize_days_preview(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"])
        == "2026-01-01, 2026-01-02, 2026-01-03, ..."
    )


def test_build_data_availability_warnings_includes_l2_and_tcbbo_reasons() -> None:
    warnings = build_data_availability_warnings(
        execution_config={"tcbbo_gate_enabled": True},
        l2_applied={
            "effective_l2_confirm_enabled": True,
            "has_l2": True,
            "missing_l2_days_count": 1,
            "missing_l2_days": ["2026-02-05"],
            "tcbbo_gate_enabled": True,
            "tcbbo_feature_required": True,
            "tcbbo_available": False,
            "tcbbo_missing_reason": "tcbbo_file_not_found",
        },
    )

    assert any("L2 coverage missing for 1 day(s)" in item for item in warnings)
    assert any("TCBBO parquet file not found" in item for item in warnings)


def test_build_report_metadata_uses_profile_metadata() -> None:
    metadata = build_report_metadata(
        run_key="run-1:MU:2026-02-01",
        run_date_label="2026-02-01",
        aos_applied={"unified_profile": {"profile_id": "u-fallback"}},
        execution_config={"unified_profile_id": "u-active"},
    )

    assert metadata["run_key"] == "run-1:MU:2026-02-01"
    assert metadata["unified_profile_id"] == "u-active"


def test_build_report_metadata_includes_control_plane_fingerprints() -> None:
    metadata = build_report_metadata(
        run_key="run-1:MU:2026-02-01",
        run_date_label="2026-02-01",
        aos_applied={},
        execution_config={
            "config_fingerprint": "cfg_exec123",
            "control_plane_snapshot": {"aos_applied_fingerprint": "cfg_aos456"},
        },
    )

    assert metadata["config_fingerprint"] == "cfg_exec123"
    assert metadata["aos_applied_fingerprint"] == "cfg_aos456"


def test_build_run_request_config_snapshot_json_normalizes_values() -> None:
    class _DummyRequest:
        def dict(self) -> dict:
            return {"created_at": datetime(2026, 2, 28, 12, 0, 0)}

    payload = build_run_request_config_snapshot(_DummyRequest())

    assert payload["created_at"].startswith("2026-02-28")
