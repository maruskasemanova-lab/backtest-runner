"""
Databento data loader service.
Downloads and catalogs L2, OHLCV, and trades data from Databento.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

from .system_settings import SystemSettings

logger = logging.getLogger("DatabentoService")

SUPPORTED_SCHEMAS = {
    "mbp-10": {"description": "L2 Market Depth (10 levels)", "ext_primary": ".mbn"},
    "ohlcv-1m": {"description": "1-Minute OHLCV Bars", "ext_primary": ".csv"},
    "trades": {"description": "Raw Trade Tape", "ext_primary": ".mbn"},
}


@dataclass
class CatalogEntry:
    ticker: str
    schema: str
    dataset: str
    start_date: str
    end_date: str
    file_mbn: Optional[str] = None
    file_parquet: Optional[str] = None
    file_csv: Optional[str] = None
    size_bytes: int = 0
    row_count: int = 0
    downloaded_at: Optional[str] = None
    status: str = "ready"
    error_message: Optional[str] = None
    progress_pct: float = 100.0
    source_root: Optional[str] = None
    managed: bool = True


class DataCatalog:
    """JSON-backed catalog of downloaded/discovered data files."""

    def __init__(self, catalog_path: str = "data/data_catalog.json"):
        self.path = Path(catalog_path)
        self._entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if not self.path.exists():
            self._entries = []
            return
        try:
            self._entries = json.loads(self.path.read_text())
        except Exception:
            self._entries = []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._entries, indent=2, default=str))

    def list_all(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def find(self, ticker: str, schema: str, start: str, end: str) -> Optional[Dict[str, Any]]:
        for entry in self._entries:
            if (
                entry.get("ticker") == ticker
                and entry.get("schema") == schema
                and entry.get("start_date") == start
                and entry.get("end_date") == end
            ):
                return entry
        return None

    def upsert(self, entry: CatalogEntry):
        existing = self.find(entry.ticker, entry.schema, entry.start_date, entry.end_date)
        payload = asdict(entry)
        if existing:
            existing.update(payload)
        else:
            self._entries.append(payload)
        self._save()

    def remove(self, ticker: str, schema: str, start: str, end: str) -> bool:
        before = len(self._entries)
        self._entries = [
            entry
            for entry in self._entries
            if not (
                entry.get("ticker") == ticker
                and entry.get("schema") == schema
                and entry.get("start_date") == start
                and entry.get("end_date") == end
            )
        ]
        if len(self._entries) < before:
            self._save()
            return True
        return False

    def list_by_ticker(self, ticker: str) -> List[Dict[str, Any]]:
        return [entry for entry in self._entries if entry.get("ticker") == ticker]


class DatabentoService:
    """Downloads data from Databento and manages a unified local catalog."""

    def __init__(
        self,
        l2_dir: str = "data/l2",
        ohlcv_dir: str = "data",
        catalog_path: str = "data/data_catalog.json",
    ):
        self.settings = SystemSettings()
        self.catalog = DataCatalog(catalog_path)
        self._active_downloads: Dict[str, Dict[str, Any]] = {}
        self._project_root = Path(__file__).resolve().parents[1]
        # Cache real OHLCV ET date ranges keyed by (path, mtime_ns, size_bytes).
        self._ohlcv_range_cache: Dict[Tuple[str, int, int], Optional[Tuple[str, str]]] = {}

        self.l2_dir = Path(l2_dir)
        self.ohlcv_dir = Path(ohlcv_dir)
        self._ohlcv_scan_dirs: List[Path] = []
        self._l2_scan_dirs: List[Path] = []
        self._refresh_data_roots()

        # Always scan at startup so the catalog includes newly added external files.
        self.scan_existing_files()

    def _refresh_data_roots(self) -> None:
        self.settings.reload()
        self.ohlcv_dir = self.settings.primary_ohlcv_dir()
        self.l2_dir = self.settings.primary_l2_dir()
        self._ohlcv_scan_dirs = self.settings.get_ohlcv_dirs(existing_only=False)
        self._l2_scan_dirs = self.settings.get_l2_dirs(existing_only=False)

    def get_settings(self) -> Dict[str, Any]:
        return self.settings.to_public_dict()

    def update_data_dirs(
        self,
        ohlcv_data_dirs: Optional[List[str]] = None,
        l2_data_dirs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        ok = self.settings.update_data_dirs(
            ohlcv_data_dirs=ohlcv_data_dirs,
            l2_data_dirs=l2_data_dirs,
        )
        if not ok:
            raise RuntimeError("Failed to update data directories")
        self._refresh_data_roots()
        self.scan_existing_files()
        return self.get_settings()

    def set_api_key(self, api_key: str) -> Dict[str, Any]:
        ok = self.settings.set_databento_api_key(api_key)
        if not ok:
            raise RuntimeError("Failed to persist Databento API key")
        return self.get_settings()

    def _resolve_api_key(self) -> str:
        return self.settings.resolve_databento_api_key()

    def _get_client(self):
        import databento as db

        api_key = self._resolve_api_key()
        if not api_key:
            raise RuntimeError("DATABENTO_API_KEY is not set (env var or system settings)")
        return db.Historical(api_key)

    @staticmethod
    def _is_valid_iso_date(value: str) -> bool:
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except Exception:
            return False

    @staticmethod
    def _parse_l2_basename(stem: str) -> Optional[Tuple[str, str, str, str]]:
        # trades: TICKER_trades_YYYY-MM-DD_YYYY-MM-DD
        if "_trades_" in stem:
            parts = stem.split("_trades_")
            if len(parts) != 2:
                return None
            ticker = parts[0].upper()
            dates = parts[1].split("_")
            if len(dates) != 2:
                return None
            start_date, end_date = dates
            schema = "trades"
        else:
            # mbp-10: TICKER_YYYY-MM-DD_YYYY-MM-DD
            parts = stem.split("_")
            if len(parts) < 3:
                return None
            ticker = parts[0].upper()
            start_date = parts[1]
            end_date = parts[2]
            schema = "mbp-10"

        if not (DatabentoService._is_valid_iso_date(start_date) and DatabentoService._is_valid_iso_date(end_date)):
            return None
        return ticker, schema, start_date, end_date

    @staticmethod
    def _parse_ohlcv_basename(stem: str) -> Optional[Tuple[str, str, str, str]]:
        # TICKER_ohlcv-1m_YYYY-MM-DD_YYYY-MM-DD
        if "_ohlcv-" not in stem:
            return None
        ticker, tail = stem.split("_ohlcv-", 1)
        parts = tail.split("_")
        if len(parts) < 3:
            return None
        timeframe = parts[0]
        start_date = parts[1]
        end_date = parts[2]
        if not timeframe:
            return None
        if not (DatabentoService._is_valid_iso_date(start_date) and DatabentoService._is_valid_iso_date(end_date)):
            return None
        schema = f"ohlcv-{timeframe}"
        return ticker.upper(), schema, start_date, end_date

    def _is_managed_path(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self._project_root.resolve())
            return True
        except ValueError:
            return False

    @staticmethod
    def _entry_formats(entry: Dict[str, Any]) -> List[str]:
        formats: List[str] = []
        if entry.get("file_mbn"):
            formats.append("mbn")
        if entry.get("file_parquet"):
            formats.append("parquet")
        if entry.get("file_csv"):
            formats.append("csv")
        return formats

    def _resolve_entry_path(self, path_str: Optional[str]) -> Optional[Path]:
        if not path_str:
            return None
        path = Path(path_str).expanduser()
        if path.is_absolute():
            return path
        return (self._project_root / path).resolve()

    @staticmethod
    def _pick_timestamp_column(columns: List[str]) -> Optional[str]:
        for col in ("timestamp", "ts_event", "ts_recv", "time", "datetime", "date"):
            if col in columns:
                return col
        return None

    def _infer_ohlcv_et_range_from_path(self, path: Path) -> Optional[Tuple[str, str]]:
        """
        Infer actual ET date range from OHLCV file contents.
        This protects against filename metadata drift.
        """
        try:
            stat = path.stat()
        except OSError:
            return None

        if not hasattr(self, "_ohlcv_range_cache") or not isinstance(self._ohlcv_range_cache, dict):
            self._ohlcv_range_cache = {}

        mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
        key = (str(path.resolve()), mtime_ns, int(stat.st_size))
        if key in self._ohlcv_range_cache:
            return self._ohlcv_range_cache[key]

        try:
            if path.suffix.lower() in (".parquet", ".parq"):
                df = pd.read_parquet(path)
            else:
                df = pd.read_csv(path)
        except Exception:
            self._ohlcv_range_cache[key] = None
            return None

        ts_col = self._pick_timestamp_column(list(df.columns))
        if ts_col is None:
            self._ohlcv_range_cache[key] = None
            return None

        ts = pd.to_datetime(df[ts_col], utc=True, errors="coerce").dropna()
        if ts.empty:
            self._ohlcv_range_cache[key] = None
            return None

        et = ts.dt.tz_convert(ZoneInfo("America/New_York"))
        resolved = (
            et.min().date().isoformat(),
            et.max().date().isoformat(),
        )
        self._ohlcv_range_cache[key] = resolved
        return resolved

    def _effective_entry_range(self, entry: Dict[str, Any]) -> Tuple[str, str]:
        """
        Return effective date coverage for an entry.
        For OHLCV entries, prefer actual ET range from file contents when possible.
        """
        start_date = str(entry.get("start_date", ""))
        end_date = str(entry.get("end_date", ""))

        schema = str(entry.get("schema", "")).lower()
        if not schema.startswith("ohlcv-"):
            return start_date, end_date

        preferred_file = self._preferred_entry_file(entry)
        preferred_path = self._resolve_entry_path(preferred_file)
        if not preferred_path or not preferred_path.exists():
            return "", ""

        actual = self._infer_ohlcv_et_range_from_path(preferred_path)
        if actual is None:
            return "", ""
        return actual

    def scan_existing_files(self) -> List[CatalogEntry]:
        """Scan configured data directories and register untracked files."""
        self._refresh_data_roots()
        new_entries: List[CatalogEntry] = []

        # Scan L2/trades files (.mbn/.parquet)
        for data_dir in self._l2_scan_dirs:
            if not data_dir.exists() or not data_dir.is_dir():
                continue

            grouped: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
            l2_files = list(data_dir.glob("*.mbn")) + list(data_dir.glob("*.parquet"))
            for file_path in l2_files:
                parsed = self._parse_l2_basename(file_path.stem)
                if not parsed:
                    continue
                ticker, schema, start_date, end_date = parsed
                key = (ticker, schema, start_date, end_date)
                if key not in grouped:
                    grouped[key] = {
                        "ticker": ticker,
                        "schema": schema,
                        "start_date": start_date,
                        "end_date": end_date,
                        "source_root": str(data_dir.resolve()),
                    }
                if file_path.suffix == ".mbn":
                    grouped[key]["file_mbn"] = file_path
                elif file_path.suffix == ".parquet":
                    grouped[key]["file_parquet"] = file_path

            for ticker, schema, start_date, end_date in grouped.keys():
                if self.catalog.find(ticker, schema, start_date, end_date):
                    continue
                info = grouped[(ticker, schema, start_date, end_date)]
                mbn_path = info.get("file_mbn")
                parquet_path = info.get("file_parquet")

                size_bytes = 0
                preferred = parquet_path or mbn_path
                if preferred and preferred.exists():
                    size_bytes = preferred.stat().st_size
                downloaded_at = (
                    datetime.fromtimestamp(preferred.stat().st_mtime).isoformat()
                    if preferred and preferred.exists()
                    else None
                )

                managed = bool(preferred and self._is_managed_path(preferred))
                entry = CatalogEntry(
                    ticker=ticker,
                    schema=schema,
                    dataset="XNAS.ITCH",
                    start_date=start_date,
                    end_date=end_date,
                    file_mbn=str(mbn_path) if mbn_path else None,
                    file_parquet=str(parquet_path) if parquet_path else None,
                    size_bytes=size_bytes,
                    status="ready",
                    downloaded_at=downloaded_at,
                    source_root=info.get("source_root"),
                    managed=managed,
                )
                self.catalog.upsert(entry)
                new_entries.append(entry)

        # Scan OHLCV files (.csv/.parquet/.parq)
        for data_dir in self._ohlcv_scan_dirs:
            if not data_dir.exists() or not data_dir.is_dir():
                continue

            grouped: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
            for pattern in ("*_ohlcv-*_*.csv", "*_ohlcv-*_*.parquet", "*_ohlcv-*_*.parq"):
                for file_path in data_dir.glob(pattern):
                    parsed = self._parse_ohlcv_basename(file_path.stem)
                    if not parsed:
                        continue
                    ticker, schema, start_date, end_date = parsed
                    key = (ticker, schema, start_date, end_date)
                    if key not in grouped:
                        grouped[key] = {
                            "ticker": ticker,
                            "schema": schema,
                            "start_date": start_date,
                            "end_date": end_date,
                            "source_root": str(data_dir.resolve()),
                        }
                    if file_path.suffix == ".csv":
                        grouped[key]["file_csv"] = file_path
                    elif file_path.suffix in (".parquet", ".parq"):
                        grouped[key]["file_parquet"] = file_path

            for ticker, schema, start_date, end_date in grouped.keys():
                if self.catalog.find(ticker, schema, start_date, end_date):
                    continue
                info = grouped[(ticker, schema, start_date, end_date)]
                csv_path = info.get("file_csv")
                parquet_path = info.get("file_parquet")
                preferred = parquet_path or csv_path
                if not preferred:
                    continue

                entry = CatalogEntry(
                    ticker=ticker,
                    schema=schema,
                    dataset="XNAS.ITCH",
                    start_date=start_date,
                    end_date=end_date,
                    file_csv=str(csv_path) if csv_path else None,
                    file_parquet=str(parquet_path) if parquet_path else None,
                    size_bytes=preferred.stat().st_size if preferred.exists() else 0,
                    status="ready",
                    downloaded_at=datetime.fromtimestamp(preferred.stat().st_mtime).isoformat()
                    if preferred.exists()
                    else None,
                    source_root=info.get("source_root"),
                    managed=self._is_managed_path(preferred),
                )
                self.catalog.upsert(entry)
                new_entries.append(entry)

        if new_entries:
            logger.info(f"Scanned and registered {len(new_entries)} new file(s)")
        return new_entries

    def list_catalog(
        self,
        refresh: bool = False,
        ticker: Optional[str] = None,
        schema: Optional[str] = None,
        file_format: Optional[str] = None,
        source: Optional[str] = None,
        managed: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        if refresh:
            self.scan_existing_files()

        ticker_filter = str(ticker or "").strip().upper()
        schema_filter = str(schema or "").strip().lower()
        format_filter = str(file_format or "").strip().lower()
        source_filter = str(source or "").strip()

        rows = self.catalog.list_all()
        filtered: List[Dict[str, Any]] = []
        for entry in rows:
            entry_managed = bool(entry.get("managed", True))
            if ticker_filter and str(entry.get("ticker", "")).upper() != ticker_filter:
                continue
            if schema_filter and str(entry.get("schema", "")).lower() != schema_filter:
                continue
            if source_filter and str(entry.get("source_root", "")) != source_filter:
                continue
            if managed is not None and entry_managed != managed:
                continue
            if format_filter:
                formats = self._entry_formats(entry)
                if format_filter not in formats:
                    continue

            copy_entry = dict(entry)
            copy_entry["managed"] = entry_managed
            copy_entry["formats"] = self._entry_formats(entry)
            filtered.append(copy_entry)

        filtered.sort(
            key=lambda item: (
                str(item.get("ticker", "")),
                str(item.get("start_date", "")),
                str(item.get("schema", "")),
            )
        )
        return filtered

    def get_available_data_summary(self, refresh: bool = False) -> Dict[str, Any]:
        entries = self.list_catalog(refresh=refresh)
        tickers = set()
        l2_tickers = set()
        date_ranges: Dict[str, Dict[str, Any]] = {}

        for entry in entries:
            if entry.get("status") not in ("ready", "downloading", "converting"):
                continue
            ticker = str(entry.get("ticker", "")).upper()
            schema = str(entry.get("schema", "")).lower()
            start_date, end_date = self._effective_entry_range(entry)

            if schema.startswith("ohlcv-"):
                if not (
                    self._is_valid_iso_date(start_date)
                    and self._is_valid_iso_date(end_date)
                ):
                    continue
                tickers.add(ticker)
                if ticker not in date_ranges:
                    date_ranges[ticker] = {
                        "start": start_date,
                        "end": end_date,
                        "files": [],
                    }
                else:
                    if start_date < date_ranges[ticker]["start"]:
                        date_ranges[ticker]["start"] = start_date
                    if end_date > date_ranges[ticker]["end"]:
                        date_ranges[ticker]["end"] = end_date

                for key in ("file_parquet", "file_csv"):
                    file_path = entry.get(key)
                    if file_path:
                        file_name = Path(file_path).name
                        if file_name not in date_ranges[ticker]["files"]:
                            date_ranges[ticker]["files"].append(file_name)

            if schema == "mbp-10":
                l2_tickers.add(ticker)

        # Keep compatibility: include pure-L2 tickers in ticker list as well.
        tickers.update(l2_tickers)

        return {
            "tickers": sorted(tickers),
            "l2_tickers": sorted(l2_tickers),
            "date_ranges": date_ranges,
            "data_dir": str(self.ohlcv_dir),
            "data_dirs": [str(p) for p in self._ohlcv_scan_dirs],
            "l2_dirs": [str(p) for p in self._l2_scan_dirs],
        }

    @staticmethod
    def _range_overlaps(
        entry_start: str, entry_end: str, start_date: str, end_date: str
    ) -> bool:
        return entry_start <= end_date and entry_end >= start_date

    @staticmethod
    def _iter_days(start_date: str, end_date: str) -> List[str]:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            raise ValueError(f"Invalid date range: {start_date} > {end_date}")
        days: List[str] = []
        current = start_dt
        while current <= end_dt:
            days.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return days

    @staticmethod
    def _preferred_entry_file(entry: Dict[str, Any]) -> Optional[str]:
        return entry.get("file_parquet") or entry.get("file_csv") or entry.get("file_mbn")

    def _has_ready_coverage_for_day(
        self,
        ticker: str,
        schema: str,
        day: str,
        entries: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        ticker_upper = str(ticker or "").upper()
        schema_lower = str(schema or "").lower()
        rows = entries if entries is not None else self.list_catalog(refresh=False, ticker=ticker_upper)
        for entry in rows:
            if str(entry.get("ticker", "")).upper() != ticker_upper:
                continue
            if str(entry.get("schema", "")).lower() != schema_lower:
                continue
            if entry.get("status") != "ready":
                continue

            entry_start = str(entry.get("start_date", ""))
            entry_end = str(entry.get("end_date", ""))
            if schema_lower.startswith("ohlcv-"):
                entry_start, entry_end = self._effective_entry_range(entry)
                if not (
                    self._is_valid_iso_date(entry_start)
                    and self._is_valid_iso_date(entry_end)
                ):
                    continue
            if not self._range_overlaps(entry_start, entry_end, day, day):
                continue

            preferred_file = self._preferred_entry_file(entry)
            preferred_path = self._resolve_entry_path(preferred_file)
            if preferred_path and preferred_path.exists():
                return True
        return False

    def get_range_coverage(
        self,
        ticker: str,
        schema: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        ticker_upper = str(ticker or "").upper()
        schema_lower = str(schema or "").lower()
        days = self._iter_days(start_date, end_date)
        entries = self.list_catalog(refresh=False, ticker=ticker_upper)
        covered_days: List[str] = []
        missing_days: List[str] = []
        for day in days:
            if self._has_ready_coverage_for_day(
                ticker=ticker_upper,
                schema=schema_lower,
                day=day,
                entries=entries,
            ):
                covered_days.append(day)
            else:
                missing_days.append(day)

        return {
            "ticker": ticker_upper,
            "schema": schema_lower,
            "start_date": start_date,
            "end_date": end_date,
            "total_days": len(days),
            "covered_days": covered_days,
            "missing_days": missing_days,
            "fully_covered": len(missing_days) == 0,
        }

    def get_files_for_range(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        schema_prefix: str = "ohlcv-",
    ) -> List[str]:
        ticker = ticker.upper()
        candidates: List[Dict[str, Any]] = []
        for entry in self.list_catalog(refresh=False, ticker=ticker):
            if entry.get("status") != "ready":
                continue
            entry_schema = str(entry.get("schema", "")).lower()
            if not entry_schema.startswith(schema_prefix.lower()):
                continue
            entry_start, entry_end = self._effective_entry_range(entry)
            if entry_schema.startswith("ohlcv-") and not (
                self._is_valid_iso_date(entry_start)
                and self._is_valid_iso_date(entry_end)
            ):
                continue
            if not self._range_overlaps(entry_start, entry_end, start_date, end_date):
                continue

            preferred_file = entry.get("file_parquet") or entry.get("file_csv")
            if not preferred_file:
                continue
            preferred_path = self._resolve_entry_path(preferred_file)
            if not preferred_path or not preferred_path.exists():
                continue

            try:
                start_dt = datetime.strptime(entry_start, "%Y-%m-%d")
                end_dt = datetime.strptime(entry_end, "%Y-%m-%d")
            except Exception:
                continue

            candidates.append(
                {
                    "file": str(preferred_path),
                    "start": entry_start,
                    "end": entry_end,
                    "start_dt": start_dt,
                    "end_dt": end_dt,
                    "schema": entry_schema,
                }
            )

        # Deterministic ordering: smallest covering range first, then path.
        def _sort_key(row: Dict[str, Any]) -> Tuple[int, str]:
            try:
                span_days = (row["end_dt"] - row["start_dt"]).days
            except Exception:
                span_days = 999999
            return (span_days, row["file"])

        if not candidates:
            return []

        # Prefer minimal range files that cover each requested day.
        try:
            requested_start = datetime.strptime(start_date, "%Y-%m-%d")
            requested_end = datetime.strptime(end_date, "%Y-%m-%d")
        except Exception:
            requested_start = None
            requested_end = None

        selected_files = []
        seen = set()

        if requested_start and requested_end and requested_start <= requested_end:
            requested_days = []
            day = requested_start
            while day <= requested_end:
                requested_days.append(day.date())
                day += timedelta(days=1)

            uncovered = set(requested_days)
            while uncovered:
                best_row = None
                best_cover = set()
                best_key = None
                for row in candidates:
                    covered = {
                        target_day
                        for target_day in uncovered
                        if row["start_dt"].date() <= target_day <= row["end_dt"].date()
                    }
                    if not covered:
                        continue
                    row_key = _sort_key(row)
                    if (
                        len(covered) > len(best_cover)
                        or (len(covered) == len(best_cover) and (best_key is None or row_key < best_key))
                    ):
                        best_row = row
                        best_cover = covered
                        best_key = row_key

                if not best_row:
                    break

                if best_row["file"] not in seen:
                    seen.add(best_row["file"])
                    selected_files.append(best_row["file"])
                uncovered -= best_cover

        # Fallback if no day-level coverage was found.
        if not selected_files:
            for row in sorted(candidates, key=_sort_key):
                path = row["file"]
                if path in seen:
                    continue
                seen.add(path)
                selected_files.append(path)
        return selected_files

    def get_cost_estimate(
        self, ticker: str, schema: str, start: str, end: str, dataset: str = "XNAS.ITCH"
    ) -> Dict[str, Any]:
        """Get cost estimate from Databento before downloading."""
        client = self._get_client()
        # Databento end is exclusive - add 1 day.
        end_exclusive = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        cost = client.metadata.get_cost(
            dataset=dataset,
            symbols=[ticker],
            schema=schema,
            start=start,
            end=end_exclusive,
            stype_in="raw_symbol",
        )
        return {
            "estimated_cost_usd": cost,
            "ticker": ticker,
            "schema": schema,
            "start_date": start,
            "end_date": end,
            "dataset": dataset,
        }

    def _output_dir(self, schema: str) -> Path:
        if schema in ("mbp-10", "trades"):
            return self.l2_dir
        return self.ohlcv_dir

    def _output_filename(self, ticker: str, schema: str, start: str, end: str) -> str:
        if schema.startswith("ohlcv-"):
            return f"{ticker}_{schema}_{start}_{end}.csv"
        if schema == "trades":
            return f"{ticker}_trades_{start}_{end}.mbn"
        # mbp-10 (L2)
        return f"{ticker}_{start}_{end}.mbn"

    def _blocking_download(
        self,
        ticker: str,
        schema: str,
        start: str,
        end: str,
        dataset: str,
        convert_to_parquet: bool,
    ) -> CatalogEntry:
        """Synchronous download - runs in executor."""
        import databento as db

        client = self._get_client()
        out_dir = self._output_dir(schema)
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = self._output_filename(ticker, schema, start, end)
        out_path = out_dir / filename

        # Databento end is exclusive.
        end_exclusive = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        logger.info(f"Downloading {schema} for {ticker}: {start} -> {end} (exclusive: {end_exclusive})")

        data = client.timeseries.get_range(
            dataset=dataset,
            symbols=[ticker],
            schema=schema,
            start=start,
            end=end_exclusive,
            stype_in="raw_symbol",
        )

        entry = CatalogEntry(
            ticker=ticker,
            schema=schema,
            dataset=dataset,
            start_date=start,
            end_date=end,
            downloaded_at=datetime.utcnow().isoformat(),
            source_root=str(out_dir.resolve()),
            managed=True,
        )

        if schema.startswith("ohlcv-"):
            df = data.to_df()
            if df.empty:
                entry.status = "error"
                entry.error_message = "No data returned"
                return entry
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
                if "ts_event" in df.columns:
                    df = df.rename(columns={"ts_event": "timestamp"})
                elif "index" in df.columns:
                    df = df.rename(columns={"index": "timestamp"})
            df.to_csv(out_path, index=False)
            entry.file_csv = str(out_path)
            entry.size_bytes = out_path.stat().st_size
            entry.row_count = len(df)
        else:
            # Save as MBN first.
            data.replay(str(out_path))
            entry.file_mbn = str(out_path)

            if convert_to_parquet:
                parquet_path = out_path.with_suffix(".parquet")
                logger.info(f"Converting to Parquet: {parquet_path}")
                stored = db.DBNStore.from_file(str(out_path))
                df = stored.to_df()
                df.to_parquet(str(parquet_path))
                entry.file_parquet = str(parquet_path)
                entry.row_count = len(df)
                entry.size_bytes = parquet_path.stat().st_size
            else:
                entry.size_bytes = out_path.stat().st_size

        entry.status = "ready"
        entry.progress_pct = 100.0
        return entry

    async def download(
        self,
        ticker: str,
        schema: str,
        start_date: str,
        end_date: str,
        dataset: str = "XNAS.ITCH",
        convert_to_parquet: bool = True,
        broadcast_fn: Optional[Callable] = None,
    ) -> CatalogEntry:
        """Download data from Databento asynchronously, one file per day."""
        job_key = f"{ticker}:{schema}:{start_date}:{end_date}"
        if job_key in self._active_downloads:
            raise RuntimeError(f"Download already in progress: {job_key}")

        days = self._iter_days(start_date, end_date)
        if not days:
            raise RuntimeError(f"No days to download: {start_date} -> {end_date}")

        self._active_downloads[job_key] = {
            "status": "downloading",
            "ticker": ticker,
            "schema": schema,
            "start_date": start_date,
            "end_date": end_date,
            "total_days": len(days),
        }

        if broadcast_fn:
            await broadcast_fn(
                {
                    "type": "download_progress",
                    "ticker": ticker,
                    "schema": schema,
                    "status": "downloading",
                    "progress_pct": 0,
                    "message": f"Downloading {schema} data for {ticker} in {len(days)} day chunk(s)...",
                }
            )

        source_root = str(self._output_dir(schema).resolve())
        summary = CatalogEntry(
            ticker=ticker,
            schema=schema,
            dataset=dataset,
            start_date=start_date,
            end_date=end_date,
            downloaded_at=datetime.utcnow().isoformat(),
            source_root=source_root,
            managed=True,
            status="ready",
            progress_pct=100.0,
        )

        downloaded_days = 0
        skipped_days = 0
        error_days = 0
        total_rows = 0
        errors: List[str] = []

        try:
            loop = asyncio.get_event_loop()
            entries = self.list_catalog(refresh=False, ticker=ticker)
            for idx, day in enumerate(days, start=1):
                progress_before = round(((idx - 1) / len(days)) * 100.0, 1)

                if self._has_ready_coverage_for_day(
                    ticker=ticker,
                    schema=schema,
                    day=day,
                    entries=entries,
                ):
                    skipped_days += 1
                    if broadcast_fn:
                        await broadcast_fn(
                            {
                                "type": "download_progress",
                                "ticker": ticker,
                                "schema": schema,
                                "status": "downloading",
                                "progress_pct": progress_before,
                                "message": (
                                    f"[{idx}/{len(days)}] Skipping {day} "
                                    "(already covered by ready data)"
                                ),
                            }
                        )
                    continue

                pending = CatalogEntry(
                    ticker=ticker,
                    schema=schema,
                    dataset=dataset,
                    start_date=day,
                    end_date=day,
                    status="downloading",
                    progress_pct=progress_before,
                    source_root=source_root,
                    managed=True,
                )
                self.catalog.upsert(pending)
                entries.append(asdict(pending))

                if broadcast_fn:
                    await broadcast_fn(
                        {
                            "type": "download_progress",
                            "ticker": ticker,
                            "schema": schema,
                            "status": "downloading",
                            "progress_pct": progress_before,
                            "message": f"[{idx}/{len(days)}] Downloading {day}...",
                        }
                    )

                try:
                    entry = await loop.run_in_executor(
                        None,
                        self._blocking_download,
                        ticker,
                        schema,
                        day,
                        day,
                        dataset,
                        convert_to_parquet,
                    )
                except Exception as exc:
                    entry = CatalogEntry(
                        ticker=ticker,
                        schema=schema,
                        dataset=dataset,
                        start_date=day,
                        end_date=day,
                        status="error",
                        error_message=str(exc),
                        source_root=source_root,
                        managed=True,
                    )

                self.catalog.upsert(entry)
                entries = self.list_catalog(refresh=False, ticker=ticker)
                if entry.status == "ready":
                    downloaded_days += 1
                    total_rows += int(entry.row_count or 0)
                else:
                    error_days += 1
                    errors.append(f"{day}: {entry.error_message or 'download failed'}")

            summary.row_count = total_rows
            if error_days > 0:
                summary.status = "error"
                summary.error_message = "; ".join(errors[:3])
                if broadcast_fn:
                    await broadcast_fn(
                        {
                            "type": "download_progress",
                            "ticker": ticker,
                            "schema": schema,
                            "status": "error",
                            "progress_pct": 100,
                            "message": (
                                f"Daily download finished with errors for {ticker} {schema}: "
                                f"{downloaded_days} downloaded, {skipped_days} skipped, {error_days} failed."
                            ),
                        }
                    )
            else:
                if broadcast_fn:
                    await broadcast_fn(
                        {
                            "type": "download_progress",
                            "ticker": ticker,
                            "schema": schema,
                            "status": "ready",
                            "progress_pct": 100,
                            "message": (
                                f"Daily download complete: {ticker} {schema} "
                                f"({downloaded_days} downloaded, {skipped_days} skipped)."
                            ),
                        }
                    )

            return summary
        finally:
            self._active_downloads.pop(job_key, None)

    def delete_entry(self, ticker: str, schema: str, start: str, end: str) -> bool:
        """Delete local managed files and remove from catalog."""
        entry = self.catalog.find(ticker, schema, start, end)
        if not entry:
            return False

        if not bool(entry.get("managed", True)):
            logger.warning(
                "Refusing to delete unmanaged entry outside workspace: "
                f"{ticker}:{schema}:{start}:{end}"
            )
            return False

        for key in ("file_mbn", "file_parquet", "file_csv"):
            path_str = entry.get(key)
            if not path_str:
                continue
            path = Path(path_str)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted: {path}")

        return self.catalog.remove(ticker, schema, start, end)

    def get_active_downloads(self) -> List[Dict[str, Any]]:
        return list(self._active_downloads.values())

    def get_schemas(self) -> Dict[str, Any]:
        return SUPPORTED_SCHEMAS
