"""
TCBBO Options Flow Analyzer API routes.

Endpoints:
  GET  /api/tcbbo/files                – List available TCBBO parquet files
  POST /api/tcbbo/analyze              – Run full pipeline, return summary
  GET  /api/tcbbo/sweeps               – Get whale sweep detections
  GET  /api/tcbbo/flow                 – Get minute-level flow bars (Options CVD)
  GET  /api/tcbbo/flow/daily-summary   – Get per-day aggregated flow summary
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.routes.context import ApiServices, get_api_services
from src.tcbbo_analyzer import (
    AnalysisResult,
    FlowBar,
    SweepCluster,
    TCBBOAnalyzer,
    find_tcbbo_files,
)

logger = logging.getLogger("tcbbo_routes")
router = APIRouter()

# Module-level cache: keyed by (file_path, date_filter)
_analysis_cache: Dict[tuple, Dict[str, Any]] = {}

# Shared analyzer instance
_analyzer = TCBBOAnalyzer()


class AnalyzeRequest(BaseModel):
    file: str
    date: Optional[str] = None
    sweep_window_ms: int = 1000
    sweep_min_premium_usd: float = 50_000.0
    flow_bar_freq: str = "1min"


def _get_or_run_analysis(req: AnalyzeRequest) -> Dict[str, Any]:
    """Run analysis or return cached result."""
    cache_key = (req.file, req.date)

    if cache_key in _analysis_cache:
        cached = _analysis_cache[cache_key]
        # Check if parameters match
        if (
            cached.get("_params", {}).get("sweep_window_ms") == req.sweep_window_ms
            and cached.get("_params", {}).get("sweep_min_premium_usd")
            == req.sweep_min_premium_usd
            and cached.get("_params", {}).get("flow_bar_freq") == req.flow_bar_freq
        ):
            return cached

    analyzer = TCBBOAnalyzer(
        sweep_window_ms=req.sweep_window_ms,
        sweep_min_premium_usd=req.sweep_min_premium_usd,
        flow_bar_freq=req.flow_bar_freq,
    )

    summary, sweeps, flow_bars, _df = analyzer.analyze(req.file, date_filter=req.date)

    result = {
        "summary": asdict(summary),
        "sweeps": [asdict(s) for s in sweeps],
        "flow_bars": [asdict(b) for b in flow_bars],
        "_params": {
            "sweep_window_ms": req.sweep_window_ms,
            "sweep_min_premium_usd": req.sweep_min_premium_usd,
            "flow_bar_freq": req.flow_bar_freq,
        },
    }
    _analysis_cache[cache_key] = result
    return result


# -----------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------


@router.get("/api/tcbbo/files")
async def list_tcbbo_files(
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    services: ApiServices = Depends(get_api_services),
):
    """List available TCBBO parquet files in data directory."""
    files = find_tcbbo_files(data_dir="data", ticker=ticker)
    return {"files": files}


@router.post("/api/tcbbo/analyze")
async def analyze_tcbbo(
    request: AnalyzeRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Run full 5-phase TCBBO analysis pipeline. Returns summary."""
    try:
        result = _get_or_run_analysis(request)
        return {
            "summary": result["summary"],
            "sweep_count": len(result["sweeps"]),
            "flow_bar_count": len(result["flow_bars"]),
        }
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.exception("TCBBO analysis failed")
        raise HTTPException(500, f"Analysis failed: {exc}")


@router.post("/api/tcbbo/sweeps")
async def get_sweeps(
    request: AnalyzeRequest,
    limit: int = Query(100, ge=1, le=5000),
    min_premium: float = Query(0, ge=0),
    sentiment: Optional[Literal["bullish", "bearish", "mixed"]] = Query(None),
    sort_by: Literal["premium", "time", "contracts"] = Query("premium"),
    services: ApiServices = Depends(get_api_services),
):
    """Get detected whale sweeps from TCBBO analysis."""
    try:
        result = _get_or_run_analysis(request)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.exception("TCBBO sweep detection failed")
        raise HTTPException(500, f"Analysis failed: {exc}")

    sweeps = result["sweeps"]

    # Filter
    if min_premium > 0:
        sweeps = [s for s in sweeps if s["total_premium_usd"] >= min_premium]
    if sentiment:
        sweeps = [s for s in sweeps if s["sentiment"] == sentiment]

    # Sort
    if sort_by == "premium":
        sweeps.sort(key=lambda s: s["total_premium_usd"], reverse=True)
    elif sort_by == "time":
        sweeps.sort(key=lambda s: s["start_time"])
    elif sort_by == "contracts":
        sweeps.sort(key=lambda s: s["total_contracts"], reverse=True)

    return {
        "total": len(sweeps),
        "sweeps": sweeps[:limit],
    }


@router.post("/api/tcbbo/flow")
async def get_flow_bars(
    request: AnalyzeRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Get minute-level options flow bars (Options CVD timeseries)."""
    try:
        result = _get_or_run_analysis(request)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.exception("TCBBO flow computation failed")
        raise HTTPException(500, f"Analysis failed: {exc}")

    return {
        "flow_bar_freq": request.flow_bar_freq,
        "bar_count": len(result["flow_bars"]),
        "bars": result["flow_bars"],
    }


@router.post("/api/tcbbo/flow/daily-summary")
async def get_daily_summary(
    request: AnalyzeRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Get per-day aggregated flow summary."""
    try:
        result = _get_or_run_analysis(request)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.exception("TCBBO daily summary failed")
        raise HTTPException(500, f"Analysis failed: {exc}")

    bars = result["flow_bars"]
    if not bars:
        return {"days": []}

    # Aggregate by date
    from collections import defaultdict

    daily: Dict[str, Dict[str, Any]] = {}
    for b in bars:
        day = b["timestamp"][:10]
        if day not in daily:
            daily[day] = {
                "date": day,
                "call_premium_buy": 0.0,
                "call_premium_sell": 0.0,
                "put_premium_buy": 0.0,
                "put_premium_sell": 0.0,
                "net_premium": 0.0,
                "trade_count": 0,
                "contract_volume": 0,
                "sweep_count": 0,
            }
        d = daily[day]
        d["call_premium_buy"] += b["call_premium_buy"]
        d["call_premium_sell"] += b["call_premium_sell"]
        d["put_premium_buy"] += b["put_premium_buy"]
        d["put_premium_sell"] += b["put_premium_sell"]
        d["net_premium"] += b["net_premium"]
        d["trade_count"] += b["trade_count"]
        d["contract_volume"] += b["contract_volume"]
        d["sweep_count"] += b["sweep_count"]

    # Round and compute totals
    for d in daily.values():
        for k in [
            "call_premium_buy",
            "call_premium_sell",
            "put_premium_buy",
            "put_premium_sell",
            "net_premium",
        ]:
            d[k] = round(d[k], 2)
        d["total_bullish"] = round(d["call_premium_buy"] + d["put_premium_sell"], 2)
        d["total_bearish"] = round(d["put_premium_buy"] + d["call_premium_sell"], 2)

    days = sorted(daily.values(), key=lambda x: x["date"])
    return {"days": days}


@router.post("/api/tcbbo/cache/clear")
async def clear_cache(
    services: ApiServices = Depends(get_api_services),
):
    """Clear the in-memory analysis cache."""
    count = len(_analysis_cache)
    _analysis_cache.clear()
    return {"cleared": count}
