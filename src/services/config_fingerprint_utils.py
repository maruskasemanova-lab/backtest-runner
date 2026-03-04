"""Compute a stable fingerprint for a resolved execution config.

The fingerprint captures the *effective trading parameters* so that
diagnostics calendar results can be grouped by config version.  When
the ticker JSON (e.g. MU.json) is updated, the fingerprint changes
automatically, and old results no longer mix with new ones.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Set

# Keys whose values may change between runs without representing a
# meaningful config difference (provenance metadata, source labels, etc.).
_IGNORED_SUFFIXES: tuple[str, ...] = (
    "_source",
    "_source_runtime",
)

_IGNORED_KEYS: Set[str] = {
    "requested_l2_only",
    "requested_l2_confirm",
    "positioning_cfg_requested",
    "positioning_cfg",
    "liquidity_sweep_l2_auto_source",
}


def _strip_volatile(obj: Any) -> Any:
    """Recursively remove volatile / provenance-only keys."""
    if isinstance(obj, dict):
        return {
            k: _strip_volatile(v)
            for k, v in obj.items()
            if k not in _IGNORED_KEYS
            and not any(k.endswith(s) for s in _IGNORED_SUFFIXES)
        }
    if isinstance(obj, (list, tuple)):
        return [_strip_volatile(item) for item in obj]
    return obj


def compute_config_fingerprint(execution_config: Dict[str, Any]) -> str:
    """Return a short, stable fingerprint for the given execution config.

    The fingerprint is a ``cfg_`` prefixed 12-hex-char SHA-256 digest of the
    *effective* trading parameters (volatile/source metadata stripped).

    >>> compute_config_fingerprint({"trading_config": {"a": 1}})
    'cfg_...'
    """
    cleaned = _strip_volatile(execution_config)
    canonical = json.dumps(cleaned, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"cfg_{digest}"
