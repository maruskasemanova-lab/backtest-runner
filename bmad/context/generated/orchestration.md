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
| `api_server.py` | yes | 1879 | `0452b19 2026-02-13` |
| `session_runner.py` | yes | 848 | `0452b19 2026-02-13` |
| `data_loader.py` | yes | 300 | `baf7110 2026-02-07` |
| `available_data.py` | yes | 224 | `baf7110 2026-02-07` |
| `decision_tracker.py` | yes | 440 | `64da33c 2026-02-10` |
| `performance_tracker.py` | yes | 822 | `13f270b 2026-02-06` |
| `src/routes/context.py` | yes | 42 | `0452b19 2026-02-13` |
| `src/routes/system_routes.py` | yes | 31 | `da07c20 2026-02-12` |
| `src/routes/l2_routes.py` | yes | 51 | `da07c20 2026-02-12` |
| `src/routes/data_loader_routes.py` | yes | 236 | `da07c20 2026-02-12` |
| `src/routes/live_trader_routes.py` | yes | 68 | `da07c20 2026-02-12` |
| `src/routes/config_read_routes.py` | yes | 78 | `da07c20 2026-02-12` |
| `src/routes/config_write_routes.py` | yes | 64 | `da07c20 2026-02-12` |
| `src/routes/run_routes.py` | yes | 186 | `0452b19 2026-02-13` |
| `src/routes/adaptive_tuner_routes.py` | yes | 38 | `da07c20 2026-02-12` |
| `src/routes/run_start_routes.py` | yes | 33 | `0452b19 2026-02-13` |
| `src/models/config_requests.py` | yes | 32 | `da07c20 2026-02-12` |
| `src/models/run_requests.py` | yes | 103 | `0452b19 2026-02-13` |
| `src/models/tuner_requests.py` | yes | 83 | `0452b19 2026-02-13` |
| `src/services/live_trader_service.py` | yes | 255 | `da07c20 2026-02-12` |
| `src/services/run_registry.py` | yes | 21 | `da07c20 2026-02-12` |
| `src/services/config_write_service.py` | yes | 264 | `da07c20 2026-02-12` |
| `src/services/run_control_service.py` | yes | 294 | `0452b19 2026-02-13` |
| `src/services/adaptive_tuner_orchestration_service.py` | yes | 161 | `da07c20 2026-02-12` |
| `src/services/adaptive_tuner_worker_service.py` | yes | 601 | `da07c20 2026-02-12` |
| `src/services/adaptive_tuner_core_service.py` | yes | 508 | `0452b19 2026-02-13` |
| `src/services/adaptive_tuner_search_service.py` | yes | 270 | `0452b19 2026-02-13` |
| `src/services/adaptive_tuner_runtime_service.py` | yes | 419 | `0452b19 2026-02-13` |
| `src/services/adaptive_tuner_v2_service.py` | yes | 796 | `0452b19 2026-02-13` |
| `src/services/strategy_api_types.py` | yes | 23 | `0452b19 2026-02-13` |
| `src/services/strategy_api_updates_service.py` | yes | 206 | `0452b19 2026-02-13` |
| `src/services/strategy_api_profiles_service.py` | yes | 390 | `0452b19 2026-02-13` |
| `src/services/strategy_api_session_service.py` | yes | 245 | `0452b19 2026-02-13` |
| `src/services/start_run_service.py` | yes | 907 | `0452b19 2026-02-13` |
| `src/services/start_run_data_service.py` | yes | 1013 | `0452b19 2026-02-13` |
| `src/services/start_run_execution_config_service.py` | yes | 454 | `0452b19 2026-02-13` |
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
- `function` `_parse_bool_env` (line 250)
- `function` `_parse_startup_prewarm_tickers` (line 261)
- `function` `_run_startup_prewarm_request_sync` (line 288)
- `function` `_refresh_runtime_data_services` (line 293)
- `async_function` `_broadcast_with_api_services` (line 304)
- `function` `_build_config_write_deps` (line 339)
- `function` `_build_run_control_deps` (line 361)
- `function` `_build_adaptive_tuner_deps` (line 374)
- `function` `_build_adaptive_tuner_worker_deps` (line 390)
- `function` `_build_adaptive_tuner_runtime_deps` (line 416)
- `function` `_build_adaptive_tuner_v2_deps` (line 436)
- `function` `_build_strategy_api_integration_deps` (line 454)
- ... 125 more symbols

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
- `function` `get_api_services` (line 38)

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
- `async_function` `get_run_state_endpoint` (line 28)
- `async_function` `step_run_endpoint` (line 39)
- `async_function` `play_run_endpoint` (line 50)
- `async_function` `pause_run_endpoint` (line 72)
- `async_function` `resume_run_endpoint` (line 83)
- `async_function` `stop_run_endpoint` (line 94)
- `async_function` `restart_run_endpoint` (line 105)
- `async_function` `get_processed_bars_endpoint` (line 116)
- `async_function` `get_bar_details_endpoint` (line 127)
- `async_function` `get_markers_endpoint` (line 139)
- `async_function` `get_chart_annotations_endpoint` (line 151)
- `async_function` `get_run_summary_endpoint` (line 162)
- ... 2 more symbols

### `src/routes/adaptive_tuner_routes.py`
- `async_function` `run_adaptive_tuner_endpoint` (line 15)
- `async_function` `get_adaptive_tuner_job_endpoint` (line 24)
- `async_function` `list_adaptive_tuner_jobs_endpoint` (line 33)

### `src/routes/run_start_routes.py`
- `async_function` `start_run_endpoint` (line 11)
- `async_function` `prewarm_run_endpoint` (line 20)
- `async_function` `flush_run_cache_endpoint` (line 29)

### `src/models/config_requests.py`
- `class` `AdaptiveTunerProfileApplyRequest` (line 6)
- `class` `StrategyComboCaptureRequest` (line 11)
- `class` `StrategyComboApplyRequest` (line 18)
- `class` `AOSUpdateRequest` (line 25)
- `class` `PositioningUpdateRequest` (line 30)

### `src/models/run_requests.py`
- `class` `StartRunRequest` (line 6)
- `class` `PrewarmRunRequest` (line 72)
- `class` `PlayRequest` (line 97)

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
- `function` `get_run_state` (line 24)
- `async_function` `step_run` (line 29)
- `async_function` `play_run` (line 34)
- `function` `pause_run` (line 137)
- `function` `resume_run` (line 143)
- `function` `stop_run` (line 149)
- `async_function` `restart_run` (line 155)
- `function` `get_processed_bars` (line 199)
- `function` `get_bar_details` (line 208)
- `function` `get_markers` (line 254)
- `function` `get_chart_annotations` (line 271)
- ... 3 more symbols

### `src/services/adaptive_tuner_orchestration_service.py`
- `class` `AdaptiveTunerOrchestrationDeps` (line 11)
- `async_function` `run_adaptive_tuner` (line 25)
- `function` `get_adaptive_tuner_job` (line 145)
- `function` `list_adaptive_tuner_jobs` (line 153)

### `src/services/adaptive_tuner_worker_service.py`
- `class` `AdaptiveTunerWorkerDeps` (line 13)
- `async_function` `run_v2_adaptive_tuner_job` (line 37)
- `async_function` `run_adaptive_tuner_job` (line 361)

### `src/services/adaptive_tuner_core_service.py`
- `function` `normalize_strategy_selection_mode` (line 10)
- `function` `normalize_non_negative_int` (line 15)
- `function` `normalize_clamped_int` (line 27)
- `function` `normalize_bool_options` (line 40)
- `function` `normalize_int_options` (line 54)
- `function` `normalize_mode_options` (line 74)
- `function` `normalize_float_options` (line 89)
- `function` `normalize_strategy_sets` (line 114)
- `function` `normalize_regime_filter_sets` (line 140)
- `function` `normalize_time_window_sets` (line 174)
- `function` `normalize_regime_strategy_map_sets` (line 207)
- `function` `iter_date_strings` (line 262)
- ... 10 more symbols

### `src/services/adaptive_tuner_search_service.py`
- `function` `candidate_key` (line 20)
- `function` `build_adaptive_tuner_search_space` (line 31)
- `function` `build_grid_candidates` (line 61)
- `function` `build_random_candidates` (line 84)
- `function` `build_adaptive_candidate_config` (line 113)
- `function` `compute_tuner_score` (line 142)
- `function` `compute_tuner_score_robust` (line 169)
- `function` `build_tuner_profile_entry` (line 237)

### `src/services/adaptive_tuner_runtime_service.py`
- `class` `AdaptiveTunerRuntimeDeps` (line 14)
- `async_function` `evaluate_adaptive_tuner_candidate` (line 32)
- `async_function` `evaluate_v2_candidate` (line 160)
- `async_function` `persist_tuner_result_to_primary_aos` (line 341)

### `src/services/adaptive_tuner_v2_service.py`
- `class` `AdaptiveTunerV2Deps` (line 12)
- `function` `build_v2_search_space` (line 28)
- `function` `v2_candidate_key` (line 250)
- `function` `build_v2_baseline_candidate` (line 296)
- `function` `build_v2_random_candidates` (line 351)
- `function` `build_v2_candidate_config` (line 492)
- `function` `analyze_vectors` (line 653)

### `src/services/strategy_api_types.py`
- `class` `StrategyApiIntegrationDeps` (line 8)

### `src/services/strategy_api_updates_service.py`
- `function` `_parse_positive_int_env` (line 13)
- `function` `_parse_positive_float_env` (line 23)
- `async_function` `_post_strategy_update` (line 47)
- `async_function` `_run_strategy_updates` (line 64)
- `async_function` `apply_strategy_overrides` (line 92)
- `async_function` `fetch_remote_strategies` (line 118)
- `async_function` `apply_strategy_param_map` (line 135)
- `async_function` `apply_global_trailing` (line 168)

### `src/services/strategy_api_profiles_service.py`
- `function` `_parse_positive_float_env` (line 11)
- `function` `normalize_strategy_key` (line 31)
- `function` `resolve_active_adaptive_tuner_candidate` (line 38)
- `function` `extract_profile_runtime_overrides` (line 65)
- `async_function` `apply_active_strategy_combo` (line 165)
- `async_function` `apply_active_adaptive_tuner_profile` (line 209)
- `async_function` `apply_aos_optimizations` (line 263)

### `src/services/strategy_api_session_service.py`
- `function` `_parse_positive_float_env` (line 11)
- `async_function` `configure_session` (line 31)
- `async_function` `clear_remote_strategy_sessions` (line 126)
- `async_function` `reset_remote_orchestrator_state` (line 151)
- `async_function` `reset_remote_orchestrator_state_scoped` (line 174)
- `async_function` `load_remote_checkpoint` (line 191)
- `async_function` `save_remote_checkpoint` (line 213)

### `src/services/start_run_service.py`
- `function` `_parse_non_negative_int_env` (line 24)
- `function` `_parse_bool_env` (line 34)
- `class` `StartRunDeps` (line 61)
- `function` `_resolve_request_range` (line 88)
- `function` `_resolve_local_aos_applied` (line 96)
- `function` `_canonical_trading_hours` (line 158)
- `function` `_build_prewarm_cache_key` (line 175)
- `function` `_resolve_prewarm_scope_range` (line 203)
- `function` `_inclusive_day_span` (line 249)
- `function` `_normalize_reset_scope` (line 259)
- `async_function` `start_run` (line 266)
- `async_function` `prewarm_run_data` (line 755)

### `src/services/start_run_data_service.py`
- `function` `_parse_positive_int_env` (line 17)
- `function` `clear_start_run_data_caches` (line 54)
- `function` `_cache_get` (line 74)
- `function` `_cache_set` (line 83)
- `function` `_disk_cache_path` (line 103)
- `function` `_ensure_disk_cache_dir` (line 108)
- `function` `_prune_disk_cache` (line 112)
- `function` `_disk_cache_get` (line 148)
- `function` `_disk_cache_set` (line 165)
- `function` `_count_disk_cache_entries` (line 178)
- `function` `_disk_cache_total_bytes` (line 185)
- `function` `_prune_all_disk_caches` (line 199)
- ... 23 more symbols

### `src/services/start_run_execution_config_service.py`
- `function` `resolve_execution_config` (line 6)

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
| `POST` | `/api/run/{run_id}/{ticker}/{date}/restart` | `restart_run_endpoint` | `src/routes/run_routes.py` |
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
| `POST` | `/api/run/prewarm` | `prewarm_run_endpoint` | `src/routes/run_start_routes.py` |
| `POST` | `/api/run/cache/flush` | `flush_run_cache_endpoint` | `src/routes/run_start_routes.py` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
