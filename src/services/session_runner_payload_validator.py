from typing import Any, Callable, Dict

from pydantic import ValidationError

from src.services.session_runner_models import Err, Ok, Result, StrategyBarPayload


ValidateStrategyBarPayload = Callable[[Dict[str, Any]], Result[Dict[str, Any], str]]


class StrategyBarPayloadValidator:
    def validate(self, payload: Dict[str, Any]) -> Result[Dict[str, Any], str]:
        try:
            model = StrategyBarPayload.model_validate(payload)
        except ValidationError as exc:
            return Err(str(exc))
        return Ok(model.model_dump(mode="json", exclude_none=True))
