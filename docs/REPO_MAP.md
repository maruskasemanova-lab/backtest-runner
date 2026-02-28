# Repo Map

Generated at: `2026-02-28T14:54:41Z`

## Tree (depth 2)

```text
.
./.axon
./.axon/kuzu
./.cache
./.cache/start_run_data
./.claude
./.claude/commands
./.codex
./.codex/prompts
./.codex/tmp
./.cursor
./.dockerignore
./.env
./.env.example
./.git
./.gitignore
./.pytest_cache
./.pytest_cache/.gitignore
./.pytest_cache/CACHEDIR.TAG
./.pytest_cache/README.md
./.pytest_cache/v
./.ruff_cache
./.ruff_cache/.gitignore
./.ruff_cache/0.12.11
./.ruff_cache/CACHEDIR.TAG
./.vercel
./.vercel/README.txt
./.vercelignore
./.vscode
./AGENTS.md
./BMAD_QUICKSTART.md
./CLAUDE.md
./Dockerfile
./README.md
./__pycache__
./_bmad
./_bmad-output
./_bmad-output/.DS_Store
./_bmad-output/implementation-artifacts
./_bmad-output/planning-artifacts
./_bmad/_config
./_bmad/_memory
./_bmad/bmb
./_bmad/bmm
./_bmad/core
./analysis
./analysis/.DS_Store
./analysis/backtest_analysis_report.md
./analysis/claude_handoff_2026-02-06
./analysis/claude_handoff_architecture_2026-02-13
./analysis/mu_tuning_summary_2026-01-20_2026-02-06.md
./analysis/optimization
./analysis/runtime
./aos_optimization
./aos_optimization/.adaptive_tuner_aos
./aos_optimization/aos_history.jsonl
./aos_optimization/aos_optimizer.py
./aos_optimization/aos_time_analysis.py
./aos_optimization/aos_walk_forward.py
./aos_optimization/profiles
./aos_optimization/run_migration.py
./aos_optimization/short_trend_analysis.py
./aos_optimization/tickers
./aos_optimization/update_mu_profile.py
./aos_walk_forward_results
./api
./api/__pycache__
./api/index.py
./api_server.py
./batch_runner.py
./bmad
./bmad/README.md
./bmad/backlog
./bmad/context
./bmad/templates
./bmad/workflows
./config
./config/fly
./config/report_storage.json.example
./conftest.py
./data
./data/l2
./data/l2_precomputed
./data/remote_cache
./data/saas_state.db
./data/saas_state.db.corrupt_backup_20260227_210116
./data/saas_state.db.pre_repair_20260227_210116
./data/saas_state.recover_20260227_210116.sql
./data/saas_state.root_snapshot.db
./data/saas_state_8012.db
./data_loader.py
./db
./db/supabase
./decision_tracker.py
./docker-compose.dev.yml
./docker-compose.prod.yml
./docs
./docs/L2_DEFINITIONS.md
./docs/PATTERN_DISCOVERY.md
./docs/REPO_MAP.md
./docs/deploy
./docs/llm
./fly.toml
./frontend
./frontend/.axon
./frontend/.env.example
./frontend/.netlify
./frontend/.wrangler
./frontend/dist
./frontend/index.html
./frontend/netlify.toml
./frontend/node_modules
./frontend/postcss.config.cjs
./frontend/rsbuild.config.ts
./frontend/src
./frontend/tailwind.config.cjs
./frontend/vite.config.ts
./frontend/vitest.config.ts
./logs
./monte_carlo.py
./oos_validator.py
./pattern_library
./pattern_library/.gitkeep
./performance_tracker.py
./plans
./plans/anti-lookahead-refactor-plan.md
./plans/architecture-analysis.md
./plans/bmad_day_trading_runtime_impl_refactor_plan.md
./plans/bmad_supabase_user_persistence_plan.md
./plans/data-analysis.md
./plans/data-strategy-recommendation.md
./plans/final-architecture-plan.md
./plans/pattern_discovery_engine_implementation.md
./plans/project-analysis-report.md
./plans/recommendation.md
./plans/scalp_l2_bmad_iteration_plan.md
./plans/walk-forward-backtest-plan.md
./pyproject.toml
./render.yaml
./requirements.txt
./run_strategy_test.py
./scripts
./scripts/__pycache__
./scripts/analyze_mu_four_phase.py
./scripts/analyze_mu_tuning.py
./scripts/analyze_skips.py
./scripts/analyze_strategies.py
./scripts/audit_ticker_range.py
./scripts/axon-flow.sh
./scripts/bootstrap_bmad.sh
./scripts/check_costs.py
./scripts/check_db_schemas.py
./scripts/codex-project.sh
./scripts/convert_l2_to_parquet.py
./scripts/convert_mbn_to_ohlcv.py
./scripts/convert_mu_new_to_csv.py
./scripts/debug_l2_footprint.py
./scripts/deploy_backend_fly.sh
./scripts/deploy_backend_render.sh
./scripts/deploy_fly_stack.sh
./scripts/deploy_frontend_cloudflare_pages.sh
./scripts/deploy_strategy_fly.sh
./scripts/diagnostic_single_day.py
./scripts/download_all_l2.py
./scripts/download_googl_all.py
./scripts/download_googl_l2.py
./scripts/download_l2_data.py
./scripts/download_l2_mu.py
./scripts/download_l2_mu_jan_start.py
./scripts/download_mu_l2.py
./scripts/download_mu_ohlcv.py
./scripts/download_new_data.py
./scripts/download_ohlcv.py
./scripts/fetch_databento.py
./scripts/find_sweep_key.py
./scripts/gen_repo_map.sh
./scripts/generate_context_pack.py
./scripts/ibkr_mu_profitable_scalps_analysis.py
./scripts/ibkr_mu_scalp_parity.py
./scripts/mu_diagnostic.py
./scripts/next_bmad_story.py
./scripts/parallel_lane_summary.py
./scripts/parse_temp.py
./scripts/patch_configs.py
./scripts/precompute_l2_feature_map.py
./scripts/print_trades.py
./scripts/publish_mu_r2_janfeb.py
./scripts/query_duckdb_googl.py
./scripts/reproduce_backtest_start.sh
./scripts/run_overnight_gap_batch.py
./scripts/run_pattern_discovery.py
./scripts/scalp_l2_research_run.py
./scripts/set_netlify_fly_env.sh
./scripts/sync_claude_bmad_names.sh
./scripts/sync_codex_prompts.sh
./scripts/test-start.js
./scripts/test_intrabar.py
./scripts/test_logs.py
./scripts/test_sweep_api.py
./scripts/track_down.py
./scripts/track_missing.py
./scripts/track_skips.py
./scripts/tune_mu_strategies.py
./scripts/upload_mu_r2_wrangler.sh
./scripts/validate_holdout.py
./scripts/validate_llm_context.py
./scripts/verify_l2_data.py
./scripts/walk_forward_tune_mu.py
./session_runner.py
./src
./src/__init__.py
./src/__pycache__
./src/aos_config.py
./src/config_io.py
./src/databento_service.py
./src/intrabar_frame_builder.py
./src/l2_data_manager.py
./src/l2_feature_aggregator.py
./src/l2_feature_service.py
./src/l2_schema.py
./src/models
./src/momentum_diversification.py
./src/normalization.py
./src/observability
./src/order_flow_engine.py
./src/parquet_compat.py
./src/pattern_discovery
./src/routes
./src/runtime_mode.py
./src/security
./src/services
./src/session_config.py
./src/strategy_api_client.py
./src/system_settings.py
./src/tcbbo_analyzer.py
./src/time_utils.py
./start_all.sh
./strategy_api_auth_headers.py
./supabase
./supabase/.gitignore
./supabase/.temp
./supabase/config.toml
./supabase/migrations
./tests
./tests/__init__.py
./tests/__pycache__
./tests/fixtures
./tests/test_adaptive_tuner_api.py
./tests/test_api_server_l2_sessionized.py
./tests/test_available_data_cache.py
./tests/test_chart_preview_routes.py
./tests/test_context_pack_generation.py
./tests/test_data_loader_api_key_auth.py
./tests/test_data_loader_path_resolution.py
./tests/test_databento_blocking_download_compat.py
./tests/test_databento_daily_coverage.py
./tests/test_databento_download_precompute.py
./tests/test_databento_ohlcv_effective_range.py
./tests/test_databento_remote_manifest.py
./tests/test_databento_tcbbo_support.py
./tests/test_day_trading_manager_atr_fallback.py
./tests/test_day_trading_manager_session_reset.py
./tests/test_day_trading_runtime_guards.py
./tests/test_decision_tracker_pattern_description.py
./tests/test_decision_tracker_schema_v2.py
./tests/test_evidence_engine_no_candlestick.py
./tests/test_execution_realism.py
./tests/test_intrabar_frame_builder.py
./tests/test_l2_data_manager_cache_coverage.py
./tests/test_l2_data_manager_intrabar_cache.py
./tests/test_l2_data_manager_remote_catalog.py
./tests/test_l2_data_manager_runtime_dirs.py
./tests/test_l2_feature_aggregator.py
./tests/test_l2_feature_service_precomputed.py
./tests/test_l2_routes.py
./tests/test_live_trader_monitor_api.py
./tests/test_llm_context_validation.py
./tests/test_monte_carlo_risk_gate.py
./tests/test_multilayer_strategy_only_threshold.py
./tests/test_multilayer_weight_source.py
./tests/test_network_policy.py
./tests/test_no_lookahead.py
./tests/test_oos_validator_split.py
./tests/test_order_flow_engine_guards.py
./tests/test_pattern_discovery.py
./tests/test_performance_tracker_time_buckets.py
./tests/test_profile_options_service.py
./tests/test_run_control_intrabar_eval.py
./tests/test_run_control_playback_mode.py
./tests/test_run_control_restart.py
./tests/test_run_control_run_reports_store.py
./tests/test_run_start_routes_diagnose.py
./tests/test_runtime_mode_and_registry.py
./tests/test_saas_adaptive_profile_utils.py
./tests/test_saas_payload_utils.py
./tests/test_saas_plan_resolution_utils.py
./tests/test_saas_primitives.py
./tests/test_saas_query_utils.py
./tests/test_saas_service_subscription_lifecycle.py
./tests/test_security_auth.py
./tests/test_session_runner_intrabar_payload.py
./tests/test_session_runner_markers.py
./tests/test_start_run_cache_key_utils.py
./tests/test_start_run_data_availability_warnings.py
./tests/test_start_run_data_service_cache.py
./tests/test_start_run_execution_config_service.py
./tests/test_start_run_load_phase_service.py
./tests/test_start_run_load_phase_utils.py
./tests/test_start_run_planning_utils.py
./tests/test_start_run_prewarm_service.py
./tests/test_start_run_progressive_plan.py
./tests/test_start_run_progressive_utils.py
./tests/test_start_run_report_utils.py
./tests/test_start_run_runner_setup_service.py
./tests/test_start_run_session_phase_service.py
./tests/test_start_run_shared_utils.py
./tests/test_start_run_strategy_overrides_mode.py
./tests/test_start_run_time_window_service.py
./tests/test_strategy_api_auth_headers.py
./tests/test_strategy_api_profiles_service.py
./tests/test_strategy_api_session_service.py
./tests/test_strategy_api_updates_service.py
./tests/test_strategy_combo_profiles_api.py
./tests/test_supabase_user_settings_store.py
./tests/test_system_routes_diagnostic_report.py
./tests/test_system_routes_l2_runtime.py
./tests/test_trailing_stop_regime_aware.py
./tests/test_unified_profiles_api.py
./tests/test_v2_routes.py
./tests/test_walk_forward_runner_parallel_mode.py
./tests/test_wfo_optimizer.py
./tests/test_wfo_optimizer_flow_matrix.py
./tests/test_wfo_optimizer_parallel_mode.py
./tuning_runner.py
./walk_forward_results
./walk_forward_results/mu_baseline
./walk_forward_results/mu_ibkr_live_profile_2025-10-01_2026-02-13
./walk_forward_results/mu_ibkr_live_profile_2025-10-01_2026-02-13_all_enabled
./walk_forward_results/mu_non_overfit_v2_2025-10-01_2026-02-13
./walk_forward_results/mu_non_overfit_v3_2025-10-01_2026-02-13
./walk_forward_runner.py
./wfo_optimizer.py
```

## Entrypoints / Key Files

- `api_server.py` (runner API orchestration, adaptive tuner, AOS config endpoints)
- `session_runner.py` (bar playback engine, marker lifecycle)
- `data_loader.py` (OHLCV loading/filtering)
- `src/l2_feature_service.py` (L2 feature attachment to bars)
- `src/l2_data_manager.py` (L2 file loading and raw L2 access)
- `frontend/src/App.jsx` (frontend orchestration shell)
- `frontend/src/components/RunConfig.jsx` (run payload + pre-run AOS/profile apply)
- `frontend/src/components/AdaptiveTuner.jsx` (tuner UI + polling)
- `frontend/src/components/AdaptiveStrategyStudio.jsx` (adaptive config editor)

## Adaptive Tuning Hot Spots

- `POST /api/adaptive-tuner/run` in `api_server.py`
- `_run_adaptive_tuner_job` (v1 worker) in `api_server.py`
- `_run_v2_adaptive_tuner_job` (v2 worker) in `api_server.py`
- `_evaluate_adaptive_tuner_candidate` / `_evaluate_v2_candidate` in `api_server.py`
- `tests/test_adaptive_tuner_api.py`

## AOS Config Persistence Surface

- Source file: `aos_optimization/aos_config.json`
- Read helpers: `_load_aos_config`
- Write helper: `_save_aos_config`
- Write endpoints: `/api/aos-config/update`, `/api/strategy-combos/*`, `/api/adaptive-tuner/profiles/apply`, tuner workers
- `/api/run/start` reads/apply runtime config but does not directly persist `aos_config.json`

## LLM Context Files

- `CLAUDE.md` (persistent agent instructions)
- `AGENTS.md` (deterministic protocol for coding agents)
- `docs/llm/*.md` (manual behavior/contract docs)
- `bmad/context/generated/*` (generated machine/context index)
