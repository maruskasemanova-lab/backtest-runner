from src.services.start_run_service import _build_data_availability_warnings


def test_build_data_availability_warnings_reports_missing_l2_days() -> None:
    warnings = _build_data_availability_warnings(
        execution_config={"tcbbo_gate_enabled": False},
        l2_applied={
            "effective_l2_confirm_enabled": True,
            "has_l2": True,
            "missing_l2_days_count": 2,
            "missing_l2_days": ["2026-02-05", "2026-02-06"],
            "tcbbo_gate_enabled": False,
        },
    )

    assert any("L2 coverage missing for 2 day(s)" in msg for msg in warnings)


def test_build_data_availability_warnings_reports_missing_tcbbo_reason() -> None:
    warnings = _build_data_availability_warnings(
        execution_config={"tcbbo_gate_enabled": True},
        l2_applied={
            "effective_l2_confirm_enabled": False,
            "l2_requested": False,
            "tcbbo_gate_enabled": True,
            "tcbbo_available": False,
            "tcbbo_missing_reason": "tcbbo_file_not_found",
            "tcbbo_files_found": 0,
        },
    )

    assert any("TCBBO parquet file not found" in msg for msg in warnings)


def test_build_data_availability_warnings_reports_missing_tcbbo_for_options_flow_alpha() -> (
    None
):
    warnings = _build_data_availability_warnings(
        execution_config={"tcbbo_gate_enabled": False},
        l2_applied={
            "effective_l2_confirm_enabled": False,
            "l2_requested": False,
            "tcbbo_gate_enabled": False,
            "tcbbo_feature_required": True,
            "tcbbo_feature_required_by": ["options_flow_alpha"],
            "tcbbo_available": False,
            "tcbbo_missing_reason": "tcbbo_file_not_found",
        },
    )

    assert any("OptionsFlowAlpha is enabled" in msg for msg in warnings)
