from __future__ import annotations

from src.normalization import normalize_unified_profiles
from src.routes.unified_profile_user_store import (
    migrate_ticker_profiles_from_json_if_needed,
)
from src.security.auth import AuthContext


class _StubSettingsStore:
    def __init__(self):
        self._settings_by_user = {}

    def get_user_settings(self, *, user_id: str):
        return dict(self._settings_by_user.get(user_id, {}))

    def merge_user_settings(self, *, user_id: str, tenant_id: str, patch: dict):
        current = dict(self._settings_by_user.get(user_id, {}))
        current.update(dict(patch or {}))
        self._settings_by_user[user_id] = current
        return current


def test_migrate_ticker_profiles_from_json_if_needed_bootstraps_missing_ticker() -> None:
    auth = AuthContext(
        user_id="user-1",
        tenant_id="tenant-1",
        role="admin",
        plan_tier="admin",
        email=None,
        claims={},
    )
    store = _StubSettingsStore()

    migrate_ticker_profiles_from_json_if_needed(
        auth=auth,
        settings_store=store,
        ticker="MU",
        load_aos_config=lambda: {
            "tickers": {
                "MU": {
                    "unified_profiles": [
                        {"profile_id": "u1", "profile_name": "From JSON"}
                    ],
                    "active_unified_profile_id": "u1",
                }
            }
        },
        normalize_unified_profiles=normalize_unified_profiles,
    )

    settings = store.get_user_settings(user_id="user-1")
    ticker_state = (
        settings.get("unified_profile_store", {}).get("tickers", {}).get("MU", {})
    )
    assert ticker_state.get("active_profile_id") == "u1"
    assert ticker_state.get("profiles", [{}])[0].get("profile_id") == "u1"


def test_migrate_ticker_profiles_from_json_if_needed_does_not_overwrite_existing_db_state() -> None:
    auth = AuthContext(
        user_id="user-1",
        tenant_id="tenant-1",
        role="admin",
        plan_tier="admin",
        email=None,
        claims={},
    )
    store = _StubSettingsStore()
    store.merge_user_settings(
        user_id="user-1",
        tenant_id="tenant-1",
        patch={
            "unified_profile_store": {
                "tickers": {
                    "MU": {
                        "profiles": [{"profile_id": "db-u1", "profile_name": "DB"}],
                        "active_profile_id": "db-u1",
                    }
                }
            }
        },
    )

    migrate_ticker_profiles_from_json_if_needed(
        auth=auth,
        settings_store=store,
        ticker="MU",
        load_aos_config=lambda: {
            "tickers": {
                "MU": {
                    "unified_profiles": [
                        {"profile_id": "json-u1", "profile_name": "JSON"}
                    ],
                    "active_unified_profile_id": "json-u1",
                }
            }
        },
        normalize_unified_profiles=normalize_unified_profiles,
    )

    settings = store.get_user_settings(user_id="user-1")
    ticker_state = (
        settings.get("unified_profile_store", {}).get("tickers", {}).get("MU", {})
    )
    assert ticker_state.get("active_profile_id") == "db-u1"
    assert ticker_state.get("profiles", [{}])[0].get("profile_id") == "db-u1"
