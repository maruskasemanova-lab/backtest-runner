#!/usr/bin/env python3
"""
Download MU MBP-10 (L2) data from Databento.

Important:
- Databento `end` is exclusive.
- To include 2026-02-05, set `--end-date 2026-02-06`.
"""

import argparse
import os

import databento as db


def download_data(api_key: str, ticker: str, start_date: str, end_date: str, output_dir: str) -> None:
    if not api_key:
        raise RuntimeError("Missing DATABENTO_API_KEY environment variable")

    os.makedirs(output_dir, exist_ok=True)
    client = db.Historical(api_key)
    output_file = os.path.join(output_dir, f"{ticker}_{start_date}_{end_date}.mbn")

    print(f"[{ticker}] Downloading MBP-10 from {start_date} to {end_date} (end exclusive)...")
    data = client.timeseries.get_range(
        dataset="XNAS.ITCH",
        symbols=ticker,
        start=start_date,
        end=end_date,
        schema="mbp-10",
        stype_in="raw_symbol",
        limit=None,
    )
    data.to_file(output_file)
    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"[{ticker}] Downloaded {size_mb:.2f} MB to {output_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download MU L2 data (Databento MBP-10).")
    parser.add_argument("--ticker", default="MU")
    parser.add_argument("--start-date", default="2026-02-03")
    parser.add_argument(
        "--end-date",
        default="2026-02-06",
        help="Exclusive end date. Example: 2026-02-06 includes 2026-02-05 session.",
    )
    parser.add_argument(
        "--output-dir",
        default="/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data/l2",
    )
    args = parser.parse_args()

    api_key = os.getenv("DATABENTO_API_KEY", "")
    download_data(
        api_key=api_key,
        ticker=args.ticker.upper(),
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
