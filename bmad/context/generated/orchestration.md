# Domain: Run Orchestration API

**ID:** `orchestration`

## Mission

Own run lifecycle, API contracts, data routing, and integration to strategy service.

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
| `api_server.py` | yes | 4296 | `64da33c 2026-02-10` |
| `session_runner.py` | yes | 828 | `64da33c 2026-02-10` |
| `data_loader.py` | yes | 300 | `baf7110 2026-02-07` |
| `available_data.py` | yes | 224 | `baf7110 2026-02-07` |
| `decision_tracker.py` | yes | 440 | `64da33c 2026-02-10` |
| `performance_tracker.py` | yes | 822 | `13f270b 2026-02-06` |
| `src/config_io.py` | yes | 28 | `64da33c 2026-02-10` |
| `src/system_settings.py` | yes | 172 | `baf7110 2026-02-07` |
| `src/databento_service.py` | yes | 1106 | `64da33c 2026-02-10` |
| `src/databento_live.py` | yes | 107 | `baf7110 2026-02-07` |

## Change Checks

- Keep API contracts backward compatible where possible.
- Always preserve no-lookahead semantics in bar stepping.
- Keep comparable_mode and checkpoint behavior deterministic.
- Update tests for request model changes.

## Critical Invariants

- Runner must never use future bars when building payloads.
- Run key identity remains run_id:ticker:date_or_range.
- Runner -> strategy config passthrough keeps explicit execution defaults.
- Comparable mode must force cold start and ignore checkpoint warm-start.

## Test Targets

- `tests/test_no_lookahead.py`
- `tests/test_session_runner_markers.py`
- `tests/test_decision_tracker_schema_v2.py`
- `tests/test_data_loader_path_resolution.py`
- `tests/test_day_trading_manager_session_reset.py`

## Key Symbols

### `api_server.py`
- `function` `_load_strategy_overrides` (line 69)
- `function` `_load_aos_config` (line 73)
- `function` `_save_aos_config` (line 78)
- `function` `_normalize_strategy_selection_mode` (line 86)
- `function` `_normalize_non_negative_int` (line 91)
- `function` `_normalize_clamped_int` (line 99)
- `function` `_normalize_bool_options` (line 107)
- `function` `_normalize_int_options` (line 121)
- `function` `_normalize_mode_options` (line 141)
- `function` `_normalize_float_options` (line 156)
- `function` `_normalize_strategy_sets` (line 181)
- `function` `_normalize_regime_filter_sets` (line 208)
- ... 107 more symbols

### `session_runner.py`
- `class` `RunConfig` (line 19)
- `class` `SessionRunner` (line 34)

### `data_loader.py`
- `class` `DataLoader` (line 15)

### `available_data.py`
- `class` `TickerData` (line 21)
- `class` `DataDiscovery` (line 30)
- `function` `get_discovery` (line 213)
- `function` `reset_discovery` (line 221)

### `decision_tracker.py`
- `class` `MarkerType` (line 11)
- `class` `DecisionMarker` (line 26)
- `class` `DecisionTracker` (line 58)

### `performance_tracker.py`
- `class` `Regime` (line 15)
- `class` `TradeRecord` (line 23)
- `class` `StrategyPerformance` (line 74)
- `class` `PerformanceTracker` (line 268)
- `function` `create_tracker` (line 762)

### `src/config_io.py`
- `function` `load_json_file` (line 11)
- `function` `save_json_file` (line 21)

### `src/system_settings.py`
- `function` `_normalize_dirs` (line 20)
- `function` `mask_secret` (line 42)
- `class` `SystemSettings` (line 51)

### `src/databento_service.py`
- `class` `CatalogEntry` (line 31)
- `class` `DataCatalog` (line 50)
- `class` `DatabentoService` (line 115)

### `src/databento_live.py`
- `class` `DatabentoLiveClient` (line 20)

## Endpoint Summary

| Method | Path | Handler | File |
|---|---|---|---|
| `WEBSOCKET` | `/ws/live` | `websocket_endpoint` | `api_server.py` |
| `GET` | `/` | `root` | `api_server.py` |
| `GET` | `/api/health` | `health` | `api_server.py` |
| `GET` | `/api/available-data` | `get_available_data` | `api_server.py` |
| `GET` | `/api/strategy-overrides` | `get_strategy_overrides` | `api_server.py` |
| `GET` | `/api/strategy-overrides/{ticker}` | `get_ticker_overrides` | `api_server.py` |
| `GET` | `/api/strategy-combos/{ticker}` | `get_strategy_combos` | `api_server.py` |
| `POST` | `/api/strategy-combos/capture` | `capture_strategy_combo` | `api_server.py` |
| `POST` | `/api/strategy-combos/apply` | `apply_strategy_combo` | `api_server.py` |
| `GET` | `/api/data/files` | `list_data_files` | `api_server.py` |
| `GET` | `/api/aos-config` | `get_aos_config` | `api_server.py` |
| `GET` | `/api/aos-config/{ticker}` | `get_ticker_aos_config` | `api_server.py` |
| `POST` | `/api/aos-config/update` | `update_aos_config` | `api_server.py` |
| `GET` | `/api/adaptive-tuner/options/{ticker}` | `get_adaptive_tuner_options` | `api_server.py` |
| `POST` | `/api/adaptive-tuner/profiles/apply` | `apply_adaptive_tuner_profile` | `api_server.py` |
| `POST` | `/api/adaptive-tuner/run` | `run_adaptive_tuner` | `api_server.py` |
| `GET` | `/api/adaptive-tuner/{job_id}` | `get_adaptive_tuner_job` | `api_server.py` |
| `GET` | `/api/adaptive-tuner` | `list_adaptive_tuner_jobs` | `api_server.py` |
| `POST` | `/api/run/start` | `start_run` | `api_server.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/state` | `get_run_state` | `api_server.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/step` | `step_run` | `api_server.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/play` | `play_run` | `api_server.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/pause` | `pause_run` | `api_server.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/resume` | `resume_run` | `api_server.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/stop` | `stop_run` | `api_server.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/bars` | `get_processed_bars` | `api_server.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/bar-details/{minute_key}` | `get_bar_details` | `api_server.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/markers` | `get_markers` | `api_server.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/chart-annotations` | `get_chart_annotations` | `api_server.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/summary` | `get_run_summary` | `api_server.py` |
| `DELETE` | `/api/run/{run_id}/{ticker}/{date}` | `delete_run` | `api_server.py` |
| `GET` | `/api/runs` | `list_runs` | `api_server.py` |
| `GET` | `/api/l2/footprint/{ticker}` | `get_footprint_data` | `api_server.py` |
| `GET` | `/api/l2/icebergs/{ticker}` | `get_icebergs` | `api_server.py` |
| `GET` | `/api/data-loader/catalog` | `get_data_catalog` | `api_server.py` |
| `GET` | `/api/data-loader/catalog/{ticker}` | `get_ticker_catalog` | `api_server.py` |
| `GET` | `/api/data-loader/settings` | `get_data_loader_settings` | `api_server.py` |
| `PUT` | `/api/data-loader/settings` | `update_data_loader_settings` | `api_server.py` |
| `PUT` | `/api/data-loader/api-key` | `set_databento_api_key` | `api_server.py` |
| `GET` | `/api/data-loader/schemas` | `get_supported_schemas` | `api_server.py` |
| `POST` | `/api/data-loader/cost-estimate` | `get_cost_estimate` | `api_server.py` |
| `POST` | `/api/data-loader/download` | `start_download` | `api_server.py` |
| `GET` | `/api/data-loader/downloads/active` | `get_active_downloads` | `api_server.py` |
| `DELETE` | `/api/data-loader/entry` | `delete_data_entry` | `api_server.py` |
| `POST` | `/api/data-loader/scan` | `scan_existing_data` | `api_server.py` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
