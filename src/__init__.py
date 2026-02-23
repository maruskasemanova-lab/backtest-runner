"""
Backtest Runner Source Package.

This package contains the core modules for the backtest runner service.
"""

from .time_utils import (
    to_utc_datetime,
)

from .l2_schema import (
    L2_PAYLOAD_KEYS,
    L2_EXTENDED_KEYS,
    L2_ALL_KEYS,
)

from .momentum_diversification import (
    normalize_momentum_diversification_payload,
    build_regime_strategy_map_options,
    MICRO_REGIMES,
    ROUTE_KEYS,
    STRATEGY_FAMILY_MAP,
)

from .normalization import (
    normalize_strategy_selection_mode,
    normalize_clamped_int,
    sanitize_strategy_params,
    normalize_strategy_combo_profiles,
    normalize_tuner_profiles,
    normalize_non_negative_int,
)

from .aos_config import (
    load_aos_config,
    save_aos_config,
    load_positioning_config,
    save_positioning_config,
    merge_positioning_into_aos_snapshot,
    POSITIONING_CONFIG_KEYS,
)

from .session_config import (
    configure_session,
    clear_remote_strategy_sessions,
    reset_remote_orchestrator_state,
    load_remote_checkpoint,
    save_remote_checkpoint,
)

from .strategy_api_client import (
    fetch_remote_strategies,
    apply_strategy_param_map,
    apply_strategy_overrides,
    apply_global_trailing,
)

__all__ = [
    # Time utilities
    "to_utc_datetime",
    # L2 schema
    "L2_PAYLOAD_KEYS",
    "L2_EXTENDED_KEYS",
    "L2_ALL_KEYS",
    # Momentum diversification
    "normalize_momentum_diversification_payload",
    "build_regime_strategy_map_options",
    "MICRO_REGIMES",
    "ROUTE_KEYS",
    "STRATEGY_FAMILY_MAP",
    # Normalization
    "normalize_strategy_selection_mode",
    "normalize_clamped_int",
    "sanitize_strategy_params",
    "normalize_strategy_combo_profiles",
    "normalize_tuner_profiles",
    "normalize_non_negative_int",
    # AOS config
    "load_aos_config",
    "save_aos_config",
    "load_positioning_config",
    "save_positioning_config",
    "merge_positioning_into_aos_snapshot",
    "POSITIONING_CONFIG_KEYS",
    # Session config
    "configure_session",
    "clear_remote_strategy_sessions",
    "reset_remote_orchestrator_state",
    "load_remote_checkpoint",
    "save_remote_checkpoint",
    # Strategy API client
    "fetch_remote_strategies",
    "apply_strategy_param_map",
    "apply_strategy_overrides",
    "apply_global_trailing",
]
