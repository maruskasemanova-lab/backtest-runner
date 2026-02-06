# Domain: Run Orchestration API

**ID:** `orchestration`

## Mission

Own run lifecycle, API contracts, and integration to strategy service.

## Depends On

- `strategy-engine`
- `data-l2`
- `frontend`

## Entrypoints

- `api_server.py`
- `session_runner.py`

## File Inventory

| File | Exists | Lines | Last Commit |
|---|---:|---:|---|
| `api_server.py` | yes | 1052 | `2971a5a 2026-02-06` |
| `session_runner.py` | yes | 510 | `2971a5a 2026-02-06` |
| `data_loader.py` | yes | 267 | `583f2bc 2026-02-06` |
| `src/config_io.py` | yes | 106 | `2971a5a 2026-02-06` |
| `src/l2_feature_service.py` | yes | 189 | `2971a5a 2026-02-06` |

## Change Checks

- Keep API contracts backward compatible where possible.
- Always preserve no-lookahead semantics in bar stepping.
- Update tests for request model changes.

## Prompt Primer

Load this file plus `bmad/context/generated/00-index.md`, then keep edits scoped to the file inventory unless interface changes are explicitly required.
