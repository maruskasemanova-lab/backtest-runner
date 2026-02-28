import json
import glob
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Find most recent report dir
reports = glob.glob(str(REPO_ROOT / "reports" / "*"))
latest_report_dir = max(reports, key=os.path.getmtime)
data_file = os.path.join(latest_report_dir, "performance_data.json")

print(f"Analyzing: {data_file}")

with open(data_file) as f:
    data = json.load(f)

# See if there's a skipped_trades array or similar
if "skipped_trades" in data:
    skips = data["skipped_trades"]
    reasons = {}
    for s in skips:
        r = s.get("skip_reason", "unknown")
        reasons[r] = reasons.get(r, 0) + 1
    print("\nSkipped trades found:", len(skips))
    for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {r}: {c}")
else:
    print("\nNo 'skipped_trades' array found in JSON.")

    # Check if trades array has any skipped ones
    if "trades" in data:
        filled = 0
        skipped = 0
        reasons = {}
        for t in data["trades"]:
            if t.get("status") == "skipped" or t.get("exit_reason") == "skipped":
                skipped += 1
                r = t.get("skip_reason", t.get("exit_reason", "unknown"))
                reasons[r] = reasons.get(r, 0) + 1
            else:
                filled += 1
        print(f"Trades array: {filled} filled, {skipped} skipped.")
        if skipped > 0:
            for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
                print(f"  {r}: {c}")
