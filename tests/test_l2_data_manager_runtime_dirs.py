from __future__ import annotations

from pathlib import Path

from src.l2_data_manager import L2DataManager


def test_runtime_dirs_fallback_when_settings_paths_are_stale(monkeypatch):
    class _FakeSettings:
        def get_l2_dirs(self, existing_only: bool = False):
            if existing_only:
                return []
            return [
                Path("/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data/l2"),
                Path("/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data"),
            ]

    monkeypatch.setattr("src.l2_data_manager.SystemSettings", lambda: _FakeSettings())

    manager = L2DataManager()
    project_root = Path(__file__).resolve().parents[1]
    expected_l2 = str((project_root / "data" / "l2").resolve())
    expected_data = str((project_root / "data").resolve())

    assert expected_l2 in manager.data_dirs
    assert expected_data in manager.data_dirs
