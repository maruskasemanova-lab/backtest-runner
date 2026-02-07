# MU Profitability Improvement Roadmap
Generated: 2026-02-06 by Claude Code

## Executive Summary (12 bullets)

1. **System is trading but net negative**: 12 trades across 10 runs, aggregate PnL = -$140.78
2. **Borderline entries (score 58-70) are pure loss**: 2 trades, 0 wins, -$124.94 — this bucket accounts for ~89% of total losses
3. **High-quality entries (score >70) are profitable**: 6 trades, 4 wins, +$85.00, 67% win rate
4. **Regime churn is extreme**: 15-17 transitions per 720-bar session — context instability kills signal quality
5. **Edge adjustment kills valid follow-up**: After first loss, edge_adjustment=-12 suppresses next signal's confidence by 12 points
6. **Partial exits capture crumbs, stops take full hits**: Flow deterioration exits at +$4.61/+$5.69 vs stop losses at -$62.47/-$42.07
7. **Only MomentumFlow fires**: 100% of trades are MomentumFlow shorts — strategy diversity is theoretical, not actual
8. **Signal extraction is extremely sparse**: 0.98% signal-to-pattern ratio — vast majority of detected patterns never generate trades
9. **One great trade saves everything**: 2026-02-04's $71.91 winner (score 128.5, patterns+strategy) proves the system works when aligned
10. **The winning formula**: Score >70 + patterns detected + no edge penalty = profitable trades
11. **Fix priority order**: Entry quality > regime stability > edge warmup > exit asymmetry > observability
12. **Quick wins available**: Threshold raise + edge warmup can be done in <2 hours and should eliminate 100% of borderline losses

## Root-Cause Ranking (by expected impact on expectancy)

| Rank | Blocker | Category | Evidence | Expected Impact |
|------|---------|----------|----------|-----------------|
| 1 | Borderline entries (58-70) | Signal Quality | 2 trades, 0% WR, -$124.94 | Removing these → net PnL improves by +$124.94 |
| 2 | Regime churn (15-17 flips/session) | Regime Classification | Context changes every ~45 bars | Reduces false strategy switches, improves signal context stability |
| 3 | Edge penalty after 1 trade | Signal Quality | -12 adjustment on trade #2 (base 79→67) | Valid signals suppressed, reduces opportunity set |
| 4 | Exit asymmetry (tiny partials vs full stops) | Execution/Exit Logic | Partial: +$4.61, Stop: -$62.47 | More time for winners to run, better expectancy ratio |
| 5 | Missing observability fields | Data Quality | regime=null in signals, null scores in older trades | Better diagnosis, faster iteration cycles |

## Blocker #1: Borderline Entry Quality

**Current state**: `threshold=58`, `min_confidence=58`, `require_pattern=false`
- Signals with `combined_score=58.5` (just 0.5 above threshold) enter with no pattern confirmation
- These strategy-only signals at borderline confidence are net catastrophic

**Evidence breakdown**:
- Trade at 15:49 on 2026-02-03: `combined=58.5, strategy=58.5, pattern=0` → stop loss in 5 min, -$62.47
- Same trade in phase_4_validation: identical result
- Compare with winning 2026-02-04: `combined=128.5, strategy=90.2, pattern=85.0` → held 13 min, +$71.91

**Fix: Conditional quality gate**
```
IF pattern_score > 0:
    threshold = 58 (patterns provide directional confirmation)
ELSE (strategy-only):
    threshold = 68 (strategy must be high-conviction when no pattern)
```

This preserves the multi-layer advantage while filtering low-quality strategy-only signals.

## Blocker #2: Regime Churn

**Current state**: `regime_refresh_bars=12` (refresh every ~12 minutes on 1m bars)
- 2026-02-03: 16 regime detections, 15 transitions → regime flip every ~45 bars
- Final regime always lands on MIXED (not useful as a filter)

**Fix: Increase cadence + add hysteresis**
- Change `regime_refresh_bars` from 12 → 30 (refresh every ~30 min)
- Add "sticky" regime: require 2 consecutive same-regime detections before flip
- This halves the transition rate and filters out noise flips

## Blocker #3: Edge Adjustment at Low Sample

**Current state**: Edge formula `(win_rate - 0.5) * 36 + (pf - 1) * 6 + expectancy * 4`
- After 1 losing trade: win_rate ≈ 0.33 → (0.33-0.5)*36 = -6.0
- Plus pf=0 → (0-1)*6 = -6.0 → total clamps to -12.0
- Applied to next signal: base_confidence 79.0 → adjusted 67.0

**Fix: Warmup period**
- Don't apply edge adjustment until strategy has ≥ 3 trades in session
- This prevents single-trade statistical noise from suppressing valid signals
- After warmup, ramp coefficient gradually (50% at trade 3, 75% at trade 4, 100% at trade 5+)

## Blocker #4: Exit Asymmetry

**Current state**:
- `_maybe_take_partial_profit`: exits 50% on ANY flow deterioration (signed_aggression sign flip)
- No minimum hold time before partial exit
- Stop loss at full ATR×1.8 distance

**Result**: Winners are trimmed to +$4-5, losers run full stops at -$42-62

**Fix: Minimum hold + minimum R-multiple before partial**
- Add `partial_min_hold_bars=3` (don't take partials before 3 bars held)
- Add minimum unrealized R-multiple of 0.5R before flow deterioration partial triggers
- This gives winners more room to develop while keeping protective intent

## Blocker #5: Observability

**Current gaps**:
- `regime` field is null in all signal events
- Trade events in older runs have null score/flow fields
- No marker for rejected signals (we know signals were generated but not why candidates were filtered)

**Fix: Add rejection tracking**
- Add `signal_rejected` marker type with gate_reason, candidate_score, rejection_threshold fields
- Include regime + micro_regime in all signal metadata
- This enables deterministic post-mortem analysis

---

## Implementation Plan

### P0 — Critical (implement first, ~2 hours)

#### 1. Conditional Quality Gate
**File**: `market_regime_detection/src/multi_layer_decision.py`
- Modify threshold comparison (line ~240) to use higher threshold when pattern_score=0
- Add `strategy_only_threshold` parameter (default 68)

**File**: `market_regime_detection/src/day_trading_manager.py`
- Pass `strategy_only_threshold` through `_build_multilayer_for_ticker()`
- Expose in AOS config under `multilayer` section

#### 2. Edge Adjustment Warmup
**File**: `market_regime_detection/src/day_trading_manager.py`
- Modify `_strategy_edge_adjustment()` (line ~1769) to return 0.0 if trade count < 3
- Add ramp factor: `ramp = min(1.0, max(0.0, (n - 2) / 3.0))` → multiply edge by ramp

#### 3. Regime Refresh Cadence
**File**: `market_regime_detection/src/day_trading_manager.py`
- Change default `regime_refresh_bars` from 12 to 30
- Add hysteresis: track `_pending_regime` and only apply after 2 consecutive same detections

### P1 — High Priority (next session, ~2 hours)

#### 4. Partial Exit Minimum Hold
**File**: `market_regime_detection/src/day_trading_manager.py`
- Add `partial_min_hold_bars=3` parameter
- Check bars held before allowing flow-deterioration partial exits
- Add minimum unrealized PnL check (0.5R) for flow-based partials

#### 5. Signal Rejection Markers
**File**: `market_regime_detection/src/day_trading_manager.py`
- In `_process_trading_bar` E6 section, when `l2_filtered`, add detailed marker
- In multi-layer evaluate, when below threshold, add detailed marker
- Schema: `{gate: "threshold|l2|pattern|cooldown", candidate_score, threshold_used, regime, micro_regime}`

### P2 — Medium Priority (DONE)

#### 6. Regime Hysteresis ✓
- Implemented: `_pending_regime` tracking, 2 consecutive same-detection before flip
- In `_maybe_refresh_regime()` — session attribute `_pending_regime`

#### 7. Time-of-Day Thresholds ✓
- Implemented: `_time_of_day_threshold_boost()` static method
- Midday (10:30-14:00 ET): +5 to both `threshold` and `strategy_only_threshold`
- Open/close: unchanged (boost=0)
- `tod_threshold_boost` reported in `layer_scores` and `signal_rejected` payloads

#### 8. Enhanced Observability ✓
- All signal metadata includes `regime` + `micro_regime`
- `signal_rejected` emitted for both L2 and threshold gate rejections
- Rejection payloads include: gate, score, threshold, regime, tod_boost, reasoning
- `layer_scores` includes `tod_threshold_boost`, `weights_snapshot`, `l2_quality_ok`

---

## New Parameter Set (copy-paste for AOS config)

```json
{
  "multilayer": {
    "pattern_weight": 0.45,
    "strategy_weight": 0.55,
    "threshold": 58,
    "strategy_only_threshold": 68,
    "require_pattern": false,
    "volume_confirm_ratio": 1.15
  },
  "regime_refresh_bars": 30,
  "edge_warmup_trades": 3,
  "partial_min_hold_bars": 3,
  "partial_min_r_multiple": 0.5
}
```

## Expected Impact

| Change | Trades Eliminated | PnL Impact | Confidence |
|--------|-------------------|------------|------------|
| Threshold 68 for strategy-only | 2 borderline trades | +$124.94 saved | HIGH (direct evidence) |
| Edge warmup | 0 eliminated, 1 improved | +$5-15 (better signal on trade #2) | MEDIUM |
| Regime refresh 30 bars | TBD (fewer false switches) | Indirect improvement | MEDIUM |
| Partial min hold 3 bars | 0 eliminated, 2 improved | +$10-30 (winners run longer) | MEDIUM |

**Conservative estimate**: P0 fixes alone should flip aggregate PnL from -$140 to approximately -$15 to +$10.
**With P1**: Expected to reach breakeven or slight positive territory.

## Go/No-Go Criteria for Production

1. **Minimum**: 10 OOS days with ≥ 5 trading days producing signals
2. **Win rate**: ≥ 50% on scored trades (excluding borderline)
3. **Profit factor**: ≥ 1.2 on aggregate
4. **Max single-day loss**: < $100
5. **No borderline entries**: 0 trades with combined_score < 68 and pattern_score = 0
6. **Regime stability**: ≤ 8 transitions per session (down from 15-17)
