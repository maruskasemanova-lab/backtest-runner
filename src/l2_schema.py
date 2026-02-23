"""
L2 Schema - Schema definitions for L2 order flow features.

This module centralizes L2 feature keys and validation to ensure
consistent handling across all components.
"""

from __future__ import annotations

from typing import Set


# Core L2 payload keys from order flow processing
L2_PAYLOAD_KEYS: Set[str] = {
    "delta",
    "imbalance",
    "iceberg_bias",
    "participation_ratio",
    "directional_consistency",
    "signed_aggression",
    "book_pressure",
    "flow_score",
}

# Extended L2 keys for advanced analysis
L2_EXTENDED_KEYS: Set[str] = {
    "delta_acceleration",
    "delta_price_divergence",
    "absorption_score",
    "momentum_flow_score",
    "iceberg_detected",
    "large_lot_ratio",
    "spread_pct",
    "volume_imbalance",
}

# All L2 keys
L2_ALL_KEYS: Set[str] = L2_PAYLOAD_KEYS | L2_EXTENDED_KEYS
