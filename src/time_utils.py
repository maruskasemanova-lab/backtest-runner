"""
Time Utilities - Centralized timestamp handling for backtest runner.

This module provides consistent timestamp normalization across all components
to avoid look-ahead bias and ensure timezone consistency.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Union

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
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
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
