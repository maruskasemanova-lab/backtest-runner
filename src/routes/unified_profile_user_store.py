from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

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
from src.services.config_write_service import ConfigWriteDeps
from src.services.saas_service import V2Services
from src.services.unified_profile_user_settings_service import (
    build_unified_profile_settings_patch,
    build_unified_profile_state_from_settings,
    merge_unified_profile_options_payload,
)


def _local_profile_user_id() -> str:
    token = str(
        os.getenv("BACKTEST_LOCAL_PROFILE_USER_ID")
        or os.getenv("BACKTEST_DEFAULT_USER_ID")
        or "local-dev-user"
    ).strip()
    return token or "local-dev-user"


def _local_profile_tenant_id(user_id: str) -> str:
    tenant = str(
        os.getenv("BACKTEST_LOCAL_PROFILE_TENANT_ID")
        or os.getenv("BACKTEST_DEFAULT_TENANT_ID")
        or ""
    ).strip()
    return tenant or f"tenant_{user_id}"


def _settings_store_for_user(services: V2Services):
    candidate = getattr(services, "user_settings_store", None)
    if candidate is not None:
        return candidate
    return getattr(services, "store", None)


def _resolve_v2_services(request: Request) -> V2Services:
    services = getattr(request.app.state, "v2_services", None)
    if isinstance(services, V2Services):
        return services
    raise HTTPException(status_code=500, detail="v2 services are not initialized")


def resolve_profile_store_context(request: Request) -> tuple[AuthContext, Any]:
    services = _resolve_v2_services(request)
    auth_header = str(request.headers.get("Authorization") or "").strip()
    if auth_header:
        try:
            token = parse_bearer_token(auth_header)
            payload = decode_and_verify_jwt(
                token,
                secret=resolve_jwt_secret(),
                allow_unverified=allow_unverified_jwt(),
            )
        except JwtValidationError as exc:
            raise HTTPException(status_code=401, detail=str(exc))

        base_auth = build_auth_context(payload)
        effective_plan = services.store.get_effective_plan(
            user_id=base_auth.user_id,
            claim_plan_tier=extract_plan_tier(payload, base_auth.role),
            role=base_auth.role,
        )
        auth = build_auth_context(payload, plan_tier_override=effective_plan)
    else:
        local_user_id = _local_profile_user_id()
        auth = AuthContext(
            user_id=local_user_id,
            tenant_id=_local_profile_tenant_id(local_user_id),
            role="admin",
            plan_tier="admin",
            email=None,
            claims={"source": "local_profile_fallback"},
        )

    services.store.ensure_identity(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        role=auth.role,
        email=auth.email,
    )
    settings_store = _settings_store_for_user(services)
    if settings_store is None:
        raise HTTPException(status_code=500, detail="user settings store is not initialized")
    return auth, settings_store


def migrate_ticker_profiles_from_json_if_needed(
    *,
    auth: AuthContext,
    settings_store: Any,
    ticker: str,
    load_aos_config,
    normalize_unified_profiles,
) -> None:
    ticker_upper = str(ticker or "").upper().strip()
    if not ticker_upper:
        return

    settings = settings_store.get_user_settings(user_id=auth.user_id)
    state = build_unified_profile_state_from_settings(
        settings=settings,
        ticker=ticker_upper,
        normalize_unified_profiles=normalize_unified_profiles,
    )
    if state["profiles"] or state.get("active_profile_id"):
        return

    aos_cfg = load_aos_config()
    ticker_cfg = aos_cfg.get("tickers", {}).get(ticker_upper, {})
    if not isinstance(ticker_cfg, dict):
        return

    json_profiles = normalize_unified_profiles(ticker_cfg.get("unified_profiles", []))
    json_active_profile_id = str(ticker_cfg.get("active_unified_profile_id") or "").strip() or None
    if not json_profiles and not json_active_profile_id:
        return

    patch = build_unified_profile_settings_patch(
        settings=settings,
        ticker=ticker_upper,
        profiles=json_profiles,
        active_profile_id=json_active_profile_id,
    )
    settings_store.merge_user_settings(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        patch=patch,
    )


def build_user_unified_profile_options_payload(
    *,
    request: Request,
    ticker: str,
    base_payload: Dict[str, Any],
    load_aos_config,
    normalize_unified_profiles,
) -> Dict[str, Any]:
    auth, settings_store = resolve_profile_store_context(request)
    migrate_ticker_profiles_from_json_if_needed(
        auth=auth,
        settings_store=settings_store,
        ticker=ticker,
        load_aos_config=load_aos_config,
        normalize_unified_profiles=normalize_unified_profiles,
    )
    settings = settings_store.get_user_settings(user_id=auth.user_id)
    state = build_unified_profile_state_from_settings(
        settings=settings,
        ticker=ticker,
        normalize_unified_profiles=normalize_unified_profiles,
    )
    return merge_unified_profile_options_payload(
        base_payload=base_payload,
        user_profiles=state["profiles"],
        user_active_profile_id=state["active_profile_id"],
    )


def bind_user_unified_profile_store_callbacks(
    *,
    request: Request,
    ticker: str,
    load_aos_config,
    deps: ConfigWriteDeps,
) -> None:
    auth, settings_store = resolve_profile_store_context(request)
    migrate_ticker_profiles_from_json_if_needed(
        auth=auth,
        settings_store=settings_store,
        ticker=ticker,
        load_aos_config=load_aos_config,
        normalize_unified_profiles=deps.normalize_unified_profiles,
    )

    def _load_state(target_ticker: str) -> tuple[list[Dict[str, Any]], Optional[str]]:
        settings = settings_store.get_user_settings(user_id=auth.user_id)
        state = build_unified_profile_state_from_settings(
            settings=settings,
            ticker=target_ticker,
            normalize_unified_profiles=deps.normalize_unified_profiles,
        )
        return state["profiles"], state["active_profile_id"]

    def _save_state(
        target_ticker: str,
        profiles: list[Dict[str, Any]],
        active_profile_id: Optional[str],
    ) -> None:
        settings = settings_store.get_user_settings(user_id=auth.user_id)
        patch = build_unified_profile_settings_patch(
            settings=settings,
            ticker=target_ticker,
            profiles=profiles,
            active_profile_id=active_profile_id,
        )
        settings_store.merge_user_settings(
            user_id=auth.user_id,
            tenant_id=auth.tenant_id,
            patch=patch,
        )

    deps.load_unified_profile_state = _load_state
    deps.save_unified_profile_state = _save_state
