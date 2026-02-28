from datetime import date, datetime
from typing import Any, Callable, Dict

from pydantic import ValidationError

from src.services.session_runner_models import Err, Ok, Result, StrategyBarPayload


ValidateStrategyBarPayload = Callable[[Dict[str, Any]], Result[Dict[str, Any], str]]


class StrategyBarPayloadValidator:
    @staticmethod
    def _to_json_compatible(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): StrategyBarPayloadValidator._to_json_compatible(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [StrategyBarPayloadValidator._to_json_compatible(item) for item in value]

        # Handle numpy scalars/arrays and other array-like types without importing numpy.
        item_attr = getattr(value, "item", None)
        if callable(item_attr):
            try:
                return StrategyBarPayloadValidator._to_json_compatible(item_attr())
            except Exception:
                pass
        tolist_attr = getattr(value, "tolist", None)
        if callable(tolist_attr):
            try:
                return StrategyBarPayloadValidator._to_json_compatible(tolist_attr())
            except Exception:
                pass

        return str(value)

    def validate(self, payload: Dict[str, Any]) -> Result[Dict[str, Any], str]:
        try:
            model = StrategyBarPayload.model_validate(payload)
        except ValidationError as exc:
            return Err(str(exc))
        normalized = self._to_json_compatible(
            model.model_dump(mode="python", exclude_none=True)
        )
        return Ok(normalized)
