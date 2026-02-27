from types import SimpleNamespace

import pytest

import src.services.start_run_load_phase_service as load_phase_service
import src.services.start_run_data_service as start_run_data_service
from src.services.start_run_load_phase_service import (
    LoadPhaseDeps,
    LoadPhaseInputs,
    run_start_load_phase,
)


class _Logger:
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None


def _build_deps() -> LoadPhaseDeps:
    def _load_run_bars(**kwargs):
        return ([{"timestamp": "2026-02-05T14:30:00Z"}], ["dummy.csv"])

    def _enrich_bars_with_l2(**kwargs):
        return (list(kwargs["bars"]), {}, False)

    return LoadPhaseDeps(
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


def _build_inputs(*, tcbbo_gate_enabled: bool, options_flow_alpha_enabled: bool) -> LoadPhaseInputs:
    request = SimpleNamespace(run_id="load-phase-test", date_from=None, date_to=None)
    return LoadPhaseInputs(
        request=request,
        ticker="MU",
        run_key="load-phase-test:MU:2026-02-05",
        range_start="2026-02-05",
        range_end="2026-02-05",
        load_range_start="2026-02-05",
        load_range_end="2026-02-05",
        comparable_mode=False,
        aos_applied={
            "positioning": {"options_flow_alpha_enabled": options_flow_alpha_enabled}
        },
        execution_cfg={
            "requested_l2_only": False,
            "requested_l2_confirm": False,
            "effective_tcbbo_gate_enabled": tcbbo_gate_enabled,
        },
        progressive_plan=None,
        progressive_pending_chunks=[],
    )


@pytest.mark.asyncio
async def test_run_start_load_phase_enriches_tcbbo_when_options_flow_alpha_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_enrich_bars_with_tcbbo(**kwargs):
        calls.append(dict(kwargs))
        return list(kwargs["bars"]), {"tcbbo_available": True}

    monkeypatch.setattr(
        start_run_data_service, "enrich_bars_with_tcbbo", fake_enrich_bars_with_tcbbo
    )
    monkeypatch.setattr(
        load_phase_service,
        "filter_bars_for_requested_time_window",
        lambda *, bars, request, to_utc_datetime: list(bars),
    )

    result = await run_start_load_phase(
        inputs=_build_inputs(tcbbo_gate_enabled=False, options_flow_alpha_enabled=True),
        deps=_build_deps(),
        record_phase_ms=lambda *args, **kwargs: None,
    )

    assert len(calls) == 1
    assert calls[0]["ticker"] == "MU"
    assert result.l2_stats["tcbbo_available"] is True
    assert result.l2_stats["tcbbo_enrichment_required"] is True
    assert "options_flow_alpha" in result.l2_stats["tcbbo_enrichment_reasons"]


@pytest.mark.asyncio
async def test_run_start_load_phase_skips_tcbbo_when_not_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_enrich_bars_with_tcbbo(**kwargs):
        calls.append(dict(kwargs))
        return list(kwargs["bars"]), {"tcbbo_available": True}

    monkeypatch.setattr(
        start_run_data_service, "enrich_bars_with_tcbbo", fake_enrich_bars_with_tcbbo
    )
    monkeypatch.setattr(
        load_phase_service,
        "filter_bars_for_requested_time_window",
        lambda *, bars, request, to_utc_datetime: list(bars),
    )

    result = await run_start_load_phase(
        inputs=_build_inputs(tcbbo_gate_enabled=False, options_flow_alpha_enabled=False),
        deps=_build_deps(),
        record_phase_ms=lambda *args, **kwargs: None,
    )

    assert calls == []
    assert "tcbbo_available" not in result.l2_stats
