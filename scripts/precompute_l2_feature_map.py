from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.l2_data_manager import L2DataManager
from src.l2_feature_service import L2FeatureService
from src.parquet_compat import write_parquet_compat


def _parse_iso_day(raw: str) -> datetime:
    day = datetime.strptime(str(raw), "%Y-%m-%d")
    return day.replace(tzinfo=timezone.utc)


def _iter_days(start_day: datetime, end_day: datetime) -> Iterable[datetime]:
    current = start_day
    while current <= end_day:
        yield current
        current = current + timedelta(days=1)


def _feature_rows(feature_map: Dict[int, Dict[str, object]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for minute_key in sorted(feature_map.keys()):
        features = feature_map[minute_key] if isinstance(feature_map[minute_key], dict) else {}
        row: Dict[str, object] = {"minute_key": int(minute_key)}
        row.update(features)
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Precompute daily L2 minute feature maps for faster run start.",
    )
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g. MU)")
    parser.add_argument("--start-date", required=True, help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument(
        "--data-dir",
        default="",
        help="Optional raw L2 directory override (defaults to configured runtime roots).",
    )
    parser.add_argument(
        "--output-dir",
        default="data/l2_precomputed",
        help="Output directory for precomputed per-day parquet files.",
    )
    parser.add_argument(
        "--include-icebergs",
        action="store_true",
        help="Also compute iceberg counts/bias in precomputed features.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rebuild files even when target parquet already exists.",
    )
    args = parser.parse_args()

    start_day = _parse_iso_day(args.start_date)
    end_day = _parse_iso_day(args.end_date)
    if end_day < start_day:
        raise ValueError("end-date must be >= start-date")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ticker = str(args.ticker).strip().upper()
    manager = (
        L2DataManager(data_dirs=[str(Path(args.data_dir).expanduser().resolve())])
        if str(args.data_dir or "").strip()
        else L2DataManager()
    )
    manager.precomputed_features_enabled = False

    logger = logging.getLogger("precompute_l2_feature_map")
    logger.setLevel(logging.INFO)
    service = L2FeatureService(
        manager=manager,
        logger=logger,
        iceberg_detection_enabled=bool(args.include_icebergs),
    )

    built = 0
    skipped = 0
    for day in _iter_days(start_day, end_day):
        day_token = day.date().isoformat()
        target = output_dir / f"{ticker}_{day_token}.parquet"
        if target.exists() and not bool(args.overwrite):
            print(f"Skipping {target} (exists)")
            skipped += 1
            continue

        start_dt = datetime.combine(day.date(), time(0, 0, 0), tzinfo=timezone.utc)
        end_dt = datetime.combine(day.date(), time(23, 59, 59, 999999), tzinfo=timezone.utc)

        feature_map, stats = service.build_feature_map(
            ticker=ticker,
            start_dt_utc=start_dt,
            end_dt_utc=end_dt,
        )
        if not feature_map:
            print(f"No L2 features for {ticker} {day_token}; skipping.")
            skipped += 1
            continue

        rows = _feature_rows(feature_map)
        frame = pd.DataFrame(rows)
        write_parquet_compat(frame, target, index=False)
        built += 1
        print(
            f"Built {target} minutes={len(rows)} trade_events={int(stats.get('trade_events', 0))} "
            f"icebergs={int(stats.get('icebergs', 0))}"
        )

    print(
        f"Done ticker={ticker} start={args.start_date} end={args.end_date} "
        f"built={built} skipped={skipped} output_dir={output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
