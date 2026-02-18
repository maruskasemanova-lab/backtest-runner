from __future__ import annotations

import pytest

from src.security.network_policy import (
    StrategyApiPolicyError,
    enforce_strategy_url_policy,
    normalize_base_url,
)


def test_normalize_base_url_rejects_invalid_scheme():
    with pytest.raises(StrategyApiPolicyError):
        normalize_base_url("ftp://localhost:8001")


def test_non_admin_strategy_url_forced_to_internal():
    resolved = enforce_strategy_url_policy(
        "http://evil.internal:9000",
        is_admin=False,
        internal_url="http://strategy-internal:8001",
    )
    assert resolved == "http://strategy-internal:8001"


def test_admin_strategy_url_allowed_from_allowlist(monkeypatch):
    monkeypatch.setenv(
        "BACKTEST_STRATEGY_API_ALLOWLIST",
        "http://strategy-internal:8001,http://localhost:8001",
    )
    resolved = enforce_strategy_url_policy(
        "http://localhost:8001",
        is_admin=True,
        internal_url="http://strategy-internal:8001",
    )
    assert resolved == "http://localhost:8001"


def test_admin_strategy_url_denied_when_not_in_allowlist(monkeypatch):
    monkeypatch.setenv(
        "BACKTEST_STRATEGY_API_ALLOWLIST",
        "http://strategy-internal:8001,http://localhost:8001",
    )
    with pytest.raises(StrategyApiPolicyError):
        enforce_strategy_url_policy(
            "http://169.254.169.254:80",
            is_admin=True,
            internal_url="http://strategy-internal:8001",
        )
