export type AdaptiveStudioObjectRecord = Record<string, unknown>;

export type AdaptiveStudioUnifiedViewTab = "strategy" | "execution";
export type AdaptiveStudioActionLoadingToken = string | null;
export type AdaptiveStudioStrategySelectionMode = "all_enabled" | "adaptive_top_n";
export type AdaptiveStudioPriorityScope = "regime_preferences" | "micro_regime_preferences";
export type AdaptiveStudioPriorityMap = Record<string, string[]>;

export type AdaptiveStudioFormState = {
  strategy_selection_mode: AdaptiveStudioStrategySelectionMode;
  max_active_strategies: number;
  flow_bias_enabled: boolean;
  use_ohlcv_fallbacks: boolean;
  min_active_bars_before_switch: number;
  switch_cooldown_bars: number;
  flow_bias_strategies: string[];
  regime_preferences: AdaptiveStudioPriorityMap;
  micro_regime_preferences: AdaptiveStudioPriorityMap;
};

export type AdaptiveStudioFormUpdater =
  | AdaptiveStudioFormState
  | ((prev: AdaptiveStudioFormState) => AdaptiveStudioFormState);

export type AdaptiveStudioUnifiedProfileRow = {
  profile_id: string;
  profile_name: string;
  created_at: string;
  updated_at: string;
  strategy_profile: AdaptiveStudioObjectRecord;
  execution_profile: AdaptiveStudioObjectRecord;
  source_strategy_combo_profile_id: string;
  source_adaptive_tuner_profile_id: string;
};

export type AdaptiveStudioComboProfileRow = {
  profile_id?: unknown;
  profile_name?: unknown;
  strategy_params?: AdaptiveStudioObjectRecord;
  [key: string]: unknown;
};

export type AdaptiveStudioTunedProfileRow = {
  profile_id?: unknown;
  profile_name?: unknown;
  candidate?: AdaptiveStudioObjectRecord;
  best_trial?: AdaptiveStudioObjectRecord;
  [key: string]: unknown;
};

export type AdaptiveStudioStudioProfileRow = {
  profile_id: string;
  profile_name: string;
  created_at: string;
  updated_at: string;
  adaptive_form: AdaptiveStudioObjectRecord;
  execution_modules: AdaptiveStudioObjectRecord;
  execution_params: AdaptiveStudioObjectRecord;
  strategy_combo_profile_id: string;
  strategy_combo_profile_name: string;
};
