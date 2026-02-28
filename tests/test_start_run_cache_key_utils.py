from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone

from src.services.start_run_cache_key_utils import (
    base_cache_meta_matches,
    build_base_bars_cache_key,
    build_base_bars_meta,
    build_l2_enrich_cache_key,
    build_reference_bars_cache_key,
    build_reference_bars_meta,
    compute_l2_day_coverage,
    file_identity,
    reference_cache_meta_matches,
    select_best_superset_entry,
)


def test_file_identity_for_existing_file(tmp_path) -> None:
    sample = tmp_path / "sample.csv"
    sample.write_text("x", encoding="utf-8")

    resolved, mtime_ns, size = file_identity(str(sample))

    assert resolved.endswith("sample.csv")
    assert mtime_ns > 0
    assert size == 1


def test_build_base_bars_cache_key_is_stable_for_equivalent_inputs(tmp_path) -> None:
    sample = tmp_path / "a.csv"
    sample.write_text("x", encoding="utf-8")
    file_path = str(sample)

    key_a = build_base_bars_cache_key(
        ticker="mu",
        range_start="2026-02-01",
        range_end="2026-02-02",
        data_files=[file_path],
        time_filter_enabled=True,
        trading_hours=(9, 10, 11),
        regular_session_only=False,
    )
    key_b = build_base_bars_cache_key(
        ticker="MU",
        range_start="2026-02-01",
        range_end="2026-02-02",
        data_files=[file_path],
        time_filter_enabled=True,
        trading_hours=(9, 10, 11),
        regular_session_only=False,
    )

    assert key_a == key_b


def test_build_reference_bars_cache_key_uses_file_identity(tmp_path) -> None:
    sample = tmp_path / "ref.csv"
    sample.write_text("x", encoding="utf-8")

    key = build_reference_bars_cache_key(
        ticker="MU",
        range_start="2026-02-01",
        range_end="2026-02-01",
        ref_files=[str(sample)],
    )

    assert "MU" in key
    assert "ref.csv" in key


def test_compute_l2_day_coverage_reports_missing_days() -> None:
    bars = [
        {"timestamp": datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc)},
        {"timestamp": datetime(2026, 2, 4, 14, 30, tzinfo=timezone.utc)},
    ]
    minute_day1 = int(datetime(2026, 2, 3, 14, 30, tzinfo=timezone.utc).timestamp() // 60)
    coverage = compute_l2_day_coverage(
        bars=bars,
        feature_map={minute_day1: {"l2_delta": 1.0}},
        to_utc_datetime=lambda value: value,
    )

    assert coverage["bar_days"] == ["2026-02-03", "2026-02-04"]
    assert coverage["l2_days"] == ["2026-02-03"]
    assert coverage["missing_days"] == ["2026-02-04"]


def test_build_l2_enrich_cache_key_changes_when_bar_payload_changes() -> None:
    bars_a = [
        {
            "timestamp": "2026-02-03T14:30:00Z",
            "open": 100.0,
            "close": 101.0,
            "volume": 1000.0,
        }
    ]
    bars_b = [
        {
            "timestamp": "2026-02-03T14:30:00Z",
            "open": 100.0,
            "close": 102.0,
            "volume": 1000.0,
        }
    ]

    key_a = build_l2_enrich_cache_key(
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        requested_l2_only=False,
        requested_l2_confirm=True,
        comparable_mode=False,
        is_multi_day_request=False,
        bars=bars_a,
    )
    key_b = build_l2_enrich_cache_key(
        ticker="MU",
        range_start="2026-02-03",
        range_end="2026-02-03",
        requested_l2_only=False,
        requested_l2_confirm=True,
        comparable_mode=False,
        is_multi_day_request=False,
        bars=bars_b,
    )

    assert key_a != key_b


def test_select_best_superset_entry_prefers_smallest_covering_range() -> None:
    payload_store = OrderedDict(
        [
            ("wide", "payload-wide"),
            ("tight", "payload-tight"),
        ]
    )
    meta_store = {
        "wide": {"ticker": "MU", "range_start": "2026-02-01", "range_end": "2026-02-10"},
        "tight": {
            "ticker": "MU",
            "range_start": "2026-02-03",
            "range_end": "2026-02-06",
        },
    }

    selected = select_best_superset_entry(
        payload_store=payload_store,
        meta_store=meta_store,
        range_start="2026-02-04",
        range_end="2026-02-05",
        meta_matches=lambda meta: meta.get("ticker") == "MU",
    )

    assert selected == ("tight", "payload-tight", "2026-02-03", "2026-02-06")


def test_cache_meta_match_helpers() -> None:
    identities = (("/tmp/a.csv", 1, 2),)
    base_meta = build_base_bars_meta(
        ticker="MU",
        range_start="2026-02-01",
        range_end="2026-02-02",
        time_filter_enabled=True,
        trading_hours=(9, 10),
        regular_session_only=False,
        file_identities=identities,
    )
    ref_meta = build_reference_bars_meta(
        ticker="MU",
        range_start="2026-02-01",
        range_end="2026-02-02",
        file_identities=identities,
    )

    assert base_cache_meta_matches(
        meta=base_meta,
        ticker="MU",
        time_filter_enabled=True,
        trading_hours=(9, 10),
        regular_session_only=False,
        file_identities=identities,
    )
    assert reference_cache_meta_matches(
        meta=ref_meta,
        ticker="MU",
        file_identities=identities,
    )
