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
| `api_server.py` | yes | 1760 | `66679f2 2026-03-05` |
| `session_runner.py` | yes | 2452 | `f30de01 2026-03-05` |
| `data_loader.py` | yes | 544 | `d064025 2026-03-01` |
| `src/services/data_discovery.py` | yes | 221 | `6c4716f 2026-02-28` |
| `decision_tracker.py` | yes | 553 | `d064025 2026-03-01` |
| `performance_tracker.py` | yes | 993 | `6c4716f 2026-02-28` |
| `src/routes/context.py` | yes | 47 | `51e9988 2026-03-02` |
| `src/routes/system_routes.py` | yes | 224 | `66679f2 2026-03-05` |
| `src/routes/l2_routes.py` | yes | 122 | `1273b21 2026-02-23` |
| `src/routes/data_loader_routes.py` | yes | 289 | `1273b21 2026-02-23` |
| `src/routes/live_trader_routes.py` | yes | 164 | `51e9988 2026-03-02` |
| `src/routes/config_read_routes.py` | yes | 140 | `f30de01 2026-03-05` |
| `src/routes/config_write_routes.py` | yes | 111 | `d064025 2026-03-01` |
| `src/routes/run_routes.py` | yes | 279 | `66679f2 2026-03-05` |
| `src/routes/adaptive_tuner_routes.py` | yes | 38 | `da07c20 2026-02-12` |
| `src/routes/run_start_routes.py` | yes | 345 | `1273b21 2026-02-23` |
| `src/routes/v2_routes.py` | yes | 3008 | `f30de01 2026-03-05` |
| `src/models/config_requests.py` | yes | 47 | `b9accc6 2026-02-18` |
| `src/models/run_requests.py` | yes | 277 | `604f06b 2026-03-05` |
| `src/models/tuner_requests.py` | yes | 95 | `1273b21 2026-02-23` |
| `src/security/auth.py` | yes | 279 | `1273b21 2026-02-23` |
| `src/security/network_policy.py` | yes | 139 | `51e9988 2026-03-02` |
| `src/observability/runtime_metrics.py` | yes | 74 | `1273b21 2026-02-23` |
| `src/services/live_trader_service.py` | yes | 272 | `1273b21 2026-02-23` |
| `src/services/run_registry.py` | yes | 35 | `0d50960 2026-03-04` |
| `src/services/config_write_service.py` | yes | 786 | `f30de01 2026-03-05` |
| `src/services/user_dataset_utils.py` | yes | 235 | `f30de01 2026-03-05` |
| `src/services/run_control_service.py` | yes | 1589 | `66679f2 2026-03-05` |
| `src/services/saas_service.py` | yes | 2394 | `f30de01 2026-03-05` |
| `src/services/adaptive_tuner_orchestration_service.py` | yes | 177 | `1273b21 2026-02-23` |
| `src/services/adaptive_tuner_worker_service.py` | yes | 672 | `1273b21 2026-02-23` |
| `src/services/adaptive_tuner_core_service.py` | yes | 533 | `1273b21 2026-02-23` |
| `src/services/adaptive_tuner_search_service.py` | yes | 280 | `1273b21 2026-02-23` |
| `src/services/adaptive_tuner_runtime_service.py` | yes | 999 | `d064025 2026-03-01` |
| `src/services/adaptive_tuner_v2_service.py` | yes | 1099 | `1273b21 2026-02-23` |
| `src/services/strategy_api_types.py` | yes | 33 | `1273b21 2026-02-23` |
| `src/services/strategy_api_updates_service.py` | yes | 267 | `d064025 2026-03-01` |
| `src/services/strategy_api_profiles_service.py` | yes | 138 | `f30de01 2026-03-05` |
| `src/services/strategy_api_session_service.py` | yes | 539 | `d064025 2026-03-01` |
| `src/services/start_run_service.py` | yes | 1027 | `f30de01 2026-03-05` |
| `src/services/start_run_data_service.py` | yes | 1501 | `d064025 2026-03-01` |
| `src/services/start_run_execution_config_service.py` | yes | 913 | `0d50960 2026-03-04` |
| `src/services/start_run_local_aos_service.py` | yes | 59 | `f30de01 2026-03-05` |
| `src/services/start_run_prewarm_utils.py` | yes | 230 | `f30de01 2026-03-05` |
| `src/services/start_run_bootstrap_phase_service.py` | yes | 289 | `f30de01 2026-03-05` |
| `src/services/start_run_load_phase_service.py` | yes | 180 | `0248cab 2026-02-28` |
| `src/services/start_run_session_phase_service.py` | yes | 142 | `8f49f06 2026-02-23` |
| `src/services/start_run_execution_payload_service.py` | yes | 989 | `f30de01 2026-03-05` |
| `src/services/start_run_runner_setup_service.py` | yes | 397 | `0248cab 2026-02-28` |
| `src/services/execution_config/helpers.py` | yes | 310 | `1273b21 2026-02-23` |
| `src/services/execution_config/intraday_context.py` | yes | 466 | `0248cab 2026-02-28` |
| `src/config_io.py` | yes | 29 | `1273b21 2026-02-23` |
| `src/system_settings.py` | yes | 179 | `1273b21 2026-02-23` |
| `src/databento_service.py` | yes | 2046 | `58ebada 2026-02-27` |

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
- `function` `_run_startup_prewarm_request_sync` (line 308)
- `function` `_refresh_runtime_data_services` (line 313)
- `function` `_run_file_storage_migrations` (line 423)
- `async_function` `_collect_http_runtime_metrics` (line 463)
- `function` `_build_config_write_deps` (line 478)
- `function` `_build_run_control_deps` (line 501)
- `function` `_build_adaptive_tuner_deps` (line 517)
- `function` `_build_adaptive_tuner_worker_deps` (line 533)
- `function` `_build_adaptive_tuner_runtime_deps` (line 559)
- `function` `_build_adaptive_tuner_v2_deps` (line 580)
- `function` `_build_strategy_api_integration_deps` (line 598)
- `function` `_build_start_run_deps` (line 620)
- ... 68 more symbols

### `session_runner.py`
- `function` `_normalize_profile_token` (line 96)
- `class` `RunConfig` (line 106)
- `class` `SessionRunner` (line 125)

### `data_loader.py`
- `class` `DataLoader` (line 22)

### `src/services/data_discovery.py`
- `class` `TickerData` (line 22)
- `class` `DataDiscovery` (line 32)
- `function` `get_discovery` (line 210)
- `function` `reset_discovery` (line 218)

### `decision_tracker.py`
- `class` `MarkerType` (line 12)
- `function` `_to_json_compatible` (line 28)
- `function` `_timestamp_to_iso` (line 55)
- `function` `_timestamp_to_epoch_seconds` (line 62)
- `class` `DecisionMarker` (line 83)
- `class` `DecisionTracker` (line 116)

### `performance_tracker.py`
- `class` `Regime` (line 16)
- `class` `TradeRecord` (line 25)
- `class` `StrategyPerformance` (line 153)
- `class` `PerformanceTracker` (line 356)

### `src/routes/context.py`
- `class` `ApiServices` (line 9)
- `function` `get_api_services` (line 43)

### `src/routes/system_routes.py`
- `function` `_project_root` (line 22)
- `function` `_run_reports_store` (line 26)
- `function` `_active_runners` (line 32)
- `function` `_run_reports_source_mode` (line 40)
- `function` `_build_run_reports_read_deps` (line 49)
- `function` `_sanitize_segment` (line 58)
- `function` `_sanitize_run_key` (line 68)
- `function` `_coerce_non_negative_int` (line 78)
- `async_function` `root` (line 91)
- `async_function` `health` (line 100)
- `async_function` `get_l2_runtime` (line 109)
- `async_function` `update_l2_runtime` (line 125)
- ... 4 more symbols

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
- `async_function` `get_data_catalog` (line 82)
- `async_function` `sync_remote_catalog` (line 103)
- `async_function` `get_ticker_catalog` (line 117)
- `async_function` `get_data_loader_settings` (line 126)
- `async_function` `update_data_loader_settings` (line 132)
- `async_function` `set_databento_api_key` (line 150)
- ... 6 more symbols

### `src/routes/live_trader_routes.py`
- `function` `_supports_db_live_trader` (line 15)
- `async_function` `list_live_trader_runs` (line 24)
- `async_function` `get_live_trader_events` (line 57)
- `async_function` `get_live_trader_snapshot` (line 101)

### `src/routes/config_read_routes.py`
- `function` `_build_ticker_config_repository_deps` (line 18)
- `async_function` `get_strategy_overrides` (line 35)
- `async_function` `get_ticker_overrides` (line 41)
- `async_function` `get_strategy_combos` (line 50)
- `async_function` `get_aos_config` (line 58)
- `async_function` `get_ticker_aos_config` (line 66)
- `async_function` `get_positioning_config` (line 78)
- `async_function` `get_ticker_positioning_config` (line 84)
- `async_function` `get_adaptive_tuner_options` (line 92)
- `async_function` `get_unified_profiles` (line 100)
- `async_function` `get_aos_history` (line 118)

### `src/routes/config_write_routes.py`
- `async_function` `capture_strategy_combo_endpoint` (line 30)
- `async_function` `apply_strategy_combo_endpoint` (line 39)
- `async_function` `update_aos_config_endpoint` (line 48)
- `async_function` `update_positioning_config_endpoint` (line 57)
- `async_function` `apply_adaptive_tuner_profile_endpoint` (line 66)
- `async_function` `capture_unified_profile_endpoint` (line 75)
- `async_function` `apply_unified_profile_endpoint` (line 95)

### `src/routes/run_routes.py`
- `async_function` `get_run_state_endpoint` (line 33)
- `async_function` `step_run_endpoint` (line 44)
- `async_function` `play_run_endpoint` (line 64)
- `async_function` `pause_run_endpoint` (line 86)
- `async_function` `resume_run_endpoint` (line 97)
- `async_function` `stop_run_endpoint` (line 108)
- `async_function` `restart_run_endpoint` (line 119)
- `async_function` `restore_run_snapshot_endpoint` (line 130)
- `async_function` `get_processed_bars_endpoint` (line 146)
- `async_function` `get_bar_details_endpoint` (line 164)
- `async_function` `evaluate_intrabar_slice_endpoint` (line 178)
- `async_function` `get_markers_endpoint` (line 192)
- ... 7 more symbols

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
- `async_function` `flush_run_cache_endpoint` (line 341)

### `src/routes/v2_routes.py`
- `class` `BillingCheckoutRequest` (line 61)
- `class` `BillingPortalRequest` (line 68)
- `class` `V2UserSettingsUpdateRequest` (line 72)
- `class` `V2UserDatasetRequest` (line 76)
- `class` `V2RunRequest` (line 90)
- `class` `V2AdaptiveTunerRequest` (line 95)
- `class` `V2DownloadRequest` (line 99)
- `class` `V2AdaptiveStrategyProfileRequest` (line 108)
- `function` `_request_id` (line 118)
- `function` `_utc_now` (line 123)
- `function` `_utc_iso` (line 127)
- `function` `_detail` (line 133)
- ... 88 more symbols

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
- `class` `PrewarmRunRequest` (line 243)
- `class` `PlayRequest` (line 270)

### `src/models/tuner_requests.py`
- `class` `AdaptiveTunerRequest` (line 6)

### `src/security/auth.py`
- `class` `AuthContext` (line 16)
- `class` `JwtValidationError` (line 25)
- `function` `_b64url_decode` (line 29)
- `function` `_b64url_encode` (line 37)
- `function` `parse_bearer_token` (line 41)
- `function` `_resolve_supabase_auth_verify_url` (line 51)
- `function` `_resolve_supabase_auth_verify_api_key` (line 64)
- `function` `_resolve_supabase_auth_verify_timeout_seconds` (line 75)
- `function` `_verify_jwt_via_supabase_auth` (line 84)
- `function` `decode_and_verify_jwt` (line 128)
- `function` `resolve_jwt_secret` (line 184)
- `function` `allow_unverified_jwt` (line 190)
- ... 5 more symbols

### `src/security/network_policy.py`
- `class` `StrategyApiPolicyError` (line 8)
- `function` `parse_csv_env` (line 15)
- `function` `normalize_base_url` (line 30)
- `function` `default_internal_strategy_api_url` (line 47)
- `function` `resolve_strategy_allowlist` (line 52)
- `function` `enforce_strategy_url_policy` (line 76)
- `function` `_is_loopback_host` (line 99)
- `function` `_resolve_runtime_reachable_strategy_url` (line 108)
- `function` `enforce_strategy_url_allowlist_only` (line 116)
- `function` `cors_allow_origins_from_env` (line 128)
- `function` `should_allow_credentials` (line 137)

### `src/observability/runtime_metrics.py`
- `function` `_percentile` (line 8)
- `class` `RuntimeMetrics` (line 25)

### `src/services/live_trader_service.py`
- `function` `sanitize_live_run_id` (line 14)
- `function` `live_artifact_file` (line 23)
- `function` `read_jsonl_tail` (line 28)
- `function` `parse_utc_iso` (line 55)
- `function` `extract_runtime_summary` (line 70)
- `function` `infer_live_run_status` (line 104)
- `function` `discover_live_trader_runs` (line 124)
- `function` `live_trader_events_payload` (line 189)
- `function` `live_trader_snapshot_payload` (line 216)

### `src/services/run_registry.py`
- `class` `RunRegistry` (line 11)

### `src/services/config_write_service.py`
- `class` `ConfigWriteDeps` (line 20)
- `function` `_utc_now_iso` (line 46)
- `function` `_normalize_trading_hours` (line 50)
- `function` `_resolve_active_adaptive_candidate` (line 67)
- `function` `_build_strategy_profile_snapshot` (line 99)
- `function` `_build_execution_profile_snapshot` (line 170)
- `function` `_load_unified_profile_state` (line 195)
- `function` `_save_unified_profile_state` (line 229)
- `function` `_clear_local_unified_profile_state` (line 247)
- `async_function` `capture_unified_profile` (line 258)
- `async_function` `apply_unified_profile` (line 353)
- `async_function` `capture_strategy_combo` (line 513)
- ... 4 more symbols

### `src/services/user_dataset_utils.py`
- `class` `DatasetInputError` (line 12)
- `function` `normalize_dataset_identifier` (line 19)
- `function` `normalize_dataset_status` (line 38)
- `function` `normalize_dataset_format` (line 55)
- `function` `storage_path_segment` (line 80)
- `function` `default_user_dataset_s3_path` (line 90)
- `function` `format_user_dataset` (line 111)
- `function` `user_datasets_local_cache_dir` (line 142)
- `function` `user_dataset_local_cache_path` (line 153)
- `function` `user_dataset_upload_max_bytes` (line 161)
- `function` `is_http_remote_locator` (line 170)
- `function` `user_dataset_storage_mode` (line 175)
- ... 3 more symbols

### `src/services/run_control_service.py`
- `class` `RunControlDeps` (line 32)
- `function` `_runner_date_label` (line 46)
- `function` `_runner_run_key` (line 57)
- `function` `_runner_completed_successfully` (line 69)
- `function` `_snapshot_backed_runner` (line 101)
- `function` `_guard_snapshot_runner_mutation` (line 105)
- `function` `_runner_state_payload` (line 117)
- `async_function` `_flush_runner_from_memory` (line 135)
- `async_function` `_read_raw_request_payload` (line 167)
- `function` `_set_runner_trade_eval_mode` (line 179)
- `function` `_effective_runner_trade_eval_mode` (line 200)
- `function` `_resolve_requested_trade_eval_mode` (line 211)
- ... 38 more symbols

### `src/services/saas_service.py`
- `class` `UserSettingsStore` (line 50)
- `class` `RunReportsStore` (line 62)
- `class` `RunStateMirror` (line 97)
- `class` `UserDatasetsStore` (line 116)
- `class` `ConfigSnapshotRecord` (line 149)
- `class` `AosHistoryEntryRecord` (line 157)
- `class` `LiveTraderEventRecord` (line 165)
- `class` `SaaSStateStore` (line 174)
- `class` `V2Services` (line 2358)

### `src/services/adaptive_tuner_orchestration_service.py`
- `class` `AdaptiveTunerOrchestrationDeps` (line 11)
- `async_function` `run_adaptive_tuner` (line 25)
- `function` `get_adaptive_tuner_job` (line 159)
- `function` `list_adaptive_tuner_jobs` (line 169)

### `src/services/adaptive_tuner_worker_service.py`
- `class` `AdaptiveTunerWorkerDeps` (line 13)
- `async_function` `run_v2_adaptive_tuner_job` (line 37)
- `async_function` `run_adaptive_tuner_job` (line 411)

### `src/services/adaptive_tuner_core_service.py`
- `function` `normalize_strategy_selection_mode` (line 10)
- `function` `normalize_non_negative_int` (line 15)
- `function` `normalize_clamped_int` (line 27)
- `function` `normalize_bool_options` (line 40)
- `function` `normalize_int_options` (line 56)
- `function` `normalize_mode_options` (line 76)
- `function` `normalize_float_options` (line 91)
- `function` `normalize_strategy_sets` (line 116)
- `function` `normalize_regime_filter_sets` (line 144)
- `function` `normalize_time_window_sets` (line 178)
- `function` `normalize_regime_strategy_map_sets` (line 215)
- `function` `iter_date_strings` (line 274)
- ... 10 more symbols

### `src/services/adaptive_tuner_search_service.py`
- `function` `candidate_key` (line 20)
- `function` `build_adaptive_tuner_search_space` (line 33)
- `function` `build_grid_candidates` (line 63)
- `function` `build_random_candidates` (line 86)
- `function` `build_adaptive_candidate_config` (line 119)
- `function` `compute_tuner_score` (line 150)
- `function` `compute_tuner_score_robust` (line 177)
- `function` `build_tuner_profile_entry` (line 247)

### `src/services/adaptive_tuner_runtime_service.py`
- `function` `_parse_bool_env` (line 22)
- `function` `_parse_positive_int_env` (line 34)
- `function` `_shutdown_day_parallel_pool` (line 60)
- `function` `_get_day_parallel_pool` (line 77)
- `function` `_resolve_day_parallel_workers` (line 102)
- `function` `_build_v2_runtime_overrides` (line 116)
- `function` `_aggregate_day_metrics` (line 172)
- `function` `_evaluate_tuner_day_subprocess` (line 199)
- `async_function` `_evaluate_tuner_days_parallel` (line 280)
- `class` `AdaptiveTunerRuntimeDeps` (line 302)
- `async_function` `evaluate_adaptive_tuner_candidate` (line 323)
- `async_function` `evaluate_v2_candidate` (line 548)
- ... 1 more symbols

### `src/services/adaptive_tuner_v2_service.py`
- `class` `AdaptiveTunerV2Deps` (line 12)
- `function` `build_v2_search_space` (line 30)
- `function` `v2_candidate_key` (line 349)
- `function` `build_v2_baseline_candidate` (line 406)
- `function` `build_v2_random_candidates` (line 512)
- `function` `build_v2_candidate_config` (line 737)
- `function` `analyze_vectors` (line 933)

### `src/services/strategy_api_types.py`
- `class` `StrategyApiIntegrationDeps` (line 8)

### `src/services/strategy_api_updates_service.py`
- `function` `_parse_positive_int_env` (line 17)
- `function` `_parse_positive_float_env` (line 27)
- `function` `_strategy_api_headers` (line 47)
- `async_function` `_post_strategy_update` (line 51)
- `async_function` `_run_strategy_updates` (line 70)
- `async_function` `apply_strategy_overrides` (line 105)
- `async_function` `fetch_remote_strategies` (line 131)
- `async_function` `apply_strategy_param_map` (line 158)
- `async_function` `apply_global_trailing` (line 191)

### `src/services/strategy_api_profiles_service.py`
- `function` `normalize_strategy_key` (line 23)
- `function` `resolve_active_adaptive_tuner_candidate` (line 27)
- `function` `resolve_active_unified_profile` (line 34)
- `function` `extract_profile_runtime_overrides` (line 41)
- `function` `_extract_unified_runtime_overrides` (line 48)
- `async_function` `apply_active_strategy_combo` (line 55)
- `async_function` `apply_active_adaptive_tuner_profile` (line 69)
- `async_function` `apply_aos_optimizations` (line 81)

### `src/services/strategy_api_session_service.py`
- `function` `_parse_positive_float_env` (line 15)
- `function` `_strategy_api_headers` (line 31)
- `async_function` `configure_session` (line 35)
- `async_function` `clear_remote_strategy_sessions` (line 295)
- `async_function` `reset_remote_orchestrator_state` (line 328)
- `async_function` `reset_remote_orchestrator_state_scoped` (line 382)
- `async_function` `apply_orchestrator_config` (line 439)
- `async_function` `load_remote_checkpoint` (line 473)
- `async_function` `save_remote_checkpoint` (line 501)

### `src/services/start_run_service.py`
- `function` `_parse_non_negative_int_env` (line 84)
- `function` `_parse_bool_env` (line 94)
- `function` `_strategy_reset_success` (line 146)
- `function` `_strategy_reset_detail` (line 152)
- `function` `_to_json_compatible` (line 158)
- `class` `StartRunDeps` (line 191)
- `function` `_resolve_request_range` (line 224)
- `function` `_normalize_profile_ref_token` (line 232)
- `function` `_first_profile_ref_token` (line 236)
- `function` `_extract_effective_profile_metadata` (line 240)
- `function` `_summarize_days_preview` (line 251)
- `function` `_build_data_availability_warnings` (line 255)
- ... 18 more symbols

### `src/services/start_run_data_service.py`
- `function` `_parse_positive_int_env` (line 40)
- `class` `BaseBarsCacheContext` (line 85)
- `class` `ReferenceBarsCacheContext` (line 92)
- `function` `clear_start_run_data_caches` (line 98)
- `function` `_cache_get` (line 123)
- `function` `_cache_set` (line 132)
- `function` `_disk_cache_path` (line 152)
- `function` `_ensure_disk_cache_dir` (line 157)
- `function` `_prune_disk_cache` (line 161)
- `function` `_disk_cache_get` (line 197)
- `function` `_disk_cache_set` (line 215)
- `function` `_count_disk_cache_entries` (line 228)
- ... 38 more symbols

### `src/services/start_run_execution_config_service.py`
- `function` `_resolve_strategy_selection` (line 40)
- `function` `_resolve_positioning_config` (line 97)
- `function` `_resolve_l2_lookback_bars` (line 115)
- `function` `_resolve_l2_config` (line 124)
- `function` `_resolve_positioning_fields` (line 198)
- `function` `_apply_intraday_profile_overrides` (line 321)
- `function` `_apply_context_risk_profile_overrides` (line 384)
- `function` `_parse_clamped_int` (line 463)
- `function` `_request_fields_set` (line 471)
- `function` `_resolve_regime_runtime_value` (line 481)
- `function` `_resolve_runtime_basics` (line 512)
- `function` `_resolve_runtime_stop_loss` (line 549)
- ... 2 more symbols

### `src/services/start_run_local_aos_service.py`
- `function` `_local_profile_resolution_deps` (line 23)
- `function` `resolve_local_aos_applied` (line 36)

### `src/services/start_run_prewarm_utils.py`
- `class` `PrewarmRequestState` (line 16)
- `class` `PrewarmInflightRegistry` (line 31)
- `function` `build_prewarm_cache_key` (line 65)
- `function` `resolve_prewarm_scope_range` (line 98)
- `function` `resolve_prewarm_request_state` (line 149)
- `function` `raise_for_guard_reason` (line 220)

### `src/services/start_run_bootstrap_phase_service.py`
- `class` `BootstrapPhaseInputs` (line 16)
- `class` `BootstrapPhaseDeps` (line 23)
- `class` `BootstrapPhaseResult` (line 38)
- `function` `_positive_or_zero` (line 53)
- `async_function` `_run_orchestrator_reset` (line 61)
- `function` `_extract_adaptive_profile_runtime` (line 102)
- `function` `_resolve_momentum_diversification` (line 110)
- `async_function` `_apply_global_trailing_from_execution_cfg` (line 149)
- `async_function` `run_start_bootstrap_phase` (line 183)

### `src/services/start_run_load_phase_service.py`
- `class` `LoadPhaseInputs` (line 19)
- `class` `LoadPhaseDeps` (line 35)
- `class` `LoadPhaseResult` (line 50)
- `async_function` `run_start_load_phase` (line 64)

### `src/services/start_run_session_phase_service.py`
- `class` `SessionPhaseInputs` (line 11)
- `class` `SessionPhaseDeps` (line 27)
- `class` `SessionPhaseResult` (line 35)
- `async_function` `run_start_session_phase` (line 46)

### `src/services/start_run_execution_payload_service.py`
- `class` `ExecutionPayloadInputs` (line 10)
- `class` `ExecutionPayloadResult` (line 37)
- `function` `_apply_control_plane_snapshot` (line 42)
- `function` `_build_l2_thresholds` (line 65)
- `function` `_is_options_flow_alpha_enabled` (line 81)
- `function` `_build_core_execution_payload` (line 90)
- `function` `_build_runtime_execution_payload` (line 444)
- `function` `_build_intraday_levels_payload` (line 488)
- `function` `_build_context_risk_payload` (line 769)
- `function` `_resolve_include_extended_hours` (line 807)
- `function` `_apply_optional_execution_limits` (line 821)
- `function` `_apply_effective_profile_metadata` (line 849)
- ... 2 more symbols

### `src/services/start_run_runner_setup_service.py`
- `class` `RunnerSetupInputs` (line 19)
- `class` `RunnerSetupDeps` (line 44)
- `function` `_register_runner_callbacks` (line 63)
- `function` `_apply_runner_runtime_metadata` (line 100)
- `function` `_load_chunk_payload` (line 144)
- `function` `_append_deduped_chunk_bars` (line 207)
- `async_function` `_append_remaining_chunks` (line 236)
- `function` `setup_runner_with_progressive_loading` (line 346)

### `src/services/execution_config/helpers.py`
- `function` `coerce_bool` (line 6)
- `function` `pick_l2_float` (line 20)
- `function` `resolve_optional_runtime_non_negative_int` (line 46)
- `function` `resolve_optional_runtime_bool` (line 59)
- `function` `resolve_positioning_float` (line 68)
- `function` `resolve_positioning_int` (line 117)
- `function` `resolve_positioning_bool` (line 166)
- `function` `resolve_positioning_str` (line 201)
- `function` `resolve_stop_loss_mode` (line 246)
- `function` `resolve_adverse_flow_threshold` (line 269)

### `src/services/execution_config/intraday_context.py`
- `function` `_int_min` (line 8)
- `function` `_int_clamp` (line 15)
- `function` `_float_clamp` (line 23)
- `function` `_bool_default` (line 41)
- `function` `resolve_intraday_levels_config` (line 48)
- `function` `resolve_context_risk_config` (line 405)

### `src/config_io.py`
- `function` `load_json_file` (line 12)
- `function` `save_json_file` (line 22)

### `src/system_settings.py`
- `function` `_normalize_dirs` (line 21)
- `function` `mask_secret` (line 43)
- `class` `SystemSettings` (line 52)

### `src/databento_service.py`
- `class` `CatalogEntry` (line 41)
- `class` `DataCatalog` (line 60)
- `class` `DatabentoService` (line 126)

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
| `GET` | `/api/reports/history/{ticker}` | `get_saved_run_history` | `src/routes/system_routes.py` |
| `GET` | `/api/reports/run-snapshot` | `get_run_playback_snapshot` | `src/routes/system_routes.py` |
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
| `GET` | `/api/aos-history/{ticker}` | `get_aos_history` | `src/routes/config_read_routes.py` |
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
| `POST` | `/api/run/{run_id}/{ticker}/{date}/restore-snapshot` | `restore_run_snapshot_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/bars` | `get_processed_bars_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/bar-details/{minute_key}` | `get_bar_details_endpoint` | `src/routes/run_routes.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/intrabar_eval` | `evaluate_intrabar_slice_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/markers` | `get_markers_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/chart-annotations` | `get_chart_annotations_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/summary` | `get_run_summary_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/summary-db` | `get_run_summary_db_endpoint` | `src/routes/run_routes.py` |
| `GET` | `/api/run/{run_id}/{ticker}/{date}/run-status` | `get_run_status_endpoint` | `src/routes/run_routes.py` |
| `DELETE` | `/api/run/{run_id}/{ticker}/{date}` | `delete_run_endpoint` | `src/routes/run_routes.py` |
| `POST` | `/api/run/{run_id}/{ticker}/{date}/orchestrator-config` | `update_orchestrator_config_endpoint` | `src/routes/run_routes.py` |
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
| `GET` | `/datasets` | `v2_list_user_datasets` | `src/routes/v2_routes.py` |
| `GET` | `/datasets/{dataset_id}` | `v2_get_user_dataset` | `src/routes/v2_routes.py` |
| `POST` | `/datasets` | `v2_upsert_user_dataset` | `src/routes/v2_routes.py` |
| `DELETE` | `/datasets/{dataset_id}` | `v2_delete_user_dataset` | `src/routes/v2_routes.py` |
| `POST` | `/datasets/upload/csv` | `v2_upload_user_dataset_csv` | `src/routes/v2_routes.py` |
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
