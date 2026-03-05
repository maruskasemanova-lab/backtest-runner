# AOS Control Plane Modularization Plan (BMAD)

Date: 2026-03-05
Primary Domain: `orchestration`
Secondary Domains (contract-safe integration): `frontend`, `strategy-engine`

## Executive Summary

Current AOS and ticker configuration flow works, but it mixes four different concerns into one path:

1. persisted ticker policy,
2. active profile selection,
3. effective run-time resolved config,
4. remote strategy API publish/apply state.

The result is a config system that is feature-rich but hard to reason about, hard to audit, and expensive to extend safely. The next refactor should be DB-first and model-first, not file-first. Files should remain only as migration/bootstrap/export adapters.

This plan supersedes the old file-driven emphasis from `_bmad-output/planning-artifacts/aos-config-refactor-plan.md`. The current runtime already uses DB-backed `config_snapshots` as the primary read/write path for the default config flow.

## Current-State Findings

### 1. Source of truth is already split, but the UI still talks like it is file-first

- `api_server.py`
  - `_load_aos_config()` reads primary config from DB-backed `config_snapshots` when no explicit path is passed.
  - `_save_aos_config()` writes primary config back to DB and records AOS history entries.
  - `_load_positioning_config()` and `_save_positioning_config()` do the same for positioning.
- `src/services/file_store_migration_service.py`
  - `ensure_primary_config_snapshots()` seeds DB from files only when snapshots do not exist.
- `frontend/src/components/AOSOptimizations.tsx`
  - still tells the user that `aos_optimization/aos_config.json` and `positioning_config.json` are the source of truth.

Implication:
- The app already behaves DB-first, but part of the mental model and some helper code still behave as if files are primary.

### 2. One ticker's state is fragmented across multiple storage and runtime layers

Today a single ticker can be influenced by:

- `aos_config` ticker payload
- `positioning_config` ticker payload
- `strategy_combo_profiles`
- `adaptive_tuner_profiles`
- `unified_profiles`
- user-scoped unified-profile state in `user_settings`
- request-time overrides from `StartRunRequest`
- remote strategy API sync side effects

Primary files:

- `src/services/config_write_service.py`
- `src/services/strategy_api_profiles_service.py`
- `src/services/profile_options_service.py`
- `src/routes/unified_profile_user_store.py`
- `src/services/start_run_execution_config_service.py`
- `src/models/run_requests.py`

Implication:
- There is no single aggregate model for "ticker configuration".

### 3. Merge precedence is reimplemented in several places

The same conceptual merge is happening in multiple services:

- `src/services/start_run_local_aos_service.py`
- `src/services/strategy_api_profiles_service.py`
- `src/services/start_run_execution_config_service.py`
- `src/services/profile_options_service.py`
- `src/services/local_config_service.py`

Implication:
- Every new config field increases drift risk.
- Behavior can diverge between:
  - what FE sees,
  - what remote strategy API receives,
  - what `run/start` ultimately uses.

### 4. Runtime resolution and remote publish are still coupled

`run_start_bootstrap_phase()` currently:

1. resets remote orchestrator state,
2. clears remote sessions,
3. optionally applies strategy overrides,
4. applies AOS optimizations to remote strategy API,
5. resolves execution config for the run.

Implication:
- the read path for a run still mutates external state;
- "resolve config" and "publish config" are not separate application operations.

### 5. Persistence is asymmetrical

- `config_snapshots` persists primary AOS and positioning snapshots.
- `aos_history_entries` only records a narrow subset of changes.
- unified profiles can live either:
  - in legacy ticker JSON/DB config, or
  - in per-user `user_settings`.

Implication:
- auditability exists, but not at the real domain boundary;
- user-scoped and global config ownership are inconsistent.

### 6. Test coverage is decent for resolvers, but thin for end-to-end precedence

Strong existing tests:

- `tests/test_start_run_execution_config_service.py`
- `tests/test_strategy_api_profiles_service.py`
- `tests/test_config_write_service_unified_store.py`
- `tests/test_unified_profiles_api.py`
- `tests/test_strategy_combo_profiles_api.py`
- `tests/test_local_config_service.py`

Still missing as a first-class contract:

- save -> activate -> publish -> start-run precedence chain
- multi-user/profile scope behavior under one canonical repository
- old endpoint parity after repository unification

## What The Application Should Do

The application should treat configuration as a control plane with explicit lifecycle states, not as loosely merged JSON blobs.

For every ticker and actor scope, the app should support:

1. `save`
   - Persist strategy/execution/adaptive defaults and saved profile catalogs.
   - No remote side effects.
2. `activate`
   - Set which saved profile(s) are active for next use.
   - No implicit remote sync unless requested.
3. `resolve`
   - Build one deterministic effective config snapshot for:
     - FE inspection,
     - run start,
     - diagnostics,
     - previews.
4. `publish`
   - Push the resolved config to the remote strategy service.
   - Record publish result, target, revision, fingerprint, and timestamps.
5. `snapshot`
   - Persist the exact effective config used by each run.
   - Reuse the same fingerprint for diagnostics and replay.

That gives you a clean separation between:

- saved state,
- active state,
- effective state,
- published state,
- per-run immutable snapshot.

## Target Architecture

### A. Canonical aggregate

Introduce one canonical domain object:

- `TickerConfigAggregate`

Suggested sections:

- `ticker`
- `scope`
  - `global`
  - `user`
- `strategy_defaults`
- `execution_defaults`
- `adaptive_defaults`
- `saved_profiles`
  - `strategy_combo`
  - `adaptive_tuner`
  - `unified`
- `active_refs`
  - `strategy_combo_profile_id`
  - `adaptive_profile_id`
  - `unified_profile_id`
- `metadata`
  - `schema_version`
  - `revision`
  - `fingerprint`
  - `updated_at`
  - `updated_by`

### B. Resolver as the only merge authority

Create one resolver service responsible for precedence:

- `ConfigResolver.resolve_effective_ticker_config(...)`

Proposed precedence:

1. explicit run request overrides
2. active unified profile
3. active adaptive profile runtime overrides
4. active strategy combo strategy params
5. saved ticker defaults
6. global defaults
7. code defaults

Important:

- `unified` is a first-class profile type, not a fallback overlay hack.
- legacy combo+adaptive recomposition stays only as a compatibility adapter until migration is complete.

### C. Repository layer

Create one repository boundary:

- `ConfigRepository`

Responsibilities:

- read/write canonical aggregate
- persist revisions
- persist active refs
- persist audit events
- expose compatibility projections for old endpoints

Do not let route/services read raw `config_snapshots` or `user_settings` directly once this layer exists.

### D. Publish layer

Create one explicit remote publisher:

- `ConfigPublisher.publish_effective_config(...)`

Responsibilities:

- sync strategy params
- sync adaptive/orchestrator knobs
- sync execution-derived remote knobs only where required
- persist publish status:
  - `last_published_revision`
  - `last_published_fingerprint`
  - `last_publish_target`
  - `last_publish_status`
  - `last_publish_error`

### E. Projection layer

Create read models for FE:

- `TickerConfigProjection`
- `UnifiedProfileOptionsProjection`
- `AdaptiveProfileOptionsProjection`
- `RunConfigProjection`

This keeps FE endpoints stable while backend storage becomes sane.

## Persistence Model

Recommended DB-first shape:

### 1. Keep

- `config_snapshots`
  - but demote to system backup/export snapshot role
- `aos_history_entries`
  - only as migration input until replaced

### 2. Add

- `ticker_config_documents`
  - one row per `ticker + scope + section + revision`
- `ticker_config_active_refs`
  - current active profile refs per `ticker + scope`
- `ticker_config_events`
  - append-only audit log of semantic changes
- `ticker_config_publish_state`
  - remote publish status and last published fingerprint

### 3. Run snapshots

Either extend existing run summary persistence or add:

- `run_config_snapshots`
  - `run_key`
  - `ticker`
  - `scope`
  - `effective_config_json`
  - `config_fingerprint`
  - `resolved_revision`

This is aligned with the current `config_fingerprint` approach and makes diagnostics deterministic.

## Proposed Python Module Layout

Use a dedicated config domain package instead of spreading logic across generic services:

- `src/services/config_domain/models.py`
- `src/services/config_domain/schemas.py`
- `src/services/config_domain/repository.py`
- `src/services/config_domain/resolver.py`
- `src/services/config_domain/publisher.py`
- `src/services/config_domain/history.py`
- `src/services/config_domain/projections.py`
- `src/services/config_domain/migrations.py`
- `src/services/config_domain/compat.py`

Then progressively reduce responsibility in:

- `src/services/config_write_service.py`
- `src/services/strategy_api_profiles_service.py`
- `src/services/profile_options_service.py`
- `src/services/start_run_execution_config_service.py`
- `src/services/start_run_bootstrap_phase_service.py`
- `src/routes/unified_profile_user_store.py`

## API Direction

Do not break current routes immediately. Add a versioned control-plane surface and keep old routes as compatibility wrappers.

### Compatibility routes to keep

- `GET /api/aos-config`
- `GET /api/aos-config/{ticker}`
- `POST /api/aos-config/update`
- `GET /api/profiles/{ticker}`
- `POST /api/profiles/capture`
- `POST /api/profiles/apply`
- `POST /api/adaptive-tuner/profiles/apply`
- `POST /api/strategy-combos/apply`

### New v2/vNext control-plane routes

- `GET /api/v2/config/tickers/{ticker}`
- `PATCH /api/v2/config/tickers/{ticker}/defaults/strategy`
- `PATCH /api/v2/config/tickers/{ticker}/defaults/execution`
- `PATCH /api/v2/config/tickers/{ticker}/defaults/adaptive`
- `POST /api/v2/config/tickers/{ticker}/profiles/{profile_type}`
- `POST /api/v2/config/tickers/{ticker}/activate`
- `POST /api/v2/config/tickers/{ticker}/resolve`
- `POST /api/v2/config/tickers/{ticker}/publish`
- `GET /api/v2/config/tickers/{ticker}/history`

## Recommended 2026 Tooling

### Axon

Use Axon as the blast-radius and symbol-impact layer before each slice:

- index both repos
- query impacts for:
  - `ConfigRepository`
  - `ConfigResolver`
  - `ConfigPublisher`
  - `run_start_bootstrap_phase`
  - `resolve_execution_config`
- run change-detection on diffs before merge

Practical use:

- every refactor PR should include an Axon impact summary for affected symbols and callers.

### Python MCP

Use Python MCP refactoring tools to keep modules bounded:

- package metrics before/after each slice
- long-function extraction guidance for:
  - `config_write_service.py`
  - `strategy_api_profiles_service.py`
  - `start_run_execution_config_service.py`
- test coverage checks specifically for precedence and migration flows

### MCP inside the product

Build a small internal MCP server for configuration operations:

- resources:
  - current ticker config
  - active refs
  - revision history
  - run config snapshots
- tools:
  - resolve effective config
  - diff revisions
  - validate change
  - promote profile
  - explain fingerprint drift

This is useful for both engineers and future local agent workflows.

### Persistence and typing

Recommended stack:

- Pydantic v2 + `pydantic-settings` for typed config schemas and environment settings
- SQLAlchemy 2.x typed ORM for canonical config persistence and migration-safe models
- OpenTelemetry traces for:
  - `config.resolve`
  - `config.publish`
  - `run.start.bootstrap`
  - `run.start.resolve_execution_config`
- Keep Temporal optional:
  - use it only if config publish/promote becomes multi-node durable workflow;
  - otherwise keep the existing local async queue semantics

## Migration Plan

### Phase 0. Define canonical schema without behavior change

- add `TickerConfigAggregate` and typed section schemas
- add repository interface backed by current DB snapshots + user settings
- keep old routes and service signatures

### Phase 1. Centralize read resolution

- move all read-side merge logic into `ConfigResolver`
- make:
  - `profile_options_service`
  - `strategy_api_profiles_service`
  - `start_run_local_aos_service`
  - `start_run_execution_config_service`
  consume resolver output instead of raw storage merges

### Phase 2. Centralize writes

- route all writes through `ConfigRepository`
- stop direct writes to:
  - raw ticker config blobs
  - user settings patches
  - legacy profile fields outside repository adapters

### Phase 3. Split publish from resolve

- replace `apply_aos_optimizations()` behavior with:
  - `resolve_effective_config()`
  - `publish_effective_config()`
- `run_start_bootstrap_phase()` should resolve first, publish only when explicitly enabled

### Phase 4. Add revisioned per-ticker tables

- migrate from snapshot-centric storage to per-ticker revisioned documents
- keep snapshot export for rollback and backup

### Phase 5. Remove legacy recomposition paths

- retire synthetic legacy unified profile generation once all active data is migrated to first-class profile documents

## Acceptance Criteria

1. One canonical resolver defines precedence for all ticker config usage.
2. One canonical repository owns persistence for saved profiles, active refs, and revision history.
3. `run/start` consumes a resolved immutable config snapshot instead of ad hoc multi-source merges.
4. Remote publish is a separate application operation with recorded status.
5. Existing FE endpoints remain backward compatible during migration.
6. Run diagnostics can always answer:
   - what config was active,
   - what effective config was used,
   - what was published remotely,
   - why a fingerprint changed.

## Validation Plan

Required:

1. `python3 scripts/generate_context_pack.py`
2. `python3 scripts/validate_llm_context.py --strict`

Implementation-phase tests:

- `pytest tests/test_start_run_execution_config_service.py`
- `pytest tests/test_strategy_api_profiles_service.py`
- `pytest tests/test_config_write_service_unified_store.py`
- `pytest tests/test_unified_profiles_api.py`
- `pytest tests/test_strategy_combo_profiles_api.py`
- `pytest tests/test_local_config_service.py`

New tests to add during implementation:

- precedence matrix contract tests
- repository migration tests
- save/activate/publish/run integration tests
- multi-user scope tests for unified profiles

## Main Risks

1. Legacy endpoints currently expose storage shape, not domain shape.
2. Unified profiles are partly user-scoped while other profiles remain ticker-global.
3. `run/start` currently depends on remote side effects during bootstrap.
4. Old FE text and assumptions can mislead operators about the true source of truth.

## Recommended Next Story

Start with a backend story that does not change external contracts:

- introduce `ConfigResolver`
- route all read paths through it
- keep storage exactly as-is for the first slice

That gives immediate leverage without forcing a risky migration first.
