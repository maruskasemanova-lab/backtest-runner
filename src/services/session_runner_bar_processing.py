from __future__ import annotations

import asyncio
from io import BytesIO
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.services.session_runner_strategy_client import StrategyApiClient

try:
    import polars as pl
except Exception:  # pragma: no cover - optional dependency in some test envs
    pl = None


RecoverStrategySession = Callable[..., Awaitable[bool]]
OnSessionStateChange = Callable[[], None]
CloseClient = Callable[[], Awaitable[None]]
IsRecoverableStrategyError = Callable[[int, str], bool]


@dataclass(frozen=True)
class StrategyBarProcessResult:
    success: bool
    response_payload: Optional[Dict[str, Any]] = None
    response_model: Optional[Any] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class StrategyBarBatchProcessResult:
    success: bool
    response_payloads: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    fallback_to_single: bool = False


class StrategyBarProcessor:
    _ARROW_IPC_CONTENT_TYPE = "application/vnd.apache.arrow.stream"

    def __init__(
        self,
        *,
        strategy_api_client: StrategyApiClient,
        recover_strategy_session: RecoverStrategySession,
        on_session_state_change: OnSessionStateChange,
        close_client: CloseClient,
        is_recoverable_strategy_error: IsRecoverableStrategyError,
    ):
        self._strategy_api_client = strategy_api_client
        self._recover_strategy_session = recover_strategy_session
        self._on_session_state_change = on_session_state_change
        self._close_client = close_client
        self._is_recoverable_strategy_error = is_recoverable_strategy_error

    @staticmethod
    def _normalize_response_payload(raw_result: Any) -> Dict[str, Any]:
        return dict(raw_result) if isinstance(raw_result, dict) else {}

    @classmethod
    def _normalize_batch_response_payloads(
        cls,
        raw_result: Any,
    ) -> List[Dict[str, Any]]:
        if isinstance(raw_result, dict):
            raw_items = raw_result.get("results")
        elif isinstance(raw_result, list):
            raw_items = raw_result
        else:
            raw_items = None
        if not isinstance(raw_items, list):
            return []
        return [cls._normalize_response_payload(item) for item in raw_items]

    @staticmethod
    def _encode_arrow_payload(payloads: List[Dict[str, Any]]) -> Optional[bytes]:
        if pl is None:
            return None
        try:
            frame = pl.DataFrame(
                payloads,
                infer_schema_length=max(1, min(len(payloads), 1_000)),
            )
            buffer = BytesIO()
            frame.write_ipc(buffer)
            return buffer.getvalue()
        except Exception:
            return None

    @staticmethod
    def _encode_arrow_frame(payload_frame: Any) -> Optional[bytes]:
        write_ipc = getattr(payload_frame, "write_ipc", None)
        if not callable(write_ipc):
            return None
        try:
            buffer = BytesIO()
            write_ipc(buffer)
            return buffer.getvalue()
        except Exception:
            return None

    async def process(
        self,
        *,
        payload: Dict[str, Any],
    ) -> StrategyBarProcessResult:
        recovery_attempted = False
        for attempt in range(2):
            try:
                response = await self._strategy_api_client.post_json(
                    "/api/session/bar",
                    json=payload,
                )
                self._on_session_state_change()
                status_code = StrategyApiClient.response_status_code(response)
                if status_code != 200:
                    error_text = await StrategyApiClient.response_text(response)
                    can_recover = (
                        not recovery_attempted
                        and attempt == 0
                        and self._is_recoverable_strategy_error(status_code, error_text)
                    )
                    if can_recover:
                        recovery_attempted = True
                        recovered = await self._recover_strategy_session(
                            reason=f"http_{status_code}",
                            detail=error_text,
                        )
                        if recovered:
                            continue
                        if status_code in {502, 503, 504}:
                            await asyncio.sleep(0.2)
                            await self._close_client()
                            continue
                    return StrategyBarProcessResult(
                        success=False,
                        error=f"API error {status_code}: {error_text}",
                    )

                raw_result = await StrategyApiClient.response_json(response)
                return StrategyBarProcessResult(
                    success=True,
                    response_payload=self._normalize_response_payload(raw_result),
                )
            except Exception as exc:
                if not StrategyApiClient.is_transport_error(exc):
                    raise
                can_recover = not recovery_attempted and attempt == 0
                if can_recover:
                    recovery_attempted = True
                    recovered = await self._recover_strategy_session(
                        reason="connection_error",
                        detail=str(exc),
                    )
                    if recovered:
                        continue
                    await asyncio.sleep(0.2)
                    await self._close_client()
                    continue
                return StrategyBarProcessResult(
                    success=False,
                    error=f"Connection error: {str(exc)}",
                )

        return StrategyBarProcessResult(
            success=False,
            error="Strategy response missing after recovery attempts",
        )

    async def process_batch(
        self,
        *,
        payloads: List[Dict[str, Any]],
    ) -> StrategyBarBatchProcessResult:
        if not payloads:
            return StrategyBarBatchProcessResult(success=True, response_payloads=[])

        arrow_payload = self._encode_arrow_payload(payloads)
        return await self._process_batch_request(
            arrow_payload=arrow_payload,
            json_payloads=payloads if arrow_payload is None else None,
        )

    async def process_batch_frame(
        self,
        *,
        payload_frame: Any,
    ) -> StrategyBarBatchProcessResult:
        arrow_payload = self._encode_arrow_frame(payload_frame)
        json_payloads: Optional[List[Dict[str, Any]]] = None
        if arrow_payload is None:
            to_dicts = getattr(payload_frame, "to_dicts", None)
            if callable(to_dicts):
                raw_rows = to_dicts()
                if isinstance(raw_rows, list):
                    json_payloads = [
                        dict(row) for row in raw_rows if isinstance(row, dict)
                    ]
        return await self._process_batch_request(
            arrow_payload=arrow_payload,
            json_payloads=json_payloads,
        )

    async def _process_batch_request(
        self,
        *,
        arrow_payload: Optional[bytes],
        json_payloads: Optional[List[Dict[str, Any]]],
    ) -> StrategyBarBatchProcessResult:
        recovery_attempted = False
        for attempt in range(2):
            try:
                if arrow_payload is not None:
                    response = await self._strategy_api_client.post_content(
                        "/api/session/bars",
                        content=arrow_payload,
                        content_type=self._ARROW_IPC_CONTENT_TYPE,
                    )
                elif json_payloads is not None:
                    response = await self._strategy_api_client.post_json(
                        "/api/session/bars",
                        json={"bars": json_payloads},
                    )
                else:
                    return StrategyBarBatchProcessResult(
                        success=False,
                        error="Unable to encode strategy batch payload",
                    )
                self._on_session_state_change()
                status_code = StrategyApiClient.response_status_code(response)
                if status_code != 200:
                    error_text = await StrategyApiClient.response_text(response)
                    if status_code in {404, 405, 415}:
                        return StrategyBarBatchProcessResult(
                            success=False,
                            error=f"API error {status_code}: {error_text}",
                            fallback_to_single=True,
                        )
                    can_recover = (
                        not recovery_attempted
                        and attempt == 0
                        and self._is_recoverable_strategy_error(status_code, error_text)
                    )
                    if can_recover:
                        recovery_attempted = True
                        recovered = await self._recover_strategy_session(
                            reason=f"batch_http_{status_code}",
                            detail=error_text,
                        )
                        if recovered:
                            continue
                        if status_code in {502, 503, 504}:
                            await asyncio.sleep(0.2)
                            await self._close_client()
                            continue
                    return StrategyBarBatchProcessResult(
                        success=False,
                        error=f"API error {status_code}: {error_text}",
                    )

                raw_result = await StrategyApiClient.response_json(response)
                return StrategyBarBatchProcessResult(
                    success=True,
                    response_payloads=self._normalize_batch_response_payloads(raw_result),
                )
            except Exception as exc:
                if not StrategyApiClient.is_transport_error(exc):
                    raise
                can_recover = not recovery_attempted and attempt == 0
                if can_recover:
                    recovery_attempted = True
                    recovered = await self._recover_strategy_session(
                        reason="batch_connection_error",
                        detail=str(exc),
                    )
                    if recovered:
                        continue
                    await asyncio.sleep(0.2)
                    await self._close_client()
                    continue
                return StrategyBarBatchProcessResult(
                    success=False,
                    error=f"Connection error: {str(exc)}",
                )

        return StrategyBarBatchProcessResult(
            success=False,
            error="Strategy batch response missing after recovery attempts",
        )
