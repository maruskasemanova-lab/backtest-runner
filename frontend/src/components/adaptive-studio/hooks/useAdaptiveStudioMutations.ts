import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type {
  AdaptiveStudioActionLoadingToken,
  AdaptiveStudioObjectRecord,
  AdaptiveStudioUnifiedProfileRow,
} from "../profileTypes";

type UseAdaptiveStudioMutationsArgs = {
  activeTicker: string;
  strategyApiBase: string;
  refreshActiveTickerData: () => Promise<void>;
  setTickerConfigCache: (nextConfig: AdaptiveStudioObjectRecord) => void;
};

type SaveAdaptiveConfigArgs = {
  nextConfig: AdaptiveStudioObjectRecord;
};

type CaptureUnifiedProfileArgs = {
  profileName: string;
  setActive?: boolean;
};

type ApplyUnifiedProfileArgs = {
  profile: AdaptiveStudioUnifiedProfileRow | null | undefined;
};

type JsonRequestResult = {
  payload: AdaptiveStudioObjectRecord;
  response: Response;
};

type UseAdaptiveStudioMutationsResult = {
  saving: boolean;
  unifiedActionLoading: AdaptiveStudioActionLoadingToken;
  saveAdaptiveConfig: (args: SaveAdaptiveConfigArgs) => Promise<AdaptiveStudioObjectRecord>;
  captureUnifiedProfile: (args: CaptureUnifiedProfileArgs) => Promise<void>;
  applyUnifiedProfile: (args: ApplyUnifiedProfileArgs) => Promise<void>;
};

const asPayloadRecord = (value: unknown): AdaptiveStudioObjectRecord =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as AdaptiveStudioObjectRecord)
    : {};

const buildHttpError = (
  payload: AdaptiveStudioObjectRecord,
  status: number,
  fallback?: string,
) => {
  const detail = String(payload.detail || "").trim();
  if (detail) return new Error(detail);
  if (fallback) return new Error(`${fallback} (HTTP ${status})`);
  return new Error(`HTTP ${status}`);
};

const postJson = async (url: string, body: unknown): Promise<JsonRequestResult> => {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = asPayloadRecord(await response.json().catch(() => ({})));
  return { response, payload };
};

const resolveUnifiedProfileSources = (
  profile: AdaptiveStudioUnifiedProfileRow | null | undefined,
) => {
  const strategyProfile = asPayloadRecord(profile?.strategy_profile);
  return {
    sourceCombo: String(
      profile?.source_strategy_combo_profile_id ||
        strategyProfile.active_strategy_combo_profile_id ||
        "",
    ).trim(),
    sourceAdaptive: String(
      profile?.source_adaptive_tuner_profile_id ||
        strategyProfile.active_adaptive_tuner_profile_id ||
        "",
    ).trim(),
  };
};

export function useAdaptiveStudioMutations({
  activeTicker,
  strategyApiBase,
  refreshActiveTickerData,
  setTickerConfigCache,
}: UseAdaptiveStudioMutationsArgs): UseAdaptiveStudioMutationsResult {
  const [captureUnifiedActionLoading, setCaptureUnifiedActionLoading] = useState<AdaptiveStudioActionLoadingToken>(null);
  const [applyUnifiedActionLoading, setApplyUnifiedActionLoading] = useState<AdaptiveStudioActionLoadingToken>(null);

  const saveAdaptiveConfigMutation = useMutation({
    mutationKey: ["adaptive-studio", "save-config", activeTicker],
    mutationFn: async ({ nextConfig }: SaveAdaptiveConfigArgs) => {
      if (!activeTicker) throw new Error("Ticker is required.");
      const { response, payload } = await postJson("/api/aos-config/update", {
        ticker: activeTicker,
        config: nextConfig,
      });
      if (!response.ok) {
        throw buildHttpError(payload, response.status, "Failed to save adaptive configuration");
      }
      return nextConfig;
    },
    onSuccess: (nextConfig) => {
      setTickerConfigCache(nextConfig);
    },
  });

  const captureUnifiedProfileMutation = useMutation({
    mutationKey: ["adaptive-studio", "capture-unified-profile", activeTicker],
    mutationFn: async ({ profileName, setActive = true }: CaptureUnifiedProfileArgs) => {
      if (!activeTicker || !profileName) throw new Error("Unified profile name is required.");
      const { response, payload } = await postJson("/api/profiles/capture", {
        ticker: activeTicker,
        profile_name: profileName,
        strategy_api_url: strategyApiBase,
        set_active: setActive,
      });
      if (!response.ok) {
        throw buildHttpError(payload, response.status);
      }
    },
    onMutate: () => {
      setCaptureUnifiedActionLoading("capture");
    },
    onSuccess: async () => {
      await refreshActiveTickerData();
    },
    onSettled: () => {
      setCaptureUnifiedActionLoading(null);
    },
  });

  const applyUnifiedProfileMutation = useMutation({
    mutationKey: ["adaptive-studio", "apply-unified-profile", activeTicker],
    mutationFn: async ({ profile }: ApplyUnifiedProfileArgs) => {
      const profileId = String(profile?.profile_id || "").trim();
      if (!activeTicker || !profileId) throw new Error("Unified profile ID is required.");

      const { response, payload } = await postJson("/api/profiles/apply", {
        ticker: activeTicker,
        profile_id: profileId,
        strategy_api_url: strategyApiBase,
        apply_now: false,
        apply_execution: true,
      });
      if (response.ok) return;

      const { sourceCombo, sourceAdaptive } = resolveUnifiedProfileSources(profile);
      if (!sourceCombo && !sourceAdaptive) {
        throw buildHttpError(payload, response.status);
      }

      if (sourceCombo) {
        const comboResult = await postJson("/api/strategy-combos/apply", {
          ticker: activeTicker,
          profile_id: sourceCombo,
          strategy_api_url: strategyApiBase,
          apply_now: false,
        });
        if (!comboResult.response.ok) {
          throw buildHttpError(
            comboResult.payload,
            comboResult.response.status,
            "Legacy combo apply failed",
          );
        }
      }

      if (sourceAdaptive) {
        const adaptiveResult = await postJson("/api/adaptive-tuner/profiles/apply", {
          ticker: activeTicker,
          profile_id: sourceAdaptive,
        });
        if (!adaptiveResult.response.ok) {
          throw buildHttpError(
            adaptiveResult.payload,
            adaptiveResult.response.status,
            "Legacy adaptive apply failed",
          );
        }
      }
    },
    onMutate: ({ profile }) => {
      const profileId = String(profile?.profile_id || "").trim();
      setApplyUnifiedActionLoading(profileId ? `active:${profileId}` : "active");
    },
    onSuccess: async () => {
      await refreshActiveTickerData();
    },
    onSettled: () => {
      setApplyUnifiedActionLoading(null);
    },
  });

  return {
    saving: saveAdaptiveConfigMutation.isPending,
    unifiedActionLoading: captureUnifiedActionLoading || applyUnifiedActionLoading,
    saveAdaptiveConfig: saveAdaptiveConfigMutation.mutateAsync,
    captureUnifiedProfile: captureUnifiedProfileMutation.mutateAsync,
    applyUnifiedProfile: applyUnifiedProfileMutation.mutateAsync,
  };
}
