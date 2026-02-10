# Story 4.1: Contract Table for Start and Session Config APIs

Status: done

## Story

As a platform engineer,  
I want field-level contract documentation for runner and session config APIs,  
so that integration expectations are explicit and stable.

## Acceptance Criteria

1. Given current API behavior and defaults, when contract documentation is updated, then `/api/run/start` and `/api/session/config` field tables are documented with defaults.
2. Given documented contracts, when validated, then docs align with current behavior.

## Tasks / Subtasks

- [x] Validate presence of contract documentation
  - [x] Confirmed `docs/llm/api-contracts.md` covers runner start and strategy session config contracts.
- [x] Validate docs consistency pipeline
  - [x] `python3 scripts/generate_context_pack.py`
  - [x] `python3 scripts/validate_llm_context.py --strict`

## Dev Agent Record

### Agent Model Used

GPT-5 Codex (CLI)

### Completion Notes List

- Contract documentation is present and validation scripts pass.

### File List

- `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/_bmad-output/implementation-artifacts/4-1-contract-table-for-start-and-session-config-apis.md`

### Change Log

- 2026-02-09: Story validated and marked done.
