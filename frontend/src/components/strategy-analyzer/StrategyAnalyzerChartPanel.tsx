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
  const fallbackBars = (Array.isArray(chartBars) ? chartBars : []).filter(
    (bar) => Number.isFinite(Number(bar?.time))
  ) as StrategyAnalyzerPreviewBar[];
  const selectionBars = bars.length > 0 ? bars : fallbackBars;
  const hasRenderableBars = selectionBars.length > 0;
  const renderBars = chartBars.length > 0 ? chartBars : selectionBars;

  return (
    <div className="card chart-container sa-chart-panel">
      <div className="card-header sa-chart-header">
        <span className="card-title">
          {hasRenderableBars ? `${ticker} - ${dateFrom} \u2192 ${dateTo}` : "Strategy Analyzer"}
        </span>
        <div className="chart-toolbar sa-chart-toolbar">
          {isAnalyzerAttachedRun && analyzerDisplayPhase ? (
            <span className={`phase-badge ${String(analyzerDisplayPhase || "").toLowerCase()}`}>
              {analyzerDisplayPhase}
            </span>
          ) : null}
          {selectedRangeFrom && selectedRangeTo && (
            <span className="sa-range-pill">
              {selectedRangeFrom.replace("T", " ")} &rarr; {selectedRangeTo.replace("T", " ")}
            </span>
          )}
          <button
            className={rangeSelectMode ? "btn btn-primary" : "btn btn-secondary"}
            onClick={onToggleRangeSelectMode}
            title={rangeSelectMode ? "Cancel range selection" : "Select range on chart"}
            type="button"
          >
            {rangeSelectMode ? "Cancel Selection" : "Select Range"}
          </button>
        </div>
      </div>

      <div className="sa-chart-stage">
        {hasRenderableBars ? (
          <>
            <div className="sa-chart-viewport">
              <div className="sa-chart-canvas">
                <CandlestickChart
                  ref={chartRef}
                  bars={renderBars}
                  markers={analyzerChartMarkers}
                  icebergs={[]}
                  onMarkerClick={onChartMarkerClick}
                  onBarClick={onBarClick}
                  selectedMarker={selectedMarker}
                  chartState={analyzerChartState || selectedRangeWindow || null}
                  onChartStateChange={onChartStateChange}
                />
              </div>
              <ChartRangeSelector
                enabled={rangeSelectMode}
                chartRef={chartRef}
                bars={selectionBars}
                onRangeSelected={onRangeSelected}
                onSelectionClear={onSelectionClear}
                selectedFrom={selectedRangeFrom}
                selectedTo={selectedRangeTo}
              />
            </div>
            <StrategyAnalyzerScrubSlider
              rangeScrubMeta={rangeScrubMeta}
              focusSelectedRangeOffset={focusSelectedRangeOffset}
              moveSelectedRangeByStep={moveSelectedRangeByStep}
            />
          </>
        ) : (
          <div className="sa-chart-empty">
            {loading ? "Loading bars..." : "Select a ticker and date range, then click Load Chart"}
          </div>
        )}
      </div>
    </div>
  );
}
