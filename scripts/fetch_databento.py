#!/usr/bin/env python3
"""
Fetch Databento OHLCV-1m data and store to the local databento_data folder.
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from available_data import DataDiscovery, DEFAULT_DATA_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Databento OHLCV-1m data.")
    parser.add_argument(
        "--tickers",
        type=str,
        required=True,
        help="Comma-separated tickers (e.g. AAPL,MSFT,GOOGL,MU)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="Inclusive end date in YYYY-MM-DD",
    )
    parser.add_argument(
        "--default-start",
        type=str,
        default="2025-08-01",
        help="Start date for tickers without existing data (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="XNAS.ITCH",
        help="Databento dataset (default: XNAS.ITCH)",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default="ohlcv-1m",
        help="Databento schema (default: ohlcv-1m)",
    )
    return parser.parse_args()


def next_day(date_str: str) -> str:
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def main() -> None:
    args = parse_args()

    api_key = os.getenv("DATABENTO_API_KEY")
    if not api_key:
        raise SystemExit("DATABENTO_API_KEY is not set.")

    try:
        import databento as db
    except Exception as exc:
        raise SystemExit(f"Databento client not available: {exc}")

    data_dir = Path(DEFAULT_DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    discovery = DataDiscovery(str(data_dir))
    client = db.Historical(api_key)

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    end_date = args.end_date
    end_exclusive = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

    for ticker in tickers:
        existing_range = discovery.get_date_range(ticker)
        if existing_range.get("end"):
            start_date = next_day(existing_range["end"])
        else:
            start_date = args.default_start

        if start_date > end_date:
            print(f"[{ticker}] up to date (start {start_date} > end {end_date})")
            continue

        out_name = f"{ticker}_ohlcv-1m_{start_date}_{end_date}.csv"
        out_path = data_dir / out_name

        print(f"[{ticker}] downloading {start_date} -> {end_date} into {out_path}")
        data = client.timeseries.get_range(
            dataset=args.dataset,
            schema=args.schema,
            symbols=[ticker],
            stype_in="raw_symbol",
            start=start_date,
            end=end_exclusive,
        )

        df = data.to_df()
        if df.empty:
            print(f"[{ticker}] no data returned")
            continue

        if "ts_event" in df.columns:
            df = df.rename(columns={"ts_event": "timestamp"})
        else:
            # Databento sometimes returns ts_event as the index
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
                if "ts_event" in df.columns:
                    df = df.rename(columns={"ts_event": "timestamp"})
                elif "index" in df.columns:
                    df = df.rename(columns={"index": "timestamp"})

        df.to_csv(out_path, index=False)
        print(f"[{ticker}] saved {len(df)} rows")


if __name__ == "__main__":
    main()
