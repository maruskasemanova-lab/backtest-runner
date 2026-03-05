import type { RefObject } from "react";
import CandlestickChart from "../CandlestickChart";
import ChartRangeSelector from "./ChartRangeSelector";
import StrategyAnalyzerScrubSlider from "./StrategyAnalyzerScrubSlider";
import type {
  StrategyAnalyzerChartBarLike,
  StrategyAnalyzerChartHandle,
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

function formatRangeLabel(from: string | null, to: string | null): string {
  if (!from || !to) return "Replay window not locked";
  return `${from.replace("T", " ")} -> ${to.replace("T", " ")}`;
}

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
    (bar) => Number.isFinite(Number(bar?.time)),
  ) as StrategyAnalyzerPreviewBar[];
  const selectionBars = bars.length > 0 ? bars : fallbackBars;
  const hasRenderableBars = selectionBars.length > 0;
  const renderBars = chartBars.length > 0 ? chartBars : selectionBars;
  const selectedRangeReady = Boolean(selectedRangeFrom && selectedRangeTo);

  return (
    <div className="card chart-container sa-chart-panel">
      <div className="card-header sa-chart-header">
        <div className="sa-chart-heading">
          <div className="sa-section-kicker">Replay Canvas</div>
          <span className="card-title">
            {hasRenderableBars ? `${ticker} | ${dateFrom} -> ${dateTo}` : "Strategy Analyzer"}
          </span>
          <div className="sa-chart-meta">
            <span className="sa-meta-pill">{hasRenderableBars ? `${selectionBars.length.toLocaleString()} preview bars` : "Load market tape"}</span>
            <span className={`sa-state-pill ${selectedRangeReady ? "is-ready" : "is-idle"}`}>
              {selectedRangeReady ? "Window selected" : "Window pending"}
            </span>
            {isAnalyzerAttachedRun && analyzerDisplayPhase ? (
              <span className={`phase-badge ${String(analyzerDisplayPhase || "").toLowerCase()}`}>
                {analyzerDisplayPhase}
              </span>
            ) : null}
          </div>
        </div>

        <div className="chart-toolbar sa-chart-toolbar">
          <span className="sa-range-pill">{formatRangeLabel(selectedRangeFrom, selectedRangeTo)}</span>
          <button
            className={rangeSelectMode ? "btn btn-primary" : "btn btn-secondary"}
            onClick={onToggleRangeSelectMode}
            title={rangeSelectMode ? "Cancel range selection" : "Select range on chart"}
            type="button"
          >
            {rangeSelectMode ? "Cancel range pick" : "Pick range on chart"}
          </button>
        </div>
      </div>

      <div className="sa-chart-stage">
        {hasRenderableBars ? (
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
        ) : (
          <div className="sa-chart-empty">
            <div className="sa-chart-empty__panel">
              <div className="sa-section-kicker">Trader Workflow</div>
              <h3 className="sa-chart-empty__title">Load a market tape first</h3>
              <p className="sa-chart-empty__copy">
                Pick the symbol and day span from the right rail, then draw a precise replay window on the chart before you start tweaking entries.
              </p>
              <div className="sa-empty-step-grid">
                <div className="sa-empty-step">
                  <span className="sa-empty-step__index">01</span>
                  <span className="sa-empty-step__copy">Load the exact session you want to inspect.</span>
                </div>
                <div className="sa-empty-step">
                  <span className="sa-empty-step__index">02</span>
                  <span className="sa-empty-step__copy">Mark the regime leg or failed sequence you want to replay.</span>
                </div>
                <div className="sa-empty-step">
                  <span className="sa-empty-step__index">03</span>
                  <span className="sa-empty-step__copy">Run replay, pause, tweak gates and inspect each decision path.</span>
                </div>
              </div>
            </div>
            <div className="sa-chart-empty__status">
              {loading ? "Loading bars..." : "Select a ticker and date range, then click Load market tape."}
            </div>
          </div>
        )}
      </div>

      {hasRenderableBars ? (
        <div className="sa-chart-footer">
          {isAnalyzerAttachedRun ? (
            <StrategyAnalyzerScrubSlider
              rangeScrubMeta={rangeScrubMeta}
              focusSelectedRangeOffset={focusSelectedRangeOffset}
              moveSelectedRangeByStep={moveSelectedRangeByStep}
            />
          ) : (
            <div className="sa-chart-footer-note">
              {selectedRangeReady
                ? "Replay window locked. Start the replay from the action rail to activate scrub + live decision diagnostics."
                : "Use the chart picker or manual timestamps to lock a replay window before you start."}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
