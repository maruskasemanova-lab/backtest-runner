import { ProFieldGuide, ProPlaybookItem, StrategyRuleOverview } from "./types";

/** Human-readable metadata for each known strategy module. */
export const STRATEGY_DESCRIPTIONS: Record<string, string> = {
  momentum_flow:
    "Uses real-time L2 order flow to detect directional momentum surges. Best in trending markets.",
  absorption_reversal:
    "Detects when large resting orders absorb aggressive flow, signaling an imminent reversal.",
  exhaustion_fade:
    "Identifies when a directional move is losing steam - fades the move for mean-reversion.",
  scalp_l2_intrabar:
    "Ultra-short-term scalping using intrabar L2 microstructure - aggression, book pressure, spreads.",
  iceberg_defense:
    "Exits positions when hidden iceberg orders are detected working against your direction.",
  mean_reversion:
    "Enters when price deviates significantly from its mean (VWAP/MA), expecting a return to fair value.",
  momentum:
    "Classic breakout strategy - enters after consolidation range is broken on high volume.",
  pullback:
    "Enters on pullbacks within an established trend. Waits for retrace to MA support.",
  rotation:
    "Detects rotation patterns within price action. Capitalizes on regime transitions.",
  vwap_magnet:
    "Trades the tendency of price to gravitate toward VWAP with exhaustion signals.",
  volume_profile:
    "Uses volume-at-price distribution to identify high-volume nodes and low-volume gaps.",
  gap_liquidity:
    "Trades gap fills and liquidity voids with confirmation from L2 book dynamics.",
};

export const PRO_FIELD_GUIDE: Record<string, ProFieldGuide> = {
  allowed_regimes: { range: "1-2 regimes", behavior: "Keep only regimes where this strategy has stable expectancy and low variance." },
  exit_mode: { range: "global/custom", behavior: "Use global for consistent portfolio exits, custom for strategy-specific behavior." },
  risk_mode: { range: "global/custom", behavior: "Use global for uniform risk budget, custom when edge quality differs by strategy." },
  entry_deviation_pct: { range: "0.3-1.2%", behavior: "Higher means fewer but deeper mean-reversion setups." },
  min_confidence: { range: "55-70", behavior: "Raise when false positives increase; lower only with strong post-trade validation." },
  volume_confirmation: { range: "on", behavior: "Disable only if the ticker has unreliable volume patterns intraday." },
  volume_confirm: { range: "on", behavior: "Require volume agreement when entries are too frequent or weak." },
  volume_lookback: { range: "10-40 bars", behavior: "Shorter reacts faster; longer smooths noise and stabilizes thresholds." },
  volume_exhaustion_ratio: { range: "0.7-1.0", behavior: "Lower values trigger earlier exhaustion signals, higher values are stricter." },
  volume_stop_pct: { range: "0.5-1.8%", behavior: "Tighten in low-liquidity names, loosen when trend legs need room." },
  trailing_stop_pct: { range: "0.3-1.5%", behavior: "Tighter protects quickly; wider captures runners but increases giveback." },
  rr_ratio: { range: "1.4-3.0", behavior: "Higher RR needs cleaner entries and lower hit-rate tolerance." },
  pullback_threshold_pct: { range: "0.3-0.9%", behavior: "Higher waits for deeper pullbacks and reduces chase risk." },
  ma_fast_period: { range: "20-80", behavior: "Faster MA adapts quickly but can overreact in chop." },
  ma_slow_period: { range: "80-200", behavior: "Use a slower anchor to avoid trend flips from short-term noise." },
  volume_surge_ratio: { range: "1.1-1.8", behavior: "Raise to require stronger participation before taking pullback continuation." },
  consolidation_bars: { range: "6-20", behavior: "Longer consolidation often gives stronger breakout context." },
  volume_threshold: { range: "1.2-2.2", behavior: "Higher threshold filters weak breakouts that fail quickly." },
  consolidation_range_pct: { range: "0.3-1.2%", behavior: "Smaller ranges enforce tighter compression before breakout entries." },
  breakout_pct: { range: "0.08-0.35%", behavior: "Higher value avoids micro-breaks but can enter later." },
  lookback_period: { range: "8-30", behavior: "Longer windows make rotation signals steadier and less reactive." },
  rotation_threshold: { range: "0.3-0.9", behavior: "Raise to demand cleaner directional rotation before entry." },
  volume_increase_ratio: { range: "1.0-1.4", behavior: "Higher ratio favors rotations with stronger participation." },
  min_distance_pct: { range: "0.2-0.8%", behavior: "Avoid VWAP entries too close to fair value where edge is thin." },
  max_distance_pct: { range: "2.0-5.0%", behavior: "Cap extreme dislocations that often occur during unstable conditions." },
  bars_since_vwap_threshold: { range: "3-12", behavior: "Higher value waits for more persistent dislocation before entry." },
  profile_lookback: { range: "40-120", behavior: "Longer profile improves node stability but reacts slower to regime shifts." },
  num_bins: { range: "16-40", behavior: "Too low hides structure; too high overfits noise." },
  pb_threshold: { range: "0.45-0.8", behavior: "Raise to require clearer profile imbalance before signal." },
  symmetry_tolerance_pct: { range: "0.05-0.2%", behavior: "Tighter tolerance enforces more uniform node rejection." },
  gap_threshold_pct: { range: "0.4-1.5%", behavior: "Higher thresholds ignore marginal gaps that lack structural importance." },
  gap_fill_tolerance_pct: { range: "0.05-0.2%", behavior: "Wait for near-complete fills to optimize entry risk." },
};

export const DEFAULT_PRO_PLAYBOOK: ProPlaybookItem[] = [
  { label: "Execution Layer", guidance: "Use strategy settings for structural tuning. Use global execution modules for portfolio-wide protections." },
  { label: "Regime alignment", guidance: "Ensure at least half your enabled cast is aligned with expected session conditions." }
];

export const PRO_STRATEGY_PLAYBOOK: Record<string, ProPlaybookItem[]> = {
  momentum_flow: [
    { label: "Open focus", guidance: "Keep thresholds low (0.01-0.03) near open for explosive moves." },
    { label: "Midday chop", guidance: "Raise imbalance and aggression thresholds >0.06 to avoid fakeouts." }
  ],
  scalp_l2_intrabar: [
    { label: "Spread penalty", guidance: "Aggressively penalize flow scores when spread > 8bps." },
    { label: "Flow margin", guidance: "Require strict flow evidence margin during low liquidity periods." }
  ],
  mean_reversion: [
    { label: "VIX awareness", guidance: "Widen entry_deviation_pct when macro VIX is expanding." },
    { label: "Convergence failure", guidance: "Don't fight regime transitions; ensure allowed_regimes excludes TRENDING." }
  ],
  pullback: [
    { label: "Trend strength", guidance: "Only trade when ADX > 25 or MA slopes are steep." },
    { label: "Support bounce", guidance: "Require volume surge on the reversal bar, not just the pullback leg." }
  ],
  vwap_magnet: [
    { label: "Morning session", guidance: "First VWAP touches are highest probability. Subsequent fades lose edge." },
    { label: "Volatility guard", guidance: "Use atr_stop_mult and trailing_stop_pct to adapt around open-drive volatility." }
  ]
};

export const DEFAULT_BUILTIN_RULE_OVERVIEW: StrategyRuleOverview = {
  entry: [
    "Strategy is enabled and current regime is allowed.",
    "No active position conflict for this strategy (or pyramiding limits respected).",
    "Signal must pass confidence/evidence threshold and risk sanity checks.",
    "Runtime gates apply: cooldown, max trades/day, L2 gate, diversification gate.",
  ],
  exit: [
    "Hard exits: stop-loss, take-profit, trailing stop policy.",
    "Adaptive exits: momentum fail-fast, adverse flow, time exit.",
    "Risk brakes: max daily loss and run-level drawdown halt.",
    "Optional custom exit formula can force-close position.",
  ],
};

export const BUILTIN_RULE_OVERVIEW: Record<string, StrategyRuleOverview> = {
  absorption_reversal: {
    entry: ["Requires absorption + divergence confirmation before reversal signal.", "Uses min_absorption_rate, min_divergence, min_signed_aggression, min_book_pressure.", "Checks minimum extension from fair value via min_price_extension_pct.", "Applies confidence threshold and flow-aware evidence gate."],
    exit: ["Uses ATR/volume-based stop framework (effective risk mode values).", "Uses RR + trailing policy (effective exit mode values).", "Runtime adverse-flow and fail-fast exits can close early.", "Optional custom exit formula can override normal hold behavior."],
  },
  momentum_flow: {
    entry: ["Requires directional flow alignment and aggression confirmation.", "Uses min_signed_aggression, min_directional_consistency, min_imbalance, min_sweep_intensity.", "Evidence layer must pass combined threshold + confirming source checks.", "L2 confirmation and momentum diversification gates are applied."],
    exit: ["Stop-loss / take-profit / trailing policy from effective risk+exit config.", "Momentum fail-fast can close when flow deteriorates quickly.", "Adverse flow and time exit policies run continuously.", "Optional custom exit formula can force close by your own rule."]
  },
  exhaustion_fade: {
    entry: ["Requires exhaustion profile (delta/sweep) and absorption divergence.", "Uses min_delta_zscore, max_sweep_intensity, min_absorption_rate, min_divergence.", "Book pressure and confidence filters reduce weak countertrend entries.", "Runtime trade-limit and cooldown gates still apply."],
    exit: ["RR and trailing define baseline fade exit shape.", "Risk module can tighten/loosen stops by risk mode.", "Adverse flow and fail-fast can pre-empt target exits.", "Optional custom exit formula can terminate position immediately."]
  },
  iceberg_defense: {
    entry: ["Requires opposing iceberg/hidden liquidity read before entry/defense action.", "Uses min_iceberg_bias, max_opposing_aggression, min_absorption_rate.", "Flow evidence gate validates direction quality.", "Confidence and session-level guardrails remain active."],
    exit: ["Can close early when opposing aggression breaches configured ceiling.", "Uses effective ATR/RR/trailing controls for baseline exits.", "Adverse-flow and time-based exits run in parallel.", "Optional custom exit formula can force protection exit."]
  },
  scalp_l2_intrabar: {
    entry: ["Requires strong intrabar microstructure confirmation (flow + spread + volatility).", "Checks min_flow_score, aggression, consistency, imbalance, participation, intrabar windows.", "Cost filters enforce minimum reward-to-cost and spread constraints.", "L2 coverage/confirmation and evidence threshold gating are mandatory."],
    exit: ["Tight stop/trailing logic is evaluated continuously.", "Time/adverse-flow/fail-fast exits protect against micro-regime flips.", "Intrabar deterioration can tighten trailing behavior.", "Optional custom exit formula allows custom microstructure kill-switch."]
  },
  mean_reversion: {
    entry: ["Looks for statistically meaningful deviation from fair value.", "Uses entry_deviation_pct with volume exhaustion/confirmation filters.", "Regime gating favors CHOPPY/MIXED contexts.", "Confidence/evidence threshold + runtime risk gates still apply."],
    exit: ["Uses effective trailing + volume stop policy.", "Session-level time exit and adverse-flow exits can close early.", "Run-level max-loss/drawdown guards can halt the day.", "Optional custom exit formula adds your own close condition."]
  },
  momentum: {
    entry: ["Requires consolidation structure + breakout confirmation.", "Uses consolidation_bars, consolidation_range_pct, breakout_pct, volume_threshold.", "Confidence and evidence threshold must clear runtime gate.", "Cooldown/trade-cap and risk filters apply before queueing signal."],
    exit: ["RR + trailing define runner capture logic.", "Volume/risk mode can adapt stop tightness.", "Adverse-flow/fail-fast/time exits remain active.", "Optional custom exit formula can close based on custom momentum decay."]
  },
  pullback: {
    entry: ["Requires trend alignment plus pullback depth + participation return.", "Uses MA periods, pullback_threshold_pct, volume_surge_ratio.", "Confidence and evidence thresholds must pass.", "Runtime guardrails (cooldown, limits, L2 gates) are enforced."],
    exit: ["Uses effective RR/trailing/volume-stop framework.", "Adverse flow and time-based exits may close before TP.", "Portfolio/daily risk brakes remain active.", "Optional custom exit formula can enforce discretionary-style management."]
  },
  rotation: {
    entry: ["Looks for regime rotation via lookback_period and rotation_threshold.", "Volume_increase_ratio and confidence help filter weak rotations.", "Evidence threshold and runtime guards are still required.", "Trade only when current micro-regime supports selected strategy set."],
    exit: ["Trailing and risk stops handle rotation reversals.", "Time/adverse-flow exits run as secondary protection.", "Run-level drawdown control can force session stop.", "Optional custom exit formula can lock fast rotation exits."]
  },
  vwap_magnet: {
    entry: ["Requires distance-from-VWAP window and persistence criteria.", "Uses min_distance_pct, max_distance_pct, bars_since_vwap_threshold.", "Volume confirmation and confidence/evidence gate reduce low-quality entries.", "Session-level trade limits and cooldown rules apply."],
    exit: ["Reversion exits are managed by trailing + volume stop policy.", "Adverse-flow/time exits can close before full VWAP mean-reversion.", "Global risk halts remain active at session/run level.", "Optional custom exit formula lets you define VWAP-specific close logic."]
  },
  volume_profile: {
    entry: ["Uses profile structure and imbalance conditions for setup validation.", "Inputs include profile_lookback, num_bins, pb_threshold, symmetry_tolerance_pct.", "Confidence/evidence gate is required for execution.", "Runtime risk/cooldown/L2 gates remain active."],
    exit: ["ATR/RR/trailing controls define node-to-node risk envelope.", "Adverse-flow and time exits can close profile trades early.", "Session/run drawdown protections still apply.", "Optional custom exit formula can encode custom profile invalidation."]
  },
  gap_liquidity: {
    entry: ["Requires meaningful gap dislocation and liquidity-structure confirmation.", "Uses gap_threshold_pct, swing_lookback, liquidity_cluster_bars, gap_fill_tolerance_pct.", "Confidence/evidence threshold and runtime gates apply.", "Signal is queued only after all gate checks pass."],
    exit: ["ATR/RR/trailing controls manage open-gap volatility.", "Adverse-flow/fail-fast/time exits may close before full gap objective.", "Risk brakes (daily/run drawdown) can force immediate closure.", "Optional custom exit formula lets you encode bespoke gap-failure logic."]
  }
};

export const DEFAULT_FORMULA_VARIABLES = [
  "price",
  "open",
  "high",
  "low",
  "volume",
  "vwap",
  "sma5",
  "sma10",
  "sma20",
  "sma50",
  "ema9",
  "ema21",
  "macd",
  "macd_signal",
  "macd_hist",
  "bollinger_upper",
  "bollinger_lower",
  "bollinger_mid",
];

export const STRATEGY_RECOMMENDED_PARAMS = {
  mean_reversion: {
    entry_deviation_pct: 0.3,
    min_confidence: 60.0,
    volume_confirmation: true,
    volume_lookback: 20,
    volume_exhaustion_ratio: 0.9,
    volume_stop_pct: 0.6,
    trailing_stop_pct: 0.3,
    allowed_regimes: ["CHOPPY", "MIXED"],
  },
  momentum: {
    consolidation_bars: 10,
    volume_threshold: 1.5,
    volume_lookback: 20,
    consolidation_range_pct: 0.6,
    breakout_pct: 0.15,
    volume_stop_pct: 0.8,
    rr_ratio: 2.5,
    trailing_stop_pct: 1.5,
    allowed_regimes: ["TRENDING"],
  },
  pullback: {
    pullback_threshold_pct: 0.5,
    ma_fast_period: 50,
    ma_slow_period: 100,
    volume_lookback: 20,
    volume_surge_ratio: 1.2,
    volume_stop_pct: 1.0,
    rr_ratio: 1.5,
    trailing_stop_pct: 1.0,
    allowed_regimes: ["TRENDING"],
  },
  rotation: {
    lookback_period: 10,
    rotation_threshold: 0.5,
    volume_lookback: 10,
    volume_increase_ratio: 1.05,
    volume_stop_pct: 0.9,
    trailing_stop_pct: 1.0,
    allowed_regimes: ["MIXED", "CHOPPY"],
  },
  vwap_magnet: {
    min_distance_pct: 0.4,
    max_distance_pct: 3.0,
    bars_since_vwap_threshold: 5,
    volume_confirm: true,
    volume_lookback: 20,
    volume_stop_pct: 0.7,
    trailing_stop_pct: 0.4,
    allowed_regimes: ["CHOPPY", "MIXED"],
  },
  scalp_l2_intrabar: {
    enabled: true,
    allowed_regimes: ["TRENDING", "CHOPPY", "MIXED"],
    min_flow_score: 48.0,
    min_signed_aggression: 0.045,
    min_directional_consistency: 0.58,
    min_imbalance: 0.03,
    min_book_pressure: 0.02,
    min_participation_ratio: 0.05,
    min_flow_score_trend_3bar: -2.0,
    min_intrabar_move_pct: 0.035,
    min_intrabar_push_ratio: 0.12,
    min_intrabar_coverage_points: 4,
    min_intrabar_directional_consistency: 0.12,
    intrabar_eval_window_seconds: 5,
    min_intrabar_window_move_pct: 0.015,
    min_intrabar_window_push_ratio: 0.08,
    min_intrabar_window_directional_consistency: 0.08,
    max_intrabar_micro_volatility_bps: 18.0,
    max_intrabar_spread_bps: 8.0,
    spread_penalty_floor_bps: 4.0,
    spread_flow_score_penalty_per_bps: 0.45,
    min_round_trip_cost_bps: 6.5,
    spread_cost_multiplier: 1.1,
    min_reward_to_cost_ratio: 1.7,
    min_flow_signal_margin: 0.01,
    max_abs_price_extension_pct: 1.8,
    require_intrabar_confirmation: false,
    no_intrabar_flow_buffer: 10.0,
    min_confidence: 55.0,
    atr_stop_multiplier: 0.66,
    min_stop_loss_pct: 0.05,
    rr_ratio: 1.35,
    trailing_stop_pct: 0.28,
  },
};
