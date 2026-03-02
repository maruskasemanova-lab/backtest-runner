from __future__ import annotations

import os
from typing import Iterable, List
from urllib.parse import urlparse


class StrategyApiPolicyError(ValueError):
    pass


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def parse_csv_env(name: str, default: str = "") -> List[str]:
    raw = str(os.getenv(name, default) or "").strip()
    if not raw:
        return []
    values: List[str] = []
    seen = set()
    for token in raw.split(","):
        item = token.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        values.append(item)
    return values


def normalize_base_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        raise StrategyApiPolicyError("Strategy API URL is empty")
    if raw.lower() in {"inprocess", "local"}:
        return "http://inprocess"
    parsed = urlparse(raw)
    if parsed.scheme == "inprocess":
        return "http://inprocess"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise StrategyApiPolicyError(
            "Strategy API URL must include http/https scheme and host"
        )
    # Keep path/query/fragment stripped for allowlist comparison.
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def default_internal_strategy_api_url() -> str:
    raw = os.getenv("BACKTEST_INTERNAL_STRATEGY_API_URL", "http://localhost:8001")
    return normalize_base_url(str(raw))


def resolve_strategy_allowlist(internal_url: str | None = None) -> List[str]:
    internal = (
        normalize_base_url(internal_url)
        if internal_url
        else default_internal_strategy_api_url()
    )
    configured = parse_csv_env(
        "BACKTEST_STRATEGY_API_ALLOWLIST",
        "http://localhost:8001,http://127.0.0.1:8001,http://localhost:8012,http://127.0.0.1:8012,http://inprocess",
    )
    values: List[str] = []
    seen = set()
    for candidate in [internal, *configured]:
        try:
            normalized = normalize_base_url(candidate)
        except StrategyApiPolicyError:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        values.append(normalized)
    return values


def enforce_strategy_url_policy(
    requested_url: str,
    *,
    is_admin: bool,
    internal_url: str | None = None,
) -> str:
    internal = (
        normalize_base_url(internal_url)
        if internal_url
        else default_internal_strategy_api_url()
    )
    if not is_admin:
        return internal

    normalized = normalize_base_url(requested_url or internal)
    allowlist = resolve_strategy_allowlist(internal_url=internal)
    if normalized not in allowlist:
        raise StrategyApiPolicyError(
            f"Strategy API URL '{normalized}' is not in allowed list"
        )
    return normalized


def _is_loopback_host(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    hostname = str(parsed.hostname or "").strip().lower()
    return hostname in _LOOPBACK_HOSTS or hostname == "inprocess"


def _resolve_runtime_reachable_strategy_url(
    requested_url: str, internal_url: str
) -> str:
    if _is_loopback_host(requested_url) and not _is_loopback_host(internal_url):
        return internal_url
    return requested_url


def enforce_strategy_url_allowlist_only(requested_url: str) -> str:
    internal = default_internal_strategy_api_url()
    normalized = normalize_base_url(requested_url)
    normalized = _resolve_runtime_reachable_strategy_url(normalized, internal)
    allowlist = resolve_strategy_allowlist(internal_url=internal)
    if normalized not in allowlist:
        raise StrategyApiPolicyError(
            f"Strategy API URL '{normalized}' is not in allowed list"
        )
    return normalized


def cors_allow_origins_from_env(*, env_name: str, default: str) -> List[str]:
    values = parse_csv_env(env_name, default)
    if not values:
        return []
    if "*" in values:
        return ["*"]
    return values


def should_allow_credentials(origins: Iterable[str]) -> bool:
    vals = list(origins)
    return bool(vals) and "*" not in vals
