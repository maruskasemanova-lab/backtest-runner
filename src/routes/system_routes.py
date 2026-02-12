from fastapi import APIRouter, Depends

from src.routes.context import ApiServices, get_api_services

router = APIRouter()


@router.get("/")
async def root(services: ApiServices = Depends(get_api_services)):
    return {
        "name": "Unified Backtest Runner",
        "version": "1.0.0",
        "active_runs": len(services.active_runners),
    }


@router.get("/api/health")
async def health():
    return {"status": "healthy"}


@router.get("/api/available-data")
async def get_available_data(services: ApiServices = Depends(get_api_services)):
    """Get available tickers and date ranges from data files."""
    return services.databento_svc.get_available_data_summary(refresh=False)


@router.get("/api/data/files")
async def list_data_files(services: ApiServices = Depends(get_api_services)):
    """List available data files."""
    return services.data_loader.list_available_files()
