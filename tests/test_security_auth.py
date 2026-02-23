from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from src.security.auth import JwtValidationError, decode_and_verify_jwt


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _make_jwt(
    payload: dict,
    *,
    secret: str = "test-secret",
    alg: str = "HS256",
    sig: str | None = None,
) -> str:
    header = {"alg": alg, "typ": "JWT"}
    part_header = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    part_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signed = f"{part_header}.{part_payload}"
    if sig is None:
        sig = _b64url(
            hmac.new(
                secret.encode("utf-8"), signed.encode("utf-8"), hashlib.sha256
            ).digest()
        )
    return f"{signed}.{sig}"


class _StubResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = int(status_code)
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_decode_and_verify_jwt_hs256_uses_supabase_auth_fallback(monkeypatch):
    token = _make_jwt(
        {
            "sub": "jwt-sub-ignored",
            "exp": int(time.time()) + 3600,
        },
        secret="unknown-secret",
    )

    monkeypatch.setenv("BACKTEST_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("BACKTEST_SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

    def _fake_request(method, url, headers=None, timeout=None, **kwargs):
        assert method == "GET"
        assert url == "https://example.supabase.co/auth/v1/user"
        assert headers["Authorization"] == f"Bearer {token}"
        assert headers["apikey"] == "service-role-key"
        _ = timeout, kwargs
        return _StubResponse(
            200,
            {
                "id": "supabase-user-1",
                "email": "user1@example.com",
                "app_metadata": {"role": "premium", "plan_tier": "premium"},
                "user_metadata": {"timezone": "UTC"},
            },
        )

    monkeypatch.setattr("src.security.auth.requests.request", _fake_request)
    claims = decode_and_verify_jwt(token, secret="", allow_unverified=False)
    assert claims["sub"] == "supabase-user-1"
    assert claims["email"] == "user1@example.com"
    assert claims["app_metadata"]["role"] == "premium"


def test_decode_and_verify_jwt_rs256_uses_supabase_auth_fallback(monkeypatch):
    token = _make_jwt(
        {
            "sub": "jwt-sub-ignored",
            "exp": int(time.time()) + 3600,
        },
        alg="RS256",
        sig="not-a-real-rs256-signature",
    )

    monkeypatch.setenv("BACKTEST_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("BACKTEST_SUPABASE_PUBLISHABLE_KEY", "publishable-key")

    def _fake_request(method, url, headers=None, timeout=None, **kwargs):
        assert method == "GET"
        assert url == "https://example.supabase.co/auth/v1/user"
        assert headers["Authorization"] == f"Bearer {token}"
        assert headers["apikey"] == "publishable-key"
        _ = timeout, kwargs
        return _StubResponse(
            200,
            {
                "id": "supabase-user-2",
                "email": "user2@example.com",
                "app_metadata": {"role": "free"},
            },
        )

    monkeypatch.setattr("src.security.auth.requests.request", _fake_request)
    claims = decode_and_verify_jwt(token, secret="", allow_unverified=False)
    assert claims["sub"] == "supabase-user-2"
    assert claims["email"] == "user2@example.com"


def test_decode_and_verify_jwt_supabase_auth_failure_raises(monkeypatch):
    token = _make_jwt(
        {
            "sub": "jwt-sub-ignored",
            "exp": int(time.time()) + 3600,
        },
        secret="unknown-secret",
    )
    monkeypatch.setenv("BACKTEST_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("BACKTEST_SUPABASE_SERVICE_ROLE_KEY", "service-role-key")

    def _fake_request(method, url, headers=None, timeout=None, **kwargs):
        _ = method, url, headers, timeout, kwargs
        return _StubResponse(401, {"error": "invalid_token"})

    monkeypatch.setattr("src.security.auth.requests.request", _fake_request)
    with pytest.raises(JwtValidationError):
        decode_and_verify_jwt(token, secret="", allow_unverified=False)
