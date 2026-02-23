from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from src.services import strategy_api_updates_service as svc


class _DummyLogger:
    def warning(self, *args: Any, **kwargs: Any) -> None:
        return None


class _GetResponse:
    def __init__(self, payload: Dict[str, Any], status: int = 200):
        self._payload = payload
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def json(self) -> Dict[str, Any]:
        return dict(self._payload)


class _ClientSessionStub:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *args: Any, **kwargs: Any) -> _GetResponse:
        return _GetResponse(self._payload, status=200)


def test_apply_global_trailing_updates_global_exit_and_risk_fields(monkeypatch) -> None:
    captured_updates: List[Tuple[str, Dict[str, Any]]] = []

    async def _run_updates(
        *, strategy_api_url: str, updates: List[Tuple[str, Dict[str, Any]]]
    ):
        captured_updates.extend(updates)
        return [(name, 200, None) for name, _ in updates]

    monkeypatch.setattr(
        svc,
        "aiohttp",
        SimpleNamespace(
            ClientSession=lambda *args, **kwargs: _ClientSessionStub(
                {"momentum_flow": {}, "pullback": {}}
            )
        ),
    )
    monkeypatch.setattr(svc, "_run_strategy_updates", _run_updates)

    deps = SimpleNamespace(logger=_DummyLogger())
    asyncio.run(
        svc.apply_global_trailing(
            "http://localhost:8001",
            0.77,
            deps,
            global_exit_rr_ratio=1.9,
            global_risk_atr_stop_multiplier=0.72,
            global_risk_volume_stop_pct=0.84,
            global_risk_min_stop_loss_pct=0.06,
        )
    )

    assert len(captured_updates) == 2
    expected = {
        "global_trailing_stop_pct": 0.77,
        "global_rr_ratio": 1.9,
        "global_atr_stop_multiplier": 0.72,
        "global_volume_stop_pct": 0.84,
        "global_min_stop_loss_pct": 0.06,
    }
    assert captured_updates[0][1] == expected
    assert captured_updates[1][1] == expected
