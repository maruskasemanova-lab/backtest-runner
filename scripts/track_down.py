import json
import glob
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT_ARTIFACTS = Path("/tmp/backtest-runner-artifacts/root-cleanup-2026-02-28")

# The user is running a live test or backtest. The logs they quoted look like Strategy API output.
# Let's search inside the API server runtime or printed out from `api_server.py` standard output.
logs = [
    str(ROOT_ARTIFACTS / "logs" / "start_all_restart3.log"),
    str(ROOT_ARTIFACTS / "logs" / "start_all_restart2.log"),
    str(ROOT_ARTIFACTS / "logs" / "start_all_restart.log"),
    str(REPO_ROOT.parent / "market_regime_detection" / "start_strategy_restart.log"),
]

for log in logs:
    if os.path.exists(log):
        with open(log, "r") as f:
            content = f.read()
            if (
                "20:09:00" in content
                or "17:17:00" in content
                or "margin 9.4 >=" in content
            ):
                print(f"FOUND SIGNAL IN: {log}")
