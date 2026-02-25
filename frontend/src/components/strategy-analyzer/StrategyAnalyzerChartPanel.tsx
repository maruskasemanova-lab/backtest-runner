import type { RefObject } from "react";
import CandlestickChart from "../CandlestickChart";
import ChartRangeSelector from "./ChartRangeSelector";
import StrategyAnalyzerScrubSlider from "./StrategyAnalyzerScrubSlider";
import type {
  StrategyAnalyzerChartHandle,
  StrategyAnalyzerChartBarLike,
  StrategyAnalyzerChartMarkerClickTarget,
  StrategyAnalyzerChartWindow,
  StrategyAnalyzerDecisionMarker,
  StrategyAnalyzerPreviewBar,
  StrategyAnalyzerRangeScrubMeta,
} from "./types";

type Props = {
  bars: StrategyAnalyzerPreviewBar[];
  ticker: string;
  dateFrom: string;
  dateTo: string;
  loading: boolean;
  isAnalyzerAttachedRun: boolean;
  analyzerDisplayPhase: string | null | undefined;
  selectedRangeFrom: string | null;
  selectedRangeTo: string | null;
  rangeSelectMode: boolean;
  onToggleRangeSelectMode: () => void;
  chartRef: RefObject<StrategyAnalyzerChartHandle | null>;
  chartBars: StrategyAnalyzerChartBarLike[];
  analyzerChartMarkers: StrategyAnalyzerDecisionMarker[];
  onChartMarkerClick?: (markerOrId: StrategyAnalyzerChartMarkerClickTarget) => void;
  onBarClick: (bar: StrategyAnalyzerChartBarLike) => void;
  selectedMarker: StrategyAnalyzerDecisionMarker | null;
  analyzerChartState: StrategyAnalyzerChartWindow | null;
  selectedRangeWindow: StrategyAnalyzerChartWindow | null;
  onChartStateChange: (state: StrategyAnalyzerChartWindow | null) => void;
  onRangeSelected: (from: string, to: string) => void;
  onSelectionClear: () => void;
  rangeScrubMeta: StrategyAnalyzerRangeScrubMeta;
  focusSelectedRangeOffset: (nextOffset: number) => void;
  moveSelectedRangeByStep: (direction: -1 | 1) => void;
};

export default function StrategyAnalyzerChartPanel({
  bars,
  ticker,
  dateFrom,
  dateTo,
  loading,
  isAnalyzerAttachedRun,
  analyzerDisplayPhase,
  selectedRangeFrom,
  selectedRangeTo,
  rangeSelectMode,
  onToggleRangeSelectMode,
  chartRef,
  chartBars,
  analyzerChartMarkers,
  onChartMarkerClick,
  onBarClick,
  selectedMarker,
  analyzerChartState,
  selectedRangeWindow,
  onChartStateChange,
  onRangeSelected,
  onSelectionClear,
  rangeScrubMeta,
  focusSelectedRangeOffset,
  moveSelectedRangeByStep,
}: Props) {
  return (
    <div className="card chart-container" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
      <div className="card-header" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="card-title">
          {bars.length > 0 ? `${ticker} - ${dateFrom} \u2192 ${dateTo}` : "Strategy Analyzer"}
        </span>
        <div className="chart-toolbar" style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          {isAnalyzerAttachedRun && analyzerDisplayPhase ? (
            <span className={`phase-badge ${String(analyzerDisplayPhase || "").toLowerCase()}`}>
              {analyzerDisplayPhase}
            </span>
          ) : null}
          {selectedRangeFrom && selectedRangeTo && (
            <span
              style={{
                fontSize: "0.8rem",
                color: "var(--accent-blue)",
                fontWeight: 600,
                display: "flex",
                alignItems: "center",
              }}
            >
              {selectedRangeFrom.replace("T", " ")} &rarr; {selectedRangeTo.replace("T", " ")}
            </span>
          )}
          <button
            className={rangeSelectMode ? "btn btn-primary" : "btn btn-secondary"}
            onClick={onToggleRangeSelectMode}
            title={rangeSelectMode ? "Cancel range selection" : "Select range on chart"}
            style={{ padding: "4px 14px", fontSize: "0.8rem", fontWeight: 600 }}
          >
            {rangeSelectMode ? "Cancel Selection" : "Select Range"}
          </button>
        </div>
      </div>

      <div style={{ position: "relative", flex: 1, minHeight: 0 }}>
        {bars.length > 0 ? (
          <>
            <CandlestickChart
              ref={chartRef}
              bars={chartBars}
              markers={analyzerChartMarkers}
              icebergs={[]}
              onMarkerClick={onChartMarkerClick}
              onBarClick={onBarClick}
              selectedMarker={selectedMarker}
              chartState={analyzerChartState || selectedRangeWindow || null}
              onChartStateChange={onChartStateChange}
            />
            <ChartRangeSelector
              enabled={rangeSelectMode}
              chartRef={chartRef}
              bars={bars}
              onRangeSelected={onRangeSelected}
              onSelectionClear={onSelectionClear}
              selectedFrom={selectedRangeFrom}
              selectedTo={selectedRangeTo}
            />
          </>
        ) : (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: "var(--text-muted)",
              fontSize: "0.9rem",
            }}
          >
            {loading ? "Loading bars..." : "Select a ticker and date range, then click Load Chart"}
          </div>
        )}
      </div>

      <StrategyAnalyzerScrubSlider
        rangeScrubMeta={rangeScrubMeta}
        focusSelectedRangeOffset={focusSelectedRangeOffset}
        moveSelectedRangeByStep={moveSelectedRangeByStep}
      />
    </div>
  );
}
