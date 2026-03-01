from __future__ import annotations

import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import aiohttp
import httpx

_INPROCESS_TRANSPORT_VALUES = {"inprocess", "local"}
_HTTP_TRANSPORT_VALUES = {"http", "network"}
_INPROCESS_SCHEMES = {"inprocess"}
_INPROCESS_HOSTS = {
    "inprocess",
    "strategy-inprocess",
    "strategy-local",
    "local-strategy",
}
_INPROCESS_BASE_URL = "http://strategy-inprocess.local"
_INPROCESS_SERVER_MODULE_NAME = "_backtest_strategy_api_inprocess_server"


def _env_transport_mode() -> str:
    return str(os.getenv("BACKTEST_STRATEGY_API_TRANSPORT", "") or "").strip().lower()


def _looks_like_url(raw_value: str) -> bool:
    return "://" in raw_value


def is_inprocess_strategy_url(strategy_api_url: Optional[str]) -> bool:
    mode = _env_transport_mode()
    if mode in _INPROCESS_TRANSPORT_VALUES:
        return True
    if mode in _HTTP_TRANSPORT_VALUES:
        return False

    raw = str(strategy_api_url or "").strip()
    if not raw:
        return False
    if raw.lower() in _INPROCESS_TRANSPORT_VALUES:
        return True

    parsed = urlparse(raw if _looks_like_url(raw) else f"http://{raw}")
    if str(parsed.scheme or "").lower() in _INPROCESS_SCHEMES:
        return True
    host = str(parsed.hostname or "").strip().lower()
    return host in _INPROCESS_HOSTS


def normalize_strategy_api_base_url(strategy_api_url: Optional[str]) -> str:
    raw = str(strategy_api_url or "").strip()
    if is_inprocess_strategy_url(raw):
        return _INPROCESS_BASE_URL
    if not raw:
        return "http://localhost:8001"
    return raw.rstrip("/")


def _candidate_inprocess_server_paths() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    return [
        repo_root.parent / "market_regime_detection" / "api_server.py",
        repo_root.parent / "market-regime-detection" / "api_server.py",
    ]


def _load_inprocess_strategy_app() -> Any:
    loaded = sys.modules.get(_INPROCESS_SERVER_MODULE_NAME)
    if loaded is not None:
        app = getattr(loaded, "app", None)
        if app is not None:
            return app

    server_path = next(
        (path for path in _candidate_inprocess_server_paths() if path.exists()),
        None,
    )
    if server_path is None:
        raise RuntimeError(
            "In-process strategy API requested but sibling api_server.py was not found."
        )

    spec = importlib.util.spec_from_file_location(
        _INPROCESS_SERVER_MODULE_NAME,
        str(server_path),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load in-process strategy API module spec.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[_INPROCESS_SERVER_MODULE_NAME] = module
    spec.loader.exec_module(module)
    app = getattr(module, "app", None)
    if app is None:
        raise RuntimeError("In-process strategy API module does not expose FastAPI app.")
    return app


class _HttpxResponseShim:
    def __init__(self, response: httpx.Response):
        self._response = response
        self.status = int(response.status_code)

    async def json(self) -> Any:
        return self._response.json()

    async def text(self) -> str:
        return str(self._response.text or "")


class _HttpxRequestContext:
    def __init__(self, request_coro: Any):
        self._request_coro = request_coro
        self._response: Optional[httpx.Response] = None

    async def __aenter__(self) -> _HttpxResponseShim:
        self._response = await self._request_coro
        return _HttpxResponseShim(self._response)

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class StrategyApiSession:
    def __init__(
        self,
        *,
        base_url: str,
        aiohttp_session: Optional[aiohttp.ClientSession] = None,
        httpx_client: Optional[httpx.AsyncClient] = None,
    ):
        self._base_url = str(base_url).rstrip("/")
        self._aiohttp_session = aiohttp_session
        self._httpx_client = httpx_client

    def _resolve_url(self, url: str) -> str:
        raw = str(url or "").strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        if raw.startswith("/"):
            return f"{self._base_url}{raw}"
        return f"{self._base_url}/{raw}"

    def get(self, url: str, **kwargs: Any) -> Any:
        target_url = self._resolve_url(url)
        if self._aiohttp_session is not None:
            return self._aiohttp_session.get(target_url, **kwargs)
        assert self._httpx_client is not None
        return _HttpxRequestContext(
            self._httpx_client.get(target_url, **kwargs)
        )

    def post(self, url: str, **kwargs: Any) -> Any:
        target_url = self._resolve_url(url)
        if self._aiohttp_session is not None:
            return self._aiohttp_session.post(target_url, **kwargs)
        assert self._httpx_client is not None
        return _HttpxRequestContext(
            self._httpx_client.post(target_url, **kwargs)
        )

    def delete(self, url: str, **kwargs: Any) -> Any:
        target_url = self._resolve_url(url)
        if self._aiohttp_session is not None:
            return self._aiohttp_session.delete(target_url, **kwargs)
        assert self._httpx_client is not None
        return _HttpxRequestContext(
            self._httpx_client.delete(target_url, **kwargs)
        )


@asynccontextmanager
async def open_strategy_api_session(
    *,
    strategy_api_url: str,
    timeout_seconds: float,
    connect_timeout_seconds: float = 3.0,
) -> Any:
    base_url = normalize_strategy_api_base_url(strategy_api_url)
    timeout_total = max(0.1, float(timeout_seconds))
    connect_timeout = min(timeout_total, max(0.1, float(connect_timeout_seconds)))

    if is_inprocess_strategy_url(strategy_api_url):
        timeout = httpx.Timeout(timeout=timeout_total, connect=connect_timeout)
        transport = httpx.ASGITransport(app=_load_inprocess_strategy_app())
        async with httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            base_url=base_url,
        ) as client:
            yield StrategyApiSession(base_url=base_url, httpx_client=client)
        return

    timeout = aiohttp.ClientTimeout(total=timeout_total, connect=connect_timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        yield StrategyApiSession(base_url=base_url, aiohttp_session=session)


def build_httpx_client_kwargs(strategy_api_url: str) -> Dict[str, Any]:
    base_url = normalize_strategy_api_base_url(strategy_api_url)
    kwargs: Dict[str, Any] = {"base_url": base_url}
    if is_inprocess_strategy_url(strategy_api_url):
        kwargs["transport"] = httpx.ASGITransport(app=_load_inprocess_strategy_app())
    return kwargs

