import requests
from pathlib import Path
from tempfile import gettempdir
from datetime import datetime

url = "http://localhost:8002/api/run/start"
payload = {
    "run_id": "test_sweep_reason",
    "ticker": "MU",
    "date_from": "2026-02-09",
    "date_to": "2026-02-13",
    "account_size_usd": 100000,
    "strategy_selection_mode": "all_enabled",
    "liquidity_sweep_detection_enabled": True,
    "strategy_api_url": "http://localhost:8001",
}
resp = requests.post(url, json=payload)
data = resp.json()

import json

# let's just save data to a file so I can parse it
output_path = Path(gettempdir()) / (
    f"temp_test_sweep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)
with output_path.open("w", encoding="utf-8") as f:
    json.dump(data, f)

print(f"Saved to {output_path}")
