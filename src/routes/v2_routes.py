from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Awaitable, Dict, Optional, Tuple
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.models.run_requests import StartRunRequest
from src.models.tuner_requests import AdaptiveTunerRequest
from src.security.auth import (
    AuthContext,
    JwtValidationError,
    allow_unverified_jwt,
    build_auth_context,
    decode_and_verify_jwt,
    extract_plan_tier,
    parse_bearer_token,
    resolve_jwt_secret,
)
from src.security.network_policy import (
    StrategyApiPolicyError,
    enforce_strategy_url_policy,
)
from src.services.saas_service import V2Services, resolve_plan_limits
from src.services.adaptive_tuner_orchestration_service import (
    run_adaptive_tuner as service_run_adaptive_tuner,
)

router = APIRouter(prefix="/api/v2")
HEAVY_JOB_TYPES = ("run", "adaptive_tuner", "download")


class BillingCheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str
    price_id: Optional[str] = None
    plan_tier: str = "premium"


class BillingPortalRequest(BaseModel):
    return_url: Optional[str] = None


class V2UserSettingsUpdateRequest(BaseModel):
    settings: Dict[str, Any] = Field(default_factory=dict)


class V2RunRequest(StartRunRequest):
    # v2 preserves request shape but always enforces strategy URL policy.
    pass


class V2AdaptiveTunerRequest(AdaptiveTunerRequest):
    pass


class V2DownloadRequest(BaseModel):
    ticker: str
    data_schema: str = "mbp-10"
    start_date: str
    end_date: str
    dataset: str = "XNAS.ITCH"
    convert_to_parquet: bool = True


class V2AdaptiveStrategyProfileRequest(BaseModel):
    ticker: str
    profile_name: str
    candidate: Dict[str, Any]
    adaptive_version: int = 1
    scope: str = "user"  # user | global
    profile_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def _request_id(request: Request) -> str:
    candidate = str(request.headers.get("x-request-id") or "").strip()
    return candidate if candidate else uuid4().hex


def _detail(
    *,
    code: str,
    message: str,
    request_id: str,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
    if isinstance(extras, dict) and extras:
        payload.update(extras)
    return payload


def _raise(
    status_code: int,
    *,
    code: str,
    message: str,
    request_id: str,
    extras: Optional[Dict[str, Any]] = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_detail(
            code=code, message=message, request_id=request_id, extras=extras
        ),
    )


def _parse_iso_day(value: str) -> date:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("empty date")
    if len(raw) >= 10:
        raw = raw[:10]
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _normalize_ticker(value: Any, *, request_id: str) -> str:
    token = str(value or "").strip().upper()
    if not token:
        _raise(
            400,
            code="invalid_ticker",
            message="ticker is required",
            request_id=request_id,
        )
    if not token.replace("-", "").replace("_", "").isalnum():
        _raise(
            400,
            code="invalid_ticker",
            message="ticker contains invalid characters",
            request_id=request_id,
        )
    return token


def _resolve_run_span_days(request: StartRunRequest) -> int:
    if request.date_from and request.date_to:
        start_day = _parse_iso_day(request.date_from)
        end_day = _parse_iso_day(request.date_to)
        if end_day < start_day:
            raise ValueError("date_to must be >= date_from")
        return (end_day - start_day).days + 1
    if request.date:
        _parse_iso_day(request.date)
        return 1
    raise ValueError("Either date or date_from/date_to must be set")


def _resolve_date_span_days(date_from: str, date_to: str) -> int:
    start_day = _parse_iso_day(date_from)
    end_day = _parse_iso_day(date_to)
    if end_day < start_day:
        raise ValueError("date_to must be >= date_from")
    return (end_day - start_day).days + 1


def _run_identity(request: StartRunRequest) -> Tuple[str, str, str]:
    run_id = str(request.run_id or "").strip()
    ticker = str(request.ticker or "").strip().upper()
    date_label = str(
        request.date or f"{request.date_from}_to_{request.date_to}"
    ).strip()
    return run_id, ticker, date_label


def _parse_run_key(run_key: str) -> Tuple[str, str, str]:
    parts = str(run_key or "").split(":")
    if len(parts) < 3:
        raise ValueError(f"Invalid run_key '{run_key}'")
    date_label = parts[-1]
    ticker = parts[-2]
    run_id = ":".join(parts[:-2])
    return run_id, ticker, date_label


def _normalize_idempotency_key(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) > 128:
        raise ValueError("Idempotency key must be <= 128 characters")
    for ch in raw:
        code = ord(ch)
        if code < 33 or code > 126:
            raise ValueError("Idempotency key must use visible ASCII characters")
    return raw


def _resolve_idempotency_key(request: Request, *, request_id: str) -> Optional[str]:
    raw = request.headers.get("Idempotency-Key")
    if raw is None:
        raw = request.headers.get("X-Idempotency-Key")
    try:
        return _normalize_idempotency_key(raw)
    except ValueError as exc:
        _raise(
            400, code="invalid_idempotency_key", message=str(exc), request_id=request_id
        )
    return None


def _format_job_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": str(job.get("job_id") or ""),
        "job_type": str(job.get("job_type") or ""),
        "status": str(job.get("status") or ""),
        "error": job.get("error"),
        "run_key": job.get("run_key"),
        "idempotency_key": job.get("idempotency_key"),
        "attempts": int(job.get("attempts") or 0),
        "max_attempts": int(job.get("max_attempts") or 1),
        "payload": job.get("payload") if isinstance(job.get("payload"), dict) else {},
        "result": job.get("result") if isinstance(job.get("result"), dict) else {},
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


def _resolve_job_max_attempts(*, services: V2Services, job_type: str) -> int:
    env_key = f"BACKTEST_V2_JOB_MAX_ATTEMPTS_{str(job_type or '').strip().upper()}"
    raw = os.getenv(env_key)
    if raw is None:
        raw = os.getenv("BACKTEST_V2_JOB_MAX_ATTEMPTS")
    if raw is None:
        raw = str(services.default_job_max_attempts)
    try:
        parsed = int(str(raw).strip())
    except Exception:
        parsed = int(services.default_job_max_attempts)
    return max(1, min(parsed, 5))


def _retry_delay_seconds(*, services: V2Services, attempt: int) -> float:
    base = max(0.05, float(services.job_retry_base_seconds))
    max_delay = max(base, float(services.job_retry_max_delay_seconds))
    exponent = max(0, int(attempt) - 1)
    return min(max_delay, base * (2**exponent))


def _should_retry_exception(exc: Exception) -> bool:
    if isinstance(exc, ValueError):
        return False
    if isinstance(exc, HTTPException):
        try:
            status = int(exc.status_code)
        except Exception:
            return True
        return status >= 500
    return True


def _error_text(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return json.dumps(detail, separators=(",", ":"), sort_keys=True)[:2000]
        return str(detail or f"HTTP {exc.status_code}")[:2000]
    return str(exc)[:2000]


def _job_auth_from_record(
    *, job: Dict[str, Any], fallback: AuthContext, services: V2Services
) -> AuthContext:
    owner_user_id = (
        str(job.get("user_id") or fallback.user_id).strip() or fallback.user_id
    )
    owner_tenant_id = (
        str(job.get("tenant_id") or fallback.tenant_id).strip() or fallback.tenant_id
    )
    if owner_user_id == fallback.user_id:
        role = fallback.role
        plan_tier = fallback.plan_tier
    else:
        user_row = services.store.get_user(user_id=owner_user_id)
        role = str((user_row or {}).get("role") or "free").strip().lower()
        if role not in {"free", "premium", "admin"}:
            role = "free"
        claim_plan_tier = "premium" if role == "premium" else "free"
        plan_tier = services.store.get_effective_plan(
            user_id=owner_user_id,
            claim_plan_tier=claim_plan_tier,
            role=role,
        )
    return AuthContext(
        user_id=owner_user_id,
        tenant_id=owner_tenant_id,
        role=role,
        plan_tier=plan_tier,
        email=None,
        claims={},
    )


def _schedule_job_task(
    *, services: V2Services, job_id: str, job_coro: Awaitable[None]
) -> None:
    async def _run() -> None:
        if services.dispatch_lock is None:
            services.dispatch_lock = asyncio.Lock()

        async with services.dispatch_lock:
            if job_id in services.active_dispatch_job_ids:
                return
            services.active_dispatch_job_ids.add(job_id)

        semaphore = services.job_semaphore
        try:
            if semaphore is None:
                await job_coro
                return
            async with semaphore:
                await job_coro
        finally:
            if services.dispatch_lock is None:
                return
            async with services.dispatch_lock:
                services.active_dispatch_job_ids.discard(job_id)

    asyncio.create_task(_run())


def _dispatch_queued_job_if_needed(
    *,
    job: Dict[str, Any],
    auth: AuthContext,
    services: V2Services,
    api_services: Any,
) -> None:
    if not isinstance(job, dict):
        return
    if str(job.get("status") or "").strip().lower() != "queued":
        return
    attempts = max(0, int(job.get("attempts") or 0))
    max_attempts = max(1, int(job.get("max_attempts") or 1))
    if attempts >= max_attempts and job.get("error"):
        return

    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    request_payload = (
        payload.get("request") if isinstance(payload.get("request"), dict) else {}
    )
    if not request_payload:
        return

    job_id = str(job.get("job_id") or "").strip()
    job_type = str(job.get("job_type") or "").strip().lower()
    if not job_id:
        return

    job_auth = _job_auth_from_record(job=job, fallback=auth, services=services)
    if job_type == "run":
        job_coro = _execute_run_job(
            request_payload=request_payload,
            auth=job_auth,
            job_id=job_id,
            services=services,
            api_services=api_services,
        )
    elif job_type == "adaptive_tuner":
        job_coro = _execute_adaptive_tuner_job(
            request_payload=request_payload,
            auth=job_auth,
            job_id=job_id,
            services=services,
            api_services=api_services,
        )
    elif job_type == "download":
        job_coro = _execute_download_job(
            request_payload=request_payload,
            auth=job_auth,
            job_id=job_id,
            services=services,
            api_services=api_services,
        )
    else:
        return
    _schedule_job_task(services=services, job_id=job_id, job_coro=job_coro)


def _enforce_global_backlog_limit(*, services: V2Services, request_id: str) -> None:
    max_backlog = max(1, int(services.max_queue_backlog))
    queued_heavy = services.store.count_jobs(
        statuses=("queued",), job_types=HEAVY_JOB_TYPES
    )
    if queued_heavy >= max_backlog:
        _raise(
            429,
            code="queue_backlog_exceeded",
            message="Heavy job backlog is full, retry later",
            request_id=request_id,
            extras={
                "queued_heavy_jobs": queued_heavy,
                "max_queue_backlog": max_backlog,
            },
        )


def _maybe_idempotent_job(
    *,
    auth: AuthContext,
    services: V2Services,
    job_type: str,
    idempotency_key: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not idempotency_key:
        return None
    return services.store.get_job_by_idempotency_key(
        user_id=auth.user_id,
        job_type=job_type,
        idempotency_key=idempotency_key,
    )


def _stripe_secret_key() -> str:
    return str(os.getenv("STRIPE_SECRET_KEY") or "").strip()


def _stripe_webhook_secret() -> str:
    return str(os.getenv("STRIPE_WEBHOOK_SECRET") or "").strip()


def _parse_non_negative_int(value: Any, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        return max(0, int(default))
    return max(0, parsed)


def _billing_grace_days() -> int:
    return _parse_non_negative_int(os.getenv("BACKTEST_BILLING_GRACE_DAYS", "3"), 3)


def _to_utc_iso_from_unix(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except Exception:
        token = str(value).strip()
        return token or None
    if parsed <= 0:
        return None
    return datetime.utcfromtimestamp(parsed).replace(microsecond=0).isoformat() + "Z"


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "on"}


def _grace_until_iso(*, now_ts: float, days: int) -> Optional[str]:
    if days <= 0:
        return None
    return (
        datetime.utcfromtimestamp(now_ts + (days * 86400))
        .replace(microsecond=0)
        .isoformat()
        + "Z"
    )


def _as_object(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_csv_env_set(name: str, default: str = "") -> set[str]:
    raw = str(os.getenv(name, default) or "").strip()
    if not raw:
        return set()
    values: set[str] = set()
    for token in raw.split(","):
        item = str(token).strip().lower()
        if item:
            values.add(item)
    return values


def _invite_only_enabled() -> bool:
    return _to_bool(os.getenv("BACKTEST_INVITE_ONLY_BETA", "0"))


def _is_invite_allowed(auth: AuthContext) -> bool:
    user_id = str(auth.user_id or "").strip().lower()
    tenant_id = str(auth.tenant_id or "").strip().lower()
    email = str(auth.email or "").strip().lower()

    allow_users = _parse_csv_env_set("BACKTEST_INVITE_ALLOWLIST_USERS")
    allow_tenants = _parse_csv_env_set("BACKTEST_INVITE_ALLOWLIST_TENANTS")
    allow_emails = _parse_csv_env_set("BACKTEST_INVITE_ALLOWLIST_EMAILS")

    if user_id and user_id in allow_users:
        return True
    if tenant_id and tenant_id in allow_tenants:
        return True
    if email and email in allow_emails:
        return True
    return False


def _enforce_invite_only(*, auth: AuthContext, request_id: str) -> None:
    if not _invite_only_enabled():
        return
    if auth.role == "admin" or auth.plan_tier == "admin":
        return
    if _is_invite_allowed(auth):
        return
    _raise(
        403,
        code="invite_only_beta",
        message="Signups are invite-only during beta rollout",
        request_id=request_id,
    )


def _heavy_ops_enabled() -> bool:
    return _to_bool(os.getenv("BACKTEST_V2_HEAVY_OPS_ENABLED", "1"))


def _enforce_heavy_ops_enabled(*, auth: AuthContext, request_id: str) -> None:
    if _heavy_ops_enabled():
        return
    if auth.role == "admin" or auth.plan_tier == "admin":
        return
    _raise(
        503,
        code="heavy_ops_disabled",
        message="Heavy operations are temporarily disabled",
        request_id=request_id,
    )


def _enforce_admin_role(*, auth: AuthContext, request_id: str) -> None:
    if auth.role == "admin" or auth.plan_tier == "admin":
        return
    _raise(
        403,
        code="forbidden",
        message="Admin role required",
        request_id=request_id,
    )


def _is_admin(auth: AuthContext) -> bool:
    return auth.role == "admin" or auth.plan_tier == "admin"


def _normalize_profile_scope(value: Any, *, auth: AuthContext, request_id: str) -> str:
    scope = str(value or "user").strip().lower()
    if scope not in {"user", "global"}:
        _raise(
            400,
            code="invalid_scope",
            message="scope must be 'user' or 'global'",
            request_id=request_id,
        )
    if scope == "global" and not _is_admin(auth):
        _raise(
            403,
            code="forbidden",
            message="Only superuser can manage global strategies",
            request_id=request_id,
        )
    return scope


def _can_manage_adaptive_profile(*, profile: Dict[str, Any], auth: AuthContext) -> bool:
    if _is_admin(auth):
        return True
    scope = str(profile.get("scope") or "").strip().lower()
    owner_user_id = str(profile.get("owner_user_id") or "").strip()
    return scope == "user" and owner_user_id == auth.user_id


def _format_adaptive_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "profile_id": str(profile.get("profile_id") or ""),
        "scope": str(profile.get("scope") or "user"),
        "ticker": str(profile.get("ticker") or ""),
        "profile_name": str(profile.get("profile_name") or ""),
        "adaptive_version": int(profile.get("adaptive_version") or 1),
        "candidate": (
            profile.get("candidate")
            if isinstance(profile.get("candidate"), dict)
            else {}
        ),
        "metadata": (
            profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
        ),
        "owner_user_id": str(profile.get("owner_user_id") or "") or None,
        "owner_tenant_id": str(profile.get("owner_tenant_id") or "") or None,
        "created_at": profile.get("created_at"),
        "updated_at": profile.get("updated_at"),
    }


def _stripe_post(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    secret = _stripe_secret_key()
    if not secret:
        raise RuntimeError("Stripe is not configured (missing STRIPE_SECRET_KEY)")
    resp = requests.post(
        f"https://api.stripe.com{path}",
        data=data,
        auth=(secret, ""),
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Stripe API error [{resp.status_code}]: {resp.text[:500]}")
    payload = resp.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Stripe API returned unexpected payload")
    return payload


def _verify_stripe_signature(
    raw_body: bytes, signature_header: str, webhook_secret: str
) -> bool:
    if not webhook_secret:
        return True
    raw_sig = str(signature_header or "").strip()
    if not raw_sig:
        return False

    timestamp = ""
    v1_signatures = []
    for token in raw_sig.split(","):
        key, _, value = token.partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            v1_signatures.append(value)
    if not timestamp or not v1_signatures:
        return False

    signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
    expected = hmac.new(
        webhook_secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in v1_signatures)


def get_v2_services(request: Request) -> V2Services:
    services = getattr(request.app.state, "v2_services", None)
    if isinstance(services, V2Services):
        return services
    raise HTTPException(status_code=500, detail="v2 services are not initialized")


def _maybe_apply_retention_cleanup(*, auth: AuthContext, services: V2Services) -> None:
    limits = resolve_plan_limits(auth.plan_tier)
    day_key = datetime.utcnow().date().isoformat()
    marker_key = f"{auth.user_id}:{limits.retention_days}"
    if services.retention_cleanup_markers.get(marker_key) == day_key:
        return

    try:
        services.store.prune_user_history(
            user_id=auth.user_id,
            retention_days=limits.retention_days,
        )
    except Exception:
        # Retention cleanup is best-effort and must not block authenticated calls.
        return

    prefix = f"{auth.user_id}:"
    stale_keys = [
        key
        for key in list(services.retention_cleanup_markers.keys())
        if key.startswith(prefix) and key != marker_key
    ]
    for stale_key in stale_keys:
        services.retention_cleanup_markers.pop(stale_key, None)
    services.retention_cleanup_markers[marker_key] = day_key


async def get_auth_context(
    request: Request,
    services: V2Services = Depends(get_v2_services),
) -> AuthContext:
    req_id = _request_id(request)

    try:
        token = parse_bearer_token(request.headers.get("Authorization"))
        payload = decode_and_verify_jwt(
            token,
            secret=resolve_jwt_secret(),
            allow_unverified=allow_unverified_jwt(),
        )
    except JwtValidationError as exc:
        _raise(401, code="unauthorized", message=str(exc), request_id=req_id)

    base_auth = build_auth_context(payload)
    effective_plan = services.store.get_effective_plan(
        user_id=base_auth.user_id,
        claim_plan_tier=extract_plan_tier(payload, base_auth.role),
        role=base_auth.role,
    )
    auth = build_auth_context(payload, plan_tier_override=effective_plan)

    services.store.ensure_identity(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        role=auth.role,
        email=auth.email,
    )
    _enforce_invite_only(auth=auth, request_id=req_id)
    _maybe_apply_retention_cleanup(auth=auth, services=services)

    limits = resolve_plan_limits(auth.plan_tier)
    allowed, used = services.limiter.consume(
        f"{auth.user_id}:rpm",
        limit=limits.req_per_min,
    )
    services.store.increment_usage(user_id=auth.user_id, metric="api_requests")
    if not allowed:
        _raise(
            429,
            code="rate_limited",
            message="Too many requests for current plan tier",
            request_id=req_id,
            extras={
                "plan_tier": auth.plan_tier,
                "limit_per_min": limits.req_per_min,
                "used_in_window": used,
            },
        )

    request.state.request_id = req_id
    request.state.auth_context = auth
    return auth


def _quota_snapshot(*, auth: AuthContext, services: V2Services) -> Dict[str, Any]:
    limits = resolve_plan_limits(auth.plan_tier)
    usage = services.store.get_usage_for_day(user_id=auth.user_id)
    active_runs = services.store.count_active_runs(user_id=auth.user_id)
    active_run_jobs = services.store.count_active_jobs(
        user_id=auth.user_id, job_types=("run",)
    )
    active_heavy_jobs = services.store.count_jobs(
        user_id=auth.user_id,
        statuses=("running",),
        job_types=HEAVY_JOB_TYPES,
    )
    queued_heavy_jobs = services.store.count_jobs(
        user_id=auth.user_id,
        statuses=("queued",),
        job_types=HEAVY_JOB_TYPES,
    )
    return {
        "day_key": datetime.utcnow().date().isoformat(),
        "limits": {
            "concurrent_runs": limits.concurrent_runs,
            "max_range_days": limits.max_range_days,
            "req_per_min": limits.req_per_min,
            "retention_days": limits.retention_days,
            "ads_enabled": limits.ads_enabled,
        },
        "usage": {
            "api_requests": int(usage.get("api_requests", 0)),
            "run_start_requests": int(usage.get("run_start_requests", 0)),
            "active_runs": int(active_runs),
            "active_run_jobs": int(active_run_jobs),
            "active_heavy_jobs": int(active_heavy_jobs),
            "queued_heavy_jobs": int(queued_heavy_jobs),
        },
    }


def _settings_store_for_user(services: V2Services):
    candidate = getattr(services, "user_settings_store", None)
    if candidate is not None:
        return candidate
    return services.store


def _sync_user_run_statuses(
    *, auth: AuthContext, services: V2Services, api_services: Any
) -> None:
    active_map = getattr(api_services, "active_runners", {})
    active_keys = set(active_map.keys()) if isinstance(active_map, dict) else set()
    tracked = services.store.list_run_keys_by_user(
        user_id=auth.user_id,
        statuses=("queued", "running", "ready", "active"),
    )
    for run_key in tracked:
        if run_key not in active_keys:
            services.store.update_run_status(run_key=run_key, status="completed")


def _active_heavy_jobs(*, auth: AuthContext, services: V2Services) -> int:
    return services.store.count_active_jobs(
        user_id=auth.user_id,
        job_types=HEAVY_JOB_TYPES,
    )


def _enforce_plan_limits_for_heavy_op(
    *,
    auth: AuthContext,
    services: V2Services,
    request_id: str,
    requested_range_days: int,
    api_services: Any,
) -> Dict[str, int]:
    limits = resolve_plan_limits(auth.plan_tier)
    if requested_range_days > limits.max_range_days:
        _raise(
            402,
            code="plan_limit_exceeded",
            message="Date range exceeds current plan limit",
            request_id=request_id,
            extras={
                "plan_tier": auth.plan_tier,
                "max_range_days": limits.max_range_days,
                "requested_range_days": requested_range_days,
            },
        )

    _sync_user_run_statuses(auth=auth, services=services, api_services=api_services)
    active_runs = services.store.count_active_runs(user_id=auth.user_id)
    active_jobs = _active_heavy_jobs(auth=auth, services=services)
    if active_runs + active_jobs >= limits.concurrent_runs:
        _raise(
            402,
            code="plan_limit_exceeded",
            message="Concurrent heavy-job limit reached for current plan",
            request_id=request_id,
            extras={
                "plan_tier": auth.plan_tier,
                "concurrent_runs_limit": limits.concurrent_runs,
                "active_runs": active_runs,
                "active_jobs": active_jobs,
            },
        )
    return {
        "active_runs": int(active_runs),
        "active_jobs": int(active_jobs),
    }


async def _execute_run_job(
    *,
    request_payload: Dict[str, Any],
    auth: AuthContext,
    job_id: str,
    services: V2Services,
    api_services: Any,
) -> None:
    req = StartRunRequest(**request_payload)
    run_id, ticker, date_label = _run_identity(req)
    provisional_run_key = f"{run_id}:{ticker}:{date_label}"

    while True:
        attempts, max_attempts = services.store.begin_job_attempt(job_id=job_id)
        services.store.update_run_status(run_key=provisional_run_key, status="running")
        run_key: Optional[str] = None

        try:
            result = await api_services.start_run(req)
            if isinstance(result, dict):
                run_key = str(result.get("run_key") or "").strip() or None
            effective_run_key = run_key or provisional_run_key

            resolved_run_id, resolved_ticker, resolved_date_label = _parse_run_key(
                effective_run_key
            )
            services.store.upsert_run(
                run_key=effective_run_key,
                user_id=auth.user_id,
                tenant_id=auth.tenant_id,
                run_id=resolved_run_id,
                ticker=resolved_ticker,
                date_label=resolved_date_label,
                status="ready",
                metadata={
                    "plan_tier": auth.plan_tier,
                    "job_id": job_id,
                    "attempts": attempts,
                },
            )
            services.store.update_job(
                job_id=job_id,
                status="completed",
                result=result if isinstance(result, dict) else {"result": result},
                run_key=effective_run_key,
            )
            return
        except Exception as exc:
            error = _error_text(exc)
            should_retry = attempts < max_attempts and _should_retry_exception(exc)
            if should_retry:
                services.store.update_run_status(
                    run_key=provisional_run_key, status="queued"
                )
                services.store.update_job(job_id=job_id, status="queued", error=error)
                await asyncio.sleep(
                    _retry_delay_seconds(services=services, attempt=attempts)
                )
                continue
            services.store.update_run_status(
                run_key=provisional_run_key, status="failed"
            )
            services.store.update_job(job_id=job_id, status="failed", error=error)
            return


async def _execute_adaptive_tuner_job(
    *,
    request_payload: Dict[str, Any],
    auth: AuthContext,
    job_id: str,
    services: V2Services,
    api_services: Any,
) -> None:
    request_obj = AdaptiveTunerRequest(**request_payload)
    while True:
        attempts, max_attempts = services.store.begin_job_attempt(job_id=job_id)
        try:
            custom = getattr(api_services, "v2_run_adaptive_tuner", None)
            if callable(custom):
                result = await custom(request_obj)
            else:
                result = await service_run_adaptive_tuner(
                    request_obj,
                    api_services.build_adaptive_tuner_deps(),
                )
            services.store.update_job(
                job_id=job_id,
                status="completed",
                result=result if isinstance(result, dict) else {"result": result},
            )
            return
        except Exception as exc:
            error = _error_text(exc)
            should_retry = attempts < max_attempts and _should_retry_exception(exc)
            if should_retry:
                services.store.update_job(job_id=job_id, status="queued", error=error)
                await asyncio.sleep(
                    _retry_delay_seconds(services=services, attempt=attempts)
                )
                continue
            services.store.update_job(job_id=job_id, status="failed", error=error)
            return


async def _execute_download_job(
    *,
    request_payload: Dict[str, Any],
    auth: AuthContext,
    job_id: str,
    services: V2Services,
    api_services: Any,
) -> None:
    req = V2DownloadRequest(**request_payload)
    ticker = str(req.ticker or "").upper().strip()

    while True:
        attempts, max_attempts = services.store.begin_job_attempt(job_id=job_id)
        try:
            custom = getattr(api_services, "v2_run_download", None)
            if callable(custom):
                result = await custom(req)
            else:
                coverage = api_services.databento_svc.get_range_coverage(
                    ticker=ticker,
                    schema=req.data_schema,
                    start_date=req.start_date,
                    end_date=req.end_date,
                )
                if coverage.get("fully_covered"):
                    result = {"status": "already_exists", "coverage": coverage}
                else:

                    async def _broadcast(msg: Dict[str, Any]) -> None:
                        broadcaster = getattr(api_services, "broadcast", None)
                        if callable(broadcaster):
                            await broadcaster(msg)

                    entry = await api_services.databento_svc.download(
                        ticker=ticker,
                        schema=req.data_schema,
                        start_date=req.start_date,
                        end_date=req.end_date,
                        dataset=req.dataset,
                        convert_to_parquet=req.convert_to_parquet,
                        broadcast_fn=_broadcast,
                    )
                    entry_status = (
                        str(entry.get("status"))
                        if isinstance(entry, dict)
                        else str(getattr(entry, "status", "done"))
                    )
                    result = {
                        "status": "completed",
                        "entry_status": entry_status,
                        "ticker": ticker,
                        "schema": req.data_schema,
                    }
            services.store.update_job(
                job_id=job_id,
                status="completed",
                result=result if isinstance(result, dict) else {"result": result},
            )
            return
        except Exception as exc:
            error = _error_text(exc)
            should_retry = attempts < max_attempts and _should_retry_exception(exc)
            if should_retry:
                services.store.update_job(job_id=job_id, status="queued", error=error)
                await asyncio.sleep(
                    _retry_delay_seconds(services=services, attempt=attempts)
                )
                continue
            services.store.update_job(job_id=job_id, status="failed", error=error)
            return


@router.get("/auth/me")
async def v2_me(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    api_services = getattr(request.app.state, "api_services", None)
    if api_services is not None:
        _sync_user_run_statuses(auth=auth, services=services, api_services=api_services)
    return {
        "request_id": req_id,
        "user_id": auth.user_id,
        "tenant_id": auth.tenant_id,
        "role": auth.role,
        "plan_tier": auth.plan_tier,
        "email": auth.email,
        "quota_snapshot": _quota_snapshot(auth=auth, services=services),
    }


@router.get("/plans")
async def v2_plans(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    _ = auth
    req_id = _request_id(request)
    return {
        "request_id": req_id,
        "plans": {
            "free": {
                "concurrent_runs": 1,
                "max_range_days": 5,
                "req_per_min": 30,
                "retention_days": 7,
                "ads_enabled": True,
            },
            "premium": {
                "concurrent_runs": 5,
                "max_range_days": 60,
                "req_per_min": 300,
                "retention_days": 180,
                "ads_enabled": False,
            },
        },
    }


@router.get("/usage")
async def v2_usage(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    api_services = getattr(request.app.state, "api_services", None)
    if api_services is not None:
        _sync_user_run_statuses(auth=auth, services=services, api_services=api_services)
    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "quota_snapshot": _quota_snapshot(auth=auth, services=services),
        "feature_flags": {
            "ads_enabled": bool(
                services.ads_enabled and resolve_plan_limits(auth.plan_tier).ads_enabled
            ),
            "ads_provider": services.ads_provider,
            "ads_placements": list(services.ads_placements),
        },
        "rollout": {
            "invite_only_beta": _invite_only_enabled(),
            "heavy_ops_enabled": _heavy_ops_enabled(),
        },
    }


@router.get("/user/settings")
async def v2_user_settings(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    settings_store = _settings_store_for_user(services)
    settings = settings_store.get_user_settings(user_id=auth.user_id)
    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "settings": settings,
    }


@router.put("/user/settings")
async def v2_upsert_user_settings(
    payload: V2UserSettingsUpdateRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    settings_store = _settings_store_for_user(services)
    try:
        settings = settings_store.merge_user_settings(
            user_id=auth.user_id,
            tenant_id=auth.tenant_id,
            patch=payload.settings,
        )
    except ValueError as exc:
        _raise(
            400, code="invalid_settings_payload", message=str(exc), request_id=req_id
        )
    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "settings": settings,
    }


@router.get("/ops/metrics")
async def v2_ops_metrics(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    _enforce_admin_role(auth=auth, request_id=req_id)

    max_backlog = max(1, int(services.max_queue_backlog))
    queued_heavy = services.store.count_jobs(
        statuses=("queued",), job_types=HEAVY_JOB_TYPES
    )
    running_heavy = services.store.count_jobs(
        statuses=("running",), job_types=HEAVY_JOB_TYPES
    )
    failed_heavy = services.store.count_jobs(
        statuses=("failed",), job_types=HEAVY_JOB_TYPES
    )
    completed_heavy = services.store.count_jobs(
        statuses=("completed",), job_types=HEAVY_JOB_TYPES
    )
    finished_heavy = failed_heavy + completed_heavy
    fail_rate = (failed_heavy / finished_heavy) if finished_heavy > 0 else 0.0

    ws_clients = getattr(request.app.state, "connected_clients", None)
    ws_active = len(ws_clients) if isinstance(ws_clients, list) else 0
    ws_max = int(getattr(request.app.state, "max_ws_clients", 0) or 0)
    ws_util = (ws_active / ws_max) if ws_max > 0 else 0.0

    runtime = {}
    runtime_metrics = getattr(request.app.state, "runtime_metrics", None)
    snapshot_fn = getattr(runtime_metrics, "snapshot", None)
    if callable(snapshot_fn):
        candidate = snapshot_fn()
        if isinstance(candidate, dict):
            runtime = candidate

    raw_db_path = str(getattr(services.store, "db_path", "") or "").strip()
    db_path = Path(raw_db_path) if raw_db_path else None
    db_exists = bool(db_path and db_path.exists())
    db_size_bytes = (
        int(db_path.stat().st_size) if db_exists and db_path is not None else 0
    )

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "timestamp_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "queue": {
            "queued_heavy_jobs": int(queued_heavy),
            "running_heavy_jobs": int(running_heavy),
            "completed_heavy_jobs": int(completed_heavy),
            "failed_heavy_jobs": int(failed_heavy),
            "heavy_fail_rate": round(fail_rate, 6),
            "max_queue_backlog": int(max_backlog),
            "queue_backlog_utilization": round(min(1.0, queued_heavy / max_backlog), 6),
            "active_dispatch_jobs": int(len(services.active_dispatch_job_ids)),
        },
        "websocket": {
            "active_clients": int(ws_active),
            "max_clients": int(ws_max),
            "utilization": round(min(1.0, ws_util), 6),
        },
        "runtime": runtime,
        "storage": {
            "saas_db_path": str(db_path) if db_path is not None else None,
            "saas_db_exists": bool(db_exists),
            "saas_db_size_bytes": int(db_size_bytes),
        },
    }


@router.get("/strategies/adaptive")
async def v2_list_adaptive_strategies(
    request: Request,
    ticker: str = "",
    include_global: bool = True,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    normalized_ticker = (
        _normalize_ticker(ticker, request_id=req_id)
        if str(ticker or "").strip()
        else None
    )
    profiles = services.store.list_adaptive_strategy_profiles(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        ticker=normalized_ticker,
        include_user=True,
        include_global=bool(include_global),
    )
    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "ticker": normalized_ticker,
        "profiles": [_format_adaptive_profile(item) for item in profiles],
        "count": len(profiles),
    }


@router.post("/strategies/adaptive")
async def v2_upsert_adaptive_strategy(
    payload: V2AdaptiveStrategyProfileRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    normalized_ticker = _normalize_ticker(payload.ticker, request_id=req_id)
    normalized_scope = _normalize_profile_scope(
        payload.scope, auth=auth, request_id=req_id
    )
    profile_name = str(payload.profile_name or "").strip()
    if not profile_name:
        _raise(
            400,
            code="invalid_profile_name",
            message="profile_name is required",
            request_id=req_id,
        )

    profile_id = str(payload.profile_id or "").strip() or None
    existing = (
        services.store.get_adaptive_strategy_profile(profile_id=profile_id)
        if profile_id
        else None
    )
    if profile_id and not existing:
        _raise(
            404,
            code="profile_not_found",
            message="Adaptive strategy profile not found",
            request_id=req_id,
        )
    if isinstance(existing, dict) and not _can_manage_adaptive_profile(
        profile=existing, auth=auth
    ):
        _raise(
            403,
            code="forbidden",
            message="Profile does not belong to current user",
            request_id=req_id,
        )

    if not _is_admin(auth):
        normalized_scope = "user"

    try:
        saved = services.store.upsert_adaptive_strategy_profile(
            profile_id=profile_id,
            scope=normalized_scope,
            owner_user_id=None if normalized_scope == "global" else auth.user_id,
            owner_tenant_id=None if normalized_scope == "global" else auth.tenant_id,
            ticker=normalized_ticker,
            profile_name=profile_name,
            adaptive_version=max(1, int(payload.adaptive_version or 1)),
            candidate=payload.candidate,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        _raise(400, code="invalid_profile_payload", message=str(exc), request_id=req_id)

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "profile": _format_adaptive_profile(saved),
    }


@router.delete("/strategies/adaptive/{profile_id}")
async def v2_delete_adaptive_strategy(
    profile_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    target = services.store.get_adaptive_strategy_profile(profile_id=profile_id)
    if not isinstance(target, dict):
        _raise(
            404,
            code="profile_not_found",
            message="Adaptive strategy profile not found",
            request_id=req_id,
        )
    if not _can_manage_adaptive_profile(profile=target, auth=auth):
        _raise(
            403,
            code="forbidden",
            message="Profile does not belong to current user",
            request_id=req_id,
        )

    deleted = services.store.delete_adaptive_strategy_profile(profile_id=profile_id)
    if not deleted:
        _raise(
            404,
            code="profile_not_found",
            message="Adaptive strategy profile not found",
            request_id=req_id,
        )

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "profile_id": profile_id,
        "deleted": True,
    }


@router.post("/billing/checkout")
async def v2_billing_checkout(
    payload: BillingCheckoutRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
):
    req_id = _request_id(request)
    plan = str(payload.plan_tier or "premium").strip().lower()
    if plan != "premium":
        _raise(
            400,
            code="invalid_plan",
            message="Only premium checkout is supported",
            request_id=req_id,
        )

    try:
        session = _stripe_post(
            "/v1/checkout/sessions",
            {
                "mode": "subscription",
                "success_url": payload.success_url,
                "cancel_url": payload.cancel_url,
                "line_items[0][price]": payload.price_id
                or str(os.getenv("STRIPE_PREMIUM_PRICE_ID") or "").strip(),
                "line_items[0][quantity]": "1",
                "client_reference_id": auth.user_id,
                "metadata[user_id]": auth.user_id,
                "metadata[tenant_id]": auth.tenant_id,
                "metadata[target_plan]": "premium",
                "customer_email": auth.email or "",
            },
        )
    except Exception as exc:
        _raise(503, code="billing_unavailable", message=str(exc), request_id=req_id)

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "checkout_url": session.get("url"),
        "session_id": session.get("id"),
    }


@router.post("/billing/portal")
async def v2_billing_portal(
    payload: BillingPortalRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    customer_id = services.store.get_stripe_customer_id(user_id=auth.user_id)
    if not customer_id:
        _raise(
            404,
            code="customer_not_found",
            message="No Stripe customer linked for user",
            request_id=req_id,
        )

    try:
        session = _stripe_post(
            "/v1/billing_portal/sessions",
            {
                "customer": customer_id,
                "return_url": payload.return_url
                or str(
                    os.getenv("BILLING_PORTAL_RETURN_URL") or "http://localhost:5173"
                ),
            },
        )
    except Exception as exc:
        _raise(503, code="billing_unavailable", message=str(exc), request_id=req_id)

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "portal_url": session.get("url"),
    }


@router.post("/billing/webhook/stripe")
async def v2_billing_webhook_stripe(
    request: Request,
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    raw = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    if not _verify_stripe_signature(raw, signature, _stripe_webhook_secret()):
        _raise(
            401,
            code="invalid_signature",
            message="Invalid Stripe signature",
            request_id=req_id,
        )

    try:
        event = json.loads(raw.decode("utf-8"))
    except Exception:
        _raise(
            400,
            code="invalid_json",
            message="Webhook payload is not valid JSON",
            request_id=req_id,
        )

    if not isinstance(event, dict):
        _raise(
            400,
            code="invalid_payload",
            message="Webhook payload must be JSON object",
            request_id=req_id,
        )

    event_id = str(event.get("id") or "").strip() or f"evt_{uuid4().hex}"
    inserted = services.store.mark_webhook_event_processed(
        provider="stripe",
        event_id=event_id,
        payload=event,
    )
    if not inserted:
        return {
            "request_id": req_id,
            "status": "duplicate_ignored",
            "event_id": event_id,
        }

    event_type = str(event.get("type") or "").strip()
    data_envelope = _as_object(event.get("data"))
    data_object = _as_object(data_envelope.get("object"))
    metadata = _as_object(data_object.get("metadata"))
    user_id = str(metadata.get("user_id") or "").strip()
    customer_id = str(data_object.get("customer") or "").strip() or None
    subscription_id = (
        str(data_object.get("subscription") or data_object.get("id") or "").strip()
        or None
    )

    if not user_id and customer_id:
        user_id = services.store.find_user_id_by_stripe_customer(customer_id) or ""
    if not user_id and subscription_id:
        user_id = (
            services.store.find_user_id_by_stripe_subscription(subscription_id) or ""
        )
    stripe_status = str(data_object.get("status") or "").strip().lower()
    cancel_at_period_end = _to_bool(data_object.get("cancel_at_period_end"))
    current_period_end = _to_utc_iso_from_unix(data_object.get("current_period_end"))
    now_ts = time.time()
    grace_until = _grace_until_iso(now_ts=now_ts, days=_billing_grace_days())
    previous_subscription = (
        services.store.get_subscription(user_id=user_id) if user_id else None
    )
    previous_plan_tier = (
        services.store.get_effective_plan(
            user_id=user_id, claim_plan_tier="free", role="free"
        )
        if user_id
        else None
    )
    previous_status = (
        str(previous_subscription.get("status") or "").strip().lower()
        if isinstance(previous_subscription, dict)
        else None
    )
    handled = False
    note: Optional[str] = None

    if isinstance(previous_subscription, dict):
        if not customer_id:
            customer_id = (
                str(previous_subscription.get("stripe_customer_id") or "").strip()
                or None
            )
        if not subscription_id:
            subscription_id = (
                str(previous_subscription.get("stripe_subscription_id") or "").strip()
                or None
            )
        if not current_period_end:
            current_period_end = (
                str(previous_subscription.get("current_period_end") or "").strip()
                or None
            )

    if user_id:
        if event_type == "checkout.session.completed":
            services.store.upsert_subscription(
                user_id=user_id,
                plan_tier="premium",
                status="active",
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                current_period_end=current_period_end,
                cancel_at_period_end=cancel_at_period_end,
                scheduled_plan_tier="free" if cancel_at_period_end else None,
                grace_until=None,
            )
            handled = True
            note = "checkout_completed"
        elif event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
        }:
            if stripe_status in {"active", "trialing"}:
                plan_tier = "premium"
                status = "active"
                applied_grace_until = None
            elif stripe_status in {"past_due", "incomplete", "unpaid"}:
                plan_tier = "premium"
                status = "grace"
                applied_grace_until = grace_until
            elif stripe_status in {"canceled", "paused"}:
                plan_tier = "premium"
                status = "canceled"
                applied_grace_until = None
            else:
                plan_tier = "free"
                status = "canceled"
                applied_grace_until = None

            services.store.upsert_subscription(
                user_id=user_id,
                plan_tier=plan_tier,
                status=status,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                current_period_end=current_period_end,
                cancel_at_period_end=cancel_at_period_end,
                scheduled_plan_tier=(
                    "free" if (cancel_at_period_end or status == "canceled") else None
                ),
                grace_until=applied_grace_until,
            )
            handled = True
            note = f"subscription_{status}"
        elif event_type == "invoice.payment_failed":
            services.store.upsert_subscription(
                user_id=user_id,
                plan_tier="premium",
                status="grace",
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                current_period_end=current_period_end,
                cancel_at_period_end=cancel_at_period_end,
                scheduled_plan_tier="free" if cancel_at_period_end else None,
                grace_until=grace_until,
            )
            handled = True
            note = "invoice_payment_failed"
        elif event_type == "invoice.payment_succeeded":
            services.store.upsert_subscription(
                user_id=user_id,
                plan_tier="premium",
                status="active",
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                current_period_end=current_period_end,
                cancel_at_period_end=cancel_at_period_end,
                scheduled_plan_tier="free" if cancel_at_period_end else None,
                grace_until=None,
            )
            handled = True
            note = "invoice_payment_succeeded"
        elif event_type in {
            "customer.subscription.deleted",
            "customer.subscription.paused",
        }:
            services.store.upsert_subscription(
                user_id=user_id,
                plan_tier="premium",
                status="canceled",
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                current_period_end=current_period_end,
                cancel_at_period_end=False,
                scheduled_plan_tier="free",
                grace_until=None,
            )
            handled = True
            note = "subscription_deleted_or_paused"
    else:
        note = "unmatched_user"

    next_subscription = (
        services.store.get_subscription(user_id=user_id) if user_id else None
    )
    next_plan_tier = (
        services.store.get_effective_plan(
            user_id=user_id, claim_plan_tier="free", role="free"
        )
        if user_id
        else None
    )
    next_status = (
        str(next_subscription.get("status") or "").strip().lower()
        if isinstance(next_subscription, dict)
        else None
    )
    services.store.record_billing_audit_event(
        provider="stripe",
        event_id=event_id,
        event_type=event_type,
        user_id=user_id or None,
        previous_plan_tier=previous_plan_tier,
        next_plan_tier=next_plan_tier,
        previous_status=previous_status,
        next_status=next_status,
        note=note,
        payload=event,
    )

    return {
        "request_id": req_id,
        "status": "processed",
        "event_id": event_id,
        "event_type": event_type,
        "handled": handled,
    }


@router.post("/runs")
async def v2_create_run(
    payload: V2RunRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    api_services = getattr(request.app.state, "api_services", None)
    if api_services is None:
        _raise(
            500,
            code="service_unavailable",
            message="Core API services unavailable",
            request_id=req_id,
        )
    _enforce_heavy_ops_enabled(auth=auth, request_id=req_id)
    idempotency_key = _resolve_idempotency_key(request, request_id=req_id)
    existing_job = _maybe_idempotent_job(
        auth=auth,
        services=services,
        job_type="run",
        idempotency_key=idempotency_key,
    )
    if existing_job:
        return {
            "request_id": req_id,
            "tenant_id": auth.tenant_id,
            "plan_tier": auth.plan_tier,
            "job_id": str(existing_job.get("job_id") or ""),
            "quota_snapshot": _quota_snapshot(auth=auth, services=services),
            "status": str(existing_job.get("status") or "queued"),
            "run_key": existing_job.get("run_key"),
            "idempotent_replay": True,
        }

    try:
        range_days = _resolve_run_span_days(payload)
    except ValueError as exc:
        _raise(400, code="invalid_date_range", message=str(exc), request_id=req_id)

    _enforce_plan_limits_for_heavy_op(
        auth=auth,
        services=services,
        request_id=req_id,
        requested_range_days=range_days,
        api_services=api_services,
    )
    _enforce_global_backlog_limit(services=services, request_id=req_id)

    is_admin = auth.role == "admin" or auth.plan_tier == "admin"
    try:
        resolved_strategy_url = enforce_strategy_url_policy(
            payload.strategy_api_url,
            is_admin=is_admin,
            internal_url=services.internal_strategy_api_url,
        )
    except StrategyApiPolicyError as exc:
        _raise(403, code="strategy_api_forbidden", message=str(exc), request_id=req_id)

    # Persist queued run metadata before launching worker task.
    run_id, ticker, date_label = _run_identity(payload)
    provisional_run_key = f"{run_id}:{ticker}:{date_label}"

    body = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    body["strategy_api_url"] = resolved_strategy_url

    job_id = f"job_{uuid4().hex}"
    services.store.create_job(
        job_id=job_id,
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        job_type="run",
        payload={"run_key": provisional_run_key, "request": body},
        status="queued",
        idempotency_key=idempotency_key,
        max_attempts=_resolve_job_max_attempts(services=services, job_type="run"),
    )
    services.store.upsert_run(
        run_key=provisional_run_key,
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        run_id=run_id,
        ticker=ticker,
        date_label=date_label,
        status="queued",
        metadata={"job_id": job_id, "plan_tier": auth.plan_tier},
    )
    services.store.increment_usage(user_id=auth.user_id, metric="run_start_requests")

    _schedule_job_task(
        services=services,
        job_id=job_id,
        job_coro=_execute_run_job(
            request_payload=body,
            auth=auth,
            job_id=job_id,
            services=services,
            api_services=api_services,
        ),
    )

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "job_id": job_id,
        "quota_snapshot": _quota_snapshot(auth=auth, services=services),
        "status": "queued",
        "run_key": provisional_run_key,
        "idempotency_key": idempotency_key,
    }


@router.post("/adaptive-tuner/run")
async def v2_run_adaptive_tuner(
    payload: V2AdaptiveTunerRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    api_services = getattr(request.app.state, "api_services", None)
    if api_services is None:
        _raise(
            500,
            code="service_unavailable",
            message="Core API services unavailable",
            request_id=req_id,
        )
    _enforce_heavy_ops_enabled(auth=auth, request_id=req_id)
    idempotency_key = _resolve_idempotency_key(request, request_id=req_id)
    existing_job = _maybe_idempotent_job(
        auth=auth,
        services=services,
        job_type="adaptive_tuner",
        idempotency_key=idempotency_key,
    )
    if existing_job:
        return {
            "request_id": req_id,
            "tenant_id": auth.tenant_id,
            "plan_tier": auth.plan_tier,
            "job_id": str(existing_job.get("job_id") or ""),
            "status": str(existing_job.get("status") or "queued"),
            "quota_snapshot": _quota_snapshot(auth=auth, services=services),
            "idempotent_replay": True,
        }

    try:
        range_days = _resolve_date_span_days(payload.date_from, payload.date_to)
    except ValueError as exc:
        _raise(400, code="invalid_date_range", message=str(exc), request_id=req_id)

    _enforce_plan_limits_for_heavy_op(
        auth=auth,
        services=services,
        request_id=req_id,
        requested_range_days=range_days,
        api_services=api_services,
    )
    _enforce_global_backlog_limit(services=services, request_id=req_id)

    is_admin = auth.role == "admin" or auth.plan_tier == "admin"
    try:
        resolved_strategy_url = enforce_strategy_url_policy(
            payload.strategy_api_url,
            is_admin=is_admin,
            internal_url=services.internal_strategy_api_url,
        )
    except StrategyApiPolicyError as exc:
        _raise(403, code="strategy_api_forbidden", message=str(exc), request_id=req_id)

    body = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    body["strategy_api_url"] = resolved_strategy_url

    job_id = f"job_{uuid4().hex}"
    services.store.create_job(
        job_id=job_id,
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        job_type="adaptive_tuner",
        payload={"request": body},
        status="queued",
        idempotency_key=idempotency_key,
        max_attempts=_resolve_job_max_attempts(
            services=services, job_type="adaptive_tuner"
        ),
    )
    services.store.increment_usage(
        user_id=auth.user_id, metric="adaptive_tuner_requests"
    )

    _schedule_job_task(
        services=services,
        job_id=job_id,
        job_coro=_execute_adaptive_tuner_job(
            request_payload=body,
            auth=auth,
            job_id=job_id,
            services=services,
            api_services=api_services,
        ),
    )

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "job_id": job_id,
        "status": "queued",
        "quota_snapshot": _quota_snapshot(auth=auth, services=services),
        "idempotency_key": idempotency_key,
    }


@router.post("/data/download")
async def v2_download_data(
    payload: V2DownloadRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    api_services = getattr(request.app.state, "api_services", None)
    if api_services is None:
        _raise(
            500,
            code="service_unavailable",
            message="Core API services unavailable",
            request_id=req_id,
        )
    _enforce_heavy_ops_enabled(auth=auth, request_id=req_id)
    idempotency_key = _resolve_idempotency_key(request, request_id=req_id)
    existing_job = _maybe_idempotent_job(
        auth=auth,
        services=services,
        job_type="download",
        idempotency_key=idempotency_key,
    )
    if existing_job:
        return {
            "request_id": req_id,
            "tenant_id": auth.tenant_id,
            "plan_tier": auth.plan_tier,
            "job_id": str(existing_job.get("job_id") or ""),
            "status": str(existing_job.get("status") or "queued"),
            "quota_snapshot": _quota_snapshot(auth=auth, services=services),
            "idempotent_replay": True,
        }

    try:
        range_days = _resolve_date_span_days(payload.start_date, payload.end_date)
    except ValueError as exc:
        _raise(400, code="invalid_date_range", message=str(exc), request_id=req_id)

    _enforce_plan_limits_for_heavy_op(
        auth=auth,
        services=services,
        request_id=req_id,
        requested_range_days=range_days,
        api_services=api_services,
    )
    _enforce_global_backlog_limit(services=services, request_id=req_id)

    body = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    job_id = f"job_{uuid4().hex}"
    services.store.create_job(
        job_id=job_id,
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        job_type="download",
        payload={"request": body},
        status="queued",
        idempotency_key=idempotency_key,
        max_attempts=_resolve_job_max_attempts(services=services, job_type="download"),
    )
    services.store.increment_usage(user_id=auth.user_id, metric="download_requests")

    _schedule_job_task(
        services=services,
        job_id=job_id,
        job_coro=_execute_download_job(
            request_payload=body,
            auth=auth,
            job_id=job_id,
            services=services,
            api_services=api_services,
        ),
    )

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "job_id": job_id,
        "status": "queued",
        "quota_snapshot": _quota_snapshot(auth=auth, services=services),
        "idempotency_key": idempotency_key,
    }


@router.get("/jobs/{job_id}")
async def v2_get_job(
    job_id: str,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    services: V2Services = Depends(get_v2_services),
):
    req_id = _request_id(request)
    api_services = getattr(request.app.state, "api_services", None)
    if api_services is not None:
        _sync_user_run_statuses(auth=auth, services=services, api_services=api_services)

    job = services.store.get_job(job_id=job_id)
    if not job:
        _raise(404, code="job_not_found", message="Job not found", request_id=req_id)

    owner_id = str(job.get("user_id") or "")
    is_admin = auth.role == "admin" or auth.plan_tier == "admin"
    if owner_id and owner_id != auth.user_id and not is_admin:
        _raise(
            403,
            code="forbidden",
            message="Job does not belong to current user",
            request_id=req_id,
        )

    if api_services is not None:
        _dispatch_queued_job_if_needed(
            job=job,
            auth=auth,
            services=services,
            api_services=api_services,
        )
        refreshed = services.store.get_job(job_id=job_id)
        if isinstance(refreshed, dict):
            job = refreshed

    return {
        "request_id": req_id,
        "tenant_id": auth.tenant_id,
        "plan_tier": auth.plan_tier,
        "job_id": job_id,
        "job": _format_job_payload(job),
    }
