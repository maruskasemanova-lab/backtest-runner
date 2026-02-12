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
| `api_server.py` | yes | 2674 | `1feb58e 2026-02-12` |
| `session_runner.py` | yes | 828 | `17d2b9d 2026-02-11` |
| `data_loader.py` | yes | 300 | `baf7110 2026-02-07` |
| `available_data.py` | yes | 224 | `baf7110 2026-02-07` |
| `decision_tracker.py` | yes | 440 | `64da33c 2026-02-10` |
| `performance_tracker.py` | yes | 822 | `13f270b 2026-02-06` |
| `src/routes/context.py` | yes | 41 | `-` |
| `src/routes/system_routes.py` | yes | 31 | `-` |
| `src/routes/l2_routes.py` | yes | 51 | `-` |
| `src/routes/data_loader_routes.py` | yes | 236 | `-` |
| `src/routes/live_trader_routes.py` | yes | 68 | `-` |
| `src/routes/config_read_routes.py` | yes | 78 | `-` |
| `src/routes/config_write_routes.py` | yes | 64 | `-` |
| `src/routes/run_routes.py` | yes | 174 | `-` |
| `src/routes/adaptive_tuner_routes.py` | yes | 38 | `-` |
| `src/routes/run_start_routes.py` | yes | 15 | `-` |
| `src/models/config_requests.py` | yes | 32 | `-` |
| `src/models/run_requests.py` | yes | 66 | `-` |
| `src/models/tuner_requests.py` | yes | 78 | `-` |
| `src/services/live_trader_service.py` | yes | 255 | `-` |
| `src/services/run_registry.py` | yes | 21 | `-` |
| `src/services/config_write_service.py` | yes | 264 | `-` |
| `src/services/run_control_service.py` | yes | 223 | `-` |
| `src/services/adaptive_tuner_orchestration_service.py` | yes | 161 | `-` |
| `src/services/adaptive_tuner_worker_service.py` | yes | 601 | `-` |
| `src/services/adaptive_tuner_runtime_service.py` | yes | 412 | `-` |
| `src/services/adaptive_tuner_v2_service.py` | yes | 735 | `-` |
| `src/services/start_run_service.py` | yes | 884 | `-` |
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
- `function` `_refresh_runtime_data_services` (line 199)
- `async_function` `_broadcast_with_api_services` (line 210)
- `function` `_build_config_write_deps` (line 244)
- `function` `_build_run_control_deps` (line 266)
- `function` `_build_adaptive_tuner_deps` (line 278)
- `function` `_build_adaptive_tuner_worker_deps` (line 294)
- `function` `_build_adaptive_tuner_runtime_deps` (line 320)
- `function` `_build_adaptive_tuner_v2_deps` (line 340)
- `function` `_build_start_run_deps` (line 358)
- `function` `_load_strategy_overrides` (line 402)
- `function` `_resolve_aos_config_path` (line 406)
- `function` `_load_aos_config` (line 416)
- ... 116 more symbols

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

### `src/routes/context.py`
- `class` `ApiServices` (line 9)
- `function` `get_api_services` (line 37)

### `src/routes/system_routes.py`
- `async_function` `root` (line 9)
- `async_function` `health` (line 18)
- `async_function` `get_available_data` (line 23)
- `async_function` `list_data_files` (line 29)

### `src/routes/l2_routes.py`
- `async_function` `get_footprint_data` (line 11)
- `async_function` `get_icebergs` (line 34)

### `src/routes/data_loader_routes.py`
- `class` `DownloadRequest` (line 13)
- `class` `CostEstimateRequest` (line 22)
- `class` `DeleteDataRequest` (line 30)
- `class` `DataSettingsRequest` (line 37)
- `class` `DatabentoApiKeyRequest` (line 42)
- `async_function` `get_data_catalog` (line 47)
- `async_function` `get_ticker_catalog` (line 68)
- `async_function` `get_data_loader_settings` (line 77)
- `async_function` `update_data_loader_settings` (line 83)
- `async_function` `set_databento_api_key` (line 101)
- `async_function` `get_supported_schemas` (line 114)
- `async_function` `get_cost_estimate` (line 120)
- ... 4 more symbols

### `src/routes/live_trader_routes.py`
- `async_function` `list_live_trader_runs` (line 14)
- `async_function` `get_live_trader_events` (line 37)
- `async_function` `get_live_trader_snapshot` (line 55)

### `src/routes/config_read_routes.py`
- `async_function` `get_strategy_overrides` (line 11)
- `async_function` `get_ticker_overrides` (line 17)
- `async_function` `get_strategy_combos` (line 24)
- `async_function` `get_aos_config` (line 30)
- `async_function` `get_ticker_aos_config` (line 38)
- `async_function` `get_positioning_config` (line 64)
- `async_function` `get_ticker_positioning_config` (line 70)
- `async_function` `get_adaptive_tuner_options` (line 76)

### `src/routes/config_write_routes.py`
- `async_function` `capture_strategy_combo_endpoint` (line 23)
- `async_function` `apply_strategy_combo_endpoint` (line 32)
- `async_function` `update_aos_config_endpoint` (line 41)
- `async_function` `update_positioning_config_endpoint` (line 50)
- `async_function` `apply_adaptive_tuner_profile_endpoint` (line 59)

### `src/routes/run_routes.py`
- `async_function` `get_run_state_endpoint` (line 27)
- `async_function` `step_run_endpoint` (line 38)
- `async_function` `play_run_endpoint` (line 49)
- `async_function` `pause_run_endpoint` (line 71)
- `async_function` `resume_run_endpoint` (line 82)
- `async_function` `stop_run_endpoint` (line 93)
- `async_function` `get_processed_bars_endpoint` (line 104)
- `async_function` `get_bar_details_endpoint` (line 115)
- `async_function` `get_markers_endpoint` (line 127)
- `async_function` `get_chart_annotations_endpoint` (line 139)
- `async_function` `get_run_summary_endpoint` (line 150)
- `async_function` `delete_run_endpoint` (line 161)
- ... 1 more symbols

### `src/routes/adaptive_tuner_routes.py`
- `async_function` `run_adaptive_tuner_endpoint` (line 15)
- `async_function` `get_adaptive_tuner_job_endpoint` (line 24)
- `async_function` `list_adaptive_tuner_jobs_endpoint` (line 33)

### `src/routes/run_start_routes.py`
- `async_function` `start_run_endpoint` (line 10)

### `src/models/config_requests.py`
- `class` `AdaptiveTunerProfileApplyRequest` (line 6)
- `class` `StrategyComboCaptureRequest` (line 11)
- `class` `StrategyComboApplyRequest` (line 18)
- `class` `AOSUpdateRequest` (line 25)
- `class` `PositioningUpdateRequest` (line 30)

### `src/models/run_requests.py`
- `class` `StartRunRequest` (line 6)
- `class` `PlayRequest` (line 64)

### `src/models/tuner_requests.py`
- `class` `AdaptiveTunerRequest` (line 6)

### `src/services/live_trader_service.py`
- `function` `sanitize_live_run_id` (line 14)
- `function` `live_artifact_file` (line 23)
- `function` `read_jsonl_tail` (line 28)
- `function` `parse_utc_iso` (line 53)
- `function` `extract_runtime_summary` (line 68)
- `function` `infer_live_run_status` (line 99)
- `function` `discover_live_trader_runs` (line 117)
- `function` `live_trader_events_payload` (line 180)
- `function` `live_trader_snapshot_payload` (line 205)

### `src/services/run_registry.py`
- `class` `RunRegistry` (line 6)

### `src/services/config_write_service.py`
- `class` `ConfigWriteDeps` (line 8)
- `async_function` `capture_strategy_combo` (line 27)
- `async_function` `apply_strategy_combo` (line 72)
- `function` `update_aos_config` (line 120)
- `function` `update_positioning_config` (line 189)
- `function` `apply_adaptive_tuner_profile` (line 210)

### `src/services/run_control_service.py`
- `class` `RunControlDeps` (line 13)
- `function` `get_run_state` (line 23)
- `async_function` `step_run` (line 28)
- `async_function` `play_run` (line 33)
- `function` `pause_run` (line 110)
- `function` `resume_run` (line 116)
- `function` `stop_run` (line 122)
- `function` `get_processed_bars` (line 128)
- `function` `get_bar_details` (line 137)
- `function` `get_markers` (line 183)
- `function` `get_chart_annotations` (line 200)
- `function` `get_run_summary` (line 205)
- ... 2 more symbols

### `src/services/adaptive_tuner_orchestration_service.py`
- `class` `AdaptiveTunerOrchestrationDeps` (line 11)
- `async_function` `run_adaptive_tuner` (line 25)
- `function` `get_adaptive_tuner_job` (line 145)
- `function` `list_adaptive_tuner_jobs` (line 153)

### `src/services/adaptive_tuner_worker_service.py`
- `class` `AdaptiveTunerWorkerDeps` (line 13)
- `async_function` `run_v2_adaptive_tuner_job` (line 37)
- `async_function` `run_adaptive_tuner_job` (line 361)

### `src/services/adaptive_tuner_runtime_service.py`
- `class` `AdaptiveTunerRuntimeDeps` (line 14)
- `async_function` `evaluate_adaptive_tuner_candidate` (line 32)
- `async_function` `evaluate_v2_candidate` (line 160)
- `async_function` `persist_tuner_result_to_primary_aos` (line 334)

### `src/services/adaptive_tuner_v2_service.py`
- `class` `AdaptiveTunerV2Deps` (line 12)
- `function` `build_v2_search_space` (line 28)
- `function` `v2_candidate_key` (line 220)
- `function` `build_v2_baseline_candidate` (line 261)
- `function` `build_v2_random_candidates` (line 311)
- `function` `build_v2_candidate_config` (line 436)
- `function` `analyze_vectors` (line 592)

### `src/services/start_run_service.py`
- `class` `StartRunDeps` (line 15)
- `async_function` `start_run` (line 40)

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
| `GET` | `/` | `root` | `src/routes/system_routes.py` |
| `GET` | `/api/health` | `health` | `src/routes/system_routes.py` |
| `GET` | `/api/available-data` | `get_available_data` | `src/routes/system_routes.py` |
| `GET` | `/api/data/files` | `list_data_files` | `src/routes/system_routes.py` |
| `GET` | `/api/l2/footprint/{ticker}` | `get_footprint_data` | `src/routes/l2_routes.py` |
| `GET` | `/api/l2/icebergs/{ticker}` | `get_icebergs` | `src/routes/l2_routes.py` |
| `GET` | `/api/data-loader/catalog` | `get_data_catalog` | `src/routes/data_loader_routes.py` |
| `GET` | `/api/data-loader/catalog/{ticker}` | `get_ticker_catalog` | `src/routes/data_loader_routes.py` |
| `GET` | `/api/data-loader/settings` | `get_data_loader_settings` | `src/routes/data_loader_routes.py` |
| `PUT` | `/api/data-loader/settings` | `update_data_loader_settings` | `src/routes/data_loader_routes.py` |
| `PUT` | `/api/data-loader/api-key` | `set_databento_api_key` | `src/routes/data_loader_routes.py` |
| `GET` | `/api/data-loader/schemas` | `get_supported_schemas` | `src/routes/data_loader_routes.py` |
| `POST` | `/api/data-loader/cost-estimate` | `get_cost_estimate` | `src/routes/data_loader_routes.py` |
| `POST` | `/api/data-loader/download` | `start_download` | `src/routes/data_loader_routes.py` |
| `GET` | `/api/data-loader/downloads/active` | `get_active_downloads` | `src/routes/data_loader_routes.py` |
| `DELETE` | `/api/data-loader/entry` | `delete_data_entry` | `src/routes/data_loader_routes.py` |
| `POST` | `/api/data-loader/scan` | `scan_existing_data` | `src/routes/data_loader_routes.py` |
| `GET` | `/api/live-trader/runs` | `list_live_trader_runs` | `src/routes/live_trader_routes.py` |
| `GET` | `/api/live-trader/events/{run_id}` | `get_live_trader_events` | `src/routes/live_trader_routes.py` |
| `GET` | `/api/live-trader/snapshot/{run_id}` | `get_live_trader_snapshot` | `src/routes/live_trader_routes.py` |
| `GET` | `/api/strategy-overrides` | `get_strategy_overrides` | `src/routes/config_read_routes.py` |
| `GET` | `/api/strategy-overrides/{ticker}` | `get_ticker_overrides` | `src/routes/config_read_routes.py` |
| `GET` | `/api/strategy-combos/{ticker}` | `get_strategy_combos` | `src/routes/config_read_routes.py` |
| `GET` | `/api/aos-config` | `get_aos_config` | `src/routes/config_read_routes.py` |
| `GET` | `/api/aos-config/{ticker}` | `get_ticker_aos_config` | `src/routes/config_read_routes.py` |
| `GET` | `/api/positioning-config` | `get_positioning_config` | `src/routes/config_read_routes.py` |
| `GET` | `/api/positioning-config/{ticker}` | `get_ticker_positioning_config` | `src/routes/config_read_routes.py` |
| `GET` | `/api/adaptive-tuner/options/{ticker}` | `get_adaptive_tuner_options` | `src/routes/config_read_routes.py` |
| `POST` | `/api/strategy-combos/capture` | `capture_strategy_combo_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/strategy-combos/apply` | `apply_strategy_combo_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/aos-config/update` | `update_aos_config_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/positioning-config/update` | `update_positioning_config_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/adaptive-tuner/profiles/apply` | `apply_adaptive_tuner_profile_endpoint` | `src/routes/config_write_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/state` | `get_run_state_endpoint` | `src/routes/run_routes.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/step` | `step_run_endpoint` | `src/routes/run_routes.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/play` | `play_run_endpoint` | `src/routes/run_routes.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/pause` | `pause_run_endpoint` | `src/routes/run_routes.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/resume` | `resume_run_endpoint` | `src/routes/run_routes.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/stop` | `stop_run_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/bars` | `get_processed_bars_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/bar-details/{minute_key}` | `get_bar_details_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/markers` | `get_markers_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/chart-annotations` | `get_chart_annotations_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/summary` | `get_run_summary_endpoint` | `src/routes/run_routes.py` |
| `DELETE` | `/api/run/{run_id}/{ticker}/{date}` | `delete_run_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/runs` | `list_runs_endpoint` | `src/routes/run_routes.py` |
| `POST` | `/api/adaptive-tuner/run` | `run_adaptive_tuner_endpoint` | `src/routes/adaptive_tuner_routes.py` |
| `GET` | `/api/adaptive-tuner/{job_id}` | `get_adaptive_tuner_job_endpoint` | `src/routes/adaptive_tuner_routes.py` |
| `GET` | `/api/adaptive-tuner` | `list_adaptive_tuner_jobs_endpoint` | `src/routes/adaptive_tuner_routes.py` |
| `POST` | `/api/run/start` | `start_run_endpoint` | `src/routes/run_start_routes.py` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
