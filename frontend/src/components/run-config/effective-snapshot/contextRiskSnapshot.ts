import type { EffectiveSnapshotConfigContext } from "./types";

export const buildActiveContextRiskSnapshot = ({
  config,
  effectiveConfig,
}: EffectiveSnapshotConfigContext) => {
const activeContextAwareRiskEnabled = Boolean(
  effectiveConfig.context_aware_risk_enabled ?? config.context_aware_risk_enabled ?? false,
);
const activeContextRiskSlBufferPct = Math.max(
  0,
  Number(effectiveConfig.context_risk_sl_buffer_pct ?? config.context_risk_sl_buffer_pct ?? 0.03),
);
const activeContextRiskMinRoomPct = Math.max(
  0,
  Number(effectiveConfig.context_risk_min_room_pct ?? config.context_risk_min_room_pct ?? 0.15),
);
const activeContextRiskMinEffectiveRr = Math.max(
  0,
  Number(
    effectiveConfig.context_risk_min_effective_rr ?? config.context_risk_min_effective_rr ?? 0.8,
  ),
);
const activeContextRiskTrailingTightenZone = Math.max(
  0,
  Math.min(
    1,
    Number(
      effectiveConfig.context_risk_trailing_tighten_zone ??
        config.context_risk_trailing_tighten_zone ??
        0.2,
    ),
  ),
);
const activeContextRiskTrailingTightenFactor = Math.max(
  0,
  Math.min(
    1,
    Number(
      effectiveConfig.context_risk_trailing_tighten_factor ??
        config.context_risk_trailing_tighten_factor ??
        0.5,
    ),
  ),
);
const activeContextRiskLevelTrailEnabled = Boolean(
  effectiveConfig.context_risk_level_trail_enabled ??
    config.context_risk_level_trail_enabled ??
    true,
);
const activeContextRiskMaxAnchorSearchPct = Math.max(
  0.1,
  Number(
    effectiveConfig.context_risk_max_anchor_search_pct ??
      config.context_risk_max_anchor_search_pct ??
      1.5,
  ),
);
const activeContextRiskMinLevelTestsForSl = Math.max(
  0,
  Math.trunc(
    Number(
      effectiveConfig.context_risk_min_level_tests_for_sl ??
        config.context_risk_min_level_tests_for_sl ??
        1,
    ),
  ),
);

  return {
    activeContextAwareRiskEnabled,
    activeContextRiskSlBufferPct,
    activeContextRiskMinRoomPct,
    activeContextRiskMinEffectiveRr,
    activeContextRiskTrailingTightenZone,
    activeContextRiskTrailingTightenFactor,
    activeContextRiskLevelTrailEnabled,
    activeContextRiskMaxAnchorSearchPct,
    activeContextRiskMinLevelTestsForSl,
  };
};
