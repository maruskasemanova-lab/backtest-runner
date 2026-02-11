# Repo Map

Generated at: `2026-02-11T07:00:50Z`

## Tree (depth 2)

```text
.
├── AGENTS.md
├── BMAD_QUICKSTART.md
├── CLAUDE.md
├── README.md
├── _bmad
│   ├── _config
│   ├── _memory
│   ├── bmb
│   ├── bmm
│   └── core
├── analysis
│   ├── claude_handoff_2026-02-06
│   └── mu_tuning_summary_2026-01-20_2026-02-06.md
├── aos_optimization
├── aos_optimizer.py
├── aos_time_analysis.py
├── aos_walk_forward.py
├── api_server.py
├── available_data.py
├── backtest_analysis_report.md
├── batch_runner.py
├── bmad
│   ├── README.md
│   ├── backlog
│   ├── context
│   ├── templates
│   └── workflows
├── data
│   └── l2
├── data_loader.py
├── decision_tracker.py
├── docs
│   ├── L2_DEFINITIONS.md
│   ├── REPO_MAP.md
│   └── llm
├── frontend
│   ├── index.html
│   ├── public
│   ├── src
│   └── vite.config.js
├── monte_carlo.py
├── oos_validator.py
├── performance_tracker.py
├── plans
│   ├── anti-lookahead-refactor-plan.md
│   ├── architecture-analysis.md
│   ├── data-analysis.md
│   ├── data-strategy-recommendation.md
│   ├── final-architecture-plan.md
│   ├── recommendation.md
│   └── walk-forward-backtest-plan.md
├── requirements.txt
├── run_strategy_test.py
├── scripts
│   ├── audit_ticker_range.py
│   ├── bootstrap_bmad.sh
│   ├── codex-project.sh
│   ├── convert_l2_to_parquet.py
│   ├── convert_mbn_to_ohlcv.py
│   ├── convert_mu_new_to_csv.py
│   ├── debug_l2_footprint.py
│   ├── download_all_l2.py
│   ├── download_googl_l2.py
│   ├── download_l2_data.py
│   ├── download_l2_mu.py
│   ├── download_l2_mu_jan_start.py
│   ├── download_mu_l2.py
│   ├── download_mu_ohlcv.py
│   ├── download_new_data.py
│   ├── download_ohlcv.py
│   ├── fetch_databento.py
│   ├── gen_repo_map.sh
│   ├── generate_context_pack.py
│   ├── next_bmad_story.py
│   ├── sync_claude_bmad_names.sh
│   ├── sync_codex_prompts.sh
│   ├── validate_llm_context.py
│   └── verify_l2_data.py
├── session_runner.py
├── short_trend_analysis.py
├── src
│   ├── __init__.py
│   ├── config_io.py
│   ├── databento_live.py
│   ├── databento_service.py
│   ├── intrabar_frame_builder.py
│   ├── l2_data_manager.py
│   ├── l2_feature_aggregator.py
│   ├── l2_feature_service.py
│   ├── order_flow_engine.py
│   ├── run_artifact_store.py
│   └── system_settings.py
├── start_all.sh
├── tests
│   ├── test_adaptive_tuner_api.py
│   ├── test_api_server_l2_sessionized.py
│   ├── test_context_pack_generation.py
│   ├── test_data_loader_path_resolution.py
│   ├── test_databento_daily_coverage.py
│   ├── test_databento_ohlcv_effective_range.py
│   ├── test_day_trading_manager_atr_fallback.py
│   ├── test_day_trading_manager_session_reset.py
│   ├── test_decision_tracker_pattern_description.py
│   ├── test_decision_tracker_schema_v2.py
│   ├── test_evidence_engine_no_candlestick.py
│   ├── test_execution_realism.py
│   ├── test_intrabar_frame_builder.py
│   ├── test_l2_feature_aggregator.py
│   ├── test_llm_context_validation.py
│   ├── test_monte_carlo_risk_gate.py
│   ├── test_multilayer_strategy_only_threshold.py
│   ├── test_multilayer_weight_source.py
│   ├── test_no_lookahead.py
│   ├── test_oos_validator_split.py
│   ├── test_performance_tracker_time_buckets.py
│   ├── test_session_runner_intrabar_payload.py
│   ├── test_session_runner_markers.py
│   ├── test_start_run_strategy_overrides_mode.py
│   ├── test_strategy_combo_profiles_api.py
│   ├── test_trailing_stop_regime_aware.py
│   ├── test_wfo_optimizer.py
│   └── test_wfo_optimizer_flow_matrix.py
├── tuning_runner.py
├── walk_forward_runner.py
└── wfo_optimizer.py

26 directories, 100 files
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
