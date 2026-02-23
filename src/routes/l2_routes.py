from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from src.routes.context import ApiServices, get_api_services

router = APIRouter()


@router.get("/api/l2/footprint/{ticker}")
async def get_footprint_data(
    ticker: str,
    start_time: str,
    end_time: str,
    timeframe: str = "1min",
    services: ApiServices = Depends(get_api_services),
):
    """Get L2 Footprint data for a specific time range."""
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "Invalid timestamp format. Use ISO 8601.")

    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    services.l2_manager.load_data(ticker, start_date, end_date)
    bars = services.l2_manager.get_footprint_bars(ticker, start_dt, end_dt, timeframe)
    return {"ticker": ticker, "timeframe": timeframe, "bars": bars}


def _iceberg_epoch_seconds(row: Any) -> float:
    if not isinstance(row, dict):
        return 0.0
    raw_time = row.get("time")
    if isinstance(raw_time, (int, float)):
        return float(raw_time)
    if isinstance(raw_time, str):
        try:
            parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            return float(parsed.timestamp())
        except ValueError:
            return 0.0
    raw_timestamp = row.get("timestamp")
    if isinstance(raw_timestamp, str):
        try:
            parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            return float(parsed.timestamp())
        except ValueError:
            return 0.0
    return 0.0


@router.get("/api/l2/icebergs/{ticker}")
async def get_icebergs(
    ticker: str,
    start_time: str,
    end_time: str,
    limit: int = Query(default=400, ge=0, le=5000),
    min_hidden_size: int = Query(default=0, ge=0, le=1_000_000),
    min_trade_size: int = Query(default=0, ge=0, le=1_000_000),
    sort: Literal["time", "hidden_size", "trade_size"] = "time",
    services: ApiServices = Depends(get_api_services),
):
    """Get detected iceberg orders for a specific time range."""
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "Invalid timestamp format. Use ISO 8601.")

    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    services.l2_manager.load_data(ticker, start_date, end_date)
    raw_rows = services.l2_manager.detect_icebergs(ticker, start_dt, end_dt)
    rows = raw_rows if isinstance(raw_rows, list) else []

    filtered = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        trade_size = int(max(0, float(row.get("trade_size", 0) or 0)))
        hidden_size = int(max(0, float(row.get("hidden_size", 0) or 0)))
        if trade_size < min_trade_size or hidden_size < min_hidden_size:
            continue
        normalized = dict(row)
        normalized["trade_size"] = trade_size
        normalized["hidden_size"] = hidden_size
        filtered.append(normalized)

    if sort == "hidden_size":
        filtered.sort(
            key=lambda row: (
                int(row.get("hidden_size", 0) or 0),
                _iceberg_epoch_seconds(row),
            ),
            reverse=True,
        )
    elif sort == "trade_size":
        filtered.sort(
            key=lambda row: (
                int(row.get("trade_size", 0) or 0),
                _iceberg_epoch_seconds(row),
            ),
            reverse=True,
        )
    else:
        filtered.sort(key=_iceberg_epoch_seconds)

    if limit > 0 and len(filtered) > limit:
        if sort == "time":
            filtered = filtered[-limit:]
        else:
            filtered = filtered[:limit]

    if sort != "time":
        # Keep client timeline stable regardless of ranking mode used for truncation.
        filtered.sort(key=_iceberg_epoch_seconds)
    return filtered
