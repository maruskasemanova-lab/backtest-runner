from __future__ import annotations

import gzip
import hashlib
import json
from typing import Any, Dict, Mapping, Optional, Tuple


def json_dumps_compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def decode_json_object(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def row_to_job_payload(row: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(row)
    payload["payload"] = decode_json_object(payload.pop("payload_json", None))
    payload["result"] = decode_json_object(payload.pop("result_json", None))
    return payload


def row_to_adaptive_profile_payload(row: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(row)
    payload["candidate"] = decode_json_object(payload.pop("candidate_json", None))
    payload["metadata"] = decode_json_object(payload.pop("metadata_json", None))
    payload["adaptive_version"] = max(1, int(payload.get("adaptive_version") or 1))
    payload["scope"] = str(payload.get("scope") or "user").strip().lower()
    return payload


def build_diagnostic_payload_blob(payload: Any) -> Tuple[bytes, str, int, int]:
    serialized = json_dumps_compact(
        payload if isinstance(payload, dict) else {}
    ).encode("utf-8")
    compressed = gzip.compress(serialized, compresslevel=6)
    checksum = hashlib.sha256(serialized).hexdigest()
    return compressed, checksum, int(len(serialized)), int(len(compressed))


def decode_diagnostic_payload_blob(raw_blob: Any) -> Optional[Dict[str, Any]]:
    if raw_blob is None:
        return None
    try:
        compressed = bytes(raw_blob)
        decoded = gzip.decompress(compressed).decode("utf-8")
    except Exception:
        return None
    parsed = decode_json_object(decoded)
    return parsed if isinstance(parsed, dict) else None
