from __future__ import annotations

import pytest

from src.services.saas_adaptive_profile_utils import (
    build_adaptive_strategy_profile_record,
    build_list_adaptive_strategy_profiles_query,
    normalize_profile_scope,
)
from src.services.saas_service import SaaSStateStore


def test_normalize_profile_scope_accepts_supported_values() -> None:
    assert normalize_profile_scope(" user ") == "user"
    assert normalize_profile_scope("GLOBAL") == "global"


def test_normalize_profile_scope_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="scope must be 'user' or 'global'"):
        normalize_profile_scope("tenant")


def test_build_adaptive_strategy_profile_record_normalizes_user_scope() -> None:
    record = build_adaptive_strategy_profile_record(
        profile_id=" asp-1 ",
        scope=" user ",
        owner_user_id=" user-1 ",
        owner_tenant_id=" tenant-1 ",
        ticker=" mu ",
        profile_name=" Trend ",
        adaptive_version=0,
        candidate={"alpha": 1},
        metadata=["ignored"],
    )

    assert record == {
        "profile_id": "asp-1",
        "scope": "user",
        "owner_user_id": "user-1",
        "owner_tenant_id": "tenant-1",
        "ticker": "MU",
        "profile_name": "Trend",
        "adaptive_version": 1,
        "candidate": {"alpha": 1},
        "metadata": {},
    }


def test_build_adaptive_strategy_profile_record_global_scope_clears_owners() -> None:
    record = build_adaptive_strategy_profile_record(
        profile_id=None,
        scope="global",
        owner_user_id="user-1",
        owner_tenant_id="tenant-1",
        ticker="spy",
        profile_name="Global",
        adaptive_version=2,
        candidate=None,
        metadata={"source": "test"},
    )

    assert record["profile_id"].startswith("asp_")
    assert record["scope"] == "global"
    assert record["owner_user_id"] is None
    assert record["owner_tenant_id"] is None
    assert record["candidate"] == {}
    assert record["metadata"] == {"source": "test"}


def test_build_adaptive_strategy_profile_record_requires_owner_for_user_scope() -> None:
    with pytest.raises(
        ValueError,
        match="user scope profile requires owner_user_id and owner_tenant_id",
    ):
        build_adaptive_strategy_profile_record(
            profile_id=None,
            scope="user",
            owner_user_id="user-1",
            owner_tenant_id=" ",
            ticker="MU",
            profile_name="Missing Tenant",
            adaptive_version=1,
            candidate=None,
            metadata=None,
        )


def test_build_list_adaptive_strategy_profiles_query_requires_visibility() -> None:
    payload = build_list_adaptive_strategy_profiles_query(
        user_id="user-1",
        tenant_id="tenant-1",
        include_user=False,
        include_global=False,
    )

    assert payload is None


def test_build_list_adaptive_strategy_profiles_query_builds_expected_filters() -> None:
    payload = build_list_adaptive_strategy_profiles_query(
        user_id=" user-1 ",
        tenant_id=" tenant-1 ",
        ticker=" mu ",
    )
    assert payload is not None
    query, args = payload

    assert (
        query
        == "SELECT * FROM adaptive_strategy_profiles WHERE ((scope = 'user' AND owner_user_id = ? AND owner_tenant_id = ?) OR (scope = 'global')) AND ticker = ? ORDER BY CASE WHEN scope = 'global' THEN 0 ELSE 1 END, updated_at DESC, profile_id ASC"
    )
    assert args == ("user-1", "tenant-1", "MU")


def test_store_adaptive_profile_round_trip_uses_extracted_helpers(tmp_path) -> None:
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))

    saved = store.upsert_adaptive_strategy_profile(
        profile_id=None,
        scope="user",
        owner_user_id="user-1",
        owner_tenant_id="tenant-1",
        ticker="mu",
        profile_name="Intraday",
        adaptive_version=3,
        candidate={"signal": "strong"},
        metadata={"source": "unit-test"},
    )

    profiles = store.list_adaptive_strategy_profiles(
        user_id="user-1",
        tenant_id="tenant-1",
        ticker="MU",
    )

    assert saved["scope"] == "user"
    assert saved["ticker"] == "MU"
    assert saved["candidate"] == {"signal": "strong"}
    assert [profile["profile_id"] for profile in profiles] == [saved["profile_id"]]
