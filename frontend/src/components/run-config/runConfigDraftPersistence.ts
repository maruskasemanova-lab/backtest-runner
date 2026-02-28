import {
  RUN_CONFIG_DRAFT_STORAGE_KEY,
  RUN_CONFIG_DRAFT_VERSION,
  START_MODE_FAST_RESTART,
  MU_TICKER,
  deriveStartModeFromLegacyFlags,
  normalizeStartMode,
} from "./runConfigCore";

export const isPlainObject = (value) =>
  !!value && typeof value === "object" && !Array.isArray(value);

export const readPersistedRunConfigDraft = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(RUN_CONFIG_DRAFT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!isPlainObject(parsed)) return null;

    if (isPlainObject(parsed.config)) {
      return {
        version: Number(parsed.version || RUN_CONFIG_DRAFT_VERSION),
        saved_at: String(parsed.saved_at || ""),
        config: parsed.config,
        selected_unified_profile_id: String(parsed.selected_unified_profile_id || ""),
      };
    }

    // Backward compatibility for older draft format = plain config object.
    return {
      version: 0,
      saved_at: "",
      config: parsed,
      selected_unified_profile_id: "",
    };
  } catch (error) {
    console.warn("Failed to read persisted run config draft:", error);
    return null;
  }
};

export const normalizeDraftVersion = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const applyRunConfigDraftMigrations = (mergedConfig, draftConfig, draftVersion) => {
  const version = normalizeDraftVersion(draftVersion);
  if (!isPlainObject(draftConfig)) {
    return mergedConfig;
  }
  const nextConfig = {
    ...mergedConfig,
    start_mode: deriveStartModeFromLegacyFlags(
      draftConfig,
      normalizeStartMode(mergedConfig.start_mode, START_MODE_FAST_RESTART),
    ),
  };

  if (version < 3 && !Object.prototype.hasOwnProperty.call(draftConfig, "start_mode")) {
    return nextConfig;
  }
  // v3 -> v4: loosen context-risk & intraday-levels defaults
  if (version < 4) {
    nextConfig.context_risk_sl_buffer_pct = 0.05;
    nextConfig.context_risk_min_room_pct = 0.08;
    nextConfig.context_risk_min_effective_rr = 0.5;
    nextConfig.intraday_levels_min_levels_for_context = 1;
    nextConfig.intraday_levels_min_confluence_score = 1;
    nextConfig.intraday_levels_momentum_min_room_pct = 0.15;
  }
  // v4 -> v5: loosen entry quality gates
  if (version < 5) {
    nextConfig.intraday_levels_micro_confirmation_enabled = false;
    nextConfig.intraday_levels_break_cooldown_bars = 3;
    nextConfig.intraday_levels_adaptive_window_rvol_threshold = 0.5;
    nextConfig.time_exit_bars = Math.max(nextConfig.time_exit_bars || 0, 15);
  }
  // v5 -> v6: data-driven tuning - wider SL/TP, less noise exits
  if (version < 6) {
    nextConfig.trailing_activation_pct = 0.20;
    nextConfig.trailing_stop_pct = 0.80;
    nextConfig.break_even_buffer_pct = 0.03;
    nextConfig.break_even_min_hold_bars = 3;
    nextConfig.time_exit_bars = Math.max(nextConfig.time_exit_bars || 0, 20);
    nextConfig.context_risk_sl_buffer_pct = 0.10;
    nextConfig.context_risk_max_anchor_search_pct = 2.5;
    nextConfig.global_risk_min_stop_loss_pct = 0.15;
  }
  // v6 -> v7: default to all strategies enabled unless draft explicitly pins another mode.
  if (version < 7) {
    const hasExplicitMode = Object.prototype.hasOwnProperty.call(draftConfig, "strategy_selection_mode");
    if (!hasExplicitMode || !String(nextConfig.strategy_selection_mode || "").trim()) {
      nextConfig.strategy_selection_mode = "all_enabled";
    }
    const hasExplicitMax = Object.prototype.hasOwnProperty.call(draftConfig, "max_active_strategies");
    if (!hasExplicitMax || !Number.isFinite(Number(nextConfig.max_active_strategies))) {
      nextConfig.max_active_strategies = 20;
    }
  }
  // v7 -> v8: enable MU entry-quality gate by default for older drafts.
  if (version < 8) {
    const ticker = String(nextConfig.ticker || draftConfig.ticker || "").trim().toUpperCase();
    if (ticker === MU_TICKER) {
      nextConfig.intraday_levels_entry_quality_enabled = true;
    }
  }
  // v8 -> v9: default to using both L2 and TCBBO flow gates in run-start payloads.
  if (version < 9) {
    nextConfig.l2_confirm_enabled = true;
    nextConfig.tcbbo_gate_enabled = true;
    nextConfig.tcbbo_min_net_premium = Number.isFinite(Number(nextConfig.tcbbo_min_net_premium))
      ? Number(nextConfig.tcbbo_min_net_premium)
      : 0.0;
    nextConfig.tcbbo_sweep_boost = Number.isFinite(Number(nextConfig.tcbbo_sweep_boost))
      ? Number(nextConfig.tcbbo_sweep_boost)
      : 5.0;
    nextConfig.tcbbo_lookback_bars = Number.isFinite(Number(nextConfig.tcbbo_lookback_bars))
      ? Math.max(1, Math.trunc(Number(nextConfig.tcbbo_lookback_bars)))
      : 5;
  }
  return nextConfig;
};

export const mergeRunConfigWithDefaults = (draftConfig, defaults, draftVersion = RUN_CONFIG_DRAFT_VERSION) => {
  if (!isPlainObject(draftConfig)) {
    return defaults;
  }
  const merged = { ...defaults };
  Object.keys(defaults).forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(draftConfig, key)) {
      merged[key] = draftConfig[key];
    }
  });
  if (!Array.isArray(merged.momentum_sleeves)) {
    merged.momentum_sleeves = [];
  }
  if (!Array.isArray(merged.regime_filter)) {
    merged.regime_filter = [];
  }
  return applyRunConfigDraftMigrations(merged, draftConfig, draftVersion);
};

export const writePersistedRunConfigDraft = (config, selectedUnifiedProfileId) => {
  if (typeof window === "undefined") return null;
  try {
    const payload = {
      version: RUN_CONFIG_DRAFT_VERSION,
      saved_at: new Date().toISOString(),
      config,
      selected_unified_profile_id: String(selectedUnifiedProfileId || ""),
    };
    window.localStorage.setItem(RUN_CONFIG_DRAFT_STORAGE_KEY, JSON.stringify(payload));
    return payload;
  } catch (error) {
    console.warn("Failed to persist run config draft:", error);
    return null;
  }
};
