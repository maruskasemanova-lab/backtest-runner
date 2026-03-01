from __future__ import annotations

import numpy as np
from fastapi.encoders import jsonable_encoder

from src.services.start_run_service import _to_json_compatible


def test_to_json_compatible_handles_numpy_datetime64_and_arrays() -> None:
    payload = {
        "timestamp": np.datetime64("2026-02-13T14:31:00"),
        "close": np.float64(101.25),
        "sizes": np.array([1, 2, 3], dtype=np.int64),
        "nested": {"day": np.datetime64("2026-02-13")},
    }

    normalized = _to_json_compatible(payload)

    assert normalized["timestamp"].startswith("2026-02-13T14:31:00")
    assert normalized["close"] == 101.25
    assert normalized["sizes"] == [1, 2, 3]
    assert normalized["nested"]["day"] == "2026-02-13"

    encoded = jsonable_encoder(normalized)
    assert encoded["nested"]["day"] == "2026-02-13"
