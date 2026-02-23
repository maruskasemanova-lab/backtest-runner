"""
AOS Config - AOS (Automated Optimization Settings) configuration management.

This module handles loading, saving, and manipulating AOS configuration
including ticker-specific settings, strategy combos, and tuner profiles.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import json
from datetime import datetime
import os

from src.config_io import load_json_file, save_json_file


logger = logging.getLogger("AOSConfig")


# Keys that belong to positioning config, not AOS ticker config
POSITIONING_CONFIG_KEYS: Set[str] = {
    "risk_per_trade_pct",
    "max_position_notional_pct",
    "max_fill_participation_rate",
    "min_fill_ratio",
    "enable_partial_take_profit",
    "partial_take_profit_rr",
    "partial_take_profit_fraction",
    "trailing_stop_pct",
    "global_exit_rr_ratio",
    "global_risk_atr_stop_multiplier",
    "global_risk_volume_stop_pct",
    "global_risk_min_stop_loss_pct",
    "trailing_activation_pct",
    "break_even_buffer_pct",
    "break_even_min_hold_bars",
    "break_even_activation_min_mfe_pct",
    "break_even_activation_min_r",
    "break_even_activation_min_r_trending_5m",
    "break_even_activation_min_r_choppy_5m",
    "break_even_activation_use_levels",
    "break_even_activation_use_l2",
    "break_even_movement_formula_enabled",
    "break_even_movement_formula",
    "break_even_proof_formula_enabled",
    "break_even_proof_formula",
    "break_even_activation_formula_enabled",
    "break_even_activation_formula",
    "break_even_trailing_handoff_formula_enabled",
    "break_even_trailing_handoff_formula",
    "trailing_enabled_in_choppy",
    "time_exit_bars",
    "time_exit_formula_enabled",
    "time_exit_formula",
    "adverse_flow_exit_enabled",
    "adverse_flow_threshold",
    "adverse_flow_min_hold_bars",
    "adverse_flow_consistency_threshold",
    "adverse_book_pressure_threshold",
    "adverse_flow_exit_formula_enabled",
    "adverse_flow_exit_formula",
    "stop_loss_mode",
    "fixed_stop_loss_pct",
    "context_aware_risk_enabled",
    "context_risk_sl_buffer_pct",
    "context_risk_min_sl_pct",
    "context_risk_min_room_pct",
    "context_risk_min_effective_rr",
    "context_risk_trailing_tighten_zone",
    "context_risk_trailing_tighten_factor",
    "context_risk_level_trail_enabled",
    "context_risk_max_anchor_search_pct",
    "context_risk_min_level_tests_for_sl",
    "intraday_levels_micro_confirmation_enabled",
    "intraday_levels_micro_confirmation_bars",
    "intraday_levels_micro_confirmation_disable_for_sweep",
    "intraday_levels_micro_confirmation_sweep_bars",
    "intraday_levels_micro_confirmation_require_intrabar",
    "intraday_levels_micro_confirmation_intrabar_window_seconds",
    "intraday_levels_micro_confirmation_intrabar_min_coverage_points",
    "intraday_levels_micro_confirmation_intrabar_min_move_pct",
    "intraday_levels_micro_confirmation_intrabar_min_push_ratio",
    "intraday_levels_micro_confirmation_intrabar_max_spread_bps",
}


def load_aos_config(
    aos_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Load AOS optimization config from JSON file.

    Args:
        aos_config_path: Optional path to config file

    Returns:
        AOS configuration dictionary
    """
    path = (
        Path(aos_config_path)
        if aos_config_path
        else Path("aos_optimization/aos_config.json")
    )
    config = load_json_file(path, default={"version": "1.0.0", "tickers": {}})

    # Load separate ticker files dynamically
    tickers_dir = path.parent / "tickers"
    if "tickers" not in config or not isinstance(config["tickers"], dict):
        config["tickers"] = {}

    if tickers_dir.exists() and tickers_dir.is_dir():
        for ticker_file in tickers_dir.glob("*.json"):
            ticker = ticker_file.stem.upper()
            try:
                ticker_data = load_json_file(ticker_file, default={})
                config["tickers"][ticker] = ticker_data
            except Exception as e:
                logger.error(f"Failed to load ticker config from {ticker_file}: {e}")

    return config


def _log_aos_history(
    old_config: Dict[str, Any], new_config: Dict[str, Any], path: Optional[Path]
) -> None:
    """Log the diff of active profiles for each ticker to a history file."""
    try:
        if not path:
            return

        history_path = path.parent / "aos_history.jsonl"
        old_tickers = old_config.get("tickers", {})
        new_tickers = new_config.get("tickers", {})

        entries = []
        now_iso = datetime.utcnow().isoformat() + "Z"

        for ticker, new_ticker_data in new_tickers.items():
            if not isinstance(new_ticker_data, dict):
                continue

            old_ticker_data = old_tickers.get(ticker, {})
            if not isinstance(old_ticker_data, dict):
                old_ticker_data = {}

            # Check if active unifed profile changed or if it's the first time
            old_active_id = old_ticker_data.get("active_unified_profile_id")
            new_active_id = new_ticker_data.get("active_unified_profile_id")

            # Or if adaptive tuner profile changed
            old_tuner_id = old_ticker_data.get("active_adaptive_tuner_profile_id")
            new_tuner_id = new_ticker_data.get("active_adaptive_tuner_profile_id")

            # Find the actual profile shapes to compute a diff if we want, or just log the new profile wholesale
            # For simplicity & robust one-source-of-truth, we'll log the fact that the active profile changed,
            # and what the new active profile ID is. The frontend can fetch the full profiles to diff, or we just
            # store the whole snapshot of the new profile.

            if old_active_id != new_active_id or old_tuner_id != new_tuner_id:
                # Find the actual full unified profile data for the new active ID
                unified_profiles = new_ticker_data.get("unified_profiles", [])
                active_unified_profile = next(
                    (
                        p
                        for p in unified_profiles
                        if p.get("profile_id") == new_active_id
                    ),
                    {},
                )

                entry = {
                    "timestamp": now_iso,
                    "ticker": ticker,
                    "old_active_unified_profile_id": old_active_id,
                    "new_active_unified_profile_id": new_active_id,
                    "old_active_adaptive_tuner_profile_id": old_tuner_id,
                    "new_active_adaptive_tuner_profile_id": new_tuner_id,
                    "active_profile_snapshot": active_unified_profile,
                }
                entries.append(entry)

        if entries:
            with open(history_path, "a") as f:
                for entry in entries:
                    f.write(json.dumps(entry) + "\\n")
    except Exception as e:
        logger.error(f"Failed to append to aos_history.jsonl: {e}")


def save_aos_config(
    config: Dict[str, Any],
    aos_config_path: Optional[Union[str, Path]] = None,
) -> bool:
    """
    Save AOS optimization config to JSON file.

    Args:
        config: Configuration dictionary to save
        aos_config_path: Optional path to config file

    Returns:
        True if save was successful
    """
    path = (
        Path(aos_config_path)
        if aos_config_path
        else Path("aos_optimization/aos_config.json")
    )

    # Try to load the existing config to compute the delta for history
    try:
        old_config = load_aos_config(path)
        _log_aos_history(old_config, config, path)
    except Exception as e:
        logger.warning(f"Could not load old config for history logging: {e}")

    config_to_save = dict(config)
    tickers = config_to_save.pop("tickers", {})
    config_to_save["tickers"] = {}

    tickers_dir = path.parent / "tickers"
    tickers_dir.mkdir(parents=True, exist_ok=True)

    success = True
    for ticker, ticker_data in tickers.items():
        if isinstance(ticker_data, dict):
            ticker_file = tickers_dir / f"{ticker.upper()}.json"
            if not save_json_file(ticker_file, ticker_data):
                logger.error(f"Failed to save ticker config to {ticker_file}")
                success = False

    if not save_json_file(path, config_to_save):
        success = False

    # restore for caller
    config_to_save["tickers"] = tickers

    return success


def load_positioning_config(
    positioning_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Load positioning config from JSON file.

    Args:
        positioning_config_path: Optional path to config file

    Returns:
        Positioning configuration dictionary
    """
    path = Path(positioning_config_path) if positioning_config_path else None
    return load_json_file(path, default={"version": "1.0.0", "tickers": {}})


def save_positioning_config(
    config: Dict[str, Any],
    positioning_config_path: Optional[Union[str, Path]] = None,
) -> bool:
    """
    Save positioning config to JSON file.

    Args:
        config: Configuration dictionary to save
        positioning_config_path: Optional path to config file

    Returns:
        True if save was successful
    """
    path = Path(positioning_config_path) if positioning_config_path else None
    return save_json_file(config, path)


def merge_positioning_into_aos_snapshot(
    aos_config: Dict[str, Any],
    positioning_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge positioning config into AOS snapshot for display.

    Args:
        aos_config: AOS configuration
        positioning_config: Positioning configuration

    Returns:
        Merged configuration snapshot
    """
    result = dict(aos_config)

    for ticker, ticker_config in result.get("tickers", {}).items():
        if not isinstance(ticker_config, dict):
            continue

        positioning_ticker = positioning_config.get("tickers", {}).get(ticker, {})
        if not isinstance(positioning_ticker, dict):
            continue

        for key in POSITIONING_CONFIG_KEYS:
            if key in positioning_ticker and key not in ticker_config:
                ticker_config[key] = positioning_ticker[key]

    return result


def resolve_aos_config_path(
    aos_config_path: Optional[Union[str, Path]] = None,
    default_path: Optional[Path] = None,
) -> Path:
    """
    Resolve AOS config path from input or default.

    Args:
        aos_config_path: Optional input path
        default_path: Default path to use if input is None

    Returns:
        Resolved Path object
    """
    if aos_config_path is None:
        return default_path or Path("aos_optimization/aos_config.json")

    raw = str(aos_config_path).strip()
    if not raw:
        return default_path or Path("aos_optimization/aos_config.json")

    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def build_strategy_combo_profile_entry(
    ticker: str,
    profile_name: str,
    strategy_params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a new strategy combo profile entry.

    Args:
        ticker: Ticker symbol
        profile_name: Name for the profile
        strategy_params: Strategy parameters to save

    Returns:
        Profile entry dictionary
    """
    from datetime import datetime
    from uuid import uuid4

    return {
        "profile_id": str(uuid4())[:8],
        "profile_name": profile_name,
        "ticker": ticker.upper(),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "strategy_params": strategy_params,
    }
