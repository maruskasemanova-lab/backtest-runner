from __future__ import annotations

from src.services.heatmap_memory_zone_service import build_heatmap_memory_catalog


class _StateStore:
    def __init__(self, rows):
        self.rows = list(rows)

    def list_daily_price_heatmap_rows(
        self,
        *,
        ticker: str,
        date_from: str,
        date_to: str,
        bin_size: float,
    ):
        assert ticker == "MU"
        assert float(bin_size) == 0.5
        return [
            row for row in self.rows
            if date_from <= str(row.get("as_of_date")) <= date_to
        ]


def test_build_heatmap_memory_catalog_creates_hvn_and_lvn_zones_from_prior_day() -> None:
    rows = [
        {
            "as_of_date": "2026-02-18",
            "price_bin": price,
            "cumulative_bar_share": bar_share,
            "cumulative_volume_share": volume_share,
        }
        for price, bar_share, volume_share in [
            (100.0, 0.02, 0.02),
            (100.5, 0.03, 0.03),
            (101.0, 0.08, 0.08),
            (101.5, 0.03, 0.03),
            (102.0, 0.02, 0.02),
            (102.5, 0.01, 0.01),
            (103.0, 0.005, 0.005),
            (103.5, 0.01, 0.01),
            (104.0, 0.02, 0.02),
            (104.5, 0.03, 0.03),
            (105.0, 0.07, 0.07),
            (105.5, 0.03, 0.03),
            (106.0, 0.02, 0.02),
        ]
    ]
    bars = [
        {
            "timestamp": "2026-02-19T14:30:00Z",
            "open": 103.0,
            "close": 103.2,
        }
    ]

    catalog = build_heatmap_memory_catalog(
        ticker="MU",
        bars=bars,
        state_store=_StateStore(rows),
        max_distance_pct=15.0,
        max_hvn_zones=3,
        max_lvn_zones=2,
    )

    assert catalog is not None
    day_payload = catalog["days"]["2026-02-19"]
    assert day_payload["source_as_of_date"] == "2026-02-18"

    zones = list(day_payload["zones"])
    assert any(zone["zone_type"] == "HVN" and zone["peak_price"] == 101.0 for zone in zones)
    assert any(zone["zone_type"] == "HVN" and zone["peak_price"] == 105.0 for zone in zones)
    assert any(zone["zone_type"] == "LVN" and zone["peak_price"] == 103.0 for zone in zones)


def test_build_heatmap_memory_catalog_never_uses_same_day_rows() -> None:
    rows = [
        {
            "as_of_date": "2026-02-19",
            "price_bin": 103.0,
            "cumulative_bar_share": 0.09,
            "cumulative_volume_share": 0.09,
        }
    ]
    bars = [
        {
            "timestamp": "2026-02-19T14:30:00Z",
            "open": 103.0,
            "close": 103.2,
        }
    ]

    catalog = build_heatmap_memory_catalog(
        ticker="MU",
        bars=bars,
        state_store=_StateStore(rows),
    )

    assert catalog is None
