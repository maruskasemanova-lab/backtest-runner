from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from fastapi.encoders import jsonable_encoder

from src.services.run_control_service import RunControlDeps, get_processed_bars


class _DummyRunner:
    def __init__(self) -> None:
        self.current_bar_index = 1
        self.bars = [object(), object()]

    def get_processed_bars(self):
        return [
            {
                "timestamp": np.datetime64("2026-02-13T14:31:00"),
                "open": np.float64(100.0),
                "close": np.float64(101.25),
                "sizes": np.array([1, 2, 3], dtype=np.int64),
                "nested": {"day": np.datetime64("2026-02-13")},
            }
        ]


class _DummyRegistry:
    def __init__(self, runner: _DummyRunner) -> None:
        self._runner = runner

    def require(self, run_id: str, ticker: str, date: str):
        return f"{run_id}:{ticker}:{date}", self._runner


def _build_deps(runner: _DummyRunner) -> RunControlDeps:
    async def _noop(*args, **kwargs):
        return None

    return RunControlDeps(
        run_registry=_DummyRegistry(runner),
        active_runners={},
        marker_type_enum=None,
        logger=SimpleNamespace(error=lambda *args, **kwargs: None),
        save_remote_checkpoint=_noop,
        clear_remote_strategy_sessions=_noop,
        configure_session=_noop,
    )


def test_get_processed_bars_normalizes_numpy_values_for_json() -> None:
    runner = _DummyRunner()
    deps = _build_deps(runner)

    payload = get_processed_bars("r1", "MU", "2026-02-13", deps)

    assert payload["current_index"] == 1
    assert payload["total_bars"] == 2
    assert payload["bars"][0]["timestamp"].startswith("2026-02-13T14:31:00")
    assert payload["bars"][0]["close"] == 101.25
    assert payload["bars"][0]["sizes"] == [1, 2, 3]
    assert payload["bars"][0]["nested"]["day"] == "2026-02-13"

    encoded = jsonable_encoder(payload)
    assert encoded["bars"][0]["nested"]["day"] == "2026-02-13"
