from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict

from fastapi import Request
from fastapi.exceptions import HTTPException


@dataclass
class ApiServices:
    """Runtime services exposed to route modules via FastAPI dependency injection."""

    data_loader: Any
    l2_manager: Any
    l2_features: Any
    active_runners: Dict[str, Any]
    databento_svc: Any
    logger: Any
    get_live_trader_artifacts_dir: Callable[[], Any]
    live_run_active_window_seconds: int
    load_strategy_overrides: Callable[[], Dict[str, Any]]
    build_strategy_combo_options_payload: Callable[[str], Dict[str, Any]]
    load_aos_config: Callable[[], Dict[str, Any]]
    load_positioning_config: Callable[[], Dict[str, Any]]
    merge_positioning_into_aos_snapshot: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
    get_ticker_positioning_config: Callable[[str], Dict[str, Any]]
    positioning_config_keys: Any
    build_adaptive_tuner_options_payload: Callable[[str], Dict[str, Any]]
    build_config_write_deps: Callable[[], Any]
    build_run_control_deps: Callable[[], Any]
    build_adaptive_tuner_deps: Callable[[], Any]
    start_run: Callable[[Any], Awaitable[Any]]
    broadcast: Callable[[Dict[str, Any]], Awaitable[None]]
    refresh_runtime_data_services: Callable[[], None]
    reset_discovery: Callable[[], None]


def get_api_services(request: Request) -> ApiServices:
    services = getattr(request.app.state, "api_services", None)
    if isinstance(services, ApiServices):
        return services
    raise HTTPException(status_code=500, detail="API services are not initialized")
