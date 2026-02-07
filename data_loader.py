"""
Data Loader - Loads trading day data from various sources.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo
import os

from src.system_settings import DEFAULT_EXTERNAL_DATA_DIR, SystemSettings


class DataLoader:
    """Loads and prepares trading day data for the backtest runner."""
    
    # Default data directory
    DEFAULT_DATA_DIR = str(DEFAULT_EXTERNAL_DATA_DIR)
    PROJECT_ROOT = Path(__file__).resolve().parent
    
    def __init__(self, data_dir: Optional[str] = None, data_dirs: Optional[List[str]] = None):
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
    
    def load_parquet(self, filename: str) -> pd.DataFrame:
        """Load data from Parquet file."""
        filepath = self._resolve_file_path(filename)
        
        df = pd.read_parquet(filepath)
        return self._prepare_dataframe(df)
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare dataframe with required columns."""
        # Find and normalize timestamp column
        timestamp_cols = ['timestamp', 'ts_event', 'ts_recv', 'time', 'datetime', 'date']
        
        for col in timestamp_cols:
            if col in df.columns:
                df['timestamp'] = pd.to_datetime(df[col])
                break
        else:
            raise ValueError(f"No timestamp column found. Available: {list(df.columns)}")
        
        # Ensure OHLCV columns
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                # Try to find alternative names
                alt_names = {
                    'open': ['Open', 'OPEN', 'o'],
                    'high': ['High', 'HIGH', 'h'],
                    'low': ['Low', 'LOW', 'l'],
                    'close': ['Close', 'CLOSE', 'c'],
                    'volume': ['Volume', 'VOLUME', 'v', 'vol']
                }
                for alt in alt_names.get(col, []):
                    if alt in df.columns:
                        df[col] = df[alt]
                        break
                else:
                    raise ValueError(f"Required column '{col}' not found in data")
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        return df
    
    def filter_trading_day(
        self, 
        df: pd.DataFrame, 
        date: str,
        include_premarket: bool = True,
        premarket_start: time = time(4, 0),
        market_open: time = time(9, 30),
        market_close: time = time(16, 0)
    ) -> pd.DataFrame:
        """Filter data to a specific trading day."""
        target_date = pd.to_datetime(date).date()
        market_ts = self._market_timestamp_series(df)

        # Filter by market date (ET)
        date_mask = market_ts.dt.date == target_date

        if include_premarket:
            time_mask = (
                (market_ts.dt.time >= premarket_start) &
                (market_ts.dt.time <= market_close)
            )
        else:
            time_mask = (
                (market_ts.dt.time >= market_open) & 
                (market_ts.dt.time <= market_close)
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
        market_close: time = time(16, 0)
    ) -> pd.DataFrame:
        """Filter data to a date range (inclusive) and session hours."""
        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        market_ts = self._market_timestamp_series(df)

        # Date range filter (inclusive) in ET
        date_mask = (market_ts.dt.date >= start) & (market_ts.dt.date <= end)

        if include_premarket:
            time_mask = (
                (market_ts.dt.time >= premarket_start) &
                (market_ts.dt.time <= market_close)
            )
        else:
            time_mask = (
                (market_ts.dt.time >= market_open) &
                (market_ts.dt.time <= market_close)
            )

        final_mask = date_mask & time_mask
        return df[final_mask].reset_index(drop=True)

    def filter_trading_hours(
        self,
        df: pd.DataFrame,
        hours_et: Optional[List[int]] = None
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
    
    def get_bars_iterator(
        self, 
        df: pd.DataFrame
    ):
        """Yield bars one by one for walk-forward simulation."""
        for idx, row in df.iterrows():
            yield {
                'index': idx,
                'timestamp': row['timestamp'],
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
                'vwap': float(row.get('vwap', 0)) if 'vwap' in row else None
            }
    
    def generate_mock_data(
        self, 
        ticker: str, 
        date: str,
        base_price: float = 150.0,
        volatility: float = 0.02,
        bars_per_day: int = 390  # 1-min bars for regular hours
    ) -> pd.DataFrame:
        """Generate mock trading data for testing."""
        np.random.seed(42)
        
        target_date = pd.to_datetime(date)
        
        # Generate timestamps (9:30 AM to 4:00 PM)
        timestamps = pd.date_range(
            start=target_date.replace(hour=9, minute=30),
            periods=bars_per_day,
            freq='1min'
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
            
            volume = int(np.random.uniform(10000, 100000) * (1 + np.random.uniform(0, 2)))
            
            data.append({
                'timestamp': ts,
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(close, 2),
                'volume': volume,
                'vwap': round((open_price + close + high + low) / 4, 2)
            })
        
        df = pd.DataFrame(data)
        df['symbol'] = ticker
        
        return df
    
    def list_available_files(self) -> List[Dict[str, Any]]:
        """List available data files in configured data directories."""
        files = []
        seen_paths = set()
        
        for base_dir in self.data_dirs:
            if not base_dir.exists():
                continue

            for ext in ['*.csv', '*.parquet', '*.parq']:
                for filepath in base_dir.glob(ext):
                    resolved = str(filepath.resolve())
                    if resolved in seen_paths:
                        continue
                    seen_paths.add(resolved)
                    stat = filepath.stat()
                    files.append({
                        'name': filepath.name,
                        'path': resolved,
                        'size_mb': round(stat.st_size / 1024 / 1024, 2),
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
        
        return sorted(files, key=lambda x: x['name'])
