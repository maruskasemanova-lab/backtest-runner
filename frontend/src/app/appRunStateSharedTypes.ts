export type AnyRecord = Record<string, any>;

export type RunKeyParts = {
  runId: string;
  ticker: string;
  date: string;
};

export type RunDateWindow = {
  dateFrom: string;
  dateTo: string;
  startTime: string;
  endTime: string;
};

export type BarAnalysisArtifacts = {
  nestedAnalysis: AnyRecord | null;
  layerScores: AnyRecord | null;
  signalRejected: AnyRecord | null;
  candidateDiagnostics: AnyRecord | null;
  intrabarEvalTrace: AnyRecord | null;
  intradayLevelsSnapshot: AnyRecord | null;
  levelContextSnapshot: AnyRecord | null;
  entryQualityDiagnosticsSnapshot: AnyRecord | null;
  tcbboConfirmationSnapshot: AnyRecord | null;
  intrabarConfirmationSnapshot: AnyRecord | null;
  microConfirmationSnapshot: AnyRecord | null;
  contextRiskSnapshot: AnyRecord | null;
  latestCheckpoint: AnyRecord | null;
  resolvedWarmupOnly: boolean | undefined;
  resolvedBarIndex: number | undefined;
  shouldAttachAnalysisPayload: boolean;
};
