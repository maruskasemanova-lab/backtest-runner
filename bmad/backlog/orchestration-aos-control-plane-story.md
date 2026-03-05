# Story Template (BMAD Adapted)

## Story ID

`orchestration-aos-control-plane`

## Objective

Introduce a canonical AOS/ticker configuration control plane that separates persisted saved state, active profile selection, effective resolved run config, and remote publish state, while preserving current runner/strategy API compatibility and no-lookahead invariants.

## Scope

- In scope:
  - Central read-side `ConfigResolver` for ticker config precedence.
  - Canonical repository boundary for AOS/positioning/profile state.
  - Compatibility wrappers for existing `/api/aos-config`, `/api/profiles`, combo, and adaptive routes.
  - Deterministic run-start consumption of resolved config snapshots and fingerprints.
  - Audit/history model improvement for config changes and publishes.
- Out of scope:
  - Full frontend redesign.
  - Strategy-engine trading logic changes.
  - Big-bang removal of all legacy config fields in one PR.

## Domain

Primary domain from `bmad/context/component-map.json`:

`orchestration`

Secondary planned execution domains:

- `frontend`
- `strategy-engine`

## Files To Touch

- `api_server.py`
- `src/routes/config_read_routes.py`
- `src/routes/config_write_routes.py`
- `src/routes/unified_profile_user_store.py`
- `src/services/config_write_service.py`
- `src/services/profile_options_service.py`
- `src/services/strategy_api_profiles_service.py`
- `src/services/start_run_bootstrap_phase_service.py`
- `src/services/start_run_execution_config_service.py`
- `src/services/local_config_service.py`
- `src/services/saas_service.py`
- `src/services/config_domain/*` (new)
- `frontend/src/components/AOSOptimizations.tsx`
- `frontend/src/components/run-config/useRunConfigProfiles.ts`
- `frontend/src/components/adaptive-studio/hooks/useAdaptiveStudioData.ts`

## Contracts / Interfaces

- Input payload changes:
  - No breaking changes in existing `/api/*` routes during migration.
  - New versioned control-plane routes may be added under `/api/v2/config/*`.
- Output payload changes:
  - Existing payloads stay backward compatible.
  - Responses may gain explicit revision/publish/fingerprint metadata.
- Backward compatibility notes:
  - `run/start` precedence semantics must remain deterministic.
  - `comparable_mode` cold-start semantics remain unchanged.
  - No same-bar execution invariant remains unaffected because this story does not alter strategy execution timing.

## Acceptance Criteria

1. Functional:
   - One canonical resolver defines effective ticker config precedence across run-start, profile options, and FE read endpoints.
   - One canonical repository owns persisted config/profile state behind compatibility wrappers.
   - `run/start` stores or exposes the exact resolved config revision/fingerprint it used.
2. Performance:
   - Resolver/publisher split does not add repeated O(n) re-merge work across the same request path.
   - No material start-run latency regression from duplicate remote config fanout.
3. Safety (no lookahead, risk guardrails):
   - No bar-processing or strategy execution logic changes.
   - `comparable_mode` and checkpoint behavior remain deterministic.
   - Remote publish/apply remains opt-in and auditable.

## Test Plan

- Unit tests:
  - `tests/test_start_run_execution_config_service.py`
  - `tests/test_strategy_api_profiles_service.py`
  - `tests/test_config_write_service_unified_store.py`
  - `tests/test_local_config_service.py`
- Integration tests:
  - `tests/test_unified_profiles_api.py`
  - `tests/test_strategy_combo_profiles_api.py`
  - `tests/test_start_run_strategy_overrides_mode.py`
- Manual validation:
  - Save, activate, publish, and run-start flow for one ticker with and without auth.
  - Confirm `config_fingerprint` and active profile metadata remain stable across replay.
  - `python3 scripts/generate_context_pack.py`
  - `python3 scripts/validate_llm_context.py --strict`

## Rollback Plan

- What to revert first:
  - Revert new `config_domain/*` usage from routes and run-start bootstrap.
  - Restore legacy direct config merges in `config_write_service.py`, `strategy_api_profiles_service.py`, and `start_run_execution_config_service.py`.
- Which metrics/logs indicate rollback is needed:
  - Mismatch between FE-visible ticker config and `run/start` effective config.
  - Remote publish failures or unexpected publish-on-read behavior.
  - Fingerprint drift for unchanged saved config.
