/**
 * Shared utility functions for the Backtest Runner frontend.
 *
 * Consolidates helpers that were previously duplicated across
 * App.tsx, RunConfig.tsx, AOSOptimizations.tsx, DecisionPanel.tsx,
 * CandlestickChart.tsx, FootprintChart.tsx, AdaptiveTuner.tsx,
 * StrategySettings.tsx, and AdaptiveStrategyStudio.tsx.
 */

// ─── Number helpers ───────────────────────────────────────────────

export const toFiniteNumber = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const clamp = (value, fallback, min, max) =>
  Math.max(min, Math.min(max, toFiniteNumber(value, fallback)));

export const clampInt = (value, fallback, min, max) =>
  Math.max(min, Math.min(max, Math.trunc(toFiniteNumber(value, fallback))));

// ─── Timestamp helpers ────────────────────────────────────────────

const normalizeEpochSeconds = (value) => {
  if (!Number.isFinite(value)) return null;
  // Backends may emit epoch in ms/us/ns. Normalize down to seconds.
  let normalized = Number(value);
  let divisions = 0;
  while (Math.abs(normalized) >= 1e11 && divisions < 4) {
    normalized /= 1000;
    divisions += 1;
  }
  return normalized;
};

const parseIsoTimestampToSeconds = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return null;
  const normalized = raw.replace(/(\.\d{3})\d+/, "$1");
  // Backend often returns ISO timestamps without timezone suffix.
  // Treat those as UTC to avoid local-time drift (e.g., +01:00 => -1h range end).
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized);
  const isoLike = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(normalized);
  const parseTarget = !hasTimezone && isoLike ? `${normalized}Z` : normalized;
  const parsed = Date.parse(parseTarget);
  return Number.isNaN(parsed) ? null : parsed / 1000;
};

export const toUnixSeconds = (value) => {
  if (value === null || value === undefined) return null;
  if (typeof value === "number" && Number.isFinite(value)) {
    return normalizeEpochSeconds(value);
  }
  if (typeof value === "string") {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) {
      return normalizeEpochSeconds(numeric);
    }
    const parsedIsoSeconds = parseIsoTimestampToSeconds(value);
    if (Number.isFinite(parsedIsoSeconds)) return parsedIsoSeconds;
  }
  if (typeof value === "object" && value !== null) {
    if (value.timestamp !== undefined) return toUnixSeconds(value.timestamp);
    if (value.time !== undefined) return toUnixSeconds(value.time);
    if (
      Number.isFinite(value.year) &&
      Number.isFinite(value.month) &&
      Number.isFinite(value.day)
    ) {
      return Date.UTC(value.year, value.month - 1, value.day) / 1000;
    }
  }
  return null;
};

export const toIsoTimestamp = (value) => {
  const seconds = toUnixSeconds(value);
  if (!Number.isFinite(seconds)) return null;
  return new Date(seconds * 1000).toISOString();
};

export const formatTimestamp = (value) => {
  if (!value) return "-";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return String(value);
  return new Date(parsed).toLocaleString();
};

// ─── String / text helpers ────────────────────────────────────────

export const normalizeText = (value) => {
  if (value === null || value === undefined) return "";
  return String(value).trim().toLowerCase();
};

// ─── Date helpers ─────────────────────────────────────────────────

export const normalizeIsoDay = (value) => {
  const text = String(value || "").trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text : "";
};

// ─── Boolean helpers ──────────────────────────────────────────────

export const toBool = (value, fallback) => {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "y", "on"].includes(normalized)) return true;
    if (["0", "false", "no", "n", "off"].includes(normalized)) return false;
  }
  return fallback;
};

// ─── CSV / token helpers ──────────────────────────────────────────

export const parseCsvTokens = (value, normalizeToken) => {
  const tokens = String(value || "").split(",");
  const seen = new Set();
  const normalized = [];
  tokens.forEach((token) => {
    const raw = String(token || "").trim();
    if (!raw) return;
    const next =
      typeof normalizeToken === "function" ? normalizeToken(raw) : raw;
    if (!next || seen.has(next)) return;
    seen.add(next);
    normalized.push(next);
  });
  return normalized;
};

export const toCsvString = (value, normalizeToken) =>
  parseCsvTokens(
    Array.isArray(value) ? value.join(",") : value,
    normalizeToken,
  ).join(",");

// ─── Sleeve / config helpers ──────────────────────────────────────

export const normalizeSleeveId = (value, fallback = "sleeve_1") => {
  const raw = String(value || "")
    .trim()
    .toLowerCase();
  const cleaned = raw
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned || fallback;
};

// ─── Deployment/runtime URL helpers ──────────────────────────────

const trimTrailingSlashes = (value: string) => String(value || "").trim().replace(/\/+$/, "");

const rewriteDockerAliasForBrowser = (value: string) => {
  const raw = trimTrailingSlashes(value);
  if (!raw) return raw;
  if (typeof window === "undefined") return raw;

  try {
    const parsed = new URL(raw);
    const alias = String(parsed.hostname || "").trim().toLowerCase();
    if (!["strategy-api", "runner-api"].includes(alias)) {
      return raw;
    }

    const browserHost = String(window.location.hostname || "").trim().toLowerCase();
    if (!["localhost", "127.0.0.1"].includes(browserHost)) {
      return raw;
    }

    parsed.hostname = browserHost;
    return trimTrailingSlashes(parsed.toString());
  } catch (_err) {
    return raw;
  }
};

const isLocalBrowserHost = () => {
  if (typeof window === "undefined") return false;
  const host = String(window.location.hostname || "").trim().toLowerCase();
  return host === "localhost" || host === "127.0.0.1";
};

export const defaultStrategyApiUrl = (() => {
  const configured = rewriteDockerAliasForBrowser(import.meta.env.VITE_STRATEGY_API_URL || "");
  if (configured) return configured;
  return isLocalBrowserHost() ? "http://localhost:8001" : "";
})();

const defaultLocalRunnerApiBaseUrl = (() => {
  if (typeof window === "undefined") return "";
  if (!isLocalBrowserHost()) return "";
  const protocol = window.location.protocol === "https:" ? "https:" : "http:";
  const hostname = String(window.location.hostname || "").trim().toLowerCase();
  if (!hostname) return "";
  return `${protocol}//${hostname}:8002`;
})();

export const defaultRunnerApiBaseUrl = (() => {
  const configured = rewriteDockerAliasForBrowser(import.meta.env.VITE_API_BASE_URL || "");
  if (configured) return configured;
  return rewriteDockerAliasForBrowser(defaultLocalRunnerApiBaseUrl);
})();

const _isServerlessLikeHost = (value: string) => {
  if (!value) return false;
  try {
    const parsed = new URL(value);
    const host = String(parsed.hostname || "").trim().toLowerCase();
    return (
      host.endsWith(".vercel.app") ||
      host.includes("amazonaws.com") ||
      host.includes("lambda")
    );
  } catch (_err) {
    return false;
  }
};

export const defaultPlaybackApiBaseUrl = (() => {
  const configured = rewriteDockerAliasForBrowser(
    import.meta.env.VITE_PLAYBACK_API_BASE_URL || "",
  );
  if (configured) return configured;
  if (defaultRunnerApiBaseUrl && !_isServerlessLikeHost(defaultRunnerApiBaseUrl)) {
    return rewriteDockerAliasForBrowser(defaultRunnerApiBaseUrl);
  }
  return "";
})();

const STATEFUL_RUN_API_PREFIXES = ["/api/run", "/api/runs"];
const WS_LIVE_PATH = "/ws/live";

const buildWsLiveUrlFromHttpBase = (base: string) => {
  const normalized = trimTrailingSlashes(base);
  if (!normalized) return "";
  try {
    const parsed = new URL(normalized);
    const wsProto = parsed.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProto}//${parsed.host}${WS_LIVE_PATH}`;
  } catch (_err) {
    return "";
  }
};

const pushUniqueUrl = (target: string[], value: string) => {
  const normalized = String(value || "").trim();
  if (!normalized) return;
  if (!target.includes(normalized)) {
    target.push(normalized);
  }
};

export const isStatefulRunApiPath = (path: string) => {
  const normalized = String(path || "").trim().toLowerCase();
  return STATEFUL_RUN_API_PREFIXES.some((prefix) => normalized.startsWith(prefix));
};

export const resolveApiRequestUrl = (input: string) => {
  const raw = String(input || "");
  if (!raw.startsWith("/api")) return raw;

  const queryIdx = raw.indexOf("?");
  const pathOnly = queryIdx >= 0 ? raw.slice(0, queryIdx) : raw;
  const statefulPath = isStatefulRunApiPath(pathOnly);

  const base = statefulPath
    ? defaultPlaybackApiBaseUrl || defaultRunnerApiBaseUrl
    : defaultRunnerApiBaseUrl || defaultPlaybackApiBaseUrl;

  if (!base) return raw;
  return `${trimTrailingSlashes(base)}${raw}`;
};

export const hasConfiguredApiRequestRewrite = Boolean(
  defaultRunnerApiBaseUrl || defaultPlaybackApiBaseUrl,
);

export const wsFeatureEnabled = (() => {
  const raw = String(import.meta.env.VITE_WS_ENABLED || "").trim().toLowerCase();
  if (!raw) return true;
  return !["0", "false", "no", "off"].includes(raw);
})();

export const resolveRunnerApiBaseUrl = (strategyApiUrl?: string) => {
  if (defaultPlaybackApiBaseUrl) {
    return rewriteDockerAliasForBrowser(defaultPlaybackApiBaseUrl);
  }

  if (defaultRunnerApiBaseUrl) {
    return rewriteDockerAliasForBrowser(defaultRunnerApiBaseUrl);
  }

  const candidate = trimTrailingSlashes(strategyApiUrl || "");
  if (!candidate) {
    return "";
  }

  try {
    const parsed = new URL(candidate);
    if (parsed.port === "8001") {
      parsed.port = "8002";
      return rewriteDockerAliasForBrowser(trimTrailingSlashes(parsed.toString()));
    }
    return rewriteDockerAliasForBrowser(trimTrailingSlashes(parsed.toString()));
  } catch (_err) {
    const remapped = candidate.includes("8001") ? candidate.replace("8001", "8002") : candidate;
    return rewriteDockerAliasForBrowser(remapped);
  }
};

export const resolveWsLiveUrl = () => {
  const candidates = resolveWsLiveUrlCandidates();
  if (candidates.length > 0) {
    return candidates[0];
  }

  if (typeof window === "undefined") {
    return `ws://127.0.0.1:8002${WS_LIVE_PATH}`;
  }

  const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${wsProtocol}://${window.location.host}${WS_LIVE_PATH}`;
};

export const resolveWsLiveUrlCandidates = () => {
  const candidates: string[] = [];
  const configuredWsBase = trimTrailingSlashes(import.meta.env.VITE_WS_BASE_URL || "");
  let deferredConfiguredWsUrl = "";
  if (configuredWsBase) {
    const configuredWsUrl = configuredWsBase.endsWith(WS_LIVE_PATH)
      ? configuredWsBase
      : `${configuredWsBase}${WS_LIVE_PATH}`;
    if (typeof window !== "undefined" && isLocalBrowserHost()) {
      try {
        const parsed = new URL(configuredWsUrl);
        const host = String(parsed.hostname || "").trim().toLowerCase();
        const port = String(parsed.port || "").trim();
        if ((host === "localhost" || host === "127.0.0.1") && port === "5173") {
          // Misconfigured local WS base often points to Vite dev server.
          // Keep it as last resort and prefer runner API candidates first.
          deferredConfiguredWsUrl = configuredWsUrl;
        } else {
          pushUniqueUrl(candidates, configuredWsUrl);
        }
      } catch (_err) {
        pushUniqueUrl(candidates, configuredWsUrl);
      }
    } else {
      pushUniqueUrl(candidates, configuredWsUrl);
    }
  }

  if (typeof window === "undefined") {
    if (defaultPlaybackApiBaseUrl) {
      pushUniqueUrl(candidates, buildWsLiveUrlFromHttpBase(defaultPlaybackApiBaseUrl));
    }
    if (defaultRunnerApiBaseUrl) {
      pushUniqueUrl(candidates, buildWsLiveUrlFromHttpBase(defaultRunnerApiBaseUrl));
    }
    return candidates;
  }

  const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
  const browserHost = String(window.location.host || "").trim();

  if (isLocalBrowserHost()) {
    const browserHostname = String(window.location.hostname || "").trim().toLowerCase();
    // Local dev typically serves frontend on :5173 and runner on :8002.
    // Prefer :8002 candidates first to avoid sticky reconnect loops to Vite.
    if (browserHostname) {
      pushUniqueUrl(candidates, `${wsProtocol}://${browserHostname}:8002${WS_LIVE_PATH}`);
    }
    if (browserHostname !== "localhost") {
      pushUniqueUrl(candidates, `${wsProtocol}://localhost:8002${WS_LIVE_PATH}`);
    }
    if (browserHostname !== "127.0.0.1") {
      pushUniqueUrl(candidates, `${wsProtocol}://127.0.0.1:8002${WS_LIVE_PATH}`);
    }
  }

  if (defaultPlaybackApiBaseUrl) {
    pushUniqueUrl(candidates, buildWsLiveUrlFromHttpBase(defaultPlaybackApiBaseUrl));
  }

  if (defaultRunnerApiBaseUrl) {
    pushUniqueUrl(candidates, buildWsLiveUrlFromHttpBase(defaultRunnerApiBaseUrl));
  }

  if (browserHost) {
    pushUniqueUrl(candidates, `${wsProtocol}://${browserHost}${WS_LIVE_PATH}`);
  }
  if (deferredConfiguredWsUrl) {
    pushUniqueUrl(candidates, deferredConfiguredWsUrl);
  }

  return candidates;
};
