import json
import glob
import os

# The user is running a live test or backtest. The logs they quoted look like Strategy API output.
# Let's search inside the API server runtime or printed out from `api_server.py` standard output.
logs = [
    "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/start_all_restart3.log",
    "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/start_all_restart2.log",
    "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/start_all_restart.log",
    "/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/start_strategy_restart.log",
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
