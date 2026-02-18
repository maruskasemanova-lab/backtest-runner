from typing import Any, Dict, Optional

from pydantic import BaseModel


class AdaptiveTunerProfileApplyRequest(BaseModel):
    ticker: str
    profile_id: str


class StrategyComboCaptureRequest(BaseModel):
    ticker: str
    profile_name: Optional[str] = None
    strategy_api_url: str = "http://localhost:8001"
    set_active: bool = True


class StrategyComboApplyRequest(BaseModel):
    ticker: str
    profile_id: str
    strategy_api_url: str = "http://localhost:8001"
    apply_now: bool = True


class UnifiedProfileCaptureRequest(BaseModel):
    ticker: str
    profile_name: Optional[str] = None
    strategy_api_url: str = "http://localhost:8001"
    set_active: bool = True


class UnifiedProfileApplyRequest(BaseModel):
    ticker: str
    profile_id: str
    strategy_api_url: str = "http://localhost:8001"
    apply_now: bool = True
    apply_execution: bool = True


class AOSUpdateRequest(BaseModel):
    ticker: str
    config: Dict[str, Any]


class PositioningUpdateRequest(BaseModel):
    ticker: str
    config: Dict[str, Any]
