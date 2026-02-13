"""
Momentum Diversification - Multi-sleeve allocation and micro-regime routing.

This module handles momentum diversification configuration including:
- Multi-sleeve allocation with independent L2 filters
- Micro-regime routing (TRENDING_UP, BREAKOUT, CHOPPY, etc.)
- Route-based strategy mapping (impulse, continuation, defensive)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# Valid micro-regime keys
MICRO_REGIMES: Set[str] = {
    "TRENDING_UP",
    "TRENDING_DOWN",
    "BREAKOUT",
    "MIXED",
    "ABSORPTION",
    "CHOPPY",
}

# Valid route keys
ROUTE_KEYS: Set[str] = {"impulse", "continuation", "defensive"}

# Strategy family taxonomy for regime-conditional mapping
STRATEGY_FAMILY_MAP: Dict[str, str] = {
    "momentum_flow": "trend-follow",
    "momentum": "trend-follow",
    "pullback": "trend-follow",
    "mean_reversion": "reversal",
    "absorption_reversal": "reversal",
    "exhaustion_fade": "reversal",
    "vwap_magnet": "reversal",
    "volume_profile": "level-based",
    "gap_liquidity": "level-based",
    "rotation": "sector",
    "iceberg_defense": "institutional",
}


@dataclass
class MomentumDiversificationConfig:
    """Configuration for momentum diversification."""
    
    enabled: bool = False
    require_l2_coverage: bool = False
    min_flow_score: float = 0.0
    min_directional_consistency: float = 0.0
    min_signed_aggression: float = 0.0
    min_imbalance: float = 0.0
    min_cvd: float = 0.0
    min_directional_price_change_pct: float = 0.0
    min_price_trend_efficiency: float = 0.0
    min_last_bar_body_ratio: float = 0.0
    min_last_bar_close_location: float = 0.0
    allowed_micro_regimes: List[str] = field(default_factory=list)
    blocked_micro_regimes: List[str] = field(default_factory=list)
    route_enabled: bool = False
    route_require_l2_coverage: bool = False
    route_flow_score_impulse: float = 0.0
    route_strategy_map: Dict[str, List[str]] = field(default_factory=dict)
    micro_regime_routes: Dict[str, str] = field(default_factory=dict)
    fail_fast_exit_enabled: bool = False
    fail_fast_max_bars: int = 5
    fail_fast_signed_aggression_max: float = -0.1
    fail_fast_book_pressure_max: float = -0.1
    fail_fast_directional_consistency_max: float = 0.3
    apply_to_strategies: List[str] = field(default_factory=list)
    sleeves: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "require_l2_coverage": self.require_l2_coverage,
            "min_flow_score": self.min_flow_score,
            "min_directional_consistency": self.min_directional_consistency,
            "min_signed_aggression": self.min_signed_aggression,
            "min_imbalance": self.min_imbalance,
            "min_cvd": self.min_cvd,
            "min_directional_price_change_pct": self.min_directional_price_change_pct,
            "min_price_trend_efficiency": self.min_price_trend_efficiency,
            "min_last_bar_body_ratio": self.min_last_bar_body_ratio,
            "min_last_bar_close_location": self.min_last_bar_close_location,
            "allowed_micro_regimes": self.allowed_micro_regimes,
            "blocked_micro_regimes": self.blocked_micro_regimes,
            "route_enabled": self.route_enabled,
            "route_require_l2_coverage": self.route_require_l2_coverage,
            "route_flow_score_impulse": self.route_flow_score_impulse,
            "route_strategy_map": self.route_strategy_map,
            "micro_regime_routes": self.micro_regime_routes,
            "fail_fast_exit_enabled": self.fail_fast_exit_enabled,
            "fail_fast_max_bars": self.fail_fast_max_bars,
            "fail_fast_signed_aggression_max": self.fail_fast_signed_aggression_max,
            "fail_fast_book_pressure_max": self.fail_fast_book_pressure_max,
            "fail_fast_directional_consistency_max": self.fail_fast_directional_consistency_max,
            "apply_to_strategies": self.apply_to_strategies,
            "sleeves": self.sleeves,
        }


def normalize_momentum_diversification_payload(
    raw: Any,
    *,
    include_sleeves: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Normalize and validate momentum diversification payload.
    
    Args:
        raw: Raw configuration dictionary
        include_sleeves: Whether to process sleeve configurations
        
    Returns:
        Normalized configuration dictionary or None if invalid
    """
    if not isinstance(raw, dict):
        return None

    payload: Dict[str, Any] = {}
    bool_keys = {
        "enabled",
        "require_l2_coverage",
        "route_enabled",
        "route_require_l2_coverage",
        "fail_fast_exit_enabled",
    }
    for key in bool_keys:
        if key in raw:
            payload[key] = bool(raw.get(key))

    float_bounds = {
        "min_flow_score": (0.0, 100.0),
        "min_directional_consistency": (0.0, 1.0),
        "min_signed_aggression": (0.0, 1.0),
        "min_imbalance": (0.0, 1.0),
        "min_cvd": (-1_000_000_000.0, 1_000_000_000.0),
        "min_directional_price_change_pct": (-100.0, 100.0),
        "min_price_trend_efficiency": (0.0, 1.0),
        "min_last_bar_body_ratio": (0.0, 1.0),
        "min_last_bar_close_location": (0.0, 1.0),
        "min_delta_acceleration": (-1_000_000_000.0, 1_000_000_000.0),
        "min_delta_price_divergence": (-10.0, 10.0),
        "route_flow_score_impulse": (0.0, 100.0),
        "fail_fast_signed_aggression_max": (-1.0, 0.0),
        "fail_fast_book_pressure_max": (-1.0, 0.0),
        "fail_fast_directional_consistency_max": (0.0, 1.0),
    }
    for key, (low, high) in float_bounds.items():
        if key not in raw:
            continue
        try:
            value = float(raw.get(key))
        except (TypeError, ValueError):
            continue
        payload[key] = max(low, min(high, value))

    if "fail_fast_max_bars" in raw:
        try:
            value = int(raw.get("fail_fast_max_bars"))
        except (TypeError, ValueError):
            value = 0
        payload["fail_fast_max_bars"] = max(1, min(30, value))

    if isinstance(raw.get("apply_to_strategies"), list):
        cleaned = []
        seen = set()
        for item in raw.get("apply_to_strategies", []):
            value = str(item or "").strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
        if cleaned:
            payload["apply_to_strategies"] = cleaned

    for list_key in ("allowed_micro_regimes", "blocked_micro_regimes"):
        if not isinstance(raw.get(list_key), list):
            continue
        cleaned = []
        seen = set()
        for item in raw.get(list_key, []):
            value = str(item or "").strip().upper()
            if value not in MICRO_REGIMES or value in seen:
                continue
            seen.add(value)
            cleaned.append(value)
        payload[list_key] = cleaned

    route_map = raw.get("route_strategy_map")
    if isinstance(route_map, dict):
        cleaned_route_map: Dict[str, List[str]] = {}
        for route_key in ROUTE_KEYS:
            values = route_map.get(route_key, [])
            if not isinstance(values, list):
                continue
            cleaned = []
            seen = set()
            for item in values:
                value = str(item or "").strip().lower()
                if not value or value in seen:
                    continue
                seen.add(value)
                cleaned.append(value)
            cleaned_route_map[route_key] = cleaned
        if cleaned_route_map:
            payload["route_strategy_map"] = cleaned_route_map

    micro_routes = raw.get("micro_regime_routes")
    if isinstance(micro_routes, dict):
        cleaned_micro_routes: Dict[str, str] = {}
        for micro_key in MICRO_REGIMES:
            route_name = str(micro_routes.get(micro_key, "")).strip().lower()
            if route_name not in ROUTE_KEYS:
                continue
            cleaned_micro_routes[micro_key] = route_name
        if cleaned_micro_routes:
            payload["micro_regime_routes"] = cleaned_micro_routes

    if include_sleeves and isinstance(raw.get("sleeves"), list):
        cleaned_sleeves: List[Dict[str, Any]] = []
        seen_ids = set()
        for idx, item in enumerate(raw.get("sleeves", [])):
            if not isinstance(item, dict):
                continue
            sleeve_payload = normalize_momentum_diversification_payload(
                item,
                include_sleeves=False,
            )
            if not sleeve_payload:
                continue
            raw_id = str(item.get("sleeve_id") or item.get("name") or f"sleeve_{idx + 1}").strip()
            normalized_id = raw_id.lower().replace(" ", "_")
            if not normalized_id:
                normalized_id = f"sleeve_{idx + 1}"
            if normalized_id in seen_ids:
                continue
            seen_ids.add(normalized_id)
            sleeve_payload["sleeve_id"] = normalized_id

            if "allocation_weight" in item:
                try:
                    weight = float(item.get("allocation_weight"))
                except (TypeError, ValueError):
                    weight = 0.0
                sleeve_payload["allocation_weight"] = max(0.0, min(1.0, weight))

            cleaned_sleeves.append(sleeve_payload)
            if len(cleaned_sleeves) >= 8:
                break
        if cleaned_sleeves:
            payload["sleeves"] = cleaned_sleeves

    return payload or None


def build_regime_strategy_map_options(
    enabled: List[str],
    strategy_family_map: Optional[Dict[str, str]] = None,
) -> List[Optional[Dict[str, List[str]]]]:
    """
    Build regime-conditional strategy map options for v2 search space.

    Returns a list of map candidates. ``None`` means flat mode (no per-regime
    mapping, backward compatible). Each map assigns a strategy list to each
    macro regime (TRENDING / MIXED / CHOPPY).
    
    Args:
        enabled: List of enabled strategy names
        strategy_family_map: Optional custom strategy family map
        
    Returns:
        List of regime strategy map options
    """
    family_map = strategy_family_map or STRATEGY_FAMILY_MAP
    
    trend = [s for s in enabled if family_map.get(s) == "trend-follow"]
    reversal = [s for s in enabled if family_map.get(s) == "reversal"]
    
    # Fallback: if a family bucket is empty, use enabled list
    if not trend:
        trend = enabled[:1]
    if not reversal:
        reversal = enabled[:1]
        
    return [
        None,  # flat mode — backward compatible
        {"TRENDING": trend, "MIXED": reversal, "CHOPPY": []},
        {"TRENDING": trend, "MIXED": reversal, "CHOPPY": reversal},
        {"TRENDING": trend, "MIXED": trend + reversal, "CHOPPY": []},
    ]
