from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import os
from pathlib import Path
import pickle
from threading import RLock
from typing import Any, Callable, Dict, List, Tuple

import pandas as pd
from fastapi import HTTPException

from src.services.start_run_cache_key_utils import (
    base_cache_meta_matches as cache_base_cache_meta_matches,
    build_base_bars_cache_key as cache_build_base_bars_cache_key,
    build_base_bars_meta as cache_build_base_bars_meta,
    build_l2_enrich_cache_key as cache_build_l2_enrich_cache_key,
    build_reference_bars_cache_key as cache_build_reference_bars_cache_key,
    build_reference_bars_meta as cache_build_reference_bars_meta,
    compute_l2_day_coverage as cache_compute_l2_day_coverage,
    file_identity as cache_file_identity,
    reference_cache_meta_matches as cache_reference_cache_meta_matches,
    select_best_superset_entry as cache_select_best_superset_entry,
)
from src.services.start_run_range_utils import (
    slice_bars_for_day_range as _slice_bars_for_day_range,
    slice_reference_map_for_day_range as _slice_reference_map_for_day_range,
    summarize_days_compact as _summarize_days,
)
from src.services.start_run_time_filter_utils import (
    canonical_trading_hours as _canonical_trading_hours,
    coerce_include_extended_hours as _coerce_include_extended_hours,
)


def _parse_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return max(1, int(default))
    try:
        return max(1, int(str(raw).strip()))
    except (TypeError, ValueError):
        return max(1, int(default))


_BASE_BARS_CACHE_MAX_ENTRIES = _parse_positive_int_env(
    "BACKTEST_BASE_BARS_CACHE_MAX_ENTRIES", 16
)
_REFERENCE_BARS_CACHE_MAX_ENTRIES = _parse_positive_int_env(
    "BACKTEST_REFERENCE_BARS_CACHE_MAX_ENTRIES", 16
)
_L2_ENRICH_CACHE_MAX_ENTRIES = _parse_positive_int_env(
    "BACKTEST_L2_ENRICH_CACHE_MAX_ENTRIES", 8
)
_PREWARM_RESULT_CACHE_MAX_ENTRIES = _parse_positive_int_env(
    "BACKTEST_PREWARM_RESULT_CACHE_MAX_ENTRIES", 64
)
_DISK_CACHE_MAX_ENTRIES = _parse_positive_int_env("BACKTEST_DISK_CACHE_MAX_ENTRIES", 24)
_DISK_CACHE_MAX_BYTES = _parse_positive_int_env(
    "BACKTEST_DISK_CACHE_MAX_BYTES",
    8 * 1024 * 1024 * 1024,
)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DISK_CACHE_ROOT = _PROJECT_ROOT / ".cache" / "start_run_data"
_BASE_BARS_DISK_DIR = _DISK_CACHE_ROOT / "bars"
_REFERENCE_BARS_DISK_DIR = _DISK_CACHE_ROOT / "reference"
_L2_ENRICH_DISK_DIR = _DISK_CACHE_ROOT / "l2_enriched"
_PREWARM_RESULT_DISK_DIR = _DISK_CACHE_ROOT / "prewarm_results"
_CACHE_LOCK = RLock()
_BASE_BARS_CACHE: "OrderedDict[str, Tuple[List[Dict[str, Any]], List[str]]]" = (
    OrderedDict()
)
_REFERENCE_BARS_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_L2_ENRICH_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_PREWARM_RESULT_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_BASE_BARS_CACHE_META: Dict[str, Dict[str, Any]] = {}
_REFERENCE_BARS_CACHE_META: Dict[str, Dict[str, Any]] = {}


@dataclass(frozen=True)
class BaseBarsCacheContext:
    cache_key: str
    meta: Dict[str, Any]
    file_identities: Tuple[Tuple[str, int, int], ...]


@dataclass(frozen=True)
class ReferenceBarsCacheContext:
    cache_key: str
    meta: Dict[str, Any]
    file_identities: Tuple[Tuple[str, int, int], ...]


def clear_start_run_data_caches(*, include_disk: bool = False) -> None:
    """Clear in-memory caches and optionally on-disk cache files."""
    with _CACHE_LOCK:
        _BASE_BARS_CACHE.clear()
        _REFERENCE_BARS_CACHE.clear()
        _L2_ENRICH_CACHE.clear()
        _PREWARM_RESULT_CACHE.clear()
        _BASE_BARS_CACHE_META.clear()
        _REFERENCE_BARS_CACHE_META.clear()
    if include_disk:
        for cache_dir in (
            _BASE_BARS_DISK_DIR,
            _REFERENCE_BARS_DISK_DIR,
            _L2_ENRICH_DISK_DIR,
            _PREWARM_RESULT_DISK_DIR,
        ):
            if not cache_dir.exists():
                continue
            for path in cache_dir.glob("*.pkl"):
                try:
                    path.unlink()
                except OSError:
                    continue


def _cache_get(cache: OrderedDict, key: str) -> Any:
    with _CACHE_LOCK:
        value = cache.get(key)
        if value is None:
            return None
        cache.move_to_end(key)
        return deepcopy(value)


def _cache_set(
    cache: OrderedDict,
    key: str,
    value: Any,
    max_entries: int,
    *,
    meta_store: Dict[str, Dict[str, Any]] | None = None,
    meta_value: Dict[str, Any] | None = None,
) -> None:
    with _CACHE_LOCK:
        cache[key] = deepcopy(value)
        cache.move_to_end(key)
        if meta_store is not None:
            meta_store[key] = dict(meta_value or {})
        while len(cache) > max_entries:
            evicted_key, _ = cache.popitem(last=False)
            if meta_store is not None:
                meta_store.pop(evicted_key, None)


def _disk_cache_path(cache_dir: Path, key: str) -> Path:
    hashed = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return cache_dir / f"{hashed}.pkl"


def _ensure_disk_cache_dir(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)


def _prune_disk_cache(
    cache_dir: Path,
    max_entries: int = _DISK_CACHE_MAX_ENTRIES,
    max_bytes: int = _DISK_CACHE_MAX_BYTES,
) -> None:
    try:
        files = [path for path in cache_dir.glob("*.pkl") if path.is_file()]
    except OSError:
        return
    if not files:
        return

    files_with_stats = []
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        files_with_stats.append((path, int(stat.st_mtime_ns), int(stat.st_size)))
    files_with_stats.sort(key=lambda item: item[1], reverse=True)

    kept_count = 0
    kept_bytes = 0
    for path, _, size in files_with_stats:
        allow_by_count = kept_count < max_entries
        allow_by_bytes = (kept_bytes + size) <= max_bytes or kept_count == 0
        if allow_by_count and allow_by_bytes:
            kept_count += 1
            kept_bytes += size
            continue
        try:
            path.unlink()
        except OSError:
            continue


def _disk_cache_get(cache_dir: Path, key: str) -> Any:
    cache_path = _disk_cache_path(cache_dir, key)
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("rb") as handle:
            payload = pickle.load(handle)
        os.utime(cache_path, None)
        return deepcopy(payload)
    except Exception:
        try:
            cache_path.unlink()
        except OSError:
            pass
        return None


def _disk_cache_set(cache_dir: Path, key: str, payload: Any) -> None:
    try:
        _ensure_disk_cache_dir(cache_dir)
        cache_path = _disk_cache_path(cache_dir, key)
        tmp_path = cache_path.with_suffix(".tmp")
        with tmp_path.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        tmp_path.replace(cache_path)
        _prune_disk_cache(cache_dir)
    except Exception:
        return


def _count_disk_cache_entries(cache_dir: Path) -> int:
    try:
        return sum(1 for path in cache_dir.glob("*.pkl") if path.is_file())
    except OSError:
        return 0


def _disk_cache_total_bytes(cache_dir: Path) -> int:
    total = 0
    try:
        files = [path for path in cache_dir.glob("*.pkl") if path.is_file()]
    except OSError:
        return 0
    for path in files:
        try:
            total += int(path.stat().st_size)
        except OSError:
            continue
    return total


def _prune_all_disk_caches() -> None:
    for cache_dir in (
        _BASE_BARS_DISK_DIR,
        _REFERENCE_BARS_DISK_DIR,
        _L2_ENRICH_DISK_DIR,
        _PREWARM_RESULT_DISK_DIR,
    ):
        _prune_disk_cache(cache_dir)


_prune_all_disk_caches()


def get_start_run_data_cache_stats() -> Dict[str, Any]:
    with _CACHE_LOCK:
        memory_stats = {
            "base_bars_entries": len(_BASE_BARS_CACHE),
            "reference_entries": len(_REFERENCE_BARS_CACHE),
            "l2_enriched_entries": len(_L2_ENRICH_CACHE),
            "prewarm_results": len(_PREWARM_RESULT_CACHE),
        }
    disk_stats = {
        "base_bars_entries": _count_disk_cache_entries(_BASE_BARS_DISK_DIR),
        "reference_entries": _count_disk_cache_entries(_REFERENCE_BARS_DISK_DIR),
        "l2_enriched_entries": _count_disk_cache_entries(_L2_ENRICH_DISK_DIR),
        "prewarm_results": _count_disk_cache_entries(_PREWARM_RESULT_DISK_DIR),
        "base_bars_bytes": _disk_cache_total_bytes(_BASE_BARS_DISK_DIR),
        "reference_bytes": _disk_cache_total_bytes(_REFERENCE_BARS_DISK_DIR),
        "l2_enriched_bytes": _disk_cache_total_bytes(_L2_ENRICH_DISK_DIR),
        "prewarm_results_bytes": _disk_cache_total_bytes(_PREWARM_RESULT_DISK_DIR),
        "max_entries_per_dir": _DISK_CACHE_MAX_ENTRIES,
        "max_bytes_per_dir": _DISK_CACHE_MAX_BYTES,
    }
    return {"memory": memory_stats, "disk": disk_stats}


def flush_start_run_data_cache(*, include_disk: bool = False) -> Dict[str, Any]:
    before = get_start_run_data_cache_stats()
    clear_start_run_data_caches(include_disk=include_disk)
    after = get_start_run_data_cache_stats()
    return {
        "success": True,
        "include_disk": bool(include_disk),
        "before": before,
        "after": after,
    }


def get_prewarm_result(key: str) -> Dict[str, Any] | None:
    cached = _cache_get(_PREWARM_RESULT_CACHE, key)
    if isinstance(cached, dict):
        return cached
    cached_disk = _disk_cache_get(_PREWARM_RESULT_DISK_DIR, key)
    if isinstance(cached_disk, dict):
        _cache_set(
            _PREWARM_RESULT_CACHE,
            key,
            cached_disk,
            _PREWARM_RESULT_CACHE_MAX_ENTRIES,
        )
        return cached_disk
    return None


def set_prewarm_result(key: str, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        return
    _cache_set(
        _PREWARM_RESULT_CACHE,
        key,
        payload,
        _PREWARM_RESULT_CACHE_MAX_ENTRIES,
    )
    _disk_cache_set(_PREWARM_RESULT_DISK_DIR, key, payload)


def _filter_regular_session_only(*, df: pd.DataFrame, data_loader: Any) -> pd.DataFrame:
    """
    Restrict bars to regular market hours (ET 09:30-16:00 inclusive close print).

    This is a run-level override used when caller disables pre/post-market bars.
    """
    if df is None or df.empty:
        return df.reset_index(drop=True)

    market_ts = None
    try:
        if hasattr(data_loader, "_market_timestamp_series"):
            market_ts = data_loader._market_timestamp_series(df)
    except Exception:
        market_ts = None

    if market_ts is None:
        try:
            market_ts = pd.to_datetime(df["timestamp"], utc=True)
            if getattr(market_ts.dt, "tz", None) is not None:
                market_ts = market_ts.dt.tz_convert("America/New_York")
        except Exception:
            return df.reset_index(drop=True)

    try:
        hours = market_ts.dt.hour
        minutes = market_ts.dt.minute
        open_mask = (hours > 9) | ((hours == 9) & (minutes >= 30))
        close_mask = (hours < 16) | ((hours == 16) & (minutes == 0))
        mask = open_mask & close_mask
        return df.loc[mask].reset_index(drop=True)
    except Exception:
        return df.reset_index(drop=True)


def _file_identity(path_value: str) -> Tuple[str, int, int]:
    return cache_file_identity(path_value)


def _build_base_bars_cache_key(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    data_files: List[str],
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
) -> str:
    return cache_build_base_bars_cache_key(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        data_files=data_files,
        time_filter_enabled=time_filter_enabled,
        trading_hours=trading_hours,
        regular_session_only=regular_session_only,
    )


def _build_reference_bars_cache_key(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    ref_files: List[str],
) -> str:
    return cache_build_reference_bars_cache_key(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        ref_files=ref_files,
    )


def _compute_l2_day_coverage(
    *,
    bars: List[Dict[str, Any]],
    feature_map: Dict[int, Dict[str, Any]],
    to_utc_datetime: Any,
) -> Dict[str, Any]:
    return cache_compute_l2_day_coverage(
        bars=bars,
        feature_map=feature_map,
        to_utc_datetime=to_utc_datetime,
    )


def _build_l2_enrich_cache_key(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    comparable_mode: bool,
    is_multi_day_request: bool,
    bars: List[Dict[str, Any]],
) -> str:
    return cache_build_l2_enrich_cache_key(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        requested_l2_only=requested_l2_only,
        requested_l2_confirm=requested_l2_confirm,
        comparable_mode=comparable_mode,
        is_multi_day_request=is_multi_day_request,
        bars=bars,
    )


def _build_base_bars_meta(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> Dict[str, Any]:
    return cache_build_base_bars_meta(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        time_filter_enabled=time_filter_enabled,
        trading_hours=trading_hours,
        regular_session_only=regular_session_only,
        file_identities=file_identities,
    )


def _build_reference_bars_meta(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> Dict[str, Any]:
    return cache_build_reference_bars_meta(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        file_identities=file_identities,
    )


def _select_best_superset_entry(
    *,
    payload_store: OrderedDict,
    meta_store: Dict[str, Dict[str, Any]],
    range_start: str,
    range_end: str,
    meta_matches: Callable[[Dict[str, Any]], bool],
) -> Tuple[str, Any, str, str] | None:
    return cache_select_best_superset_entry(
        payload_store=payload_store,
        meta_store=meta_store,
        range_start=range_start,
        range_end=range_end,
        meta_matches=meta_matches,
    )


def _base_cache_meta_matches(
    *,
    meta: Dict[str, Any],
    ticker: str,
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> bool:
    return cache_base_cache_meta_matches(
        meta=meta,
        ticker=ticker,
        time_filter_enabled=time_filter_enabled,
        trading_hours=trading_hours,
        regular_session_only=regular_session_only,
        file_identities=file_identities,
    )


def _reference_cache_meta_matches(
    *,
    meta: Dict[str, Any],
    ticker: str,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> bool:
    return cache_reference_cache_meta_matches(
        meta=meta,
        ticker=ticker,
        file_identities=file_identities,
    )


def _find_base_bars_superset_in_memory(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> Tuple[List[Dict[str, Any]], List[str], str, str] | None:
    selected = None
    with _CACHE_LOCK:
        selected = _select_best_superset_entry(
            payload_store=_BASE_BARS_CACHE,
            meta_store=_BASE_BARS_CACHE_META,
            range_start=range_start,
            range_end=range_end,
            meta_matches=lambda meta: _base_cache_meta_matches(
                meta=meta,
                ticker=ticker,
                time_filter_enabled=time_filter_enabled,
                trading_hours=trading_hours,
                regular_session_only=regular_session_only,
                file_identities=file_identities,
            ),
        )
        if selected is not None:
            _BASE_BARS_CACHE.move_to_end(selected[0])
    if selected is None:
        return None
    _, (cached_bars, cached_files), cached_start, cached_end = selected
    sliced = _slice_bars_for_day_range(
        cached_bars,
        range_start=range_start,
        range_end=range_end,
    )
    if not sliced:
        return None
    return deepcopy(sliced), list(cached_files), cached_start, cached_end


def _find_reference_bars_superset_in_memory(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    file_identities: Tuple[Tuple[str, int, int], ...],
) -> Tuple[Dict[str, Any], str, str] | None:
    selected = None
    with _CACHE_LOCK:
        selected = _select_best_superset_entry(
            payload_store=_REFERENCE_BARS_CACHE,
            meta_store=_REFERENCE_BARS_CACHE_META,
            range_start=range_start,
            range_end=range_end,
            meta_matches=lambda meta: _reference_cache_meta_matches(
                meta=meta,
                ticker=ticker,
                file_identities=file_identities,
            ),
        )
        if selected is not None:
            _REFERENCE_BARS_CACHE.move_to_end(selected[0])
    if selected is None:
        return None
    _, cached_ref_map, cached_start, cached_end = selected
    sliced = _slice_reference_map_for_day_range(
        cached_ref_map,
        range_start=range_start,
        range_end=range_end,
    )
    return deepcopy(sliced), cached_start, cached_end


def _resolve_run_data_files(
    *,
    request: Any,
    ticker: str,
    range_start: str,
    range_end: str,
    databento_svc: Any,
    get_discovery: Any,
) -> List[str]:
    data_file = request.data_file
    if data_file:
        return [data_file]

    databento_svc.scan_existing_files()
    data_files = databento_svc.get_files_for_range(
        ticker=ticker,
        start_date=range_start,
        end_date=range_end,
        schema_prefix="ohlcv-",
    )
    if data_files:
        return data_files

    catalog_rows = databento_svc.list_catalog(refresh=False, ticker=ticker)
    has_catalog_ohlcv = any(
        str(row.get("schema", "")).lower().startswith("ohlcv-")
        and row.get("status") == "ready"
        for row in catalog_rows
    )
    if has_catalog_ohlcv:
        return data_files
    discovery = get_discovery()
    return discovery.get_files_for_range(ticker, range_start, range_end)


def _resolve_run_time_filter_state(
    *,
    request: Any,
    aos_applied: Dict[str, Any],
) -> Tuple[bool, Tuple[int, ...], bool]:
    time_filter_enabled = bool(
        aos_applied.get("time_filter_enabled") and aos_applied.get("trading_hours")
    )
    trading_hours = _canonical_trading_hours(aos_applied.get("trading_hours"))
    regular_session_only = False
    include_extended_hours = _coerce_include_extended_hours(
        getattr(request, "include_extended_hours", None)
    )
    if include_extended_hours is True:
        return False, tuple(), False
    if include_extended_hours is False:
        return False, tuple(), True
    return time_filter_enabled, trading_hours, regular_session_only


def _build_base_bars_cache_context(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    data_files: List[str],
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
) -> BaseBarsCacheContext | None:
    if not data_files:
        return None
    file_identities = tuple(_file_identity(file) for file in data_files)
    cache_key = _build_base_bars_cache_key(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        data_files=data_files,
        time_filter_enabled=time_filter_enabled,
        trading_hours=trading_hours,
        regular_session_only=regular_session_only,
    )
    meta = _build_base_bars_meta(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        time_filter_enabled=time_filter_enabled,
        trading_hours=trading_hours,
        regular_session_only=regular_session_only,
        file_identities=file_identities,
    )
    return BaseBarsCacheContext(
        cache_key=cache_key,
        meta=meta,
        file_identities=file_identities,
    )


def _store_base_bars_cache(
    *,
    cache_context: BaseBarsCacheContext,
    bars: List[Dict[str, Any]],
    data_files: List[str],
) -> None:
    _cache_set(
        _BASE_BARS_CACHE,
        cache_context.cache_key,
        (bars, list(data_files)),
        _BASE_BARS_CACHE_MAX_ENTRIES,
        meta_store=_BASE_BARS_CACHE_META,
        meta_value=cache_context.meta,
    )
    _disk_cache_set(
        _BASE_BARS_DISK_DIR,
        cache_context.cache_key,
        (bars, list(data_files)),
    )


def _try_load_cached_base_bars(
    *,
    cache_context: BaseBarsCacheContext,
    ticker: str,
    range_start: str,
    range_end: str,
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
    logger: Any,
) -> Tuple[List[Dict[str, Any]], List[str]] | None:
    cached_bars_payload = _cache_get(_BASE_BARS_CACHE, cache_context.cache_key)
    if cached_bars_payload is not None:
        cached_bars, cached_files = cached_bars_payload
        logger.info(
            "Using cached bars for %s %s..%s (%d bars)",
            ticker,
            range_start,
            range_end,
            len(cached_bars),
        )
        return cached_bars, cached_files

    superset_payload = _find_base_bars_superset_in_memory(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        time_filter_enabled=time_filter_enabled,
        trading_hours=trading_hours,
        regular_session_only=regular_session_only,
        file_identities=cache_context.file_identities,
    )
    if superset_payload is not None:
        superset_bars, superset_files, cached_start, cached_end = superset_payload
        logger.info(
            "Using prewarmed superset bars for %s %s..%s from %s..%s (%d bars)",
            ticker,
            range_start,
            range_end,
            cached_start,
            cached_end,
            len(superset_bars),
        )
        _store_base_bars_cache(
            cache_context=cache_context,
            bars=superset_bars,
            data_files=list(superset_files),
        )
        return superset_bars, list(superset_files)

    cached_disk_payload = _disk_cache_get(_BASE_BARS_DISK_DIR, cache_context.cache_key)
    if cached_disk_payload is None:
        return None
    cached_bars, cached_files = cached_disk_payload
    _cache_set(
        _BASE_BARS_CACHE,
        cache_context.cache_key,
        (cached_bars, list(cached_files)),
        _BASE_BARS_CACHE_MAX_ENTRIES,
        meta_store=_BASE_BARS_CACHE_META,
        meta_value=cache_context.meta,
    )
    logger.info(
        "Using disk-cached bars for %s %s..%s (%d bars)",
        ticker,
        range_start,
        range_end,
        len(cached_bars),
    )
    return cached_bars, list(cached_files)


def _load_dataframe_from_files(
    *,
    data_files: List[str],
    range_start: str,
    range_end: str,
    data_loader: Any,
    time_filter_enabled: bool,
    trading_hours: Tuple[int, ...],
    regular_session_only: bool,
    logger: Any,
) -> pd.DataFrame:
    dfs = []
    skipped_files = []
    for file in data_files:
        try:
            if file.endswith(".parquet") or file.endswith(".parq"):
                dfs.append(data_loader.load_parquet(file))
            else:
                dfs.append(data_loader.load_csv(file))
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc))
        except Exception as exc:
            logger.warning(f"Skipping invalid data file {file}: {exc}")
            skipped_files.append(file)
            continue

    if not dfs:
        skipped_note = (
            f" Skipped files: {', '.join(skipped_files)}" if skipped_files else ""
        )
        raise HTTPException(
            400, f"No usable data files for the specified date/range.{skipped_note}"
        )

    df = pd.concat(dfs, ignore_index=True)
    df = (
        df.drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    df = data_loader.filter_trading_range(df, range_start, range_end)
    if regular_session_only:
        return _filter_regular_session_only(df=df, data_loader=data_loader)
    if time_filter_enabled and trading_hours:
        return data_loader.filter_trading_hours(df, list(trading_hours))
    return df


def _build_available_ohlcv_hint(*, databento_svc: Any, ticker: str) -> str:
    try:
        summary = databento_svc.get_available_data_summary(refresh=True)
        date_ranges = (
            summary.get("date_ranges", {}) if isinstance(summary, dict) else {}
        )
        ticker_range = (
            date_ranges.get(ticker, {}) if isinstance(date_ranges, dict) else {}
        )
        available_start = str(ticker_range.get("start") or "").strip()
        available_end = str(ticker_range.get("end") or "").strip()
        if available_start and available_end:
            return f" Available OHLCV range: {available_start} to {available_end}."
    except Exception:
        return ""
    return ""


def _load_dataframe_without_files(
    *,
    request: Any,
    ticker: str,
    range_start: str,
    range_end: str,
    data_loader: Any,
    databento_svc: Any,
    logger: Any,
) -> pd.DataFrame:
    if not request.allow_mock_data:
        availability_hint = _build_available_ohlcv_hint(
            databento_svc=databento_svc, ticker=ticker
        )
        raise HTTPException(
            404,
            f"No data files found for {ticker} in range {range_start} to {range_end}. "
            f"Backtest aborted to avoid mock-data contamination.{availability_hint}",
        )
    logger.warning(
        f"No data file found for {ticker} in range {range_start} to {range_end}, using mock data (allow_mock_data=True)"
    )
    return data_loader.generate_mock_data(ticker=ticker, date=range_start)


def load_run_bars(
    *,
    request: Any,
    ticker: str,
    range_start: str,
    range_end: str,
    data_loader: Any,
    databento_svc: Any,
    get_discovery: Any,
    aos_applied: Dict[str, Any],
    logger: Any,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    data_files = _resolve_run_data_files(
        request=request,
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        databento_svc=databento_svc,
        get_discovery=get_discovery,
    )
    time_filter_enabled, trading_hours, regular_session_only = (
        _resolve_run_time_filter_state(
            request=request,
            aos_applied=aos_applied,
        )
    )
    cache_context = _build_base_bars_cache_context(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        data_files=data_files,
        time_filter_enabled=time_filter_enabled,
        trading_hours=trading_hours,
        regular_session_only=regular_session_only,
    )
    if cache_context is not None:
        cached_bars = _try_load_cached_base_bars(
            cache_context=cache_context,
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            time_filter_enabled=time_filter_enabled,
            trading_hours=trading_hours,
            regular_session_only=regular_session_only,
            logger=logger,
        )
        if cached_bars is not None:
            return cached_bars

    if data_files:
        df = _load_dataframe_from_files(
            data_files=data_files,
            range_start=range_start,
            range_end=range_end,
            data_loader=data_loader,
            time_filter_enabled=time_filter_enabled,
            trading_hours=trading_hours,
            regular_session_only=regular_session_only,
            logger=logger,
        )
    else:
        df = _load_dataframe_without_files(
            request=request,
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            data_loader=data_loader,
            databento_svc=databento_svc,
            logger=logger,
        )
    bars = list(data_loader.get_bars_iterator(df))
    if not bars:
        raise HTTPException(400, "No data available for the specified date/range")
    if cache_context is not None:
        _store_base_bars_cache(
            cache_context=cache_context,
            bars=bars,
            data_files=data_files,
        )
    return bars, data_files


def enrich_bars_with_l2(
    *,
    bars: List[Dict[str, Any]],
    ticker: str,
    range_start: str,
    range_end: str,
    requested_l2_only: bool,
    requested_l2_confirm: bool,
    comparable_mode: bool,
    is_multi_day_request: bool,
    aos_l2_config_applied: bool,
    to_utc_datetime: Any,
    build_l2_feature_map: Any,
    normalize_l2_feature_map_for_market_day_sessions: Any,
    attach_l2_features: Any,
    logger: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], bool]:
    l2_stats: Dict[str, Any] = {
        "requested_l2_only": requested_l2_only,
        "requested_l2_confirm_enabled": requested_l2_confirm,
        "aos_l2_config_applied": aos_l2_config_applied,
        "has_l2": False,
        "footprint_bars": 0,
        "icebergs": 0,
        "covered_minutes": 0,
        "bars_with_l2": 0,
        "bars_total": len(bars),
        "bars_after_filter": len(bars),
    }
    use_l2 = bool(requested_l2_only or requested_l2_confirm)
    l2_sessionized_by_market_day = bool(comparable_mode and is_multi_day_request)
    if use_l2:
        l2_cache_key = _build_l2_enrich_cache_key(
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            requested_l2_only=requested_l2_only,
            requested_l2_confirm=requested_l2_confirm,
            comparable_mode=comparable_mode,
            is_multi_day_request=is_multi_day_request,
            bars=bars,
        )
        cached_l2_payload = _cache_get(_L2_ENRICH_CACHE, l2_cache_key)
        if cached_l2_payload is not None:
            logger.info(
                "Using cached L2 enrichment for %s %s..%s (%d bars)",
                ticker,
                range_start,
                range_end,
                len(cached_l2_payload.get("bars", [])),
            )
            return (
                list(cached_l2_payload.get("bars", [])),
                dict(cached_l2_payload.get("l2_stats", l2_stats)),
                bool(
                    cached_l2_payload.get(
                        "l2_sessionized_by_market_day", l2_sessionized_by_market_day
                    )
                ),
            )
        cached_l2_disk_payload = _disk_cache_get(_L2_ENRICH_DISK_DIR, l2_cache_key)
        if cached_l2_disk_payload is not None:
            _cache_set(
                _L2_ENRICH_CACHE,
                l2_cache_key,
                cached_l2_disk_payload,
                _L2_ENRICH_CACHE_MAX_ENTRIES,
            )
            logger.info(
                "Using disk-cached L2 enrichment for %s %s..%s (%d bars)",
                ticker,
                range_start,
                range_end,
                len(cached_l2_disk_payload.get("bars", [])),
            )
            return (
                list(cached_l2_disk_payload.get("bars", [])),
                dict(cached_l2_disk_payload.get("l2_stats", l2_stats)),
                bool(
                    cached_l2_disk_payload.get(
                        "l2_sessionized_by_market_day", l2_sessionized_by_market_day
                    )
                ),
            )

        first_ts_utc = to_utc_datetime(bars[0]["timestamp"])
        last_ts_utc = to_utc_datetime(bars[-1]["timestamp"]) + timedelta(minutes=1)
        feature_map, build_stats = build_l2_feature_map(
            ticker=ticker,
            start_dt_utc=first_ts_utc,
            end_dt_utc=last_ts_utc,
        )
        if l2_sessionized_by_market_day:
            build_stats.update(
                normalize_l2_feature_map_for_market_day_sessions(
                    feature_map=feature_map,
                    bars=bars,
                )
            )
        l2_stats.update(build_stats)
        l2_day_coverage = _compute_l2_day_coverage(
            bars=bars,
            feature_map=feature_map,
            to_utc_datetime=to_utc_datetime,
        )
        missing_l2_days = list(l2_day_coverage.get("missing_days", []))
        l2_stats.update(
            {
                "bar_days_total": len(l2_day_coverage.get("bar_days", [])),
                "l2_days_total": len(l2_day_coverage.get("l2_days", [])),
                "missing_l2_days": missing_l2_days,
                "missing_l2_days_count": len(missing_l2_days),
            }
        )
        bars, attach_stats = attach_l2_features(
            bars, feature_map, l2_only=requested_l2_only
        )
        l2_stats.update(attach_stats)
        l2_stats["has_l2"] = bool(l2_stats.get("bars_with_l2", 0) > 0)

        if requested_l2_only and missing_l2_days:
            missing_preview = _summarize_days(missing_l2_days)
            raise HTTPException(
                400,
                f"L2-only mode requested but missing L2 coverage for {len(missing_l2_days)} day(s) "
                f"for {ticker} in range {range_start} to {range_end}. Missing days: {missing_preview}.",
            )
        if requested_l2_only and not bars:
            raise HTTPException(
                400,
                f"L2-only mode requested but no L2-aligned bars found for {ticker} "
                f"in range {range_start} to {range_end}.",
            )
        if requested_l2_confirm and missing_l2_days:
            missing_preview = _summarize_days(missing_l2_days)
            raise HTTPException(
                400,
                f"L2 confirmation requested but missing L2 coverage for {len(missing_l2_days)} day(s) "
                f"for {ticker} in range {range_start} to {range_end}. Missing days: {missing_preview}.",
            )
        if requested_l2_confirm and not l2_stats.get("has_l2"):
            raise HTTPException(
                400,
                f"L2 confirmation requested but no L2 data was found for {ticker} "
                f"in range {range_start} to {range_end}.",
            )
        l2_payload = {
            "bars": bars,
            "l2_stats": l2_stats,
            "l2_sessionized_by_market_day": l2_sessionized_by_market_day,
        }
        _cache_set(
            _L2_ENRICH_CACHE,
            l2_cache_key,
            l2_payload,
            _L2_ENRICH_CACHE_MAX_ENTRIES,
        )
        _disk_cache_set(
            _L2_ENRICH_DISK_DIR,
            l2_cache_key,
            l2_payload,
        )
    return bars, l2_stats, l2_sessionized_by_market_day


def _resolve_reference_data_files(
    *,
    range_start: str,
    range_end: str,
    databento_svc: Any,
    get_discovery: Any,
) -> List[str]:
    databento_svc.scan_existing_files()
    qqq_files = databento_svc.get_files_for_range(
        ticker="QQQ",
        start_date=range_start,
        end_date=range_end,
        schema_prefix="ohlcv-",
    )
    if qqq_files:
        return qqq_files
    discovery = get_discovery()
    return discovery.get_files_for_range("QQQ", range_start, range_end)


def _build_reference_cache_context(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    ref_files: List[str],
) -> ReferenceBarsCacheContext:
    file_identities = tuple(_file_identity(file) for file in ref_files)
    cache_key = _build_reference_bars_cache_key(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        ref_files=ref_files,
    )
    meta = _build_reference_bars_meta(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        file_identities=file_identities,
    )
    return ReferenceBarsCacheContext(
        cache_key=cache_key,
        meta=meta,
        file_identities=file_identities,
    )


def _store_reference_bars_cache(
    *,
    cache_context: ReferenceBarsCacheContext,
    ref_bars_map: Dict[str, Any],
) -> None:
    _cache_set(
        _REFERENCE_BARS_CACHE,
        cache_context.cache_key,
        ref_bars_map,
        _REFERENCE_BARS_CACHE_MAX_ENTRIES,
        meta_store=_REFERENCE_BARS_CACHE_META,
        meta_value=cache_context.meta,
    )
    _disk_cache_set(
        _REFERENCE_BARS_DISK_DIR,
        cache_context.cache_key,
        ref_bars_map,
    )


def _try_load_cached_reference_bars(
    *,
    cache_context: ReferenceBarsCacheContext,
    ticker: str,
    range_start: str,
    range_end: str,
    logger: Any,
) -> Dict[str, Any] | None:
    cached_ref_map = _cache_get(_REFERENCE_BARS_CACHE, cache_context.cache_key)
    if cached_ref_map is not None:
        logger.info(
            "Using cached QQQ reference bars for %s %s..%s (%d bars)",
            ticker,
            range_start,
            range_end,
            len(cached_ref_map),
        )
        return cached_ref_map

    superset_ref_payload = _find_reference_bars_superset_in_memory(
        ticker=ticker,
        range_start=range_start,
        range_end=range_end,
        file_identities=cache_context.file_identities,
    )
    if superset_ref_payload is not None:
        superset_ref_map, cached_start, cached_end = superset_ref_payload
        logger.info(
            "Using prewarmed superset QQQ bars for %s %s..%s from %s..%s (%d bars)",
            ticker,
            range_start,
            range_end,
            cached_start,
            cached_end,
            len(superset_ref_map),
        )
        _store_reference_bars_cache(
            cache_context=cache_context,
            ref_bars_map=superset_ref_map,
        )
        return superset_ref_map

    cached_disk_ref_map = _disk_cache_get(
        _REFERENCE_BARS_DISK_DIR, cache_context.cache_key
    )
    if cached_disk_ref_map is None:
        return None
    _cache_set(
        _REFERENCE_BARS_CACHE,
        cache_context.cache_key,
        cached_disk_ref_map,
        _REFERENCE_BARS_CACHE_MAX_ENTRIES,
        meta_store=_REFERENCE_BARS_CACHE_META,
        meta_value=cache_context.meta,
    )
    logger.info(
        "Using disk-cached QQQ reference bars for %s %s..%s (%d bars)",
        ticker,
        range_start,
        range_end,
        len(cached_disk_ref_map),
    )
    return cached_disk_ref_map


def _load_reference_map_from_files(
    *,
    ref_files: List[str],
    range_start: str,
    range_end: str,
    data_loader: Any,
    logger: Any,
) -> Dict[str, Any]:
    ref_bars_map: Dict[str, Any] = {}
    if not ref_files:
        return ref_bars_map

    qqq_dfs = []
    for file in ref_files:
        try:
            if file.endswith(".parquet") or file.endswith(".parq"):
                qqq_dfs.append(data_loader.load_parquet(file))
            else:
                qqq_dfs.append(data_loader.load_csv(file))
        except Exception:
            continue
    if not qqq_dfs:
        return ref_bars_map

    qqq_df = pd.concat(qqq_dfs, ignore_index=True)
    qqq_df = data_loader.filter_trading_range(qqq_df, range_start, range_end)
    for qqq_bar in data_loader.get_bars_iterator(qqq_df):
        ts = qqq_bar.get("timestamp")
        ts_key = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
        qqq_bar["ticker"] = "QQQ"
        ref_bars_map[ts_key] = qqq_bar
    logger.info(f"Loaded {len(ref_bars_map)} QQQ reference bars for cross-asset")
    return ref_bars_map


def enrich_bars_with_tcbbo(
    *,
    bars: List[Dict[str, Any]],
    ticker: str,
    range_start: str,
    range_end: str,
    logger: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Attach TCBBO options flow fields to bars if TCBBO data is available.

    Follows the same pattern as enrich_bars_with_l2: discovers data files,
    builds a minute-keyed feature map, and attaches fields to matching bars.

    Returns (bars, tcbbo_stats).
    """
    from src.tcbbo_analyzer import build_tcbbo_feature_map, find_tcbbo_files

    tcbbo_stats: Dict[str, Any] = {
        "tcbbo_available": False,
        "tcbbo_minutes_covered": 0,
        "tcbbo_bars_enriched": 0,
        "tcbbo_bars_total": len(bars),
        "tcbbo_files_found": 0,
        "tcbbo_missing_reason": "tcbbo_file_not_found",
    }

    files = find_tcbbo_files(data_dir="data", ticker=ticker)
    tcbbo_stats["tcbbo_files_found"] = len(files)
    if files:
        roots = []
        seen_roots = set()
        for row in files:
            root = str(row.get("search_root") or "").strip()
            if not root or root in seen_roots:
                continue
            seen_roots.add(root)
            roots.append(root)
        if roots:
            tcbbo_stats["tcbbo_search_roots"] = roots
    if not files:
        return bars, tcbbo_stats

    # Pick the file whose date range best overlaps with the requested range
    best_file = None
    for f in files:
        if f["start_date"] <= range_start.replace("-", "") and f[
            "end_date"
        ] >= range_end.replace("-", ""):
            best_file = f["file"]
            break
    if best_file is None:
        # Fallback: use the first file for this ticker
        best_file = files[0]["file"]
    tcbbo_stats["tcbbo_selected_file"] = str(best_file)

    try:
        feature_map, build_stats = build_tcbbo_feature_map(best_file)
    except Exception as exc:
        logger.warning("TCBBO enrichment failed for %s: %s", ticker, exc)
        tcbbo_stats["tcbbo_missing_reason"] = "tcbbo_build_failed"
        tcbbo_stats["tcbbo_error"] = str(exc)
        return bars, tcbbo_stats

    tcbbo_stats.update(build_stats)
    tcbbo_stats["tcbbo_available"] = len(feature_map) > 0
    if feature_map:
        tcbbo_stats["tcbbo_missing_reason"] = None
    else:
        tcbbo_stats["tcbbo_missing_reason"] = "tcbbo_no_feature_rows"

    enriched = 0
    for bar in bars:
        ts = bar.get("timestamp")
        if ts is None:
            continue
        # Normalize to minute-floored ISO key matching feature_map
        if hasattr(ts, "isoformat"):
            ts_key = ts.replace(second=0, microsecond=0).isoformat()
        else:
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                ts_key = dt.replace(second=0, microsecond=0).isoformat()
            except Exception:
                continue

        features = feature_map.get(ts_key)
        if features:
            bar.update(features)
            enriched += 1

    tcbbo_stats["tcbbo_bars_enriched"] = enriched
    if not enriched and tcbbo_stats.get("tcbbo_available"):
        tcbbo_stats["tcbbo_missing_reason"] = "tcbbo_no_bar_overlap"
    logger.info(
        "TCBBO enrichment: %d/%d bars enriched from %s",
        enriched,
        len(bars),
        best_file,
    )
    return bars, tcbbo_stats


def load_reference_bars_map(
    *,
    ticker: str,
    range_start: str,
    range_end: str,
    data_loader: Any,
    databento_svc: Any,
    get_discovery: Any,
    logger: Any,
) -> Dict[str, Any]:
    if ticker.upper() == "QQQ":
        return {}
    ref_bars_map: Dict[str, Any] = {}
    try:
        qqq_files = _resolve_reference_data_files(
            range_start=range_start,
            range_end=range_end,
            databento_svc=databento_svc,
            get_discovery=get_discovery,
        )
        cache_context = _build_reference_cache_context(
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            ref_files=qqq_files,
        )
        cached_ref_map = _try_load_cached_reference_bars(
            cache_context=cache_context,
            ticker=ticker,
            range_start=range_start,
            range_end=range_end,
            logger=logger,
        )
        if cached_ref_map is not None:
            return cached_ref_map
        ref_bars_map = _load_reference_map_from_files(
            ref_files=qqq_files,
            range_start=range_start,
            range_end=range_end,
            data_loader=data_loader,
            logger=logger,
        )
        _store_reference_bars_cache(
            cache_context=cache_context,
            ref_bars_map=ref_bars_map,
        )
        return ref_bars_map
    except Exception as exc:
        logger.debug(f"Could not load QQQ reference data: {exc}")
    return ref_bars_map
