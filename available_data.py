"""
Data discovery module for scanning available trading data files.
"""
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = "/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/databento_data"


@dataclass
class TickerData:
    """Available data for a single ticker."""
    ticker: str
    files: List[str] = field(default_factory=list)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    available_dates: List[str] = field(default_factory=list)


class DataDiscovery:
    """Scans data directory and returns available tickers and dates."""
    
    # Pattern for parsing filenames like: AAPL_ohlcv-1m_2025-08-01_2026-01-28.csv
    FILENAME_PATTERN = re.compile(
        r'^([A-Z]+)_ohlcv-\d+[mhd]_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.csv$'
    )
    
    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self.data_dir = Path(data_dir)
        self._cache: Optional[Dict[str, TickerData]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Cache for 1 minute
    
    def scan(self, force_refresh: bool = False) -> Dict[str, TickerData]:
        """Scan data directory and return available ticker data."""
        # Check cache
        if not force_refresh and self._cache is not None:
            if self._cache_time and (datetime.now() - self._cache_time).seconds < self._cache_ttl_seconds:
                return self._cache
        
        tickers: Dict[str, TickerData] = {}
        
        if not self.data_dir.exists():
            logger.warning(f"Data directory does not exist: {self.data_dir}")
            return tickers
        
        # Scan CSV files
        for file in self.data_dir.glob("*.csv"):
            match = self.FILENAME_PATTERN.match(file.name)
            if match:
                ticker = match.group(1)
                start_date = match.group(2)
                end_date = match.group(3)
                
                if ticker not in tickers:
                    tickers[ticker] = TickerData(ticker=ticker)
                
                tickers[ticker].files.append(file.name)
                
                # Update date range (take widest range)
                if tickers[ticker].start_date is None or start_date < tickers[ticker].start_date:
                    tickers[ticker].start_date = start_date
                if tickers[ticker].end_date is None or end_date > tickers[ticker].end_date:
                    tickers[ticker].end_date = end_date
        
        # Generate available trading dates for each ticker
        for ticker_data in tickers.values():
            if ticker_data.start_date and ticker_data.end_date:
                ticker_data.available_dates = self._generate_trading_dates(
                    ticker_data.start_date,
                    ticker_data.end_date
                )
        
        # Update cache
        self._cache = tickers
        self._cache_time = datetime.now()
        
        logger.info(f"Discovered {len(tickers)} tickers with data")
        return tickers
    
    def _generate_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """Generate list of trading dates (weekdays only)."""
        from datetime import timedelta
        
        dates = []
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        current = start
        while current <= end and len(dates) < 500:
            # Skip weekends (5=Saturday, 6=Sunday)
            if current.weekday() < 5:
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        
        return dates
    
    def get_tickers(self) -> List[str]:
        """Get list of available tickers."""
        data = self.scan()
        return sorted(data.keys())
    
    def get_date_range(self, ticker: str) -> Dict[str, Optional[str]]:
        """Get available date range for a ticker."""
        data = self.scan()
        if ticker in data:
            return {
                "start": data[ticker].start_date,
                "end": data[ticker].end_date
            }
        return {"start": None, "end": None}
    
    def get_file_for_date(self, ticker: str, date: str) -> Optional[str]:
        """Get the data file that contains data for a specific date."""
        data = self.scan()
        if ticker not in data:
            return None
        
        target_date = datetime.strptime(date, "%Y-%m-%d")
        
        for file in data[ticker].files:
            match = self.FILENAME_PATTERN.match(file)
            if match:
                file_start = datetime.strptime(match.group(2), "%Y-%m-%d")
                file_end = datetime.strptime(match.group(3), "%Y-%m-%d")
                if file_start <= target_date <= file_end:
                    return str(self.data_dir / file)
        
        return None

    def get_files_for_range(self, ticker: str, start_date: str, end_date: str) -> List[str]:
        """Get all data files that overlap a date range (inclusive)."""
        data = self.scan()
        if ticker not in data:
            return []

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        files = []

        for file in data[ticker].files:
            match = self.FILENAME_PATTERN.match(file)
            if not match:
                continue
            file_start = datetime.strptime(match.group(2), "%Y-%m-%d")
            file_end = datetime.strptime(match.group(3), "%Y-%m-%d")
            if file_start <= end and file_end >= start:
                files.append(str(self.data_dir / file))

        return sorted(files)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return all available data as a dictionary for API response."""
        data = self.scan()
        
        return {
            "tickers": sorted(data.keys()),
            "date_ranges": {
                ticker: {
                    "start": td.start_date,
                    "end": td.end_date,
                    "files": td.files
                }
                for ticker, td in data.items()
            },
            "data_dir": str(self.data_dir)
        }


# Singleton instance
_discovery: Optional[DataDiscovery] = None


def get_discovery() -> DataDiscovery:
    """Get or create the data discovery singleton."""
    global _discovery
    if _discovery is None:
        _discovery = DataDiscovery()
    return _discovery
