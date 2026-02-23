#!/usr/bin/env python3
"""
Download L2 (mbp-10) data for MU ticker from Databento for early January 2026.

Missing dates:
- January: 2026-01-01 to 2026-01-19
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Set API key provided by user
API_KEY = "db-qr7kiSdqdFBgBwakarv6cGe7HcBvy"
os.environ["DATABENTO_API_KEY"] = API_KEY

import databento as db

# Output directory
OUTPUT_DIR = Path("/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data/l2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TICKER = "MU"
SCHEMA = "mbp-10"
DATASET = "XNAS.ITCH"

# Trading days to download (excluding weekends)
DATES_TO_DOWNLOAD = []

# January start to Jan 20 (exclusive of 20, as we have it)
start = datetime(2026, 1, 1)
end = datetime(2026, 1, 19)
current = start
while current <= end:
    # Skip weekends (5 = Saturday, 6 = Sunday)
    if current.weekday() < 5:
        DATES_TO_DOWNLOAD.append(current.strftime("%Y-%m-%d"))
    current += timedelta(days=1)


def download_day(client: db.Historical, day: str) -> bool:
    """Download L2 data for a single day."""
    out_path = OUTPUT_DIR / f"{TICKER}_{day}_{day}.parquet"

    if out_path.exists():
        print(f"  [SKIP] {day} already exists: {out_path}")
        return True

    # Databento uses exclusive end date, so we add 1 day
    end_exclusive = (datetime.strptime(day, "%Y-%m-%d") + timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )

    print(f"  [DOWNLOAD] {day}...")
    try:
        data = client.timeseries.get_range(
            dataset=DATASET,
            symbols=[TICKER],
            schema=SCHEMA,
            start=day,
            end=end_exclusive,
            stype_in="raw_symbol",
        )

        # Convert to parquet
        df = data.to_df()
        if df.empty:
            print(f"  [WARN] {day}: No data returned (possibly holiday)")
            return False

        df.to_parquet(str(out_path))
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"  [OK] {day}: {len(df):,} rows, {size_mb:.1f} MB")
        return True

    except Exception as e:
        print(f"  [ERROR] {day}: {e}")
        return False


def main():
    print(f"Downloading L2 data for {TICKER}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Days to download: {len(DATES_TO_DOWNLOAD)}")
    print(f"Dates: {DATES_TO_DOWNLOAD}")
    print("-" * 50)

    client = db.Historical(API_KEY)

    success = 0
    failed = 0

    for day in DATES_TO_DOWNLOAD:
        if download_day(client, day):
            success += 1
        else:
            failed += 1

    print("-" * 50)
    print(f"Done: {success} success, {failed} failed")


if __name__ == "__main__":
    main()
