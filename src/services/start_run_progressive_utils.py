from __future__ import annotations

from typing import Any, Mapping


def is_active_runner(
    *,
    active_runners: Mapping[str, Any],
    run_key: str,
    runner: Any,
) -> bool:
    return active_runners.get(run_key) is runner


def update_progressive_chunk_state(
    *,
    runner: Any,
    chunk_end: str,
    remaining_chunks: int,
) -> None:
    runner._progressive_loading_loaded_until = chunk_end
    runner._progressive_loading_pending_chunks = max(0, int(remaining_chunks))


def finalize_progressive_loading(
    *,
    runner: Any,
    completion_status: str,
    remaining_chunks: int,
    full_range_end: str,
    abort_reason: str | None = None,
) -> None:
    fully_loaded = completion_status == "completed" and remaining_chunks == 0
    runner._progressive_loading_complete = fully_loaded
    runner._progressive_loading_pending_chunks = (
        0 if fully_loaded else max(0, int(remaining_chunks))
    )
    if fully_loaded and not runner._progressive_loading_last_error:
        runner._progressive_loading_loaded_until = full_range_end
    elif abort_reason and not runner._progressive_loading_last_error:
        runner._progressive_loading_last_error = abort_reason


__all__ = [
    "finalize_progressive_loading",
    "is_active_runner",
    "update_progressive_chunk_state",
]

