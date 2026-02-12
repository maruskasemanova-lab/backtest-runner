# Story Template (BMAD Adapted)

## Story ID

`orchestration-api-server-decomposition`

## Objective

Decompose `api_server.py` from a monolithic implementation into route/service modules with dependency-injected runtime state, while preserving all existing runner API contracts, no-lookahead invariants, and current test behavior.

## Scope

- In scope:
  - Move endpoint handlers from `api_server.py` into `src/routes/*`.
  - Move reusable business logic into `src/services/*`.
  - Keep backward-compatible helper symbols in `api_server.py` where tests/imports currently depend on them.
  - Reduce duplicate run-not-found/error boilerplate using small abstractions.
  - Keep `bmad/context/component-map.json` ownership mapping updated.
- Out of scope:
  - Strategy-engine contract redesign.
  - Frontend UI changes.
  - Behavioral changes to scoring, tuning, execution, or marker payload schemas.

## Domain

Primary domain from `bmad/context/component-map.json`:

`orchestration`

## Files To Touch

- `api_server.py`
- `src/routes/context.py`
- `src/routes/system_routes.py`
- `src/routes/l2_routes.py`
- `src/routes/data_loader_routes.py`
- `src/routes/live_trader_routes.py`
- `src/routes/config_read_routes.py`
- `src/routes/config_write_routes.py` (planned)
- `src/routes/run_routes.py` (planned)
- `src/services/live_trader_service.py`
- `src/services/run_registry.py`
- `src/services/config_service.py` (planned)
- `bmad/context/component-map.json`

## Contracts / Interfaces

- Input payload changes:
  - None planned.
- Output payload changes:
  - None planned.
- Backward compatibility notes:
  - Existing endpoint paths/methods must stay identical.
  - Existing module-level symbols currently used by tests should remain available until tests are migrated.
  - `run_key` identity remains `run_id:ticker:date_or_range`.

## Acceptance Criteria

1. Functional:
   - All current orchestration endpoints remain reachable on identical paths/methods.
   - `api_server.py` line count continues to decrease each phase.
2. Performance:
   - No additional O(n) overhead in critical run/step/play path beyond existing behavior.
3. Safety (no lookahead, risk guardrails):
   - No changes that can introduce lookahead in runner bar stepping.
   - `comparable_mode`/checkpoint semantics unchanged.
   - No same-bar execution invariant remains unaffected (no strategy-side behavior changes).

## Test Plan

- Unit tests:
  - `tests/test_live_trader_monitor_api.py`
  - `tests/test_strategy_combo_profiles_api.py`
  - `tests/test_adaptive_tuner_api.py`
  - `tests/test_api_server_l2_sessionized.py`
  - `tests/test_start_run_strategy_overrides_mode.py`
- Integration tests:
  - `tests/test_no_lookahead.py`
  - `tests/test_session_runner_markers.py`
  - `tests/test_decision_tracker_schema_v2.py`
  - `tests/test_data_loader_path_resolution.py`
  - `tests/test_day_trading_manager_session_reset.py`
- Manual validation:
  - FastAPI TestClient smoke for extracted endpoint groups.
  - `python3 scripts/generate_context_pack.py`
  - `python3 scripts/validate_llm_context.py --strict`

## Rollback Plan

- What to revert first:
  - Revert latest extracted router include and route module.
  - Restore original endpoint handler decorators in `api_server.py`.
- Which metrics/logs indicate rollback is needed:
  - Endpoint 404/422 regressions on existing frontend calls.
  - Any failure in orchestration API tests listed above.
  - Any validation failure in `validate_llm_context.py --strict`.

## Execution Progress

- Phase 1 (completed):
  - Extracted system, L2, data-loader routes.
  - Introduced `ApiServices` DI context.
- Phase 2 (completed):
  - Extracted live-trader routes + `live_trader_service`.
  - Added `run_registry` abstraction for consistent run lookup errors.
- Phase 3 (completed):
  - Extracted config read routes.
  - Extracted config write logic to `config_write_service`.
  - Extracted config write routes + request models.
- Phase 4 (completed):
  - Extracted run-control logic to `run_control_service`.
  - Extracted run-control endpoints to `run_routes`.
- Phase 5 (completed):
  - Moved adaptive tuner job orchestration endpoint logic to `src/services/adaptive_tuner_orchestration_service.py`.
  - Moved adaptive tuner endpoint registration to `src/routes/adaptive_tuner_routes.py`.
  - Moved `/api/run/start` endpoint registration to `src/routes/run_start_routes.py`.
  - Moved `StartRunRequest` and `AdaptiveTunerRequest` models into `src/models/`.
  - Extracted full `start_run` orchestration body into `src/services/start_run_service.py` and retained backward-compatible wrapper in `api_server.py`.
- Phase 6 (next):
  - Extracted adaptive tuner worker loops (`_run_adaptive_tuner_job`, `_run_v2_adaptive_tuner_job`) into `src/services/adaptive_tuner_worker_service.py` with DI dependency container.
  - Kept backward-compatible wrappers in `api_server.py` for test monkeypatch compatibility.
  - Extracted adaptive tuner evaluation and persistence runtime helpers into `src/services/adaptive_tuner_runtime_service.py` with DI dependency container.
  - Remaining: extract/adapt v2 search-space and candidate-config helper cluster into dedicated modules while preserving direct test-call compatibility wrappers in `api_server.py`.
