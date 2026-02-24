from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Tuple

import pytest
from fastapi import HTTPException

from src.services import run_control_service
from src.services.run_control_service import RunControlDeps, evaluate_intrabar_slice


@dataclass
class _DummyConfig:
    run_id: str = "run-123"
    ticker: str = "NVDA"
    strategy_api_url: str = "http://localhost:8001"


class _FakeResponse:
    def __init__(self, status: int, payload: Any = None, text_value: str = "") -> None:
        self.status = status
        self._payload = payload if payload is not None else {}
        self._text_value = text_value

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return self._text_value


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[Tuple[str, Dict[str, Any]]] = []
        self.closed = False

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self._response


class _DummyRunner:
    def __init__(self, session: _FakeSession) -> None:
        self.config = _DummyConfig()
        self._session = session

    async def _get_strategy_http_session(self):
        return self._session


class _DummyRegistry:
    def __init__(self, runner: _DummyRunner) -> None:
        self.runner = runner

    def require(self, run_id: str, ticker: str, date: str):
        _ = run_id, ticker, date
        return "run-123:NVDA:2026-02-04", self.runner


def _build_deps(runner: _DummyRunner) -> RunControlDeps:
    async def _noop(*args, **kwargs):
        _ = args, kwargs
        return None

    return RunControlDeps(
        run_registry=_DummyRegistry(runner),
        active_runners={},
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        reports_dir=Path("."),
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_noop,
        configure_session=_noop,
    )


def _valid_intrabar_payload() -> Dict[str, Any]:
    return {
        "run_id": "ignored-run",
        "ticker": "ignored-ticker",
        "timestamp": "2026-02-04T19:21:59Z",
        "open": 100.0,
        "high": 101.0,
        "low": 99.5,
        "close": 100.8,
        "volume": 1200.0,
        "intrabar_quotes_1s": [{"s": "2026-02-04T19:21:55Z", "bid": 100.7, "ask": 100.9}],
    }


def test_evaluate_intrabar_slice_proxies_payload_and_headers(monkeypatch):
    monkeypatch.setattr(
        run_control_service,
        "build_strategy_api_headers",
        lambda strategy_api_url=None: {"x-internal-token": "secret-token"},
    )
    fake_session = _FakeSession(_FakeResponse(200, payload={"ok": True}))
    deps = _build_deps(_DummyRunner(fake_session))

    result = asyncio.run(
        evaluate_intrabar_slice(
            "external-run", "MU", "2026-02-04", _valid_intrabar_payload(), deps
        )
    )

    assert result == {"ok": True}
    assert len(fake_session.calls) == 1
    url, kwargs = fake_session.calls[0]
    assert url == "http://localhost:8001/api/session/intrabar_eval"
    assert kwargs["headers"] == {"x-internal-token": "secret-token"}
    assert kwargs["json"]["run_id"] == "run-123"
    assert kwargs["json"]["ticker"] == "NVDA"


def test_evaluate_intrabar_slice_surfaces_strategy_error():
    fake_session = _FakeSession(_FakeResponse(422, text_value="invalid bar payload"))
    deps = _build_deps(_DummyRunner(fake_session))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            evaluate_intrabar_slice(
                "run-1", "MU", "2026-02-04", _valid_intrabar_payload(), deps
            )
        )

    assert exc.value.status_code == 422
    assert "invalid bar payload" in str(exc.value.detail)


def test_evaluate_intrabar_slice_requires_core_bar_fields():
    fake_session = _FakeSession(_FakeResponse(200, payload={"ok": True}))
    deps = _build_deps(_DummyRunner(fake_session))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            evaluate_intrabar_slice(
                "run-1",
                "MU",
                "2026-02-04",
                {"open": 100.0, "high": 101.0},
                deps,
            )
        )

    assert exc.value.status_code == 400
    assert "timestamp" in str(exc.value.detail)
