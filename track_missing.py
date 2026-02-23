import json
import glob
import os

logs = glob.glob(
    "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/reports/*/performance_data.json"
)
latest = max(logs, key=os.path.getmtime)
print(f"Reading: {latest}")

with open(latest) as f:
    perf = json.load(f)

# The user mentioned signals that appeared but were not executed. They are probably logged in the frontend output stream, or the API console. Let's dump all signals recorded in the backtest report "trades" array to see if ANY signal is logged there besides those that got executed.
decisions_file = latest.replace("performance_data.json", "decisions.json")
if os.path.exists(decisions_file):
    print("Found decisions.json. Will search there...")
    with open(decisions_file) as f:
        data = json.load(f)
        signals = [
            x
            for x in data
            if "17:17" in x.get("timestamp", "")
            or "20:07" in x.get("timestamp", "")
            or "20:09" in x.get("timestamp", "")
        ]
        print(json.dumps(signals, indent=2))
else:
    print(
        f"No decisions file at {decisions_file}. Searching system logs directly for why those times would be blocked..."
    )
