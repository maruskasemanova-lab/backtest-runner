import json
import glob
import os

logs = glob.glob(
    "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/reports/*/performance_data.json"
)
latest = max(logs, key=os.path.getmtime)

with open(latest) as f:
    perf = json.load(f)

# The orchestrator dumps run diagnostics including skipped signals to "diagnostics" or "decisions" arrays if extended reporting is on.
# Let's see what keys are there.
print("Keys in performance.json:", list(perf.keys()))

if "trades" in perf:
    times = []
    for t in perf["trades"]:
        times.append(t.get("entry_time"))
    print("\nFilled trades at:")
    for t in sorted(times):
        print(" ", t)

decisions_file = latest.replace("performance_data.json", "decisions.json")
if os.path.exists(decisions_file):
    with open(decisions_file) as f:
        decs = json.load(f)
    print(f"\nDecisions file exists: {len(decs)} decisions total.")
    skips = [
        d
        for d in decs
        if "17:17" in d.get("time", "")
        or "20:07" in d.get("time", "")
        or "20:09" in d.get("time", "")
    ]
    for d in skips:
        print(f"Skipped signal at {d.get('time')}: {d.get('reason')}")
else:
    print(f"\nNo decisions.json found in {os.path.dirname(latest)}")
