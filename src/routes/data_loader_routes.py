import asyncio
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.routes.context import ApiServices, get_api_services

router = APIRouter()


class DownloadRequest(BaseModel):
    ticker: str
    data_schema: str = "mbp-10"
    start_date: str
    end_date: str
    dataset: str = "XNAS.ITCH"
    convert_to_parquet: bool = True


class CostEstimateRequest(BaseModel):
    ticker: str
    data_schema: str = "mbp-10"
    start_date: str
    end_date: str
    dataset: str = "XNAS.ITCH"


class DeleteDataRequest(BaseModel):
    ticker: str
    data_schema: str
    start_date: str
    end_date: str


class DataSettingsRequest(BaseModel):
    ohlcv_data_dirs: Optional[List[str]] = None
    l2_data_dirs: Optional[List[str]] = None


class DatabentoApiKeyRequest(BaseModel):
    api_key: str


@router.get("/api/data-loader/catalog")
async def get_data_catalog(
    refresh: bool = False,
    ticker: Optional[str] = None,
    schema: Optional[str] = None,
    file_format: Optional[str] = None,
    source: Optional[str] = None,
    managed: Optional[bool] = None,
    services: ApiServices = Depends(get_api_services),
):
    """List unified data catalog entries with optional filters."""
    return services.databento_svc.list_catalog(
        refresh=refresh,
        ticker=ticker,
        schema=schema,
        file_format=file_format,
        source=source,
        managed=managed,
    )


@router.get("/api/data-loader/catalog/{ticker}")
async def get_ticker_catalog(
    ticker: str,
    services: ApiServices = Depends(get_api_services),
):
    """List catalog data for a specific ticker."""
    return services.databento_svc.list_catalog(ticker=ticker.upper())


@router.get("/api/data-loader/settings")
async def get_data_loader_settings(services: ApiServices = Depends(get_api_services)):
    """Read centralized data manager settings."""
    return services.databento_svc.get_settings()


@router.put("/api/data-loader/settings")
async def update_data_loader_settings(
    request: DataSettingsRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Update OHLCV/L2 data roots used by catalog discovery."""
    try:
        settings = services.databento_svc.update_data_dirs(
            ohlcv_data_dirs=request.ohlcv_data_dirs,
            l2_data_dirs=request.l2_data_dirs,
        )
        services.refresh_runtime_data_services()
        services.reset_discovery()
        return settings
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))


@router.put("/api/data-loader/api-key")
async def set_databento_api_key(
    request: DatabentoApiKeyRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Set Databento API key for this system (persisted in settings)."""
    try:
        settings = services.databento_svc.set_api_key(request.api_key)
        return {"status": "ok", **settings}
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))


@router.get("/api/data-loader/schemas")
async def get_supported_schemas(services: ApiServices = Depends(get_api_services)):
    """List supported Databento schemas."""
    return services.databento_svc.get_schemas()


@router.post("/api/data-loader/cost-estimate")
async def get_cost_estimate(
    request: CostEstimateRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Get Databento cost estimate before downloading."""
    try:
        return services.databento_svc.get_cost_estimate(
            ticker=request.ticker.upper(),
            schema=request.data_schema,
            start=request.start_date,
            end=request.end_date,
            dataset=request.dataset,
        )
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"Cost estimate failed: {exc}")


@router.post("/api/data-loader/download")
async def start_download(
    request: DownloadRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Start a data download from Databento (runs in background)."""
    ticker = request.ticker.upper()

    try:
        coverage = services.databento_svc.get_range_coverage(
            ticker=ticker,
            schema=request.data_schema,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(400, f"Invalid date range: {exc}")

    if coverage.get("fully_covered"):
        return {"status": "already_exists", "coverage": coverage}

    async def _broadcast(msg: Dict[str, Any]) -> None:
        await services.broadcast(msg)

    async def _do_download() -> None:
        try:
            entry = await services.databento_svc.download(
                ticker=ticker,
                schema=request.data_schema,
                start_date=request.start_date,
                end_date=request.end_date,
                dataset=request.dataset,
                convert_to_parquet=request.convert_to_parquet,
                broadcast_fn=_broadcast,
            )
            services.logger.info(
                "Download complete: %s %s -> %s",
                ticker,
                request.data_schema,
                entry.status,
            )
        except Exception as exc:
            services.logger.error("Download failed: %s", exc)

    asyncio.create_task(_do_download())
    return {
        "status": "started",
        "ticker": ticker,
        "schema": request.data_schema,
        "days_total": coverage.get("total_days", 0),
        "days_to_download": len(coverage.get("missing_days", [])),
        "days_already_covered": len(coverage.get("covered_days", [])),
    }


@router.get("/api/data-loader/downloads/active")
async def get_active_downloads(services: ApiServices = Depends(get_api_services)):
    """Get list of currently downloading jobs."""
    return services.databento_svc.get_active_downloads()


@router.delete("/api/data-loader/entry")
async def delete_data_entry(
    request: DeleteDataRequest,
    services: ApiServices = Depends(get_api_services),
):
    """Delete a downloaded data entry and its files."""
    existing = services.databento_svc.catalog.find(
        request.ticker.upper(),
        request.data_schema,
        request.start_date,
        request.end_date,
    )
    if not existing:
        raise HTTPException(404, "Entry not found")
    if not bool(existing.get("managed", True)):
        raise HTTPException(
            403,
            "Refusing to delete unmanaged/external entry. Remove file manually if needed.",
        )
    success = services.databento_svc.delete_entry(
        request.ticker.upper(),
        request.data_schema,
        request.start_date,
        request.end_date,
    )
    if not success:
        raise HTTPException(500, "Delete failed")
    return {"status": "deleted"}


@router.post("/api/data-loader/scan")
async def scan_existing_data(services: ApiServices = Depends(get_api_services)):
    """Scan data directories and register untracked files."""
    entries = services.databento_svc.scan_existing_files()
    return {"scanned": len(entries), "entries": [asdict(e) for e in entries]}
