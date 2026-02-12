"""
Backtest Runner Source Package.

This package contains the core modules for the backtest runner service.
"""
from .time_utils import (
    to_utc_datetime,
    epoch_minute_key,
    epoch_second_key,
    format_iso_utc,
    parse_iso_utc,
    is_within_window,
)

from .l2_schema import (
    L2_PAYLOAD_KEYS,
    L2_EXTENDED_KEYS,
    L2_ALL_KEYS,
    get_default_l2_feature_bucket,
    validate_l2_features,
    has_l2_coverage,
    L2FeatureStats,
    compute_l2_stats,
)

from .momentum_diversification import (
    normalize_momentum_diversification_payload,
    build_regime_strategy_map_options,
    MomentumDiversificationConfig,
    MICRO_REGIMES,
    ROUTE_KEYS,
    STRATEGY_FAMILY_MAP,
)

from .normalization import (
    normalize_strategy_selection_mode,
    normalize_clamped_int,
    normalize_bool_options,
    normalize_strategy_sets,
    normalize_regime_filter_sets,
    sanitize_strategy_params,
    normalize_strategy_combo_profiles,
    normalize_tuner_profiles,
    normalize_non_negative_int,
    normalize_int_options,
    normalize_mode_options,
    normalize_float_options,
    normalize_time_window_sets,
    normalize_regime_strategy_map_sets,
    normalize_strategy_key,
)

from .aos_config import (
    load_aos_config,
    save_aos_config,
    load_positioning_config,
    save_positioning_config,
    get_ticker_positioning_config,
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
    apply_active_strategy_combo,
    apply_active_adaptive_tuner_profile,
)

from .tuner_scoring import (
    compute_tuner_score,
    compute_tuner_score_robust,
    compute_adaptive_score,
    compute_adaptive_score_robust,
    aggregate_day_results,
)


__all__ = [
    # Time utilities
    "to_utc_datetime",
    "epoch_minute_key",
    "epoch_second_key",
    "format_iso_utc",
    "parse_iso_utc",
    "is_within_window",
    # L2 schema
    "L2_PAYLOAD_KEYS",
    "L2_EXTENDED_KEYS",
    "L2_ALL_KEYS",
    "get_default_l2_feature_bucket",
    "validate_l2_features",
    "has_l2_coverage",
    "L2FeatureStats",
    "compute_l2_stats",
    # Momentum diversification
    "normalize_momentum_diversification_payload",
    "build_regime_strategy_map_options",
    "MomentumDiversificationConfig",
    "MICRO_REGIMES",
    "ROUTE_KEYS",
    "STRATEGY_FAMILY_MAP",
    # Normalization
    "normalize_strategy_selection_mode",
    "normalize_clamped_int",
    "normalize_bool_options",
    "normalize_strategy_sets",
    "normalize_regime_filter_sets",
    "sanitize_strategy_params",
    "normalize_strategy_combo_profiles",
    "normalize_tuner_profiles",
    "normalize_non_negative_int",
    "normalize_int_options",
    "normalize_mode_options",
    "normalize_float_options",
    "normalize_time_window_sets",
    "normalize_regime_strategy_map_sets",
    "normalize_strategy_key",
    # AOS config
    "load_aos_config",
    "save_aos_config",
    "load_positioning_config",
    "save_positioning_config",
    "get_ticker_positioning_config",
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
    "apply_active_strategy_combo",
    "apply_active_adaptive_tuner_profile",
    # Tuner scoring
    "compute_tuner_score",
    "compute_tuner_score_robust",
    "compute_adaptive_score",
    "compute_adaptive_score_robust",
    "aggregate_day_results",
]
