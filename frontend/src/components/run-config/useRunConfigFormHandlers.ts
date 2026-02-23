import { useCallback, useMemo } from "react";
import type { Dispatch, SetStateAction } from "react";
import { normalizeIsoDay } from "../../utils";
import {
  MU_TICKER,
  MU_REPRO_DATE_TO,
  MU_REPRO_DATE_FROM,
  MU_SCALP_DATE_TO,
  MU_SCALP_DATE_FROM,
  START_MODE_DAY_ISOLATED_AUDIT,
  MU_INTRADAY_NON_OVERFIT_BASELINE,
  applyMuMomentumDefaults,
  resolveTickerCoverageRange,
  resolveDateRangeWithFallback,
} from "./runConfigHelpers";

type UseRunConfigFormHandlersArgs = {
  config: Record<string, any>;
  setConfig: Dispatch<SetStateAction<Record<string, any>>>;
  availableData: Record<string, any> | null;
  onTickerChange?: (ticker: string) => void;
  setSelectedUnifiedProfileId: (profileId: string) => void;
  muReproProfileId: string;
  muScalpProfileId: string;
};

export const useRunConfigFormHandlers = ({
  config,
  setConfig,
  availableData,
  onTickerChange,
  setSelectedUnifiedProfileId,
  muReproProfileId,
  muScalpProfileId,
}: UseRunConfigFormHandlersArgs) => {
  const dateRange = useMemo(() => {
    const coverage = resolveTickerCoverageRange({
      availableData,
      ticker: config.ticker,
      l2Only: !!config.l2_only,
    });
    const range = coverage.effectiveRange;
    return {
      min: range?.start || null,
      max: range?.end || null,
      l2_min: coverage.l2Range?.start || null,
      l2_max: coverage.l2Range?.end || null,
      ohlcv_min: coverage.ohlcvRange?.start || null,
      ohlcv_max: coverage.ohlcvRange?.end || null,
    };
  }, [availableData, config.ticker, config.l2_only]);

  const handleDateFromChange = useCallback(
    (value: string) => {
      setConfig((prev) => {
        const nextTo = prev.date_to && value > prev.date_to ? value : prev.date_to;
        return {
          ...prev,
          date_from: value,
          date: value,
          date_to: nextTo,
        };
      });
    },
    [setConfig],
  );

  const handleDateToChange = useCallback(
    (value: string) => {
      setConfig((prev) => {
        const nextFrom = prev.date_from && value < prev.date_from ? value : prev.date_from;
        return {
          ...prev,
          date_to: value,
          date: nextFrom || prev.date,
          date_from: nextFrom,
        };
      });
    },
    [setConfig],
  );

  const handleTickerChange = useCallback(
    (ticker: string) => {
      const upperTicker = String(ticker || "").trim().toUpperCase();
      const coverage = resolveTickerCoverageRange({
        availableData,
        ticker: upperTicker,
        l2Only: !!config.l2_only,
      });
      const range = coverage.effectiveRange;
      const defaultDate = normalizeIsoDay(range?.end);

      setConfig((prev) => {
        const prevTicker = String(prev.ticker || "").trim().toUpperCase();
        const tickerChanged = upperTicker !== prevTicker;
        const dateSeed = tickerChanged
          ? resolveDateRangeWithFallback({
              range,
              from: defaultDate || range?.start,
              to: defaultDate || range?.end,
              fallbackDate:
                defaultDate || range?.start || prev.date_from || prev.date_to || prev.date,
            })
          : resolveDateRangeWithFallback({
              range,
              from: prev.date_from,
              to: prev.date_to,
              fallbackDate: defaultDate || prev.date_from || prev.date_to || prev.date,
            });
        const nextDraft = {
          ...prev,
          ticker: upperTicker,
          ...dateSeed,
        };
        return applyMuMomentumDefaults(nextDraft, upperTicker, prev.ticker);
      });

      if (onTickerChange) {
        onTickerChange(upperTicker);
      }
    },
    [availableData, config.l2_only, onTickerChange, setConfig],
  );

  const handleApplyMuReproPreset = useCallback(() => {
    setConfig((prev) => {
      if (String(prev.ticker || "").trim().toUpperCase() !== MU_TICKER) {
        return prev;
      }
      return {
        ...prev,
        date: MU_REPRO_DATE_TO,
        date_from: MU_REPRO_DATE_FROM,
        date_to: MU_REPRO_DATE_TO,
        include_extended_hours: false,
        apply_aos_optimizations_on_start: true,
        start_mode: START_MODE_DAY_ISOLATED_AUDIT,
        momentum_diversification_override_enabled: false,
        ...MU_INTRADAY_NON_OVERFIT_BASELINE,
      };
    });
    setSelectedUnifiedProfileId(muReproProfileId);
  }, [muReproProfileId, setConfig, setSelectedUnifiedProfileId]);

  const handleApplyMuScalpPreset = useCallback(() => {
    setConfig((prev) => {
      if (String(prev.ticker || "").trim().toUpperCase() !== MU_TICKER) {
        return prev;
      }
      return {
        ...prev,
        date: MU_SCALP_DATE_TO,
        date_from: MU_SCALP_DATE_FROM,
        date_to: MU_SCALP_DATE_TO,
        include_extended_hours: false,
        l2_only: true,
        l2_confirm_enabled: true,
        l2_min_imbalance: 0.02,
        l2_min_directional_consistency: 0.25,
        l2_min_signed_aggression: 0.02,
        l2_lookback_bars: 3,
        start_mode: START_MODE_DAY_ISOLATED_AUDIT,
        apply_aos_optimizations_on_start: false,
        momentum_diversification_override_enabled: false,
      };
    });
    setSelectedUnifiedProfileId(muScalpProfileId);
  }, [muScalpProfileId, setConfig, setSelectedUnifiedProfileId]);

  return {
    dateRange,
    handleDateFromChange,
    handleDateToChange,
    handleTickerChange,
    handleApplyMuReproPreset,
    handleApplyMuScalpPreset,
  };
};
