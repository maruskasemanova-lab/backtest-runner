import { describe, expect, it } from "vitest";
import {
  buildAdaptiveConfigUpdate,
  buildStudioProfileDeleteConfig,
  buildStudioProfileSaveConfig,
  resolveLinkedComboProfile,
} from "./adaptive-studio-builders";
import { DEFAULT_STRATEGIES } from "../constants/adaptive-studio";

describe("adaptive studio builders", () => {
  it("builds adaptive config update with normalized adaptive and execution state", () => {
    const nextConfig = buildAdaptiveConfigUpdate({
      rawTickerConfig: {
        adaptive: {
          use_ohlcv_fallbacks: false,
        },
        positioning: {
          existing_toggle: true,
        },
      },
      form: {
        strategy_selection_mode: "adaptive_top_n",
        max_active_strategies: 4,
        flow_bias_enabled: true,
        use_ohlcv_fallbacks: true,
        min_active_bars_before_switch: 2,
        switch_cooldown_bars: 5,
        flow_bias_strategies: ["Momentum Flow", "momentum-flow"] as unknown as string[],
        regime_preferences: {
          TRENDING: ["Momentum Flow", "pull back"] as unknown as string[],
        },
        micro_regime_preferences: {
          BREAKOUT: ["Gap Liquidity"] as unknown as string[],
        },
      },
      strategyUniverse: DEFAULT_STRATEGIES,
      executionModulesSnapshot: {
        l2_confirm_enabled: true,
      },
      executionParamsSnapshot: {
        trailing_stop_pct: 0.75,
      },
    });

    expect(nextConfig).toMatchObject({
      strategy_selection_mode: "adaptive_top_n",
      max_active_strategies: 4,
      positioning: {
        existing_toggle: true,
        l2_confirm_enabled: true,
        trailing_stop_pct: 0.75,
      },
      adaptive: {
        flow_bias_enabled: true,
        use_ohlcv_fallbacks: true,
        flow_bias_strategies: ["momentum_flow"],
        regime_preferences: {
          TRENDING: ["momentum_flow", "pullback"],
        },
        micro_regime_preferences: {
          BREAKOUT: ["gap_liquidity"],
        },
      },
    });
  });

  it("builds studio profile save config with stable profile id for same name", () => {
    const result = buildStudioProfileSaveConfig({
      activeTicker: "MU",
      currentConfig: {},
      currentProfiles: [
        {
          profile_id: "mu-existing",
          profile_name: "MU Existing",
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-02T00:00:00Z",
          adaptive_form: {},
          execution_modules: {},
          execution_params: {},
          strategy_combo_profile_id: "",
          strategy_combo_profile_name: "",
        },
      ],
      profileName: "MU Existing",
      form: {
        strategy_selection_mode: "adaptive_top_n",
        max_active_strategies: 3,
        flow_bias_enabled: true,
        use_ohlcv_fallbacks: true,
        min_active_bars_before_switch: 0,
        switch_cooldown_bars: 0,
        flow_bias_strategies: ["momentum_flow"],
        regime_preferences: {},
        micro_regime_preferences: {},
      },
      strategyUniverse: DEFAULT_STRATEGIES,
      executionModulesSnapshot: {
        l2_confirm_enabled: true,
      },
      executionParamsSnapshot: {
        trailing_stop_pct: 0.8,
      },
      comboProfileId: "combo-1",
      comboProfileName: "Combo 1",
    });

    expect(result.savedProfileId).toBe("mu-existing");
    expect(result.nextConfig).toMatchObject({
      active_adaptive_studio_profile_id: "mu-existing",
      adaptive_studio_profiles: [
        {
          profile_id: "mu-existing",
          strategy_combo_profile_id: "combo-1",
          strategy_combo_profile_name: "Combo 1",
        },
      ],
    });
  });

  it("builds studio profile delete config and promotes next profile when deleting active", () => {
    const result = buildStudioProfileDeleteConfig({
      currentConfig: {},
      currentProfiles: [
        {
          profile_id: "profile-a",
          profile_name: "A",
          created_at: "",
          updated_at: "",
          adaptive_form: {},
          execution_modules: {},
          execution_params: {},
          strategy_combo_profile_id: "",
          strategy_combo_profile_name: "",
        },
        {
          profile_id: "profile-b",
          profile_name: "B",
          created_at: "",
          updated_at: "",
          adaptive_form: {},
          execution_modules: {},
          execution_params: {},
          strategy_combo_profile_id: "",
          strategy_combo_profile_name: "",
        },
      ],
      activeStudioProfileId: "profile-a",
      targetProfileId: "profile-a",
    });

    expect(result.nextActiveProfileId).toBe("profile-b");
    expect(result.nextConfig).toMatchObject({
      active_adaptive_studio_profile_id: "profile-b",
      adaptive_studio_profiles: [{ profile_id: "profile-b" }],
    });
  });

  it("resolves linked combo profile label from active combo id", () => {
    expect(
      resolveLinkedComboProfile({
        activeComboId: "combo-1",
        comboList: [{ profile_id: "combo-1", profile_name: "Combo 1" }],
      }),
    ).toEqual({
      comboProfileId: "combo-1",
      comboProfileName: "Combo 1",
    });
  });
});
