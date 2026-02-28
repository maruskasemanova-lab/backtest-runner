from __future__ import annotations

from src.services.saas_payload_utils import (
    build_diagnostic_payload_blob,
    decode_diagnostic_payload_blob,
    decode_json_object,
    json_dumps_compact,
    row_to_adaptive_profile_payload,
    row_to_job_payload,
)


def test_json_dumps_compact_is_stable_and_sorted() -> None:
    serialized = json_dumps_compact({"b": 2, "a": 1})
    assert serialized == '{"a":1,"b":2}'


def test_decode_json_object_handles_invalid_payload() -> None:
    assert decode_json_object(None) == {}
    assert decode_json_object("invalid json") == {}
    assert decode_json_object('["not","object"]') == {}
    assert decode_json_object('{"ok":1}') == {"ok": 1}


def test_row_to_job_payload_decodes_payload_and_result() -> None:
    row_payload = row_to_job_payload(
        {
            "job_id": "job-1",
            "payload_json": '{"ticker":"MU"}',
            "result_json": '{"ok":true}',
        }
    )
    assert row_payload["job_id"] == "job-1"
    assert row_payload["payload"] == {"ticker": "MU"}
    assert row_payload["result"] == {"ok": True}
    assert "payload_json" not in row_payload
    assert "result_json" not in row_payload


def test_row_to_adaptive_profile_payload_normalizes_fields() -> None:
    payload = row_to_adaptive_profile_payload(
        {
            "profile_id": "p-1",
            "candidate_json": '{"score":1}',
            "metadata_json": '{"source":"test"}',
            "adaptive_version": 0,
            "scope": "GLOBAL",
        }
    )
    assert payload["candidate"] == {"score": 1}
    assert payload["metadata"] == {"source": "test"}
    assert payload["adaptive_version"] == 1
    assert payload["scope"] == "global"


def test_diagnostic_payload_blob_roundtrip_and_fallback() -> None:
    compressed, checksum, payload_size, compressed_size = build_diagnostic_payload_blob(
        {"phase": 2, "ticker": "MU"}
    )
    assert isinstance(checksum, str) and len(checksum) == 64
    assert payload_size > 0
    assert compressed_size > 0
    assert decode_diagnostic_payload_blob(compressed) == {"phase": 2, "ticker": "MU"}

    compressed_other, *_ = build_diagnostic_payload_blob(["not", "dict"])
    assert decode_diagnostic_payload_blob(compressed_other) == {}
    assert decode_diagnostic_payload_blob(b"invalid-gzip") is None
