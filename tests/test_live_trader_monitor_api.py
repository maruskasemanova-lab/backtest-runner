from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pytest

from src.services.saas_service import SaaSStateStore


_API_SERVER_PATH = Path(__file__).resolve().parents[1] / "api_server.py"
_PROJECT_ROOT = str(_API_SERVER_PATH.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_API_SERVER_SPEC = importlib.util.spec_from_file_location(
    "api_server_module", _API_SERVER_PATH
)
assert _API_SERVER_SPEC is not None and _API_SERVER_SPEC.loader is not None
api_server = importlib.util.module_from_spec(_API_SERVER_SPEC)
_API_SERVER_SPEC.loader.exec_module(api_server)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")


def _bind_temp_state_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SaaSStateStore:
    store = SaaSStateStore(str(tmp_path / "saas_state.db"))
    monkeypatch.setattr(api_server.v2_services, "store", store)
    monkeypatch.setattr(api_server.api_services, "state_store", store)
    monkeypatch.setattr(api_server.app.state, "saas_state_store", store, raising=False)
    return store


def test_read_jsonl_tail_skips_invalid_lines(tmp_path: Path) -> None:
    target = tmp_path / "decisions_test.jsonl"
    target.write_text('{"a":1}\nnot-json\n[1,2,3]\n{"b":2}\n', encoding="utf-8")

    rows = api_server._read_jsonl_tail(target, limit=10)
    assert rows == [{"a": 1}, {"b": 2}]


def test_discover_live_trader_runs_groups_streams(tmp_path: Path, monkeypatch) -> None:
    _bind_temp_state_store(monkeypatch, tmp_path)
    _write_jsonl(tmp_path / "runtime_runA.jsonl", [{"x": 1}])
    _write_jsonl(tmp_path / "decisions_runA.jsonl", [{"y": 2}])
    _write_jsonl(tmp_path / "orders_runB.jsonl", [{"z": 3}])

    monkeypatch.setattr(api_server, "LIVE_TRADER_ARTIFACTS_DIR", tmp_path)

    rows = api_server._discover_live_trader_runs(limit=10)
    run_ids = {row["run_id"] for row in rows}
    assert run_ids == {"runA", "runB"}

    run_a = next(item for item in rows if item["run_id"] == "runA")
    assert "runtime" in run_a["streams"]
    assert "decisions" in run_a["streams"]
    assert run_a["status"] in {"active", "idle"}


def test_get_live_trader_snapshot_returns_latest_records(
    tmp_path: Path, monkeypatch
) -> None:
    _bind_temp_state_store(monkeypatch, tmp_path)
    _write_jsonl(tmp_path / "runtime_run123.jsonl", [{"kind": "runtime", "v": 1}])
    _write_jsonl(
        tmp_path / "decisions_run123.jsonl",
        [{"kind": "decision", "id": 1}, {"kind": "decision", "id": 2}],
    )

    monkeypatch.setattr(api_server, "LIVE_TRADER_ARTIFACTS_DIR", tmp_path)

    snapshot = asyncio.run(api_server.get_live_trader_snapshot("run123", tail_limit=50))
    assert snapshot["run_id"] == "run123"
    assert snapshot["streams"]["runtime"]["exists"] is True
    assert snapshot["streams"]["decisions"]["count"] == 2
    assert snapshot["streams"]["decisions"]["latest"]["id"] == 2
    assert snapshot["status"] in {"active", "idle"}


def test_get_live_trader_events_rejects_invalid_stream() -> None:
    with pytest.raises(api_server.HTTPException) as exc:
        asyncio.run(api_server.get_live_trader_events("run123", stream="bad", limit=10))
    assert exc.value.status_code == 400


def test_discover_live_runs_marks_finished_and_filters_active(
    tmp_path: Path, monkeypatch
) -> None:
    _bind_temp_state_store(monkeypatch, tmp_path)
    active_path = tmp_path / "runtime_run_active.jsonl"
    finished_path = tmp_path / "runtime_run_finished.jsonl"

    _write_jsonl(
        active_path,
        [
            {
                "event": "runtime_started",
                "ticker": "MU",
                "active_profile_id": "c4bb2197e651",
                "execution_config": {"market_data_source": "databento"},
            }
        ],
    )
    _write_jsonl(
        finished_path,
        [
            {
                "event": "runtime_finished",
                "ticker": "NVDA",
                "active_profile_id": "nvda-profile",
                "execution_config": {"market_data_source": "databento"},
            }
        ],
    )

    now = time.time()
    os.utime(active_path, (now, now))
    old = now - 3600
    os.utime(finished_path, (old, old))

    monkeypatch.setattr(api_server, "LIVE_TRADER_ARTIFACTS_DIR", tmp_path)

    all_rows = api_server._discover_live_trader_runs(limit=10)
    statuses = {row["run_id"]: row["status"] for row in all_rows}
    assert statuses["run_active"] == "active"
    assert statuses["run_finished"] == "finished"

    active_rows = api_server._discover_live_trader_runs(limit=10, active_only=True)
    assert [row["run_id"] for row in active_rows] == ["run_active"]
