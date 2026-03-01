from __future__ import annotations

from src.normalization import normalize_unified_profiles
from src.services.unified_profile_user_settings_service import (
    build_unified_profile_settings_patch,
    build_unified_profile_state_from_settings,
    merge_unified_profile_options_payload,
)


def test_build_unified_profile_state_from_settings_reads_ticker_state() -> None:
    settings = {
        "unified_profile_store": {
            "tickers": {
                "MU": {
                    "profiles": [
                        {"profile_id": "u1", "profile_name": "MU one"},
                        {"profile_id": "u2", "profile_name": "MU two"},
                    ],
                    "active_profile_id": "u2",
                }
            }
        }
    }

    state = build_unified_profile_state_from_settings(
        settings=settings,
        ticker="mu",
        normalize_unified_profiles=normalize_unified_profiles,
    )

    assert state["ticker"] == "MU"
    assert [row["profile_id"] for row in state["profiles"]] == ["u1", "u2"]
    assert state["active_profile_id"] == "u2"


def test_build_unified_profile_settings_patch_preserves_existing_store_keys() -> None:
    settings = {
        "run_config_draft": {"ticker": "MU"},
        "unified_profile_store": {
            "tickers": {
                "AAPL": {
                    "profiles": [{"profile_id": "a1", "profile_name": "AAPL one"}],
                    "active_profile_id": "a1",
                }
            },
            "meta": {"version": 1},
        },
    }

    patch = build_unified_profile_settings_patch(
        settings=settings,
        ticker="MU",
        profiles=[{"profile_id": "u1", "profile_name": "MU one"}],
        active_profile_id="u1",
    )

    store = patch["unified_profile_store"]
    assert store["meta"] == {"version": 1}
    assert store["tickers"]["AAPL"]["active_profile_id"] == "a1"
    assert store["tickers"]["MU"]["active_profile_id"] == "u1"
    assert store["tickers"]["MU"]["profiles"][0]["profile_id"] == "u1"


def test_merge_unified_profile_options_payload_prefers_user_profiles_and_keeps_legacy() -> None:
    payload = merge_unified_profile_options_payload(
        base_payload={
            "ticker": "MU",
            "active_profile_id": "legacy-unified-MU-combo-a-tuned-a",
            "profiles": [
                {
                    "profile_id": "legacy-unified-MU-combo-a-tuned-a",
                    "profile_name": "Legacy A",
                },
                {
                    "profile_id": "legacy-unified-MU-combo-b-tuned-a",
                    "profile_name": "Legacy B",
                },
                {"profile_id": "json-u1", "profile_name": "JSON stale"},
            ],
        },
        user_profiles=[
            {"profile_id": "db-u1", "profile_name": "DB one"},
            {"profile_id": "db-u2", "profile_name": "DB two"},
        ],
        user_active_profile_id="db-u2",
    )

    assert payload["active_profile_id"] == "db-u2"
    ids = [str(row.get("profile_id") or "") for row in payload["profiles"]]
    assert ids[:2] == ["db-u1", "db-u2"]
    assert "legacy-unified-MU-combo-a-tuned-a" in ids
    assert "legacy-unified-MU-combo-b-tuned-a" in ids
    assert "json-u1" not in ids
