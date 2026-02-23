#!/usr/bin/env python3
"""Download MU OHLCV-1m data from Databento for backtesting."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

API_KEY = os.environ.get("DATABENTO_API_KEY", "db-TWf5ne9UQdHSDMwk6uHBvTesi5rq4")
os.environ["DATABENTO_API_KEY"] = API_KEY

import databento as db

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATASET = "XNAS.ITCH"
SCHEMA = "ohlcv-1m"

DOWNLOADS = [
    ("MU", "2026-01-20", "2026-02-06"),
]


def download_range(client: db.Historical, ticker: str, start: str, end: str) -> bool:
    out_name = f"{ticker}_{SCHEMA}_{start}_{end}.csv"
    out_path = OUTPUT_DIR / out_name

    if out_path.exists():
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"  [SKIP] {out_name} already exists ({size_mb:.1f} MB)")
        return True

    end_exclusive = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )

    print(f"  [DOWNLOAD] {ticker} {start} -> {end} ...")
    try:
        data = client.timeseries.get_range(
            dataset=DATASET,
            symbols=[ticker],
            schema=SCHEMA,
            start=start,
            end=end_exclusive,
            stype_in="raw_symbol",
        )

        df = data.to_df()
        if df.empty:
            print(f"  [WARN] No data returned for {ticker}")
            return False

        if hasattr(df.index, "name") and df.index.name:
            df = df.reset_index()
            if "ts_event" in df.columns:
                df = df.rename(columns={"ts_event": "timestamp"})

        df.to_csv(str(out_path), index=False)
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"  [OK] {len(df):,} rows, {size_mb:.1f} MB -> {out_name}")
        return True

    except Exception as e:
        print(f"  [ERROR] {ticker}: {e}")
        return False


def main():
    print("Downloading MU OHLCV-1m data from Databento")
    print(f"Output: {OUTPUT_DIR}")
    print("-" * 50)

    client = db.Historical(API_KEY)

    success = 0
    failed = 0

    for ticker, start, end in DOWNLOADS:
        print(f"\n{ticker}: {start} to {end}")
        if download_range(client, ticker, start, end):
            success += 1
        else:
            failed += 1

    print("-" * 50)
    print(f"Done: {success} success, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
