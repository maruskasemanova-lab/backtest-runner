import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { defaultStrategyApiUrl } from "../utils";
import { useTickerStrategyPresets } from "./strategy-settings/useTickerStrategyPresets";

/** Human-readable metadata for each known strategy module. */
const STRATEGY_DESCRIPTIONS: Record<string, string> = {
  momentum_flow:
    "Uses real-time L2 order flow to detect directional momentum surges. Best in trending markets.",
  absorption_reversal:
    "Detects when large resting orders absorb aggressive flow, signaling an imminent reversal.",
  exhaustion_fade:
    "Identifies when a directional move is losing steam — fades the move for mean-reversion.",
  scalp_l2_intrabar:
    "Ultra-short-term scalping using intrabar L2 microstructure — aggression, book pressure, spreads.",
  iceberg_defense:
    "Exits positions when hidden iceberg orders are detected working against your direction.",
  mean_reversion:
    "Enters when price deviates significantly from its mean (VWAP/MA), expecting a return to fair value.",
  momentum:
    "Classic breakout strategy — enters after consolidation range is broken on high volume.",
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

interface ProFieldGuide {
  range: string;
  behavior: string;
}

interface ProPlaybookItem {
  label: string;
  guidance: string;
}

interface StrategyRuleOverview {
  entry: string[];
  exit: string[];
}

const PRO_FIELD_GUIDE: Record<string, ProFieldGuide> = {
  allowed_regimes: {
    range: "1-2 regimes",
    behavior: "Keep only regimes where this strategy has stable expectancy and low variance.",
  },
  exit_mode: {
    range: "global/custom",
    behavior: "Use global for consistent portfolio exits, custom for strategy-specific behavior.",
  },
  risk_mode: {
    range: "global/custom",
    behavior: "Use global for uniform risk budget, custom when edge quality differs by strategy.",
  },
  entry_deviation_pct: {
    range: "0.3-1.2%",
    behavior: "Higher means fewer but deeper mean-reversion setups.",
  },
  min_confidence: {
    range: "55-70",
    behavior: "Raise when false positives increase; lower only with strong post-trade validation.",
  },
  volume_confirmation: {
    range: "on",
    behavior: "Disable only if the ticker has unreliable volume patterns intraday.",
  },
  volume_confirm: {
    range: "on",
    behavior: "Require volume agreement when entries are too frequent or weak.",
  },
  volume_lookback: {
    range: "10-40 bars",
    behavior: "Shorter reacts faster; longer smooths noise and stabilizes thresholds.",
  },
  volume_exhaustion_ratio: {
    range: "0.7-1.0",
    behavior: "Lower values trigger earlier exhaustion signals, higher values are stricter.",
  },
  volume_stop_pct: {
    range: "0.5-1.8%",
    behavior: "Tighten in low-liquidity names, loosen when trend legs need room.",
  },
  trailing_stop_pct: {
    range: "0.3-1.5%",
    behavior: "Tighter protects quickly; wider captures runners but increases giveback.",
  },
  rr_ratio: {
    range: "1.4-3.0",
    behavior: "Higher RR needs cleaner entries and lower hit-rate tolerance.",
  },
  pullback_threshold_pct: {
    range: "0.3-0.9%",
    behavior: "Higher waits for deeper pullbacks and reduces chase risk.",
  },
  ma_fast_period: {
    range: "20-80",
    behavior: "Faster MA adapts quickly but can overreact in chop.",
  },
  ma_slow_period: {
    range: "80-200",
    behavior: "Use a slower anchor to avoid trend flips from short-term noise.",
  },
  volume_surge_ratio: {
    range: "1.1-1.8",
    behavior: "Raise to require stronger participation before taking pullback continuation.",
  },
  consolidation_bars: {
    range: "6-20",
    behavior: "Longer consolidation often gives stronger breakout context.",
  },
  volume_threshold: {
    range: "1.2-2.2",
    behavior: "Higher threshold filters weak breakouts that fail quickly.",
  },
  consolidation_range_pct: {
    range: "0.3-1.2%",
    behavior: "Smaller ranges enforce tighter compression before breakout entries.",
  },
  breakout_pct: {
    range: "0.08-0.35%",
    behavior: "Higher value avoids micro-breaks but can enter later.",
  },
  lookback_period: {
    range: "8-30",
    behavior: "Longer windows make rotation signals steadier and less reactive.",
  },
  rotation_threshold: {
    range: "0.3-0.9",
    behavior: "Raise to demand cleaner directional rotation before entry.",
  },
  volume_increase_ratio: {
    range: "1.0-1.4",
    behavior: "Higher ratio favors rotations with stronger participation.",
  },
  min_distance_pct: {
    range: "0.2-0.8%",
    behavior: "Avoid VWAP entries too close to fair value where edge is thin.",
  },
  max_distance_pct: {
    range: "2.0-5.0%",
    behavior: "Cap extreme dislocations that often occur during unstable conditions.",
  },
  bars_since_vwap_threshold: {
    range: "3-12",
    behavior: "Higher value waits for more persistent dislocation before entry.",
  },
  profile_lookback: {
    range: "40-120",
    behavior: "Longer profile improves node stability but reacts slower to regime shifts.",
  },
  num_bins: {
    range: "16-40",
    behavior: "Too low hides structure; too high overfits noise.",
  },
  pb_threshold: {
    range: "0.45-0.8",
    behavior: "Raise to require clearer profile imbalance before signal.",
  },
  symmetry_tolerance_pct: {
    range: "0.1-0.3",
    behavior: "Lower tolerance demands cleaner asymmetry in profile shape.",
  },
  atr_stop_mult: {
    range: "1.8-3.2",
    behavior: "Higher multiplier reduces stop-outs but increases per-trade risk.",
  },
  atr_stop_multiplier: {
    range: "0.6-1.4",
    behavior: "Tune by realized volatility; too tight causes churn in noisy flow.",
  },
  gap_threshold_pct: {
    range: "0.2-0.8%",
    behavior: "Higher threshold focuses on meaningful dislocations.",
  },
  swing_lookback: {
    range: "10-40",
    behavior: "Longer swing context avoids reacting to single-bar spikes.",
  },
  liquidity_cluster_bars: {
    range: "3-10",
    behavior: "Increase when liquidity zones are unstable intraday.",
  },
  gap_fill_tolerance_pct: {
    range: "0.05-0.3%",
    behavior: "Tighter tolerance improves fill precision but lowers hit rate.",
  },
  min_absorption_rate: {
    range: "0.4-0.7",
    behavior: "Higher value means stronger passive absorption before reversal confirmation.",
  },
  min_divergence: {
    range: "0.1-0.3",
    behavior: "Raise to require clearer price-flow disagreement before fading.",
  },
  min_signed_aggression: {
    range: "0.03-0.12",
    behavior: "Higher threshold filters weak tape pressure and noise.",
  },
  min_book_pressure: {
    range: "0.0-0.15",
    behavior: "Increase when book signal quality is high and spoofing is low.",
  },
  min_price_extension_pct: {
    range: "0.08-0.3%",
    behavior: "Require enough extension so reversals have room to mean-revert.",
  },
  min_directional_consistency: {
    range: "0.45-0.75",
    behavior: "Higher consistency demands stable flow alignment over several bars.",
  },
  min_imbalance: {
    range: "0.02-0.08",
    behavior: "Raise only if one-sided book pressure reliably predicts continuation.",
  },
  min_sweep_intensity: {
    range: "0.05-0.2",
    behavior: "Higher values focus on strong aggressive sweeps in momentum legs.",
  },
  max_sweep_intensity: {
    range: "0.5-1.1",
    behavior: "Used as exhaustion cap; lower values fade earlier.",
  },
  min_delta_zscore: {
    range: "1.0-2.2",
    behavior: "Higher z-score requires statistically stronger tape extremes.",
  },
  min_iceberg_bias: {
    range: "0.35-0.7",
    behavior: "Raise when hidden-liquidity detection is noisy.",
  },
  max_opposing_aggression: {
    range: "0.01-0.08",
    behavior: "Lower cap exits sooner when opposite tape starts taking control.",
  },
  min_flow_score: {
    range: "45-65",
    behavior: "Raise for cleaner scalp entries when slippage is rising.",
  },
  min_participation_ratio: {
    range: "0.04-0.12",
    behavior: "Higher ratio ensures enough liquidity participation to support entries.",
  },
  min_flow_score_trend_3bar: {
    range: "-4 to +4",
    behavior: "Positive slope favors continuation; negative slope permits early fades.",
  },
  min_intrabar_move_pct: {
    range: "0.02-0.08%",
    behavior: "Require minimum intrabar displacement so fees do not dominate.",
  },
  min_intrabar_push_ratio: {
    range: "0.08-0.25",
    behavior: "Higher push ratio demands cleaner directional push inside the minute.",
  },
  min_intrabar_coverage_points: {
    range: "4-20",
    behavior: "More points increase robustness when intrabar feed has gaps.",
  },
  min_intrabar_directional_consistency: {
    range: "0.08-0.25",
    behavior: "Increase when sub-minute flow flips too often.",
  },
  intrabar_eval_window_seconds: {
    range: "3-12s",
    behavior: "Short window is reactive; longer window is more robust but slower.",
  },
  min_intrabar_window_move_pct: {
    range: "0.01-0.05%",
    behavior: "Use lower values on calm tickers and higher values on volatile ones.",
  },
  min_intrabar_window_push_ratio: {
    range: "0.05-0.2",
    behavior: "Raise to avoid weak micro-pushes that reverse immediately.",
  },
  min_intrabar_window_directional_consistency: {
    range: "0.05-0.2",
    behavior: "Higher setting requires stronger agreement across micro windows.",
  },
  max_intrabar_micro_volatility_bps: {
    range: "10-30 bps",
    behavior: "Lower cap avoids unstable microstructure conditions.",
  },
  max_intrabar_spread_bps: {
    range: "4-12 bps",
    behavior: "Tight cap protects against spread-driven edge decay.",
  },
  spread_penalty_floor_bps: {
    range: "2-8 bps",
    behavior: "Minimum spread penalty to avoid overestimating scalp edge.",
  },
  spread_flow_score_penalty_per_bps: {
    range: "0.2-0.8",
    behavior: "Increase penalty when spread expansion degrades fills.",
  },
  min_round_trip_cost_bps: {
    range: "4-12 bps",
    behavior: "Use realistic fee + spread + slippage floor for viability checks.",
  },
  spread_cost_multiplier: {
    range: "1.0-1.5",
    behavior: "Lift multiplier in names with unstable quote quality.",
  },
  min_reward_to_cost_ratio: {
    range: "1.4-2.5",
    behavior: "Raise when net expectancy weakens after transaction costs.",
  },
  min_flow_signal_margin: {
    range: "0.005-0.03",
    behavior: "Require stronger edge margin when model confidence is clustered.",
  },
  max_abs_price_extension_pct: {
    range: "1.0-2.5%",
    behavior: "Blocks entries after overextended bursts with poor continuation odds.",
  },
  require_intrabar_confirmation: {
    range: "on in volatile sessions",
    behavior: "Enable when minute-level signals need microstructure confirmation.",
  },
  no_intrabar_flow_buffer: {
    range: "6-18",
    behavior: "Higher buffer delays entries when intrabar confirmation is missing.",
  },
  min_stop_loss_pct: {
    range: "0.03-0.12%",
    behavior: "Keep above fee noise floor so stops are not pure micro-noise.",
  },
};

const DEFAULT_PRO_PLAYBOOK: ProPlaybookItem[] = [
  {
    label: "Regime fit",
    guidance: "Keep only regimes where the setup has stable expectancy in your recent sample.",
  },
  {
    label: "Entry quality",
    guidance: "Raise confidence and confirmation thresholds before increasing size or trade count.",
  },
  {
    label: "Exit discipline",
    guidance: "Re-check RR and trailing values whenever volatility and spread regime changes.",
  },
  {
    label: "Cost control",
    guidance: "Track spread plus slippage drift, then tighten filters if net edge compresses.",
  },
];

const PRO_STRATEGY_PLAYBOOK: Record<string, ProPlaybookItem[]> = {
  absorption_reversal: [
    {
      label: "Absorption gate",
      guidance: "min_absorption_rate is your main quality filter; raise it when fake reversals dominate.",
    },
    {
      label: "Flow contradiction",
      guidance: "Use min_divergence and min_signed_aggression together so reversal requires true tape disagreement.",
    },
    {
      label: "Context extension",
      guidance: "min_price_extension_pct avoids fading inside mid-range noise.",
    },
    {
      label: "Stop discipline",
      guidance: "Keep atr_stop_multiplier compact and use global risk mode if multiple reversal models run together.",
    },
  ],
  momentum_flow: [
    {
      label: "Tape pressure",
      guidance: "Synchronize min_signed_aggression, min_imbalance, and min_book_pressure to avoid one-metric bias.",
    },
    {
      label: "Consistency filter",
      guidance: "min_directional_consistency should rise in chop and can be looser in clean trend days.",
    },
    {
      label: "Sweep validation",
      guidance: "min_sweep_intensity should block weak impulse starts with low follow-through.",
    },
    {
      label: "Risk sync",
      guidance: "Use global exit and risk when you want momentum and breakout strategies to share the same risk frame.",
    },
  ],
  exhaustion_fade: [
    {
      label: "Exhaustion profile",
      guidance: "Pair min_delta_zscore with max_sweep_intensity to fade only stretched directional runs.",
    },
    {
      label: "Absorption confirmation",
      guidance: "min_absorption_rate and min_divergence should confirm that aggressive flow is being absorbed.",
    },
    {
      label: "Book stability",
      guidance: "Increase min_book_pressure only when depth data is stable and not spoof-heavy.",
    },
    {
      label: "Tighter exits",
      guidance: "Fade trades usually need faster stop logic than trend-following setups.",
    },
  ],
  iceberg_defense: [
    {
      label: "Hidden-liquidity read",
      guidance: "Use min_iceberg_bias as your primary trigger; raise it when detection quality is mixed.",
    },
    {
      label: "Opposing flow guard",
      guidance: "max_opposing_aggression should stay strict to cut positions once opposite tape appears.",
    },
    {
      label: "Absorption quality",
      guidance: "min_absorption_rate helps avoid exits from temporary quote noise.",
    },
    {
      label: "Portfolio alignment",
      guidance: "Apply global risk mode when iceberg defense is used as a shared protective layer.",
    },
  ],
  scalp_l2_intrabar: [
    {
      label: "Microstructure quality",
      guidance: "Control spread and volatility first (max_intrabar_spread_bps, max_intrabar_micro_volatility_bps).",
    },
    {
      label: "Signal strength",
      guidance: "Raise min_flow_score and min_flow_signal_margin when fills worsen or slippage rises.",
    },
    {
      label: "Cost viability",
      guidance: "Keep min_reward_to_cost_ratio and min_round_trip_cost_bps realistic for current fee model.",
    },
    {
      label: "Intrabar confirmation",
      guidance: "Enable require_intrabar_confirmation in unstable sessions to reduce false micro-breaks.",
    },
  ],
  mean_reversion: [
    {
      label: "Distance quality",
      guidance: "entry_deviation_pct should be high enough to avoid trading tiny deviations around fair value.",
    },
    {
      label: "Exhaustion check",
      guidance: "volume_exhaustion_ratio and volume_confirmation reduce entries against active trend expansion.",
    },
    {
      label: "Regime discipline",
      guidance: "Prefer CHOPPY and MIXED regimes unless trend decay is obvious.",
    },
    {
      label: "Stop width",
      guidance: "volume_stop_pct and trailing_stop_pct should reflect current intraday volatility cluster.",
    },
  ],
  momentum: [
    {
      label: "Compression quality",
      guidance: "consolidation_bars plus consolidation_range_pct define breakout structure quality.",
    },
    {
      label: "Participation",
      guidance: "volume_threshold should rise when low-volume breakouts fail quickly.",
    },
    {
      label: "Trigger precision",
      guidance: "breakout_pct balances early entry against breakout confirmation.",
    },
    {
      label: "Runner management",
      guidance: "Use wider trailing_stop_pct only if trend days routinely extend beyond first target.",
    },
  ],
  pullback: [
    {
      label: "Trend backbone",
      guidance: "ma_fast_period and ma_slow_period should stay aligned with the holding horizon.",
    },
    {
      label: "Retrace quality",
      guidance: "pullback_threshold_pct should avoid shallow pullbacks that are just noise.",
    },
    {
      label: "Re-entry demand",
      guidance: "volume_surge_ratio confirms renewed participation after retrace.",
    },
    {
      label: "Risk shape",
      guidance: "Calibrate rr_ratio and trailing_stop_pct together so pullback winners are not cut too early.",
    },
  ],
  rotation: [
    {
      label: "Cycle detection",
      guidance: "lookback_period and rotation_threshold set how quickly regime turns are recognized.",
    },
    {
      label: "Volume context",
      guidance: "volume_increase_ratio should confirm that rotation has real participation.",
    },
    {
      label: "Whipsaw control",
      guidance: "Increase confidence and thresholds in fragmented intraday tape.",
    },
    {
      label: "Exit cadence",
      guidance: "Use tighter trailing when rotation cycles are short and mean-reverting.",
    },
  ],
  vwap_magnet: [
    {
      label: "Dislocation window",
      guidance: "min_distance_pct and max_distance_pct define tradeable VWAP dislocation range.",
    },
    {
      label: "Persistence filter",
      guidance: "bars_since_vwap_threshold reduces entries from single-bar deviations.",
    },
    {
      label: "Participation check",
      guidance: "volume_confirm helps avoid low-liquidity mean-reversion traps.",
    },
    {
      label: "Reversion exits",
      guidance: "Use tighter trailing near VWAP because edge decays quickly after reversion.",
    },
  ],
  volume_profile: [
    {
      label: "Profile stability",
      guidance: "profile_lookback and num_bins should balance structural clarity vs responsiveness.",
    },
    {
      label: "Imbalance edge",
      guidance: "pb_threshold and symmetry_tolerance_pct filter weak profile asymmetries.",
    },
    {
      label: "Risk envelope",
      guidance: "atr_stop_mult should account for node-to-node travel distance.",
    },
    {
      label: "Target realism",
      guidance: "rr_ratio should match typical rotation between value area boundaries.",
    },
  ],
  gap_liquidity: [
    {
      label: "Gap significance",
      guidance: "gap_threshold_pct must be high enough so only material dislocations are traded.",
    },
    {
      label: "Structure context",
      guidance: "swing_lookback and liquidity_cluster_bars validate nearby liquidity targets.",
    },
    {
      label: "Fill precision",
      guidance: "gap_fill_tolerance_pct controls how strict the fill-completion trigger is.",
    },
    {
      label: "Volatility guard",
      guidance: "Use atr_stop_mult and trailing_stop_pct to adapt around open-drive volatility.",
    },
  ],
};

const DEFAULT_BUILTIN_RULE_OVERVIEW: StrategyRuleOverview = {
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

const BUILTIN_RULE_OVERVIEW: Record<string, StrategyRuleOverview> = {
  absorption_reversal: {
    entry: [
      "Requires absorption + divergence confirmation before reversal signal.",
      "Uses min_absorption_rate, min_divergence, min_signed_aggression, min_book_pressure.",
      "Checks minimum extension from fair value via min_price_extension_pct.",
      "Applies confidence threshold and flow-aware evidence gate.",
    ],
    exit: [
      "Uses ATR/volume-based stop framework (effective risk mode values).",
      "Uses RR + trailing policy (effective exit mode values).",
      "Runtime adverse-flow and fail-fast exits can close early.",
      "Optional custom exit formula can override normal hold behavior.",
    ],
  },
  momentum_flow: {
    entry: [
      "Requires directional flow alignment and aggression confirmation.",
      "Uses min_signed_aggression, min_directional_consistency, min_imbalance, min_sweep_intensity.",
      "Evidence layer must pass combined threshold + confirming source checks.",
      "L2 confirmation and momentum diversification gates are applied.",
    ],
    exit: [
      "Stop-loss / take-profit / trailing policy from effective risk+exit config.",
      "Momentum fail-fast can close when flow deteriorates quickly.",
      "Adverse flow and time exit policies run continuously.",
      "Optional custom exit formula can force close by your own rule.",
    ],
  },
  exhaustion_fade: {
    entry: [
      "Requires exhaustion profile (delta/sweep) and absorption divergence.",
      "Uses min_delta_zscore, max_sweep_intensity, min_absorption_rate, min_divergence.",
      "Book pressure and confidence filters reduce weak countertrend entries.",
      "Runtime trade-limit and cooldown gates still apply.",
    ],
    exit: [
      "RR and trailing define baseline fade exit shape.",
      "Risk module can tighten/loosen stops by risk mode.",
      "Adverse flow and fail-fast can pre-empt target exits.",
      "Optional custom exit formula can terminate position immediately.",
    ],
  },
  iceberg_defense: {
    entry: [
      "Requires opposing iceberg/hidden liquidity read before entry/defense action.",
      "Uses min_iceberg_bias, max_opposing_aggression, min_absorption_rate.",
      "Flow evidence gate validates direction quality.",
      "Confidence and session-level guardrails remain active.",
    ],
    exit: [
      "Can close early when opposing aggression breaches configured ceiling.",
      "Uses effective ATR/RR/trailing controls for baseline exits.",
      "Adverse-flow and time-based exits run in parallel.",
      "Optional custom exit formula can force protection exit.",
    ],
  },
  scalp_l2_intrabar: {
    entry: [
      "Requires strong intrabar microstructure confirmation (flow + spread + volatility).",
      "Checks min_flow_score, aggression, consistency, imbalance, participation, intrabar windows.",
      "Cost filters enforce minimum reward-to-cost and spread constraints.",
      "L2 coverage/confirmation and evidence threshold gating are mandatory.",
    ],
    exit: [
      "Tight stop/trailing logic is evaluated continuously.",
      "Time/adverse-flow/fail-fast exits protect against micro-regime flips.",
      "Intrabar deterioration can tighten trailing behavior.",
      "Optional custom exit formula allows custom microstructure kill-switch.",
    ],
  },
  mean_reversion: {
    entry: [
      "Looks for statistically meaningful deviation from fair value.",
      "Uses entry_deviation_pct with volume exhaustion/confirmation filters.",
      "Regime gating favors CHOPPY/MIXED contexts.",
      "Confidence/evidence threshold + runtime risk gates still apply.",
    ],
    exit: [
      "Uses effective trailing + volume stop policy.",
      "Session-level time exit and adverse-flow exits can close early.",
      "Run-level max-loss/drawdown guards can halt the day.",
      "Optional custom exit formula adds your own close condition.",
    ],
  },
  momentum: {
    entry: [
      "Requires consolidation structure + breakout confirmation.",
      "Uses consolidation_bars, consolidation_range_pct, breakout_pct, volume_threshold.",
      "Confidence and evidence threshold must clear runtime gate.",
      "Cooldown/trade-cap and risk filters apply before queueing signal.",
    ],
    exit: [
      "RR + trailing define runner capture logic.",
      "Volume/risk mode can adapt stop tightness.",
      "Adverse-flow/fail-fast/time exits remain active.",
      "Optional custom exit formula can close based on custom momentum decay.",
    ],
  },
  pullback: {
    entry: [
      "Requires trend alignment plus pullback depth + participation return.",
      "Uses MA periods, pullback_threshold_pct, volume_surge_ratio.",
      "Confidence and evidence thresholds must pass.",
      "Runtime guardrails (cooldown, limits, L2 gates) are enforced.",
    ],
    exit: [
      "Uses effective RR/trailing/volume-stop framework.",
      "Adverse flow and time-based exits may close before TP.",
      "Portfolio/daily risk brakes remain active.",
      "Optional custom exit formula can enforce discretionary-style management.",
    ],
  },
  rotation: {
    entry: [
      "Looks for regime rotation via lookback_period and rotation_threshold.",
      "Volume_increase_ratio and confidence help filter weak rotations.",
      "Evidence threshold and runtime guards are still required.",
      "Trade only when current micro-regime supports selected strategy set.",
    ],
    exit: [
      "Trailing and risk stops handle rotation reversals.",
      "Time/adverse-flow exits run as secondary protection.",
      "Run-level drawdown control can force session stop.",
      "Optional custom exit formula can lock fast rotation exits.",
    ],
  },
  vwap_magnet: {
    entry: [
      "Requires distance-from-VWAP window and persistence criteria.",
      "Uses min_distance_pct, max_distance_pct, bars_since_vwap_threshold.",
      "Volume confirmation and confidence/evidence gate reduce low-quality entries.",
      "Session-level trade limits and cooldown rules apply.",
    ],
    exit: [
      "Reversion exits are managed by trailing + volume stop policy.",
      "Adverse-flow/time exits can close before full VWAP mean-reversion.",
      "Global risk halts remain active at session/run level.",
      "Optional custom exit formula lets you define VWAP-specific close logic.",
    ],
  },
  volume_profile: {
    entry: [
      "Uses profile structure and imbalance conditions for setup validation.",
      "Inputs include profile_lookback, num_bins, pb_threshold, symmetry_tolerance_pct.",
      "Confidence/evidence gate is required for execution.",
      "Runtime risk/cooldown/L2 gates remain active.",
    ],
    exit: [
      "ATR/RR/trailing controls define node-to-node risk envelope.",
      "Adverse-flow and time exits can close profile trades early.",
      "Session/run drawdown protections still apply.",
      "Optional custom exit formula can encode custom profile invalidation.",
    ],
  },
  gap_liquidity: {
    entry: [
      "Requires meaningful gap dislocation and liquidity-structure confirmation.",
      "Uses gap_threshold_pct, swing_lookback, liquidity_cluster_bars, gap_fill_tolerance_pct.",
      "Confidence/evidence threshold and runtime gates apply.",
      "Signal is queued only after all gate checks pass.",
    ],
    exit: [
      "ATR/RR/trailing controls manage open-gap volatility.",
      "Adverse-flow/fail-fast/time exits may close before full gap objective.",
      "Risk brakes (daily/run drawdown) can force immediate closure.",
      "Optional custom exit formula lets you encode bespoke gap-failure logic.",
    ],
  },
};

const DEFAULT_FORMULA_VARIABLES = [
  "price",
  "open",
  "high",
  "low",
  "volume",
  "vwap",
  "regime",
  "micro_regime",
  "confidence",
  "flow_score",
  "signed_aggression",
  "directional_consistency",
  "imbalance",
  "absorption_rate",
  "book_pressure",
  "sweep_intensity",
  "atr",
  "adx",
  "rsi",
  "position_side",
  "bars_held",
  "position_pnl_pct",
  "entry_price",
  "stop_loss",
  "take_profit",
];

const FORMULA_OPERATOR_TOKENS = [
  "and",
  "or",
  "not",
  "(",
  ")",
  ">",
  ">=",
  "<",
  "<=",
  "==",
  "!=",
];

interface StrategySettingsProps {
  apiUrl?: string;
  selectedTicker?: string;
  initialExpandAll?: boolean;
}

export default function StrategySettings({ apiUrl, selectedTicker, initialExpandAll = false }: StrategySettingsProps) {
  const [strategies, setStrategies] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [drafts, setDrafts] = useState<Record<string, Record<string, any>>>({});
  const [showCoreOnly, setShowCoreOnly] = useState(true);
  const [showProNotes, setShowProNotes] = useState(true);
  const [strategyCategory, setStrategyCategory] = useState("all");
  const [autoExpandedTicker, setAutoExpandedTicker] = useState("");
  const [tooltipStrategy, setTooltipStrategy] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 });
  const hoverTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resolvedUrl = apiUrl || defaultStrategyApiUrl;

  const formatFieldLabel = (field) => {
    const upperTokenMap = new Map([
      ["ma", "MA"],
      ["rr", "RR"],
      ["vwap", "VWAP"],
      ["l2", "L2"],
      ["pct", "%"],
    ]);
    return String(field || "")
      .split("_")
      .filter(Boolean)
      .map((token) => {
        const normalized = token.toLowerCase();
        if (upperTokenMap.has(normalized)) {
          return upperTokenMap.get(normalized);
        }
        return normalized.charAt(0).toUpperCase() + normalized.slice(1);
      })
      .join(" ");
  };

  const fetchStrategies = useCallback(async () => {
    if (!resolvedUrl) return null;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${resolvedUrl}/api/strategies`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setStrategies(data);
      return data;
    } catch (err) {
      setError(`Failed to load strategies: ${err.message}`);
      return null;
    } finally {
      setLoading(false);
    }
  }, [resolvedUrl]);

  const toggleExpanded = (name) => {
    setExpanded((prev) => ({ ...prev, [name]: !prev[name] }));
    setDrafts((prev) => ({ ...prev, [name]: prev[name] || strategies?.[name] || {} }));
  };

  const regimeOptions = useMemo(() => ["TRENDING", "CHOPPY", "MIXED"], []);
  const flowCoreSet = useMemo(
    () => new Set(["momentum_flow", "absorption_reversal", "exhaustion_fade", "scalp_l2_intrabar"]),
    []
  );
  const strategyCategoryMap = useMemo(
    () => ({
      momentum_flow: "flow",
      absorption_reversal: "flow",
      exhaustion_fade: "flow",
      iceberg_defense: "flow",
      scalp_l2_intrabar: "scalp",
    }),
    []
  );
  const resolveStrategyCategory = useCallback(
    (name) => strategyCategoryMap[name] || "other",
    [strategyCategoryMap]
  );
  const formatCategoryLabel = useCallback((categoryKey) => {
    if (categoryKey === "all") return "All";
    if (categoryKey === "flow") return "Flow";
    if (categoryKey === "scalp") return "Scalp";
    return "Other";
  }, []);

  const recommendedParams = useMemo(
    () => ({
      mean_reversion: {
        entry_deviation_pct: 0.3, min_confidence: 60.0, volume_confirmation: true,
        volume_lookback: 20, volume_exhaustion_ratio: 0.9, volume_stop_pct: 0.6,
        trailing_stop_pct: 0.3, allowed_regimes: ["CHOPPY", "MIXED"],
      },
      momentum: {
        consolidation_bars: 10, volume_threshold: 1.5, volume_lookback: 20,
        consolidation_range_pct: 0.6, breakout_pct: 0.15, volume_stop_pct: 0.8,
        rr_ratio: 2.5, trailing_stop_pct: 1.5, allowed_regimes: ["TRENDING"],
      },
      pullback: {
        pullback_threshold_pct: 0.5, ma_fast_period: 50, ma_slow_period: 100,
        volume_lookback: 20, volume_surge_ratio: 1.2, volume_stop_pct: 1.0,
        rr_ratio: 1.5, trailing_stop_pct: 1.0, allowed_regimes: ["TRENDING"],
      },
      rotation: {
        lookback_period: 10, rotation_threshold: 0.5, volume_lookback: 10,
        volume_increase_ratio: 1.05, volume_stop_pct: 0.9, trailing_stop_pct: 1.0,
        allowed_regimes: ["MIXED", "CHOPPY"],
      },
      vwap_magnet: {
        min_distance_pct: 0.4, max_distance_pct: 3.0, bars_since_vwap_threshold: 5,
        volume_confirm: true, volume_lookback: 20, volume_stop_pct: 0.7,
        trailing_stop_pct: 0.4, allowed_regimes: ["TRENDING", "CHOPPY", "MIXED"],
      },
      scalp_l2_intrabar: {
        enabled: true, allowed_regimes: ["TRENDING", "CHOPPY", "MIXED"],
        min_flow_score: 48.0, min_signed_aggression: 0.045,
        min_directional_consistency: 0.58, min_imbalance: 0.03,
        min_book_pressure: 0.02, min_participation_ratio: 0.05,
        min_flow_score_trend_3bar: -2.0, min_intrabar_move_pct: 0.035,
        min_intrabar_push_ratio: 0.12, min_intrabar_coverage_points: 4,
        min_intrabar_directional_consistency: 0.12, intrabar_eval_window_seconds: 5,
        min_intrabar_window_move_pct: 0.015, min_intrabar_window_push_ratio: 0.08,
        min_intrabar_window_directional_consistency: 0.08,
        max_intrabar_micro_volatility_bps: 18.0, max_intrabar_spread_bps: 8.0,
        spread_penalty_floor_bps: 4.0, spread_flow_score_penalty_per_bps: 0.45,
        min_round_trip_cost_bps: 6.5, spread_cost_multiplier: 1.1,
        min_reward_to_cost_ratio: 1.7, min_flow_signal_margin: 0.01,
        max_abs_price_extension_pct: 1.8, require_intrabar_confirmation: false,
        no_intrabar_flow_buffer: 10.0, min_confidence: 55.0,
        atr_stop_multiplier: 0.66, min_stop_loss_pct: 0.05,
        rr_ratio: 1.35, trailing_stop_pct: 0.28,
      },
    }),
    []
  );

  const onApplyStrategyState = useCallback((strategyName, current) => {
    setStrategies((prev) => (prev ? { ...prev, [strategyName]: current } : prev));
    setDrafts((prev) => ({ ...prev, [strategyName]: current }));
  }, []);

  useTickerStrategyPresets({ selectedTicker, resolvedUrl, onApplyStrategyState, fetchStrategies });

  useEffect(() => {
    setShowCoreOnly(selectedTicker === "MU");
  }, [selectedTicker]);

  useEffect(() => { fetchStrategies(); }, [fetchStrategies]);

  useEffect(() => {
    const handler = (event) => {
      const ticker = String(event?.detail?.ticker || "").toUpperCase().trim();
      const selected = String(selectedTicker || "").toUpperCase().trim();
      if (!ticker || !selected || ticker !== selected) return;
      fetchStrategies();
    };
    window.addEventListener("adaptive-profile-updated", handler);
    return () => window.removeEventListener("adaptive-profile-updated", handler);
  }, [fetchStrategies, selectedTicker]);

  const toggleStrategy = async (name, enabled) => {
    try {
      setStrategies((prev) =>
        prev ? { ...prev, [name]: { ...prev[name], enabled } } : prev
      );
      const resp = await fetch(`${resolvedUrl}/api/strategies/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, enabled }),
      });
      if (!resp.ok) throw new Error(`Toggle failed: ${resp.status}`);
    } catch (err) {
      setError(err.message);
      fetchStrategies();
    }
  };

  const saveDraft = async (name) => {
    const draft = drafts[name];
    if (!draft) return;
    try {
      const params = { ...draft };
      delete params.enabled;
      delete params.name;
      delete params.display_name;
      delete params.open_positions;
      delete params.total_signals;
      delete params.last_signal;
      delete params.global_trailing_stop_pct;
      delete params.effective_trailing_stop_pct;
      delete params.global_rr_ratio;
      delete params.effective_rr_ratio;
      delete params.global_atr_stop_multiplier;
      delete params.effective_atr_stop_multiplier;
      delete params.global_volume_stop_pct;
      delete params.effective_volume_stop_pct;
      delete params.global_min_stop_loss_pct;
      delete params.effective_min_stop_loss_pct;
      delete params.custom_formula_supported_variables;
      delete params.custom_formula_variable_docs;
      delete params.custom_formula_examples;
      const resp = await fetch(`${resolvedUrl}/api/strategies/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, params }),
      });
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
      const data = await resp.json();
      setStrategies((prev) => (prev ? { ...prev, [name]: data.current } : prev));
      setDrafts((prev) => ({ ...prev, [name]: data.current }));
    } catch (err) {
      setError(err.message);
      fetchStrategies();
    }
  };

  const updateDraftField = (name, field, value) => {
    setDrafts((prev) => ({
      ...prev,
      [name]: { ...(prev[name] || {}), [field]: value },
    }));
  };

  const appendFormulaToken = useCallback(
    (name: string, field: string, token: string) => {
      setDrafts((prev) => {
        const existingDraft = { ...(prev[name] || {}) };
        const currentBase =
          existingDraft[field] ?? strategies?.[name]?.[field] ?? "";
        const current = String(currentBase || "");
        const needsSpace = current.length > 0 && !/\s$/.test(current);
        const next = `${current}${needsSpace ? " " : ""}${token}`;
        return {
          ...prev,
          [name]: { ...existingDraft, [field]: next },
        };
      });
    },
    [strategies]
  );

  const getFieldGuide = useCallback((field: string): ProFieldGuide | null => {
    return PRO_FIELD_GUIDE[field] || null;
  }, []);

  const getStrategyPlaybook = useCallback((name: string): ProPlaybookItem[] => {
    return PRO_STRATEGY_PLAYBOOK[name] || DEFAULT_PRO_PLAYBOOK;
  }, []);

  const getStrategyRuleOverview = useCallback((name: string): StrategyRuleOverview => {
    return BUILTIN_RULE_OVERVIEW[name] || DEFAULT_BUILTIN_RULE_OVERVIEW;
  }, []);

  const renderField = (name, field, value) => {
    const fieldGuide = showProNotes ? getFieldGuide(field) : null;
    const guideTitle = fieldGuide
      ? `Pro range: ${fieldGuide.range}. ${fieldGuide.behavior}`
      : undefined;
    if (field === "custom_entry_formula" || field === "custom_exit_formula") {
      const isEntryFormula = field === "custom_entry_formula";
      const enabledField = isEntryFormula
        ? "custom_entry_formula_enabled"
        : "custom_exit_formula_enabled";
      const enabled = Boolean(
        drafts[name]?.[enabledField] ?? strategies?.[name]?.[enabledField] ?? false
      );
      const rawVars =
        drafts[name]?.custom_formula_supported_variables ??
        strategies?.[name]?.custom_formula_supported_variables;
      const formulaVars =
        Array.isArray(rawVars) && rawVars.length
          ? rawVars.map((item) => String(item || "").trim()).filter(Boolean)
          : DEFAULT_FORMULA_VARIABLES;
      const formulaExamples =
        drafts[name]?.custom_formula_examples ??
        strategies?.[name]?.custom_formula_examples ??
        {};
      const entryExample = String(
        formulaExamples?.entry ||
          "regime in ('TRENDING','MIXED') and flow_score >= 55 and signed_aggression > 0.05"
      );
      const exitExample = String(
        formulaExamples?.exit ||
          "position_side == 'long' and (position_pnl_pct < -0.35 or flow_score < 40)"
      );
      const currentFormula = String(drafts[name]?.[field] ?? value ?? "");
      return (
        <div className="sc-formula-field" key={field}>
          <label className="sc-field-label">
            {isEntryFormula ? "Custom Entry Formula" : "Custom Exit Formula"}
          </label>
          <textarea
            className="sc-formula-input"
            rows={3}
            value={currentFormula}
            disabled={!enabled}
            placeholder={
              enabled
                ? "Write boolean formula (and/or, >, <, ==, !=, in, min/max/abs...)"
                : "Enable formula switch first"
            }
            onChange={(e) => updateDraftField(name, field, e.target.value)}
          />
          <div className="sc-formula-tools">
            <div className="sc-formula-ops">
              {FORMULA_OPERATOR_TOKENS.map((token) => (
                <button
                  key={`${field}-${token}`}
                  className="sc-formula-op-btn"
                  type="button"
                  disabled={!enabled}
                  onClick={() => appendFormulaToken(name, field, token)}
                >
                  {token}
                </button>
              ))}
            </div>
            <select
              className="sc-formula-var-select"
              disabled={!enabled}
              value=""
              onChange={(e) => {
                if (!e.target.value) return;
                appendFormulaToken(name, field, e.target.value);
                e.target.value = "";
              }}
            >
              <option value="">Insert variable...</option>
              {formulaVars.map((variableName) => (
                <option key={`${field}-${variableName}`} value={variableName}>
                  {variableName}
                </option>
              ))}
            </select>
          </div>
          <span className="sc-field-meta">
            Example: {isEntryFormula ? entryExample : exitExample}
          </span>
        </div>
      );
    }
    if (field === "allowed_regimes" && Array.isArray(value)) {
      return (
        <div key={field} className="sc-regime-field">
          <span className="sc-field-label">Allowed Regimes</span>
          <div className="sc-regime-options">
            {regimeOptions.map((opt) => {
              const checked = (drafts[name]?.allowed_regimes || value || []).includes(opt);
              return (
                <label key={opt} className="sc-regime-chip">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      const current = new Set(drafts[name]?.allowed_regimes || value || []);
                      e.target.checked ? current.add(opt) : current.delete(opt);
                      updateDraftField(name, "allowed_regimes", Array.from(current));
                    }}
                  />
                  {opt}
                </label>
              );
            })}
          </div>
          {fieldGuide && (
            <span className="sc-field-meta" title={fieldGuide.behavior}>
              Pro: {fieldGuide.range}
            </span>
          )}
        </div>
      );
    }
    if (field === "trailing_stop_mode" || field === "exit_mode" || field === "risk_mode") {
      const isRiskMode = field === "risk_mode";
      const modeField = isRiskMode ? "risk_mode" : "exit_mode";
      const currentMode = String(
        drafts[name]?.[modeField] ?? drafts[name]?.trailing_stop_mode ?? value ?? "custom"
      )
        .trim()
        .toLowerCase() === "global"
        ? "global"
        : "custom";
      return (
        <div className="sc-field" key={field}>
          <label className="sc-field-label">{isRiskMode ? "Risk Source" : "Exit Source"}</label>
          <select
            value={currentMode}
            onChange={(e) =>
              setDrafts((prev) => ({
                ...prev,
                [name]: {
                  ...(prev[name] || {}),
                  [modeField]: e.target.value,
                  ...(!isRiskMode ? { trailing_stop_mode: e.target.value } : {}),
                },
              }))
            }
            className="sc-field-input"
            title={guideTitle}
          >
            <option value="custom">Custom (strategy)</option>
            <option value="global">Global (modules)</option>
          </select>
          {fieldGuide && (
            <span className="sc-field-meta" title={fieldGuide.behavior}>
              Pro: {fieldGuide.range}
            </span>
          )}
        </div>
      );
    }
    if (typeof value === "number") {
      return (
        <div className="sc-field" key={field}>
          <label className="sc-field-label">{formatFieldLabel(field)}</label>
          <input
            type="number"
            step="0.01"
            value={drafts[name]?.[field] ?? value}
            onChange={(e) => updateDraftField(name, field, Number(e.target.value))}
            className="sc-field-input"
            title={guideTitle}
          />
          {fieldGuide && (
            <span className="sc-field-meta" title={fieldGuide.behavior}>
              Pro: {fieldGuide.range}
            </span>
          )}
        </div>
      );
    }
    if (typeof value === "boolean") {
      return (
        <div className="sc-field sc-field-bool" key={field}>
          <label className="sc-field-label">{formatFieldLabel(field)}</label>
          <input
            type="checkbox"
            checked={drafts[name]?.[field] ?? value}
            onChange={(e) => updateDraftField(name, field, e.target.checked)}
            className="sc-field-check"
            title={guideTitle}
          />
          {fieldGuide && (
            <span className="sc-field-meta" title={fieldGuide.behavior}>
              Pro: {fieldGuide.range}
            </span>
          )}
        </div>
      );
    }
    return null;
  };

  const handleReset = async (name) => {
    const fresh = await fetchStrategies();
    const latest = fresh?.[name] || strategies?.[name] || {};
    setDrafts((prev) => ({ ...prev, [name]: latest }));
  };

  const applyRecommended = async (name) => {
    const recommended = recommendedParams[name];
    if (!recommended) return;
    try {
      const resp = await fetch(`${resolvedUrl}/api/strategies/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, params: recommended }),
      });
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
      const data = await resp.json();
      setStrategies((prev) => (prev ? { ...prev, [name]: data.current } : prev));
      setDrafts((prev) => ({ ...prev, [name]: data.current }));
    } catch (err) {
      setError(err.message);
      fetchStrategies();
    }
  };

  const getStrategyWarning = (name, cfg) => {
    if (name !== "mean_reversion") return null;
    const deviation = cfg.entry_deviation_pct;
    if (typeof deviation === "number" && deviation > 2) {
      return "Deviation is very high; signals will likely never trigger.";
    }
    return null;
  };

  const strategyFieldExclusions = useMemo(
    () =>
      new Set([
        "enabled",
        "display_name",
        "name",
        "open_positions",
        "total_signals",
        "last_signal",
        "trailing_stop_mode",
        "global_trailing_stop_pct",
        "effective_trailing_stop_pct",
        "global_rr_ratio",
        "effective_rr_ratio",
        "global_atr_stop_multiplier",
        "effective_atr_stop_multiplier",
        "global_volume_stop_pct",
        "effective_volume_stop_pct",
        "global_min_stop_loss_pct",
        "effective_min_stop_loss_pct",
        "custom_formula_supported_variables",
        "custom_formula_variable_docs",
        "custom_formula_examples",
      ]),
    []
  );

  const classifyFieldGroup = (field) => {
    if (field === "allowed_regimes") return "Regime";
    if (/custom_.*formula/.test(field)) return "Custom Rules";
    if (/intrabar|spread_penalty|spread_cost|min_round_trip_cost|min_reward_to_cost|no_intrabar|require_intrabar/i.test(field))
      return "Scalp Intrabar";
    if (/stop|trailing|rr_ratio|risk|take_profit|time_exit/i.test(field))
      return "Risk & Exit";
    if (/entry|breakout|pullback|deviation|threshold|lookback|consolidation|rotation|distance|bars_since|ma_|volume|confidence|confirm/i.test(field))
      return "Signal Setup";
    return "Other";
  };

  const groupFieldsForEdit = (name, cfg) => {
    const grouped = {
      Regime: [],
      "Scalp Intrabar": [],
      "Signal Setup": [],
      "Risk & Exit": [],
      "Custom Rules": [],
      Other: [],
    };
    Object.entries(cfg || {}).forEach(([field, value]) => {
      if (strategyFieldExclusions.has(field)) return;
      if (
        !(
          typeof value === "number" ||
          typeof value === "boolean" ||
          (field === "allowed_regimes" && Array.isArray(value)) ||
          (
            [
              "trailing_stop_mode",
              "exit_mode",
              "risk_mode",
              "custom_entry_formula",
              "custom_exit_formula",
            ].includes(field) &&
            typeof value === "string"
          )
        )
      )
        return;
      const group = classifyFieldGroup(field);
      grouped[group].push([field, value]);
    });
    if (name === "scalp_l2_intrabar") {
      const scalpOrder = [
        "min_flow_score", "min_flow_score_trend_3bar", "min_signed_aggression",
        "min_directional_consistency", "min_imbalance", "min_book_pressure",
        "min_participation_ratio", "min_intrabar_move_pct", "min_intrabar_push_ratio",
        "min_intrabar_coverage_points", "min_intrabar_directional_consistency",
        "intrabar_eval_window_seconds", "min_intrabar_window_move_pct",
        "min_intrabar_window_push_ratio", "min_intrabar_window_directional_consistency",
        "max_intrabar_micro_volatility_bps", "max_intrabar_spread_bps",
        "spread_penalty_floor_bps", "spread_flow_score_penalty_per_bps",
        "min_round_trip_cost_bps", "spread_cost_multiplier", "min_reward_to_cost_ratio",
        "require_intrabar_confirmation", "no_intrabar_flow_buffer",
      ];
      const rank = new Map(scalpOrder.map((f, i) => [f, i]));
      Object.keys(grouped).forEach((gk) => {
        grouped[gk].sort((a, b) => {
          const rA = rank.has(a[0]) ? rank.get(a[0]) : Number.MAX_SAFE_INTEGER;
          const rB = rank.has(b[0]) ? rank.get(b[0]) : Number.MAX_SAFE_INTEGER;
          return rA !== rB ? rA - rB : String(a[0]).localeCompare(String(b[0]));
        });
      });
    }
    return Object.entries(grouped).filter(([, entries]) => entries.length > 0);
  };

  const strategyEntries = useMemo(() => {
    if (!strategies) return [];
    const sorted = Object.entries(strategies).sort((a, b) => {
      const aE = a[1]?.enabled ? 1 : 0;
      const bE = b[1]?.enabled ? 1 : 0;
      if (aE !== bE) return bE - aE;
      return String(a[1]?.display_name || a[0]).localeCompare(String(b[1]?.display_name || b[0]));
    });
    const withCoreFilter =
      selectedTicker === "MU" && showCoreOnly
        ? sorted.filter(([name]) => flowCoreSet.has(name))
        : sorted;
    if (strategyCategory === "all") return withCoreFilter;
    return withCoreFilter.filter(([name]) => resolveStrategyCategory(name) === strategyCategory);
  }, [strategies, selectedTicker, showCoreOnly, flowCoreSet, strategyCategory, resolveStrategyCategory]);

  const warningByStrategy = useMemo(() => {
    const next: Record<string, string | null> = {};
    strategyEntries.forEach(([name, cfg]) => { next[name] = getStrategyWarning(name, cfg); });
    return next;
  }, [strategyEntries]);

  const editableGroupsByStrategy = useMemo(() => {
    const next: Record<string, Array<[string, Array<[string, any]>]>> = {};
    strategyEntries.forEach(([name, cfg]) => { next[name] = groupFieldsForEdit(name, cfg); });
    return next;
  }, [strategyEntries]);

  useEffect(() => {
    if (!initialExpandAll || !strategies) return;
    const tickerKey = String(selectedTicker || "").toUpperCase().trim() || "ALL";
    if (autoExpandedTicker === tickerKey) return;
    const rows = Object.entries(strategies || {});
    if (!rows.length) return;
    const nextExp: Record<string, boolean> = {};
    const nextDr: Record<string, Record<string, any>> = {};
    rows.forEach(([name, cfg]) => {
      nextExp[name] = true;
      nextDr[name] = cfg && typeof cfg === "object" ? cfg : {};
    });
    setExpanded((prev) => ({ ...nextExp, ...prev }));
    setDrafts((prev) => ({ ...nextDr, ...prev }));
    setAutoExpandedTicker(tickerKey);
  }, [autoExpandedTicker, initialExpandAll, selectedTicker, strategies]);

  const expandAllVisible = useCallback(() => {
    if (!strategyEntries.length) return;
    const nextExp: Record<string, boolean> = {};
    const nextDr: Record<string, Record<string, any>> = {};
    strategyEntries.forEach(([name, cfg]) => {
      nextExp[name] = true;
      nextDr[name] = cfg && typeof cfg === "object" ? cfg : {};
    });
    setExpanded((prev) => ({ ...prev, ...nextExp }));
    setDrafts((prev) => ({ ...nextDr, ...prev }));
  }, [strategyEntries]);

  const collapseAllVisible = useCallback(() => {
    if (!strategyEntries.length) return;
    const visibleKeys = new Set(strategyEntries.map(([name]) => name));
    setExpanded((prev) => {
      const next = { ...prev };
      visibleKeys.forEach((name) => { next[name] = false; });
      return next;
    });
  }, [strategyEntries]);

  const enabledCount = useMemo(
    () => strategyEntries.filter(([, cfg]) => !!cfg?.enabled).length,
    [strategyEntries]
  );

  const handleNameMouseEnter = useCallback((e: React.MouseEvent, name: string) => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setTooltipPos({ top: rect.bottom + 6, left: rect.left });
    hoverTimeoutRef.current = setTimeout(() => setTooltipStrategy(name), 250);
  }, []);

  const handleNameMouseLeave = useCallback(() => {
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    setTooltipStrategy(null);
  }, []);

  return (
    <div className="sc-panel">
      {/* Toolbar */}
      <div className="sc-toolbar">
        <div className="sc-toolbar-left">
          <span className="sc-counter">{enabledCount}/{strategyEntries.length}</span>
          <select
            value={strategyCategory}
            onChange={(e) => setStrategyCategory(e.target.value)}
            className="sc-select"
            title="Filter strategy category"
          >
            <option value="all">All categories</option>
            <option value="flow">Flow</option>
            <option value="scalp">Scalp</option>
            <option value="other">Other</option>
          </select>
          {selectedTicker === "MU" && (
            <button
              className={`sc-chip-btn ${showCoreOnly ? "active" : ""}`}
              onClick={() => setShowCoreOnly((prev) => !prev)}
            >
              Core Only
            </button>
          )}
          <button
            className={`sc-chip-btn sc-chip-btn-pro ${showProNotes ? "active" : ""}`}
            onClick={() => setShowProNotes((prev) => !prev)}
            title="Show professional setting guidance"
          >
            Pro Notes
          </button>
        </div>
        <div className="sc-toolbar-right">
          <button className="sc-icon-btn" onClick={fetchStrategies} disabled={loading} title="Refresh">
            {loading ? "…" : "↻"}
          </button>
          <button className="sc-icon-btn" onClick={expandAllVisible} disabled={!strategyEntries.length} title="Expand all">
            ⬇
          </button>
          <button className="sc-icon-btn" onClick={collapseAllVisible} disabled={!strategyEntries.length} title="Collapse all">
            ⬆
          </button>
        </div>
      </div>

      {/* Status */}
      {error && <div className="sc-msg sc-msg-error">{error}</div>}
      {!strategies && !error && !loading && <div className="sc-msg">No data</div>}
      {selectedTicker === "MU" && showCoreOnly && <div className="sc-msg">Core MU flow strategies only.</div>}
      {strategies && strategyEntries.length === 0 && <div className="sc-msg">No strategies match the filter.</div>}

      {/* Strategy list */}
      <div className="sc-list">
        {strategies &&
          strategyEntries.map(([name, cfg]) => {
            const displayName = cfg.display_name || cfg.name || name;
            const regimes = (cfg.allowed_regimes || cfg.regimes || []).join(", ") || "all";
            const categoryKey = resolveStrategyCategory(name);
            const warning = warningByStrategy[name];
            const editableGroups = editableGroupsByStrategy[name] || [];
            const isExpanded = !!expanded[name];
            return (
              <div
                key={name}
                className={`sc-item ${cfg.enabled ? "on" : "off"} ${isExpanded ? "open" : ""}`}
              >
                {/* Card header row */}
                <div className="sc-item-head" onClick={() => toggleExpanded(name)}>
                  <div className="sc-item-info">
                    <span
                      className="sc-item-name"
                      onMouseEnter={(e) => { e.stopPropagation(); handleNameMouseEnter(e, name); }}
                      onMouseLeave={handleNameMouseLeave}
                    >
                      {displayName}
                    </span>
                    <span className={`sc-cat ${categoryKey}`}>
                      {formatCategoryLabel(categoryKey)}
                    </span>
                    <span className="sc-regimes">{regimes}</span>
                  </div>
                  <div className="sc-item-controls" onClick={(e) => e.stopPropagation()}>
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={cfg.enabled}
                        onChange={(e) => toggleStrategy(name, e.target.checked)}
                      />
                      <span className="slider" />
                    </label>
                  </div>
                  <span className={`sc-expand-arrow ${isExpanded ? "open" : ""}`}>›</span>
                </div>

                {/* Expanded edit panel — flat sections */}
                {isExpanded && (
                  <div className="sc-item-body">
                    {warning && <div className="sc-warning">⚠ {warning}</div>}
                    <div className="sc-msg">
                      Exit source: {String(cfg?.exit_mode || cfg?.trailing_stop_mode || "custom")}
                      {" | "}
                      Risk source: {String(cfg?.risk_mode || "custom")}
                      {typeof cfg?.effective_trailing_stop_pct === "number"
                        ? ` | trailing ${Number(cfg.effective_trailing_stop_pct).toFixed(2)}%`
                        : ""}
                      {typeof cfg?.effective_rr_ratio === "number"
                        ? ` | rr ${Number(cfg.effective_rr_ratio).toFixed(2)}`
                        : ""}
                      {typeof cfg?.effective_atr_stop_multiplier === "number"
                        ? ` | atr x${Number(cfg.effective_atr_stop_multiplier).toFixed(2)}`
                        : ""}
                    </div>
                    {(() => {
                      const ruleOverview = getStrategyRuleOverview(name);
                      return (
                        <div className="sc-rule-card">
                          <div className="sc-rule-title">Built-in Entry Checks</div>
                          <ul className="sc-rule-list">
                            {ruleOverview.entry.map((item, idx) => (
                              <li key={`${name}-entry-${idx}`} className="sc-rule-item">
                                {item}
                              </li>
                            ))}
                          </ul>
                          <div className="sc-rule-title">Built-in Exit Checks</div>
                          <ul className="sc-rule-list">
                            {ruleOverview.exit.map((item, idx) => (
                              <li key={`${name}-exit-${idx}`} className="sc-rule-item">
                                {item}
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })()}
                    {showProNotes && (
                      <div className="sc-pro-card">
                        <div className="sc-pro-title">Professional Playbook</div>
                        <div className="sc-pro-grid">
                          {getStrategyPlaybook(name).map((item) => (
                            <div key={`${name}-${item.label}`} className="sc-pro-item">
                              <span className="sc-pro-key">{item.label}:</span> {item.guidance}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {editableGroups.map(([groupLabel, groupFields]) => (
                      <div key={groupLabel} className="sc-section">
                        <div className="sc-section-label">{groupLabel}</div>
                        <div className="sc-grid">
                          {groupFields.map(([field, value]) => renderField(name, field, value))}
                        </div>
                      </div>
                    ))}
                    <div className="sc-actions">
                      <button className="sc-btn" onClick={() => handleReset(name)}>Reset</button>
                      {recommendedParams[name] && (
                        <button className="sc-btn" onClick={() => applyRecommended(name)}>Recommended</button>
                      )}
                      <button className="sc-btn sc-btn-primary" onClick={() => saveDraft(name)}>Save</button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
      </div>

      {/* Tooltip */}
      {tooltipStrategy && STRATEGY_DESCRIPTIONS[tooltipStrategy] && (
        <div className="strategy-tooltip" style={{ top: tooltipPos.top, left: tooltipPos.left }}>
          {STRATEGY_DESCRIPTIONS[tooltipStrategy]}
        </div>
      )}
    </div>
  );
}
