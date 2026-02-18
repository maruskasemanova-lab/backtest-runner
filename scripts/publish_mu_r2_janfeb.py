#!/usr/bin/env python3
"""
Publish MU January/February datasets to Cloudflare R2 and generate a public manifest.

Required env vars:
  R2_ACCOUNT_ID
  R2_BUCKET
  (for upload mode) R2_ACCESS_KEY_ID
  (for upload mode) R2_SECRET_ACCESS_KEY

Optional:
  R2_MANIFEST_MODE          (public|private, defaults to public)
  R2_PUBLIC_BASE_URL        (required when mode=public; e.g. https://pub-xxxx.r2.dev)
  R2_S3_ENDPOINT            (defaults to https://<account_id>.r2.cloudflarestorage.com)
  R2_PREFIX                 (defaults to mu)
  R2_DRY_RUN                (1=true: prepare manifest/stage only, do not upload)
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import boto3
import pyarrow.parquet as pq


def _required_env(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _non_overlap_mu_ohlcv_files(data_dir: Path) -> List[Path]:
    return [
        data_dir / "MU_ohlcv-1m_2026-01-20_2026-02-06.csv",
        data_dir / "MU_ohlcv-1m_2026-02-09_2026-02-09.csv",
        data_dir / "MU_ohlcv-1m_2026-02-10_2026-02-10.csv",
        data_dir / "MU_ohlcv-1m_2026-02-11_2026-02-11.csv",
        data_dir / "MU_ohlcv-1m_2026-02-12_2026-02-12.csv",
        data_dir / "MU_ohlcv-1m_2026-02-13_2026-02-13.csv",
    ]


def _mu_l2_jan_feb_files(l2_dir: Path) -> List[Path]:
    jan = sorted(l2_dir.glob("MU_2026-01-*_2026-01-*.parquet"))
    feb = sorted(l2_dir.glob("MU_2026-02-*_2026-02-*.parquet"))
    return jan + feb


def _parse_dates_from_stem(stem: str) -> tuple[str, str]:
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"Unexpected file stem: {stem}")
    return parts[-2], parts[-1]


def _csv_row_count(path: Path) -> int:
    with path.open("rb") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _build_r2_client(
    *,
    endpoint: str,
    access_key_id: str,
    secret_access_key: str,
):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name="auto",
    )


def _upload_file(client: Any, *, bucket: str, key: str, source: Path, content_type: str) -> None:
    with source.open("rb") as handle:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=handle,
            ContentType=content_type,
            CacheControl="public, max-age=86400",
        )


def _object_locator(
    *,
    manifest_mode: str,
    key: str,
    bucket: str,
    public_base_url: str,
) -> str:
    if manifest_mode == "private":
        return f"s3://{bucket}/{key}"
    return f"{public_base_url}/{key}"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data"
    l2_dir = data_dir / "l2"
    stage_dir = Path("/tmp/mu_r2_publish_stage")
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    (stage_dir / "mu" / "ohlcv").mkdir(parents=True, exist_ok=True)
    (stage_dir / "mu" / "l2").mkdir(parents=True, exist_ok=True)

    account_id = _required_env("R2_ACCOUNT_ID")
    bucket = _required_env("R2_BUCKET")
    manifest_mode = str(os.getenv("R2_MANIFEST_MODE", "public") or "public").strip().lower()
    if manifest_mode not in {"public", "private"}:
        raise RuntimeError("R2_MANIFEST_MODE must be 'public' or 'private'")
    public_base_url = str(os.getenv("R2_PUBLIC_BASE_URL", "") or "").strip().rstrip("/")
    if manifest_mode == "public" and not public_base_url:
        raise RuntimeError("R2_PUBLIC_BASE_URL is required when R2_MANIFEST_MODE=public")
    dry_run = str(os.getenv("R2_DRY_RUN", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
    access_key_id = str(os.getenv("R2_ACCESS_KEY_ID", "") or "").strip()
    secret_access_key = str(os.getenv("R2_SECRET_ACCESS_KEY", "") or "").strip()
    if not dry_run:
        if not access_key_id:
            raise RuntimeError("Missing required env var: R2_ACCESS_KEY_ID")
        if not secret_access_key:
            raise RuntimeError("Missing required env var: R2_SECRET_ACCESS_KEY")
    endpoint = str(os.getenv("R2_S3_ENDPOINT", "") or "").strip()
    if not endpoint:
        endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    prefix = str(os.getenv("R2_PREFIX", "mu") or "mu").strip().strip("/")
    if not prefix:
        prefix = "mu"

    manifest_entries: List[Dict[str, Any]] = []
    upload_jobs: List[Dict[str, Any]] = []

    # OHLCV files are kept as-is.
    ohlcv_files = [path for path in _non_overlap_mu_ohlcv_files(data_dir) if path.exists()]
    for src in ohlcv_files:
        dst = stage_dir / "mu" / "ohlcv" / src.name
        shutil.copy2(src, dst)
        start_date, end_date = _parse_dates_from_stem(src.stem)
        key = f"{prefix}/ohlcv/{dst.name}"
        file_locator = _object_locator(
            manifest_mode=manifest_mode,
            key=key,
            bucket=bucket,
            public_base_url=public_base_url,
        )
        manifest_entries.append(
            {
                "ticker": "MU",
                "schema": "ohlcv-1m",
                "dataset": "XNAS.ITCH",
                "start_date": start_date,
                "end_date": end_date,
                "file_csv": file_locator,
                "size_bytes": int(dst.stat().st_size),
                "row_count": int(_csv_row_count(dst)),
                "status": "ready",
                "source_root": f"s3://{bucket}/{prefix}/ohlcv",
            }
        )
        upload_jobs.append(
            {
                "key": key,
                "source": dst,
                "content_type": "text/csv",
            }
        )

    # L2 parquet files are recompressed to zstd level 9 to fit free-tier budgets.
    l2_sources = _mu_l2_jan_feb_files(l2_dir)
    for idx, src in enumerate(l2_sources, start=1):
        dst = stage_dir / "mu" / "l2" / src.name
        table = pq.read_table(src)
        pq.write_table(table, dst, compression="zstd", compression_level=9)
        start_date, end_date = _parse_dates_from_stem(src.stem)
        key = f"{prefix}/l2/{dst.name}"
        file_locator = _object_locator(
            manifest_mode=manifest_mode,
            key=key,
            bucket=bucket,
            public_base_url=public_base_url,
        )
        manifest_entries.append(
            {
                "ticker": "MU",
                "schema": "mbp-10",
                "dataset": "XNAS.ITCH",
                "start_date": start_date,
                "end_date": end_date,
                "file_parquet": file_locator,
                "size_bytes": int(dst.stat().st_size),
                "row_count": int(table.num_rows),
                "status": "ready",
                "source_root": f"s3://{bucket}/{prefix}/l2",
            }
        )
        upload_jobs.append(
            {
                "key": key,
                "source": dst,
                "content_type": "application/octet-stream",
            }
        )
        if idx % 5 == 0:
            print(f"recompressed {idx}/{len(l2_sources)} L2 files")

    total_size = sum(int(item.get("size_bytes", 0) or 0) for item in manifest_entries)
    print(f"Prepared {len(manifest_entries)} entries ({round(total_size / (1024 ** 3), 4)} GiB)")

    manifest_payload = {
        "version": "1.0",
        "mode": manifest_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": manifest_entries,
    }
    manifest_local = stage_dir / "mu_janfeb_manifest.json"
    manifest_local.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    manifest_key = f"{prefix}/manifests/mu_janfeb_manifest.json"
    manifest_url = _object_locator(
        manifest_mode=manifest_mode,
        key=manifest_key,
        bucket=bucket,
        public_base_url=public_base_url,
    )

    if dry_run:
        print("Dry-run mode: upload skipped.")
        print(f"Local manifest: {manifest_local}")
        print(f"Expected manifest URL: {manifest_url}")
        return

    client = _build_r2_client(
        endpoint=endpoint,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
    )

    # Upload dataset artifacts.
    for item in upload_jobs:
        _upload_file(
            client,
            bucket=bucket,
            key=str(item["key"]),
            source=Path(item["source"]),
            content_type=str(item["content_type"]),
        )

    _upload_file(
        client,
        bucket=bucket,
        key=manifest_key,
        source=manifest_local,
        content_type="application/json",
    )

    print("R2 upload completed.")
    print(f"Manifest URL: {manifest_url}")


if __name__ == "__main__":
    main()
