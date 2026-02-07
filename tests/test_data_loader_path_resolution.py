from pathlib import Path

from data_loader import DataLoader


def test_resolve_file_path_accepts_root_prefixed_relative_path(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / f"TEST_OHLCV_{tmp_path.name}_A.csv"
    target.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")

    loader = DataLoader(data_dirs=[str(data_dir)])
    loader.project_root = tmp_path

    resolved = loader._resolve_file_path(f"data/{target.name}")
    assert resolved == target.resolve()


def test_resolve_file_path_accepts_plain_filename_in_configured_root(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / f"TEST_OHLCV_{tmp_path.name}_B.csv"
    target.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")

    loader = DataLoader(data_dirs=[str(data_dir)])
    resolved = loader._resolve_file_path(target.name)
    assert resolved == target.resolve()
