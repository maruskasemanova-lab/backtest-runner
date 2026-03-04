import { UnifiedConfigDialog } from "../unified-config/UnifiedConfigDialog";
import DiagnosticCalendarDayDetail from "./DiagnosticCalendarDayDetail";
import DiagnosticCalendarMonthGrid from "./DiagnosticCalendarMonthGrid";
import DiagnosticCalendarToolbar from "./DiagnosticCalendarToolbar";
import useDiagnosticCalendarViewModel from "./useDiagnosticCalendarViewModel";

type DiagnosticCalendarProps = {
  onOpenInStrategyAnalyzer?: (payload: {
    ticker: string;
    isoDate: string;
    runKey?: string | null;
    runId?: string | null;
    variantKey?: string | null;
    dateFrom?: string | null;
    dateTo?: string | null;
  }) => void;
};

function DiagnosticCalendar({ onOpenInStrategyAnalyzer }: DiagnosticCalendarProps) {
  const {
    calendarModel,
    dayDetailModel,
    dialogModel,
    error,
    filterModel,
    reportPath,
    setActiveDayRunKey,
    summary,
  } = useDiagnosticCalendarViewModel();

  const {
    adaptiveProfileOptions,
    appliedFilters,
    applyDraftFilters,
    runIdOptions,
    setTradeViewMode,
    setVariantFilter,
    tradeViewMode,
    variantFilter,
  } = filterModel;
  const {
    dayProfileSummaryMap,
    dayResults,
    loading,
    maxAbsPnlPct,
    monthlyViews,
    report,
    selectedDate,
    setSelectedDate,
  } = calendarModel;
  const {
    selectedRunConfigSnapshotSections,
    selectedRunSnapshotSubtitle,
    setShowRunConfigSnapshotDialog,
    showRunConfigSnapshotDialog,
  } = dialogModel;

  return (
    <main className="diagnostic-calendar-page">
      <DiagnosticCalendarToolbar
        adaptiveProfileOptions={adaptiveProfileOptions}
        appliedFilters={appliedFilters}
        applyDraftFilters={applyDraftFilters}
        error={error}
        loading={loading}
        report={report}
        reportPath={reportPath}
        runIdOptions={runIdOptions}
        setTradeViewMode={setTradeViewMode}
        setVariantFilter={setVariantFilter}
        summary={summary}
        tradeViewMode={tradeViewMode}
        variantFilter={variantFilter}
      />

      <section className="diagnostic-calendar-layout">
        <DiagnosticCalendarMonthGrid
          dayProfileSummaryMap={dayProfileSummaryMap}
          dayResults={dayResults}
          loading={loading}
          maxAbsPnlPct={maxAbsPnlPct}
          monthlyViews={monthlyViews}
          report={report}
          selectedDate={selectedDate}
          setSelectedDate={setSelectedDate}
        />
        <DiagnosticCalendarDayDetail
          model={dayDetailModel}
          onOpenInStrategyAnalyzer={onOpenInStrategyAnalyzer}
          setActiveDayRunKey={setActiveDayRunKey}
          setShowRunConfigSnapshotDialog={setShowRunConfigSnapshotDialog}
        />
      </section>
      {showRunConfigSnapshotDialog && dayDetailModel.hasSelectedRunConfigSnapshot ? (
        <UnifiedConfigDialog
          isOpen={showRunConfigSnapshotDialog}
          onClose={() => setShowRunConfigSnapshotDialog(false)}
          readOnly
          title="Run Config Snapshot"
          subtitle={selectedRunSnapshotSubtitle}
          snapshotSections={selectedRunConfigSnapshotSections}
        />
      ) : null}
    </main>
  );
}

export default DiagnosticCalendar;
