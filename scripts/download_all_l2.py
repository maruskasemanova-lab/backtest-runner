import databento as db
import os
from datetime import date

# Configuration
API_KEY = os.getenv("DATABENTO_API_KEY", "")
OUTPUT_DIR = "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data/l2"
TICKERS = ["TSLA", "AAPL", "AMD", "GOOGL", "META", "MSFT", "MU", "NVDA"]
START_DATE = "2026-02-03"
# Databento end is exclusive. 2026-02-06 covers sessions on 3rd, 4th, and 5th.
END_DATE = "2026-02-06"

if __name__ == "__main__":
    if not API_KEY:
        raise RuntimeError("Missing DATABENTO_API_KEY environment variable")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    client = db.Historical(API_KEY)

    for ticker in TICKERS:
        output_file = os.path.join(OUTPUT_DIR, f"{ticker}_{START_DATE}_{END_DATE}.mbn")

        if os.path.exists(output_file):
            print(f"[{ticker}] File already exists: {output_file} (Skipping)")
            continue

        print(f"[{ticker}] Downloading MBP-10 from {START_DATE} to {END_DATE}...")

        try:
            data = client.timeseries.get_range(
                dataset="XNAS.ITCH",
                symbols=ticker,
                start=START_DATE,
                end=END_DATE,
                schema="mbp-10",
                stype_in="raw_symbol",
                limit=None,
            )
            data.to_file(output_file)
            size_mb = os.path.getsize(output_file) / (1024 * 1024)
            print(f"[{ticker}] Downloaded {size_mb:.2f} MB")

        except Exception as e:
            print(f"[{ticker}] Error downloading: {e}")
