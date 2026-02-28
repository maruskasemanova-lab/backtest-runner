"""
Data Loader - Loads trading day data from various sources.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, time, timezone
from typing import List, Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo
import os

from src.system_settings import DEFAULT_EXTERNAL_DATA_DIR, SystemSettings
from src.parquet_compat import read_parquet_compat, scan_parquet_compat

try:
    import polars as pl
except Exception:  # pragma: no cover - runtime requires polars, but keep import safe
    pl = None


class DataLoader:
    """Loads and prepares trading day data for the backtest runner."""

    # Default data directory
    DEFAULT_DATA_DIR = str(DEFAULT_EXTERNAL_DATA_DIR)
    PROJECT_ROOT = Path(__file__).resolve().parent
    TIMESTAMP_COLUMN_CANDIDATES = (
        "timestamp",
        "ts_event",
        "ts_recv",
        "time",
        "datetime",
        "date",
    )
    REQUIRED_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
    OPTIONAL_BAR_COLUMNS = ("vwap",)
    OHLCV_ALT_NAMES = {
        "open": ("Open", "OPEN", "o"),
        "high": ("High", "HIGH", "h"),
        "low": ("Low", "LOW", "l"),
        "close": ("Close", "CLOSE", "c"),
        "volume": ("Volume", "VOLUME", "v", "vol"),
    }

    def __init__(
        self, data_dir: Optional[str] = None, data_dirs: Optional[List[str]] = None
    ):
        if data_dirs:
            self.data_dirs = [Path(d).expanduser().resolve() for d in data_dirs]
        elif data_dir:
            self.data_dirs = [Path(data_dir).expanduser().resolve()]
        else:
            configured = SystemSettings().get_ohlcv_dirs(existing_only=False)
            self.data_dirs = configured or [Path(self.DEFAULT_DATA_DIR)]

        self.data_dir = self.data_dirs[0]  # Backward compatibility.
        self.project_root = self.PROJECT_ROOT
        self.market_tz = ZoneInfo("America/New_York")

    def _resolve_file_path(self, filename: str) -> Path:
        filepath = Path(filename).expanduser()
        if filepath.is_absolute():
            if filepath.exists():
                return filepath
            raise FileNotFoundError(f"Data file not found: {filepath}")

        # Try direct project-relative path first (e.g., "data/MU_ohlcv-1m_...csv").
        for candidate in (filepath, self.project_root / filepath):
            if candidate.exists():
                return candidate.resolve()

        for base_dir in self.data_dirs:
            candidate = base_dir / filepath
            if candidate.exists():
                return candidate.resolve()

            # Backward-compatible: allow "data/foo.csv" with base root ".../data".
            parts = filepath.parts
            if parts and parts[0] == base_dir.name:
                prefixed = base_dir.parent.joinpath(*parts)
                if prefixed.exists():
                    return prefixed.resolve()

        raise FileNotFoundError(
            f"Data file not found in configured roots {self.data_dirs}: {filename}"
        )

    def _market_timestamp_series(self, df: pd.DataFrame) -> pd.Series:
        """Return timestamps converted to market timezone (ET)."""
        ts = df["timestamp"]
        if ts.dt.tz is None:
            ts = ts.dt.tz_localize("UTC")
        return ts.dt.tz_convert(self.market_tz)

    def load_csv(self, filename: str) -> pd.DataFrame:
        """Load data from CSV file."""
        filepath = self._resolve_file_path(filename)

        # Read without parse_dates since column names vary
        df = pd.read_csv(filepath)
        return self._prepare_dataframe(df)

    def preferred_parquet_columns(self) -> List[str]:
        """Column projection for analyzer/runtime OHLCV parquet loads."""
        columns: List[str] = list(self.TIMESTAMP_COLUMN_CANDIDATES)
        for col in self.REQUIRED_OHLCV_COLUMNS:
            columns.append(col)
            columns.extend(self.OHLCV_ALT_NAMES.get(col, ()))
        columns.extend(self.OPTIONAL_BAR_COLUMNS)
        return list(dict.fromkeys(columns))

    @staticmethod
    def _normalize_requested_columns(columns: Optional[List[str]]) -> List[str]:
        return [str(col) for col in (columns or []) if str(col).strip()]

    def _parquet_schema_columns(self, filepath: Path) -> List[str]:
        if pl is None:
            raise RuntimeError("polars is required for parquet loading")
        schema = scan_parquet_compat(filepath).collect_schema()
        try:
            return [str(name) for name in schema.names()]
        except Exception:
            return [str(name) for name in dict(schema).keys()]

    def _existing_requested_parquet_columns(
        self, filepath: Path, columns: Optional[List[str]]
    ) -> List[str]:
        requested = self._normalize_requested_columns(columns)
        if not requested:
            return []
        available = set(self._parquet_schema_columns(filepath))
        return [col for col in requested if col in available]

    def _resolve_parquet_timestamp_column(self, available: set[str]) -> str:
        for col in self.TIMESTAMP_COLUMN_CANDIDATES:
            if col in available:
                return col
        raise ValueError(
            f"No timestamp column found. Available: {sorted(available)}"
        )

    def _resolve_parquet_value_column(self, target: str, available: set[str]) -> str:
        if target in available:
            return target
        for alt in self.OHLCV_ALT_NAMES.get(target, ()):
            if alt in available:
                return alt
        raise ValueError(f"Required column '{target}' not found in parquet data")

    @staticmethod
    def _polars_timestamp_expr(source_col: str):
        if pl is None:
            raise RuntimeError("polars is required for parquet loading")
        expr = pl.col(source_col).cast(pl.Utf8).str
        try:
            parsed = expr.to_datetime(strict=False, exact=False, format="%+")
        except TypeError:
            try:
                parsed = expr.to_datetime(strict=False, exact=False)
            except TypeError:
                parsed = expr.strptime(pl.Datetime, strict=False, exact=False, format="%+")
        return parsed.alias("timestamp")

    def _build_canonical_parquet_lazyframe(self, filepath: Path):
        if pl is None:
            raise RuntimeError("polars is required for parquet loading")
        lazy_frame = scan_parquet_compat(filepath)
        available = set(self._parquet_schema_columns(filepath))
        timestamp_col = self._resolve_parquet_timestamp_column(available)
        select_exprs = [self._polars_timestamp_expr(timestamp_col)]
        for col in self.REQUIRED_OHLCV_COLUMNS:
            source_col = self._resolve_parquet_value_column(col, available)
            select_exprs.append(pl.col(source_col).alias(col))
        if "vwap" in available:
            select_exprs.append(pl.col("vwap").alias("vwap"))
        return lazy_frame.select(select_exprs)

    def _collect_polars_frame(self, lazy_frame):
        try:
            return lazy_frame.collect(engine="streaming")
        except TypeError:
            try:
                return lazy_frame.collect(streaming=True)
            except TypeError:
                return lazy_frame.collect()

    def load_parquet(
        self, filename: str, *, columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Load data from Parquet file."""
        filepath = self._resolve_file_path(filename)
        selected_columns = self._existing_requested_parquet_columns(filepath, columns)
        df = read_parquet_compat(filepath, columns=selected_columns or None)
        return self._prepare_dataframe(df)

    def _timestamp_to_market(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            ts = value
        else:
            ts = pd.Timestamp(value).to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(self.market_tz)

    def load_parquet_bars_for_range(
        self,
        filenames: List[str],
        *,
        start_date: str,
        end_date: str,
        include_premarket: bool = True,
        trading_hours: Optional[List[int]] = None,
        regular_session_only: bool = False,
    ) -> List[Dict[str, Any]]:
        if pl is None:
            raise RuntimeError("polars is required for parquet loading")
        filepaths = [self._resolve_file_path(name) for name in filenames]
        if not filepaths:
            return []

        frames = [
            self._collect_polars_frame(self._build_canonical_parquet_lazyframe(filepath))
            for filepath in filepaths
        ]
        combined = (
            frames[0]
            if len(frames) == 1
            else pl.concat(frames, how="vertical_relaxed")
        )
        if combined.height == 0:
            return []

        combined = combined.unique(subset=["timestamp"], keep="first").sort("timestamp")
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        normalized_hours = {
            int(hour)
            for hour in (trading_hours or [])
            if str(hour).strip() and str(hour).strip().lstrip("-").isdigit()
        }
        session_start = (
            time(9, 30)
            if regular_session_only or not include_premarket
            else time(4, 0)
        )
        session_close = time(16, 0)

        bars: List[Dict[str, Any]] = []
        for row in combined.iter_rows(named=True):
            market_ts = self._timestamp_to_market(row["timestamp"])
            market_date = market_ts.date()
            if market_date < start or market_date > end:
                continue
            market_time = market_ts.time()
            if market_time < session_start or market_time > session_close:
                continue
            if (
                normalized_hours
                and not regular_session_only
                and market_ts.hour not in normalized_hours
            ):
                continue
            bars.append(
                {
                    "index": len(bars),
                    "timestamp": row["timestamp"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                    "vwap": (
                        float(row["vwap"])
                        if "vwap" in row and row["vwap"] is not None
                        else None
                    ),
                }
            )
        return bars

    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare dataframe with required columns."""
        # Find and normalize timestamp column
        for col in self.TIMESTAMP_COLUMN_CANDIDATES:
            if col in df.columns:
                df["timestamp"] = pd.to_datetime(df[col])
                break
        else:
            raise ValueError(
                f"No timestamp column found. Available: {list(df.columns)}"
            )

        # Ensure OHLCV columns
        for col in self.REQUIRED_OHLCV_COLUMNS:
            if col not in df.columns:
                for alt in self.OHLCV_ALT_NAMES.get(col, ()):
                    if alt in df.columns:
                        df[col] = df[alt]
                        break
                else:
                    raise ValueError(f"Required column '{col}' not found in data")

        # Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)

        return df

    def filter_trading_day(
        self,
        df: pd.DataFrame,
        date: str,
        include_premarket: bool = True,
        premarket_start: time = time(4, 0),
        market_open: time = time(9, 30),
        market_close: time = time(16, 0),
    ) -> pd.DataFrame:
        """Filter data to a specific trading day."""
        target_date = pd.to_datetime(date).date()
        market_ts = self._market_timestamp_series(df)

        # Filter by market date (ET)
        date_mask = market_ts.dt.date == target_date

        if include_premarket:
            time_mask = (market_ts.dt.time >= premarket_start) & (
                market_ts.dt.time <= market_close
            )
        else:
            time_mask = (market_ts.dt.time >= market_open) & (
                market_ts.dt.time <= market_close
            )

        final_mask = date_mask & time_mask
        return df[final_mask].reset_index(drop=True)

    def filter_trading_range(
        self,
        df: pd.DataFrame,
        start_date: str,
        end_date: str,
        include_premarket: bool = True,
        premarket_start: time = time(4, 0),
        market_open: time = time(9, 30),
        market_close: time = time(16, 0),
    ) -> pd.DataFrame:
        """Filter data to a date range (inclusive) and session hours."""
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        market_ts = self._market_timestamp_series(df)

        # Date range filter (inclusive) in ET
        date_mask = (market_ts.dt.date >= start) & (market_ts.dt.date <= end)

        if include_premarket:
            time_mask = (market_ts.dt.time >= premarket_start) & (
                market_ts.dt.time <= market_close
            )
        else:
            time_mask = (market_ts.dt.time >= market_open) & (
                market_ts.dt.time <= market_close
            )

        final_mask = date_mask & time_mask
        return df[final_mask].reset_index(drop=True)

    def filter_trading_hours(
        self, df: pd.DataFrame, hours_et: Optional[List[int]] = None
    ) -> pd.DataFrame:
        """Filter bars by allowed hour(s) in market timezone (ET)."""
        if not hours_et:
            return df.reset_index(drop=True)

        normalized_hours = set()
        for hour in hours_et:
            try:
                normalized_hours.add(int(hour))
            except (TypeError, ValueError):
                continue
        if not normalized_hours:
            return df.reset_index(drop=True)
        market_ts = self._market_timestamp_series(df)
        mask = market_ts.dt.hour.isin(normalized_hours)
        return df[mask].reset_index(drop=True)

    def get_bars_iterator(self, df: pd.DataFrame):
        """Yield bars one by one for walk-forward simulation."""
        has_vwap = "vwap" in df.columns
        for idx, row in enumerate(df.itertuples(index=False)):
            yield {
                "index": idx,
                "timestamp": row.timestamp,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
                "vwap": (
                    float(getattr(row, "vwap", 0.0))
                    if has_vwap and getattr(row, "vwap", None) is not None
                    else None
                ),
            }

    def generate_mock_data(
        self,
        ticker: str,
        date: str,
        base_price: float = 150.0,
        volatility: float = 0.02,
        bars_per_day: int = 390,  # 1-min bars for regular hours
    ) -> pd.DataFrame:
        """Generate mock trading data for testing."""
        np.random.seed(42)

        target_date = pd.to_datetime(date)

        # Generate timestamps (9:30 AM to 4:00 PM)
        timestamps = pd.date_range(
            start=target_date.replace(hour=9, minute=30),
            periods=bars_per_day,
            freq="1min",
        )

        # Generate price movement with random walk
        returns = np.random.normal(0, volatility / np.sqrt(bars_per_day), bars_per_day)

        # Add some trend component
        trend = np.cumsum(returns)
        prices = base_price * (1 + trend)

        # Generate OHLCV
        data = []
        for i, (ts, close) in enumerate(zip(timestamps, prices)):
            bar_volatility = volatility * np.random.uniform(0.5, 1.5)
            high = close * (1 + bar_volatility * np.random.uniform(0, 1))
            low = close * (1 - bar_volatility * np.random.uniform(0, 1))
            open_price = close + (high - low) * np.random.uniform(-0.3, 0.3)

            # Ensure OHLC consistency
            high = max(open_price, close, high)
            low = min(open_price, close, low)

            volume = int(
                np.random.uniform(10000, 100000) * (1 + np.random.uniform(0, 2))
            )

            data.append(
                {
                    "timestamp": ts,
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": volume,
                    "vwap": round((open_price + close + high + low) / 4, 2),
                }
            )

        df = pd.DataFrame(data)
        df["symbol"] = ticker

        return df

    def list_available_files(self) -> List[Dict[str, Any]]:
        """List available data files in configured data directories."""
        files = []
        seen_paths = set()

        for base_dir in self.data_dirs:
            if not base_dir.exists():
                continue

            for ext in ["*.csv", "*.parquet", "*.parq"]:
                for filepath in base_dir.glob(ext):
                    resolved = str(filepath.resolve())
                    if resolved in seen_paths:
                        continue
                    seen_paths.add(resolved)
                    stat = filepath.stat()
                    files.append(
                        {
                            "name": filepath.name,
                            "path": resolved,
                            "size_mb": round(stat.st_size / 1024 / 1024, 2),
                            "modified": datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                        }
                    )

        return sorted(files, key=lambda x: x["name"])
