import { useEffect, useMemo, useCallback } from "react";
import { useTickerStrategyPresets } from "./strategy-settings/useTickerStrategyPresets";
import { AosHistoryTimeline } from "./strategy-settings/AosHistoryTimeline";
import { useStrategySettingsState, UseStrategySettingsStateProps } from "./strategy-settings/useStrategySettingsState";
import { StrategyFieldRenderer } from "./strategy-settings/StrategyFieldRenderer";
import { ProFieldGuide, ProPlaybookItem, StrategyRuleOverview } from "./strategy-settings/types";

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

const PRO_FIELD_GUIDE: Record<string, ProFieldGuide> = {
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

const DEFAULT_PRO_PLAYBOOK: ProPlaybookItem[] = [
  { label: "Execution Layer", guidance: "Use strategy settings for structural tuning. Use global execution modules for portfolio-wide protections." },
  { label: "Regime alignment", guidance: "Ensure at least half your enabled cast is aligned with expected session conditions." }
];

const PRO_STRATEGY_PLAYBOOK: Record<string, ProPlaybookItem[]> = {
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

const DEFAULT_FORMULA_VARIABLES = [
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

interface StrategySettingsProps extends UseStrategySettingsStateProps {
  initialExpandAll?: boolean;
}

export default function StrategySettings({
  apiUrl,
  selectedTicker,
  initialExpandAll = false,
}: StrategySettingsProps) {

  const state = useStrategySettingsState({ apiUrl, selectedTicker });
  
  const formatFieldLabel = useCallback((field: string) => {
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
  }, []);

  const flowCoreSet = useMemo(
    () =>
      new Set([
        "momentum_flow",
        "absorption_reversal",
        "exhaustion_fade",
        "scalp_l2_intrabar",
      ]),
    [],
  );

  const strategyCategoryMap = useMemo(
    () => ({
      momentum_flow: "flow",
      absorption_reversal: "flow",
      exhaustion_fade: "flow",
      iceberg_defense: "flow",
      scalp_l2_intrabar: "scalp",
    }),
    [],
  );

  const resolveStrategyCategory = useCallback(
    (name: string) => strategyCategoryMap[name] || "other",
    [strategyCategoryMap],
  );

  const formatCategoryLabel = useCallback((categoryKey: string) => {
    if (categoryKey === "all") return "All";
    if (categoryKey === "flow") return "Flow";
    if (categoryKey === "scalp") return "Scalp";
    return "Other";
  }, []);

  const recommendedParams = useMemo(
    () => ({
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
    }),
    [],
  );

  const applyRecommended = useCallback(async (name: string) => {
    const recommended = recommendedParams[name as keyof typeof recommendedParams];
    if (!recommended) return;
    try {
      const resp = await fetch(`${state.resolvedUrl}/api/strategies/update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_name: name, params: recommended }),
      });
      if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
      const data = await resp.json();
      state.setStrategies((prev) =>
        prev ? { ...prev, [name]: data.current } : prev,
      );
      state.setDrafts((prev) => ({ ...prev, [name]: data.current }));
    } catch (err: any) {
      state.setError(err.message);
      state.fetchStrategies();
    }
  }, [recommendedParams, state.resolvedUrl, state.setStrategies, state.setDrafts, state.setError, state.fetchStrategies]);

  const onApplyStrategyState = useCallback((strategyName: string, current: any) => {
    state.setStrategies((prev) =>
      prev ? { ...prev, [strategyName]: current } : prev,
    );
    state.setDrafts((prev) => ({ ...prev, [strategyName]: current }));
  }, [state.setStrategies, state.setDrafts]);

  // Hook usages
  useTickerStrategyPresets({
    selectedTicker,
    resolvedUrl: state.resolvedUrl,
    onApplyStrategyState,
    fetchStrategies: state.fetchStrategies,
  });

  useEffect(() => {
    state.setShowCoreOnly(selectedTicker === "MU");
  }, [selectedTicker, state.setShowCoreOnly]);

  useEffect(() => {
    state.fetchStrategies();
  }, [state.fetchStrategies]);

  useEffect(() => {
    const handler = (event: any) => {
      const ticker = String(event?.detail?.ticker || "")
        .toUpperCase()
        .trim();
      const selected = String(selectedTicker || "")
        .toUpperCase()
        .trim();
      if (!ticker || !selected || ticker !== selected) return;
      state.fetchStrategies();
    };
    window.addEventListener("adaptive-profile-updated", handler);
    return () =>
      window.removeEventListener("adaptive-profile-updated", handler);
  }, [state.fetchStrategies, selectedTicker]);

  useEffect(() => {
    if (!initialExpandAll || !state.strategies) return;
    const tickerKey =
      String(selectedTicker || "")
        .toUpperCase()
        .trim() || "ALL";
    if (state.autoExpandedTicker === tickerKey) return;
    const rows = Object.entries(state.strategies || {});
    if (!rows.length) return;
    const nextExp: Record<string, boolean> = {};
    const nextDr: Record<string, Record<string, any>> = {};
    rows.forEach(([name, cfg]) => {
      nextExp[name] = true;
      nextDr[name] = cfg && typeof cfg === "object" ? cfg : {};
    });
    state.setExpanded((prev) => ({ ...nextExp, ...prev }));
    state.setDrafts((prev) => ({ ...nextDr, ...prev }));
    state.setAutoExpandedTicker(tickerKey);
  }, [state.autoExpandedTicker, initialExpandAll, selectedTicker, state.strategies, state.setExpanded, state.setDrafts, state.setAutoExpandedTicker]);

  const expandAllVisible = useCallback(() => {
    if (!strategyEntries.length) return;
    const nextExp: Record<string, boolean> = {};
    const nextDr: Record<string, Record<string, any>> = {};
    strategyEntries.forEach(([name, cfg]) => {
      nextExp[name] = true;
      nextDr[name] = cfg && typeof cfg === "object" ? cfg : {};
    });
    state.setExpanded((prev) => ({ ...prev, ...nextExp }));
    state.setDrafts((prev) => ({ ...nextDr, ...prev }));
  }, [state.strategies, state.setExpanded, state.setDrafts]);

  const collapseAllVisible = useCallback(() => {
    if (!strategyEntries.length) return;
    const visibleKeys = new Set(strategyEntries.map(([name]) => name));
    state.setExpanded((prev) => {
      const next = { ...prev };
      visibleKeys.forEach((name) => {
        next[name] = false;
      });
      return next;
    });
  }, [state.strategies, state.setExpanded]);

  const getFieldGuide = useCallback((field: string): ProFieldGuide | null => {
    return PRO_FIELD_GUIDE[field] || null;
  }, []);

  const getStrategyPlaybook = useCallback((name: string): ProPlaybookItem[] => {
    return PRO_STRATEGY_PLAYBOOK[name] || DEFAULT_PRO_PLAYBOOK;
  }, []);

  const getStrategyRuleOverview = useCallback(
    (name: string): StrategyRuleOverview => {
      return BUILTIN_RULE_OVERVIEW[name] || DEFAULT_BUILTIN_RULE_OVERVIEW;
    },
    [],
  );

  const getStrategyWarning = (name: string, cfg: any) => {
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
    [],
  );

  const classifyFieldGroup = (field: string) => {
    if (field === "allowed_regimes") return "Regime";
    if (/custom_.*formula/.test(field)) return "Custom Rules";
    if (
      /intrabar|spread_penalty|spread_cost|min_round_trip_cost|min_reward_to_cost|no_intrabar|require_intrabar/i.test(
        field,
      )
    )
      return "Scalp Intrabar";
    if (/stop|trailing|rr_ratio|risk|take_profit|time_exit/i.test(field))
      return "Risk & Exit";
    if (
      /entry|breakout|pullback|deviation|threshold|lookback|consolidation|rotation|distance|bars_since|ma_|volume|confidence|confirm/i.test(
        field,
      )
    )
      return "Signal Setup";
    return "Other";
  };

  const groupFieldsForEdit = useCallback((name: string, cfg: any) => {
    const grouped: Record<string, Array<[string, any]>> = {
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
          ([
            "trailing_stop_mode",
            "exit_mode",
            "risk_mode",
            "custom_entry_formula",
            "custom_exit_formula",
          ].includes(field) &&
            typeof value === "string")
        )
      )
        return;
      const group = classifyFieldGroup(field);
      grouped[group].push([field, value]);
    });
    if (name === "scalp_l2_intrabar") {
      const scalpOrder = [
        "min_flow_score",
        "min_flow_score_trend_3bar",
        "min_signed_aggression",
        "min_directional_consistency",
        "min_imbalance",
        "min_book_pressure",
        "min_participation_ratio",
        "min_intrabar_move_pct",
        "min_intrabar_push_ratio",
        "min_intrabar_coverage_points",
        "min_intrabar_directional_consistency",
        "intrabar_eval_window_seconds",
        "min_intrabar_window_move_pct",
        "min_intrabar_window_push_ratio",
        "min_intrabar_window_directional_consistency",
        "max_intrabar_micro_volatility_bps",
        "max_intrabar_spread_bps",
        "spread_penalty_floor_bps",
        "spread_flow_score_penalty_per_bps",
        "min_round_trip_cost_bps",
        "spread_cost_multiplier",
        "min_reward_to_cost_ratio",
        "require_intrabar_confirmation",
        "no_intrabar_flow_buffer",
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
  }, [strategyFieldExclusions]);

  const strategyEntries = useMemo(() => {
    if (!state.strategies) return [];
    const sorted = Object.entries(state.strategies).sort((a, b) => {
      const aE = a[1]?.enabled ? 1 : 0;
      const bE = b[1]?.enabled ? 1 : 0;
      if (aE !== bE) return bE - aE;
      return String(a[1]?.display_name || a[0]).localeCompare(
        String(b[1]?.display_name || b[0]),
      );
    });
    const withCoreFilter =
      selectedTicker === "MU" && state.showCoreOnly
        ? sorted.filter(([name]) => flowCoreSet.has(name))
        : sorted;
    if (state.strategyCategory === "all") return withCoreFilter;
    return withCoreFilter.filter(
      ([name]) => resolveStrategyCategory(name) === state.strategyCategory,
    );
  }, [
    state.strategies,
    selectedTicker,
    state.showCoreOnly,
    flowCoreSet,
    state.strategyCategory,
    resolveStrategyCategory,
  ]);

  // We have strategyEntries as a dependency of expandAllVisible and collapseAllVisible because of the memo.
  // We can safely hoist strategyEntries calculation above their definitions, 
  // or define them directly since they're just used in the TSX return.
  
  const enabledCount = useMemo(
    () => strategyEntries.filter(([, cfg]) => !!cfg?.enabled).length,
    [strategyEntries],
  );

  const warningByStrategy = useMemo(() => {
    const next: Record<string, string | null> = {};
    strategyEntries.forEach(([name, cfg]) => {
      next[name] = getStrategyWarning(name, cfg);
    });
    return next;
  }, [strategyEntries]);

  const editableGroupsByStrategy = useMemo(() => {
    const next: Record<string, Array<[string, Array<[string, any]>]>> = {};
    strategyEntries.forEach(([name, cfg]) => {
      next[name] = groupFieldsForEdit(name, cfg);
    });
    return next;
  }, [strategyEntries, groupFieldsForEdit]);

  const handleNameMouseEnter = useCallback(
    (e: React.MouseEvent, name: string) => {
      if (state.hoverTimeoutRef.current) clearTimeout(state.hoverTimeoutRef.current);
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      state.setTooltipPos({ top: rect.bottom + 6, left: rect.left });
      state.hoverTimeoutRef.current = setTimeout(() => state.setTooltipStrategy(name), 250);
    },
    [state.hoverTimeoutRef, state.setTooltipPos, state.setTooltipStrategy],
  );

  const handleNameMouseLeave = useCallback(() => {
    if (state.hoverTimeoutRef.current) clearTimeout(state.hoverTimeoutRef.current);
    state.setTooltipStrategy(null);
  }, [state.hoverTimeoutRef, state.setTooltipStrategy]);

  return (
    <div className="sc-panel">
      {/* Toolbar */}
      <div className="sc-toolbar">
        <div className="sc-toolbar-left">
          <span className="sc-counter">
            {enabledCount}/{strategyEntries.length}
          </span>
          <select
            value={state.strategyCategory}
            onChange={(e) => state.setStrategyCategory(e.target.value)}
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
              className={`sc-chip-btn ${state.showCoreOnly ? "active" : ""}`}
              onClick={() => state.setShowCoreOnly((prev) => !prev)}
            >
              Core Only
            </button>
          )}
          <button
            className={`sc-chip-btn sc-chip-btn-pro ${state.showProNotes ? "active" : ""}`}
            onClick={() => state.setShowProNotes((prev) => !prev)}
            title="Show professional setting guidance"
          >
            Pro Notes
          </button>
        </div>
        <div className="sc-toolbar-right">
          <button
            className="sc-icon-btn"
            onClick={state.fetchStrategies}
            disabled={state.loading}
            title="Refresh"
          >
            {state.loading ? "…" : "↻"}
          </button>
          <button
            className="sc-icon-btn"
            onClick={expandAllVisible}
            disabled={!strategyEntries.length}
            title="Expand all"
          >
            ⬇
          </button>
          <button
            className="sc-icon-btn"
            onClick={collapseAllVisible}
            disabled={!strategyEntries.length}
            title="Collapse all"
          >
            ⬆
          </button>
        </div>
      </div>

      {/* Status */}
      {state.error && <div className="sc-msg sc-msg-error">{state.error}</div>}
      {!state.strategies && !state.error && !state.loading && (
        <div className="sc-msg">No data</div>
      )}
      {selectedTicker === "MU" && state.showCoreOnly && (
        <div className="sc-msg">Core MU flow strategies only.</div>
      )}
      {state.strategies && strategyEntries.length === 0 && (
        <div className="sc-msg">No strategies match the filter.</div>
      )}

      {/* Strategy list */}
      <div className="sc-list">
        {state.strategies &&
          strategyEntries.map(([name, cfg]) => {
            const displayName = cfg.display_name || cfg.name || name;
            const regimes =
              (cfg.allowed_regimes || cfg.regimes || []).join(", ") || "all";
            const categoryKey = resolveStrategyCategory(name);
            const warning = warningByStrategy[name];
            const editableGroups = editableGroupsByStrategy[name] || [];
            const isExpanded = !!state.expanded[name];
            return (
              <div
                key={name}
                className={`sc-item ${cfg.enabled ? "on" : "off"} ${isExpanded ? "open" : ""}`}
              >
                {/* Card header row */}
                <div
                  className="sc-item-head"
                  onClick={() => state.toggleExpanded(name)}
                >
                  <div className="sc-item-info">
                    <span
                      className="sc-item-name"
                      onMouseEnter={(e) => {
                        e.stopPropagation();
                        handleNameMouseEnter(e, name);
                      }}
                      onMouseLeave={handleNameMouseLeave}
                    >
                      {displayName}
                    </span>
                    <span className={`sc-cat ${categoryKey}`}>
                      {formatCategoryLabel(categoryKey)}
                    </span>
                    <span className="sc-regimes">{regimes}</span>
                  </div>
                  <div
                    className="sc-item-controls"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <label className="switch">
                      <input
                        type="checkbox"
                        checked={cfg.enabled}
                        onChange={(e) => state.toggleStrategy(name, e.target.checked)}
                      />
                      <span className="slider" />
                    </label>
                  </div>
                  <span
                    className={`sc-expand-arrow ${isExpanded ? "open" : ""}`}
                  >
                    ›
                  </span>
                </div>

                {/* Expanded edit panel — flat sections */}
                {isExpanded && (
                  <div className="sc-item-body">
                    {warning && <div className="sc-warning">⚠ {warning}</div>}
                    <div className="sc-msg">
                      Exit source:{" "}
                      {String(
                        cfg?.exit_mode || cfg?.trailing_stop_mode || "custom",
                      )}
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
                          <div className="sc-rule-title">
                            Built-in Entry Checks
                          </div>
                          <ul className="sc-rule-list">
                            {ruleOverview.entry.map((item, idx) => (
                              <li
                                key={`${name}-entry-${idx}`}
                                className="sc-rule-item"
                              >
                                {item}
                              </li>
                            ))}
                          </ul>
                          <div className="sc-rule-title">
                            Built-in Exit Checks
                          </div>
                          <ul className="sc-rule-list">
                            {ruleOverview.exit.map((item, idx) => (
                              <li
                                key={`${name}-exit-${idx}`}
                                className="sc-rule-item"
                              >
                                {item}
                              </li>
                            ))}
                          </ul>
                        </div>
                      );
                    })()}
                    {state.showProNotes && (
                      <div className="sc-pro-card">
                        <div className="sc-pro-title">
                          Professional Playbook
                        </div>
                        <div className="sc-pro-grid">
                          {getStrategyPlaybook(name).map((item) => (
                            <div
                              key={`${name}-${item.label}`}
                              className="sc-pro-item"
                            >
                              <span className="sc-pro-key">{item.label}:</span>{" "}
                              {item.guidance}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {editableGroups.map(([groupLabel, groupFields]) => (
                      <div key={groupLabel} className="sc-section">
                        <div className="sc-section-label">{groupLabel}</div>
                        <div className="sc-grid">
                          {groupFields.map(([field, value]) => (
                            <StrategyFieldRenderer
                              key={field}
                              name={name}
                              field={field}
                              value={value}
                              drafts={state.drafts}
                              strategies={state.strategies}
                              updateDraftField={state.updateDraftField}
                              appendFormulaToken={state.appendFormulaToken}
                              setDrafts={state.setDrafts}
                              showProNotes={state.showProNotes}
                              getFieldGuide={getFieldGuide}
                              formatFieldLabel={formatFieldLabel}
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                    <div className="sc-actions">
                      <button
                        className="sc-btn"
                        onClick={() => state.handleReset(name)}
                      >
                        Reset
                      </button>
                      {recommendedParams[name as keyof typeof recommendedParams] && (
                        <button
                          className="sc-btn"
                          onClick={() => applyRecommended(name)}
                        >
                          Recommended
                        </button>
                      )}
                      <button
                        className="sc-btn sc-btn-primary"
                        onClick={() => state.saveDraft(name)}
                      >
                        Save
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
      </div>
      
      {/* AOS Parameters Evolution History Timeline */}
      {selectedTicker && (
        <AosHistoryTimeline ticker={selectedTicker} />
      )}

      {/* Tooltip */}
      {state.tooltipStrategy && STRATEGY_DESCRIPTIONS[state.tooltipStrategy] && (
        <div
          className="strategy-tooltip"
          style={{ top: state.tooltipPos.top, left: state.tooltipPos.left }}
        >
          {STRATEGY_DESCRIPTIONS[state.tooltipStrategy]}
        </div>
      )}
    </div>
  );
}
