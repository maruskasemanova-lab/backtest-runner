"""
Databento data loader service.
Downloads and catalogs L2, OHLCV, trades, and TCBBO data from Databento.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from .parquet_compat import read_parquet_compat, write_parquet_compat
from .system_settings import SystemSettings

logger = logging.getLogger("DatabentoService")

SUPPORTED_SCHEMAS = {
    "mbp-10": {"description": "L2 Market Depth (10 levels)", "ext_primary": ".mbn"},
    "ohlcv-1m": {"description": "1-Minute OHLCV Bars", "ext_primary": ".csv"},
    "trades": {"description": "Raw Trade Tape", "ext_primary": ".mbn"},
    "tcbbo": {
        "description": "Options Trades With BBO (OPRA parent)",
        "ext_primary": ".parquet",
    },
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

    def find(
        self, ticker: str, schema: str, start: str, end: str
    ) -> Optional[Dict[str, Any]]:
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
        existing = self.find(
            entry.ticker, entry.schema, entry.start_date, entry.end_date
        )
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


class DatabentoService:
    """Downloads data from Databento and manages a unified local catalog."""

    def __init__(
        self,
        l2_dir: str = "data/l2",
        ohlcv_dir: str = "data",
        catalog_path: str = "data/data_catalog.json",
    ):
        resolved_catalog_path = (
            str(os.getenv("BACKTEST_DATA_CATALOG_PATH", "") or "").strip()
            or catalog_path
        )
        self.settings = SystemSettings()
        self.catalog = DataCatalog(resolved_catalog_path)
        self._active_downloads: Dict[str, Dict[str, Any]] = {}
        self._project_root = Path(__file__).resolve().parents[1]
        # Cache real OHLCV ET date ranges keyed by (path, mtime_ns, size_bytes).
        self._ohlcv_range_cache: Dict[
            Tuple[str, int, int], Optional[Tuple[str, str]]
        ] = {}
        self._remote_manifest_url = str(
            os.getenv("BACKTEST_REMOTE_MANIFEST_URL", "") or ""
        ).strip()
        timeout_raw = str(os.getenv("BACKTEST_REMOTE_TIMEOUT_SEC", "30") or "").strip()
        try:
            timeout_value = float(timeout_raw)
        except ValueError:
            timeout_value = 30.0
        self._remote_request_timeout_s = max(5.0, timeout_value)
        self._available_data_remote_only = self._env_bool(
            "BACKTEST_AVAILABLE_DATA_REMOTE_ONLY",
            default=False,
        )
        self._remote_manifest_required = self._env_bool(
            "BACKTEST_REMOTE_MANIFEST_REQUIRED",
            default=False,
        )
        sync_interval_raw = str(
            os.getenv("BACKTEST_REMOTE_SYNC_MIN_INTERVAL_SEC", "30") or "30"
        ).strip()
        try:
            sync_interval_value = float(sync_interval_raw)
        except ValueError:
            sync_interval_value = 30.0
        self._remote_sync_min_interval_s = max(0.0, sync_interval_value)
        self._last_remote_sync_epoch_s = 0.0
        self._auto_precompute_l2_on_download = self._env_bool(
            "BACKTEST_L2_AUTO_PRECOMPUTE_ON_DOWNLOAD",
            default=True,
        )
        self._auto_precompute_l2_include_icebergs = self._env_bool(
            "BACKTEST_L2_AUTO_PRECOMPUTE_INCLUDE_ICEBERGS",
            default=False,
        )

        self.l2_dir = Path(l2_dir)
        self.ohlcv_dir = Path(ohlcv_dir)
        self._ohlcv_scan_dirs: List[Path] = []
        self._l2_scan_dirs: List[Path] = []
        self._refresh_data_roots()

        # Always scan at startup so the catalog includes newly added external files.
        self.scan_existing_files()
        if self._remote_manifest_url:
            synced = self.sync_remote_manifest(self._remote_manifest_url)
            if synced > 0:
                logger.info("Synced %s remote catalog entries from manifest", synced)

    @staticmethod
    def _env_bool(name: str, default: bool = False) -> bool:
        raw = str(os.getenv(name, "") or "").strip().lower()
        if not raw:
            return bool(default)
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return bool(default)

    def _refresh_data_roots(self) -> None:
        self.settings.reload()
        self.ohlcv_dir = self.settings.primary_ohlcv_dir()
        self.l2_dir = self.settings.primary_l2_dir()
        self._ohlcv_scan_dirs = self.settings.get_ohlcv_dirs(existing_only=False)
        self._l2_scan_dirs = self.settings.get_l2_dirs(existing_only=False)
        # Auto-create primary data directories so the app works in dev
        # even before any data is downloaded.
        for d in (self.ohlcv_dir, self.l2_dir):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass

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
            raise RuntimeError(
                "DATABENTO_API_KEY is not set (env var or system settings)"
            )
        return db.Historical(api_key)

    @staticmethod
    def _is_valid_iso_date(value: str) -> bool:
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True
        except Exception:
            return False

    @staticmethod
    def _normalize_date_token(value: str) -> Optional[str]:
        token = str(value or "").strip()
        if DatabentoService._is_valid_iso_date(token):
            return token
        # TCBBO filenames often store compact YYYYMMDD tokens.
        if len(token) == 8 and token.isdigit():
            try:
                return datetime.strptime(token, "%Y%m%d").strftime("%Y-%m-%d")
            except Exception:
                return None
        return None

    @staticmethod
    def _compact_date_token(value: str) -> str:
        token = str(value or "").strip()
        if DatabentoService._is_valid_iso_date(token):
            return token.replace("-", "")
        return token

    @staticmethod
    def _resolve_download_request(
        ticker: str,
        schema: str,
        dataset: str,
    ) -> Dict[str, Any]:
        schema_lower = str(schema or "").strip().lower()
        ticker_upper = str(ticker or "").strip().upper()
        dataset_raw = str(dataset or "").strip()

        if schema_lower == "tcbbo":
            base_ticker = (
                ticker_upper[:-4] if ticker_upper.endswith(".OPT") else ticker_upper
            )
            if not base_ticker:
                raise ValueError("Ticker is required for tcbbo requests")
            return {
                "schema": schema_lower,
                "storage_ticker": base_ticker,
                "dataset": "OPRA.PILLAR",
                "symbols": [f"{base_ticker}.OPT"],
                "stype_in": "parent",
            }

        return {
            "schema": schema_lower,
            "storage_ticker": ticker_upper,
            "dataset": dataset_raw or "XNAS.ITCH",
            "symbols": [ticker_upper],
            "stype_in": "raw_symbol",
        }

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

        if not (
            DatabentoService._is_valid_iso_date(start_date)
            and DatabentoService._is_valid_iso_date(end_date)
        ):
            return None
        return ticker, schema, start_date, end_date

    @staticmethod
    def _parse_tcbbo_basename(stem: str) -> Optional[Tuple[str, str, str, str]]:
        # TCBBO: {TICKER}_OPRA_tcbbo_{YYYYMMDD|YYYY-MM-DD}_{YYYYMMDD|YYYY-MM-DD}
        marker = "_OPRA_tcbbo_"
        if marker not in stem:
            return None
        ticker, tail = stem.split(marker, 1)
        parts = tail.split("_")
        if len(parts) < 2:
            return None
        start_date = DatabentoService._normalize_date_token(parts[0])
        end_date = DatabentoService._normalize_date_token(parts[1])
        if not start_date or not end_date:
            return None
        return ticker.upper(), "tcbbo", start_date, end_date

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
        if not (
            DatabentoService._is_valid_iso_date(start_date)
            and DatabentoService._is_valid_iso_date(end_date)
        ):
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

    @staticmethod
    def _is_remote_url(path_str: Optional[str]) -> bool:
        raw = str(path_str or "").strip().lower()
        return raw.startswith("https://") or raw.startswith("http://")

    @staticmethod
    def _is_s3_uri(path_str: Optional[str]) -> bool:
        raw = str(path_str or "").strip().lower()
        return raw.startswith("s3://")

    @classmethod
    def _is_remote_location(cls, path_str: Optional[str]) -> bool:
        return cls._is_remote_url(path_str) or cls._is_s3_uri(path_str)

    @classmethod
    def _is_remote_catalog_entry(cls, entry: Dict[str, Any]) -> bool:
        for key in ("file_mbn", "file_parquet", "file_csv"):
            if cls._is_remote_location(entry.get(key)):
                return True
        source_root = str(entry.get("source_root", "") or "").strip()
        if source_root.startswith("s3://") or cls._is_remote_url(source_root):
            return True
        return False

    def _sync_remote_manifest_if_due(self, *, force: bool) -> Dict[str, Any]:
        manifest_url = str(getattr(self, "_remote_manifest_url", "") or "").strip()
        if not manifest_url:
            return {
                "enabled": False,
                "url": "",
                "synced_entries": 0,
                "performed": False,
                "forced": bool(force),
            }

        now = float(time.time())
        last_sync = float(getattr(self, "_last_remote_sync_epoch_s", 0.0) or 0.0)
        min_interval = float(getattr(self, "_remote_sync_min_interval_s", 30.0) or 30.0)
        should_sync = (
            bool(force) or last_sync <= 0.0 or (now - last_sync) >= min_interval
        )
        synced = 0
        if should_sync:
            synced = int(self.sync_remote_manifest(manifest_url))
            if synced > 0:
                self._last_remote_sync_epoch_s = now
            else:
                self._last_remote_sync_epoch_s = 0.0

        return {
            "enabled": True,
            "url": manifest_url,
            "synced_entries": int(synced),
            "performed": bool(should_sync),
            "forced": bool(force),
        }

    def _remote_cache_dir(self) -> Path:
        configured = str(
            os.getenv("BACKTEST_REMOTE_CACHE_DIR", "data/remote_cache") or ""
        ).strip()
        base = Path(configured) if configured else Path("data/remote_cache")
        if not base.is_absolute():
            base = (self._project_root / base).resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _remote_cache_path_for_locator(self, locator: str) -> Path:
        parsed = urlparse(locator)
        suffix = Path(parsed.path).suffix
        digest = hashlib.sha256(locator.encode("utf-8")).hexdigest()
        filename = f"{digest}{suffix if suffix else '.bin'}"
        return self._remote_cache_dir() / filename

    @staticmethod
    def _parse_s3_uri(uri: str) -> Optional[Tuple[str, str]]:
        parsed = urlparse(str(uri or "").strip())
        if parsed.scheme.lower() != "s3":
            return None
        bucket = str(parsed.netloc or "").strip()
        key = str(parsed.path or "").lstrip("/")
        if not bucket or not key:
            return None
        return bucket, key

    def _get_s3_client(self):
        cached = getattr(self, "_remote_s3_client", None)
        if cached is not None:
            return cached

        endpoint = str(os.getenv("BACKTEST_REMOTE_S3_ENDPOINT", "") or "").strip()
        if not endpoint:
            account_id = str(
                os.getenv("BACKTEST_REMOTE_S3_ACCOUNT_ID", "") or ""
            ).strip()
            if account_id:
                endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
        access_key = str(
            os.getenv("BACKTEST_REMOTE_S3_ACCESS_KEY_ID", "") or ""
        ).strip()
        secret_key = str(
            os.getenv("BACKTEST_REMOTE_S3_SECRET_ACCESS_KEY", "") or ""
        ).strip()
        region = (
            str(os.getenv("BACKTEST_REMOTE_S3_REGION", "auto") or "auto").strip()
            or "auto"
        )

        try:
            import boto3  # type: ignore
        except Exception as exc:
            logger.warning("S3 remote data requested but boto3 import failed: %s", exc)
            self._remote_s3_client = None
            return None

        kwargs: Dict[str, Any] = {"region_name": region}
        if endpoint:
            kwargs["endpoint_url"] = endpoint
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        try:
            client = boto3.client("s3", **kwargs)
        except Exception as exc:
            logger.warning("Failed to initialize S3 client for remote data: %s", exc)
            self._remote_s3_client = None
            return None

        self._remote_s3_client = client
        return client

    def _download_remote_file_to_cache(
        self, locator: str, dest: Path
    ) -> Optional[Path]:
        tmp_path = dest.with_suffix(dest.suffix + ".part")
        timeout = float(getattr(self, "_remote_request_timeout_s", 30.0) or 30.0)
        try:
            if self._is_s3_uri(locator):
                parsed = self._parse_s3_uri(locator)
                if parsed is None:
                    return None
                bucket, key = parsed
                client = self._get_s3_client()
                if client is None:
                    return None
                response = client.get_object(Bucket=bucket, Key=key)
                body = response.get("Body")
                if body is None:
                    return None
                with tmp_path.open("wb") as handle:
                    while True:
                        chunk = body.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
            else:
                last_exc: Optional[Exception] = None
                for attempt in range(3):
                    try:
                        with requests.get(
                            locator, timeout=timeout, stream=True
                        ) as response:
                            response.raise_for_status()
                            with tmp_path.open("wb") as handle:
                                for chunk in response.iter_content(
                                    chunk_size=1024 * 1024
                                ):
                                    if chunk:
                                        handle.write(chunk)
                        last_exc = None
                        break
                    except Exception as exc:
                        last_exc = exc
                        if attempt < 2:
                            time.sleep(0.35 * (attempt + 1))
                if last_exc is not None:
                    raise last_exc
            tmp_path.replace(dest)
            return dest
        except Exception as exc:
            logger.warning("Failed to download remote file %s: %s", locator, exc)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            return None

    def _resolve_remote_entry_to_cache(self, locator: str) -> Optional[Path]:
        cache_path = self._remote_cache_path_for_locator(locator)
        if (
            cache_path.exists()
            and cache_path.is_file()
            and cache_path.stat().st_size > 0
        ):
            return cache_path
        return self._download_remote_file_to_cache(locator, cache_path)

    def _fetch_remote_manifest_payload(self, manifest_locator: str) -> Optional[Any]:
        timeout = float(getattr(self, "_remote_request_timeout_s", 30.0) or 30.0)
        try:
            if self._is_s3_uri(manifest_locator):
                parsed = self._parse_s3_uri(manifest_locator)
                if parsed is None:
                    return None
                bucket, key = parsed
                client = self._get_s3_client()
                if client is None:
                    return None
                response = client.get_object(Bucket=bucket, Key=key)
                body = response.get("Body")
                if body is None:
                    return None
                raw = body.read()
                return json.loads(raw.decode("utf-8"))

            last_exc: Optional[Exception] = None
            for attempt in range(3):
                try:
                    response = requests.get(manifest_locator, timeout=timeout)
                    response.raise_for_status()
                    return response.json()
                except Exception as exc:
                    last_exc = exc
                    if attempt < 2:
                        time.sleep(0.35 * (attempt + 1))
            if last_exc:
                raise last_exc
        except Exception as exc:
            logger.warning(
                "Failed to fetch remote manifest %s: %s", manifest_locator, exc
            )
            return None

    def sync_remote_manifest(self, manifest_url: Optional[str] = None) -> int:
        url = str(
            manifest_url or getattr(self, "_remote_manifest_url", "") or ""
        ).strip()
        if not url:
            return 0

        payload = self._fetch_remote_manifest_payload(url)
        if payload is None:
            return 0

        rows: List[Dict[str, Any]] = []
        if isinstance(payload, list):
            rows = [item for item in payload if isinstance(item, dict)]
        elif isinstance(payload, dict):
            candidates = payload.get("entries")
            if isinstance(candidates, list):
                rows = [item for item in candidates if isinstance(item, dict)]

        synced = 0
        for row in rows:
            ticker = str(row.get("ticker", "")).strip().upper()
            schema = str(row.get("schema", "")).strip().lower()
            start_date = str(row.get("start_date", "")).strip()
            end_date = str(row.get("end_date", "")).strip()
            if not ticker or not schema:
                continue
            if not (
                self._is_valid_iso_date(start_date)
                and self._is_valid_iso_date(end_date)
            ):
                continue

            file_mbn = (
                str(row.get("file_mbn") or row.get("public_url_mbn") or "").strip()
                or None
            )
            file_parquet = (
                str(
                    row.get("file_parquet") or row.get("public_url_parquet") or ""
                ).strip()
                or None
            )
            file_csv = (
                str(row.get("file_csv") or row.get("public_url_csv") or "").strip()
                or None
            )
            if not any((file_mbn, file_parquet, file_csv)):
                continue

            status = str(row.get("status", "ready") or "ready").strip().lower()
            if status not in {"ready", "downloading", "converting", "error"}:
                status = "ready"
            dataset = (
                str(row.get("dataset", "XNAS.ITCH") or "XNAS.ITCH").strip()
                or "XNAS.ITCH"
            )
            source_root = str(
                row.get("source_root", "remote_manifest") or "remote_manifest"
            ).strip()
            downloaded_at = (
                str(row.get("downloaded_at") or row.get("uploaded_at") or "").strip()
                or None
            )
            error_message = str(row.get("error_message") or "").strip() or None
            try:
                size_bytes = max(0, int(row.get("size_bytes", 0) or 0))
            except (TypeError, ValueError):
                size_bytes = 0
            try:
                row_count = max(0, int(row.get("row_count", 0) or 0))
            except (TypeError, ValueError):
                row_count = 0
            try:
                progress_pct = float(row.get("progress_pct", 100.0) or 100.0)
            except (TypeError, ValueError):
                progress_pct = 100.0

            entry = CatalogEntry(
                ticker=ticker,
                schema=schema,
                dataset=dataset,
                start_date=start_date,
                end_date=end_date,
                file_mbn=file_mbn,
                file_parquet=file_parquet,
                file_csv=file_csv,
                size_bytes=size_bytes,
                row_count=row_count,
                downloaded_at=downloaded_at,
                status=status,
                error_message=error_message,
                progress_pct=progress_pct,
                source_root=source_root,
                managed=False,
            )
            self.catalog.upsert(entry)
            synced += 1
        return synced

    def _resolve_entry_path(self, path_str: Optional[str]) -> Optional[Path]:
        if not path_str:
            return None
        if self._is_remote_location(path_str):
            return self._resolve_remote_entry_to_cache(str(path_str))
        path = Path(path_str).expanduser()
        if path.is_absolute():
            if path.exists():
                return path

            # Cross-environment fallback:
            # catalog may contain host absolute paths (e.g. /Users/... or /app/...)
            # that are not valid in current runtime. Try remapping by basename.
            basename = str(path.name or "").strip()
            if basename:
                candidate_roots = []
                seen = set()

                def _add_root(root: Optional[Path]) -> None:
                    if root is None:
                        return
                    try:
                        resolved = root.resolve()
                    except Exception:
                        return
                    key = str(resolved)
                    if key in seen:
                        return
                    seen.add(key)
                    candidate_roots.append(resolved)

                _add_root(self._project_root / "data")
                _add_root(self._project_root / "data" / "l2")
                _add_root(getattr(self, "ohlcv_dir", None))
                _add_root(getattr(self, "l2_dir", None))
                for root in list(getattr(self, "_ohlcv_scan_dirs", []) or []):
                    _add_root(root)
                for root in list(getattr(self, "_l2_scan_dirs", []) or []):
                    _add_root(root)

                for root in candidate_roots:
                    remapped = root / basename
                    if remapped.exists():
                        try:
                            return remapped.resolve()
                        except Exception:
                            return remapped

            return path

        resolved_relative = (self._project_root / path).resolve()
        if resolved_relative.exists():
            return resolved_relative
        return resolved_relative

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

        if not hasattr(self, "_ohlcv_range_cache") or not isinstance(
            self._ohlcv_range_cache, dict
        ):
            self._ohlcv_range_cache = {}

        mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9)))
        key = (str(path.resolve()), mtime_ns, int(stat.st_size))
        if key in self._ohlcv_range_cache:
            return self._ohlcv_range_cache[key]

        try:
            if path.suffix.lower() in (".parquet", ".parq"):
                df = read_parquet_compat(path)
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
        if self._is_remote_location(preferred_file):
            if self._is_valid_iso_date(start_date) and self._is_valid_iso_date(
                end_date
            ):
                return start_date, end_date
            return "", ""

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
            if not data_dir.exists():
                try:
                    data_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    continue
            if not data_dir.is_dir():
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
            if not data_dir.exists():
                try:
                    data_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    continue
            if not data_dir.is_dir():
                continue

            grouped: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
            for pattern in (
                "*_ohlcv-*_*.csv",
                "*_ohlcv-*_*.parquet",
                "*_ohlcv-*_*.parq",
            ):
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
                    downloaded_at=(
                        datetime.fromtimestamp(preferred.stat().st_mtime).isoformat()
                        if preferred.exists()
                        else None
                    ),
                    source_root=info.get("source_root"),
                    managed=self._is_managed_path(preferred),
                )
                self.catalog.upsert(entry)
                new_entries.append(entry)

        # Scan TCBBO files (OPRA options flow parquet)
        for data_dir in self._ohlcv_scan_dirs:
            if not data_dir.exists():
                try:
                    data_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    continue
            if not data_dir.is_dir():
                continue

            grouped: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
            for file_path in data_dir.glob("*_OPRA_tcbbo_*_*.parquet"):
                parsed = self._parse_tcbbo_basename(file_path.stem)
                if not parsed:
                    continue
                ticker, schema, start_date, end_date = parsed
                key = (ticker, schema, start_date, end_date)
                grouped[key] = {
                    "ticker": ticker,
                    "schema": schema,
                    "start_date": start_date,
                    "end_date": end_date,
                    "file_parquet": file_path,
                    "source_root": str(data_dir.resolve()),
                }

            for ticker, schema, start_date, end_date in grouped.keys():
                if self.catalog.find(ticker, schema, start_date, end_date):
                    continue
                info = grouped[(ticker, schema, start_date, end_date)]
                parquet_path = info.get("file_parquet")
                if parquet_path is None:
                    continue

                entry = CatalogEntry(
                    ticker=ticker,
                    schema=schema,
                    dataset="OPRA.PILLAR",
                    start_date=start_date,
                    end_date=end_date,
                    file_parquet=str(parquet_path),
                    size_bytes=(
                        parquet_path.stat().st_size if parquet_path.exists() else 0
                    ),
                    status="ready",
                    downloaded_at=(
                        datetime.fromtimestamp(parquet_path.stat().st_mtime).isoformat()
                        if parquet_path.exists()
                        else None
                    ),
                    source_root=info.get("source_root"),
                    managed=self._is_managed_path(parquet_path),
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
        remote_manifest_info = self._sync_remote_manifest_if_due(force=bool(refresh))
        entries = self.list_catalog(refresh=refresh)
        remote_only = bool(getattr(self, "_available_data_remote_only", False))
        if remote_only:
            entries = [
                entry for entry in entries if self._is_remote_catalog_entry(entry)
            ]
        tickers = set()
        l2_tickers = set()
        date_ranges: Dict[str, Dict[str, Any]] = {}
        l2_date_ranges: Dict[str, Dict[str, Any]] = {}

        def _merge_date_range(
            target: Dict[str, Dict[str, Any]],
            *,
            ticker: str,
            start_date: str,
            end_date: str,
            file_name: Optional[str] = None,
        ) -> None:
            if not (
                self._is_valid_iso_date(start_date)
                and self._is_valid_iso_date(end_date)
            ):
                return
            if ticker not in target:
                target[ticker] = {
                    "start": start_date,
                    "end": end_date,
                    "files": [],
                }
            else:
                if start_date < target[ticker]["start"]:
                    target[ticker]["start"] = start_date
                if end_date > target[ticker]["end"]:
                    target[ticker]["end"] = end_date

            if file_name and file_name not in target[ticker]["files"]:
                target[ticker]["files"].append(file_name)

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
                for key in ("file_parquet", "file_csv"):
                    file_path = entry.get(key)
                    file_name = Path(file_path).name if file_path else None
                    _merge_date_range(
                        date_ranges,
                        ticker=ticker,
                        start_date=start_date,
                        end_date=end_date,
                        file_name=file_name,
                    )

            if schema == "mbp-10":
                l2_tickers.add(ticker)
                for key in ("file_parquet", "file_mbn", "file_csv"):
                    file_path = entry.get(key)
                    file_name = Path(file_path).name if file_path else None
                    _merge_date_range(
                        l2_date_ranges,
                        ticker=ticker,
                        start_date=str(entry.get("start_date", "")).strip(),
                        end_date=str(entry.get("end_date", "")).strip(),
                        file_name=file_name,
                    )

        # Keep compatibility: include pure-L2 tickers in ticker list as well.
        tickers.update(l2_tickers)
        l2_overlap_date_ranges: Dict[str, Dict[str, Any]] = {}
        for ticker in sorted(tickers):
            ohlcv_range = date_ranges.get(ticker)
            l2_range = l2_date_ranges.get(ticker)
            if not ohlcv_range or not l2_range:
                continue
            overlap_start = max(
                str(ohlcv_range.get("start", "")),
                str(l2_range.get("start", "")),
            )
            overlap_end = min(
                str(ohlcv_range.get("end", "")),
                str(l2_range.get("end", "")),
            )
            if not (
                self._is_valid_iso_date(overlap_start)
                and self._is_valid_iso_date(overlap_end)
                and overlap_start <= overlap_end
            ):
                continue
            l2_overlap_date_ranges[ticker] = {
                "start": overlap_start,
                "end": overlap_end,
            }

        summary = {
            "tickers": sorted(tickers),
            "l2_tickers": sorted(l2_tickers),
            "date_ranges": date_ranges,
            "l2_date_ranges": l2_date_ranges,
            "l2_overlap_date_ranges": l2_overlap_date_ranges,
            "data_dir": str(self.ohlcv_dir),
            "data_dirs": [str(p) for p in self._ohlcv_scan_dirs],
            "l2_dirs": [str(p) for p in self._l2_scan_dirs],
            "remote_manifest": {
                **remote_manifest_info,
                "remote_only": bool(remote_only),
            },
        }
        require_remote = bool(getattr(self, "_remote_manifest_required", False))
        if require_remote:
            if not str(getattr(self, "_remote_manifest_url", "") or "").strip():
                raise RuntimeError(
                    "BACKTEST_REMOTE_MANIFEST_URL is required but not configured."
                )
            if not summary["tickers"]:
                raise RuntimeError(
                    "Remote manifest is required but yielded no available tickers."
                )
        return summary

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
        return (
            entry.get("file_parquet") or entry.get("file_csv") or entry.get("file_mbn")
        )

    def _has_ready_coverage_for_day(
        self,
        ticker: str,
        schema: str,
        day: str,
        entries: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        ticker_upper = str(ticker or "").upper()
        schema_lower = str(schema or "").lower()
        rows = (
            entries
            if entries is not None
            else self.list_catalog(refresh=False, ticker=ticker_upper)
        )
        if bool(getattr(self, "_available_data_remote_only", False)):
            rows = [entry for entry in rows if self._is_remote_catalog_entry(entry)]
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
            if self._is_remote_location(preferred_file):
                return True
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
        self._sync_remote_manifest_if_due(force=False)
        ticker_upper = str(ticker or "").upper()
        schema_lower = str(schema or "").lower()
        days = self._iter_days(start_date, end_date)
        entries = self.list_catalog(refresh=False, ticker=ticker_upper)
        if bool(getattr(self, "_available_data_remote_only", False)):
            entries = [
                entry for entry in entries if self._is_remote_catalog_entry(entry)
            ]
        has_schema_entries = any(
            str(entry.get("schema", "")).lower() == schema_lower for entry in entries
        )
        if (
            not has_schema_entries
            and str(getattr(self, "_remote_manifest_url", "") or "").strip()
        ):
            self._sync_remote_manifest_if_due(force=True)
            entries = self.list_catalog(refresh=False, ticker=ticker_upper)
            if bool(getattr(self, "_available_data_remote_only", False)):
                entries = [
                    entry for entry in entries if self._is_remote_catalog_entry(entry)
                ]
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
        self._sync_remote_manifest_if_due(force=False)
        ticker = ticker.upper()
        candidates: List[Dict[str, Any]] = []
        entries = self.list_catalog(refresh=False, ticker=ticker)
        if bool(getattr(self, "_available_data_remote_only", False)):
            entries = [
                entry for entry in entries if self._is_remote_catalog_entry(entry)
            ]
        has_schema_entries = any(
            str(entry.get("schema", "")).lower().startswith(schema_prefix.lower())
            for entry in entries
        )
        if (
            not has_schema_entries
            and str(getattr(self, "_remote_manifest_url", "") or "").strip()
        ):
            self._sync_remote_manifest_if_due(force=True)
            entries = self.list_catalog(refresh=False, ticker=ticker)
            if bool(getattr(self, "_available_data_remote_only", False)):
                entries = [
                    entry for entry in entries if self._is_remote_catalog_entry(entry)
                ]
        for entry in entries:
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
            if self._is_remote_location(preferred_file):
                preferred_path = self._resolve_remote_entry_to_cache(
                    str(preferred_file)
                )
            else:
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
                    if len(covered) > len(best_cover) or (
                        len(covered) == len(best_cover)
                        and (best_key is None or row_key < best_key)
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
        request_meta = self._resolve_download_request(
            ticker=ticker,
            schema=schema,
            dataset=dataset,
        )
        # Databento end is exclusive - add 1 day.
        end_exclusive = (
            datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        cost = client.metadata.get_cost(
            dataset=request_meta["dataset"],
            symbols=request_meta["symbols"],
            schema=request_meta["schema"],
            start=start,
            end=end_exclusive,
            stype_in=request_meta["stype_in"],
        )
        return {
            "estimated_cost_usd": cost,
            "ticker": request_meta["storage_ticker"],
            "schema": request_meta["schema"],
            "start_date": start,
            "end_date": end,
            "dataset": request_meta["dataset"],
        }

    def _output_dir(self, schema: str) -> Path:
        if schema in ("mbp-10", "trades"):
            return self.l2_dir
        return self.ohlcv_dir

    def _output_filename(self, ticker: str, schema: str, start: str, end: str) -> str:
        if schema == "tcbbo":
            start_compact = self._compact_date_token(start)
            end_compact = self._compact_date_token(end)
            return f"{ticker}_OPRA_tcbbo_{start_compact}_{end_compact}.parquet"
        if schema.startswith("ohlcv-"):
            return f"{ticker}_{schema}_{start}_{end}.csv"
        if schema == "trades":
            return f"{ticker}_trades_{start}_{end}.mbn"
        # mbp-10 (L2)
        return f"{ticker}_{start}_{end}.mbn"

    def _precomputed_l2_dir(self) -> Path:
        configured = str(
            os.getenv("BACKTEST_L2_PRECOMPUTED_DIR", "data/l2_precomputed") or ""
        ).strip()
        base = Path(configured) if configured else Path("data/l2_precomputed")
        if not base.is_absolute():
            base = (self._project_root / base).resolve()
        base.mkdir(parents=True, exist_ok=True)
        return base

    @staticmethod
    def _feature_rows_from_map(
        feature_map: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for minute_key in sorted(feature_map.keys()):
            features = feature_map.get(minute_key) or {}
            row: Dict[str, Any] = {"minute_key": int(minute_key)}
            if isinstance(features, dict):
                row.update(features)
            rows.append(row)
        return rows

    def _blocking_precompute_l2_day(
        self,
        ticker: str,
        day: str,
        include_icebergs: bool,
    ) -> Dict[str, Any]:
        from .l2_data_manager import L2DataManager
        from .l2_feature_service import L2FeatureService

        l2_dirs = [
            str(path)
            for path in getattr(self, "_l2_scan_dirs", [])
            if isinstance(path, Path)
        ]
        if not l2_dirs:
            l2_dirs = [str(self.l2_dir)]

        manager = L2DataManager(data_dirs=l2_dirs)
        manager.precomputed_features_enabled = False
        service = L2FeatureService(
            manager=manager,
            logger=logger,
            iceberg_detection_enabled=bool(include_icebergs),
        )

        start_dt = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(days=1) - timedelta(microseconds=1)
        feature_map, stats = service.build_feature_map(
            ticker=str(ticker).upper(),
            start_dt_utc=start_dt,
            end_dt_utc=end_dt,
        )
        if not feature_map:
            return {
                "built": False,
                "day": day,
                "ticker": str(ticker).upper(),
                "reason": "no_features",
                "minutes": 0,
                "file": "",
                "trade_events": int(stats.get("trade_events", 0) or 0),
            }

        rows = self._feature_rows_from_map(feature_map)
        frame = pd.DataFrame(rows)
        out_file = self._precomputed_l2_dir() / f"{str(ticker).upper()}_{day}.parquet"
        write_parquet_compat(frame, out_file, index=False)
        return {
            "built": True,
            "day": day,
            "ticker": str(ticker).upper(),
            "minutes": len(rows),
            "file": str(out_file),
            "trade_events": int(stats.get("trade_events", 0) or 0),
        }

    @staticmethod
    def _write_store_to_mbn(data: Any, out_path: Path) -> None:
        """
        Persist DBN payload to .mbn across Databento client versions.

        Newer Databento clients expose `to_file(path)`, while older clients
        accepted `replay(path)` for direct file writes.
        """
        target = str(out_path)

        writer = getattr(data, "to_file", None)
        if callable(writer):
            writer(target)
            return

        replay = getattr(data, "replay", None)
        if callable(replay):
            try:
                replay(target)
                return
            except TypeError as exc:
                raise RuntimeError(
                    "Databento DBNStore.replay now expects a callback; "
                    "use a client version with DBNStore.to_file support."
                ) from exc

        raise RuntimeError(
            "Databento response cannot be persisted: missing to_file()/replay()."
        )

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

        request_meta = self._resolve_download_request(
            ticker=ticker,
            schema=schema,
            dataset=dataset,
        )
        schema = request_meta["schema"]
        ticker = request_meta["storage_ticker"]
        dataset = request_meta["dataset"]

        client = self._get_client()
        out_dir = self._output_dir(schema)
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = self._output_filename(ticker, schema, start, end)
        out_path = out_dir / filename

        # Databento end is exclusive.
        end_exclusive = (
            datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")
        logger.info(
            f"Downloading {schema} for {ticker}: {start} -> {end} (exclusive: {end_exclusive})"
        )

        data = client.timeseries.get_range(
            dataset=dataset,
            symbols=request_meta["symbols"],
            schema=schema,
            start=start,
            end=end_exclusive,
            stype_in=request_meta["stype_in"],
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
        elif schema == "tcbbo":
            df = data.to_df()
            if df.empty:
                entry.status = "error"
                entry.error_message = "No data returned"
                return entry
            write_parquet_compat(df, str(out_path), index=False)
            entry.file_parquet = str(out_path)
            entry.size_bytes = out_path.stat().st_size
            entry.row_count = len(df)
        else:
            # Save as MBN first.
            self._write_store_to_mbn(data, out_path)
            entry.file_mbn = str(out_path)

            if convert_to_parquet:
                parquet_path = out_path.with_suffix(".parquet")
                logger.info(f"Converting to Parquet: {parquet_path}")
                stored = db.DBNStore.from_file(str(out_path))
                df = stored.to_df()
                write_parquet_compat(df, str(parquet_path), index=True)
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
        schema_lower = str(schema or "").strip().lower()
        request_meta = self._resolve_download_request(
            ticker=ticker,
            schema=schema_lower,
            dataset=dataset,
        )
        ticker_upper = str(request_meta["storage_ticker"]).upper()
        dataset = str(request_meta["dataset"])

        if schema_lower not in SUPPORTED_SCHEMAS:
            raise RuntimeError(f"Unsupported schema: {schema}")

        job_key = f"{ticker_upper}:{schema_lower}:{start_date}:{end_date}"
        if job_key in self._active_downloads:
            raise RuntimeError(f"Download already in progress: {job_key}")

        days = self._iter_days(start_date, end_date)
        if not days:
            raise RuntimeError(f"No days to download: {start_date} -> {end_date}")

        self._active_downloads[job_key] = {
            "status": "downloading",
            "ticker": ticker_upper,
            "schema": schema_lower,
            "start_date": start_date,
            "end_date": end_date,
            "total_days": len(days),
        }

        if broadcast_fn:
            await broadcast_fn(
                {
                    "type": "download_progress",
                    "ticker": ticker_upper,
                    "schema": schema_lower,
                    "status": "downloading",
                    "progress_pct": 0,
                    "message": f"Downloading {schema_lower} data for {ticker_upper} in {len(days)} day chunk(s)...",
                }
            )

        source_root = str(self._output_dir(schema_lower).resolve())
        summary = CatalogEntry(
            ticker=ticker_upper,
            schema=schema_lower,
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
            entries = self.list_catalog(refresh=False, ticker=ticker_upper)
            for idx, day in enumerate(days, start=1):
                progress_before = round(((idx - 1) / len(days)) * 100.0, 1)

                if self._has_ready_coverage_for_day(
                    ticker=ticker_upper,
                    schema=schema_lower,
                    day=day,
                    entries=entries,
                ):
                    skipped_days += 1
                    if broadcast_fn:
                        await broadcast_fn(
                            {
                                "type": "download_progress",
                                "ticker": ticker_upper,
                                "schema": schema_lower,
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
                    ticker=ticker_upper,
                    schema=schema_lower,
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
                            "ticker": ticker_upper,
                            "schema": schema_lower,
                            "status": "downloading",
                            "progress_pct": progress_before,
                            "message": f"[{idx}/{len(days)}] Downloading {day}...",
                        }
                    )

                try:
                    entry = await loop.run_in_executor(
                        None,
                        self._blocking_download,
                        ticker_upper,
                        schema_lower,
                        day,
                        day,
                        dataset,
                        convert_to_parquet,
                    )
                except Exception as exc:
                    entry = CatalogEntry(
                        ticker=ticker_upper,
                        schema=schema_lower,
                        dataset=dataset,
                        start_date=day,
                        end_date=day,
                        status="error",
                        error_message=str(exc),
                        source_root=source_root,
                        managed=True,
                    )

                self.catalog.upsert(entry)
                entries = self.list_catalog(refresh=False, ticker=ticker_upper)
                if entry.status == "ready":
                    downloaded_days += 1
                    total_rows += int(entry.row_count or 0)
                    should_precompute = bool(
                        str(schema_lower).lower() == "mbp-10"
                        and bool(
                            getattr(self, "_auto_precompute_l2_on_download", False)
                        )
                    )
                    if should_precompute:
                        try:
                            precompute_result = await loop.run_in_executor(
                                None,
                                self._blocking_precompute_l2_day,
                                ticker_upper,
                                day,
                                bool(
                                    getattr(
                                        self,
                                        "_auto_precompute_l2_include_icebergs",
                                        False,
                                    )
                                ),
                            )
                            if bool(precompute_result.get("built")):
                                logger.info(
                                    "Auto-precomputed L2 features for %s %s (%s minutes)",
                                    ticker_upper,
                                    day,
                                    int(precompute_result.get("minutes", 0) or 0),
                                )
                            else:
                                logger.warning(
                                    "Skipped auto-precompute for %s %s: %s",
                                    ticker_upper,
                                    day,
                                    str(precompute_result.get("reason", "unknown")),
                                )
                        except Exception as precompute_exc:
                            logger.warning(
                                "Auto-precompute failed for %s %s: %s",
                                ticker_upper,
                                day,
                                precompute_exc,
                            )
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
                            "ticker": ticker_upper,
                            "schema": schema_lower,
                            "status": "error",
                            "progress_pct": 100,
                            "message": (
                                f"Daily download finished with errors for {ticker_upper} {schema_lower}: "
                                f"{downloaded_days} downloaded, {skipped_days} skipped, {error_days} failed."
                            ),
                        }
                    )
            else:
                if broadcast_fn:
                    await broadcast_fn(
                        {
                            "type": "download_progress",
                            "ticker": ticker_upper,
                            "schema": schema_lower,
                            "status": "ready",
                            "progress_pct": 100,
                            "message": (
                                f"Daily download complete: {ticker_upper} {schema_lower} "
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
