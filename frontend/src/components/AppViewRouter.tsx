import { memo } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { IntradayLevelsDialogSelection } from '../intradayLevelsUtils';
import CandlestickChart, {
  type CandlestickChartBar,
  type CandlestickChartPriceRange,
  type CandlestickChartVisibleRange,
} from './CandlestickChart';
import FootprintChart from './FootprintChart';
import DecisionPanel from './decision-panel/DecisionPanel';
import DataManager from './DataManager';
import IntrabarPanel from './IntrabarPanel';
import IntradayLevelsDialog from './IntradayLevelsDialog';
import AdaptiveStrategyStudio from './AdaptiveStrategyStudio';
import AdaptiveTuner from './AdaptiveTuner';
import LiveTraderMonitor from './LiveTraderMonitor';
import DiagnosticCalendar from './diagnostic-calendar/DiagnosticCalendar';
import StrategyAnalyzer from './strategy-analyzer/StrategyAnalyzer';
import type {
  StrategyAnalyzerConditionsLiveAnalysis,
  StrategyAnalyzerDecisionMarker,
  StrategyAnalyzerOnEvaluateIntrabarSlice,
} from './strategy-analyzer/types';

type MarkerVisibility = {
  entries: boolean;
  exits: boolean;
  regime: boolean;
  strategy: boolean;
  icebergs: boolean;
};

type AnalyzerOpenDayRequest = {
  requestId: number;
  ticker: string;
  isoDate: string;
  runKey?: string | null;
  variantKey?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
} | null;

type ActiveRun = {
  runId: string;
  ticker: string;
  date: string;
} | null;

type AppViewRouterProps = {
  activeView: string;
  downloadProgress: any;
  selectedTicker: string | null;
  setSelectedTicker: Dispatch<SetStateAction<string | null>>;
  strategyApiUrl: string;
  authToken: string;
  handleStartRun: (config: any) => Promise<any>;
  handlePlay: (options?: any) => Promise<any> | void;
  handlePause: () => Promise<any> | void;
  handleStep: (options?: any) => Promise<any> | void;
  handleEvaluateIntrabarSlice: StrategyAnalyzerOnEvaluateIntrabarSlice;
  handleReset: () => Promise<any> | void;
  isPlaying: boolean;
  runKey: string | null;
  runState: any;
  bars: CandlestickChartBar[];
  decisionEvents: StrategyAnalyzerDecisionMarker[];
  selectedMarker: StrategyAnalyzerDecisionMarker | null;
  latestBarAnalysis: StrategyAnalyzerConditionsLiveAnalysis;
  setSelectedMarker: Dispatch<SetStateAction<StrategyAnalyzerDecisionMarker | null>>;
  handleMarkerClick: (markerOrId: any) => void;
  setActiveView: Dispatch<SetStateAction<string>>;
  handleOpenStoredRunSnapshot: (targetRunKey: string) => Promise<boolean>;
  diagnosticAnalyzerOpenDayRequest: AnalyzerOpenDayRequest;
  handleStrategyAnalyzerOpenDayRequestHandled: (requestId: number) => void;
  handleOpenDiagnosticDayInAnalyzer: (params: {
    ticker: string;
    isoDate: string;
    runKey?: string | null;
    variantKey?: string | null;
    dateFrom?: string | null;
    dateTo?: string | null;
  }) => void;
  timeframe: string;
  setTimeframe: Dispatch<SetStateAction<string>>;
  markerVisibility: MarkerVisibility;
  toggleMarkerVisibility: (key: keyof MarkerVisibility) => void;
  activeTab: string;
  setActiveTab: Dispatch<SetStateAction<string>>;
  displayedBars: CandlestickChartBar[];
  filteredMarkers: StrategyAnalyzerDecisionMarker[];
  filteredIcebergs: any[];
  chartState: CandlestickChartVisibleRange | null;
  handleChartStateChange: (range: CandlestickChartVisibleRange | null | undefined) => void;
  priceRange: CandlestickChartPriceRange;
  setPriceRange: Dispatch<SetStateAction<CandlestickChartPriceRange>>;
  l2Data: any;
  handleBarClick: (bar: CandlestickChartBar | null | undefined) => void;
  currentBar: any;
  selectedIntrabar: CandlestickChartBar | null;
  activeRun: ActiveRun;
  setSelectedIntrabar: Dispatch<SetStateAction<any>>;
  selectedIntradayLevels: IntradayLevelsDialogSelection | null;
  closeIntradayLevelsDialog: () => void;
};

// Extracted into a named function for easier debugging and memoization wrapper below.
function AppViewRouterRender({
  activeView,
  downloadProgress,
  selectedTicker,
  setSelectedTicker,
  strategyApiUrl,
  authToken,
  handleStartRun,
  handlePlay,
  handlePause,
  handleStep,
  handleEvaluateIntrabarSlice,
  handleReset,
  isPlaying,
  runKey,
  runState,
  bars,
  decisionEvents,
  selectedMarker,
  latestBarAnalysis,
  setSelectedMarker,
  handleMarkerClick,
  setActiveView,
  handleOpenStoredRunSnapshot,
  diagnosticAnalyzerOpenDayRequest,
  handleStrategyAnalyzerOpenDayRequestHandled,
  handleOpenDiagnosticDayInAnalyzer,
  timeframe,
  setTimeframe,
  markerVisibility,
  toggleMarkerVisibility,
  activeTab,
  setActiveTab,
  displayedBars,
  filteredMarkers,
  filteredIcebergs,
  chartState,
  handleChartStateChange,
  priceRange,
  setPriceRange,
  l2Data,
  handleBarClick,
  currentBar,
  selectedIntrabar,
  activeRun,
  setSelectedIntrabar,
  selectedIntradayLevels,
  closeIntradayLevelsDialog,
}: AppViewRouterProps) {
  const appViewClassName =
    activeView === 'strategy-analyzer'
      ? 'app-view app-view-strategy-analyzer'
      : 'app-view';

  return (
    <div className={appViewClassName}>
      {activeView === 'data-manager' ? (
        <DataManager downloadProgress={downloadProgress} />
      ) : activeView === 'strategy-analyzer' ? (
        <StrategyAnalyzer
          selectedTicker={selectedTicker}
          onTickerChange={setSelectedTicker}
          strategyApiUrl={strategyApiUrl}
          onStartRun={handleStartRun}
          onPlayRun={handlePlay}
          onPauseRun={handlePause}
          onStepRun={handleStep}
          onEvaluateIntrabarSlice={handleEvaluateIntrabarSlice}
          onClearRun={handleReset}
          isPlayingRun={isPlaying}
          attachedRunKey={runKey}
          attachedRunState={runState}
          attachedRunBars={bars}
          decisionEvents={decisionEvents}
          selectedMarker={selectedMarker}
          latestBarAnalysis={latestBarAnalysis}
          onDecisionSelectMarker={setSelectedMarker}
          onChartMarkerClick={handleMarkerClick}
          onSwitchToBacktest={() => setActiveView('backtest')}
          onOpenStoredRunSnapshot={handleOpenStoredRunSnapshot}
          openDayRequest={diagnosticAnalyzerOpenDayRequest}
          onOpenDayRequestHandled={handleStrategyAnalyzerOpenDayRequestHandled}
        />
      ) : activeView === 'adaptive-studio' ? (
        <AdaptiveStrategyStudio
          selectedTicker={selectedTicker}
          onTickerChange={setSelectedTicker}
          strategyApiUrl={strategyApiUrl}
          authToken={authToken}
        />
      ) : activeView === 'adaptive-tuner' ? (
        <AdaptiveTuner
          selectedTicker={selectedTicker}
          onTickerChange={setSelectedTicker}
          strategyApiUrl={strategyApiUrl}
        />
      ) : activeView === 'diagnostics' ? (
        <DiagnosticCalendar onOpenInStrategyAnalyzer={handleOpenDiagnosticDayInAnalyzer} />
      ) : activeView === 'live-trader' ? (
        <LiveTraderMonitor />
      ) : (
        <main className="app-content">
          <section className="card chart-container">
            <div className="card-header">
              <span className="card-title">
                {runState
                  ? `${runState.ticker} - ${
                      runState.date_from && runState.date_to
                        ? `${runState.date_from} → ${runState.date_to}`
                        : runState.date
                    }`
                  : 'Price Chart'}
              </span>
              {runState && (
                <span className={`phase-badge ${runState.phase?.toLowerCase()}`}>
                  {runState.phase}
                </span>
              )}
              <div className="chart-toolbar">
                <select
                  className="chart-timeframe"
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                >
                  <option value="1min">1 Min</option>
                  <option value="5min">5 Min</option>
                  <option value="15min">15 Min</option>
                  <option value="30min">30 Min</option>
                  <option value="1h">1 Hour</option>
                </select>

                <div className="marker-toggles">
                  <button
                    className={`toggle-btn ${markerVisibility.entries ? 'active' : ''}`}
                    onClick={() => toggleMarkerVisibility('entries')}
                    title="Toggle Entry Markers"
                  >
                    E
                  </button>
                  <button
                    className={`toggle-btn ${markerVisibility.exits ? 'active' : ''}`}
                    onClick={() => toggleMarkerVisibility('exits')}
                    title="Toggle Exit/SL/TP Markers"
                  >
                    X
                  </button>
                  <button
                    className={`toggle-btn ${markerVisibility.icebergs ? 'active' : ''}`}
                    onClick={() => toggleMarkerVisibility('icebergs')}
                    title="Toggle Iceberg Markers"
                  >
                    ❄️
                  </button>
                  <button
                    className={`toggle-btn ${markerVisibility.regime ? 'active' : ''}`}
                    onClick={() => toggleMarkerVisibility('regime')}
                    title="Toggle Regime Markers"
                  >
                    R
                  </button>
                  <button
                    className={`toggle-btn ${markerVisibility.strategy ? 'active' : ''}`}
                    onClick={() => toggleMarkerVisibility('strategy')}
                    title="Toggle Strategy Markers"
                  >
                    S
                  </button>
                </div>

                <button
                  className={`chart-tab ${activeTab === 'standard' ? 'active' : ''}`}
                  onClick={() => setActiveTab('standard')}
                >
                  Candles
                </button>
                <button
                  className={`chart-tab ${activeTab === 'l2' ? 'active' : ''}`}
                  onClick={() => setActiveTab('l2')}
                >
                  L2 Footprint
                </button>
              </div>
            </div>
            <div className="chart-wrapper">
              {activeTab === 'standard' ? (
                <CandlestickChart
                  bars={displayedBars}
                  markers={filteredMarkers}
                  icebergs={filteredIcebergs}
                  onMarkerClick={handleMarkerClick}
                  onBarClick={handleBarClick}
                  selectedMarker={selectedMarker}
                  chartState={chartState}
                  onChartStateChange={handleChartStateChange}
                  priceRange={priceRange}
                  onPriceRangeChange={setPriceRange}
                  l2Data={l2Data}
                />
              ) : (
                <FootprintChart
                  bars={displayedBars}
                  markers={filteredMarkers}
                  icebergs={filteredIcebergs}
                  onMarkerClick={handleMarkerClick}
                  selectedMarker={selectedMarker}
                  l2Data={l2Data}
                  chartState={chartState}
                  onChartStateChange={handleChartStateChange}
                  priceRange={priceRange}
                  onPriceRangeChange={setPriceRange}
                />
              )}
            </div>
            {currentBar && (
              <div className="current-bar-info">
                <div className="bar-stat">
                  <div className="bar-stat-value">${currentBar.open?.toFixed(2)}</div>
                  <div className="bar-stat-label">Open</div>
                </div>
                <div className="bar-stat">
                  <div className="bar-stat-value up">${currentBar.high?.toFixed(2)}</div>
                  <div className="bar-stat-label">High</div>
                </div>
                <div className="bar-stat">
                  <div className="bar-stat-value down">${currentBar.low?.toFixed(2)}</div>
                  <div className="bar-stat-label">Low</div>
                </div>
                <div className="bar-stat">
                  <div
                    className={`bar-stat-value ${currentBar.close >= currentBar.open ? 'up' : 'down'}`}
                  >
                    ${currentBar.close?.toFixed(2)}
                  </div>
                  <div className="bar-stat-label">Close</div>
                </div>
              </div>
            )}
            {selectedIntrabar && activeRun && (
              <IntrabarPanel
                runId={activeRun.runId}
                ticker={activeRun.ticker}
                date={activeRun.date}
                selectedBar={selectedIntrabar}
                onClose={() => setSelectedIntrabar(null)}
              />
            )}
            {selectedIntradayLevels && (
              <IntradayLevelsDialog
                bar={selectedIntradayLevels.bar}
                payload={selectedIntradayLevels.payload}
                sourcePath={selectedIntradayLevels.sourcePath}
                sourceMarker={selectedIntradayLevels.sourceMarker}
                relatedMarkers={selectedIntradayLevels.relatedMarkers}
                timeframeSeconds={selectedIntradayLevels.timeframeSeconds}
                onClose={closeIntradayLevelsDialog}
              />
            )}
          </section>

          <aside className="card decision-panel">
            <div className="card-header">
              <span className="card-title">Decisions</span>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                {decisionEvents.length} total
              </span>
            </div>
            <div className="card-body">
              <DecisionPanel
                markers={decisionEvents}
                selectedMarker={selectedMarker}
                onSelectMarker={setSelectedMarker}
              />
            </div>
          </aside>
        </main>
      )}
    </div>
  );
}

export default memo(AppViewRouterRender);
