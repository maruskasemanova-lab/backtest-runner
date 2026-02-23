import { useCallback } from "react";
import type { Dispatch, FormEvent, SetStateAction } from "react";
import { buildMomentumDiversificationOverridePayload } from "./momentumUtils";
import {
  normalizeStartMode,
  deriveStartModeFromLegacyFlags,
  START_MODE_FAST_RESTART,
  resolveStartModeRuntime,
  START_MODE_RESUME_WARM_START,
  normalizeStopLossMode,
  resolveFixedStopLossPct,
  buildNormalizedIntradayLevels,
  buildNormalizedContextRisk,
  normalizeTradeEvalMode,
  ACTIVE_UNIFIED_PROFILE_SENTINEL,
  MU_SCALP_PROFILE_ID,
  RUN_ID_COLLISION_PATTERN,
  buildDefaultRunId,
  AVAILABLE_RANGE_HINT_PATTERN,
  buildRunKeyFromStartPayload,
} from "./runConfigHelpers";

type UseRunConfigStartHandlerArgs = {
  config: Record<string, any>;
  setConfig: Dispatch<SetStateAction<Record<string, any>>>;
  onStart: (payload: Record<string, any>) => Promise<any>;
  setLoading: Dispatch<SetStateAction<boolean>>;
  setStartTiming: Dispatch<SetStateAction<Record<string, any> | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setCacheFlushMessage: Dispatch<SetStateAction<string | null>>;
  setPrewarmStatus: Dispatch<SetStateAction<{ state: string; message: string }>>;
  selectedUnifiedProfileId: string;
  applyUnifiedProfile: (
    ticker: string,
    profileId: string,
    options: { applyNow: boolean; applyExecution: boolean },
  ) => Promise<any>;
  activeUnifiedProfileId: string;
  setActiveUnifiedProfileId: (profileId: string) => void;
  fetchTickerAosConfig: (ticker: string, options: { hydrateExecution: boolean }) => Promise<any>;
  fetchUnifiedProfiles: (ticker: string) => Promise<any>;
  activeStrategySelectionMode: string;
  activeMaxActiveStrategies: number;
  activeRunOptions: Array<Record<string, any>>;
};

export const useRunConfigStartHandler = ({
  config,
  setConfig,
  onStart,
  setLoading,
  setStartTiming,
  setError,
  setCacheFlushMessage,
  setPrewarmStatus,
  selectedUnifiedProfileId,
  applyUnifiedProfile,
  activeUnifiedProfileId,
  setActiveUnifiedProfileId,
  fetchTickerAosConfig,
  fetchUnifiedProfiles,
  activeStrategySelectionMode,
  activeMaxActiveStrategies,
  activeRunOptions,
}: UseRunConfigStartHandlerArgs) =>
  useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      setLoading(true);
      setStartTiming(null);
      setError(null);
      setCacheFlushMessage(null);

      try {
        const startMode = normalizeStartMode(
          deriveStartModeFromLegacyFlags(config, START_MODE_FAST_RESTART),
        );
        const runtimeStartMode = resolveStartModeRuntime(startMode);
        const checkpointPath =
          startMode === START_MODE_RESUME_WARM_START
            ? String(config.checkpoint_path || "").trim() || null
            : null;
        const stopLossMode = normalizeStopLossMode(config.stop_loss_mode, "strategy");
        const fixedStopLossPct = resolveFixedStopLossPct(stopLossMode, config.fixed_stop_loss_pct);
        const normalizedIntradayLevels = buildNormalizedIntradayLevels(config);
        const normalizedContextRisk = buildNormalizedContextRisk(config);
        const tradeEvalMode = normalizeTradeEvalMode(config.trade_eval_mode);
        let unifiedProfileChanged = false;
        let unifiedAppliedProfileId = "";
        if (config.ticker) {
          const selectedProfileId =
            selectedUnifiedProfileId === ACTIVE_UNIFIED_PROFILE_SENTINEL
              ? ""
              : String(selectedUnifiedProfileId || "").trim();
          if (selectedProfileId) {
            try {
              await applyUnifiedProfile(config.ticker, selectedProfileId, {
                applyNow: true,
                applyExecution: false,
              });
              unifiedAppliedProfileId = selectedProfileId;
              if (selectedProfileId !== String(activeUnifiedProfileId || "").trim()) {
                setActiveUnifiedProfileId(selectedProfileId);
                unifiedProfileChanged = true;
              }
            } catch (profileErr: any) {
              throw new Error(`Failed to apply unified profile: ${profileErr.message}`);
            }
          }
        }

        const payload: Record<string, any> = {
          run_id: String(config.run_id || "").trim() || buildDefaultRunId(),
          ticker: String(config.ticker || "").trim().toUpperCase(),
          date_from: config.date_from,
          date_to: config.date_to,
          include_extended_hours: !!config.include_extended_hours,
          strategy_api_url: config.strategy_api_url,
          regime_detection_minutes: Number(config.regime_detection_minutes),
          account_size_usd: Number(config.account_size_usd),
          risk_per_trade_pct: Number(config.risk_per_trade_pct),
          max_position_notional_pct: Number(config.max_position_notional_pct),
          max_fill_participation_rate: Number(config.max_fill_participation_rate),
          min_fill_ratio: Number(config.min_fill_ratio),
          trailing_stop_pct: Math.max(0, Number(config.trailing_stop_pct || 0)),
          global_exit_rr_ratio: Math.max(0, Number(config.global_exit_rr_ratio || 0)),
          global_risk_atr_stop_multiplier: Math.max(
            0,
            Number(config.global_risk_atr_stop_multiplier || 0),
          ),
          global_risk_volume_stop_pct: Math.max(0, Number(config.global_risk_volume_stop_pct || 0)),
          global_risk_min_stop_loss_pct: Math.max(
            0,
            Number(config.global_risk_min_stop_loss_pct || 0),
          ),
          trailing_activation_pct: Number(config.trailing_activation_pct),
          break_even_buffer_pct: Number(config.break_even_buffer_pct),
          break_even_min_hold_bars: Number(config.break_even_min_hold_bars),
          break_even_activation_min_mfe_pct: Math.max(0, Number(config.break_even_activation_min_mfe_pct || 0)),
          break_even_activation_use_levels: config.break_even_activation_use_levels !== false,
          break_even_activation_use_l2: config.break_even_activation_use_l2 !== false,
          break_even_activation_min_r: Math.max(0, Number(config.break_even_activation_min_r || 0)),
          break_even_activation_min_r_trending_5m: Math.max(0, Number(config.break_even_activation_min_r_trending_5m || 0)),
          break_even_activation_min_r_choppy_5m: Math.max(0, Number(config.break_even_activation_min_r_choppy_5m || 0)),
          enable_partial_take_profit: config.enable_partial_take_profit !== false,
          partial_take_profit_rr: Math.max(0.25, Number(config.partial_take_profit_rr || 1.0)),
          partial_take_profit_fraction: Math.max(0.05, Math.min(0.95, Number(config.partial_take_profit_fraction || 0.5))),
          partial_flow_deterioration_min_r: Math.max(0, Number(config.partial_flow_deterioration_min_r || 0.5)),
          partial_flow_deterioration_skip_be: config.partial_flow_deterioration_skip_be !== false,
          trailing_enabled_in_choppy: !!config.trailing_enabled_in_choppy,
          time_exit_bars: Number(config.time_exit_bars),
          adverse_flow_exit_enabled: !!config.adverse_flow_exit_enabled,
          adverse_flow_threshold: Number(config.adverse_flow_threshold),
          adverse_flow_min_hold_bars: Number(config.adverse_flow_min_hold_bars),
          stop_loss_mode: stopLossMode,
          fixed_stop_loss_pct: fixedStopLossPct,
          regime_filter: config.regime_filter,
          l2_only: !!config.l2_only,
          l2_confirm_enabled: !!config.l2_confirm_enabled,
          l2_min_imbalance: Number(config.l2_min_imbalance),
          l2_min_directional_consistency: Number(config.l2_min_directional_consistency),
          l2_min_signed_aggression: Number(config.l2_min_signed_aggression),
          l2_lookback_bars: Number(config.l2_lookback_bars),
          trade_eval_mode: tradeEvalMode,
          ...normalizedIntradayLevels,
          ...normalizedContextRisk,
          comparable_mode: runtimeStartMode.comparableMode,
          orchestrator_reset_scope: runtimeStartMode.orchestratorResetScope,
          apply_aos_optimizations_on_start: !!config.apply_aos_optimizations_on_start,
          apply_ticker_overrides_on_start: false,
          cold_start_each_day: runtimeStartMode.coldStartEachDay,
          checkpoint_path: checkpointPath,
          auto_save_checkpoint: !!config.auto_save_checkpoint,
          strategy_selection_mode: activeStrategySelectionMode,
          max_active_strategies: activeMaxActiveStrategies,
        };

        if (config.momentum_diversification_override_enabled) {
          payload.momentum_diversification_override =
            buildMomentumDiversificationOverridePayload(config);
        }

        if (config.data_file) {
          payload.data_file = config.data_file;
        }
        if (unifiedAppliedProfileId === MU_SCALP_PROFILE_ID) {
          payload.strategy_selection_mode = "all_enabled";
          payload.max_active_strategies = 1;
          payload.trade_eval_mode = "intrabar_1s";
        }
        if (startMode === START_MODE_RESUME_WARM_START && !payload.checkpoint_path) {
          console.info("Resume mode selected but no checkpoint specified, proceeding without load.");
        }
        const activeRunKeys = new Set(
          (Array.isArray(activeRunOptions) ? activeRunOptions : [])
            .map((row) => String(row?.run_key || "").trim())
            .filter(Boolean),
        );
        const ensureUniqueRunIdentity = (candidatePayload: Record<string, any>) => {
          let nextPayload = {
            ...candidatePayload,
            run_id: String(candidatePayload.run_id || "").trim() || buildDefaultRunId(),
          };
          let nextRunKey = buildRunKeyFromStartPayload(nextPayload);
          let attempts = 0;
          while (nextRunKey && activeRunKeys.has(nextRunKey) && attempts < 8) {
            nextPayload = {
              ...nextPayload,
              run_id: buildDefaultRunId(),
            };
            nextRunKey = buildRunKeyFromStartPayload(nextPayload);
            attempts += 1;
          }
          return { payload: nextPayload, runKey: nextRunKey };
        };

        const initialIdentity = ensureUniqueRunIdentity(payload);
        let effectivePayload: Record<string, any> = initialIdentity.payload;
        let effectiveRunKey = initialIdentity.runKey;
        if (String(effectivePayload.run_id || "").trim() !== String(payload.run_id || "").trim()) {
          setConfig((prev) => ({
            ...prev,
            run_id: String(effectivePayload.run_id || ""),
          }));
        }

        let startResult: any = null;
        for (let attempt = 0; attempt < 4; attempt += 1) {
          try {
            startResult = await onStart(effectivePayload);
            break;
          } catch (startErr: any) {
            const startMessage = String(startErr?.message || "");
            if (!RUN_ID_COLLISION_PATTERN.test(startMessage) || attempt >= 3) {
              throw startErr;
            }
            if (effectiveRunKey) {
              activeRunKeys.add(effectiveRunKey);
            }
            const retryIdentity = ensureUniqueRunIdentity({
              ...effectivePayload,
              run_id: buildDefaultRunId(),
            });
            effectivePayload = retryIdentity.payload;
            effectiveRunKey = retryIdentity.runKey;
            setConfig((prev) => ({
              ...prev,
              run_id: String(effectivePayload.run_id || ""),
            }));
          }
        }
        if (!startResult) {
          throw new Error("Failed to start run after collision retries.");
        }
        const timingPayload = startResult?.start_timing;
        if (timingPayload && typeof timingPayload === "object") {
          setStartTiming(timingPayload);
        }
        const progressiveInfo = startResult?.progressive_loading;
        if (progressiveInfo?.enabled) {
          const pendingChunks = Number(progressiveInfo?.pending_chunks || 0);
          const loadedUntil = String(progressiveInfo?.loaded_until || "").trim();
          const targetEnd = String(progressiveInfo?.target_end || "").trim();
          setPrewarmStatus({
            state: "warming",
            message: `Run started immediately (loaded until ${loadedUntil || "n/a"}). Remaining chunks: ${pendingChunks} (target ${targetEnd || "n/a"}).`,
          });
        }
        if (unifiedProfileChanged && config.ticker) {
          Promise.allSettled([
            fetchTickerAosConfig(config.ticker, { hydrateExecution: true }),
            fetchUnifiedProfiles(config.ticker),
          ]).catch(() => null);
        }
      } catch (err: any) {
        setStartTiming(null);
        const message = String(err?.message || "Failed to start run.");
        const rangeHintMatch = message.match(AVAILABLE_RANGE_HINT_PATTERN);
        if (rangeHintMatch) {
          const hintedFrom = String(rangeHintMatch[1] || "").trim();
          const hintedTo = String(rangeHintMatch[2] || "").trim();
          if (hintedFrom && hintedTo) {
            setConfig((prev) => ({
              ...prev,
              date: hintedFrom,
              date_from: hintedFrom,
              date_to: hintedTo,
            }));
            setError(
              `${message} Date range was auto-adjusted to ${hintedFrom} -> ${hintedTo}. Start the run again.`,
            );
            return;
          }
        }
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [
      activeMaxActiveStrategies,
      activeStrategySelectionMode,
      activeUnifiedProfileId,
      applyUnifiedProfile,
      config,
      fetchTickerAosConfig,
      fetchUnifiedProfiles,
      onStart,
      selectedUnifiedProfileId,
      setActiveUnifiedProfileId,
      setCacheFlushMessage,
      setConfig,
      setError,
      setLoading,
      setPrewarmStatus,
      setStartTiming,
      activeRunOptions,
    ],
  );
