from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from src.models.run_requests import StartRunRequest
from src.runtime_mode import (
    is_serverless_environment,
    stateful_run_api_supported,
)
from src.services.run_registry import RunRegistry
from src.services.start_run_service import start_run


def _clear_serverless_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "VERCEL",
        "AWS_LAMBDA_FUNCTION_NAME",
        "NOW_REGION",
    ):
        monkeypatch.delenv(key, raising=False)


def test_runtime_mode_defaults_to_stateful(monkeypatch: pytest.MonkeyPatch):
    _clear_serverless_env(monkeypatch)
    assert is_serverless_environment() is False
    assert stateful_run_api_supported() is True


def test_runtime_mode_blocks_stateful_run_api_on_serverless_by_default(
    monkeypatch: pytest.MonkeyPatch,
):
    _clear_serverless_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    assert is_serverless_environment() is True
    assert stateful_run_api_supported() is False


def test_runtime_mode_does_not_allow_serverless_override_env(
    monkeypatch: pytest.MonkeyPatch,
):
    _clear_serverless_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    assert is_serverless_environment() is True
    assert stateful_run_api_supported() is False


def test_run_registry_returns_503_when_serverless_guard_is_active(
    monkeypatch: pytest.MonkeyPatch,
):
    _clear_serverless_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    registry = RunRegistry({})
    with pytest.raises(HTTPException) as exc:
        registry.require("r1", "MU", "2026-02-13")

    assert exc.value.status_code == 503
    assert "Stateful /api/run playback endpoints are disabled" in str(exc.value.detail)


def test_run_registry_returns_404_when_stateful_mode_is_supported(
    monkeypatch: pytest.MonkeyPatch,
):
    _clear_serverless_env(monkeypatch)

    registry = RunRegistry({})
    with pytest.raises(HTTPException) as exc:
        registry.require("r1", "MU", "2026-02-13")

    assert exc.value.status_code == 404
    assert "Run not found: r1:MU:2026-02-13" in str(exc.value.detail)


def test_start_run_rejects_serverless_when_guard_active(
    monkeypatch: pytest.MonkeyPatch,
):
    _clear_serverless_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")

    request = StartRunRequest(
        run_id="r1",
        ticker="MU",
        date="2026-02-13",
        strategy_api_url="http://localhost:8001",
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(start_run(request, deps=None))

    assert exc.value.status_code == 503
    assert "Stateful /api/run playback endpoints are disabled" in str(exc.value.detail)
