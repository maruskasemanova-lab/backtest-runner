from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

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


@router.get("/api/l2/icebergs/{ticker}")
async def get_icebergs(
    ticker: str,
    start_time: str,
    end_time: str,
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
    return services.l2_manager.detect_icebergs(ticker, start_dt, end_dt)
