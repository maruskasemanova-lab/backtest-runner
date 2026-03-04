from typing import Any, Dict, Tuple

from fastapi import HTTPException

from src.runtime_mode import (
    stateful_run_api_supported,
    stateful_run_api_unsupported_detail,
)


class RunRegistry:
    """Thin abstraction over active run registry with consistent errors."""

    def __init__(self, active_runners: Dict[str, Any]):
        self._active_runners = active_runners

    @staticmethod
    def build_key(run_id: str, ticker: str, date: str) -> str:
        return f"{run_id}:{ticker}:{date}"

    def require(self, run_id: str, ticker: str, date: str) -> Tuple[str, Any]:
        run_key = self.build_key(run_id, ticker, date)
        runner = self._active_runners.get(run_key)
        if runner is None:
            if not stateful_run_api_supported():
                raise HTTPException(503, stateful_run_api_unsupported_detail())
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "RUN_NOT_FOUND",
                    "message": f"Run not found: {run_key}",
                    "hint": "May have been flushed to DB. Use DB-backed endpoints for completed runs."
                }
            )
        return run_key, runner
