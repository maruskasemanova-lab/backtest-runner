from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    tenant_id: str
    role: str
    plan_tier: str
    email: Optional[str]
    claims: Dict[str, Any]


class JwtValidationError(ValueError):
    pass


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * ((4 - len(segment) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise JwtValidationError("Invalid base64url segment") from exc


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def parse_bearer_token(authorization_header: Optional[str]) -> str:
    raw = str(authorization_header or "").strip()
    if not raw:
        raise JwtValidationError("Missing Authorization header")
    parts = raw.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise JwtValidationError("Authorization must use Bearer token")
    return parts[1].strip()


def _resolve_supabase_auth_verify_url() -> str:
    base_url = str(
        os.getenv("BACKTEST_SUPABASE_URL")
        or os.getenv("VITE_SUPABASE_URL")
        or "",
    ).strip().rstrip("/")
    if not base_url:
        return ""
    return f"{base_url}/auth/v1/user"


def _resolve_supabase_auth_verify_api_key() -> str:
    return str(
        os.getenv("BACKTEST_SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("VITE_SUPABASE_ANON_KEY")
        or os.getenv("BACKTEST_SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or "",
    ).strip()


def _resolve_supabase_auth_verify_timeout_seconds() -> float:
    raw = str(os.getenv("BACKTEST_SUPABASE_AUTH_VERIFY_TIMEOUT_SEC") or "").strip()
    try:
        parsed = float(raw) if raw else 4.0
    except Exception:
        parsed = 4.0
    return max(1.0, min(parsed, 30.0))


def _verify_jwt_via_supabase_auth(token: str) -> Optional[Dict[str, Any]]:
    verify_url = _resolve_supabase_auth_verify_url()
    api_key = _resolve_supabase_auth_verify_api_key()
    if not verify_url or not api_key:
        return None

    response = requests.request(
        method="GET",
        url=verify_url,
        headers={
            "apikey": api_key,
            "Authorization": f"Bearer {str(token or '').strip()}",
        },
        timeout=_resolve_supabase_auth_verify_timeout_seconds(),
    )
    if response.status_code >= 400:
        snippet = str(response.text or "").strip()[:300]
        raise JwtValidationError(
            f"Supabase token verification failed [{response.status_code}]: {snippet or 'unknown error'}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise JwtValidationError("Supabase token verification returned invalid payload")

    user_id = str(payload.get("id") or "").strip()
    if not user_id:
        raise JwtValidationError("Supabase token verification payload missing user id")

    app_meta = payload.get("app_metadata")
    if not isinstance(app_meta, dict):
        app_meta = {}
    user_meta = payload.get("user_metadata")
    if not isinstance(user_meta, dict):
        user_meta = {}

    return {
        "sub": user_id,
        "email": str(payload.get("email") or "").strip() or None,
        "app_metadata": app_meta,
        "user_metadata": user_meta,
        "role": payload.get("role") or app_meta.get("role"),
    }


def decode_and_verify_jwt(token: str, *, secret: str, allow_unverified: bool = False) -> Dict[str, Any]:
    parts = str(token or "").split(".")
    if len(parts) != 3:
        raise JwtValidationError("Invalid JWT format")

    raw_header = _b64url_decode(parts[0])
    raw_payload = _b64url_decode(parts[1])

    try:
        header = json.loads(raw_header.decode("utf-8"))
    except Exception as exc:
        raise JwtValidationError("Invalid JWT header JSON") from exc

    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except Exception as exc:
        raise JwtValidationError("Invalid JWT payload JSON") from exc

    if not isinstance(header, dict) or not isinstance(payload, dict):
        raise JwtValidationError("Invalid JWT structure")

    alg = str(header.get("alg") or "").upper()
    claims = dict(payload)

    if alg == "HS256" and secret:
        signed_part = f"{parts[0]}.{parts[1]}".encode("utf-8")
        expected_sig = _b64url_encode(hmac.new(secret.encode("utf-8"), signed_part, hashlib.sha256).digest())
        if not hmac.compare_digest(parts[2], expected_sig):
            raise JwtValidationError("JWT signature verification failed")
    elif allow_unverified:
        # Explicitly allow unsigned/unsupported algorithms only in development mode.
        claims = dict(payload)
    else:
        verified = _verify_jwt_via_supabase_auth(token)
        if verified is None:
            if alg != "HS256":
                raise JwtValidationError("Unsupported JWT alg; expected HS256")
            raise JwtValidationError("JWT secret is not configured")
        claims = verified

    now = int(time.time())
    exp = claims.get("exp")
    if isinstance(exp, (int, float)) and int(exp) < now:
        raise JwtValidationError("JWT has expired")

    nbf = claims.get("nbf")
    if isinstance(nbf, (int, float)) and int(nbf) > now:
        raise JwtValidationError("JWT not yet valid")

    return claims


def resolve_jwt_secret() -> str:
    return str(
        os.getenv("BACKTEST_JWT_SECRET")
        or os.getenv("SUPABASE_JWT_SECRET")
        or ""
    ).strip()


def allow_unverified_jwt() -> bool:
    raw = str(os.getenv("BACKTEST_ALLOW_UNVERIFIED_JWT") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def extract_role(payload: Dict[str, Any]) -> str:
    app_meta = payload.get("app_metadata") if isinstance(payload.get("app_metadata"), dict) else {}
    role = (
        payload.get("role")
        or app_meta.get("role")
        or payload.get("user_role")
        or "free"
    )
    normalized = str(role).strip().lower()
    if normalized in {"premium", "admin", "free"}:
        return normalized
    if normalized in {"service_role", "superuser", "owner"}:
        return "admin"
    return "free"


def extract_plan_tier(payload: Dict[str, Any], role: str) -> str:
    app_meta = payload.get("app_metadata") if isinstance(payload.get("app_metadata"), dict) else {}
    user_meta = payload.get("user_metadata") if isinstance(payload.get("user_metadata"), dict) else {}
    raw = (
        app_meta.get("plan_tier")
        or user_meta.get("plan_tier")
        or payload.get("plan_tier")
        or ("premium" if role == "admin" else "free")
    )
    normalized = str(raw).strip().lower()
    if normalized in {"free", "premium", "admin"}:
        return normalized
    return "premium" if role == "admin" else "free"


def extract_tenant_id(payload: Dict[str, Any], user_id: str) -> str:
    tenant_id = payload.get("tenant_id") or payload.get("org_id") or payload.get("organization_id")
    normalized = str(tenant_id or "").strip()
    if normalized:
        return normalized
    return f"tenant_{user_id}"


def build_auth_context(payload: Dict[str, Any], *, plan_tier_override: Optional[str] = None) -> AuthContext:
    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise JwtValidationError("JWT missing subject (sub)")

    role = extract_role(payload)
    plan_tier = str(plan_tier_override or extract_plan_tier(payload, role)).strip().lower()
    if plan_tier not in {"free", "premium", "admin"}:
        plan_tier = "premium" if role == "admin" else "free"

    email = payload.get("email")
    return AuthContext(
        user_id=user_id,
        tenant_id=extract_tenant_id(payload, user_id),
        role=role,
        plan_tier=plan_tier,
        email=str(email).strip() if email is not None else None,
        claims=dict(payload),
    )


def is_admin(auth: AuthContext) -> bool:
    return str(auth.role).strip().lower() == "admin" or str(auth.plan_tier).strip().lower() == "admin"
