import subprocess
import sys
from pathlib import Path


def _write_trade_csv(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "pnl_dollars",
                "-120",
                "-80",
                "60",
                "-40",
                "100",
                "-30",
                "20",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_monte_carlo_returns_nonzero_on_threshold_breach(tmp_path: Path) -> None:
    csv_path = tmp_path / "trades.csv"
    _write_trade_csv(csv_path)

    proc = subprocess.run(
        [
            sys.executable,
            "monte_carlo.py",
            "--trades-file",
            str(csv_path),
            "--iterations",
            "250",
            "--seed",
            "7",
            "--max-p95-drawdown-dollars",
            "20",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 2
    assert "Risk flag:" in proc.stdout
    assert "is above" in proc.stdout


def test_monte_carlo_returns_zero_when_within_threshold(tmp_path: Path) -> None:
    csv_path = tmp_path / "trades.csv"
    _write_trade_csv(csv_path)

    proc = subprocess.run(
        [
            sys.executable,
            "monte_carlo.py",
            "--trades-file",
            str(csv_path),
            "--iterations",
            "250",
            "--seed",
            "7",
            "--max-p95-drawdown-dollars",
            "1000",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0
    assert "Risk flag:" in proc.stdout
    assert "is within" in proc.stdout
