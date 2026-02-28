import json
import sqlite3
import pandas as pd
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
db_path = REPO_ROOT / "data" / "db" / "runs.db"
conn = sqlite3.connect(str(db_path))

c = conn.cursor()
c.execute(
    "SELECT run_id, report_json FROM run_reports ORDER BY created_at DESC LIMIT 1"
)
row = c.fetchone()
if row:
    run_id, report_json = row
    report = json.loads(report_json)
    print(f"Latest run ID in DB: {run_id}")

    # We want to see how these signals were consumed.
    # Did they even arrive in the orchestrator?
    # Actually, let's query the specific signals by timestamp.
else:
    print("No runs in DB.")
