import { type AuthSnapshot, isSupabaseAuthEnabled } from '../auth/supabaseAuth';
import { normalizeIsoDay } from '../utils';

export type DiagnosticAnalyzerOpenDayRequest = {
  requestId: number;
  ticker: string;
  isoDate: string;
  runKey?: string | null;
};

export type InitialAppUrlState = {
  activeView: string;
  selectedTicker: string | null;
  strategyAnalyzerOpenDayRequest: DiagnosticAnalyzerOpenDayRequest | null;
};

export {
  parseRunKey,
  buildRunKeyFromState,
  buildRunApiBase,
  resolveRunDateWindow,
  readErrorDetail,
  normalizeNonEmptyToken,
  buildEffectiveExecutionConfigSnapshot,
  resolveTradeModeFromExecutionConfig,
  toChartBar,
  extractLiveBarAnalysis,
  mergeRunStateWithStreamBar,
  upsertStreamChartBar,
  upsertDecisionMarker,
  scoreMarkerMatch,
} from './appRunStateShared';

export const RUN_ID_COLLISION_PATTERN = /Run already exists:/i;
export const VIEW_TABS = [
  { id: 'backtest', label: 'Backtest', icon: '📈' },
  { id: 'data-manager', label: 'Data Manager', icon: '💾' },
  { id: 'strategy-analyzer', label: 'Strategy Analyzer', icon: '🔬' },
  { id: 'adaptive-studio', label: 'Adaptive Studio', icon: '🧪' },
  { id: 'adaptive-tuner', label: 'Adaptive Tuner', icon: '⚙️' },
  { id: 'diagnostics', label: 'Diagnostics', icon: '🔍' },
  { id: 'live-trader', label: 'Live Trader', icon: '🔴' },
] as const;
const VIEW_TAB_IDS = new Set(VIEW_TABS.map((tab) => tab.id));
const URL_PARAM_VIEW = 'view';
const URL_PARAM_ANALYZER_TICKER = 'sa_ticker';
const URL_PARAM_ANALYZER_DAY = 'sa_day';
const URL_PARAM_ANALYZER_RUN_KEY = 'sa_run_key';

export const SIDEBAR_NAV_ITEMS = [
  { id: 'dates', label: 'Date Range', icon: '🗓', sectionId: 'run-config', runConfigMode: 'dates', focusFieldId: 'date_from', rangeLabel: 'A1' },
  { id: 'profiles', label: 'Profiles', icon: '🧩', sectionId: 'run-config', runConfigMode: 'profiles', focusFieldId: 'unified_profile_section', rangeLabel: 'A2' },
  { id: 'start-mode', label: 'Start Mode', icon: '🚀', sectionId: 'run-config', runConfigMode: 'start', focusFieldId: 'start_mode_section', rangeLabel: 'A3' },
  { id: 'strategies', label: 'Strategies', icon: '🎛', sectionId: 'strategy-settings', focusFieldId: null, rangeLabel: 'B' },
  { id: 'modules', label: 'Global Modules', icon: '🔧', sectionId: 'execution-modules', focusFieldId: null, rangeLabel: 'E' },
  { id: 'playback', label: 'Playback', icon: '▶', sectionId: 'playback-controls', focusFieldId: null, rangeLabel: 'C' },
  { id: 'summary', label: 'Summary', icon: '📊', sectionId: 'session-summary', focusFieldId: null, rangeLabel: 'D' },
] as const;
export const RUN_CONFIG_PANEL_HOST_ID =
  SIDEBAR_NAV_ITEMS.find((item) => item.sectionId === 'run-config')?.id || 'dates';
export const DEFAULT_FEATURE_FLAGS = { ads_enabled: false, ads_provider: 'none', ads_placements: [] };
export const WS_FALLBACK_NOTICE = 'WebSocket unavailable on this deployment. Using polling mode.';
export const WS_RECONNECT_BASE_MS = 800;
export const WS_RECONNECT_MAX_MS = 8000;
export const WS_CONNECT_ATTEMPTS_BEFORE_FALLBACK = 8;
export const WS_HANDSHAKE_TIMEOUT_MS = 5000;
export const ACTIVE_RUNS_POLL_BACKTEST_VISIBLE_MS = 8000;
export const ACTIVE_RUNS_POLL_OTHER_VISIBLE_MS = 30000;
export const ICEBERG_FETCH_LIMIT = 400;
export const ICEBERG_FETCH_MIN_HIDDEN_SIZE = 120;
export const ICEBERG_FETCH_MIN_TRADE_SIZE = 250;
export const ICEBERG_RENDER_LIMIT = 240;
export const EMPTY_AUTH_SNAPSHOT: AuthSnapshot = {
  enabled: isSupabaseAuthEnabled(),
  signedIn: false,
  email: null,
  userId: null,
  token: null,
};
export const SIDEBAR_WIDTH_STORAGE_KEY = 'backtest_runner.sidebar_width';
const SIDEBAR_MIN_WIDTH = 280;
const SIDEBAR_MAX_WIDTH = 760;
export const MOBILE_SIDEBAR_BREAKPOINT = 992;

export const readStoredAuthToken = (): string => {
  if (typeof window === 'undefined') return '';
  return String(
    window.localStorage.getItem('backtest_jwt') ||
      window.localStorage.getItem('supabase_jwt') ||
      '',
  ).trim();
};

const computeStableOpenDayRequestId = (ticker: string, isoDate: string, runKey = ''): number => {
  const key = `${String(ticker || '').trim().toUpperCase()}|${String(isoDate || '').trim()}|${String(runKey || '').trim()}`;
  let hash = 0;
  for (let index = 0; index < key.length; index += 1) {
    hash = (hash * 31 + key.charCodeAt(index)) | 0;
  }
  return Math.abs(hash) || 1;
};

export const readInitialAppUrlState = (): InitialAppUrlState => {
  if (typeof window === 'undefined') {
    return {
      activeView: 'backtest',
      selectedTicker: null,
      strategyAnalyzerOpenDayRequest: null,
    };
  }

  const params = new URLSearchParams(window.location.search || '');
  const rawView = String(params.get(URL_PARAM_VIEW) || '').trim();
  const activeView = VIEW_TAB_IDS.has(rawView as (typeof VIEW_TABS)[number]['id']) ? rawView : 'backtest';
  const urlTicker = String(params.get(URL_PARAM_ANALYZER_TICKER) || '').trim().toUpperCase();
  const urlDay = normalizeIsoDay(params.get(URL_PARAM_ANALYZER_DAY));
  const urlRunKey = String(params.get(URL_PARAM_ANALYZER_RUN_KEY) || '').trim();
  const hasAnalyzerTickerPreset = activeView === 'strategy-analyzer' && Boolean(urlTicker);
  const hasAnalyzerPreset = hasAnalyzerTickerPreset && Boolean(urlDay);

  return {
    activeView,
    selectedTicker: hasAnalyzerTickerPreset ? urlTicker : null,
    strategyAnalyzerOpenDayRequest: hasAnalyzerPreset
      ? {
          requestId: computeStableOpenDayRequestId(urlTicker, String(urlDay), urlRunKey),
          ticker: urlTicker,
          isoDate: String(urlDay),
          runKey: urlRunKey || null,
        }
      : null,
  };
};

export const buildStrategyAnalyzerDayUrl = (params: {
  ticker: string;
  isoDate: string;
  runKey?: string | null;
}): string => {
  if (typeof window === 'undefined') return '';
  const nextUrl = new URL(window.location.href);
  nextUrl.searchParams.set(URL_PARAM_VIEW, 'strategy-analyzer');
  nextUrl.searchParams.set(URL_PARAM_ANALYZER_TICKER, String(params.ticker || '').trim().toUpperCase());
  nextUrl.searchParams.set(URL_PARAM_ANALYZER_DAY, String(params.isoDate || '').trim());
  const runKey = String(params.runKey || '').trim();
  if (runKey) nextUrl.searchParams.set(URL_PARAM_ANALYZER_RUN_KEY, runKey);
  else nextUrl.searchParams.delete(URL_PARAM_ANALYZER_RUN_KEY);
  return nextUrl.toString();
};

export const clampSidebarWidth = (value: number): number => {
  if (!Number.isFinite(value)) return 340;
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Math.round(value)));
};

export const readInitialSidebarWidth = (): number => {
  if (typeof window === 'undefined') return 340;
  const raw = window.localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY);
  const parsed = Number(raw);
  return clampSidebarWidth(parsed);
};
