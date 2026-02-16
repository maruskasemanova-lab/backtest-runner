#!/usr/bin/env python3
"""Backfill missing MU MBP-10 (L2) daily parquet files from Databento."""

from __future__ import annotations

import argparse
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Set

import databento as db

DEFAULT_START_DATE = "2025-11-03"
DEFAULT_END_DATE = date.today().isoformat()
DEFAULT_OUTPUT_DIR = "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data/l2"
TICKER = "MU"
SCHEMA = "mbp-10"
DATASET = "XNAS.ITCH"

# NYSE full-day market holidays needed for the covered period.
MARKET_HOLIDAYS = {
    "2025-11-27",  # Thanksgiving Day
    "2025-12-25",  # Christmas Day
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # Martin Luther King Jr. Day
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing MU L2 daily files (Databento MBP-10).")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", default=DEFAULT_END_DATE, help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for MU_YYYY-MM-DD_YYYY-MM-DD.parquet.")
    parser.add_argument("--api-key", default="", help="Databento API key. Falls back to DATABENTO_API_KEY env var.")
    return parser.parse_args()


def _iter_target_days(start_date: str, end_date: str) -> List[str]:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
    if start_dt > end_dt:
        raise ValueError(f"Invalid range: {start_date} > {end_date}")

    out: List[str] = []
    cur = start_dt
    while cur <= end_dt:
        day = cur.isoformat()
        if cur.weekday() < 5 and day not in MARKET_HOLIDAYS:
            out.append(day)
        cur += timedelta(days=1)
    return out


def _existing_days(output_dir: Path) -> Set[str]:
    pattern = re.compile(rf"^{TICKER}_(\d{{4}}-\d{{2}}-\d{{2}})_\1\.parquet$")
    out: Set[str] = set()
    for path in output_dir.glob(f"{TICKER}_*.parquet"):
        match = pattern.match(path.name)
        if match:
            out.add(match.group(1))
    return out


def _summarize_days(days: Iterable[str], *, max_items: int = 10) -> str:
    ordered = sorted(set(str(day) for day in days))
    if not ordered:
        return "-"
    if len(ordered) <= max_items:
        return ",".join(ordered)
    return f"{','.join(ordered[:max_items])},...(+{len(ordered) - max_items} more)"


def _download_single_day(client: db.Historical, output_dir: Path, day: str) -> str:
    out_path = output_dir / f"{TICKER}_{day}_{day}.parquet"
    if out_path.exists():
        return "exists"

    end_exclusive = (datetime.strptime(day, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    print(f"[DOWNLOAD] {day}")
    try:
        data = client.timeseries.get_range(
            dataset=DATASET,
            symbols=[TICKER],
            schema=SCHEMA,
            start=day,
            end=end_exclusive,
            stype_in="raw_symbol",
            limit=None,
        )
        df = data.to_df()
    except Exception as exc:  # pragma: no cover - network/service surface
        print(f"[ERROR] {day}: {exc}")
        return "error"

    if df.empty:
        print(f"[ERROR] {day}: Databento returned empty dataset.")
        return "empty"

    df.to_parquet(str(out_path))
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"[OK] {day}: rows={len(df):,} size={size_mb:.1f}MB")
    return "downloaded"


def main() -> int:
    args = _parse_args()
    api_key = args.api_key.strip() or os.getenv("DATABENTO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing Databento API key. Use --api-key or set DATABENTO_API_KEY.")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    target_days = _iter_target_days(args.start_date, args.end_date)
    existing = _existing_days(output_dir)
    missing = sorted(day for day in target_days if day not in existing)

    print(f"Ticker: {TICKER}")
    print(f"Schema: {SCHEMA}")
    print(f"Dataset: {DATASET}")
    print(f"Output: {output_dir}")
    print(f"Target range: {args.start_date}..{args.end_date}")
    print(f"Target trading days: {len(target_days)}")
    print(f"Already present: {len(target_days) - len(missing)}")
    print(f"Missing before download: {len(missing)}")
    if missing:
        print(f"Missing preview: {_summarize_days(missing)}")

    if not missing:
        print("No missing MU L2 days found.")
        return 0

    client = db.Historical(api_key)
    counters = {"downloaded": 0, "exists": 0, "empty": 0, "error": 0}
    for day in missing:
        result = _download_single_day(client, output_dir, day)
        counters[result] = int(counters.get(result, 0)) + 1

    existing_after = _existing_days(output_dir)
    missing_after = sorted(day for day in target_days if day not in existing_after)

    print("----")
    print(
        "Download summary: "
        f"downloaded={counters['downloaded']} "
        f"empty={counters['empty']} "
        f"error={counters['error']}"
    )
    print(f"Missing after download: {len(missing_after)}")
    if missing_after:
        print(f"Missing preview: {_summarize_days(missing_after)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
