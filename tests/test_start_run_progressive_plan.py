from __future__ import annotations

from src.services import start_run_service as svc


def test_progressive_plan_blocks_comparable_when_guard_disabled(monkeypatch):
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_ENABLED", True)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_ALLOW_COMPARABLE_MODE", False)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_MIN_DAYS", 2)

    plan = svc._resolve_progressive_plan(
        range_start="2026-01-01",
        range_end="2026-01-10",
        comparable_mode=True,
    )

    assert plan is None


def test_progressive_plan_uses_comparable_chunk_sizes(monkeypatch):
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_ENABLED", True)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_ALLOW_COMPARABLE_MODE", True)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_MIN_DAYS", 2)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_INITIAL_DAYS", 4)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_CHUNK_DAYS", 4)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_COMPARABLE_INITIAL_DAYS", 1)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_COMPARABLE_CHUNK_DAYS", 1)

    plan = svc._resolve_progressive_plan(
        range_start="2026-01-01",
        range_end="2026-01-06",
        comparable_mode=True,
    )

    assert isinstance(plan, dict)
    assert plan["initial_end"] == "2026-01-01"
    assert plan["initial_days"] == 1
    assert plan["chunk_days"] == 1
    assert plan["chunks"][0] == ("2026-01-02", "2026-01-02")
    assert plan["chunks"][-1] == ("2026-01-06", "2026-01-06")


def test_progressive_plan_non_comparable_keeps_standard_chunk_sizes(monkeypatch):
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_ENABLED", True)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_ALLOW_COMPARABLE_MODE", True)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_MIN_DAYS", 2)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_INITIAL_DAYS", 4)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_CHUNK_DAYS", 4)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_COMPARABLE_INITIAL_DAYS", 1)
    monkeypatch.setattr(svc, "PROGRESSIVE_LOAD_COMPARABLE_CHUNK_DAYS", 1)

    plan = svc._resolve_progressive_plan(
        range_start="2026-01-01",
        range_end="2026-01-10",
        comparable_mode=False,
    )

    assert isinstance(plan, dict)
    assert plan["initial_end"] == "2026-01-04"
    assert plan["initial_days"] == 4
    assert plan["chunk_days"] == 4
    assert plan["chunks"][0] == ("2026-01-05", "2026-01-08")
