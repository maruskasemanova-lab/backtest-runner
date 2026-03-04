import type {
  DiagnosticCalendarDayResult,
  DiagnosticCalendarFilterProfileOption,
  DiagnosticCalendarReport,
  DiagnosticCalendarRun,
  DiagnosticCalendarRunIdOption,
  DiagnosticCalendarTrade,
} from "./diagnostic-calendar-schema";

export type { DiagnosticCalendarDayResult };
export type { DiagnosticCalendarFilterProfileOption };
export type { DiagnosticCalendarReport };
export type { DiagnosticCalendarRun };
export type { DiagnosticCalendarRunIdOption };
export type { DiagnosticCalendarTrade };

export type DiagnosticCalendarDraftFilters = {
  adaptiveProfileId: string;
  historyLimit: string;
  runId: string;
  ticker: string;
};

export type DiagnosticCalendarTradeViewMode = "all" | "adaptive";

export type DiagnosticCalendarHistoryFilters = {
  adaptiveProfileId: string;
  historyLimit: number;
  runId: string;
  ticker: string;
  tradeViewMode: DiagnosticCalendarTradeViewMode;
  variantFilter: string;
};

export type DiagnosticCalendarProfileOption = {
  label: string;
  profileId: string;
};

export type DiagnosticCalendarRunOption = {
  label: string;
  runId: string;
  scopeKey: string;
};

export type DiagnosticCalendarRunFilterOption = {
  label: string;
  runId: string;
};

export type DiagnosticCalendarMonthCell = {
  day: number;
  inRange: boolean;
  isoDate: string;
  result: DiagnosticCalendarDayResult | null;
};

export type DiagnosticCalendarMonthView = {
  cells: Array<DiagnosticCalendarMonthCell | null>;
  id: string;
  label: string;
};

export type DiagnosticCalendarSummary = {
  failedDays: number;
  totalDays: number;
  totalPnlDollars: number;
  totalPnlPct: number;
  totalTrades: number;
  validDays: number;
};

export type DiagnosticCalendarReportBase = {
  adaptiveProfileOptions: DiagnosticCalendarProfileOption[];
  report: DiagnosticCalendarReport;
  reportDayResults: DiagnosticCalendarDayResult[];
  runIdOptions: DiagnosticCalendarRunFilterOption[];
};

export type StrategyAnalyzerPayload = {
  isoDate: string;
  runId?: string | null;
  runKey?: string | null;
  variantKey?: string | null;
  ticker: string;
  /** Original run date-range start (from multi-day run_key). */
  dateFrom?: string | null;
  /** Original run date-range end (from multi-day run_key). */
  dateTo?: string | null;
};

export type DiagnosticCalendarSnapshotSection = {
  config: Record<string, unknown>;
  description: string;
  title: string;
};

export type DiagnosticCalendarRunProfileFields = {
  adaptiveProfile: string | null;
  strategyComboProfile: string | null;
  unifiedProfile: string | null;
};

export type DiagnosticCalendarDayMetrics = {
  barsProcessed: number | null;
  barsTotal: number | null;
  pnlDollars: number;
  pnlPct: number;
  regimeEvals: number | null;
  signals: number | null;
  trades: number;
};

export type DiagnosticCalendarRunMetrics = {
  barsProcessed: number | null;
  barsTotal: number | null;
  pnlDollars: number | null;
  pnlPct: number | null;
  regimeEvals: number | null;
  signals: number | null;
  trades: number | null;
};

export type DiagnosticCalendarProfileDaySummary = {
  profileKey: string;
  profileLabel: string;
  pnlDollars: number;
  pnlPct: number;
  runCount: number;
  totalTrades: number;
};

export type DiagnosticCalendarDayDetailModel = {
  activeDayRunKey: string;
  canOpenSelectedDayInAnalyzer: boolean;
  dayMetrics: DiagnosticCalendarDayMetrics;
  hasSelectedRunConfigSnapshot: boolean;
  runMetrics: DiagnosticCalendarRunMetrics;
  selectedDate: string | null;
  selectedDayAnalyzerPayload: StrategyAnalyzerPayload | null;
  selectedDayProfileList: string | null;
  selectedResult: DiagnosticCalendarDayResult | null;
  selectedRunOptions: DiagnosticCalendarRunOption[];
  selectedRunProfiles: DiagnosticCalendarRunProfileFields;
  selectedRunRecord: DiagnosticCalendarRun | null;
  selectedRunTradeDetails: DiagnosticCalendarTrade[];
  selectedRuns: DiagnosticCalendarRun[];
  selectedStrategyNames: string[];
};

export type DiagnosticCalendarReportView = {
  dayResultMap: Map<string, DiagnosticCalendarDayResult>;
  dayProfileSummaryMap: Map<string, DiagnosticCalendarProfileDaySummary[]>;
  dayResults: DiagnosticCalendarDayResult[];
  maxAbsPnlPct: number;
  monthlyViews: DiagnosticCalendarMonthView[];
  summary: DiagnosticCalendarSummary;
};

export type DiagnosticCalendarDayDetailState = {
  dayDetailModel: DiagnosticCalendarDayDetailModel;
  selectedRunConfigSnapshotSections: DiagnosticCalendarSnapshotSection[];
  selectedRunSnapshotSubtitle: string;
};
