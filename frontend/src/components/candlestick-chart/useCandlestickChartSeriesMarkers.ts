import { useEffect } from "react";
import type {
  CandlestickChartBar,
  CandlestickChartSeriesMarkerLike,
  CandlestickChartSeriesMarkerPosition,
  CandlestickChartSeriesMarkerShape,
} from "../CandlestickChart";
import { getCandlestickMarkerPalette } from "./themeUtils";
import type { CandlestickChartCandleSeriesRef } from "./types";
import type { CandlestickChartNormalizedMarker } from "./useCandlestickChartMarkers";

type Params = {
  candleSeriesRef: CandlestickChartCandleSeriesRef;
  bars: CandlestickChartBar[];
  clickableMarkers: CandlestickChartNormalizedMarker[];
  avgVolume: number;
};

export default function useCandlestickChartSeriesMarkers({
  candleSeriesRef,
  bars,
  clickableMarkers,
  avgVolume,
}: Params): void {
  useEffect(() => {
    if (!candleSeriesRef.current || !bars || bars.length === 0) return;

    try {
      const palette = getCandlestickMarkerPalette();

      const validMarkerTypes = [
        "entry_executed",
        "exit_executed",
        "stop_loss_hit",
        "take_profit_hit",
        "regime_detected",
        "strategy_selected",
        "iceberg_detected",
      ];

      const finalMarkers = clickableMarkers
        .filter((m) => m && validMarkerTypes.includes(String(m.marker_type)))
        .map<CandlestickChartSeriesMarkerLike>((m) => {
          const time = m.time;
          let position: CandlestickChartSeriesMarkerPosition = "aboveBar";
          let color = "#3b82f6";
          let shape: CandlestickChartSeriesMarkerShape = "circle";
          let text = "";

          switch (m.marker_type) {
            case "entry_executed":
              if (m.side === "long") {
                position = "belowBar"; color = palette.long; shape = "arrowUp"; text = "L";
              } else {
                position = "aboveBar"; color = palette.short; shape = "arrowDown"; text = "S";
              }
              break;
            case "exit_executed":
              position = m.side === "long" ? "aboveBar" : "belowBar";
              color = palette.neutral; shape = "circle"; text = "X";
              break;
            case "stop_loss_hit":
              position = m.side === "long" ? "belowBar" : "aboveBar";
              color = palette.short; shape = "circle"; text = "SL";
              break;
            case "take_profit_hit":
              position = m.side === "long" ? "aboveBar" : "belowBar";
              color = palette.long; shape = "circle"; text = "TP";
              break;
            case "iceberg_detected": {
              const isMega = Number(m.total_size || 0) > avgVolume * 3;
              if (m.side === "buy") {
                position = "belowBar";
                color = palette.ice_buy;
                shape = "arrowUp";
                text = isMega ? "❄️" : "▲";
              } else {
                position = "aboveBar";
                color = palette.ice_sell;
                shape = "arrowDown";
                text = isMega ? "❄️" : "▼";
              }
              break;
            }
            case "regime_detected":
              position = "aboveBar";
              color = palette.blue;
              shape = "circle";
              text = typeof m.regime === "string" ? m.regime : "R";
              break;
            case "strategy_selected":
              position = "belowBar";
              color = palette.amber;
              shape = "square";
              text =
                typeof m.strategy === "string" ? m.strategy.substring(0, 3).toUpperCase() : "S";
              break;
          }

          return {
            time,
            position,
            color,
            shape,
            text,
            id: m.id || `${m.time}-${m.marker_type}`,
            size: 2,
          };
        })
        .sort((a, b) => a.time - b.time);

      candleSeriesRef.current.setMarkers(finalMarkers);
    } catch (err: unknown) {
      console.error("Chart markers update error:", err);
    }
  }, [avgVolume, bars, candleSeriesRef, clickableMarkers]);
}
