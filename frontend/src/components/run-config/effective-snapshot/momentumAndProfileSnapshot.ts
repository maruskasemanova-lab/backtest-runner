export const buildActiveMomentumDiversificationSnapshot = ({
  effectiveConfig,
}: {
  effectiveConfig: Record<string, any>;
}) => {
const activeMomentumDiversificationRaw =
  effectiveConfig?.momentum_diversification &&
  typeof effectiveConfig.momentum_diversification === "object" &&
  !Array.isArray(effectiveConfig.momentum_diversification)
    ? effectiveConfig.momentum_diversification
    : {};
const activeMomentumDiversificationApplied = Boolean(effectiveConfig?.momentum_diversification_applied);
const activeMomentumDiversificationSource = String(
  effectiveConfig?.momentum_diversification_source || "none",
);

  return {
    activeMomentumDiversificationRaw,
    activeMomentumDiversificationApplied,
    activeMomentumDiversificationSource,
  };
};

export const resolveEffectiveUnifiedProfileId = ({
  effectiveConfig,
  selectedUnifiedProfileId,
  activeUnifiedProfileId,
  activeProfileSentinel,
}: {
  effectiveConfig: Record<string, any>;
  selectedUnifiedProfileId: string;
  activeUnifiedProfileId: string;
  activeProfileSentinel: string;
}) => {
const effectiveUnifiedProfileIdFromRun = String(
  effectiveConfig?.unified_profile_id ||
    effectiveConfig?.unified_profile?.active_profile_id ||
    effectiveConfig?.unified_profile?.profile_id ||
    "",
).trim();
const requestedUnifiedProfileId =
  selectedUnifiedProfileId === activeProfileSentinel
    ? ""
    : String(selectedUnifiedProfileId || "").trim();
const effectiveUnifiedProfileId =
  effectiveUnifiedProfileIdFromRun ||
  requestedUnifiedProfileId ||
  String(activeUnifiedProfileId || "").trim();

  return effectiveUnifiedProfileId;
};
