import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";

export type AuthSnapshot = {
  enabled: boolean;
  signedIn: boolean;
  email: string | null;
  userId: string | null;
  token: string | null;
};

const AUTH_EVENT = "backtest-auth-updated";
const BACKTEST_JWT_KEY = "backtest_jwt";
const SUPABASE_JWT_KEY = "supabase_jwt";
const SUPABASE_URL = String(import.meta.env.VITE_SUPABASE_URL || "").trim();
const SUPABASE_PUBLISHABLE_KEY = String(
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY || "",
).trim();
const HAS_FRONTEND_SECRET_KEY =
  !!String(import.meta.env.VITE_SUPABASE_SECRET_KEY || "").trim() ||
  !!String(import.meta.env.VITE_SUPABASE_SERVICE_ROLE_KEY || "").trim();
const OAUTH_CALLBACK_PATH =
  String(import.meta.env.VITE_SUPABASE_OAUTH_CALLBACK_PATH || "/auth/callback").trim() ||
  "/auth/callback";
const OAUTH_REDIRECT_URL = String(import.meta.env.VITE_SUPABASE_OAUTH_REDIRECT_URL || "").trim();

if (HAS_FRONTEND_SECRET_KEY) {
  console.error(
    "Detected Supabase secret/service-role key in VITE_* env. Remove it from frontend env immediately.",
  );
}

const hasSupabaseConfig = !!SUPABASE_URL && !!SUPABASE_PUBLISHABLE_KEY;

const supabaseClient: SupabaseClient | null = hasSupabaseConfig
  ? createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        // Callback processing is handled explicitly in bootstrapAuthSession().
        detectSessionInUrl: false,
        storageKey: "backtest_runner.supabase.auth",
      },
    })
  : null;

const isBrowser = () => typeof window !== "undefined";

const dispatchAuthUpdated = () => {
  if (!isBrowser()) return;
  window.dispatchEvent(new Event(AUTH_EVENT));
};

const readStoredToken = () => {
  if (!isBrowser()) return "";
  return String(
    window.localStorage.getItem(BACKTEST_JWT_KEY) ||
      window.localStorage.getItem(SUPABASE_JWT_KEY) ||
      "",
  ).trim();
};

const writeStoredToken = (token: string) => {
  if (!isBrowser()) return;
  const next = String(token || "").trim();
  const currentBacktest = String(window.localStorage.getItem(BACKTEST_JWT_KEY) || "").trim();
  const currentSupabase = String(window.localStorage.getItem(SUPABASE_JWT_KEY) || "").trim();

  if (next) {
    if (currentBacktest === next && currentSupabase === next) {
      return;
    }
    window.localStorage.setItem(BACKTEST_JWT_KEY, next);
    window.localStorage.setItem(SUPABASE_JWT_KEY, next);
  } else {
    if (!currentBacktest && !currentSupabase) {
      return;
    }
    window.localStorage.removeItem(BACKTEST_JWT_KEY);
    window.localStorage.removeItem(SUPABASE_JWT_KEY);
  }
  dispatchAuthUpdated();
};

const parseJwtClaims = (token: string) => {
  const raw = String(token || "").trim();
  if (!raw) return {};
  const parts = raw.split(".");
  if (parts.length < 2) return {};
  try {
    const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = normalized.length % 4;
    const padded = normalized + (pad ? "=".repeat(4 - pad) : "");
    const payload = atob(padded);
    const decoded = JSON.parse(payload);
    return decoded && typeof decoded === "object" ? decoded : {};
  } catch (_error) {
    return {};
  }
};

const buildSnapshotFromToken = (token: string): AuthSnapshot => {
  const claims = parseJwtClaims(token);
  const email =
    String(
      claims.email ||
        claims.user_email ||
        claims.preferred_username ||
        claims.upn ||
        "",
    ).trim() || null;
  const userId = String(claims.sub || claims.user_id || "").trim() || null;
  return {
    enabled: hasSupabaseConfig,
    signedIn: !!token,
    email,
    userId,
    token: token || null,
  };
};

const buildSnapshotFromSession = (session: Session | null): AuthSnapshot => {
  if (!session?.access_token) {
    return {
      enabled: hasSupabaseConfig,
      signedIn: false,
      email: null,
      userId: null,
      token: null,
    };
  }
  return {
    enabled: hasSupabaseConfig,
    signedIn: true,
    email: session.user?.email || null,
    userId: session.user?.id || null,
    token: session.access_token,
  };
};

const normalizePath = (value: string) => {
  const raw = String(value || "").trim();
  if (!raw) return "/auth/callback";
  return raw.startsWith("/") ? raw : `/${raw}`;
};

const callbackPath = normalizePath(OAUTH_CALLBACK_PATH);

const parseHashParams = () => {
  if (!isBrowser()) return new URLSearchParams();
  const hash = String(window.location.hash || "").replace(/^#/, "");
  return new URLSearchParams(hash);
};

const parseSearchParams = () => {
  if (!isBrowser()) return new URLSearchParams();
  return new URLSearchParams(window.location.search || "");
};

const hasOAuthCallbackPayload = () => {
  const query = parseSearchParams();
  const hash = parseHashParams();
  return (
    !!String(query.get("code") || "").trim() ||
    !!String(query.get("error") || "").trim() ||
    !!String(hash.get("access_token") || "").trim() ||
    !!String(hash.get("error") || "").trim()
  );
};

const shouldHandleCallbackPath = () => {
  if (!isBrowser()) return false;
  const pathname = String(window.location.pathname || "").trim();
  return pathname === callbackPath;
};

const cleanupAuthCallbackUrl = () => {
  if (!isBrowser()) return;
  const query = parseSearchParams();
  const next = String(query.get("next") || "").trim();
  const target = next.startsWith("/") ? next : "/";
  window.history.replaceState({}, document.title, target);
};

const maybePersistSessionToken = (session: Session | null) => {
  const token = String(session?.access_token || "").trim();
  writeStoredToken(token);
};

export const isSupabaseAuthEnabled = () => hasSupabaseConfig;

export const getSupabaseClient = () => supabaseClient;

export const getAuthSnapshot = async (): Promise<AuthSnapshot> => {
  if (supabaseClient) {
    try {
      const { data } = await supabaseClient.auth.getSession();
      const snapshot = buildSnapshotFromSession(data?.session || null);
      maybePersistSessionToken(data?.session || null);
      return snapshot;
    } catch (error) {
      console.warn("Failed to fetch supabase session:", error);
    }
  }

  const fallbackToken = readStoredToken();
  return buildSnapshotFromToken(fallbackToken);
};

const handleImplicitFlowCallback = async (): Promise<boolean> => {
  if (!isBrowser()) return false;
  const hashParams = parseHashParams();
  const accessToken = String(hashParams.get("access_token") || "").trim();
  if (!accessToken) return false;

  writeStoredToken(accessToken);

  if (supabaseClient) {
    try {
      await supabaseClient.auth.refreshSession({
        access_token: accessToken,
        refresh_token: String(hashParams.get("refresh_token") || "").trim() || undefined,
      });
    } catch (error) {
      console.debug("Supabase refreshSession skipped/failed on implicit callback:", error);
    }
  }

  cleanupAuthCallbackUrl();
  return true;
};

const handlePkceCallback = async (): Promise<boolean> => {
  if (!isBrowser() || !supabaseClient) return false;
  const query = parseSearchParams();
  const code = String(query.get("code") || "").trim();
  if (!code) return false;

  const { data, error } = await supabaseClient.auth.exchangeCodeForSession(code);
  if (error) {
    throw error;
  }

  maybePersistSessionToken(data?.session || null);
  cleanupAuthCallbackUrl();
  return true;
};

export const bootstrapAuthSession = async (): Promise<AuthSnapshot> => {
  if (!isBrowser()) {
    return {
      enabled: hasSupabaseConfig,
      signedIn: false,
      email: null,
      userId: null,
      token: null,
    };
  }

  if (shouldHandleCallbackPath() || hasOAuthCallbackPayload()) {
    const query = parseSearchParams();
    const hash = parseHashParams();
    const oauthError = String(query.get("error") || hash.get("error") || "").trim();
    const oauthErrorDescription = query.get("error_description") || hash.get("error_description");
    if (oauthError) {
      console.warn("OAuth callback error:", oauthError, oauthErrorDescription);
      writeStoredToken("");
      cleanupAuthCallbackUrl();
      return getAuthSnapshot();
    }

    try {
      const handledImplicit = await handleImplicitFlowCallback();
      if (!handledImplicit) {
        await handlePkceCallback();
      }
    } catch (error) {
      console.error("Failed to process OAuth callback:", error);
      writeStoredToken("");
      cleanupAuthCallbackUrl();
    }
  }

  return getAuthSnapshot();
};

const resolveOAuthRedirectTo = () => {
  if (OAUTH_REDIRECT_URL) {
    try {
      const parsed = new URL(OAUTH_REDIRECT_URL);
      if (parsed.protocol === "http:" || parsed.protocol === "https:") {
        return parsed.toString();
      }
    } catch (_error) {
      // Fallback below when env is malformed.
    }
    console.warn("Ignoring invalid VITE_SUPABASE_OAUTH_REDIRECT_URL. Falling back to current origin.");
  }
  return `${window.location.origin}${callbackPath}`;
};

export const subscribeAuthSnapshot = (
  listener: (snapshot: AuthSnapshot) => void,
): (() => void) => {
  if (!isBrowser()) return () => {};

  let unsubscribed = false;

  const emitCurrent = async () => {
    if (unsubscribed) return;
    const snapshot = await getAuthSnapshot();
    if (!unsubscribed) {
      listener(snapshot);
    }
  };

  const onStorageUpdate = () => {
    emitCurrent().catch(() => null);
  };

  window.addEventListener(AUTH_EVENT, onStorageUpdate);

  let supabaseUnsubscribe: (() => void) | null = null;
  if (supabaseClient) {
    const { data } = supabaseClient.auth.onAuthStateChange((_event, session) => {
      maybePersistSessionToken(session || null);
      const snapshot = buildSnapshotFromSession(session || null);
      listener(snapshot);
    });
    supabaseUnsubscribe = () => data.subscription.unsubscribe();
  }

  emitCurrent().catch(() => null);

  return () => {
    unsubscribed = true;
    window.removeEventListener(AUTH_EVENT, onStorageUpdate);
    if (supabaseUnsubscribe) {
      supabaseUnsubscribe();
    }
  };
};

export const signInWithGoogle = async () => {
  if (!supabaseClient || !isBrowser()) {
    throw new Error("Supabase auth is not configured.");
  }

  const redirectTo = resolveOAuthRedirectTo();
  const nextPath = `${window.location.pathname || "/"}${window.location.search || ""}`;
  const next = nextPath.startsWith("/") ? nextPath : "/";
  let redirectWithNext = redirectTo;
  try {
    const parsed = new URL(redirectTo);
    if (!parsed.searchParams.get("next")) {
      parsed.searchParams.set("next", next);
    }
    redirectWithNext = parsed.toString();
  } catch (_error) {
    // Keep raw redirectTo when URL parsing fails unexpectedly.
  }
  const { error } = await supabaseClient.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: redirectWithNext,
      queryParams: {
        prompt: "select_account",
      },
    },
  });

  if (error) {
    throw error;
  }
};

export const signOutSupabase = async () => {
  if (supabaseClient) {
    try {
      await supabaseClient.auth.signOut();
    } catch (error) {
      console.warn("Supabase sign-out failed:", error);
    }
  }
  writeStoredToken("");
};
