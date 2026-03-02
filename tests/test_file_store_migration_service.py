from __future__ import annotations

import json
from pathlib import Path

from src.services.file_store_migration_service import sync_live_trader_artifacts_to_store
from src.services.saas_service import SaaSStateStore


def _append_jsonl(path: Path, rows: list[dict], *, newline: bool = True) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            if newline:
                handle.write("\n")


def test_sync_live_trader_artifacts_incremental_checkpoint(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "live_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    stream_file = artifacts_dir / "decisions_run-a.jsonl"
    stream_file.write_text("", encoding="utf-8")

    _append_jsonl(stream_file, [{"id": 1}, {"id": 2}])
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))

    first = sync_live_trader_artifacts_to_store(
        artifacts_dir=artifacts_dir,
        store=store,
    )
    assert first["scanned_files"] == 1
    assert first["scanned_lines"] == 2
    assert first["inserted"] == 2
    assert first["unchanged_files"] == 0
    assert len(
        store.list_live_trader_events(
            run_id="run-a",
            stream="decisions",
            limit=10,
        )
    ) == 2

    second = sync_live_trader_artifacts_to_store(
        artifacts_dir=artifacts_dir,
        store=store,
    )
    assert second["scanned_files"] == 1
    assert second["unchanged_files"] == 1
    assert second["scanned_lines"] == 0
    assert second["inserted"] == 0

    checkpoint = store.get_live_trader_ingest_state(source_path=str(stream_file))
    assert checkpoint is not None
    assert checkpoint["byte_offset"] == stream_file.stat().st_size

    _append_jsonl(stream_file, [{"id": 3}], newline=False)
    third = sync_live_trader_artifacts_to_store(
        artifacts_dir=artifacts_dir,
        store=store,
    )
    assert third["scanned_files"] == 1
    assert third["scanned_lines"] == 0
    assert third["inserted"] == 0
    after_partial = store.get_live_trader_ingest_state(source_path=str(stream_file))
    assert after_partial is not None
    assert after_partial["byte_offset"] == checkpoint["byte_offset"]

    with stream_file.open("a", encoding="utf-8") as handle:
        handle.write("\n")

    fourth = sync_live_trader_artifacts_to_store(
        artifacts_dir=artifacts_dir,
        store=store,
    )
    assert fourth["scanned_files"] == 1
    assert fourth["scanned_lines"] == 1
    assert fourth["inserted"] == 1
    events = store.list_live_trader_events(
        run_id="run-a",
        stream="decisions",
        limit=10,
    )
    assert [row.get("id") for row in events] == [1, 2, 3]
