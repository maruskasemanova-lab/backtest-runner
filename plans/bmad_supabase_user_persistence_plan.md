# BMAD Plan: Supabase Auth + User Persistence

## Goal

Stabilize user UX state in frontend now, then roll into full per-user persistence (runs, profiles, preferences) backed by Supabase.

## Decisions

1. Frontend draft state (short-term, low-latency): keep in browser local storage.
2. User-owned durable state (mid/long-term): persist in Supabase Postgres via runner API.
3. Backend remains contract owner: frontend never writes Supabase directly for run artifacts/profiles; it calls runner endpoints.
4. Keep backward compatibility: local fallback stays available when Supabase is unavailable.

## Domain Routing (BMAD)

- Primary now: `frontend`
- Expansion phases: `orchestration` (+ existing `strategy-engine` profile contracts unchanged)

## Phase 0 (done in this iteration)

- Persist `RunConfig` draft in local storage (`backtest_runner.run_config_draft.v1`).
- Restore ticker/date/profile selector on panel remount and reload.
- Keep behavior backward compatible with existing run start contracts.

## Phase 1: Auth Foundation (Supabase)

### Scope

- Add frontend auth session bootstrap (Supabase JS client wrapper).
- Implement `/auth/callback` handling in SPA bootstrap path.
- Store JWT in existing `backtest_jwt` / `supabase_jwt` compatibility slots.
- Add runner endpoint guard tests for Supabase-signed JWT paths.

### Deliverables

- `frontend/src/auth/*` auth utilities + callback parser.
- `frontend/src/main.tsx` callback processing and safe redirect.
- Minimal auth UI state (signed-in user badge + logout).
- Tests for auth token propagation to `/api/v2/*`.

## Phase 2: User Settings Persistence

### Scope

Persist per-user UI configuration (ticker/date/profile defaults, sidebar mode, execution preferences).

### Proposed API

- `GET /api/v2/user/settings`
- `PUT /api/v2/user/settings`

### Data Model

- Table: `user_settings`
- Key: `(user_id, namespace)`
- Value: JSONB
- Versioned payload schema for forward migration.

## Phase 3: Runs + Profiles as User Data

### Scope

- Persist run metadata/history by user.
- Persist unified profiles and profile application history by user.

### Proposed Tables

- `user_runs`
- `user_run_artifacts`
- `user_profiles_unified`
- `user_profile_events`

### Key Constraints

- Index by `(user_id, ticker, created_at desc)`.
- Soft delete + retention policy aligned with plan tiers.
- Immutable run snapshots to preserve auditability.

## Phase 4: Migration + Rollout

1. Dual-write (local store + Supabase) under feature flag.
2. Read preference: Supabase first, fallback local.
3. Backfill historical profiles/runs for opted-in users.
4. Turn off fallback only after SLO + data parity checks pass.

## Environment + Redirect URLs

For Supabase Auth redirect allowlist, include at least:

- `http://localhost:5173/auth/callback`
- `https://<netlify-site>.netlify.app/auth/callback`
- `https://<vercel-project>.vercel.app/auth/callback`
- `https://<your-custom-domain>/auth/callback` (if used)

Optional for preview builds:

- `https://*-<team-or-site>.vercel.app/auth/callback`
- `https://**--<site>.netlify.app/auth/callback`

## Risks

- Token/session drift between frontend local storage and server auth expectations.
- Profile schema drift between AOS file-backed config and DB-backed profile entities.
- Data residency/retention costs once run artifacts move to durable storage.

## Validation Gates

- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py --strict`
- frontend build + auth callback smoke test
- v2 auth regression tests for JWT and tenant scoping
