from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services.user_dataset_utils import (
    DatasetInputError,
    default_user_dataset_s3_path,
    normalize_dataset_identifier,
    read_csv_upload_frame,
    request_prefers_local_user_datasets,
)


def test_normalize_dataset_identifier_rejects_invalid_characters() -> None:
    with pytest.raises(DatasetInputError) as exc:
        normalize_dataset_identifier("bad/id")

    assert exc.value.code == "invalid_dataset_id"


def test_default_user_dataset_s3_path_uses_local_object_key_when_remote_not_preferred():
    path = default_user_dataset_s3_path(
        user_id="user-1",
        dataset_id="ds-1",
        file_format="parquet",
        prefer_remote=False,
    )

    assert path == "users/user-1/datasets/ds-1.parquet"


def test_request_prefers_local_user_datasets_uses_bucket_for_non_local_hosts(
    monkeypatch,
) -> None:
    monkeypatch.setenv("BACKTEST_USER_DATASETS_STORAGE_MODE", "auto")
    request = SimpleNamespace(url=SimpleNamespace(hostname="prod.example.com"))

    monkeypatch.delenv("BACKTEST_USER_DATASETS_BUCKET", raising=False)
    assert request_prefers_local_user_datasets(request) is True

    monkeypatch.setenv("BACKTEST_USER_DATASETS_BUCKET", "datasets-bucket")
    assert request_prefers_local_user_datasets(request) is False


def test_read_csv_upload_frame_rejects_invalid_delimiter() -> None:
    with pytest.raises(ValueError, match="delimiter must be a single character"):
        read_csv_upload_frame(body=b"a,b\n1,2\n", encoding="utf-8", delimiter="||")
