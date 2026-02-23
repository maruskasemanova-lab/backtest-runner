"""
Data discovery module for scanning available trading data files.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

from src.system_settings import DEFAULT_EXTERNAL_DATA_DIR, SystemSettings

logger = logging.getLogger(__name__)

# Default data directory
DEFAULT_DATA_DIR = str(DEFAULT_EXTERNAL_DATA_DIR)
LOCAL_DATA_DIR = str(Path(__file__).resolve().parent / "data")


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
        r"^([A-Z]+)_ohlcv-\d+[mhd]_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.(csv|parquet|parq)$"
    )

    def __init__(
        self, data_dir: Optional[str] = None, data_dirs: Optional[List[str]] = None
    ):
        if data_dirs:
            self.data_dirs = [Path(d) for d in data_dirs]
        elif data_dir:
            self.data_dirs = [Path(data_dir)]
        else:
            # Keep a single source of truth for scan roots.
            configured = SystemSettings().get_ohlcv_dirs(existing_only=False)
            self.data_dirs = configured or [
                Path(DEFAULT_DATA_DIR),
                Path(LOCAL_DATA_DIR),
            ]

        # Keep the primary path for backwards compatibility with older API payloads.
        self.data_dir = self.data_dirs[0]
        self._cache: Optional[Dict[str, TickerData]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Cache for 1 minute

    def _parse_filename(self, file_path: Path) -> Optional[Tuple[str, str, str]]:
        match = self.FILENAME_PATTERN.match(file_path.name)
        if not match:
            return None
        return match.group(1), match.group(2), match.group(3)

    def scan(self, force_refresh: bool = False) -> Dict[str, TickerData]:
        """Scan data directory and return available ticker data."""
        # Check cache
        if not force_refresh and self._cache is not None:
            if (
                self._cache_time
                and (datetime.now() - self._cache_time).total_seconds()
                < self._cache_ttl_seconds
            ):
                return self._cache

        tickers: Dict[str, TickerData] = {}

        for data_dir in self.data_dirs:
            if not data_dir.exists():
                logger.warning(f"Data directory does not exist: {data_dir}")
                continue

            for ext in ("*.csv", "*.parquet", "*.parq"):
                for file in data_dir.glob(ext):
                    parsed = self._parse_filename(file)
                    if not parsed:
                        continue

                    ticker, start_date, end_date = parsed
                    if ticker not in tickers:
                        tickers[ticker] = TickerData(ticker=ticker)

                    file_abs = str(file.resolve())
                    if file_abs not in tickers[ticker].files:
                        tickers[ticker].files.append(file_abs)

                    # Update date range (take widest range)
                    if (
                        tickers[ticker].start_date is None
                        or start_date < tickers[ticker].start_date
                    ):
                        tickers[ticker].start_date = start_date
                    if (
                        tickers[ticker].end_date is None
                        or end_date > tickers[ticker].end_date
                    ):
                        tickers[ticker].end_date = end_date

        # Generate available trading dates for each ticker
        for ticker_data in tickers.values():
            if ticker_data.start_date and ticker_data.end_date:
                ticker_data.available_dates = self._generate_trading_dates(
                    ticker_data.start_date, ticker_data.end_date
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
            return {"start": data[ticker].start_date, "end": data[ticker].end_date}
        return {"start": None, "end": None}

    def get_file_for_date(self, ticker: str, date: str) -> Optional[str]:
        """Get the data file that contains data for a specific date."""
        data = self.scan()
        if ticker not in data:
            return None

        target_date = datetime.strptime(date, "%Y-%m-%d")

        candidates: List[Tuple[int, datetime, str]] = []
        for file in data[ticker].files:
            parsed = self._parse_filename(Path(file))
            if not parsed:
                continue
            _, start_str, end_str = parsed
            file_start = datetime.strptime(start_str, "%Y-%m-%d")
            file_end = datetime.strptime(end_str, "%Y-%m-%d")
            if file_start <= target_date <= file_end:
                span_days = (file_end - file_start).days
                candidates.append((span_days, file_end, file))

        if candidates:
            # Prefer the narrowest covering file; if tied use newest end date.
            candidates.sort(key=lambda x: (x[0], -x[1].toordinal()))
            return candidates[0][2]

        return None

    def get_files_for_range(
        self, ticker: str, start_date: str, end_date: str
    ) -> List[str]:
        """Get all data files that overlap a date range (inclusive)."""
        data = self.scan()
        if ticker not in data:
            return []

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        files = []

        for file in data[ticker].files:
            parsed = self._parse_filename(Path(file))
            if not parsed:
                continue
            _, start_str, end_str = parsed
            file_start = datetime.strptime(start_str, "%Y-%m-%d")
            file_end = datetime.strptime(end_str, "%Y-%m-%d")
            if file_start <= end and file_end >= start:
                files.append(file)

        return sorted(set(files))


# Singleton instance
_discovery: Optional[DataDiscovery] = None


def get_discovery() -> DataDiscovery:
    """Get or create the data discovery singleton."""
    global _discovery
    if _discovery is None:
        _discovery = DataDiscovery()
    return _discovery


def reset_discovery() -> None:
    """Clear singleton so future calls re-read current system settings."""
    global _discovery
    _discovery = None
