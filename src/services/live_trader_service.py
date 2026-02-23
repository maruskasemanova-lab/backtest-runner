import json
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException


_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]+")


def sanitize_live_run_id(run_id: str) -> str:
    raw = str(run_id or "").strip()
    if not raw:
        raise HTTPException(400, "run_id is required")
    if not _RUN_ID_PATTERN.fullmatch(raw):
        raise HTTPException(400, "Invalid run_id format")
    return raw


def live_artifact_file(artifacts_dir: Path, stream: str, run_id: str) -> Path:
    run_id_safe = sanitize_live_run_id(run_id)
    return artifacts_dir / f"{stream}_{run_id_safe}.jsonl"


def read_jsonl_tail(
    path: Path, limit: int = 200, logger: Any = None
) -> List[Dict[str, Any]]:
    capped = max(1, min(2000, int(limit)))
    if not path.exists():
        return []

    rows: deque[Dict[str, Any]] = deque(maxlen=capped)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
    except Exception as exc:
        if logger is not None:
            logger.warning("Failed reading live artifact %s: %s", path, exc)
        return []
    return list(rows)


def parse_utc_iso(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def extract_runtime_summary(
    run_id: str, artifacts_dir: Path, logger: Any = None
) -> Optional[Dict[str, Any]]:
    runtime_path = live_artifact_file(artifacts_dir, "runtime", run_id)
    if not runtime_path.exists():
        return None
    rows = read_jsonl_tail(runtime_path, limit=20, logger=logger)
    if not rows:
        return None
    latest = rows[-1]
    if not isinstance(latest, dict):
        return None

    summary: Dict[str, Any] = {
        "event": str(latest.get("event", "runtime_started")).strip()
        or "runtime_started",
    }
    for key in (
        "ticker",
        "profile_id",
        "active_profile_id",
        "execution_config",
        "processed_minutes",
        "decisions",
        "signals",
        "orders",
        "error",
        "timestamp",
    ):
        if key in latest:
            summary[key] = latest.get(key)
    return summary


def infer_live_run_status(
    updated_at: Any,
    runtime_summary: Optional[Dict[str, Any]],
    active_window_seconds: int = 180,
) -> str:
    event = str((runtime_summary or {}).get("event", "")).strip().lower()
    if event == "runtime_error":
        return "error"
    if event == "runtime_finished":
        return "finished"

    updated_dt = parse_utc_iso(updated_at)
    now_utc = datetime.now(timezone.utc)
    if updated_dt is not None and (now_utc - updated_dt) <= timedelta(
        seconds=max(1, int(active_window_seconds))
    ):
        return "active"
    return "idle"


def discover_live_trader_runs(
    artifacts_dir: Path,
    *,
    limit: int = 20,
    active_only: bool = False,
    active_window_seconds: int = 180,
    logger: Any = None,
) -> List[Dict[str, Any]]:
    if not artifacts_dir.exists():
        return []

    run_index: Dict[str, Dict[str, Any]] = {}
    for stream in ("runtime", "decisions", "signals", "orders"):
        for file in artifacts_dir.glob(f"{stream}_*.jsonl"):
            run_id = file.stem[len(stream) + 1 :]
            entry = run_index.setdefault(
                run_id,
                {
                    "run_id": run_id,
                    "streams": {},
                    "updated_at": None,
                },
            )
            stat = file.stat()
            updated = datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z"
            entry["streams"][stream] = {
                "path": str(file),
                "size_bytes": int(stat.st_size),
                "updated_at": updated,
            }
            current_updated = entry.get("updated_at")
            if current_updated is None or updated > current_updated:
                entry["updated_at"] = updated

    rows_raw = sorted(
        run_index.values(),
        key=lambda item: str(item.get("updated_at") or ""),
        reverse=True,
    )
    rows = []
    for entry in rows_raw:
        runtime_summary = extract_runtime_summary(
            str(entry.get("run_id") or ""),
            artifacts_dir,
            logger=logger,
        )
        status = infer_live_run_status(
            entry.get("updated_at"),
            runtime_summary,
            active_window_seconds=active_window_seconds,
        )
        if active_only and status != "active":
            continue
        row = dict(entry)
        row["status"] = status
        row["runtime"] = runtime_summary
        row["ticker"] = (
            str((runtime_summary or {}).get("ticker") or "").strip().upper() or None
        )
        rows.append(row)

    capped = max(1, min(200, int(limit)))
    return rows[:capped]


def live_trader_events_payload(
    artifacts_dir: Path,
    run_id: str,
    *,
    stream: str = "decisions",
    limit: int = 200,
    logger: Any = None,
) -> Dict[str, Any]:
    stream_key = str(stream or "decisions").strip().lower()
    if stream_key not in {"runtime", "decisions", "signals", "orders"}:
        raise HTTPException(
            400, "stream must be one of: runtime, decisions, signals, orders"
        )

    file_path = live_artifact_file(artifacts_dir, stream_key, run_id)
    if not file_path.exists():
        raise HTTPException(404, f"Live stream file not found: {file_path.name}")

    events = read_jsonl_tail(file_path, limit=limit, logger=logger)
    return {
        "run_id": sanitize_live_run_id(run_id),
        "stream": stream_key,
        "count": len(events),
        "events": events,
    }


def live_trader_snapshot_payload(
    artifacts_dir: Path,
    run_id: str,
    *,
    tail_limit: int = 200,
    active_window_seconds: int = 180,
    logger: Any = None,
) -> Dict[str, Any]:
    run_id_safe = sanitize_live_run_id(run_id)
    streams = {}
    total_count = 0
    updated_at: Optional[str] = None

    for stream_key in ("runtime", "decisions", "signals", "orders"):
        file_path = live_artifact_file(artifacts_dir, stream_key, run_id_safe)
        events = (
            read_jsonl_tail(file_path, limit=tail_limit, logger=logger)
            if file_path.exists()
            else []
        )
        stream_updated = (
            datetime.utcfromtimestamp(file_path.stat().st_mtime).isoformat() + "Z"
            if file_path.exists()
            else None
        )
        streams[stream_key] = {
            "exists": bool(file_path.exists()),
            "count": len(events),
            "latest": events[-1] if events else None,
            "updated_at": stream_updated,
        }
        if stream_updated and (updated_at is None or stream_updated > updated_at):
            updated_at = stream_updated
        total_count += len(events)

    if not any(item["exists"] for item in streams.values()):
        raise HTTPException(
            404, f"No live-trader artifacts found for run_id={run_id_safe}"
        )

    runtime_latest = streams.get("runtime", {}).get("latest")
    runtime_summary = runtime_latest if isinstance(runtime_latest, dict) else None
    status = infer_live_run_status(
        updated_at,
        runtime_summary,
        active_window_seconds=active_window_seconds,
    )

    return {
        "run_id": run_id_safe,
        "tail_limit": max(1, min(2000, int(tail_limit))),
        "total_count": total_count,
        "updated_at": updated_at,
        "status": status,
        "runtime": runtime_summary,
        "streams": streams,
    }
