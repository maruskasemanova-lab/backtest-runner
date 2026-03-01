from __future__ import annotations

from src.services.strategy_api_transport import (
    is_inprocess_strategy_url,
    normalize_strategy_api_base_url,
)


def test_inprocess_strategy_url_detection_from_env(monkeypatch) -> None:
    monkeypatch.setenv("BACKTEST_STRATEGY_API_TRANSPORT", "inprocess")
    assert is_inprocess_strategy_url("http://localhost:8001") is True
    assert (
        normalize_strategy_api_base_url("http://localhost:8001")
        == "http://strategy-inprocess.local"
    )


def test_inprocess_strategy_url_detection_from_url() -> None:
    assert is_inprocess_strategy_url("inprocess://strategy") is True
    assert is_inprocess_strategy_url("http://inprocess") is True
    assert normalize_strategy_api_base_url("inprocess://strategy").startswith(
        "http://strategy-inprocess."
    )

