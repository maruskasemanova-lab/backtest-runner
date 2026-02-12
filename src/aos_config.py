"""
AOS Config - AOS (Automated Optimization Settings) configuration management.

This module handles loading, saving, and manipulating AOS configuration
including ticker-specific settings, strategy combos, and tuner profiles.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

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
    "trailing_activation_pct",
    "break_even_buffer_pct",
    "break_even_min_hold_bars",
    "trailing_enabled_in_choppy",
    "time_exit_bars",
    "adverse_flow_exit_enabled",
    "adverse_flow_threshold",
    "adverse_flow_min_hold_bars",
    "adverse_flow_consistency_threshold",
    "adverse_book_pressure_threshold",
    "stop_loss_mode",
    "fixed_stop_loss_pct",
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
    path = Path(aos_config_path) if aos_config_path else None
    return load_json_file(path, default={"version": "1.0.0", "tickers": {}})


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
    path = Path(aos_config_path) if aos_config_path else None
    return save_json_file(config, path)


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


def get_ticker_positioning_config(
    ticker: str,
    positioning_config: Optional[Dict[str, Any]] = None,
    positioning_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Get positioning config for a specific ticker.
    
    Args:
        ticker: Ticker symbol
        positioning_config: Optional pre-loaded config
        positioning_config_path: Optional path to config file
        
    Returns:
        Ticker-specific positioning configuration
    """
    config = positioning_config or load_positioning_config(positioning_config_path)
    ticker_config = config.get("tickers", {}).get(ticker.upper(), {})
    return ticker_config if isinstance(ticker_config, dict) else {}


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


def get_ticker_aos_config(
    ticker: str,
    aos_config: Optional[Dict[str, Any]] = None,
    aos_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Get AOS config for a specific ticker.
    
    Args:
        ticker: Ticker symbol
        aos_config: Optional pre-loaded config
        aos_config_path: Optional path to config file
        
    Returns:
        Ticker-specific AOS configuration
    """
    config = aos_config or load_aos_config(aos_config_path)
    ticker_config = config.get("tickers", {}).get(ticker.upper(), {})
    return ticker_config if isinstance(ticker_config, dict) else {}


def update_ticker_aos_config(
    ticker: str,
    updates: Dict[str, Any],
    aos_config: Optional[Dict[str, Any]] = None,
    aos_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Update AOS config for a specific ticker.
    
    Args:
        ticker: Ticker symbol
        updates: Updates to apply
        aos_config: Optional pre-loaded config
        aos_config_path: Optional path to config file
        
    Returns:
        Updated configuration dictionary
    """
    config = aos_config or load_aos_config(aos_config_path)
    
    if "tickers" not in config or not isinstance(config.get("tickers"), dict):
        config["tickers"] = {}
    
    ticker_upper = ticker.upper()
    ticker_config = config["tickers"].get(ticker_upper, {})
    if not isinstance(ticker_config, dict):
        ticker_config = {}
    
    ticker_config.update(updates)
    config["tickers"][ticker_upper] = ticker_config
    
    return config


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


def build_tuner_profile_entry(
    ticker: str,
    profile_name: str,
    search_space: Dict[str, Any],
    best_candidate: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a new tuner profile entry.
    
    Args:
        ticker: Ticker symbol
        profile_name: Name for the profile
        search_space: Search space configuration
        best_candidate: Optional best candidate found
        metrics: Optional performance metrics
        
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
        "search_space": search_space,
        "best_candidate": best_candidate,
        "metrics": metrics,
    }
