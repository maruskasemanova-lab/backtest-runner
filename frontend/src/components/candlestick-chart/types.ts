import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type {
  CandlestickChartApiLike,
  CandlestickChartAppliedBarsMeta,
  CandlestickChartCandleSeriesLike,
  CandlestickChartHistogramSeriesLike,
  CandlestickChartProps,
  CandlestickChartTooltipState,
  CandlestickChartVisibleRange,
} from "../CandlestickChart";

export type CandlestickChartRef = MutableRefObject<CandlestickChartApiLike | null>;
export type CandlestickChartContainerRef = MutableRefObject<HTMLDivElement | null>;
export type CandlestickChartCandleSeriesRef = MutableRefObject<CandlestickChartCandleSeriesLike | null>;
export type CandlestickChartHistogramSeriesRef =
  MutableRefObject<CandlestickChartHistogramSeriesLike | null>;
export type CandlestickChartAppliedBarsMetaRef = MutableRefObject<CandlestickChartAppliedBarsMeta>;
export type CandlestickChartVisibleRangeRef = MutableRefObject<CandlestickChartVisibleRange | null>;
export type CandlestickChartBooleanRef = MutableRefObject<boolean>;
export type CandlestickChartInteractionTimeoutRef =
  MutableRefObject<ReturnType<typeof setTimeout> | null>;
export type CandlestickChartOnChartStateChangeRef =
  MutableRefObject<CandlestickChartProps["onChartStateChange"]>;
export type CandlestickChartTooltipSetter = Dispatch<SetStateAction<CandlestickChartTooltipState>>;
export type CandlestickChartErrorSetter = Dispatch<SetStateAction<string | null>>;
export type CandlestickChartMarkerFocusKeyRef = MutableRefObject<string | null>;
