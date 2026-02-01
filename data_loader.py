"""
Data Loader - Loads trading day data from various sources.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple
import os


class DataLoader:
    """Loads and prepares trading day data for the backtest runner."""
    
    # Default data directory
    DEFAULT_DATA_DIR = "/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/databento_data"
    
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path(self.DEFAULT_DATA_DIR)
    
    def load_csv(self, filename: str) -> pd.DataFrame:
        """Load data from CSV file."""
        # Handle both relative and absolute paths
        if os.path.isabs(filename):
            filepath = Path(filename)
        else:
            filepath = self.data_dir / filename
            
        if not filepath.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")
        
        # Read without parse_dates since column names vary
        df = pd.read_csv(filepath)
        return self._prepare_dataframe(df)
    
    def load_parquet(self, filename: str) -> pd.DataFrame:
        """Load data from Parquet file."""
        if os.path.isabs(filename):
            filepath = Path(filename)
        else:
            filepath = self.data_dir / filename
            
        if not filepath.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")
        
        df = pd.read_parquet(filepath)
        return self._prepare_dataframe(df)
    
    def _prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare dataframe with required columns."""
        # Find and normalize timestamp column
        timestamp_cols = ['timestamp', 'ts_event', 'time', 'datetime', 'date']
        
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
        
        # Filter by date
        mask = df['timestamp'].dt.date == target_date
        day_df = df[mask].copy()
        
        if include_premarket:
            # Include data from premarket start
            time_mask = day_df['timestamp'].dt.time >= premarket_start
        else:
            # Only regular hours
            time_mask = (
                (day_df['timestamp'].dt.time >= market_open) & 
                (day_df['timestamp'].dt.time <= market_close)
            )
        
        return day_df[time_mask].reset_index(drop=True)
    
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
        """List available data files in the data directory."""
        files = []
        
        if not self.data_dir.exists():
            return files
        
        for ext in ['*.csv', '*.parquet', '*.parq']:
            for filepath in self.data_dir.glob(ext):
                stat = filepath.stat()
                files.append({
                    'name': filepath.name,
                    'path': str(filepath),
                    'size_mb': round(stat.st_size / 1024 / 1024, 2),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        
        return sorted(files, key=lambda x: x['name'])
