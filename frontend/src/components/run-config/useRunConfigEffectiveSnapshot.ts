import { useMemo } from "react";
import {
  buildRunConfigEffectiveSnapshot,
  type BuildRunConfigEffectiveSnapshotArgs,
} from "./runConfigEffectiveSnapshotBuilder";

type UseRunConfigEffectiveSnapshotArgs = BuildRunConfigEffectiveSnapshotArgs;

export const useRunConfigEffectiveSnapshot = ({
  config,
  effectiveExecutionConfig,
  aosTickerConfig,
  selectedUnifiedProfileId,
  activeUnifiedProfileId,
  activeProfileSentinel,
  normalizeStrategySelectionMode,
  parseMaxActiveStrategies,
}: UseRunConfigEffectiveSnapshotArgs) =>
  useMemo(
    () =>
      buildRunConfigEffectiveSnapshot({
        config,
        effectiveExecutionConfig,
        aosTickerConfig,
        selectedUnifiedProfileId,
        activeUnifiedProfileId,
        activeProfileSentinel,
        normalizeStrategySelectionMode,
        parseMaxActiveStrategies,
      }),
    [
      activeProfileSentinel,
      activeUnifiedProfileId,
      aosTickerConfig,
      config,
      effectiveExecutionConfig,
      normalizeStrategySelectionMode,
      parseMaxActiveStrategies,
      selectedUnifiedProfileId,
    ],
  );
