import asyncio
import inspect
import os
from typing import Any, Callable, Dict, Optional

import httpx


class StrategyApiClient:
    def __init__(
        self,
        *,
        strategy_api_url: str,
        headers_factory: Callable[[], Dict[str, str]],
        session_factory: Callable[..., Any],
    ):
        self._strategy_api_url = str(strategy_api_url).rstrip("/")
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
            self._session = self._session_factory(timeout=timeout)
        except TypeError:
            self._session = self._session_factory()

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

    async def post_json(
        self,
        path: str,
        *,
        json: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        session = await self.get_session()
        post_kwargs: Dict[str, Any] = {"json": json}
        headers = self._headers_factory()
        if headers:
            post_kwargs["headers"] = headers
        if params:
            post_kwargs["params"] = params
        return await self.maybe_await(
            session.post(f"{self._strategy_api_url}{path}", **post_kwargs)
        )
