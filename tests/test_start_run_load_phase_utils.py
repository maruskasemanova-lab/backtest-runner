from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.services.start_run_data_service as start_run_data_service
import src.services.start_run_load_phase_service as load_phase_service
from src.services.start_run_load_phase_utils import (
    load_initial_bars_with_progressive_retry,
    merge_tcbbo_stats,
    resolve_tcbbo_enrichment_reasons,
)


class _Logger:
    def __init__(self) -> None:
        self.messages: list[tuple] = []

    def info(self, *args, **kwargs) -> None:
        self.messages.append(args)


def test_resolve_tcbbo_enrichment_reasons_uses_gate_and_options_alpha() -> None:
    reasons = resolve_tcbbo_enrichment_reasons(
        execution_cfg={"effective_tcbbo_gate_enabled": True},
        aos_applied={"positioning": {"options_flow_alpha_enabled": True}},
    )

    assert reasons == ["tcbbo_gate", "options_flow_alpha"]


def test_merge_tcbbo_stats_adds_required_flags_only_when_stats_present() -> None:
    merged = merge_tcbbo_stats(
        l2_stats={"l2_available": True},
        tcbbo_stats={"tcbbo_available": True},
        tcbbo_enrichment_reasons=["options_flow_alpha"],
    )

    assert merged["l2_available"] is True
    assert merged["tcbbo_available"] is True
    assert merged["tcbbo_enrichment_required"] is True
    assert merged["tcbbo_enrichment_reasons"] == ["options_flow_alpha"]

    untouched = merge_tcbbo_stats(
        l2_stats={"l2_available": True},
        tcbbo_stats=None,
        tcbbo_enrichment_reasons=["options_flow_alpha"],
    )
    assert untouched == {"l2_available": True}


def test_load_initial_bars_with_progressive_retry_expands_initial_range() -> None:
    logger = _Logger()
    call_ranges: list[str] = []

    def _load_run_bars(**kwargs):
        call_ranges.append(str(kwargs["range_end"]))
        if len(call_ranges) == 1:
            raise HTTPException(404, "No data available for the specified date/range")
        return ([{"timestamp": "2026-02-05T14:30:00Z"}], ["dummy.csv"])

    inputs = SimpleNamespace(
        request=SimpleNamespace(run_id="run-1"),
        ticker="MU",
        run_key="run-1:MU:2026-02-05_to_2026-02-10",
        load_range_start="2026-02-05",
        load_range_end="2026-02-05",
        progressive_plan={"initial_end": "2026-02-05", "chunks": [("2026-02-06", "2026-02-08")]},
        progressive_pending_chunks=[("2026-02-06", "2026-02-08")],
        aos_applied={},
    )
    deps = SimpleNamespace(
        load_run_bars=_load_run_bars,
        data_loader=None,
        databento_svc=None,
        get_discovery=lambda: None,
        logger=logger,
    )

    bars, data_files, load_range_end, progressive_plan, pending_chunks = (
        load_initial_bars_with_progressive_retry(inputs=inputs, deps=deps)
    )

    assert call_ranges == ["2026-02-05", "2026-02-08"]
    assert bars == [{"timestamp": "2026-02-05T14:30:00Z"}]
    assert data_files == ["dummy.csv"]
    assert load_range_end == "2026-02-08"
    assert progressive_plan == {"initial_end": "2026-02-08", "chunks": []}
    assert pending_chunks == []
    assert logger.messages, "expected info log when initial range expands"


def test_load_initial_bars_with_progressive_retry_raises_for_non_progressive_error() -> None:
    def _load_run_bars(**kwargs):
        raise HTTPException(500, "upstream failure")

    inputs = SimpleNamespace(
        request=SimpleNamespace(run_id="run-1"),
        ticker="MU",
        run_key="run-1:MU:2026-02-05",
        load_range_start="2026-02-05",
        load_range_end="2026-02-05",
        progressive_plan=None,
        progressive_pending_chunks=[],
        aos_applied={},
    )
    deps = SimpleNamespace(
        load_run_bars=_load_run_bars,
        data_loader=None,
        databento_svc=None,
        get_discovery=lambda: None,
        logger=_Logger(),
    )

    with pytest.raises(HTTPException):
        load_initial_bars_with_progressive_retry(inputs=inputs, deps=deps)


def test_run_start_load_phase_sync_path_applies_tcbbo_enrichment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _load_run_bars(**kwargs):
        return ([{"timestamp": "2026-02-05T14:30:00Z"}], ["dummy.csv"])

    def _enrich_bars_with_l2(**kwargs):
        return (list(kwargs["bars"]), {"l2_available": True}, False)

    def _fake_enrich_bars_with_tcbbo(**kwargs):
        return list(kwargs["bars"]), {"tcbbo_available": True}

    monkeypatch.setattr(
        start_run_data_service,
        "enrich_bars_with_tcbbo",
        _fake_enrich_bars_with_tcbbo,
    )
    monkeypatch.setattr(
        load_phase_service,
        "filter_bars_for_requested_time_window",
        lambda *, bars, request, to_utc_datetime: list(bars),
    )

    deps = load_phase_service.LoadPhaseDeps(
        logger=_Logger(),
        data_loader=object(),
        databento_svc=None,
        get_discovery=lambda: None,
        load_run_bars=_load_run_bars,
        enrich_bars_with_l2=_enrich_bars_with_l2,
        to_utc_datetime=lambda value: value,
        build_l2_feature_map=lambda *args, **kwargs: {},
        normalize_l2_feature_map_for_market_day_sessions=lambda *args, **kwargs: {},
        attach_l2_features=lambda *args, **kwargs: ([], {}),
        run_l2_guard_reason=lambda **kwargs: None,
    )
    inputs = load_phase_service.LoadPhaseInputs(
        request=SimpleNamespace(run_id="load-phase-test", date_from=None, date_to=None),
        ticker="MU",
        run_key="load-phase-test:MU:2026-02-05",
        range_start="2026-02-05",
        range_end="2026-02-05",
        load_range_start="2026-02-05",
        load_range_end="2026-02-05",
        comparable_mode=False,
        aos_applied={"positioning": {"options_flow_alpha_enabled": True}},
        execution_cfg={
            "requested_l2_only": False,
            "requested_l2_confirm": False,
            "effective_tcbbo_gate_enabled": False,
        },
        progressive_plan=None,
        progressive_pending_chunks=[],
    )

    result = asyncio.run(
        load_phase_service.run_start_load_phase(
            inputs=inputs,
            deps=deps,
            record_phase_ms=lambda *args, **kwargs: None,
        )
    )

    assert result.bars == [{"timestamp": "2026-02-05T14:30:00Z"}]
    assert result.data_files == ["dummy.csv"]
    assert result.l2_stats["l2_available"] is True
    assert result.l2_stats["tcbbo_available"] is True
    assert result.l2_stats["tcbbo_enrichment_required"] is True
    assert result.l2_stats["tcbbo_enrichment_reasons"] == ["options_flow_alpha"]
