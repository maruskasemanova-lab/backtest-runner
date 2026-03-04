import { memo } from 'react';
import type { AuthSnapshot } from '../auth/supabaseAuth';

type QuotaSnapshot = {
  usage?: {
    active_runs?: number;
  } | null;
  limits?: {
    concurrent_runs?: number;
  } | null;
} | null;

type AppTopbarProps = {
  isConnected: boolean;
  planTier: string | null;
  quotaSnapshot: QuotaSnapshot;
  authSnapshot: AuthSnapshot;
  authActionBusy: boolean;
  onToggleSidebar: () => void;
  onSignIn: () => void;
  onSignOut: () => void;
};

// Extracted into a named function for easier debugging and memoization wrapper below.
function AppTopbarRender({
  isConnected,
  planTier,
  quotaSnapshot,
  authSnapshot,
  authActionBusy,
  onToggleSidebar,
  onSignIn,
  onSignOut,
}: AppTopbarProps) {
  return (
    <header className="app-topbar">
      <button
        type="button"
        className="sidebar-mobile-toggle"
        onClick={onToggleSidebar}
        aria-label="Toggle sidebar"
      >
        <span />
        <span />
        <span />
      </button>

      <div className="topbar-command">
        <span className="topbar-eyebrow">Operations Mesh</span>
        <div className="topbar-command-copy">
          <span className="topbar-title">Realtime trading control plane</span>
          <span className="topbar-subtitle">
            Tuning, diagnostics and execution in one focused workspace.
          </span>
        </div>
      </div>

      <div className="topbar-status">
        <div className="connection-indicator">
          <span className={`status-dot ${isConnected ? 'connected' : ''}`} />
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
        <span className={`plan-badge plan-${String(planTier || 'free').toLowerCase()}`}>
          {String(planTier || 'free').toUpperCase()}
        </span>
        {quotaSnapshot?.usage && quotaSnapshot?.limits ? (
          <span className="quota-badge">
            {quotaSnapshot.usage.active_runs || 0}/{quotaSnapshot.limits.concurrent_runs || 0}{' '}
            runs
          </span>
        ) : null}
        {authSnapshot.enabled ? (
          authSnapshot.signedIn ? (
            <>
              <span className="auth-user-badge" title={authSnapshot.userId || undefined}>
                {authSnapshot.email || authSnapshot.userId || 'Signed In'}
              </span>
              <button
                type="button"
                className="auth-action-btn"
                disabled={authActionBusy}
                onClick={onSignOut}
              >
                {authActionBusy ? '...' : 'Sign Out'}
              </button>
            </>
          ) : (
            <button
              type="button"
              className="auth-action-btn"
              disabled={authActionBusy}
              onClick={onSignIn}
            >
              {authActionBusy ? '...' : 'Sign In (Google)'}
            </button>
          )
        ) : (
          <span className="auth-user-badge auth-disabled">Auth Off</span>
        )}
      </div>
    </header>
  );
}

export default memo(AppTopbarRender);
