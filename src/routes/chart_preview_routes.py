"""Routes for chart preview – raw OHLCV bars without starting a backtest."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from src.routes.context import ApiServices, get_api_services

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/chart-preview/bars")
async def get_preview_bars(
    ticker: str = Query(..., min_length=1, max_length=10),
    date_from: str = Query(..., min_length=10, max_length=10),
    date_to: str = Query(..., min_length=10, max_length=10),
    services: ApiServices = Depends(get_api_services),
):
    """Return raw OHLCV bars for a ticker/date range – no session or strategy evaluation."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker must not be empty")

    # Validate date format
    try:
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="date_from and date_to must be YYYY-MM-DD"
        )

    if start > end:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")

    files = services.databento_svc.get_files_for_range(
        ticker=ticker,
        start_date=date_from,
        end_date=date_to,
        schema_prefix="ohlcv-",
    )
    if not files:
        # Manual file drops are not always cataloged yet; rescan once and retry.
        services.databento_svc.scan_existing_files()
        files = services.databento_svc.get_files_for_range(
            ticker=ticker,
            start_date=date_from,
            end_date=date_to,
            schema_prefix="ohlcv-",
        )
    if not files:
        raise HTTPException(
            status_code=404,
            detail=f"No OHLCV data files found for {ticker} in range {date_from}..{date_to}",
        )

    data_loader = services.data_loader
    import pandas as pd

    dfs = []
    for f in files:
        try:
            if f.endswith(".parquet") or f.endswith(".parq"):
                dfs.append(data_loader.load_parquet(f))
            else:
                dfs.append(data_loader.load_csv(f))
        except Exception as exc:
            logger.warning("Failed to load file %s: %s", f, exc)

    if not dfs:
        raise HTTPException(
            status_code=404, detail=f"Could not load any data files for {ticker}"
        )

    df = pd.concat(dfs, ignore_index=True)
    df = (
        df.drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    df = data_loader.filter_trading_range(df, date_from, date_to)

    bars = []
    for bar in data_loader.get_bars_iterator(df):
        ts = bar.get("timestamp")
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        bars.append(
            {
                "timestamp": str(ts),
                "open": bar["open"],
                "high": bar["high"],
                "low": bar["low"],
                "close": bar["close"],
                "volume": bar["volume"],
            }
        )

    return {
        "ticker": ticker,
        "date_from": date_from,
        "date_to": date_to,
        "bar_count": len(bars),
        "bars": bars,
    }
