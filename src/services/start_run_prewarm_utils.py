from __future__ import annotations

import concurrent.futures
import json
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional

from fastapi import HTTPException

from src.services.start_run_local_aos_service import resolve_local_aos_applied
from src.services.start_run_time_filter_utils import canonical_trading_hours


@dataclass(frozen=True)
class PrewarmRequestState:
    ticker: str
    prewarm_scope: str
    range_start: str
    range_end: str
    is_multi_day_request: bool
    aos_applied: Dict[str, Any]
    requested_l2_only_raw: bool
    requested_l2_confirm_raw: bool
    requested_l2_only: bool
    requested_l2_confirm: bool
    l2_guard_reason: Optional[str]
    prewarm_cache_key: str


class PrewarmInflightRegistry:
    def __init__(self) -> None:
        self._futures: Dict[str, concurrent.futures.Future] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> tuple[concurrent.futures.Future, bool]:
        with self._lock:
            existing = self._futures.get(key)
            if isinstance(existing, concurrent.futures.Future):
                if existing.done():
                    self._futures.pop(key, None)
                else:
                    return existing, False
            future: concurrent.futures.Future = concurrent.futures.Future()
            self._futures[key] = future
            return future, True

    def release(self, key: str, future: concurrent.futures.Future) -> None:
        with self._lock:
            current = self._futures.get(key)
            if current is future:
                self._futures.pop(key, None)

    def is_inflight(self, key: str) -> bool:
        with self._lock:
            current = self._futures.get(key)
            if not isinstance(current, concurrent.futures.Future):
                return False
            if current.done():
                self._futures.pop(key, None)
                return False
            return True


def build_prewarm_cache_key(
    *,
    request: Any,
    prewarm_scope: str,
    ticker: str,
    range_start: str,
    range_end: str,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    aos_applied: Dict[str, Any],
) -> str:
    key_payload = {
        "ticker": ticker,
        "prewarm_scope": str(prewarm_scope or "range").strip().lower(),
        "range_start": str(range_start),
        "range_end": str(range_end),
        "data_file": str(request.data_file or ""),
        "allow_mock_data": bool(request.allow_mock_data),
        "comparable_mode": bool(request.comparable_mode),
        "requested_l2_only": bool(requested_l2_only),
        "requested_l2_confirm": bool(requested_l2_confirm),
        "include_extended_hours": (
            None
            if getattr(request, "include_extended_hours", None) is None
            else bool(request.include_extended_hours)
        ),
        "time_filter_enabled": bool(aos_applied.get("time_filter_enabled", False)),
        "trading_hours": canonical_trading_hours(aos_applied.get("trading_hours")),
        "aos_config_path": str(getattr(request, "aos_config_path", "") or ""),
    }
    return json.dumps(key_payload, sort_keys=True, separators=(",", ":"))


def resolve_prewarm_scope_range(
    *,
    request: Any,
    ticker: str,
    databento_svc: Any,
    get_discovery: Callable[[], Any],
    resolve_request_range: Callable[[Any], tuple[str, str]],
) -> tuple[str, str, str]:
    requested_scope = (
        str(getattr(request, "prewarm_scope", "range") or "range").strip().lower()
    )
    prewarm_scope = (
        requested_scope if requested_scope in {"range", "ticker"} else "range"
    )
    if prewarm_scope == "range":
        range_start, range_end = resolve_request_range(request)
        return prewarm_scope, range_start, range_end

    # Ticker-level prewarm resolves to full locally available OHLCV coverage.
    try:
        databento_svc.scan_existing_files()
    except Exception:
        pass

    try:
        summary = databento_svc.get_available_data_summary(refresh=True)
    except Exception:
        summary = {}
    date_ranges = summary.get("date_ranges", {}) if isinstance(summary, dict) else {}
    ticker_range = date_ranges.get(ticker, {}) if isinstance(date_ranges, dict) else {}
    range_start = str(ticker_range.get("start") or "").strip()
    range_end = str(ticker_range.get("end") or "").strip()

    if not range_start or not range_end:
        try:
            discovery = get_discovery()
            fallback = discovery.get_date_range(ticker)
        except Exception:
            fallback = {}
        if isinstance(fallback, dict):
            range_start = str(fallback.get("start") or range_start).strip()
            range_end = str(fallback.get("end") or range_end).strip()

    if not range_start or not range_end:
        raise HTTPException(
            404,
            f"No available OHLCV coverage found for ticker {ticker} for ticker-level prewarm.",
        )
    return prewarm_scope, range_start, range_end


def resolve_prewarm_request_state(
    *,
    request: Any,
    ticker: str,
    databento_svc: Any,
    get_discovery: Callable[[], Any],
    load_aos_config: Callable[..., Dict[str, Any]],
    get_ticker_positioning_config: Callable[[str], Dict[str, Any]],
    positioning_config_keys: Iterable[str] = (),
    resolve_request_range: Callable[[Any], tuple[str, str]],
    build_l2_guard_reason: Callable[..., Optional[str]],
) -> PrewarmRequestState:
    prewarm_scope, range_start, range_end = resolve_prewarm_scope_range(
        request=request,
        ticker=ticker,
        databento_svc=databento_svc,
        get_discovery=get_discovery,
        resolve_request_range=resolve_request_range,
    )
    aos_applied = resolve_local_aos_applied(
        ticker=ticker,
        load_aos_config=load_aos_config,
        get_ticker_positioning_config=get_ticker_positioning_config,
        positioning_config_keys=positioning_config_keys,
        aos_config_path=getattr(request, "aos_config_path", None),
    )
    aos_l2_cfg = (
        aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}
    )
    requested_l2_only_raw = bool(
        request.l2_only or bool(aos_l2_cfg.get("l2_only", False))
    )
    requested_l2_confirm_raw = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    requested_l2_only = requested_l2_only_raw
    requested_l2_confirm = requested_l2_confirm_raw
    l2_guard_reason = build_l2_guard_reason(
        prewarm_scope=prewarm_scope,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        range_start=range_start,
        range_end=range_end,
    )
    return PrewarmRequestState(
        ticker=ticker,
        prewarm_scope=prewarm_scope,
        range_start=range_start,
        range_end=range_end,
        is_multi_day_request=bool(
            range_start != range_end or bool(request.date_from and request.date_to)
        ),
        aos_applied=aos_applied,
        requested_l2_only_raw=requested_l2_only_raw,
        requested_l2_confirm_raw=requested_l2_confirm_raw,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        l2_guard_reason=l2_guard_reason,
        prewarm_cache_key=build_prewarm_cache_key(
            request=request,
            prewarm_scope=prewarm_scope,
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            requested_l2_only=requested_l2_only,
            requested_l2_confirm=requested_l2_confirm,
            aos_applied=aos_applied,
        ),
    )


def raise_for_guard_reason(*, state: PrewarmRequestState, logger: Any) -> None:
    if not state.l2_guard_reason:
        return
    logger.warning(
        "%s ticker=%s range=%s..%s",
        state.l2_guard_reason,
        state.ticker,
        state.range_start,
        state.range_end,
    )
    raise HTTPException(400, state.l2_guard_reason)
