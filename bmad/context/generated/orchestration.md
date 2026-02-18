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
| `api_server.py` | yes | 2559 | `172e737 2026-02-16` |
| `session_runner.py` | yes | 1127 | `172e737 2026-02-16` |
| `data_loader.py` | yes | 301 | `baf7110 2026-02-07` |
| `available_data.py` | yes | 224 | `baf7110 2026-02-07` |
| `decision_tracker.py` | yes | 440 | `64da33c 2026-02-10` |
| `performance_tracker.py` | yes | 822 | `13f270b 2026-02-06` |
| `src/routes/context.py` | yes | 44 | `38387c6 2026-02-13` |
| `src/routes/system_routes.py` | yes | 1618 | `172e737 2026-02-16` |
| `src/routes/l2_routes.py` | yes | 116 | `da07c20 2026-02-12` |
| `src/routes/data_loader_routes.py` | yes | 283 | `da07c20 2026-02-12` |
| `src/routes/live_trader_routes.py` | yes | 68 | `da07c20 2026-02-12` |
| `src/routes/config_read_routes.py` | yes | 84 | `da07c20 2026-02-12` |
| `src/routes/config_write_routes.py` | yes | 86 | `da07c20 2026-02-12` |
| `src/routes/run_routes.py` | yes | 186 | `0452b19 2026-02-13` |
| `src/routes/adaptive_tuner_routes.py` | yes | 38 | `da07c20 2026-02-12` |
| `src/routes/run_start_routes.py` | yes | 334 | `172e737 2026-02-16` |
| `src/routes/v2_routes.py` | yes | 1825 | `-` |
| `src/models/config_requests.py` | yes | 47 | `da07c20 2026-02-12` |
| `src/models/run_requests.py` | yes | 115 | `172e737 2026-02-16` |
| `src/models/tuner_requests.py` | yes | 93 | `38387c6 2026-02-13` |
| `src/security/auth.py` | yes | 252 | `-` |
| `src/security/network_policy.py` | yes | 103 | `-` |
| `src/observability/runtime_metrics.py` | yes | 70 | `-` |
| `src/services/live_trader_service.py` | yes | 255 | `da07c20 2026-02-12` |
| `src/services/run_registry.py` | yes | 28 | `da07c20 2026-02-12` |
| `src/services/config_write_service.py` | yes | 656 | `da07c20 2026-02-12` |
| `src/services/run_control_service.py` | yes | 368 | `172e737 2026-02-16` |
| `src/services/saas_service.py` | yes | 1983 | `-` |
| `src/services/adaptive_tuner_orchestration_service.py` | yes | 161 | `da07c20 2026-02-12` |
| `src/services/adaptive_tuner_worker_service.py` | yes | 601 | `da07c20 2026-02-12` |
| `src/services/adaptive_tuner_core_service.py` | yes | 519 | `0452b19 2026-02-13` |
| `src/services/adaptive_tuner_search_service.py` | yes | 270 | `0452b19 2026-02-13` |
| `src/services/adaptive_tuner_runtime_service.py` | yes | 458 | `172e737 2026-02-16` |
| `src/services/adaptive_tuner_v2_service.py` | yes | 923 | `38387c6 2026-02-13` |
| `src/services/strategy_api_types.py` | yes | 25 | `172e737 2026-02-16` |
| `src/services/strategy_api_updates_service.py` | yes | 249 | `0452b19 2026-02-13` |
| `src/services/strategy_api_profiles_service.py` | yes | 792 | `172e737 2026-02-16` |
| `src/services/strategy_api_session_service.py` | yes | 291 | `172e737 2026-02-16` |
| `src/services/start_run_service.py` | yes | 1563 | `172e737 2026-02-16` |
| `src/services/start_run_data_service.py` | yes | 1194 | `172e737 2026-02-16` |
| `src/services/start_run_execution_config_service.py` | yes | 588 | `172e737 2026-02-16` |
| `src/config_io.py` | yes | 28 | `64da33c 2026-02-10` |
| `src/system_settings.py` | yes | 172 | `baf7110 2026-02-07` |
| `src/databento_service.py` | yes | 1728 | `64da33c 2026-02-10` |
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
- `function` `_build_cors_allow_origin_regex` (line 251)
- `function` `_parse_bool_env` (line 317)
- `function` `_parse_startup_prewarm_tickers` (line 328)
- `function` `_run_startup_prewarm_request_sync` (line 355)
- `function` `_refresh_runtime_data_services` (line 360)
- `async_function` `_broadcast_with_api_services` (line 372)
- `function` `_safe_env_int` (line 409)
- `function` `_safe_env_float` (line 418)
- `function` `_parse_bool_value` (line 427)
- `function` `_load_report_storage_config` (line 440)
- `function` `_build_supabase_user_settings_store` (line 454)
- `function` `_build_supabase_run_reports_store` (line 494)
- ... 146 more symbols

### `session_runner.py`
- `function` `_normalize_profile_token` (line 27)
- `class` `RunConfig` (line 37)
- `class` `SessionRunner` (line 55)

### `data_loader.py`
- `class` `DataLoader` (line 16)

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
- `function` `get_api_services` (line 40)

### `src/routes/system_routes.py`
- `function` `_project_root` (line 19)
- `function` `_diagnostic_cache_store` (line 23)
- `function` `_run_reports_store` (line 31)
- `function` `_run_reports_source_mode` (line 37)
- `function` `_external_report_dir_name` (line 49)
- `function` `_build_diagnostic_summary` (line 67)
- `function` `_sanitize_segment` (line 95)
- `function` `_coerce_non_negative_int` (line 105)
- `function` `_normalize_iso_date` (line 115)
- `function` `_parse_report_saved_at` (line 122)
- `function` `_parse_run_day_from_label` (line 135)
- `function` `_collect_strategy_names_from_trades` (line 145)
- ... 43 more symbols

### `src/routes/l2_routes.py`
- `async_function` `get_footprint_data` (line 12)
- `function` `_iceberg_epoch_seconds` (line 34)
- `async_function` `get_icebergs` (line 57)

### `src/routes/data_loader_routes.py`
- `class` `DownloadRequest` (line 22)
- `class` `CostEstimateRequest` (line 31)
- `class` `DeleteDataRequest` (line 39)
- `class` `DataSettingsRequest` (line 46)
- `class` `DatabentoApiKeyRequest` (line 51)
- `function` `_require_admin_access` (line 55)
- `async_function` `get_data_catalog` (line 78)
- `async_function` `sync_remote_catalog` (line 99)
- `async_function` `get_ticker_catalog` (line 113)
- `async_function` `get_data_loader_settings` (line 122)
- `async_function` `update_data_loader_settings` (line 128)
- `async_function` `set_databento_api_key` (line 146)
- ... 6 more symbols

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
- `async_function` `get_unified_profiles` (line 82)

### `src/routes/config_write_routes.py`
- `async_function` `capture_strategy_combo_endpoint` (line 27)
- `async_function` `apply_strategy_combo_endpoint` (line 36)
- `async_function` `update_aos_config_endpoint` (line 45)
- `async_function` `update_positioning_config_endpoint` (line 54)
- `async_function` `apply_adaptive_tuner_profile_endpoint` (line 63)
- `async_function` `capture_unified_profile_endpoint` (line 72)
- `async_function` `apply_unified_profile_endpoint` (line 81)

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
- `function` `_request_to_dict` (line 13)
- `function` `_preview_days` (line 19)
- `function` `_classify_start_error` (line 30)
- `function` `_inclusive_day_span` (line 49)
- `function` `_safe_range_coverage` (line 58)
- `async_function` `start_run_endpoint` (line 93)
- `async_function` `prewarm_run_endpoint` (line 102)
- `async_function` `prewarm_status_endpoint` (line 111)
- `async_function` `diagnose_run_start_endpoint` (line 120)
- `async_function` `flush_run_cache_endpoint` (line 330)

### `src/routes/v2_routes.py`
- `class` `BillingCheckoutRequest` (line 38)
- `class` `BillingPortalRequest` (line 45)
- `class` `V2UserSettingsUpdateRequest` (line 49)
- `class` `V2RunRequest` (line 53)
- `class` `V2AdaptiveTunerRequest` (line 58)
- `class` `V2DownloadRequest` (line 62)
- `class` `V2AdaptiveStrategyProfileRequest` (line 71)
- `function` `_request_id` (line 81)
- `function` `_detail` (line 86)
- `function` `_raise` (line 103)
- `function` `_parse_iso_day` (line 110)
- `function` `_normalize_ticker` (line 119)
- ... 64 more symbols

### `src/models/config_requests.py`
- `class` `AdaptiveTunerProfileApplyRequest` (line 6)
- `class` `StrategyComboCaptureRequest` (line 11)
- `class` `StrategyComboApplyRequest` (line 18)
- `class` `UnifiedProfileCaptureRequest` (line 25)
- `class` `UnifiedProfileApplyRequest` (line 32)
- `class` `AOSUpdateRequest` (line 40)
- `class` `PositioningUpdateRequest` (line 45)

### `src/models/run_requests.py`
- `class` `StartRunRequest` (line 6)
- `class` `PrewarmRunRequest` (line 81)
- `class` `PlayRequest` (line 108)

### `src/models/tuner_requests.py`
- `class` `AdaptiveTunerRequest` (line 6)

### `src/security/auth.py`
- `class` `AuthContext` (line 16)
- `class` `JwtValidationError` (line 25)
- `function` `_b64url_decode` (line 29)
- `function` `_b64url_encode` (line 37)
- `function` `parse_bearer_token` (line 41)
- `function` `_resolve_supabase_auth_verify_url` (line 51)
- `function` `_resolve_supabase_auth_verify_api_key` (line 62)
- `function` `_resolve_supabase_auth_verify_timeout_seconds` (line 73)
- `function` `_verify_jwt_via_supabase_auth` (line 82)
- `function` `decode_and_verify_jwt` (line 126)
- `function` `resolve_jwt_secret` (line 178)
- `function` `allow_unverified_jwt` (line 186)
- ... 5 more symbols

### `src/security/network_policy.py`
- `class` `StrategyApiPolicyError` (line 8)
- `function` `parse_csv_env` (line 12)
- `function` `normalize_base_url` (line 27)
- `function` `default_internal_strategy_api_url` (line 38)
- `function` `resolve_strategy_allowlist` (line 43)
- `function` `enforce_strategy_url_policy` (line 63)
- `function` `enforce_strategy_url_allowlist_only` (line 82)
- `function` `cors_allow_origins_from_env` (line 92)
- `function` `should_allow_credentials` (line 101)

### `src/observability/runtime_metrics.py`
- `function` `_percentile` (line 8)
- `class` `RuntimeMetrics` (line 25)

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
- `class` `RunRegistry` (line 11)

### `src/services/config_write_service.py`
- `class` `ConfigWriteDeps` (line 14)
- `function` `_utc_now_iso` (line 34)
- `function` `_normalize_trading_hours` (line 38)
- `function` `_resolve_active_adaptive_candidate` (line 55)
- `function` `_build_strategy_profile_snapshot` (line 85)
- `function` `_build_execution_profile_snapshot` (line 150)
- `async_function` `capture_unified_profile` (line 175)
- `async_function` `apply_unified_profile` (line 261)
- `async_function` `capture_strategy_combo` (line 405)
- `async_function` `apply_strategy_combo` (line 455)
- `function` `update_aos_config` (line 508)
- `function` `update_positioning_config` (line 577)
- ... 1 more symbols

### `src/services/run_control_service.py`
- `class` `RunControlDeps` (line 13)
- `function` `_runner_date_label` (line 25)
- `function` `_runner_run_key` (line 36)
- `async_function` `_persist_runner_summary_to_store` (line 48)
- `function` `get_run_state` (line 67)
- `async_function` `step_run` (line 72)
- `async_function` `play_run` (line 77)
- `function` `pause_run` (line 203)
- `function` `resume_run` (line 209)
- `function` `stop_run` (line 215)
- `async_function` `restart_run` (line 221)
- `function` `get_processed_bars` (line 267)
- ... 6 more symbols

### `src/services/saas_service.py`
- `class` `PlanLimits` (line 20)
- `function` `resolve_plan_limits` (line 64)
- `function` `utc_now_iso` (line 69)
- `function` `utc_day_key` (line 73)
- `function` `parse_utc_datetime` (line 79)
- `function` `normalize_user_settings_payload` (line 100)
- `class` `UserSettingsStore` (line 117)
- `class` `RunReportsStore` (line 131)
- `class` `SupabaseStoreRequestError` (line 148)
- `function` `normalize_run_summary_payload` (line 156)
- `class` `SupabaseUserSettingsStore` (line 171)
- `class` `SupabaseRunReportsStore` (line 476)
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
- `async_function` `evaluate_adaptive_tuner_candidate` (line 33)
- `async_function` `evaluate_v2_candidate` (line 161)
- `async_function` `persist_tuner_result_to_primary_aos` (line 380)

### `src/services/adaptive_tuner_v2_service.py`
- `class` `AdaptiveTunerV2Deps` (line 12)
- `function` `build_v2_search_space` (line 28)
- `function` `v2_candidate_key` (line 299)
- `function` `build_v2_baseline_candidate` (line 354)
- `function` `build_v2_random_candidates` (line 418)
- `function` `build_v2_candidate_config` (line 591)
- `function` `analyze_vectors` (line 780)

### `src/services/strategy_api_types.py`
- `class` `StrategyApiIntegrationDeps` (line 8)

### `src/services/strategy_api_updates_service.py`
- `function` `_parse_positive_int_env` (line 14)
- `function` `_parse_positive_float_env` (line 24)
- `function` `_strategy_api_headers` (line 48)
- `async_function` `_post_strategy_update` (line 52)
- `async_function` `_run_strategy_updates` (line 70)
- `async_function` `apply_strategy_overrides` (line 98)
- `async_function` `fetch_remote_strategies` (line 124)
- `async_function` `apply_strategy_param_map` (line 144)
- `async_function` `apply_global_trailing` (line 177)

### `src/services/strategy_api_profiles_service.py`
- `function` `_parse_positive_float_env` (line 12)
- `function` `_normalize_profile_ref_token` (line 34)
- `function` `_strategy_api_headers` (line 43)
- `function` `normalize_strategy_key` (line 47)
- `function` `resolve_active_adaptive_tuner_candidate` (line 54)
- `function` `resolve_active_unified_profile` (line 83)
- `function` `extract_profile_runtime_overrides` (line 104)
- `function` `_extract_unified_runtime_overrides` (line 227)
- `async_function` `apply_active_strategy_combo` (line 304)
- `async_function` `apply_active_adaptive_tuner_profile` (line 354)
- `async_function` `apply_aos_optimizations` (line 514)

### `src/services/strategy_api_session_service.py`
- `function` `_parse_positive_float_env` (line 12)
- `function` `_strategy_api_headers` (line 32)
- `async_function` `configure_session` (line 36)
- `async_function` `clear_remote_strategy_sessions` (line 138)
- `async_function` `reset_remote_orchestrator_state` (line 164)
- `async_function` `reset_remote_orchestrator_state_scoped` (line 188)
- `async_function` `apply_orchestrator_config` (line 206)
- `async_function` `load_remote_checkpoint` (line 235)
- `async_function` `save_remote_checkpoint` (line 258)

### `src/services/start_run_service.py`
- `function` `_parse_non_negative_int_env` (line 31)
- `function` `_parse_bool_env` (line 41)
- `function` `_acquire_prewarm_inflight` (line 83)
- `function` `_release_prewarm_inflight` (line 96)
- `function` `_is_prewarm_inflight` (line 103)
- `class` `StartRunDeps` (line 115)
- `function` `_resolve_request_range` (line 142)
- `function` `_resolve_local_aos_applied` (line 150)
- `function` `_normalize_profile_ref_token` (line 212)
- `function` `_first_profile_ref_token` (line 221)
- `function` `_extract_effective_profile_metadata` (line 229)
- `function` `_build_report_metadata` (line 284)
- ... 13 more symbols

### `src/services/start_run_data_service.py`
- `function` `_parse_positive_int_env` (line 17)
- `function` `clear_start_run_data_caches` (line 55)
- `function` `_cache_get` (line 80)
- `function` `_cache_set` (line 89)
- `function` `_disk_cache_path` (line 109)
- `function` `_ensure_disk_cache_dir` (line 114)
- `function` `_prune_disk_cache` (line 118)
- `function` `_disk_cache_get` (line 154)
- `function` `_disk_cache_set` (line 171)
- `function` `_count_disk_cache_entries` (line 184)
- `function` `_disk_cache_total_bytes` (line 191)
- `function` `_prune_all_disk_caches` (line 205)
- ... 27 more symbols

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
- `class` `CatalogEntry` (line 36)
- `class` `DataCatalog` (line 55)
- `class` `DatabentoService` (line 120)

### `src/databento_live.py`
- `class` `DatabentoLiveClient` (line 20)

## Endpoint Summary

| Method | Path | Handler | File |
|---|---|---|---|
| `WEBSOCKET` | `/ws/live` | `websocket_endpoint` | `api_server.py` |
| `GET` | `/` | `root` | `src/routes/system_routes.py` |
| `GET` | `/api/health` | `health` | `src/routes/system_routes.py` |
| `GET` | `/api/system/l2/runtime` | `get_l2_runtime` | `src/routes/system_routes.py` |
| `POST` | `/api/system/l2/runtime` | `update_l2_runtime` | `src/routes/system_routes.py` |
| `GET` | `/api/available-data` | `get_available_data` | `src/routes/system_routes.py` |
| `GET` | `/api/data/files` | `list_data_files` | `src/routes/system_routes.py` |
| `GET` | `/api/reports/diagnostic/{ticker}` | `get_diagnostic_report` | `src/routes/system_routes.py` |
| `GET` | `/api/reports/history/{ticker}` | `get_saved_run_history` | `src/routes/system_routes.py` |
| `GET` | `/api/l2/footprint/{ticker}` | `get_footprint_data` | `src/routes/l2_routes.py` |
| `GET` | `/api/l2/icebergs/{ticker}` | `get_icebergs` | `src/routes/l2_routes.py` |
| `GET` | `/api/data-loader/catalog` | `get_data_catalog` | `src/routes/data_loader_routes.py` |
| `POST` | `/api/data-loader/catalog/remote-sync` | `sync_remote_catalog` | `src/routes/data_loader_routes.py` |
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
| `GET` | `/api/profiles/{ticker}` | `get_unified_profiles` | `src/routes/config_read_routes.py` |
| `POST` | `/api/strategy-combos/capture` | `capture_strategy_combo_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/strategy-combos/apply` | `apply_strategy_combo_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/aos-config/update` | `update_aos_config_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/positioning-config/update` | `update_positioning_config_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/adaptive-tuner/profiles/apply` | `apply_adaptive_tuner_profile_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/profiles/capture` | `capture_unified_profile_endpoint` | `src/routes/config_write_routes.py` |
| `POST` | `/api/profiles/apply` | `apply_unified_profile_endpoint` | `src/routes/config_write_routes.py` |
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
| `POST` | `/api/run/prewarm/status` | `prewarm_status_endpoint` | `src/routes/run_start_routes.py` |
| `POST` | `/api/run/diagnose` | `diagnose_run_start_endpoint` | `src/routes/run_start_routes.py` |
| `POST` | `/api/run/cache/flush` | `flush_run_cache_endpoint` | `src/routes/run_start_routes.py` |
| `GET` | `/auth/me` | `v2_me` | `src/routes/v2_routes.py` |
| `GET` | `/plans` | `v2_plans` | `src/routes/v2_routes.py` |
| `GET` | `/usage` | `v2_usage` | `src/routes/v2_routes.py` |
| `GET` | `/user/settings` | `v2_user_settings` | `src/routes/v2_routes.py` |
| `PUT` | `/user/settings` | `v2_upsert_user_settings` | `src/routes/v2_routes.py` |
| `GET` | `/ops/metrics` | `v2_ops_metrics` | `src/routes/v2_routes.py` |
| `GET` | `/strategies/adaptive` | `v2_list_adaptive_strategies` | `src/routes/v2_routes.py` |
| `POST` | `/strategies/adaptive` | `v2_upsert_adaptive_strategy` | `src/routes/v2_routes.py` |
| `DELETE` | `/strategies/adaptive/{profile_id}` | `v2_delete_adaptive_strategy` | `src/routes/v2_routes.py` |
| `POST` | `/billing/checkout` | `v2_billing_checkout` | `src/routes/v2_routes.py` |
| `POST` | `/billing/portal` | `v2_billing_portal` | `src/routes/v2_routes.py` |
| `POST` | `/billing/webhook/stripe` | `v2_billing_webhook_stripe` | `src/routes/v2_routes.py` |
| `POST` | `/runs` | `v2_create_run` | `src/routes/v2_routes.py` |
| `POST` | `/adaptive-tuner/run` | `v2_run_adaptive_tuner` | `src/routes/v2_routes.py` |
| `POST` | `/data/download` | `v2_download_data` | `src/routes/v2_routes.py` |
| `GET` | `/jobs/{job_id}` | `v2_get_job` | `src/routes/v2_routes.py` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
