from __future__ import annotations

from pathlib import Path

import strategy_api_auth_headers as auth_headers


def _clear_token_env(monkeypatch) -> None:
    for key in (
        "BACKTEST_STRATEGY_INTERNAL_API_TOKEN",
        "STRATEGY_INTERNAL_API_TOKEN",
        "BACKTEST_STRATEGY_INTERNAL_API_ENV_FILES",
        "BACKTEST_STRATEGY_LOCAL_DEV_TOKEN_FALLBACK",
        "BACKTEST_STRATEGY_LOCAL_DEV_INTERNAL_API_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    auth_headers._resolve_token_from_env_files.cache_clear()


def test_build_strategy_api_headers_prefers_explicit_env(monkeypatch):
    _clear_token_env(monkeypatch)
    monkeypatch.setenv("BACKTEST_STRATEGY_INTERNAL_API_TOKEN", "explicit-token")

    headers = auth_headers.build_strategy_api_headers("http://127.0.0.1:8001")

    assert headers == {"x-internal-token": "explicit-token"}


def test_build_strategy_api_headers_reads_token_from_env_file(monkeypatch, tmp_path: Path):
    _clear_token_env(monkeypatch)
    env_file = tmp_path / "strategy.env"
    env_file.write_text("STRATEGY_INTERNAL_API_TOKEN=file-token\n", encoding="utf-8")
    monkeypatch.setenv("BACKTEST_STRATEGY_INTERNAL_API_ENV_FILES", str(env_file))
    auth_headers._resolve_token_from_env_files.cache_clear()

    headers = auth_headers.build_strategy_api_headers("http://localhost:8001")

    assert headers == {"x-internal-token": "file-token"}


def test_build_strategy_api_headers_uses_local_dev_fallback(monkeypatch):
    _clear_token_env(monkeypatch)

    headers = auth_headers.build_strategy_api_headers("http://localhost:8001")

    assert headers == {"x-internal-token": "dev-internal-token"}


def test_build_strategy_api_headers_skips_local_fallback_for_remote(monkeypatch):
    _clear_token_env(monkeypatch)

    headers = auth_headers.build_strategy_api_headers("https://strategy.example.com")

    assert headers == {}
