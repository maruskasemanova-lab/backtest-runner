export type ObjectRecord = Record<string, unknown>;
export type MaybeObjectRecord = ObjectRecord | null | undefined;

export type ResolutionCandidate = {
  path: string;
  value: unknown;
};

export type BaseResolutionParams = {
  details: MaybeObjectRecord;
  signalMetadata: MaybeObjectRecord;
  marketContext: MaybeObjectRecord;
};

export type ContextRiskResolutionParams = BaseResolutionParams & {
  riskControls: MaybeObjectRecord;
};

export type ResolutionResult = {
  value: ObjectRecord | null;
  sourcePath: string;
  candidates: ResolutionCandidate[];
};

export type L2SourceCandidate = {
  sourcePath: string;
  source: ObjectRecord;
};

export type L2CandidateDiagnostic = {
  sourcePath: string;
  score: number;
  availableMetrics: string[];
};

export type L2SourceResolution = {
  source: ObjectRecord | null;
  sourcePath: string;
  candidateDiagnostics: L2CandidateDiagnostic[];
};

export type L2DiagnosticsExtractResult = {
  hasAny: boolean;
  flowScore: number | null;
  signedAggression: number | null;
  l2AggressionZ: number | null;
  l2BookPressureZ: number | null;
  absorptionRate: number | null;
  largeTraderActivity: number | null;
  vwapExecutionFlow: number | null;
  sweepDetected: boolean | null;
  sourcePath: string;
  candidateDiagnostics: L2CandidateDiagnostic[];
};

export type IntradayLevelsExtractResult = {
  hasAny: boolean;
  enabled: boolean;
  stats: ObjectRecord;
  volumeProfile: ObjectRecord;
  latestEvent: ObjectRecord | null;
};

export type LevelContextExtractResult = {
  hasAny: boolean;
  payload: ObjectRecord;
  checks: ObjectRecord;
  reasons: string[];
};

export type EntryQualityDiagnosticsExtractResult = {
  hasAny: boolean;
  payload: ObjectRecord;
  tags: string[];
};

export type DecisionLogPayloadExtractResult = {
  hasAny: boolean;
  payload: ObjectRecord;
};
