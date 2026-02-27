from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from src.services.session_runner_models import Err, Ok, Result
from src.services.session_runner_payload_validator import ValidateStrategyBarPayload
from src.services.session_runner_payload_utils import (
    StrategyBarPayloadInput,
    build_validated_strategy_bar_payload,
    stringify_bar_timestamp,
)
from src.services.session_runner_strategy_client import StrategyApiClient


OnSessionStateChange = Callable[[], None]
CloseClient = Callable[[], Awaitable[None]]


class StrategySessionRecoveryHelper:
    @staticmethod
    def _normalize_utc_date(value: Any) -> Optional[date]:
        if isinstance(value, datetime):
            dt = value
        else:
            raw = str(value or "").strip()
            if not raw:
                return None
            try:
                return date.fromisoformat(raw)
            except ValueError:
                if raw.endswith("Z"):
                    raw = raw[:-1] + "+00:00"
                try:
                    dt = datetime.fromisoformat(raw)
                except ValueError:
                    return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.date()

    def __init__(
        self,
        *,
        strategy_api_client: StrategyApiClient,
        validate_strategy_bar_payload: ValidateStrategyBarPayload,
        on_session_state_change: OnSessionStateChange,
        close_client: CloseClient,
        logger: logging.Logger,
    ):
        self._strategy_api_client = strategy_api_client
        self._validate_strategy_bar_payload = validate_strategy_bar_payload
        self._on_session_state_change = on_session_state_change
        self._close_client = close_client
        self._logger = logger

    @staticmethod
    def resolve_session_date(
        *,
        restart_session_date: Any,
        date_from: Optional[str],
        date: str,
    ) -> str:
        token = str(restart_session_date or date_from or date).strip()
        return token

    @staticmethod
    def resolve_config_snapshot(restart_session_config: Any) -> Dict[str, Any]:
        if not isinstance(restart_session_config, dict):
            return {}
        return dict(restart_session_config)

    @staticmethod
    def _iter_replay_bars(
        *,
        session_date: str,
        current_bar_index: int,
        bars: Sequence[Dict[str, Any]],
    ) -> List[Tuple[int, Dict[str, Any], str]]:
        target_date = StrategySessionRecoveryHelper._normalize_utc_date(session_date)
        bars_to_replay: List[Tuple[int, Dict[str, Any], str]] = []
        for index in range(int(current_bar_index)):
            bar = bars[index]
            timestamp = bar.get("timestamp", "")
            timestamp_token = stringify_bar_timestamp(timestamp)
            timestamp_date = StrategySessionRecoveryHelper._normalize_utc_date(
                timestamp
            )
            if target_date is not None and timestamp_date is not None:
                if timestamp_date != target_date:
                    continue
            elif session_date not in timestamp_token:
                continue
            bars_to_replay.append((index, bar, timestamp_token))
        return bars_to_replay

    def _build_replay_payload(
        self,
        *,
        run_id: str,
        ticker: str,
        bar: Dict[str, Any],
        timestamp_token: str,
        l2_payload_keys: Sequence[str],
        tcbbo_payload_keys: Sequence[str],
        ref_bars_map: Mapping[str, Dict[str, Any]],
    ) -> Result[Dict[str, Any], str]:
        return build_validated_strategy_bar_payload(
            validate_strategy_bar_payload=self._validate_strategy_bar_payload,
            payload_input=StrategyBarPayloadInput(
                run_id=run_id,
                ticker=ticker,
                bar=bar,
                timestamp=timestamp_token,
            ),
            l2_payload_keys=l2_payload_keys,
            tcbbo_payload_keys=tcbbo_payload_keys,
            ref_bars_map=ref_bars_map,
        )

    async def recover_session(
        self,
        *,
        run_id: str,
        ticker: str,
        reason: str,
        detail: str,
        session_date: str,
        config_snapshot: Dict[str, Any],
        current_bar_index: int,
        bars: Sequence[Dict[str, Any]],
        l2_payload_keys: Sequence[str],
        tcbbo_payload_keys: Sequence[str],
        ref_bars_map: Mapping[str, Dict[str, Any]],
    ) -> bool:
        last_error = ""
        for attempt in range(3):
            try:
                response = await self._strategy_api_client.post_json(
                    "/api/session/config",
                    json=config_snapshot,
                    params={
                        "run_id": run_id,
                        "ticker": ticker,
                        "date": session_date,
                    },
                )
                self._on_session_state_change()
                body = await StrategyApiClient.response_text(response)
                status_code = StrategyApiClient.response_status_code(response)
                if status_code == 200:
                    self._logger.warning(
                        "Strategy session recovered run_id=%s ticker=%s date=%s reason=%s",
                        run_id,
                        ticker,
                        session_date,
                        reason,
                    )
                    return await self.replay_historical_bars(
                        run_id=run_id,
                        ticker=ticker,
                        session_date=session_date,
                        current_bar_index=current_bar_index,
                        bars=bars,
                        l2_payload_keys=l2_payload_keys,
                        tcbbo_payload_keys=tcbbo_payload_keys,
                        ref_bars_map=ref_bars_map,
                    )
                last_error = f"http_{status_code}:{body[:200]}"
            except Exception as exc:
                if not StrategyApiClient.is_transport_error(exc):
                    raise
                last_error = f"connection:{str(exc)}"
            await self._close_client()
            self._on_session_state_change()
            if attempt < 2:
                await asyncio.sleep(0.2 * (attempt + 1))

        self._logger.warning(
            "Strategy session recovery failed reason=%s detail=%s last_error=%s",
            reason,
            detail[:200],
            last_error[:300],
        )
        return False

    async def replay_historical_bars(
        self,
        *,
        run_id: str,
        ticker: str,
        session_date: str,
        current_bar_index: int,
        bars: Sequence[Dict[str, Any]],
        l2_payload_keys: Sequence[str],
        tcbbo_payload_keys: Sequence[str],
        ref_bars_map: Mapping[str, Dict[str, Any]],
    ) -> bool:
        bars_to_replay = self._iter_replay_bars(
            session_date=session_date,
            current_bar_index=current_bar_index,
            bars=bars,
        )
        if not bars_to_replay:
            return True

        self._logger.info(
            "Replaying %s historical bars for session %s to rebuild state.",
            len(bars_to_replay),
            session_date,
        )

        try:
            for index, bar, timestamp_token in bars_to_replay:
                validated_payload = self._build_replay_payload(
                    run_id=run_id,
                    ticker=ticker,
                    bar=bar,
                    timestamp_token=timestamp_token,
                    l2_payload_keys=l2_payload_keys,
                    tcbbo_payload_keys=tcbbo_payload_keys,
                    ref_bars_map=ref_bars_map,
                )
                match validated_payload:
                    case Ok(value=payload):
                        replay_payload = payload
                    case Err(error=error_text):
                        self._logger.error(
                            "Failed to replay bar index %s due to payload validation error: %s",
                            index,
                            error_text,
                        )
                        return False

                response = await self._strategy_api_client.post_json(
                    "/api/session/bar",
                    json=replay_payload,
                )
                self._on_session_state_change()
                status_code = StrategyApiClient.response_status_code(response)
                if status_code != 200:
                    error_text = await StrategyApiClient.response_text(response)
                    self._logger.error(
                        "Failed to replay bar index %s: HTTP %s %s",
                        index,
                        status_code,
                        error_text,
                    )
                    return False
            return True
        except Exception as exc:
            if not StrategyApiClient.is_transport_error(exc):
                raise
            self._logger.error("Error replaying historical bars: %s", exc)
            return False
