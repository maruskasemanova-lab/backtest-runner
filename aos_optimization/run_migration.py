import json
from pathlib import Path
import shutil

aos_config_path = Path(__file__).resolve().parent / "aos_config.json"
if not aos_config_path.exists():
    print("Does not exist!")
    exit(1)

with aos_config_path.open("r", encoding="utf-8") as f:
    config = json.load(f)

tickers_dir = aos_config_path.parent / "tickers"
tickers_dir.mkdir(parents=True, exist_ok=True)

tickers = config.pop("tickers", {})
config["tickers"] = {}

for ticker, data in tickers.items():
    if not isinstance(data, dict):
        continue
    ticker_file = tickers_dir / f"{ticker.upper()}.json"
    with ticker_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

with aos_config_path.open("w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)

print("Migration completed!")
