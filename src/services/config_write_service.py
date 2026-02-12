from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable

from fastapi import HTTPException


@dataclass
class ConfigWriteDeps:
    load_aos_config: Callable[[], Dict[str, Any]]
    save_aos_config: Callable[[Dict[str, Any]], bool]
    load_positioning_config: Callable[[], Dict[str, Any]]
    save_positioning_config: Callable[[Dict[str, Any]], bool]
    get_ticker_positioning_config: Callable[..., Dict[str, Any]]
    normalize_strategy_combo_profiles: Callable[[Any], Any]
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


async def capture_strategy_combo(request: Any, deps: ConfigWriteDeps) -> Dict[str, Any]:
    ticker = str(request.ticker or "").upper().strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")

    profile_name = str(request.profile_name or "").strip()
    if not profile_name:
        from datetime import datetime

        profile_name = f"{ticker}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    strategies_payload = await deps.fetch_remote_strategies(request.strategy_api_url)
    strategy_params = deps.extract_strategy_params_for_profile(strategies_payload)
    if not strategy_params:
        raise HTTPException(400, "No strategy parameters available to capture.")

    config = deps.load_aos_config()
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    ticker_cfg = config["tickers"].get(ticker, {})
    if not isinstance(ticker_cfg, dict):
        ticker_cfg = {}

    profiles = deps.normalize_strategy_combo_profiles(ticker_cfg.get("strategy_combo_profiles", []))
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
        "active_profile_id": str(ticker_cfg.get("active_strategy_combo_profile_id", "")).strip() or None,
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

    profiles = deps.normalize_strategy_combo_profiles(ticker_cfg.get("strategy_combo_profiles", []))
    target_profile = next(
        (profile for profile in profiles if str(profile.get("profile_id")) == profile_id),
        None,
    )
    if not isinstance(target_profile, dict):
        raise HTTPException(404, f"Strategy combo profile not found: {profile_id}")

    ticker_cfg["strategy_combo_profiles"] = profiles
    ticker_cfg["active_strategy_combo_profile_id"] = profile_id
    config["tickers"][ticker] = ticker_cfg
    if not deps.save_aos_config(config):
        raise HTTPException(500, "Failed to save active strategy combo profile")

    apply_result: Dict[str, Any] = {}
    if request.apply_now:
        strategy_params = target_profile.get("strategy_params", {})
        if isinstance(strategy_params, dict):
            apply_result = await deps.apply_strategy_param_map(
                request.strategy_api_url,
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
            incoming_positioning = {**legacy_positioning_payload, **incoming_positioning}
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
        deps.logger.info("Updated positioning config for %s: %s", ticker_upper, incoming_positioning)
    payload = dict(existing)
    merged_positioning = deps.get_ticker_positioning_config(ticker_upper, positioning_config)
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

    profiles = deps.normalize_tuner_profiles(ticker_cfg.get("adaptive_tuner_profiles", []))
    target_profile = next(
        (profile for profile in profiles if str(profile.get("profile_id")) == profile_id),
        None,
    )
    if not isinstance(target_profile, dict):
        raise HTTPException(404, f"Adaptive tuner profile not found: {profile_id}")

    best_candidate = target_profile.get("candidate", {})
    adaptive_version = deps.normalize_non_negative_int(
        target_profile.get("adaptive_version", 1),
        default=1,
        max_value=10,
    ) or 1
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
    config["tickers"][ticker] = updated_cfg

    if not deps.save_aos_config(config):
        raise HTTPException(500, "Failed to apply adaptive tuner profile")

    return {
        "success": True,
        "ticker": ticker,
        "profile_id": profile_id,
        "applied_candidate": best_candidate if isinstance(best_candidate, dict) else {},
    }
