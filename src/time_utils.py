"""
Time Utilities - Centralized timestamp handling for backtest runner.

This module provides consistent timestamp normalization across all components
to avoid look-ahead bias and ensure timezone consistency.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Tuple, Union

import pandas as pd


def to_utc_datetime(value: Any) -> datetime:
    """
    Convert value to timezone-aware UTC datetime.
    
    Args:
        value: Any timestamp-like value (datetime, str, int, float, pd.Timestamp)
        
    Returns:
        Timezone-aware datetime in UTC
        
    Raises:
        ValueError: If value cannot be converted to datetime
    """
    if value is None:
        raise ValueError("Cannot convert None to datetime")
    
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()
    elif isinstance(value, (int, float)):
        # Assume Unix timestamp
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, str):
        # Try ISO format first
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            # Try pandas parsing
            dt = pd.to_datetime(value).to_pydatetime()
    else:
        dt = pd.to_datetime(value).to_pydatetime()
    
    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    
    return dt


def epoch_minute_key(dt: datetime) -> int:
    """
    Convert datetime to epoch minute key.
    
    Args:
        dt: Timezone-aware datetime
        
    Returns:
        Integer representing minutes since Unix epoch
    """
    utc_dt = to_utc_datetime(dt) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return int(utc_dt.timestamp() // 60)


def epoch_second_key(dt: datetime) -> int:
    """
    Convert datetime to epoch second key.
    
    Args:
        dt: Timezone-aware datetime
        
    Returns:
        Integer representing seconds since Unix epoch
    """
    utc_dt = to_utc_datetime(dt) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return int(utc_dt.timestamp())


def format_iso_utc(dt: datetime) -> str:
    """
    Format datetime as ISO 8601 string in UTC.
    
    Args:
        dt: Timezone-aware datetime
        
    Returns:
        ISO 8601 formatted string with Z suffix
    """
    utc_dt = to_utc_datetime(dt) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso_utc(s: str) -> datetime:
    """
    Parse ISO 8601 string to UTC datetime.
    
    Args:
        s: ISO 8601 formatted string
        
    Returns:
        Timezone-aware datetime in UTC
    """
    return to_utc_datetime(s)


def is_within_window(
    dt: datetime,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
) -> bool:
    """
    Check if datetime is within specified window.
    
    Args:
        dt: Datetime to check
        window_start: Optional start of window (inclusive)
        window_end: Optional end of window (exclusive)
        
    Returns:
        True if dt is within window
    """
    if window_start is not None and dt < window_start:
        return False
    if window_end is not None and dt >= window_end:
        return False
    return True


def normalize_time_window(
    start: Any,
    end: Any,
) -> Tuple[datetime, datetime]:
    """
    Normalize time window to UTC datetimes.
    
    Args:
        start: Start time (any format)
        end: End time (any format)
        
    Returns:
        Tuple of (start_dt, end_dt) in UTC
    """
    start_dt = to_utc_datetime(start)
    end_dt = to_utc_datetime(end)
    return start_dt, end_dt
