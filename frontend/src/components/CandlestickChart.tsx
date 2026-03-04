import { memo, useEffect, useRef, useState, forwardRef, useImperativeHandle } from "react";
import ChartTooltip from "./ChartTooltip";
import useCandlestickChartBarSeriesData from "./candlestick-chart/useCandlestickChartBarSeriesData";
import useCandlestickChartClickSelection from "./candlestick-chart/useCandlestickChartClickSelection";
import useCandlestickChartExternalRangeSync from "./candlestick-chart/useCandlestickChartExternalRangeSync";
import useCandlestickChartLifecycle from "./candlestick-chart/useCandlestickChartLifecycle";
import useCandlestickChartMarkers from "./candlestick-chart/useCandlestickChartMarkers";
import useCandlestickChartSeriesMarkers from "./candlestick-chart/useCandlestickChartSeriesMarkers";
import useCandlestickChartSelectedMarkerFocus from "./candlestick-chart/useCandlestickChartSelectedMarkerFocus";

export type CandlestickChartVisibleRange = {
  from: number;
  to: number;
};

export type CandlestickChartVisibleRangeChangeHandler = (
  range: CandlestickChartVisibleRange | null | undefined
) => void;

export type CandlestickChartScaleMargins = {
  top?: number;
  bottom?: number;
};

export type CandlestickChartTimeScaleLike = {
  timeToCoordinate: (time: number) => number | null | undefined;
  subscribeVisibleTimeRangeChange: (cb: CandlestickChartVisibleRangeChangeHandler) => void | (() => void);
  unsubscribeVisibleTimeRangeChange?: (cb: CandlestickChartVisibleRangeChangeHandler) => void;
  getVisibleRange: () => CandlestickChartVisibleRange | null | undefined;
  setVisibleRange: (range: CandlestickChartVisibleRange) => void;
  scrollToPosition: (position: number, animated: boolean) => void;
};

export type CandlestickChartPriceScaleApplyOptions = {
  scaleMargins?: CandlestickChartScaleMargins;
  borderVisible?: boolean;
};

export type CandlestickChartPriceScaleLike = {
  options: () => { scaleMargins?: CandlestickChartScaleMargins };
  applyOptions: (options: CandlestickChartPriceScaleApplyOptions) => void;
};

export type CandlestickChartSeriesMarkerPosition = "aboveBar" | "belowBar" | "inBar";
export type CandlestickChartSeriesMarkerShape = "circle" | "square" | "arrowUp" | "arrowDown";

export type CandlestickChartSeriesMarkerLike = {
  time: number;
  position: CandlestickChartSeriesMarkerPosition;
  color: string;
  shape: CandlestickChartSeriesMarkerShape;
  text?: string;
  id?: string | number;
  size?: number;
};

export type CandlestickChartCandleSeriesLike = {
  setData: (data: CandlestickChartCandlePoint[]) => void;
  update: (data: CandlestickChartCandlePoint) => void;
  setMarkers: (markers: CandlestickChartSeriesMarkerLike[]) => void;
  priceToCoordinate?: (price: number) => number | null | undefined;
  coordinateToPrice?: (y: number) => number | null | undefined;
};

export type CandlestickChartHistogramSeriesLike = {
  setData: (data: CandlestickChartVolumePoint[]) => void;
  update: (data: CandlestickChartVolumePoint) => void;
};

type CandlestickChartApplyOptionsLike = {
  width?: number;
  height?: number;
};

type CandlestickChartCandlestickSeriesOptionsLike = {
  upColor?: string;
  downColor?: string;
  borderUpColor?: string;
  borderDownColor?: string;
  wickUpColor?: string;
  wickDownColor?: string;
};

type CandlestickChartHistogramSeriesOptionsLike = {
  color?: string;
  priceFormat?: { type?: string };
  priceScaleId?: string;
};

export type CandlestickChartApiLike = {
  timeScale: () => CandlestickChartTimeScaleLike;
  applyOptions: (options: CandlestickChartApplyOptionsLike) => void;
  remove: () => void;
  priceScale: (id: string) => CandlestickChartPriceScaleLike;
  addCandlestickSeries: (
    options: CandlestickChartCandlestickSeriesOptionsLike,
  ) => CandlestickChartCandleSeriesLike;
  addHistogramSeries: (
    options: CandlestickChartHistogramSeriesOptionsLike,
  ) => CandlestickChartHistogramSeriesLike;
  subscribeClick: (handler: CandlestickChartClickHandler) => void;
  unsubscribeClick: (handler: CandlestickChartClickHandler) => void;
};

export type CandlestickChartPriceRange = {
  top?: number;
  bottom?: number;
  from?: number;
  to?: number;
  [key: string]: unknown;
} | null;

export type CandlestickChartBar = {
  time?: number | string | null;
  open?: number | string | null;
  high?: number | string | null;
  low?: number | string | null;
  close?: number | string | null;
  volume?: number | string | null;
  __wfPlaceholder?: boolean;
  [key: string]: unknown;
};

export type CandlestickChartMarker = {
  time?: number | string | null;
  timestamp?: number | string | null;
  marker_type?: string | null;
  id?: string | number | null;
  price?: number | string | null;
  side?: string | null;
  regime?: string | null;
  strategy?: string | null;
  trade_size?: number | string | null;
  hidden_size?: number | string | null;
  total_size?: number | string | null;
  title?: string | null;
  description?: string | null;
  details?: Record<string, unknown> | null;
  __selectionSource?: string | null;
  [key: string]: unknown;
};

export type CandlestickChartHandle = {
  getChart: () => CandlestickChartApiLike | null;
  getChartContainer: () => HTMLElement | null;
};

export type CandlestickChartProps = {
  bars: CandlestickChartBar[];
  markers?: CandlestickChartMarker[];
  icebergs?: CandlestickChartMarker[];
  onMarkerClick?: (marker: CandlestickChartMarker) => void;
  onBarClick?: (bar: CandlestickChartBar) => void;
  selectedMarker?: CandlestickChartMarker | null;
  chartState?: CandlestickChartVisibleRange | null;
  onChartStateChange?: (range: CandlestickChartVisibleRange | null) => void;
  l2Data?: unknown;
  priceRange?: CandlestickChartPriceRange;
  onPriceRangeChange?: (range: CandlestickChartPriceRange) => void;
};

export type CandlestickChartTooltipState = {
  visible: boolean;
  marker: CandlestickChartMarker | null;
  x: number;
  y: number;
};

export type CandlestickChartClickPoint = { x: number; y: number };

export type CandlestickChartClickParam = {
  time?: unknown;
  point?: CandlestickChartClickPoint | null;
};

export type CandlestickChartClickHandler = (param: CandlestickChartClickParam) => void;

export type CandlestickChartCandlePoint =
  | { time: number }
  | { time: number; open: number; high: number; low: number; close: number };

export type CandlestickChartVolumePoint =
  | { time: number }
  | { time: number; value: number; color: string };

export type CandlestickChartAppliedBarsMeta = {
  length: number;
  lastTime: number | null;
};

const CandlestickChart = forwardRef<CandlestickChartHandle, CandlestickChartProps>(function CandlestickChart(
  {
    bars,
    markers,
    icebergs,
    onMarkerClick,
    onBarClick,
    selectedMarker,
    chartState,
    onChartStateChange,
    l2Data,
    priceRange,
    onPriceRangeChange,
  }: CandlestickChartProps,
  ref
) {
  const chartContainerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<CandlestickChartApiLike | null>(null);
  const candleSeriesRef = useRef<CandlestickChartCandleSeriesLike | null>(null);
  const volumeSeriesRef = useRef<CandlestickChartHistogramSeriesLike | null>(null);
  const appliedBarsMetaRef = useRef<CandlestickChartAppliedBarsMeta>({
    length: 0,
    lastTime: null,
  });
  const lastFocusedMarkerKeyRef = useRef<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Expose chart instance to parent via ref
  useImperativeHandle(ref, () => ({
    getChart: () => chartRef.current,
    getChartContainer: () => chartContainerRef.current,
  }));

  // Tooltip state
  const [tooltip, setTooltip] = useState<CandlestickChartTooltipState>({
    visible: false,
    marker: null,
    x: 0,
    y: 0
  });
  // Sync guards for external range state vs chart events.
  const isSyncingRef = useRef(false);
  const lastAppliedRangeRef = useRef<CandlestickChartVisibleRange | null>(null);
  const lastBroadcastRangeRef = useRef<CandlestickChartVisibleRange | null>(null);
  const isUserInteracting = useRef(false);
  const interactionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onChartStateChangeRef = useRef<CandlestickChartProps["onChartStateChange"]>(onChartStateChange);

  useEffect(() => {
    onChartStateChangeRef.current = onChartStateChange;
  }, [onChartStateChange]);

  useCandlestickChartLifecycle({
    chartContainerRef,
    chartRef,
    candleSeriesRef,
    volumeSeriesRef,
    appliedBarsMetaRef,
    lastAppliedRangeRef,
    lastBroadcastRangeRef,
    isSyncingRef,
    isUserInteracting,
    interactionTimeoutRef,
    onChartStateChangeRef,
    onPriceRangeChange,
    setError,
  });

  const { clickableMarkers } = useCandlestickChartMarkers({
    bars,
    markers,
    icebergs,
  });

  useCandlestickChartClickSelection({
    chartRef,
    candleSeriesRef,
    chartContainerRef,
    clickableMarkers,
    onMarkerClick,
    onBarClick,
    bars,
    setTooltip,
  });

  useCandlestickChartSeriesMarkers({
    candleSeriesRef,
    bars,
    clickableMarkers,
  });

  useCandlestickChartBarSeriesData({
    candleSeriesRef,
    volumeSeriesRef,
    appliedBarsMetaRef,
    chartRef,
    bars,
    chartState,
    setError,
  });

  useCandlestickChartSelectedMarkerFocus({
    chartRef,
    candleSeriesRef,
    chartContainerRef,
    selectedMarker,
    bars,
    lastFocusedMarkerKeyRef,
    setTooltip,
  });

  useCandlestickChartExternalRangeSync({
    chartRef,
    chartState,
    isUserInteracting,
    isSyncingRef,
    lastAppliedRangeRef,
  });

  if (error) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--accent-red)",
          flexDirection: "column",
          gap: "1rem",
        }}
      >
        <span>⚠️ Chart Error</span>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          {error}
        </span>
      </div>
    );
  }

  return (
    <>
      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
      <ChartTooltip
        marker={tooltip.marker}
        visible={tooltip.visible}
        x={tooltip.x}
        y={tooltip.y}
      />
    </>
  );
});

export default memo(CandlestickChart);
