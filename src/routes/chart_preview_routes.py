"""Routes for chart preview – raw OHLCV bars without starting a backtest."""

import logging
from datetime import datetime
from typing import Any

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


@router.get("/api/chart-preview/heatmap-daily-cumulative")
async def get_daily_cumulative_price_heatmap(
    ticker: str = Query(..., min_length=1, max_length=10),
    date_from: str = Query(..., min_length=10, max_length=10),
    date_to: str = Query(..., min_length=10, max_length=10),
    bin_size: float = Query(0.5, gt=0),
    services: ApiServices = Depends(get_api_services),
):
    """Return precomputed daily cumulative price heatmap rows from SQLite store."""
    ticker_token = ticker.strip().upper()
    if not ticker_token:
        raise HTTPException(status_code=400, detail="ticker must not be empty")

    try:
        start = datetime.strptime(date_from, "%Y-%m-%d")
        end = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="date_from and date_to must be YYYY-MM-DD"
        )
    if start > end:
        raise HTTPException(status_code=400, detail="date_from must be <= date_to")

    store = getattr(services, "state_store", None)
    list_rows = getattr(store, "list_daily_price_heatmap_rows", None)
    if not callable(list_rows):
        raise HTTPException(
            status_code=503,
            detail="Daily price heatmap store is not configured.",
        )

    try:
        rows = list_rows(
            ticker=ticker_token,
            date_from=date_from,
            date_to=date_to,
            bin_size=float(bin_size),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read daily heatmap rows: {exc}"
        ) from exc

    if not rows:
        return {
            "ticker": ticker_token,
            "date_from": date_from,
            "date_to": date_to,
            "bin_size": float(bin_size),
            "source": "sqlite_daily_price_heatmap_levels",
            "days": [],
            "rows": [],
            "latest_as_of_date": None,
            "latest_summary": None,
            "top_by_time": [],
            "top_by_volume": [],
        }

    day_values = sorted({str(item.get("as_of_date") or "") for item in rows if item.get("as_of_date")})
    day_to_index = {day: idx for idx, day in enumerate(day_values)}
    latest_day = day_values[-1] if day_values else None

    levels: dict[float, dict[str, list[float]]] = {}
    latest_day_rows: list[dict[str, Any]] = []
    for item in rows:
        as_of_date = str(item.get("as_of_date") or "")
        if not as_of_date or as_of_date not in day_to_index:
            continue
        idx = day_to_index[as_of_date]
        level = float(item.get("price_bin") or 0.0)
        slot = levels.setdefault(
            level,
            {
                "cumulative_bars": [0.0] * len(day_values),
                "cumulative_volume": [0.0] * len(day_values),
            },
        )
        slot["cumulative_bars"][idx] = float(item.get("cumulative_bars") or 0.0)
        slot["cumulative_volume"][idx] = float(item.get("cumulative_volume") or 0.0)
        if latest_day and as_of_date == latest_day:
            latest_day_rows.append(item)

    sorted_levels = sorted(levels.keys(), reverse=True)
    payload_rows = [
        {
            "price_bin": float(level),
            "cumulative_bars": [int(round(value)) for value in levels[level]["cumulative_bars"]],
            "cumulative_volume": [round(float(value), 2) for value in levels[level]["cumulative_volume"]],
        }
        for level in sorted_levels
    ]

    latest_total_bars = 0
    latest_total_volume = 0.0
    if latest_day_rows:
        latest_total_bars = int(max(float(item.get("total_bars_to_date") or 0.0) for item in latest_day_rows))
        latest_total_volume = float(
            max(float(item.get("total_volume_to_date") or 0.0) for item in latest_day_rows)
        )

    top_by_time = []
    top_by_volume = []
    if latest_day_rows:
        top_by_time = [
            {
                "price_bin": float(item.get("price_bin") or 0.0),
                "cumulative_bars": int(item.get("cumulative_bars") or 0),
                "share_pct": round(
                    (
                        (float(item.get("cumulative_bars") or 0.0) / latest_total_bars) * 100.0
                        if latest_total_bars > 0
                        else 0.0
                    ),
                    4,
                ),
            }
            for item in sorted(
                latest_day_rows,
                key=lambda row: float(row.get("cumulative_bars") or 0.0),
                reverse=True,
            )[:5]
        ]
        top_by_volume = [
            {
                "price_bin": float(item.get("price_bin") or 0.0),
                "cumulative_volume": round(float(item.get("cumulative_volume") or 0.0), 2),
                "share_pct": round(
                    (
                        (float(item.get("cumulative_volume") or 0.0) / latest_total_volume)
                        * 100.0
                        if latest_total_volume > 0
                        else 0.0
                    ),
                    4,
                ),
            }
            for item in sorted(
                latest_day_rows,
                key=lambda row: float(row.get("cumulative_volume") or 0.0),
                reverse=True,
            )[:5]
        ]

    min_price = float(sorted_levels[-1]) if sorted_levels else None
    max_price = float(sorted_levels[0]) if sorted_levels else None

    return {
        "ticker": ticker_token,
        "date_from": date_from,
        "date_to": date_to,
        "bin_size": float(bin_size),
        "source": "sqlite_daily_price_heatmap_levels",
        "days": day_values,
        "rows": payload_rows,
        "latest_as_of_date": latest_day,
        "latest_summary": {
            "total_bars": int(latest_total_bars),
            "total_volume": round(float(latest_total_volume), 2),
            "min_price_bin": min_price,
            "max_price_bin": max_price,
            "level_count": len(payload_rows),
        }
        if latest_day is not None
        else None,
        "top_by_time": top_by_time,
        "top_by_volume": top_by_volume,
    }
