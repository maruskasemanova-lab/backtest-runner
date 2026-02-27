from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from src.services.session_runner_models import StrategyBarResponse
from src.services.session_runner_strategy_client import StrategyApiClient


RecoverStrategySession = Callable[..., Awaitable[bool]]
OnSessionStateChange = Callable[[], None]
CloseClient = Callable[[], Awaitable[None]]
IsRecoverableStrategyError = Callable[[int, str], bool]


@dataclass(frozen=True)
class StrategyBarProcessResult:
    success: bool
    response_payload: Optional[Dict[str, Any]] = None
    response_model: Optional[StrategyBarResponse] = None
    error: Optional[str] = None


class StrategyBarProcessor:
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
                if not isinstance(raw_result, dict):
                    raw_result = {}
                result_model = StrategyBarResponse.model_validate(raw_result)
                return StrategyBarProcessResult(
                    success=True,
                    response_payload=result_model.model_dump(
                        mode="python",
                        exclude_none=True,
                        exclude_unset=True,
                    ),
                    response_model=result_model,
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
