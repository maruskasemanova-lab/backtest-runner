from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional
from uuid import uuid4

from fastapi import HTTPException
from src.security.network_policy import (
    StrategyApiPolicyError,
    enforce_strategy_url_allowlist_only,
)


@dataclass
class ConfigWriteDeps:
    load_aos_config: Callable[[], Dict[str, Any]]
    save_aos_config: Callable[[Dict[str, Any]], bool]
    load_positioning_config: Callable[[], Dict[str, Any]]
    save_positioning_config: Callable[[Dict[str, Any]], bool]
    get_ticker_positioning_config: Callable[..., Dict[str, Any]]
    normalize_strategy_combo_profiles: Callable[[Any], Any]
    normalize_unified_profiles: Callable[[Any], Any]
    normalize_tuner_profiles: Callable[[Any], Any]
    build_strategy_combo_profile_entry: Callable[..., Dict[str, Any]]
    fetch_remote_strategies: Callable[[str], Awaitable[Any]]
    extract_strategy_params_for_profile: Callable[[Any], Dict[str, Any]]
    apply_strategy_param_map: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]
    build_v2_candidate_config: Callable[..., Dict[str, Any]]
    build_adaptive_candidate_config: Callable[..., Dict[str, Any]]
    normalize_non_negative_int: Callable[..., Any]
    positioning_config_keys: Iterable[str]
    logger: Any
    load_unified_profile_state: Optional[
        Callable[[str], tuple[List[Dict[str, Any]], Optional[str]]]
    ] = None
    save_unified_profile_state: Optional[
        Callable[[str, List[Dict[str, Any]], Optional[str]], None]
    ] = None


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize_trading_hours(raw_hours: Any) -> List[int]:
    if not isinstance(raw_hours, list):
        return []
    normalized: List[int] = []
    seen = set()
    for item in raw_hours:
        try:
            hour = int(item)
        except (TypeError, ValueError):
            continue
        if hour < 0 or hour > 23 or hour in seen:
            continue
        seen.add(hour)
        normalized.append(hour)
    return sorted(normalized)


def _resolve_active_adaptive_candidate(
    *,
    ticker_cfg: Dict[str, Any],
    normalize_tuner_profiles: Callable[[Any], Any],
) -> Dict[str, Any]:
    active_profile_id = str(
        ticker_cfg.get("active_adaptive_tuner_profile_id", "")
    ).strip()
    if not active_profile_id:
        return {}
    profiles = normalize_tuner_profiles(ticker_cfg.get("adaptive_tuner_profiles", []))
    if not isinstance(profiles, list):
        return {}
    target_profile = next(
        (
            profile
            for profile in profiles
            if str(profile.get("profile_id", "")).strip() == active_profile_id
        ),
        None,
    )
    if not isinstance(target_profile, dict):
        return {}
    candidate = target_profile.get("candidate")
    if isinstance(candidate, dict):
        return dict(candidate)
    best_trial = target_profile.get("best_trial")
    if isinstance(best_trial, dict) and isinstance(best_trial.get("candidate"), dict):
        return dict(best_trial.get("candidate", {}))
    return {}


def _build_strategy_profile_snapshot(
    *,
    ticker_cfg: Dict[str, Any],
    strategy_params: Dict[str, Dict[str, Any]],
    normalize_tuner_profiles: Callable[[Any], Any],
    positioning_config_keys: Iterable[str],
) -> Dict[str, Any]:
    strategy_profile: Dict[str, Any] = {
        "strategy_params": strategy_params if isinstance(strategy_params, dict) else {},
    }
    for key in (
        "strategy_selection_mode",
        "max_active_strategies",
        "time_filter_enabled",
        "long_only",
        "adverse_flow_consistency_threshold",
        "adverse_book_pressure_threshold",
    ):
        if key in ticker_cfg:
            strategy_profile[key] = ticker_cfg.get(key)

    trading_hours = _normalize_trading_hours(ticker_cfg.get("trading_hours"))
    if trading_hours:
        strategy_profile["trading_hours"] = trading_hours

    l2_cfg = ticker_cfg.get("l2")
    if isinstance(l2_cfg, dict):
        strategy_profile["l2"] = dict(l2_cfg)
    adaptive_cfg = ticker_cfg.get("adaptive")
    if isinstance(adaptive_cfg, dict):
        strategy_profile["adaptive"] = dict(adaptive_cfg)

    active_combo_profile_id = str(
        ticker_cfg.get("active_strategy_combo_profile_id", "")
    ).strip()
    if active_combo_profile_id:
        strategy_profile["active_strategy_combo_profile_id"] = active_combo_profile_id

    active_adaptive_profile_id = str(
        ticker_cfg.get("active_adaptive_tuner_profile_id", "")
    ).strip()
    if active_adaptive_profile_id:
        strategy_profile["active_adaptive_tuner_profile_id"] = (
            active_adaptive_profile_id
        )
        active_candidate = _resolve_active_adaptive_candidate(
            ticker_cfg=ticker_cfg,
            normalize_tuner_profiles=normalize_tuner_profiles,
        )
        if active_candidate:
            strategy_profile["adaptive_candidate"] = active_candidate

    # Preserve all other strategy-side config fields so FE tabs can show
    # complete strategy profile context in one place.
    excluded_keys = {
        "strategy_combo_profiles",
        "adaptive_tuner_profiles",
        "unified_profiles",
        "active_unified_profile_id",
        "positioning",
    }
    excluded_keys.update(str(key) for key in positioning_config_keys)
    for key, value in ticker_cfg.items():
        key_str = str(key)
        if key_str in excluded_keys or key_str in strategy_profile:
            continue
        if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
            strategy_profile[key_str] = value
    return strategy_profile


def _build_execution_profile_snapshot(
    *,
    ticker_cfg: Dict[str, Any],
    positioning_cfg: Dict[str, Any],
    positioning_config_keys: Iterable[str],
) -> Dict[str, Any]:
    execution_profile: Dict[str, Any] = {}
    positioning_payload: Dict[str, Any] = {}

    for key in positioning_config_keys:
        if key in ticker_cfg:
            positioning_payload[key] = ticker_cfg.get(key)
        if key in positioning_cfg:
            positioning_payload[key] = positioning_cfg.get(key)

    inline_positioning = ticker_cfg.get("positioning")
    if isinstance(inline_positioning, dict):
        for key, value in inline_positioning.items():
            positioning_payload[key] = value

    if positioning_payload:
        execution_profile["positioning"] = positioning_payload
    return execution_profile


def _load_unified_profile_state(
    *,
    ticker: str,
    ticker_cfg: Dict[str, Any],
    deps: ConfigWriteDeps,
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    external_loader = getattr(deps, "load_unified_profile_state", None)
    if callable(external_loader):
        loaded_profiles, loaded_active = external_loader(ticker)
        normalized_profiles = deps.normalize_unified_profiles(loaded_profiles)
        active_profile_id = str(loaded_active or "").strip() or None
        if active_profile_id:
            known_profile_ids = {
                str(row.get("profile_id") or "").strip()
                for row in normalized_profiles
                if isinstance(row, dict)
            }
            if active_profile_id not in known_profile_ids:
                active_profile_id = None
        return normalized_profiles, active_profile_id

    profiles = deps.normalize_unified_profiles(ticker_cfg.get("unified_profiles", []))
    active_profile_id = str(ticker_cfg.get("active_unified_profile_id") or "").strip() or None
    if active_profile_id:
        known_profile_ids = {
            str(row.get("profile_id") or "").strip()
            for row in profiles
            if isinstance(row, dict)
        }
        if active_profile_id not in known_profile_ids:
            active_profile_id = None
    return profiles, active_profile_id


def _save_unified_profile_state(
    *,
    ticker: str,
    ticker_cfg: Dict[str, Any],
    profiles: List[Dict[str, Any]],
    active_profile_id: Optional[str],
    deps: ConfigWriteDeps,
) -> bool:
    external_saver = getattr(deps, "save_unified_profile_state", None)
    if callable(external_saver):
        external_saver(ticker, profiles, active_profile_id)
        return False

    ticker_cfg["unified_profiles"] = profiles
    ticker_cfg["active_unified_profile_id"] = str(active_profile_id or "").strip()
    return True


def _clear_local_unified_profile_state(ticker_cfg: Dict[str, Any]) -> bool:
    changed = False
    if "unified_profiles" in ticker_cfg:
        ticker_cfg.pop("unified_profiles", None)
        changed = True
    if "active_unified_profile_id" in ticker_cfg:
        ticker_cfg.pop("active_unified_profile_id", None)
        changed = True
    return changed


async def capture_unified_profile(
    request: Any, deps: ConfigWriteDeps
) -> Dict[str, Any]:
    ticker = str(request.ticker or "").upper().strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")

    profile_name = str(request.profile_name or "").strip()
    if not profile_name:
        profile_name = f"{ticker}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    try:
        strategy_api_url = enforce_strategy_url_allowlist_only(request.strategy_api_url)
    except StrategyApiPolicyError as exc:
        raise HTTPException(400, str(exc))

    strategies_payload = await deps.fetch_remote_strategies(strategy_api_url)
    strategy_params = deps.extract_strategy_params_for_profile(strategies_payload)
    if not strategy_params:
        raise HTTPException(400, "No strategy parameters available to capture.")

    config = deps.load_aos_config()
    positioning_config = deps.load_positioning_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    positioning_tickers = positioning_config.get("tickers")
    if not isinstance(positioning_tickers, dict):
        positioning_tickers = {}
        positioning_config["tickers"] = positioning_tickers
    positioning_ticker_cfg = positioning_tickers.get(ticker, {})
    if not isinstance(positioning_ticker_cfg, dict):
        positioning_ticker_cfg = {}

    profiles, active_profile_id = _load_unified_profile_state(
        ticker=ticker,
        ticker_cfg=ticker_cfg,
        deps=deps,
    )

    strategy_profile = _build_strategy_profile_snapshot(
        ticker_cfg=ticker_cfg,
        strategy_params=strategy_params,
        normalize_tuner_profiles=deps.normalize_tuner_profiles,
        positioning_config_keys=deps.positioning_config_keys,
    )
    execution_profile = _build_execution_profile_snapshot(
        ticker_cfg=ticker_cfg,
        positioning_cfg=positioning_ticker_cfg,
        positioning_config_keys=deps.positioning_config_keys,
    )
    source_combo_profile_id = str(
        strategy_profile.get("active_strategy_combo_profile_id", "")
    ).strip()
    source_adaptive_profile_id = str(
        strategy_profile.get("active_adaptive_tuner_profile_id", "")
    ).strip()
    now = _utc_now_iso()
    entry = {
        "profile_id": uuid4().hex[:12],
        "profile_name": profile_name,
        "created_at": now,
        "updated_at": now,
        "strategy_profile": strategy_profile,
        "execution_profile": execution_profile,
    }
    if source_combo_profile_id:
        entry["source_strategy_combo_profile_id"] = source_combo_profile_id
    if source_adaptive_profile_id:
        entry["source_adaptive_tuner_profile_id"] = source_adaptive_profile_id

    profiles.insert(0, entry)
    profiles = profiles[:30]
    if request.set_active:
        active_profile_id = entry["profile_id"]

    saved_to_local_config = _save_unified_profile_state(
        ticker=ticker,
        ticker_cfg=ticker_cfg,
        profiles=profiles,
        active_profile_id=active_profile_id,
        deps=deps,
    )
    config_changed = False
    if saved_to_local_config:
        config_changed = True
    elif _clear_local_unified_profile_state(ticker_cfg):
        config_changed = True
    if config_changed:
        config["tickers"][ticker] = ticker_cfg
        if not deps.save_aos_config(config):
            raise HTTPException(500, "Failed to save unified profile")

    return {
        "success": True,
        "ticker": ticker,
        "profile": entry,
        "active_profile_id": active_profile_id or None,
    }


async def apply_unified_profile(request: Any, deps: ConfigWriteDeps) -> Dict[str, Any]:
    ticker = str(request.ticker or "").upper().strip()
    profile_id = str(request.profile_id or "").strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")
    if not profile_id:
        raise HTTPException(400, "profile_id is required")

    config = deps.load_aos_config()
    positioning_config = deps.load_positioning_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    profiles, _active_profile_id = _load_unified_profile_state(
        ticker=ticker,
        ticker_cfg=ticker_cfg,
        deps=deps,
    )
    target_profile = next(
        (
            profile
            for profile in profiles
            if str(profile.get("profile_id", "")).strip() == profile_id
        ),
        None,
    )
    if not isinstance(target_profile, dict):
        raise HTTPException(404, f"Unified profile not found: {profile_id}")

    saved_to_local_config = _save_unified_profile_state(
        ticker=ticker,
        ticker_cfg=ticker_cfg,
        profiles=profiles,
        active_profile_id=profile_id,
        deps=deps,
    )
    config_changed = bool(saved_to_local_config)
    if not saved_to_local_config and _clear_local_unified_profile_state(ticker_cfg):
        config_changed = True

    strategy_profile = target_profile.get("strategy_profile")
    if not isinstance(strategy_profile, dict):
        strategy_profile = {}
    execution_profile = target_profile.get("execution_profile")
    if not isinstance(execution_profile, dict):
        execution_profile = {}

    applied_execution = False
    if bool(getattr(request, "apply_execution", True)):
        config_changed = True
        mode_value = strategy_profile.get("strategy_selection_mode")
        if isinstance(mode_value, str) and mode_value.strip():
            ticker_cfg["strategy_selection_mode"] = mode_value.strip().lower()

        if "max_active_strategies" in strategy_profile:
            try:
                max_active = int(strategy_profile.get("max_active_strategies"))
            except (TypeError, ValueError):
                max_active = 3
            ticker_cfg["max_active_strategies"] = max(1, min(20, max_active))

        if "time_filter_enabled" in strategy_profile:
            ticker_cfg["time_filter_enabled"] = bool(
                strategy_profile.get("time_filter_enabled")
            )
        if "long_only" in strategy_profile:
            ticker_cfg["long_only"] = bool(strategy_profile.get("long_only"))

        hours = _normalize_trading_hours(strategy_profile.get("trading_hours"))
        if hours:
            ticker_cfg["trading_hours"] = hours

        for key in (
            "adverse_flow_consistency_threshold",
            "adverse_book_pressure_threshold",
        ):
            if key not in strategy_profile:
                continue
            try:
                ticker_cfg[key] = float(strategy_profile.get(key))
            except (TypeError, ValueError):
                continue

        l2_cfg = strategy_profile.get("l2")
        if isinstance(l2_cfg, dict):
            ticker_cfg["l2"] = dict(l2_cfg)
        adaptive_cfg = strategy_profile.get("adaptive")
        if isinstance(adaptive_cfg, dict):
            ticker_cfg["adaptive"] = dict(adaptive_cfg)

        source_combo_profile_id = str(
            target_profile.get("source_strategy_combo_profile_id")
            or strategy_profile.get("active_strategy_combo_profile_id")
            or ""
        ).strip()
        if source_combo_profile_id:
            ticker_cfg["active_strategy_combo_profile_id"] = source_combo_profile_id
        source_adaptive_profile_id = str(
            target_profile.get("source_adaptive_tuner_profile_id")
            or strategy_profile.get("active_adaptive_tuner_profile_id")
            or ""
        ).strip()
        if source_adaptive_profile_id:
            ticker_cfg["active_adaptive_tuner_profile_id"] = source_adaptive_profile_id

        positioning_payload = {}
        inline_positioning = execution_profile.get("positioning")
        if isinstance(inline_positioning, dict):
            positioning_payload.update(inline_positioning)
        for key in deps.positioning_config_keys:
            if key in execution_profile:
                positioning_payload[key] = execution_profile.get(key)

        if positioning_payload:
            pos_tickers = positioning_config.get("tickers")
            if not isinstance(pos_tickers, dict):
                pos_tickers = {}
                positioning_config["tickers"] = pos_tickers
            existing_pos = pos_tickers.get(ticker, {})
            if not isinstance(existing_pos, dict):
                existing_pos = {}
            existing_pos.update(positioning_payload)
            pos_tickers[ticker] = existing_pos
            applied_execution = True

    if config_changed:
        config["tickers"][ticker] = ticker_cfg
        if not deps.save_aos_config(config):
            raise HTTPException(500, "Failed to save active unified profile")
    if applied_execution and not deps.save_positioning_config(positioning_config):
        raise HTTPException(
            500, "Failed to save positioning config for unified profile"
        )

    apply_result: Dict[str, Any] = {}
    if bool(getattr(request, "apply_now", True)):
        try:
            strategy_api_url = enforce_strategy_url_allowlist_only(
                request.strategy_api_url
            )
        except StrategyApiPolicyError as exc:
            raise HTTPException(400, str(exc))
        strategy_params = (
            strategy_profile.get("strategy_params")
            if isinstance(strategy_profile.get("strategy_params"), dict)
            else {}
        )
        if strategy_params:
            apply_result = await deps.apply_strategy_param_map(
                strategy_api_url, strategy_params
            )

    return {
        "success": True,
        "ticker": ticker,
        "profile_id": profile_id,
        "profile_name": str(target_profile.get("profile_name") or profile_id),
        "apply_now": bool(getattr(request, "apply_now", True)),
        "apply_execution": bool(getattr(request, "apply_execution", True)),
        "applied_execution": applied_execution,
        "apply_result": apply_result,
    }


async def capture_strategy_combo(request: Any, deps: ConfigWriteDeps) -> Dict[str, Any]:
    ticker = str(request.ticker or "").upper().strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")

    profile_name = str(request.profile_name or "").strip()
    if not profile_name:
        from datetime import datetime

        profile_name = f"{ticker}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    try:
        strategy_api_url = enforce_strategy_url_allowlist_only(request.strategy_api_url)
    except StrategyApiPolicyError as exc:
        raise HTTPException(400, str(exc))

    strategies_payload = await deps.fetch_remote_strategies(strategy_api_url)
    strategy_params = deps.extract_strategy_params_for_profile(strategies_payload)
    if not strategy_params:
        raise HTTPException(400, "No strategy parameters available to capture.")

    config = deps.load_aos_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    profiles = deps.normalize_strategy_combo_profiles(
        ticker_cfg.get("strategy_combo_profiles", [])
    )
    entry = deps.build_strategy_combo_profile_entry(
        ticker=ticker,
        profile_name=profile_name,
        strategy_params=strategy_params,
    )
    profiles.insert(0, entry)
    ticker_cfg["strategy_combo_profiles"] = profiles[:30]
    if request.set_active:
        ticker_cfg["active_strategy_combo_profile_id"] = entry["profile_id"]
    config["tickers"][ticker] = ticker_cfg
    if not deps.save_aos_config(config):
        raise HTTPException(500, "Failed to save strategy combo profile")

    return {
        "success": True,
        "ticker": ticker,
        "profile": entry,
        "active_profile_id": str(
            ticker_cfg.get("active_strategy_combo_profile_id", "")
        ).strip()
        or None,
    }


async def apply_strategy_combo(request: Any, deps: ConfigWriteDeps) -> Dict[str, Any]:
    ticker = str(request.ticker or "").upper().strip()
    profile_id = str(request.profile_id or "").strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")
    if not profile_id:
        raise HTTPException(400, "profile_id is required")

    config = deps.load_aos_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    profiles = deps.normalize_strategy_combo_profiles(
        ticker_cfg.get("strategy_combo_profiles", [])
    )
    target_profile = next(
        (
            profile
            for profile in profiles
            if str(profile.get("profile_id")) == profile_id
        ),
        None,
    )
    if not isinstance(target_profile, dict):
        raise HTTPException(404, f"Strategy combo profile not found: {profile_id}")

    ticker_cfg["strategy_combo_profiles"] = profiles
    ticker_cfg["active_strategy_combo_profile_id"] = profile_id
    config["tickers"][ticker] = ticker_cfg
    if not deps.save_aos_config(config):
        raise HTTPException(500, "Failed to save active strategy combo profile")

    try:
        strategy_api_url = enforce_strategy_url_allowlist_only(request.strategy_api_url)
    except StrategyApiPolicyError as exc:
        raise HTTPException(400, str(exc))

    apply_result: Dict[str, Any] = {}
    if request.apply_now:
        strategy_params = target_profile.get("strategy_params", {})
        if isinstance(strategy_params, dict):
            apply_result = await deps.apply_strategy_param_map(
                strategy_api_url,
                strategy_params,
            )

    return {
        "success": True,
        "ticker": ticker,
        "profile_id": profile_id,
        "profile_name": str(target_profile.get("profile_name") or profile_id),
        "apply_now": bool(request.apply_now),
        "apply_result": apply_result,
    }


def update_aos_config(request: Any, deps: ConfigWriteDeps) -> Dict[str, Any]:
    config = deps.load_aos_config()
    positioning_config = deps.load_positioning_config()

    if "tickers" not in config:
        config["tickers"] = {}
    if "tickers" not in positioning_config:
        positioning_config["tickers"] = {}

    ticker_upper = request.ticker.upper()
    incoming_config = dict(request.config or {})
    positioning_marker = object()
    incoming_positioning = incoming_config.pop("positioning", positioning_marker)

    legacy_positioning_payload: Dict[str, Any] = {}
    for key in deps.positioning_config_keys:
        if key in incoming_config:
            legacy_positioning_payload[key] = incoming_config.pop(key)
    if legacy_positioning_payload:
        if incoming_positioning is positioning_marker:
            incoming_positioning = {}
        if incoming_positioning is None:
            incoming_positioning = {}
        if isinstance(incoming_positioning, dict):
            incoming_positioning = {
                **legacy_positioning_payload,
                **incoming_positioning,
            }
        else:
            raise HTTPException(400, "positioning must be an object or null")

    existing = config["tickers"].get(ticker_upper, {})
    if not isinstance(existing, dict):
        existing = {}
    existing.pop("positioning", None)
    for key in deps.positioning_config_keys:
        existing.pop(key, None)
    existing.update(incoming_config)
    config["tickers"][ticker_upper] = existing

    if incoming_positioning is not positioning_marker:
        if incoming_positioning is None:
            if isinstance(positioning_config.get("tickers"), dict):
                positioning_config["tickers"].pop(ticker_upper, None)
        elif isinstance(incoming_positioning, dict):
            pos_tickers = positioning_config.get("tickers")
            if not isinstance(pos_tickers, dict):
                pos_tickers = {}
                positioning_config["tickers"] = pos_tickers
            pos_existing = pos_tickers.get(ticker_upper, {})
            if not isinstance(pos_existing, dict):
                pos_existing = {}
            pos_existing.update(incoming_positioning)
            pos_tickers[ticker_upper] = pos_existing
        else:
            raise HTTPException(400, "positioning must be an object or null")

    saved_aos = deps.save_aos_config(config)
    saved_positioning = deps.save_positioning_config(positioning_config)
    if not (saved_aos and saved_positioning):
        raise HTTPException(500, "Failed to save AOS config")

    deps.logger.info("Updated AOS config for %s: %s", ticker_upper, incoming_config)
    if incoming_positioning is not positioning_marker:
        deps.logger.info(
            "Updated positioning config for %s: %s", ticker_upper, incoming_positioning
        )
    payload = dict(existing)
    merged_positioning = deps.get_ticker_positioning_config(
        ticker_upper, positioning_config
    )
    if merged_positioning:
        payload["positioning"] = merged_positioning
    return {"success": True, "config": payload}


def update_positioning_config(request: Any, deps: ConfigWriteDeps) -> Dict[str, Any]:
    ticker_upper = str(request.ticker or "").upper().strip()
    if not ticker_upper:
        raise HTTPException(400, "ticker is required")
    incoming = dict(request.config or {})
    cfg = deps.load_positioning_config()
    tickers = cfg.get("tickers")
    if not isinstance(tickers, dict):
        tickers = {}
        cfg["tickers"] = tickers
    existing = tickers.get(ticker_upper, {})
    if not isinstance(existing, dict):
        existing = {}
    existing.update(incoming)
    tickers[ticker_upper] = existing
    if not deps.save_positioning_config(cfg):
        raise HTTPException(500, "Failed to save positioning config")
    deps.logger.info("Updated positioning config for %s: %s", ticker_upper, incoming)
    return {"success": True, "config": existing}


def apply_adaptive_tuner_profile(request: Any, deps: ConfigWriteDeps) -> Dict[str, Any]:
    ticker = str(request.ticker or "").upper().strip()
    profile_id = str(request.profile_id or "").strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")
    if not profile_id:
        raise HTTPException(400, "profile_id is required")

    config = deps.load_aos_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    profiles = deps.normalize_tuner_profiles(
        ticker_cfg.get("adaptive_tuner_profiles", [])
    )
    target_profile = next(
        (
            profile
            for profile in profiles
            if str(profile.get("profile_id")) == profile_id
        ),
        None,
    )
    if not isinstance(target_profile, dict):
        raise HTTPException(404, f"Adaptive tuner profile not found: {profile_id}")

    best_candidate = target_profile.get("candidate", {})
    adaptive_version = (
        deps.normalize_non_negative_int(
            target_profile.get("adaptive_version", 1),
            default=1,
            max_value=10,
        )
        or 1
    )
    safe_candidate = best_candidate if isinstance(best_candidate, dict) else {}
    if adaptive_version >= 2:
        updated_cfg = deps.build_v2_candidate_config(
            ticker_cfg,
            safe_candidate,
            adaptive_version=adaptive_version,
        )
    else:
        updated_cfg = deps.build_adaptive_candidate_config(
            ticker_cfg,
            safe_candidate,
            adaptive_version=adaptive_version,
        )
    updated_cfg["adaptive_tuner_profiles"] = profiles
    updated_cfg["active_adaptive_tuner_profile_id"] = profile_id
    # Keep unified/adaptive UI views aligned: once user explicitly applies a tuned
    # adaptive profile, clear any stale explicit unified active profile so callers
    # fall back to the current combo+adaptive derived active view.
    updated_cfg["active_unified_profile_id"] = ""
    config["tickers"][ticker] = updated_cfg

    if not deps.save_aos_config(config):
        raise HTTPException(500, "Failed to apply adaptive tuner profile")

    return {
        "success": True,
        "ticker": ticker,
        "profile_id": profile_id,
        "applied_candidate": best_candidate if isinstance(best_candidate, dict) else {},
    }
