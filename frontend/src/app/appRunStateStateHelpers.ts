import { normalizeIsoDay } from '../utils';
import type { AnyRecord, RunDateWindow, RunKeyParts } from './appRunStateSharedTypes';

const RUN_RANGE_LABEL_PATTERN = /^(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})$/;

export const asObjectRecord = (value: unknown): AnyRecord | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as AnyRecord) : null;

export const parseRunKey = (value: unknown): RunKeyParts | null => {
  const raw = String(value || '').trim();
  if (!raw) return null;
  const parts = raw.split(':');
  if (parts.length < 3) return null;
  const date = parts.pop();
  const ticker = parts.pop();
  const runId = parts.join(':');
  if (!runId || !ticker || !date) return null;
  return { runId, ticker, date };
};

export const buildRunKeyFromState = (runStateRow: AnyRecord | null | undefined): string | null => {
  const row = asObjectRecord(runStateRow);
  if (!row) return null;
  const runId = String(row.run_id || '').trim();
  const ticker = String(row.ticker || '').trim();
  const date = String(row.date || '').trim();
  if (!runId || !ticker || !date) return null;
  return `${runId}:${ticker}:${date}`;
};

export const buildRunApiBase = (runParts: RunKeyParts | null): string | null => {
  if (!runParts) return null;
  return `/api/run/${encodeURIComponent(runParts.runId)}/${encodeURIComponent(runParts.ticker)}/${encodeURIComponent(runParts.date)}`;
};

export const resolveRunDateWindow = (stateRow: AnyRecord | null | undefined): RunDateWindow | null => {
  const row = asObjectRecord(stateRow) || {};
  const rawDate = String(row.date || '').trim();
  const rangeMatch = rawDate.match(RUN_RANGE_LABEL_PATTERN);
  const from = normalizeIsoDay(row.date_from) || normalizeIsoDay(rangeMatch?.[1]) || normalizeIsoDay(rawDate);
  let to = normalizeIsoDay(row.date_to) || normalizeIsoDay(rangeMatch?.[2]) || from;
  if (!from) return null;
  if (!to || to < from) {
    to = from;
  }
  return {
    dateFrom: from,
    dateTo: to,
    startTime: `${from}T04:00:00Z`,
    endTime: `${to}T20:00:00Z`,
  };
};

export const readErrorDetail = async (response: Response, fallback: string): Promise<string> => {
  const backup = response.clone();
  try {
    const payload = await response.json();
    if (asObjectRecord(payload)) {
      const detail = payload.detail ?? payload.error ?? payload.message;
      if (detail !== null && detail !== undefined && String(detail).trim()) {
        return String(detail);
      }
    }
  } catch (_error) {
    // Fallback to plain-text body below.
  }

  try {
    const raw = await backup.text();
    const text = String(raw || '').trim();
    if (text) return text;
  } catch (_error) {
    // Ignore and use fallback.
  }

  return String(fallback || '').trim() || 'Unknown error';
};

export const normalizeNonEmptyToken = (value: unknown): string => {
  const token = String(value ?? '').trim();
  return token || '';
};

const pickFirstNonEmptyToken = (...values: unknown[]): string => {
  for (const value of values) {
    const token = normalizeNonEmptyToken(value);
    if (token) return token;
  }
  return '';
};

const extractRunProfileMetadata = (payload: unknown) => {
  const row = asObjectRecord(payload) || {};
  const reportMeta = asObjectRecord(row.report_metadata) || {};
  const aosApplied = asObjectRecord(row.aos_applied) || {};
  const unifiedMeta = asObjectRecord(aosApplied.unified_profile) || {};
  const adaptiveMeta = asObjectRecord(aosApplied.adaptive_profile) || {};
  const comboMeta = asObjectRecord(aosApplied.strategy_combo) || {};

  return {
    unified_profile_id: pickFirstNonEmptyToken(
      reportMeta.unified_profile_id,
      row.unified_profile_id,
      unifiedMeta.active_profile_id,
      unifiedMeta.profile_id,
    ),
    unified_profile_name: pickFirstNonEmptyToken(
      reportMeta.unified_profile_name,
      row.unified_profile_name,
      unifiedMeta.profile_name,
    ),
    adaptive_profile_id: pickFirstNonEmptyToken(
      reportMeta.adaptive_profile_id,
      row.adaptive_profile_id,
      adaptiveMeta.active_profile_id,
      adaptiveMeta.profile_id,
    ),
    strategy_combo_profile_id: pickFirstNonEmptyToken(
      reportMeta.strategy_combo_profile_id,
      row.strategy_combo_profile_id,
      comboMeta.active_profile_id,
      comboMeta.profile_id,
    ),
  };
};

export const buildEffectiveExecutionConfigSnapshot = (payload: unknown): AnyRecord | null => {
  const source = asObjectRecord(payload);
  if (!source) return null;

  const executionConfigSource = asObjectRecord(source.execution_config);
  const executionConfig = executionConfigSource
    ? { ...executionConfigSource }
    : {};
  const profileMeta = extractRunProfileMetadata(payload);

  if (profileMeta.unified_profile_id && !normalizeNonEmptyToken(executionConfig.unified_profile_id)) {
    executionConfig.unified_profile_id = profileMeta.unified_profile_id;
  }
  if (
    profileMeta.unified_profile_name &&
    !normalizeNonEmptyToken(executionConfig.unified_profile_name)
  ) {
    executionConfig.unified_profile_name = profileMeta.unified_profile_name;
  }
  if (profileMeta.adaptive_profile_id && !normalizeNonEmptyToken(executionConfig.adaptive_profile_id)) {
    executionConfig.adaptive_profile_id = profileMeta.adaptive_profile_id;
  }
  if (
    profileMeta.strategy_combo_profile_id &&
    !normalizeNonEmptyToken(executionConfig.strategy_combo_profile_id)
  ) {
    executionConfig.strategy_combo_profile_id = profileMeta.strategy_combo_profile_id;
  }

  return Object.keys(executionConfig).length ? executionConfig : null;
};

export const resolveTradeModeFromExecutionConfig = (
  executionConfig: AnyRecord | null | undefined,
  fallbackMode = 'standard',
): string => {
  const fallback =
    fallbackMode === 'intrabar_5s' ||
    fallbackMode === 'intrabar_1s' ||
    fallbackMode === 'standard'
      ? fallbackMode
      : 'standard';
  const config = asObjectRecord(executionConfig);
  if (!config) return fallback;

  const explicitMode = String(config.trade_eval_mode || '')
    .trim()
    .toLowerCase();
  if (
    explicitMode === 'intrabar_5s' ||
    explicitMode === 'intrabar_1s' ||
    explicitMode === 'standard'
  ) {
    return explicitMode;
  }

  if (typeof config.intrabar_execution_recalc_1s === 'boolean') {
    if (!config.intrabar_execution_recalc_1s) return 'standard';
    const step = Number(config.intrabar_eval_step_seconds || 1);
    return Number.isFinite(step) && step >= 5 ? 'intrabar_5s' : 'intrabar_1s';
  }

  return fallback;
};
