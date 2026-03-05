from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd


class DatasetInputError(ValueError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_dataset_identifier(value: Any) -> Optional[str]:
    token = str(value or "").strip()
    if not token:
        return None
    if len(token) > 128:
        raise DatasetInputError(
            code="invalid_dataset_id",
            message="dataset_id must be <= 128 characters",
        )
    for ch in token:
        if ch.isalnum() or ch in {"-", "_", "."}:
            continue
        raise DatasetInputError(
            code="invalid_dataset_id",
            message="dataset_id contains invalid characters",
        )
    return token


def normalize_dataset_status(value: Any) -> str:
    token = str(value or "").strip().lower() or "ready"
    if len(token) > 32:
        raise DatasetInputError(
            code="invalid_dataset_status",
            message="status must be <= 32 characters",
        )
    for ch in token:
        if ch.isalnum() or ch in {"-", "_"}:
            continue
        raise DatasetInputError(
            code="invalid_dataset_status",
            message="status contains invalid characters",
        )
    return token


def normalize_dataset_format(
    value: Any,
    *,
    default: Optional[str] = "parquet",
) -> Optional[str]:
    token = str(value or "").strip().lower()
    if not token:
        token = str(default or "").strip().lower()
    if not token:
        return None
    if len(token) > 32:
        raise DatasetInputError(
            code="invalid_dataset_format",
            message="file format must be <= 32 characters",
        )
    for ch in token:
        if ch.isalnum() or ch in {"-", "_"}:
            continue
        raise DatasetInputError(
            code="invalid_dataset_format",
            message="file format contains invalid characters",
        )
    return token


def storage_path_segment(value: Any, *, default: str) -> str:
    token = str(value or "").strip()
    if not token:
        return default
    cleaned = "".join(
        ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in token
    ).strip("._")
    return cleaned or default


def default_user_dataset_s3_path(
    *,
    user_id: str,
    dataset_id: str,
    file_format: str,
    prefer_remote: bool = True,
) -> str:
    ext = storage_path_segment(file_format, default="parquet").lower()
    safe_user_id = storage_path_segment(user_id, default="user")
    safe_dataset_id = storage_path_segment(dataset_id, default="dataset")
    object_key = f"users/{safe_user_id}/datasets/{safe_dataset_id}.{ext}"
    if not prefer_remote:
        return object_key
    bucket = str(os.getenv("BACKTEST_USER_DATASETS_BUCKET") or "").strip().rstrip("/")
    if not bucket:
        return object_key
    if "://" in bucket:
        return f"{bucket}/{object_key}"
    return f"s3://{bucket}/{object_key}"


def format_user_dataset(dataset: Dict[str, Any]) -> Dict[str, Any]:
    payload = dataset if isinstance(dataset, dict) else {}
    return {
        "dataset_id": str(payload.get("dataset_id") or ""),
        "user_id": str(payload.get("user_id") or ""),
        "tenant_id": str(payload.get("tenant_id") or ""),
        "dataset_name": str(payload.get("dataset_name") or ""),
        "source_filename": str(payload.get("source_filename") or "") or None,
        "s3_path": str(payload.get("s3_path") or ""),
        "status": str(payload.get("status") or ""),
        "file_format": str(payload.get("file_format") or ""),
        "source_format": str(payload.get("source_format") or "") or None,
        "row_count": (
            None
            if payload.get("row_count") is None
            else int(payload.get("row_count") or 0)
        ),
        "size_bytes": (
            None
            if payload.get("size_bytes") is None
            else int(payload.get("size_bytes") or 0)
        ),
        "schema_name": str(payload.get("schema_name") or "") or None,
        "metadata": (
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        ),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
    }


def user_datasets_local_cache_dir() -> Path:
    configured = str(
        os.getenv("BACKTEST_USER_DATASETS_LOCAL_CACHE_DIR") or "data/user_datasets"
    ).strip()
    base = Path(configured) if configured else Path("data/user_datasets")
    if not base.is_absolute():
        base = (Path.cwd() / base).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def user_dataset_local_cache_path(*, user_id: str, dataset_id: str) -> Path:
    safe_user_id = storage_path_segment(user_id, default="user")
    safe_dataset_id = storage_path_segment(dataset_id, default="dataset")
    target = user_datasets_local_cache_dir() / safe_user_id / f"{safe_dataset_id}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def user_dataset_upload_max_bytes() -> int:
    raw = os.getenv("BACKTEST_USER_DATASET_UPLOAD_MAX_BYTES")
    try:
        parsed = int(str(raw).strip()) if raw is not None else 25 * 1024 * 1024
    except Exception:
        parsed = 25 * 1024 * 1024
    return max(1, parsed)


def is_http_remote_locator(locator: str) -> bool:
    scheme = str(urlparse(str(locator or "").strip()).scheme or "").strip().lower()
    return scheme in {"http", "https"}


def user_dataset_storage_mode() -> str:
    mode = str(os.getenv("BACKTEST_USER_DATASETS_STORAGE_MODE") or "auto").strip().lower()
    if mode in {"local", "remote"}:
        return mode
    return "auto"


def request_prefers_local_user_datasets(request: Optional[Any]) -> bool:
    mode = user_dataset_storage_mode()
    if mode == "local":
        return True
    if mode == "remote":
        return False
    host = ""
    if request is not None:
        try:
            host = str(request.url.hostname or "").strip().lower()
        except Exception:
            host = ""
    if host in {"", "localhost", "127.0.0.1", "::1", "0.0.0.0", "testserver"}:
        return True
    bucket = str(os.getenv("BACKTEST_USER_DATASETS_BUCKET") or "").strip()
    return not bool(bucket)


def parse_s3_locator(locator: str) -> Optional[Tuple[str, str]]:
    parsed = urlparse(str(locator or "").strip())
    if parsed.scheme.lower() != "s3":
        return None
    bucket = str(parsed.netloc or "").strip()
    key = str(parsed.path or "").lstrip("/")
    if not bucket or not key:
        return None
    return bucket, key


def read_csv_upload_frame(
    *,
    body: bytes,
    encoding: str,
    delimiter: str,
) -> pd.DataFrame:
    raw_encoding = str(encoding or "").strip() or "utf-8"
    raw_delimiter = str(delimiter or ",")
    if len(raw_delimiter) != 1:
        raise ValueError("delimiter must be a single character")
    if not body:
        raise ValueError("CSV payload is empty")
    try:
        text = body.decode(raw_encoding)
    except Exception as exc:
        raise ValueError(
            f"Unable to decode CSV payload with encoding '{raw_encoding}'"
        ) from exc
    try:
        frame = pd.read_csv(io.StringIO(text), sep=raw_delimiter)
    except Exception as exc:
        raise ValueError(f"Unable to parse CSV payload: {exc}") from exc
    if frame is None:
        raise ValueError("Unable to parse CSV payload")
    return frame
