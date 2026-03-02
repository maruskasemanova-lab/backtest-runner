from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional


def _derive_run_key(payload: Dict[str, Any]) -> str:
    run_key = str(payload.get("run_key") or "").strip()
    if run_key:
        return run_key

    run_id = str(payload.get("run_id") or "").strip()
    ticker = str(payload.get("ticker") or "").strip().upper()
    date_label = str(payload.get("date") or "").strip()
    if run_id and ticker and date_label:
        return f"{run_id}:{ticker}:{date_label}"

    date_from = str(payload.get("date_from") or "").strip()
    date_to = str(payload.get("date_to") or "").strip()
    if run_id and ticker and date_from and date_to:
        return f"{run_id}:{ticker}:{date_from}_to_{date_to}"
    if run_id and ticker and date_from:
        return f"{run_id}:{ticker}:{date_from}"
    return ""


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _is_summary_like_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    if "run_id" in payload and "ticker" in payload:
        return True
    summary = payload.get("summary")
    return isinstance(summary, dict) and "run_id" in summary and "ticker" in summary


def migrate_reports_to_run_reports_store(
    *,
    reports_dir: Path,
    run_reports_store: Any,
    logger: Any = None,
    overwrite_existing: bool = False,
    max_files: Optional[int] = None,
) -> Dict[str, int]:
    result = {
        "scanned_files": 0,
        "processed_reports": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }
    if not reports_dir.exists():
        return result

    upsert = getattr(run_reports_store, "upsert_run_summary", None)
    get_one = getattr(run_reports_store, "get_run_summary", None)
    if not callable(upsert):
        return result

    files = sorted(reports_dir.rglob("*.json"))
    if max_files is not None:
        files = files[: max(0, int(max_files))]

    for report_file in files:
        result["scanned_files"] += 1
        payload = _read_json(report_file)
        if not isinstance(payload, dict):
            result["errors"] += 1
            continue
        if not _is_summary_like_payload(payload):
            result["skipped"] += 1
            continue

        summary_payload = (
            payload.get("summary")
            if isinstance(payload.get("summary"), dict)
            else payload
        )
        run_key = _derive_run_key(summary_payload)
        if not run_key:
            result["skipped"] += 1
            continue

        existing = None
        if callable(get_one):
            try:
                existing = get_one(run_key=run_key)
            except Exception:
                existing = None
        if existing and not overwrite_existing:
            result["skipped"] += 1
            continue

        try:
            upsert(run_key=run_key, summary=summary_payload)
        except Exception as exc:
            result["errors"] += 1
            if logger is not None:
                logger.warning("Failed to migrate report %s: %s", report_file, exc)
            continue

        result["processed_reports"] += 1
        if existing:
            result["updated"] += 1
        else:
            result["inserted"] += 1

    return result


def migrate_aos_history_jsonl_to_store(
    *,
    history_path: Path,
    store: Any,
    logger: Any = None,
) -> Dict[str, int]:
    result = {
        "scanned_lines": 0,
        "inserted": 0,
        "skipped": 0,
        "errors": 0,
    }
    if not history_path.exists():
        return result

    record_fn = getattr(store, "record_aos_history_entry", None)
    if not callable(record_fn):
        return result

    try:
        with history_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                result["scanned_lines"] += 1
                text = str(line or "").strip()
                if not text:
                    result["skipped"] += 1
                    continue
                try:
                    payload = json.loads(text)
                except Exception:
                    cleaned_text = text[:-2].strip() if text.endswith("\\n") else ""
                    if cleaned_text:
                        try:
                            payload = json.loads(cleaned_text)
                        except Exception:
                            result["errors"] += 1
                            continue
                    else:
                        result["errors"] += 1
                        continue
                if not isinstance(payload, dict):
                    result["skipped"] += 1
                    continue
                ticker = str(payload.get("ticker") or "").strip().upper()
                if not ticker:
                    result["skipped"] += 1
                    continue
                try:
                    inserted = bool(
                        record_fn(
                            ticker=ticker,
                            entry=payload,
                            source="file:aos_history_jsonl",
                        )
                    )
                except Exception as exc:
                    result["errors"] += 1
                    if logger is not None:
                        logger.warning("Failed to ingest AOS history entry: %s", exc)
                    continue
                if inserted:
                    result["inserted"] += 1
                else:
                    result["skipped"] += 1
    except Exception as exc:
        if logger is not None:
            logger.warning("Failed reading %s: %s", history_path, exc)
        result["errors"] += 1
    return result


def sync_live_trader_artifacts_to_store(
    *,
    artifacts_dir: Path,
    store: Any,
    logger: Any = None,
) -> Dict[str, int]:
    result = {
        "scanned_files": 0,
        "unchanged_files": 0,
        "scanned_lines": 0,
        "inserted": 0,
        "skipped": 0,
        "errors": 0,
    }
    if not artifacts_dir.exists():
        return result

    upsert_fn = getattr(store, "upsert_live_trader_event", None)
    if not callable(upsert_fn):
        return result
    get_ingest_state = getattr(store, "get_live_trader_ingest_state", None)
    upsert_ingest_state = getattr(store, "upsert_live_trader_ingest_state", None)
    supports_incremental = callable(get_ingest_state) and callable(upsert_ingest_state)

    for stream in ("runtime", "decisions", "signals", "orders"):
        for file in sorted(artifacts_dir.glob(f"{stream}_*.jsonl")):
            result["scanned_files"] += 1
            run_id = file.stem[len(stream) + 1 :].strip()
            if not run_id:
                result["skipped"] += 1
                continue
            try:
                stat = file.stat()
                source_mtime_ns = int(stat.st_mtime_ns)
                source_size_bytes = int(stat.st_size)
            except Exception:
                source_mtime_ns = None
                source_size_bytes = 0

            start_offset = 0
            if supports_incremental:
                try:
                    checkpoint = get_ingest_state(source_path=str(file))
                except Exception:
                    checkpoint = None
                if isinstance(checkpoint, dict):
                    cp_mtime = int(checkpoint.get("file_mtime_ns") or 0)
                    cp_size = int(checkpoint.get("file_size_bytes") or 0)
                    cp_offset = max(0, int(checkpoint.get("byte_offset") or 0))
                    if cp_size == source_size_bytes and cp_mtime == int(
                        source_mtime_ns or 0
                    ):
                        if cp_offset >= source_size_bytes:
                            result["unchanged_files"] += 1
                            continue
                        start_offset = min(cp_offset, source_size_bytes)
                    elif cp_offset <= source_size_bytes and cp_size <= source_size_bytes:
                        start_offset = cp_offset
                    else:
                        start_offset = 0

            try:
                with file.open("rb") as handle:
                    if start_offset > 0:
                        handle.seek(start_offset)
                    last_committed_offset = int(handle.tell())
                    while True:
                        line = handle.readline()
                        if not line:
                            break
                        if not line.endswith(b"\n"):
                            # Do not advance checkpoint beyond incomplete line.
                            break
                        result["scanned_lines"] += 1
                        text = str(
                            line.decode("utf-8", errors="replace") if line else ""
                        ).strip()
                        if not text:
                            result["skipped"] += 1
                            last_committed_offset = int(handle.tell())
                            continue
                        try:
                            payload = json.loads(text)
                        except Exception:
                            result["errors"] += 1
                            last_committed_offset = int(handle.tell())
                            continue
                        if not isinstance(payload, dict):
                            result["skipped"] += 1
                            last_committed_offset = int(handle.tell())
                            continue
                        try:
                            inserted = bool(
                                upsert_fn(
                                    run_id=run_id,
                                    stream=stream,
                                    event=payload,
                                    source_path=str(file),
                                    source_mtime_ns=source_mtime_ns,
                                )
                            )
                        except Exception as exc:
                            result["errors"] += 1
                            if logger is not None:
                                logger.warning(
                                    "Failed to ingest live-trader event from %s: %s",
                                    file,
                                    exc,
                                )
                            continue
                        if inserted:
                            result["inserted"] += 1
                        else:
                            result["skipped"] += 1
                        last_committed_offset = int(handle.tell())

                    if supports_incremental:
                        try:
                            upsert_ingest_state(
                                source_path=str(file),
                                run_id=run_id,
                                stream=stream,
                                file_mtime_ns=int(source_mtime_ns or 0),
                                file_size_bytes=int(source_size_bytes),
                                byte_offset=max(0, int(last_committed_offset)),
                            )
                        except Exception as exc:
                            if logger is not None:
                                logger.warning(
                                    "Failed to persist ingest checkpoint for %s: %s",
                                    file,
                                    exc,
                                )
            except Exception as exc:
                result["errors"] += 1
                if logger is not None:
                    logger.warning("Failed reading %s: %s", file, exc)

    return result


def ensure_primary_config_snapshots(
    *,
    store: Any,
    load_aos_config: Callable[[], Dict[str, Any]],
    load_positioning_config: Callable[[], Dict[str, Any]],
    logger: Any = None,
) -> Dict[str, int]:
    result = {"created": 0, "updated": 0, "errors": 0}
    get_snapshot = getattr(store, "get_config_snapshot", None)
    upsert_snapshot = getattr(store, "upsert_config_snapshot", None)
    if not callable(get_snapshot) or not callable(upsert_snapshot):
        return result

    try:
        aos_existing = get_snapshot(config_key="aos_config")
        aos_payload = load_aos_config()
        if not isinstance(aos_existing, dict):
            upsert_snapshot(
                config_key="aos_config",
                payload=aos_payload,
                source="file_migration",
            )
            result["created"] += 1
    except Exception as exc:
        if logger is not None:
            logger.warning("Failed to seed aos_config snapshot: %s", exc)
        result["errors"] += 1

    try:
        pos_existing = get_snapshot(config_key="positioning_config")
        pos_payload = load_positioning_config()
        if not isinstance(pos_existing, dict):
            upsert_snapshot(
                config_key="positioning_config",
                payload=pos_payload,
                source="file_migration",
            )
            result["created"] += 1
    except Exception as exc:
        if logger is not None:
            logger.warning("Failed to seed positioning_config snapshot: %s", exc)
        result["errors"] += 1

    return result
