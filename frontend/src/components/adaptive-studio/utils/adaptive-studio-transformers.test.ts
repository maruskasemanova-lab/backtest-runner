import { describe, expect, it } from "vitest";
import {
  buildLegacyUnifiedProfiles,
  normalizeTickerAdaptiveForm,
} from "./adaptive-studio-transformers";
import { DEFAULT_STRATEGIES } from "../constants/adaptive-studio";

describe("adaptive studio transformers", () => {
  it("normalizes adaptive ticker form snapshots with defaults and strategy canonicalization", () => {
    expect(
      normalizeTickerAdaptiveForm(
        {
          strategy_selection_mode: "unknown",
          max_active_strategies: "not-an-int",
          adaptive: {
            flow_bias_enabled: "yes",
            use_ohlcv_fallbacks: "off",
            flow_bias_strategies: ["Momentum Flow", "momentum-flow", "  "],
            regime_preferences: {
              TRENDING: ["Momentum Flow", "pull back"],
            },
          },
        },
        DEFAULT_STRATEGIES,
      ),
    ).toMatchObject({
      strategy_selection_mode: "adaptive_top_n",
      max_active_strategies: 3,
      flow_bias_enabled: true,
      use_ohlcv_fallbacks: false,
      flow_bias_strategies: ["momentum_flow"],
      regime_preferences: {
        TRENDING: ["momentum_flow", "pullback"],
      },
    });
  });

  it("builds legacy unified profiles with active combo+tuned sources first", () => {
    const payload = buildLegacyUnifiedProfiles({
      ticker: "MU",
      tickerConfig: {
        strategy_selection_mode: "adaptive_top_n",
        max_active_strategies: 3,
        adaptive: {
          flow_bias_enabled: true,
        },
      },
      comboPayload: {
        active_profile_id: "combo-active",
        profiles: [
          {
            profile_id: "combo-other",
            profile_name: "Other Combo",
            updated_at: "2025-01-01T00:00:00Z",
            strategy_params: {},
          },
          {
            profile_id: "combo-active",
            profile_name: "Active Combo",
            updated_at: "2025-01-02T00:00:00Z",
            strategy_params: {},
          },
        ],
      },
      tunedPayload: {
        active_profile_id: "tuned-active",
        profiles: [
          {
            profile_id: "tuned-active",
            profile_name: "Active Tuned",
            updated_at: "2025-01-02T00:00:00Z",
            candidate: {
              enabled_strategies: ["momentum_flow"],
            },
          },
        ],
      },
    });

    expect(payload.active_profile_id).toBe("legacy-unified-MU-combo-active-tuned-active");
    expect(payload.profiles[0]).toMatchObject({
      profile_id: "legacy-unified-MU-combo-active-tuned-active",
      source_strategy_combo_profile_id: "combo-active",
      source_adaptive_tuner_profile_id: "tuned-active",
    });
  });
});
