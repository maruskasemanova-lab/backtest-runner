from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from src.models.run_requests import StartRunRequest
from src.services import strategy_api_session_service as svc


class _DummyLogger:
    def warning(self, *args: Any, **kwargs: Any) -> None:
        return None


class _PostResponse:
    def __init__(self, *, status: int = 200):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self) -> str:
        return ""


class _ClientSessionStub:
    def __init__(self, captured: Dict[str, Any]):
        self._captured = captured

    def post(self, url: str, **kwargs: Any) -> _PostResponse:
        self._captured["url"] = url
        self._captured["params"] = dict(kwargs.get("params") or {})
        self._captured["headers"] = dict(kwargs.get("headers") or {})
        return _PostResponse(status=200)


class _SessionContext:
    def __init__(self, captured: Dict[str, Any]):
        self._captured = captured

    async def __aenter__(self) -> _ClientSessionStub:
        return _ClientSessionStub(self._captured)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def test_configure_session_forwards_extra_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: Dict[str, Any] = {}

    def _open_session(**kwargs: Any) -> _SessionContext:
        _ = kwargs
        return _SessionContext(captured)

    monkeypatch.setattr(svc, "open_strategy_api_session", _open_session)
    request = StartRunRequest(
        run_id="cfg-session",
        ticker="MU",
        date="2026-02-10",
        partial_protect_min_mfe_r=0.0,
        context_aware_risk_enabled=True,
        intraday_levels_spike_detection_enabled=True,
        strategy_selection_mode="adaptive_top_n",
        max_active_strategies=3,
    )
    payload = request.model_dump()
    payload.pop("strategy_api_url", None)

    deps = SimpleNamespace(logger=_DummyLogger())
    asyncio.run(
        svc.configure_session(
            strategy_api_url="http://localhost:8001",
            deps=deps,
            momentum_diversification_json=None,
            extra_blob={"mode": "test"},
            **payload,
        )
    )

    params = captured.get("params") or {}
    assert captured.get("url") == "http://localhost:8001/api/session/config"
    assert params.get("intraday_levels_spike_detection_enabled") == 1
    assert params.get("context_aware_risk_enabled") == 1
    assert params.get("context_risk_min_sl_pct") == 0.5
    assert params.get("context_risk_min_room_pct") == 0.08
    assert params.get("extra_blob") == '{"mode":"test"}'
