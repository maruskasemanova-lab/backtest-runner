import { useQuery } from '@tanstack/react-query';

type AnyRecord = Record<string, any>;

type ActiveRunsQueryOptions = {
  enabled: boolean;
  refetchIntervalMs: number | false;
  toRunKey: (row: AnyRecord | null | undefined) => string | null;
};

type UsageSnapshotQueryOptions = {
  enabled: boolean;
  token: string;
  defaultFeatureFlags: AnyRecord;
};

type RunDateWindow = {
  dateFrom: string;
  dateTo: string;
  startTime: string;
  endTime: string;
};

type L2FootprintQueryOptions = {
  enabled: boolean;
  ticker: string;
  timeframe: string;
  dateWindow: RunDateWindow | null;
};

type IcebergsQueryOptions = {
  enabled: boolean;
  ticker: string;
  dateWindow: RunDateWindow | null;
  fetchLimit: number;
  minHiddenSize: number;
  minTradeSize: number;
};

const normalizeToken = (value: unknown): string => String(value ?? '').trim();

export const useActiveRunsQuery = ({
  enabled,
  refetchIntervalMs,
  toRunKey,
}: ActiveRunsQueryOptions) =>
  useQuery({
    queryKey: ['app', 'active-runs'],
    enabled,
    refetchInterval: enabled ? refetchIntervalMs : false,
    queryFn: async () => {
      const response = await fetch('/api/runs');
      if (!response.ok) return [];
      const payload = await response.json();
      const rows = Array.isArray(payload) ? payload : [];
      return rows
        .map((row) => {
          const key = toRunKey(row);
          if (!key) return null;
          return {
            ...row,
            run_key: key,
          };
        })
        .filter(Boolean);
    },
  });

export const useUsageSnapshotQuery = ({
  enabled,
  token,
  defaultFeatureFlags,
}: UsageSnapshotQueryOptions) => {
  const normalizedToken = normalizeToken(token);
  return useQuery({
    queryKey: ['app', 'usage-snapshot', normalizedToken],
    enabled: enabled && Boolean(normalizedToken),
    refetchInterval: enabled ? 20_000 : false,
    queryFn: async () => {
      const response = await fetch('/api/v2/usage', {
        headers: {
          Authorization: `Bearer ${normalizedToken}`,
        },
      });
      if (!response.ok) {
        throw new Error(`usage_http_${response.status}`);
      }
      const payload = await response.json();
      const row = payload && typeof payload === 'object' ? payload : {};
      return {
        planTier: row.plan_tier || null,
        quotaSnapshot: row.quota_snapshot || null,
        featureFlags:
          row.feature_flags && typeof row.feature_flags === 'object'
            ? row.feature_flags
            : defaultFeatureFlags,
      };
    },
  });
};

export const useL2FootprintQuery = ({
  enabled,
  ticker,
  timeframe,
  dateWindow,
}: L2FootprintQueryOptions) =>
  useQuery({
    queryKey: [
      'app',
      'l2-footprint',
      ticker,
      timeframe,
      dateWindow?.startTime || '',
      dateWindow?.endTime || '',
    ],
    enabled: enabled && Boolean(ticker) && Boolean(dateWindow),
    queryFn: async ({ signal }) => {
      if (!dateWindow) return null;
      const params = new URLSearchParams({
        start_time: dateWindow.startTime,
        end_time: dateWindow.endTime,
        timeframe,
      });
      const response = await fetch(`/api/l2/footprint/${ticker}?${params.toString()}`, { signal });
      if (!response.ok) {
        throw new Error(`l2_footprint_http_${response.status}`);
      }
      const payload = await response.json();
      return {
        ...payload,
        date_from: dateWindow.dateFrom,
        date_to: dateWindow.dateTo,
        timeframe,
      };
    },
    staleTime: 20_000,
  });

export const useIcebergsQuery = ({
  enabled,
  ticker,
  dateWindow,
  fetchLimit,
  minHiddenSize,
  minTradeSize,
}: IcebergsQueryOptions) =>
  useQuery({
    queryKey: [
      'app',
      'icebergs',
      ticker,
      dateWindow?.startTime || '',
      dateWindow?.endTime || '',
      fetchLimit,
      minHiddenSize,
      minTradeSize,
    ],
    enabled: enabled && Boolean(ticker) && Boolean(dateWindow),
    queryFn: async ({ signal }) => {
      if (!dateWindow) return [];
      const params = new URLSearchParams({
        start_time: dateWindow.startTime,
        end_time: dateWindow.endTime,
        limit: String(fetchLimit),
        min_hidden_size: String(minHiddenSize),
        min_trade_size: String(minTradeSize),
        sort: 'hidden_size',
      });
      const response = await fetch(`/api/l2/icebergs/${ticker}?${params.toString()}`, {
        signal,
      });
      if (!response.ok) {
        throw new Error(`icebergs_http_${response.status}`);
      }
      const payload = await response.json();
      return Array.isArray(payload) ? payload : [];
    },
    staleTime: 60_000,
  });
