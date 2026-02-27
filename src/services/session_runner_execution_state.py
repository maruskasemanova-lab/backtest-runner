from dataclasses import dataclass
from typing import Any, Dict

from src.services.session_runner_models import ExecutionLifecycle


@dataclass
class ExecutionStateManager:
    lifecycle: ExecutionLifecycle = ExecutionLifecycle.INITIALIZED
    position_active: bool = False
    pending_entry: bool = False

    def reset_flat(self) -> None:
        self.lifecycle = ExecutionLifecycle.FLAT
        self.position_active = False
        self.pending_entry = False

    def consume_pending_entry(self) -> bool:
        consumed = bool(self.pending_entry)
        if consumed:
            self.pending_entry = False
        return consumed

    def apply_response(self, response: Dict[str, Any]) -> None:
        action = str(response.get("action", "") or "")
        opened = "position_opened" in response
        closed = (
            "position_closed" in response
            or action.startswith("position_closed_")
            or action == "max_loss_stop"
            or action == "session_ended"
        )

        if response.get("phase") == "END_OF_DAY":
            self.lifecycle = ExecutionLifecycle.END_OF_DAY
            self.position_active = False
            self.pending_entry = False
            return

        if opened:
            self.lifecycle = ExecutionLifecycle.IN_POSITION
            self.position_active = True
            self.pending_entry = False
            return

        if closed:
            self.lifecycle = ExecutionLifecycle.FLAT
            self.position_active = False
            self.pending_entry = False
            return

        match action:
            case "signal_queued":
                self.lifecycle = ExecutionLifecycle.PENDING_ENTRY
                self.pending_entry = True
                self.position_active = False
            case _:
                if bool(response.get("queued_for_next_bar")):
                    self.lifecycle = ExecutionLifecycle.PENDING_ENTRY
                    self.pending_entry = True
                    self.position_active = False
