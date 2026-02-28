from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from uuid import uuid4


def normalize_profile_scope(scope: str) -> str:
    normalized = str(scope or "").strip().lower()
    if normalized not in {"user", "global"}:
        raise ValueError("scope must be 'user' or 'global'")
    return normalized


def build_adaptive_strategy_profile_record(
    *,
    profile_id: Optional[str],
    scope: str,
    owner_user_id: Optional[str],
    owner_tenant_id: Optional[str],
    ticker: str,
    profile_name: str,
    adaptive_version: int,
    candidate: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    normalized_scope = normalize_profile_scope(scope)
    normalized_ticker = str(ticker or "").strip().upper()
    normalized_name = str(profile_name or "").strip()
    normalized_id = str(profile_id or "").strip() or f"asp_{uuid4().hex[:16]}"
    normalized_version = max(1, int(adaptive_version or 1))

    if not normalized_ticker:
        raise ValueError("ticker is required")
    if not normalized_name:
        raise ValueError("profile_name is required")

    if normalized_scope == "global":
        normalized_owner_user = None
        normalized_owner_tenant = None
    else:
        normalized_owner_user = str(owner_user_id or "").strip()
        normalized_owner_tenant = str(owner_tenant_id or "").strip()
        if not normalized_owner_user or not normalized_owner_tenant:
            raise ValueError(
                "user scope profile requires owner_user_id and owner_tenant_id"
            )

    return {
        "profile_id": normalized_id,
        "scope": normalized_scope,
        "owner_user_id": normalized_owner_user,
        "owner_tenant_id": normalized_owner_tenant,
        "ticker": normalized_ticker,
        "profile_name": normalized_name,
        "adaptive_version": normalized_version,
        "candidate": candidate if isinstance(candidate, dict) else {},
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def build_list_adaptive_strategy_profiles_query(
    *,
    user_id: str,
    tenant_id: str,
    ticker: Optional[str] = None,
    include_user: bool = True,
    include_global: bool = True,
) -> Optional[Tuple[str, tuple[Any, ...]]]:
    visibility_clauses: list[str] = []
    args: list[Any] = []
    normalized_user = str(user_id or "").strip()
    normalized_tenant = str(tenant_id or "").strip()

    if include_user and normalized_user and normalized_tenant:
        visibility_clauses.append(
            "(scope = 'user' AND owner_user_id = ? AND owner_tenant_id = ?)"
        )
        args.extend([normalized_user, normalized_tenant])
    if include_global:
        visibility_clauses.append("(scope = 'global')")
    if not visibility_clauses:
        return None

    clauses = ["(" + " OR ".join(visibility_clauses) + ")"]
    if ticker:
        clauses.append("ticker = ?")
        args.append(str(ticker).strip().upper())

    query = "SELECT * FROM adaptive_strategy_profiles WHERE " + " AND ".join(clauses)
    query += (
        " ORDER BY CASE WHEN scope = 'global' THEN 0 ELSE 1 END,"
        " updated_at DESC, profile_id ASC"
    )
    return query, tuple(args)
