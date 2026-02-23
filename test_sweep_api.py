import requests

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
with open("temp_test_sweep.json", "w") as f:
    json.dump(data, f)

print("Saved to temp_test_sweep.json")
