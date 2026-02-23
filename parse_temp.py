import json
import collections
import urllib.request
import urllib.error
import time

url = "http://localhost:8002/api/run/start"
payload = json.dumps(
    {
        "run_id": f"test_sweep_reason_{int(time.time())}",
        "ticker": "MU",
        "date_from": "2026-02-09",
        "date_to": "2026-02-13",
        "account_size_usd": 100000,
        "strategy_selection_mode": "all_enabled",
        "liquidity_sweep_detection_enabled": True,
        "strategy_api_url": "http://localhost:8001",
    }
).encode("utf-8")

req = urllib.request.Request(
    url, data=payload, headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req) as response:
        print("Success")
except urllib.error.HTTPError as e:
    print(e.read().decode())
except Exception as e:
    print(e)
