from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib.parse import urlparse

_TOKEN_ENV_KEYS = (
    "BACKTEST_STRATEGY_INTERNAL_API_TOKEN",
    "STRATEGY_INTERNAL_API_TOKEN",
)
_LOCAL_STRATEGY_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "strategy-api",
    "::1",
    "inprocess",
    "strategy-inprocess",
    "strategy-inprocess.local",
}


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _strip_env_value(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    if " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def _read_env_key_from_file(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    prefix = f"{key}="
    for line in lines:
        stripped = str(line or "").strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if not stripped.startswith(prefix):
            continue
        return _strip_env_value(stripped[len(prefix) :])
    return ""


def _iter_configured_env_paths() -> Iterable[Path]:
    configured = str(
        os.getenv("BACKTEST_STRATEGY_INTERNAL_API_ENV_FILES") or ""
    ).strip()
    if configured:
        for raw in configured.split(","):
            token = str(raw or "").strip()
            if token:
                yield Path(token).expanduser()
        return

    repo_root = Path(__file__).resolve().parent
    yield repo_root / ".env"
    yield repo_root.parent / "market_regime_detection" / ".env"


@lru_cache(maxsize=1)
def _resolve_token_from_env_files() -> str:
    for path in _iter_configured_env_paths():
        for key in _TOKEN_ENV_KEYS:
            token = _read_env_key_from_file(path, key)
            if token:
                return token
    return ""


def _resolve_token_from_env() -> str:
    for key in _TOKEN_ENV_KEYS:
        token = str(os.getenv(key) or "").strip()
        if token:
            return token
    return ""


def _is_local_strategy_api_url(strategy_api_url: Optional[str]) -> bool:
    raw_url = str(strategy_api_url or "").strip()
    if not raw_url:
        return False
    try:
        parsed = urlparse(raw_url)
    except ValueError:
        return False
    host = str(parsed.hostname or "").strip().lower()
    return host in _LOCAL_STRATEGY_HOSTS


def resolve_strategy_internal_api_token(strategy_api_url: Optional[str] = None) -> str:
    token = _resolve_token_from_env()
    if token:
        return token

    token = _resolve_token_from_env_files()
    if token:
        return token

    local_dev_fallback_enabled = _parse_bool_env(
        "BACKTEST_STRATEGY_LOCAL_DEV_TOKEN_FALLBACK",
        True,
    )
    if local_dev_fallback_enabled and _is_local_strategy_api_url(strategy_api_url):
        return str(
            os.getenv("BACKTEST_STRATEGY_LOCAL_DEV_INTERNAL_API_TOKEN")
            or "dev-internal-token"
        ).strip()
    return ""


def build_strategy_api_headers(
    strategy_api_url: Optional[str] = None,
) -> Dict[str, str]:
    token = resolve_strategy_internal_api_token(strategy_api_url)
    if not token:
        return {}
    return {"x-internal-token": token}
