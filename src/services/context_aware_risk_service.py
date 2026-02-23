"""
Context-Aware Risk Management Service.

Adjusts stop-loss, take-profit, and trailing based on intraday levels context
(S/R levels, volume profile POC/VA, opening range, previous-day anchors)
instead of using hardcoded ATR multiplier / RR ratio values.

The original strategy-computed SL/TP is used as FALLBACK when no relevant
level is found nearby.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ContextAwareRisk")


_STRATEGY_ROOM_DEFAULTS: Dict[str, Dict[str, float]] = {
    "momentum": {"min_room_pct": 0.08, "min_effective_rr": 0.8},
    "pullback": {"min_room_pct": 0.05, "min_effective_rr": 0.6},
    "mean_reversion": {"min_room_pct": 0.03, "min_effective_rr": 0.4},
    "rotation": {"min_room_pct": 0.02, "min_effective_rr": 0.3},
    "vwap_magnet": {"min_room_pct": 0.03, "min_effective_rr": 0.4},
    "volumeprofile": {"min_room_pct": 0.03, "min_effective_rr": 0.4},
}


@dataclass
class ContextRiskConfig:
    """Runtime configuration for context-aware risk adjustments."""

    enabled: bool = False
    sl_buffer_pct: float = 0.10
    min_room_pct: float = 0.08
    min_effective_rr: float = 1.0
    # When price has covered this fraction toward TP, tighten trailing
    trailing_tighten_zone: float = 0.2
    # Factor to multiply trailing pct by when in tighten zone
    trailing_tighten_factor: float = 0.5
    # Trail SL along intermediate levels
    level_trail_enabled: bool = True
    # Maximum distance (as % of entry) to search for anchor levels
    max_anchor_search_pct: float = 0.8
    # Minimum level tests required for a level to be used as SL anchor
    min_level_tests_for_sl: int = 2
    # Additional ATR multiplier buffer for sweep-triggered entries
    sweep_atr_buffer_multiplier: float = 0.5

    def effective_min_room_pct(self, strategy_key: str = "") -> float:
        key = str(strategy_key or "").strip().lower()
        defaults = _STRATEGY_ROOM_DEFAULTS.get(key)
        if defaults and self.min_room_pct == 0.08:
            return defaults["min_room_pct"]
        return self.min_room_pct

    def effective_min_rr(self, strategy_key: str = "") -> float:
        key = str(strategy_key or "").strip().lower()
        defaults = _STRATEGY_ROOM_DEFAULTS.get(key)
        if defaults and self.min_effective_rr == 1.0:
            return defaults["min_effective_rr"]
        return self.min_effective_rr

    @classmethod
    def from_execution_config(cls, ec: Dict[str, Any]) -> "ContextRiskConfig":
        """Build config from execution_config dict."""

        def _bool(key: str, default: bool) -> bool:
            raw = ec.get(key)
            if raw is None:
                return default
            if isinstance(raw, bool):
                return raw
            return bool(int(raw))

        def _float(key: str, default: float) -> float:
            raw = ec.get(key)
            if raw is None:
                return default
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default

        def _int(key: str, default: int) -> int:
            raw = ec.get(key)
            if raw is None:
                return default
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default

        return cls(
            enabled=_bool("context_aware_risk_enabled", False),
            sl_buffer_pct=_float("context_risk_sl_buffer_pct", 0.10),
            min_room_pct=_float("context_risk_min_room_pct", 0.08),
            min_effective_rr=_float("context_risk_min_effective_rr", 1.0),
            trailing_tighten_zone=_float("context_risk_trailing_tighten_zone", 0.2),
            trailing_tighten_factor=_float("context_risk_trailing_tighten_factor", 0.5),
            level_trail_enabled=_bool("context_risk_level_trail_enabled", True),
            max_anchor_search_pct=_float("context_risk_max_anchor_search_pct", 0.8),
            min_level_tests_for_sl=_int("context_risk_min_level_tests_for_sl", 2),
            sweep_atr_buffer_multiplier=max(
                0.0,
                _float("sweep_atr_buffer_multiplier", 0.5),
            ),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_levels(levels_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return list of level dicts from the intraday_levels payload."""
    raw = levels_payload.get("levels")
    if isinstance(raw, list):
        return [lv for lv in raw if isinstance(lv, dict)]
    return []


def _extract_poc(levels_payload: Dict[str, Any]) -> Optional[float]:
    """Return POC price from volume profile if available."""
    vp = levels_payload.get("volume_profile")
    if isinstance(vp, dict):
        poc = vp.get("poc_price")
        if poc is not None:
            try:
                return float(poc)
            except (TypeError, ValueError):
                pass
    return None


def _extract_va(
    levels_payload: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float]]:
    """Return (VAL, VAH) from volume profile."""
    vp = levels_payload.get("volume_profile")
    if not isinstance(vp, dict):
        return None, None
    val_raw = vp.get("value_area_low")
    vah_raw = vp.get("value_area_high")
    val = None
    vah = None
    if val_raw is not None:
        try:
            val = float(val_raw)
        except (TypeError, ValueError):
            pass
    if vah_raw is not None:
        try:
            vah = float(vah_raw)
        except (TypeError, ValueError):
            pass
    return val, vah


def _extract_opening_range(
    levels_payload: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float]]:
    """Return (OR low, OR high) if present."""
    orng = levels_payload.get("opening_range")
    if not isinstance(orng, dict):
        return None, None
    or_low = orng.get("low")
    or_high = orng.get("high")
    low = None
    high = None
    if or_low is not None:
        try:
            low = float(or_low)
        except (TypeError, ValueError):
            pass
    if or_high is not None:
        try:
            high = float(or_high)
        except (TypeError, ValueError):
            pass
    return low, high


def _level_price(level: Dict[str, Any]) -> Optional[float]:
    """Safely extract price from a level dict."""
    for key in ("price", "level_price", "level"):
        raw = level.get(key)
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
    return None


def _level_tests(level: Dict[str, Any]) -> int:
    """Number of tests for a level."""
    for key in ("tests", "test_count", "touches"):
        raw = level.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    return 0


def _level_broken(level: Dict[str, Any]) -> bool:
    """Whether the level has been broken."""
    return bool(level.get("broken", False))


# ---------------------------------------------------------------------------
# Core adjustment functions
# ---------------------------------------------------------------------------


def adjust_stop_loss(
    entry_price: float,
    side: str,
    original_sl: float,
    levels_payload: Dict[str, Any],
    config: ContextRiskConfig,
    atr: Optional[float] = None,
    is_sweep_trade: bool = False,
) -> Tuple[float, str]:
    """
    Compute a context-aware stop-loss anchored to the nearest relevant S/R level.

    Returns (adjusted_sl, reason) where reason describes what happened.
    """
    if entry_price <= 0:
        return original_sl, "invalid_entry"

    max_search = entry_price * config.max_anchor_search_pct / 100.0
    buffer_abs = entry_price * config.sl_buffer_pct / 100.0
    atr_buffer_abs = 0.0
    if is_sweep_trade:
        try:
            atr_buffer_abs = max(0.0, float(atr or 0.0)) * max(
                0.0, float(config.sweep_atr_buffer_multiplier)
            )
        except (TypeError, ValueError):
            atr_buffer_abs = 0.0
    total_buffer_abs = buffer_abs + atr_buffer_abs
    levels = _extract_levels(levels_payload)
    poc = _extract_poc(levels_payload)
    val, vah = _extract_va(levels_payload)
    or_low, or_high = _extract_opening_range(levels_payload)

    is_long = side.lower() in ("long", "buy")

    # Collect candidate anchor prices
    candidates: List[Tuple[float, str]] = []

    for lv in levels:
        lp = _level_price(lv)
        if lp is None:
            continue
        if _level_broken(lv):
            continue  # broken levels are unreliable for SL
        if _level_tests(lv) < config.min_level_tests_for_sl:
            continue

        if is_long:
            # For longs: support levels BELOW entry
            if lp < entry_price and (entry_price - lp) <= max_search:
                candidates.append((lp - total_buffer_abs, f"support_{lp:.2f}"))
        else:
            # For shorts: resistance levels ABOVE entry
            if lp > entry_price and (lp - entry_price) <= max_search:
                candidates.append((lp + total_buffer_abs, f"resistance_{lp:.2f}"))

    # Also consider VA boundaries as potential SL anchors
    if is_long:
        if val is not None and val < entry_price and (entry_price - val) <= max_search:
            candidates.append((val - total_buffer_abs, f"val_{val:.2f}"))
        if (
            or_low is not None
            and or_low < entry_price
            and (entry_price - or_low) <= max_search
        ):
            candidates.append((or_low - total_buffer_abs, f"or_low_{or_low:.2f}"))
    else:
        if vah is not None and vah > entry_price and (vah - entry_price) <= max_search:
            candidates.append((vah + total_buffer_abs, f"vah_{vah:.2f}"))
        if (
            or_high is not None
            and or_high > entry_price
            and (or_high - entry_price) <= max_search
        ):
            candidates.append((or_high + total_buffer_abs, f"or_high_{or_high:.2f}"))

    if not candidates:
        return original_sl, "no_nearby_level"

    if is_long:
        # For longs: pick highest candidate that is still below entry
        valid = [(price, reason) for price, reason in candidates if price < entry_price]
        if not valid:
            return original_sl, "no_valid_anchor"
        # Best anchor = closest to entry (tightest SL)
        best_price, best_reason = max(valid, key=lambda x: x[0])

        orig_dist = abs(entry_price - original_sl) if original_sl < entry_price else 0
        cand_dist = abs(entry_price - best_price)

        # Only use anchor if it's tighter (higher) than original SL, or slightly wider (up to 1.5x original distance).
        if best_price > original_sl:
            reason = f"anchored_{best_reason}"
            if atr_buffer_abs > 0.0:
                reason = f"{reason}|sweep_atr_buffer:{atr_buffer_abs:.4f}"
            return best_price, reason
        elif orig_dist > 0 and cand_dist <= orig_dist * 1.5:
            reason = f"anchored_{best_reason}_stretched"
            if atr_buffer_abs > 0.0:
                reason = f"{reason}|sweep_atr_buffer:{atr_buffer_abs:.4f}"
            return best_price, reason
        else:
            return original_sl, f"fallback_atr(anchor_{best_reason}_too_far)"
    else:
        # For shorts: pick lowest candidate that is still above entry
        valid = [(price, reason) for price, reason in candidates if price > entry_price]
        if not valid:
            return original_sl, "no_valid_anchor"
        best_price, best_reason = min(valid, key=lambda x: x[0])

        orig_dist = abs(original_sl - entry_price) if original_sl > entry_price else 0
        cand_dist = abs(best_price - entry_price)

        if best_price < original_sl:
            reason = f"anchored_{best_reason}"
            if atr_buffer_abs > 0.0:
                reason = f"{reason}|sweep_atr_buffer:{atr_buffer_abs:.4f}"
            return best_price, reason
        elif orig_dist > 0 and cand_dist <= orig_dist * 1.5:
            reason = f"anchored_{best_reason}_stretched"
            if atr_buffer_abs > 0.0:
                reason = f"{reason}|sweep_atr_buffer:{atr_buffer_abs:.4f}"
            return best_price, reason
        else:
            return original_sl, f"fallback_atr(anchor_{best_reason}_too_far)"


def adjust_take_profit(
    entry_price: float,
    side: str,
    adjusted_sl: float,
    original_tp: float,
    levels_payload: Dict[str, Any],
    config: ContextRiskConfig,
) -> Tuple[float, str]:
    """
    Set TP on the nearest level in the trade direction (resistance for long,
    support for short).  Falls back to POC or original TP.

    Returns (adjusted_tp, reason).
    """
    if entry_price <= 0:
        return original_tp, "invalid_entry"

    is_long = side.lower() in ("long", "buy")
    levels = _extract_levels(levels_payload)
    poc = _extract_poc(levels_payload)
    val, vah = _extract_va(levels_payload)
    or_low, or_high = _extract_opening_range(levels_payload)

    # Collect target candidates
    candidates: List[Tuple[float, str]] = []

    for lv in levels:
        lp = _level_price(lv)
        if lp is None:
            continue
        if is_long:
            # Resistance above entry = target
            if lp > entry_price:
                candidates.append((lp, f"resistance_{lp:.2f}"))
        else:
            if lp < entry_price:
                candidates.append((lp, f"support_{lp:.2f}"))

    # POC as target if on the right side
    if poc is not None:
        if is_long and poc > entry_price:
            candidates.append((poc, f"poc_{poc:.2f}"))
        elif not is_long and poc < entry_price:
            candidates.append((poc, f"poc_{poc:.2f}"))

    # VA boundaries
    if is_long:
        if vah is not None and vah > entry_price:
            candidates.append((vah, f"vah_{vah:.2f}"))
        if or_high is not None and or_high > entry_price:
            candidates.append((or_high, f"or_high_{or_high:.2f}"))
    else:
        if val is not None and val < entry_price:
            candidates.append((val, f"val_{val:.2f}"))
        if or_low is not None and or_low < entry_price:
            candidates.append((or_low, f"or_low_{or_low:.2f}"))

    if not candidates:
        return original_tp, "no_target_level"

    if is_long:
        # Nearest target above entry
        primary_price, primary_reason = min(candidates, key=lambda x: x[0])
    else:
        # Nearest target below entry
        primary_price, primary_reason = max(candidates, key=lambda x: x[0])

    # Allow level-based TP even if slightly farther, up to 1.5× original distance.
    # This gives trades more room to breathe when a real level exists nearby.
    if is_long:
        orig_dist = abs(original_tp - entry_price) if original_tp > entry_price else 0
        cand_dist = abs(primary_price - entry_price)
        if (
            primary_price > entry_price
            and orig_dist > 0
            and cand_dist <= orig_dist * 1.5
        ):
            return primary_price, f"target_{primary_reason}"
        elif primary_price <= original_tp:
            return primary_price, f"target_{primary_reason}"
        else:
            return original_tp, f"fallback_rr(target_{primary_reason}_farther)"
    else:
        orig_dist = abs(entry_price - original_tp) if original_tp < entry_price else 0
        cand_dist = abs(entry_price - primary_price)
        if (
            primary_price < entry_price
            and orig_dist > 0
            and cand_dist <= orig_dist * 1.5
        ):
            return primary_price, f"target_{primary_reason}"
        elif primary_price >= original_tp:
            return primary_price, f"target_{primary_reason}"
        else:
            return original_tp, f"fallback_rr(target_{primary_reason}_farther)"


def should_skip_trade(
    entry_price: float,
    side: str,
    adjusted_sl: float,
    adjusted_tp: float,
    config: ContextRiskConfig,
    strategy_key: str = "",
) -> Tuple[bool, str]:
    """
    Check if the trade should be skipped due to insufficient room or RR.

    Returns (should_skip, reason).
    """
    if entry_price <= 0:
        return True, "invalid_entry_price"

    is_long = side.lower() in ("long", "buy")

    if is_long:
        room = adjusted_tp - entry_price
        risk = entry_price - adjusted_sl
    else:
        room = entry_price - adjusted_tp
        risk = adjusted_sl - entry_price

    room_pct = (room / entry_price) * 100.0 if entry_price > 0 else 0
    risk_pct = (risk / entry_price) * 100.0 if entry_price > 0 else 0

    eff_min_room = config.effective_min_room_pct(strategy_key)
    eff_min_rr = config.effective_min_rr(strategy_key)

    if room_pct < eff_min_room:
        return True, f"room_too_small({room_pct:.3f}%<{eff_min_room}%)"

    if risk_pct <= 0:
        return True, "zero_risk"

    effective_rr = room_pct / risk_pct
    if effective_rr < eff_min_rr:
        return True, f"rr_too_low({effective_rr:.2f}<{eff_min_rr})"

    return False, "ok"


def compute_trailing_adjustment(
    current_price: float,
    entry_price: float,
    take_profit: float,
    side: str,
    base_trailing_pct: float,
    levels_payload: Optional[Dict[str, Any]],
    config: ContextRiskConfig,
) -> float:
    """
    Compute adjusted trailing stop percentage based on proximity to target level.

    Returns effective trailing pct.
    """
    if not config.enabled:
        return base_trailing_pct

    is_long = side.lower() in ("long", "buy")

    # Calculate progress toward target
    if is_long:
        total_distance = take_profit - entry_price
        covered = current_price - entry_price
    else:
        total_distance = entry_price - take_profit
        covered = entry_price - current_price

    if total_distance <= 0:
        return base_trailing_pct

    progress = covered / total_distance  # 0.0 = at entry, 1.0 = at TP

    if progress >= (1.0 - config.trailing_tighten_zone):
        # In the tighten zone (last 20% toward TP)
        return base_trailing_pct * config.trailing_tighten_factor

    return base_trailing_pct


def compute_level_trail_sl(
    current_price: float,
    entry_price: float,
    current_sl: float,
    side: str,
    levels_payload: Optional[Dict[str, Any]],
    config: ContextRiskConfig,
) -> Tuple[float, Optional[str]]:
    """
    Trail stop-loss along intermediate levels as price moves in favor.

    Returns (new_sl, reason_or_None).
    """
    if not config.level_trail_enabled or levels_payload is None:
        return current_sl, None

    is_long = side.lower() in ("long", "buy")
    levels = _extract_levels(levels_payload)
    buffer_abs = entry_price * config.sl_buffer_pct / 100.0

    if is_long:
        # Find support levels between current_sl and current_price
        trail_candidates: List[Tuple[float, str]] = []
        for lv in levels:
            lp = _level_price(lv)
            if lp is None or _level_broken(lv):
                continue
            anchor = lp - buffer_abs
            # Must be above current SL and below current price
            if anchor > current_sl and lp < current_price:
                trail_candidates.append((anchor, f"trail_support_{lp:.2f}"))
        if trail_candidates:
            best_price, best_reason = max(trail_candidates, key=lambda x: x[0])
            return best_price, best_reason
    else:
        trail_candidates = []
        for lv in levels:
            lp = _level_price(lv)
            if lp is None or _level_broken(lv):
                continue
            anchor = lp + buffer_abs
            if anchor < current_sl and lp > current_price:
                trail_candidates.append((anchor, f"trail_resistance_{lp:.2f}"))
        if trail_candidates:
            best_price, best_reason = min(trail_candidates, key=lambda x: x[0])
            return best_price, best_reason

    return current_sl, None


# ---------------------------------------------------------------------------
# High-level entry point used by SessionRunner
# ---------------------------------------------------------------------------


@dataclass
class RiskAdjustmentResult:
    """Captures the full result of a context-aware risk adjustment."""

    adjusted_sl: float
    adjusted_tp: float
    sl_reason: str
    tp_reason: str
    skip: bool
    skip_reason: str
    original_sl: float
    original_tp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adjusted_sl": round(self.adjusted_sl, 4),
            "adjusted_tp": round(self.adjusted_tp, 4),
            "original_sl": round(self.original_sl, 4),
            "original_tp": round(self.original_tp, 4),
            "sl_reason": self.sl_reason,
            "tp_reason": self.tp_reason,
            "skip": self.skip,
            "skip_reason": self.skip_reason,
        }


def adjust_entry_risk(
    entry_price: float,
    side: str,
    original_sl: float,
    original_tp: float,
    levels_payload: Dict[str, Any],
    config: ContextRiskConfig,
    atr: Optional[float] = None,
    is_sweep_trade: bool = False,
    strategy_key: str = "",
) -> RiskAdjustmentResult:
    """
    Main entry point: adjust SL, TP and check if trade should be skipped.

    Called from SessionRunner._process_decision_markers() when a
    position_opened event is received.
    """
    adjusted_sl, sl_reason = adjust_stop_loss(
        entry_price=entry_price,
        side=side,
        original_sl=original_sl,
        levels_payload=levels_payload,
        config=config,
        atr=atr,
        is_sweep_trade=is_sweep_trade,
    )

    adjusted_tp, tp_reason = adjust_take_profit(
        entry_price=entry_price,
        side=side,
        adjusted_sl=adjusted_sl,
        original_tp=original_tp,
        levels_payload=levels_payload,
        config=config,
    )

    skip, skip_reason = should_skip_trade(
        entry_price=entry_price,
        side=side,
        adjusted_sl=adjusted_sl,
        adjusted_tp=adjusted_tp,
        config=config,
        strategy_key=strategy_key,
    )

    return RiskAdjustmentResult(
        adjusted_sl=adjusted_sl,
        adjusted_tp=adjusted_tp,
        sl_reason=sl_reason,
        tp_reason=tp_reason,
        skip=skip,
        skip_reason=skip_reason,
        original_sl=original_sl,
        original_tp=original_tp,
    )
