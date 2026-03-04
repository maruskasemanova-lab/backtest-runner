#!/usr/bin/env python3
"""
Recompute cumulative day-by-day price heatmap levels into SQLite.

For each ticker and each bin size, this script stores rows in
`daily_price_heatmap_levels` keyed by:
  (ticker, as_of_date, bin_size, price_bin)

Each row is cumulative through `as_of_date` (inclusive), i.e. values on day D
contain bars/volume from all prior trading days and D itself.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import time
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_loader import DataLoader
from src.services.data_discovery import DataDiscovery
from src.services.saas_primitives import utc_now_iso

TABLE_NAME = "daily_price_heatmap_levels"
PRICE_HEATMAP_SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    ticker TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    bin_size REAL NOT NULL,
    price_bin REAL NOT NULL,
    day_bars INTEGER NOT NULL,
    day_volume REAL NOT NULL,
    cumulative_bars INTEGER NOT NULL,
    cumulative_volume REAL NOT NULL,
    total_bars_to_date INTEGER NOT NULL,
    total_volume_to_date REAL NOT NULL,
    cumulative_bar_share REAL NOT NULL,
    cumulative_volume_share REAL NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, as_of_date, bin_size, price_bin)
);
CREATE INDEX IF NOT EXISTS idx_daily_price_heatmap_lookup
    ON {TABLE_NAME}(ticker, as_of_date, bin_size, cumulative_bars DESC, cumulative_volume DESC);
CREATE INDEX IF NOT EXISTS idx_daily_price_heatmap_level_timeline
    ON {TABLE_NAME}(ticker, bin_size, price_bin, as_of_date);
"""


def _parse_bin_sizes(raw: str) -> list[float]:
    out: list[float] = []
    for token in str(raw or "").split(","):
        piece = str(token or "").strip()
        if not piece:
            continue
        value = float(piece)
        if value <= 0:
            raise ValueError(f"bin size must be > 0, got: {piece}")
        out.append(value)
    deduped = sorted({float(v) for v in out})
    if not deduped:
        raise ValueError("at least one bin size is required")
    return deduped


def _parse_tickers(raw: str) -> list[str]:
    out: list[str] = []
    for token in str(raw or "").split(","):
        ticker = str(token or "").strip().upper()
        if ticker:
            out.append(ticker)
    return sorted(set(out))


def _bin_decimals(bin_size: float) -> int:
    token = f"{float(bin_size):.10f}".rstrip("0").rstrip(".")
    if "." not in token:
        return 0
    return max(0, len(token.split(".", 1)[1]))


def ensure_price_heatmap_table(conn: sqlite3.Connection) -> None:
    conn.executescript(PRICE_HEATMAP_SCHEMA_SQL)


def _load_csv_fallback(path: Path) -> pd.DataFrame | None:
    try:
        raw = pd.read_csv(path)
    except Exception:
        return None
    if raw.empty:
        return raw

    if "timestamp" not in raw.columns:
        for candidate in ("Unnamed: 0", "index", "datetime", "date", "time"):
            if candidate in raw.columns:
                raw["timestamp"] = raw[candidate]
                break

    if "timestamp" not in raw.columns:
        try:
            indexed = pd.read_csv(path, index_col=0)
            if indexed.index.name is not None or not isinstance(indexed.index, pd.RangeIndex):
                indexed = indexed.reset_index()
                first_col = str(indexed.columns[0])
                indexed = indexed.rename(columns={first_col: "timestamp"})
                raw = indexed
        except Exception:
            return None

    if "close" not in raw.columns:
        for candidate in ("Close", "CLOSE", "c"):
            if candidate in raw.columns:
                raw["close"] = raw[candidate]
                break
    if "volume" not in raw.columns:
        for candidate in ("Volume", "VOLUME", "v", "vol"):
            if candidate in raw.columns:
                raw["volume"] = raw[candidate]
                break
    return raw


def load_ticker_bars(
    *,
    ticker: str,
    discovery: DataDiscovery,
    loader: DataLoader,
    include_premarket: bool,
) -> pd.DataFrame:
    scanned = discovery.scan(force_refresh=False)
    ticker_info = scanned.get(str(ticker or "").strip().upper())
    if ticker_info is None or not ticker_info.files:
        return pd.DataFrame(columns=["trading_day", "close", "volume"])

    frames: list[pd.DataFrame] = []
    for file_path in sorted(set(ticker_info.files)):
        path = Path(file_path)
        try:
            if path.suffix.lower() in {".parquet", ".parq"}:
                frame = loader.load_parquet(
                    str(path),
                    columns=["timestamp", "open", "high", "low", "close", "volume"],
                )
            else:
                frame = loader.load_csv(str(path))
        except Exception as exc:
            frame = None
            if path.suffix.lower() == ".csv":
                frame = _load_csv_fallback(path)
            if frame is None:
                print(f"[warn] {ticker}: failed to load {file_path}: {exc}")
                continue

        if frame.empty:
            continue
        if "timestamp" not in frame.columns or "close" not in frame.columns:
            print(f"[warn] {ticker}: missing required columns in {file_path}, skipping")
            continue
        view = frame[[col for col in ("timestamp", "close", "volume") if col in frame.columns]].copy()
        if "volume" not in view.columns:
            view["volume"] = 0.0
        frames.append(view)

    if not frames:
        return pd.DataFrame(columns=["trading_day", "close", "volume"])

    bars = pd.concat(frames, ignore_index=True)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], utc=True, errors="coerce")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars["volume"] = pd.to_numeric(bars["volume"], errors="coerce").fillna(0.0)
    bars = bars.dropna(subset=["timestamp", "close"]).copy()
    if bars.empty:
        return pd.DataFrame(columns=["trading_day", "close", "volume"])

    bars = bars.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")

    ts_et = bars["timestamp"].dt.tz_convert("America/New_York")
    market_time = ts_et.dt.time
    if include_premarket:
        time_mask = (market_time >= time(4, 0)) & (market_time <= time(16, 0))
    else:
        time_mask = (market_time >= time(9, 30)) & (market_time <= time(16, 0))

    bars = bars.loc[time_mask].copy()
    if bars.empty:
        return pd.DataFrame(columns=["trading_day", "close", "volume"])
    bars["trading_day"] = ts_et.loc[time_mask].dt.strftime("%Y-%m-%d")
    return bars[["trading_day", "close", "volume"]].reset_index(drop=True)


def build_cumulative_rows_from_bars(
    bars: pd.DataFrame,
    *,
    ticker: str,
    bin_size: float,
) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "as_of_date",
                "bin_size",
                "price_bin",
                "day_bars",
                "day_volume",
                "cumulative_bars",
                "cumulative_volume",
                "total_bars_to_date",
                "total_volume_to_date",
                "cumulative_bar_share",
                "cumulative_volume_share",
            ]
        )

    work = bars[["trading_day", "close", "volume"]].copy()
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work["volume"] = pd.to_numeric(work["volume"], errors="coerce").fillna(0.0)
    work = work[np.isfinite(work["close"])].copy()
    if work.empty:
        return pd.DataFrame()

    decimals = _bin_decimals(bin_size)
    work["price_bin"] = np.round(work["close"] / float(bin_size)) * float(bin_size)
    work["price_bin"] = work["price_bin"].round(decimals)

    grouped = (
        work.groupby(["trading_day", "price_bin"], as_index=False)
        .agg(day_bars=("close", "size"), day_volume=("volume", "sum"))
        .sort_values(["trading_day", "price_bin"], ascending=[True, False])
    )
    if grouped.empty:
        return pd.DataFrame()

    day_counts = grouped.pivot(index="trading_day", columns="price_bin", values="day_bars").fillna(0.0)
    day_counts = day_counts.sort_index().astype(np.int64)
    day_volumes = grouped.pivot(index="trading_day", columns="price_bin", values="day_volume").fillna(0.0)
    day_volumes = day_volumes.reindex(index=day_counts.index, columns=day_counts.columns, fill_value=0.0).astype(float)

    cumulative_counts = day_counts.cumsum(axis=0)
    cumulative_volumes = day_volumes.cumsum(axis=0)
    if cumulative_counts.empty or cumulative_counts.shape[1] == 0:
        return pd.DataFrame()

    num_days = cumulative_counts.shape[0]
    num_levels = cumulative_counts.shape[1]
    as_of_dates = cumulative_counts.index.astype(str).to_numpy()
    levels = np.asarray(cumulative_counts.columns.to_numpy(), dtype=float)

    day_bars_flat = day_counts.to_numpy(dtype=np.int64).reshape(-1)
    day_volume_flat = day_volumes.to_numpy(dtype=float).reshape(-1)
    cumulative_bars_flat = cumulative_counts.to_numpy(dtype=np.int64).reshape(-1)
    cumulative_volume_flat = cumulative_volumes.to_numpy(dtype=float).reshape(-1)

    total_bars_by_day = cumulative_counts.sum(axis=1).to_numpy(dtype=np.int64)
    total_volume_by_day = cumulative_volumes.sum(axis=1).to_numpy(dtype=float)
    total_bars_flat = np.repeat(total_bars_by_day, num_levels)
    total_volume_flat = np.repeat(total_volume_by_day, num_levels)

    out = pd.DataFrame(
        {
            "ticker": str(ticker or "").strip().upper(),
            "as_of_date": np.repeat(as_of_dates, num_levels),
            "bin_size": float(bin_size),
            "price_bin": np.tile(levels, num_days),
            "day_bars": day_bars_flat,
            "day_volume": day_volume_flat,
            "cumulative_bars": cumulative_bars_flat,
            "cumulative_volume": cumulative_volume_flat,
            "total_bars_to_date": total_bars_flat,
            "total_volume_to_date": total_volume_flat,
        }
    )
    out = out[out["cumulative_bars"] > 0].copy()
    if out.empty:
        return out

    out["cumulative_bar_share"] = np.where(
        out["total_bars_to_date"] > 0,
        out["cumulative_bars"] / out["total_bars_to_date"],
        0.0,
    )
    out["cumulative_volume_share"] = np.where(
        out["total_volume_to_date"] > 0,
        out["cumulative_volume"] / out["total_volume_to_date"],
        0.0,
    )

    out["price_bin"] = out["price_bin"].round(decimals)
    out["day_volume"] = out["day_volume"].round(6)
    out["cumulative_volume"] = out["cumulative_volume"].round(6)
    out["total_volume_to_date"] = out["total_volume_to_date"].round(6)
    out["cumulative_bar_share"] = out["cumulative_bar_share"].round(10)
    out["cumulative_volume_share"] = out["cumulative_volume_share"].round(10)

    return out.sort_values(["as_of_date", "price_bin"], ascending=[True, False]).reset_index(drop=True)


def _insert_rows(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    bin_size: float,
    rows: pd.DataFrame,
    batch_size: int,
) -> int:
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM {TABLE_NAME} WHERE ticker = ? AND bin_size = ?",
        (str(ticker or "").strip().upper(), float(bin_size)),
    )
    if rows.empty:
        return 0

    now = utc_now_iso()
    payload = rows.copy()
    payload["updated_at"] = now
    insert_sql = f"""
        INSERT INTO {TABLE_NAME}(
            ticker,
            as_of_date,
            bin_size,
            price_bin,
            day_bars,
            day_volume,
            cumulative_bars,
            cumulative_volume,
            total_bars_to_date,
            total_volume_to_date,
            cumulative_bar_share,
            cumulative_volume_share,
            updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, as_of_date, bin_size, price_bin) DO UPDATE SET
            day_bars=excluded.day_bars,
            day_volume=excluded.day_volume,
            cumulative_bars=excluded.cumulative_bars,
            cumulative_volume=excluded.cumulative_volume,
            total_bars_to_date=excluded.total_bars_to_date,
            total_volume_to_date=excluded.total_volume_to_date,
            cumulative_bar_share=excluded.cumulative_bar_share,
            cumulative_volume_share=excluded.cumulative_volume_share,
            updated_at=excluded.updated_at
    """

    cols = [
        "ticker",
        "as_of_date",
        "bin_size",
        "price_bin",
        "day_bars",
        "day_volume",
        "cumulative_bars",
        "cumulative_volume",
        "total_bars_to_date",
        "total_volume_to_date",
        "cumulative_bar_share",
        "cumulative_volume_share",
        "updated_at",
    ]
    inserted = 0
    for start in range(0, len(payload), batch_size):
        batch = payload.iloc[start : start + batch_size][cols]
        cur.executemany(insert_sql, batch.itertuples(index=False, name=None))
        inserted += len(batch)
    return inserted


def recompute_daily_heatmaps(
    *,
    db_path: Path,
    tickers: Sequence[str],
    bin_sizes: Sequence[float],
    include_premarket: bool,
    dry_run: bool,
    batch_size: int,
) -> int:
    discovery = DataDiscovery()
    discovered = discovery.scan(force_refresh=True)
    if not discovered:
        print("[warn] No tickers discovered in configured OHLCV directories.")
        return 0

    target_tickers = (
        sorted({ticker.upper() for ticker in tickers})
        if tickers
        else sorted(discovered.keys())
    )
    if not target_tickers:
        print("[warn] No target tickers selected.")
        return 0

    loader = DataLoader()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    ensure_price_heatmap_table(conn)

    total_rows = 0
    total_pairs = 0
    try:
        for ticker in target_tickers:
            bars = load_ticker_bars(
                ticker=ticker,
                discovery=discovery,
                loader=loader,
                include_premarket=include_premarket,
            )
            if bars.empty:
                print(f"[warn] {ticker}: no bars after load/filter, skipping")
                continue
            days = int(bars["trading_day"].nunique())
            print(f"[info] {ticker}: bars={len(bars):,} days={days}")

            for bin_size in bin_sizes:
                built = build_cumulative_rows_from_bars(
                    bars,
                    ticker=ticker,
                    bin_size=float(bin_size),
                )
                total_pairs += 1
                if dry_run:
                    print(
                        f"[dry-run] {ticker} bin={bin_size:g}: rows={len(built):,}"
                    )
                    total_rows += int(len(built))
                    continue

                inserted = _insert_rows(
                    conn,
                    ticker=ticker,
                    bin_size=float(bin_size),
                    rows=built,
                    batch_size=batch_size,
                )
                conn.commit()
                total_rows += int(inserted)
                print(f"[ok] {ticker} bin={bin_size:g}: upserted={inserted:,}")
    finally:
        conn.close()

    print(
        f"[done] ticker-bin pairs={total_pairs:,} total_rows={'(dry-run) ' if dry_run else ''}{total_rows:,}"
    )
    return total_rows


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute cumulative daily price heatmap rows "
            "(ticker + as_of_day + price_bin) into SQLite."
        )
    )
    parser.add_argument(
        "--db-path",
        default="data/saas_state.db",
        help="SQLite DB path (default: data/saas_state.db)",
    )
    parser.add_argument(
        "--tickers",
        default="",
        help="Comma-separated tickers. Empty means all discovered tickers.",
    )
    parser.add_argument(
        "--bin-sizes",
        default="0.25,0.5,1,2",
        help="Comma-separated price bin sizes (default: 0.25,0.5,1,2).",
    )
    parser.add_argument(
        "--regular-session-only",
        action="store_true",
        help="Use 09:30-16:00 ET only (default includes 04:00-16:00 ET).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="SQLite insert batch size (default: 5000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build rows and print counts without writing to DB.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    db_path = Path(str(args.db_path or "").strip() or "data/saas_state.db")
    db_path = db_path if db_path.is_absolute() else (Path.cwd() / db_path)
    tickers = _parse_tickers(args.tickers)
    bin_sizes = _parse_bin_sizes(args.bin_sizes)
    batch_size = max(100, int(args.batch_size or 5000))

    recompute_daily_heatmaps(
        db_path=db_path,
        tickers=tickers,
        bin_sizes=bin_sizes,
        include_premarket=not bool(args.regular_session_only),
        dry_run=bool(args.dry_run),
        batch_size=batch_size,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
