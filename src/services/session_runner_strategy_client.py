import asyncio
import inspect
import os
from typing import Any, Callable, Dict, Optional

import httpx

from src.services.strategy_api_transport import (
    build_httpx_client_kwargs,
    normalize_strategy_api_base_url,
)


class StrategyApiClient:
    def __init__(
        self,
        *,
        strategy_api_url: str,
        headers_factory: Callable[[], Dict[str, str]],
        session_factory: Callable[..., Any],
    ):
        self._strategy_api_target = str(strategy_api_url or "").strip()
        self._strategy_api_url = normalize_strategy_api_base_url(strategy_api_url)
        self._headers_factory = headers_factory
        self._session_factory = session_factory
        self._session: Optional[Any] = None
        self._session_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def session(self) -> Optional[Any]:
        return self._session

    @property
    def session_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        return self._session_loop

    @staticmethod
    def session_is_closed(session: Any) -> bool:
        return bool(getattr(session, "is_closed", getattr(session, "closed", False)))

    @staticmethod
    def response_status_code(response: Any) -> int:
        return int(
            getattr(response, "status_code", getattr(response, "status", 0)) or 0
        )

    @staticmethod
    async def response_text(response: Any) -> str:
        text_attr = getattr(response, "text", "")
        if callable(text_attr):
            text_attr = text_attr()
        if inspect.isawaitable(text_attr):
            text_attr = await text_attr
        return str(text_attr or "")

    @staticmethod
    async def response_json(response: Any) -> Any:
        json_attr = getattr(response, "json", None)
        if callable(json_attr):
            json_attr = json_attr()
        if inspect.isawaitable(json_attr):
            json_attr = await json_attr
        return json_attr

    @staticmethod
    async def maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def is_transport_error(exc: Exception) -> bool:
        return isinstance(exc, (httpx.HTTPError, OSError, asyncio.TimeoutError))

    async def get_session(self) -> Any:
        current_loop = asyncio.get_running_loop()
        if self._session is not None and not self.session_is_closed(self._session):
            if self._session_loop is current_loop:
                return self._session
            await self.close()

        try:
            timeout_total = float(
                os.getenv("BACKTEST_STRATEGY_API_TIMEOUT_SECONDS", "6.0")
            )
        except (TypeError, ValueError):
            timeout_total = 6.0

        try:
            timeout = httpx.Timeout(
                timeout=max(0.1, timeout_total),
                connect=3.0,
            )
            self._session = self._session_factory(
                timeout=timeout,
                **build_httpx_client_kwargs(self._strategy_api_target),
            )
        except TypeError:
            self._session = self._session_factory(
                **build_httpx_client_kwargs(self._strategy_api_target)
            )

        self._session_loop = current_loop
        return self._session

    async def close(self) -> None:
        session = self._session
        self._session = None
        self._session_loop = None
        if session is None or self.session_is_closed(session):
            return
        aclose = getattr(session, "aclose", None)
        if callable(aclose):
            result = aclose()
            if inspect.isawaitable(result):
                await result
            return
        close = getattr(session, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result

    def _build_headers(
        self,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, str]]:
        headers = dict(self._headers_factory() or {})
        if extra_headers:
            headers.update(
                {
                    str(key): str(value)
                    for key, value in extra_headers.items()
                    if value is not None
                }
            )
        return headers or None

    async def post_json(
        self,
        path: str,
        *,
        json: Any,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        session = await self.get_session()
        post_kwargs: Dict[str, Any] = {"json": json}
        headers = self._build_headers()
        if headers:
            post_kwargs["headers"] = headers
        if params:
            post_kwargs["params"] = params
        return await self.maybe_await(
            session.post(f"{self._strategy_api_url}{path}", **post_kwargs)
        )

    async def post_content(
        self,
        path: str,
        *,
        content: bytes,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
    ) -> Any:
        session = await self.get_session()
        resolved_headers = self._build_headers(headers)
        if content_type:
            if resolved_headers is None:
                resolved_headers = {}
            resolved_headers.setdefault("content-type", str(content_type))
        post_kwargs: Dict[str, Any] = {"content": content}
        if resolved_headers:
            post_kwargs["headers"] = resolved_headers
        if params:
            post_kwargs["params"] = params
        return await self.maybe_await(
            session.post(f"{self._strategy_api_url}{path}", **post_kwargs)
        )
