from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from src.models.tuner_requests import AdaptiveTunerRequest


@dataclass
class AdaptiveTunerWorkerDeps:
    adaptive_tuner_jobs: Dict[str, Dict[str, Any]]
    adaptive_tuner_slots: Any
    max_parallel_adaptive_tuners: int
    normalize_clamped_int: Callable[..., Any]
    resolve_tuner_trial_budget: Callable[..., Dict[str, Any]]
    create_isolated_tuner_aos_config_locked: Callable[[str], Awaitable[Path]]
    cleanup_isolated_tuner_aos_config: Callable[[Optional[Path]], None]
    load_aos_config: Callable[..., Dict[str, Any]]
    save_aos_config: Callable[..., bool]
    build_v2_search_space: Callable[..., Dict[str, Any]]
    build_v2_random_candidates: Callable[..., List[Dict[str, Any]]]
    build_v2_candidate_config: Callable[..., Dict[str, Any]]
    build_adaptive_tuner_search_space: Callable[..., Dict[str, Any]]
    build_grid_candidates: Callable[..., List[Dict[str, Any]]]
    build_random_candidates: Callable[..., List[Dict[str, Any]]]
    build_adaptive_candidate_config: Callable[..., Dict[str, Any]]
    prepare_tuner_trial_ticker_config: Callable[[Dict[str, Any]], Dict[str, Any]]
    evaluate_v2_candidate: Callable[..., Awaitable[Dict[str, Any]]]
    evaluate_adaptive_tuner_candidate: Callable[..., Awaitable[Dict[str, Any]]]
    analyze_vectors: Callable[..., Dict[str, Any]]
    persist_tuner_result_to_primary_aos: Callable[..., Awaitable[Dict[str, Any]]]


async def run_v2_adaptive_tuner_job(
    job_id: str,
    request: AdaptiveTunerRequest,
    dates: List[str],
    deps: AdaptiveTunerWorkerDeps,
) -> None:
    """Run a v2 multi-dimensional adaptive tuner job."""
    adaptive_tuner_jobs = deps.adaptive_tuner_jobs
    adaptive_tuner_slots = deps.adaptive_tuner_slots
    MAX_PARALLEL_ADAPTIVE_TUNERS = deps.max_parallel_adaptive_tuners
    _normalize_clamped_int = deps.normalize_clamped_int
    _resolve_tuner_trial_budget = deps.resolve_tuner_trial_budget
    _create_isolated_tuner_aos_config_locked = (
        deps.create_isolated_tuner_aos_config_locked
    )
    _cleanup_isolated_tuner_aos_config = deps.cleanup_isolated_tuner_aos_config
    _load_aos_config = deps.load_aos_config
    _save_aos_config = deps.save_aos_config
    _build_v2_search_space = deps.build_v2_search_space
    _build_v2_random_candidates = deps.build_v2_random_candidates
    _build_v2_candidate_config = deps.build_v2_candidate_config
    _prepare_tuner_trial_ticker_config = deps.prepare_tuner_trial_ticker_config
    _evaluate_v2_candidate = deps.evaluate_v2_candidate
    _analyze_vectors = deps.analyze_vectors
    _persist_tuner_result_to_primary_aos = deps.persist_tuner_result_to_primary_aos

    job = adaptive_tuner_jobs.get(job_id)
    if not job:
        return

    ticker = str(request.ticker or "").upper().strip()
    trial_budget = _resolve_tuner_trial_budget(
        requested_trials=request.n_trials,
        default_trials=32,
        quick_mode=bool(request.quick_mode),
        quick_trial_boost=request.quick_trial_boost,
        max_trials=400,
    )
    n_trials = trial_budget["effective"]
    isolated_aos_config_path: Optional[Path] = None
    async with adaptive_tuner_slots:
        try:
            isolated_aos_config_path = await _create_isolated_tuner_aos_config_locked(
                job_id
            )
            isolated_aos_config_str = str(isolated_aos_config_path)
            job["isolated_aos_config_path"] = isolated_aos_config_str
            job["max_parallel_jobs"] = MAX_PARALLEL_ADAPTIVE_TUNERS

            original_config = _load_aos_config(isolated_aos_config_str)
            original_ticker_config = copy.deepcopy(
                original_config.get("tickers", {}).get(ticker, {})
            )
            cfg_work = copy.deepcopy(original_config)
            if "tickers" not in cfg_work or not isinstance(
                cfg_work.get("tickers"), dict
            ):
                cfg_work["tickers"] = {}

            search_space = _build_v2_search_space(request, original_ticker_config)

            # Anti-overfit: warn when too few days for robust scoring
            score_metric = str(request.score_metric or "").strip().lower()
            if score_metric == "robust" and len(dates) < 10:
                job.setdefault("notes", []).append(
                    f"WARNING: Only {len(dates)} days available for robust scoring. "
                    "Minimum 10-15 days recommended for statistical significance. "
                    "Results may be unreliable."
                )

            # V2 only supports random and optuna (grid is infeasible)
            method = str(request.method or "random").strip().lower()
            if method == "grid":
                method = "random"
                job.setdefault("notes", []).append(
                    "Grid search is not feasible for v2 multi-dimensional space; using random sampling."
                )
            method_used = method

            job["started_at"] = datetime.utcnow().isoformat() + "Z"
            job["status"] = "running"
            job["progress"] = {
                "completed_trials": 0,
                "total_trials": 0,
                "method": method,
            }
            job["trials"] = []
            job["best_trial"] = None
            job["trial_budget"] = trial_budget
            job["search_space_summary"] = {
                "strategy_sets_count": len(search_space.get("strategy_sets", [])),
                "l2_options": {
                    "min_delta": len(search_space.get("l2_min_delta", [])),
                    "min_imbalance": len(search_space.get("l2_min_imbalance", [])),
                    "min_signed_aggression": len(
                        search_space.get("l2_min_signed_aggression", [])
                    ),
                },
                "regime_filter_sets_count": len(
                    search_space.get("regime_filter_sets", [])
                ),
                "evidence_options": {
                    "base_threshold": len(search_space.get("base_threshold", [])),
                    "min_confirming_sources": len(
                        search_space.get("min_confirming_sources", [])
                    ),
                },
            }
            if bool(request.quick_mode) and trial_budget["boost"] > 1:
                job.setdefault("notes", []).append(
                    "Quick mode trial boost applied: "
                    f"{trial_budget['requested']} -> {trial_budget['effective']} "
                    f"(x{trial_budget['boost']})."
                )

            optuna_module = None
            if method == "optuna":
                try:
                    import optuna as _optuna  # type: ignore

                    optuna_module = _optuna
                except Exception:
                    optuna_module = None
                    job.setdefault("notes", []).append(
                        "Optuna is not installed; fallback to random search."
                    )

            if optuna_module is None:
                # Random sampling
                method_used = "random"
                candidates = _build_v2_random_candidates(
                    search_space,
                    n_trials=n_trials,
                    seed=request.seed,
                    neighborhood_search=bool(request.neighborhood_search),
                )
                job["progress"]["total_trials"] = len(candidates)

                for idx, candidate in enumerate(candidates, start=1):
                    next_ticker_cfg = _build_v2_candidate_config(
                        original_ticker_config, candidate, request.adaptive_version
                    )
                    cfg_work["tickers"][ticker] = _prepare_tuner_trial_ticker_config(
                        next_ticker_cfg
                    )
                    if not _save_aos_config(cfg_work, isolated_aos_config_str):
                        raise RuntimeError(
                            "Failed to save temporary AOS config for v2 tuner trial"
                        )

                    result = await _evaluate_v2_candidate(
                        job_id=job_id,
                        ticker=ticker,
                        dates=dates,
                        trial_index=idx,
                        candidate=candidate,
                        request=request,
                        aos_config_path=isolated_aos_config_str,
                    )
                    job["trials"].append(result)
                    current_best = job.get("best_trial")
                    if not isinstance(current_best, dict) or float(
                        result["score"]
                    ) > float(current_best.get("score", -1e12)):
                        job["best_trial"] = result
                    job["progress"]["completed_trials"] = idx
            else:
                # Optuna TPE sampling for v2
                method_used = "optuna"
                sampler = optuna_module.samplers.TPESampler(seed=request.seed)
                study = optuna_module.create_study(
                    direction="maximize", sampler=sampler
                )
                job["progress"]["total_trials"] = n_trials

                for idx in range(1, n_trials + 1):
                    trial = study.ask()
                    ss_idx = trial.suggest_int(
                        "strategy_set_idx", 0, len(search_space["strategy_sets"]) - 1
                    )
                    rf_idx = trial.suggest_int(
                        "regime_filter_idx",
                        0,
                        len(search_space["regime_filter_sets"]) - 1,
                    )
                    tw_idx = trial.suggest_int(
                        "time_window_idx", 0, len(search_space["time_window_sets"]) - 1
                    )
                    rsm_idx = trial.suggest_int(
                        "regime_strategy_map_idx",
                        0,
                        len(search_space["regime_strategy_maps"]) - 1,
                    )
                    candidate = {
                        "strategy_selection_mode": trial.suggest_categorical(
                            "strategy_selection_mode",
                            search_space["strategy_selection_mode"],
                        ),
                        "max_active_strategies": trial.suggest_int(
                            "max_active_strategies",
                            min(search_space["max_active_strategies"]),
                            max(search_space["max_active_strategies"]),
                        ),
                        "min_active_bars_before_switch": trial.suggest_int(
                            "min_active_bars_before_switch",
                            min(search_space["min_active_bars_before_switch"]),
                            max(search_space["min_active_bars_before_switch"]),
                        ),
                        "switch_cooldown_bars": trial.suggest_int(
                            "switch_cooldown_bars",
                            min(search_space["switch_cooldown_bars"]),
                            max(search_space["switch_cooldown_bars"]),
                        ),
                        "flow_bias_enabled": trial.suggest_categorical(
                            "flow_bias_enabled", search_space["flow_bias_enabled"]
                        ),
                        "use_ohlcv_fallbacks": trial.suggest_categorical(
                            "use_ohlcv_fallbacks", search_space["use_ohlcv_fallbacks"]
                        ),
                        "enabled_strategies": list(
                            search_space["strategy_sets"][ss_idx]
                        ),
                        "l2_min_delta": trial.suggest_categorical(
                            "l2_min_delta", search_space["l2_min_delta"]
                        ),
                        "l2_min_imbalance": trial.suggest_categorical(
                            "l2_min_imbalance", search_space["l2_min_imbalance"]
                        ),
                        "l2_min_signed_aggression": trial.suggest_categorical(
                            "l2_min_signed_aggression",
                            search_space["l2_min_signed_aggression"],
                        ),
                        "l2_min_directional_consistency": trial.suggest_categorical(
                            "l2_min_directional_consistency",
                            search_space["l2_min_directional_consistency"],
                        ),
                        "regime_filter": list(
                            search_space["regime_filter_sets"][rf_idx]
                        ),
                        "base_threshold": trial.suggest_categorical(
                            "base_threshold", search_space["base_threshold"]
                        ),
                        "min_confirming_sources": trial.suggest_int(
                            "min_confirming_sources",
                            min(search_space["min_confirming_sources"]),
                            max(search_space["min_confirming_sources"]),
                        ),
                        "min_confidence": trial.suggest_categorical(
                            "min_confidence", search_space["min_confidence"]
                        ),
                        "atr_stop_multiplier": trial.suggest_categorical(
                            "atr_stop_multiplier", search_space["atr_stop_multiplier"]
                        ),
                        "rr_ratio": trial.suggest_categorical(
                            "rr_ratio", search_space["rr_ratio"]
                        ),
                        "trading_hours": list(search_space["time_window_sets"][tw_idx]),
                        "adverse_flow_consistency": trial.suggest_categorical(
                            "adverse_flow_consistency",
                            search_space["adverse_flow_consistency"],
                        ),
                        "adverse_book_pressure": trial.suggest_categorical(
                            "adverse_book_pressure",
                            search_space["adverse_book_pressure"],
                        ),
                        "time_exit_bars": trial.suggest_categorical(
                            "time_exit_bars", search_space["time_exit_bars"]
                        ),
                        "trailing_stop_pct": trial.suggest_categorical(
                            "trailing_stop_pct", search_space["trailing_stop_pct"]
                        ),
                        "regime_strategy_map": search_space["regime_strategy_maps"][
                            rsm_idx
                        ],
                    }

                    next_ticker_cfg = _build_v2_candidate_config(
                        original_ticker_config, candidate, request.adaptive_version
                    )
                    cfg_work["tickers"][ticker] = _prepare_tuner_trial_ticker_config(
                        next_ticker_cfg
                    )
                    if not _save_aos_config(cfg_work, isolated_aos_config_str):
                        raise RuntimeError(
                            "Failed to save temporary AOS config for v2 tuner trial"
                        )

                    result = await _evaluate_v2_candidate(
                        job_id=job_id,
                        ticker=ticker,
                        dates=dates,
                        trial_index=idx,
                        candidate=candidate,
                        request=request,
                        aos_config_path=isolated_aos_config_str,
                    )
                    score = float(result["score"])
                    study.tell(trial, score)
                    job["trials"].append(result)
                    current_best = job.get("best_trial")
                    if not isinstance(current_best, dict) or score > float(
                        current_best.get("score", -1e12)
                    ):
                        job["best_trial"] = result
                    job["progress"]["completed_trials"] = idx

            # --- Vector Analysis ---
            vector_analysis = {}
            if request.include_vector_analysis:
                vector_analysis = _analyze_vectors(
                    job.get("trials", []),
                    min_trades=max(1, request.min_trades_per_vector),
                )
                job["vector_analysis"] = vector_analysis

            # --- Save final merged result ---
            best_trial = job.get("best_trial")
            persist_result = await _persist_tuner_result_to_primary_aos(
                ticker=ticker,
                request=request,
                method_used=method_used,
                dates=dates,
                best_trial=best_trial if isinstance(best_trial, dict) else None,
                vector_analysis=vector_analysis if vector_analysis else None,
            )
            saved_profile = persist_result.get("saved_profile")
            if persist_result.get("persist_best_applied"):
                job.setdefault("notes", []).append(
                    "Best v2 vector candidate was persisted to aos_config.json."
                )

            job["status"] = "completed"
            job["method_used"] = method_used
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"
            job["summary"] = {
                "ticker": ticker,
                "date_from": dates[0] if dates else request.date_from,
                "date_to": dates[-1] if dates else request.date_to,
                "evaluated_days": len(dates),
                "source_effective_days": int(
                    job.get("source_effective_days", len(dates)) or len(dates)
                ),
                "trials": int(job["progress"].get("completed_trials", 0)),
                "best_score": (
                    float(best_trial.get("score", 0.0))
                    if isinstance(best_trial, dict)
                    else None
                ),
                "score_metric": request.score_metric,
                "adaptive_version": request.adaptive_version,
                "persist_best": bool(request.persist_best),
                "l2_required": bool(request.l2_required),
                "l2_only": bool(request.l2_only),
                "quick_mode": bool(request.quick_mode),
                "quick_max_days": _normalize_clamped_int(
                    request.quick_max_days, default=2, min_value=1, max_value=30
                ),
                "quick_trial_boost": trial_budget["boost"],
                "requested_trials": trial_budget["requested"],
                "effective_trial_budget": trial_budget["effective"],
            }
            if isinstance(saved_profile, dict):
                job["saved_profile"] = {
                    "profile_id": saved_profile.get("profile_id"),
                    "created_at": saved_profile.get("created_at"),
                }
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"
        finally:
            _cleanup_isolated_tuner_aos_config(isolated_aos_config_path)


async def run_adaptive_tuner_job(
    job_id: str,
    request: AdaptiveTunerRequest,
    dates: List[str],
    deps: AdaptiveTunerWorkerDeps,
) -> None:
    adaptive_tuner_jobs = deps.adaptive_tuner_jobs
    adaptive_tuner_slots = deps.adaptive_tuner_slots
    MAX_PARALLEL_ADAPTIVE_TUNERS = deps.max_parallel_adaptive_tuners
    _normalize_clamped_int = deps.normalize_clamped_int
    _resolve_tuner_trial_budget = deps.resolve_tuner_trial_budget
    _create_isolated_tuner_aos_config_locked = (
        deps.create_isolated_tuner_aos_config_locked
    )
    _cleanup_isolated_tuner_aos_config = deps.cleanup_isolated_tuner_aos_config
    _load_aos_config = deps.load_aos_config
    _save_aos_config = deps.save_aos_config
    _build_adaptive_tuner_search_space = deps.build_adaptive_tuner_search_space
    _build_grid_candidates = deps.build_grid_candidates
    _build_random_candidates = deps.build_random_candidates
    _build_adaptive_candidate_config = deps.build_adaptive_candidate_config
    _prepare_tuner_trial_ticker_config = deps.prepare_tuner_trial_ticker_config
    _evaluate_adaptive_tuner_candidate = deps.evaluate_adaptive_tuner_candidate
    _persist_tuner_result_to_primary_aos = deps.persist_tuner_result_to_primary_aos

    job = adaptive_tuner_jobs.get(job_id)
    if not job:
        return

    ticker = str(request.ticker or "").upper().strip()
    search_space = _build_adaptive_tuner_search_space(request)
    method = str(request.method or "grid").strip().lower()
    if method not in {"grid", "random", "optuna"}:
        method = "grid"
    trial_budget = _resolve_tuner_trial_budget(
        requested_trials=request.n_trials,
        default_trials=16,
        quick_mode=bool(request.quick_mode),
        quick_trial_boost=request.quick_trial_boost,
        max_trials=400,
    )
    n_trials = trial_budget["effective"]
    isolated_aos_config_path: Optional[Path] = None
    async with adaptive_tuner_slots:
        try:
            isolated_aos_config_path = await _create_isolated_tuner_aos_config_locked(
                job_id
            )
            isolated_aos_config_str = str(isolated_aos_config_path)
            job["isolated_aos_config_path"] = isolated_aos_config_str
            job["max_parallel_jobs"] = MAX_PARALLEL_ADAPTIVE_TUNERS

            original_config = _load_aos_config(isolated_aos_config_str)
            original_ticker_config = copy.deepcopy(
                original_config.get("tickers", {}).get(ticker, {})
            )
            cfg_work = copy.deepcopy(original_config)
            if "tickers" not in cfg_work or not isinstance(
                cfg_work.get("tickers"), dict
            ):
                cfg_work["tickers"] = {}

            job["started_at"] = datetime.utcnow().isoformat() + "Z"
            job["status"] = "running"
            job["progress"] = {
                "completed_trials": 0,
                "total_trials": 0,
                "method": method,
            }
            job["trials"] = []
            job["best_trial"] = None
            job["trial_budget"] = trial_budget
            if bool(request.quick_mode) and trial_budget["boost"] > 1:
                job.setdefault("notes", []).append(
                    "Quick mode trial boost applied: "
                    f"{trial_budget['requested']} -> {trial_budget['effective']} "
                    f"(x{trial_budget['boost']})."
                )

            optuna_module = None
            if method == "optuna":
                try:
                    import optuna as _optuna  # type: ignore

                    optuna_module = _optuna
                except Exception:
                    optuna_module = None
                    job.setdefault("notes", []).append(
                        "Optuna is not installed; fallback to random search."
                    )

            candidates: List[Dict[str, Any]] = []
            method_used = method
            if method == "grid":
                candidates = _build_grid_candidates(search_space)
                if len(candidates) > n_trials:
                    candidates = candidates[:n_trials]
            elif method == "random" or optuna_module is None:
                candidates = _build_random_candidates(
                    search_space, n_trials=n_trials, seed=request.seed
                )
                method_used = "random" if method == "optuna" else method
            else:
                # Optuna ask/tell loop will generate candidates on-the-fly.
                candidates = []
                method_used = "optuna"

            if method_used != "optuna":
                job["progress"]["total_trials"] = len(candidates)
                for idx, candidate in enumerate(candidates, start=1):
                    next_ticker_cfg = _build_adaptive_candidate_config(
                        original_ticker_config,
                        candidate,
                        request.adaptive_version,
                    )
                    cfg_work["tickers"][ticker] = _prepare_tuner_trial_ticker_config(
                        next_ticker_cfg
                    )
                    if not _save_aos_config(cfg_work, isolated_aos_config_str):
                        raise RuntimeError(
                            "Failed to save temporary AOS config for tuner trial"
                        )

                    result = await _evaluate_adaptive_tuner_candidate(
                        job_id=job_id,
                        ticker=ticker,
                        dates=dates,
                        trial_index=idx,
                        candidate=candidate,
                        request=request,
                        aos_config_path=isolated_aos_config_str,
                    )
                    job["trials"].append(result)
                    current_best = job.get("best_trial")
                    if not isinstance(current_best, dict) or float(
                        result["score"]
                    ) > float(current_best.get("score", -1e12)):
                        job["best_trial"] = result
                    job["progress"]["completed_trials"] = idx
            else:
                assert optuna_module is not None
                sampler = optuna_module.samplers.TPESampler(seed=request.seed)
                study = optuna_module.create_study(
                    direction="maximize", sampler=sampler
                )
                job["progress"]["total_trials"] = n_trials
                for idx in range(1, n_trials + 1):
                    trial = study.ask()
                    candidate = {
                        "strategy_selection_mode": trial.suggest_categorical(
                            "strategy_selection_mode",
                            search_space["strategy_selection_mode"],
                        ),
                        "max_active_strategies": trial.suggest_int(
                            "max_active_strategies",
                            min(search_space["max_active_strategies"]),
                            max(search_space["max_active_strategies"]),
                        ),
                        "min_active_bars_before_switch": trial.suggest_int(
                            "min_active_bars_before_switch",
                            min(search_space["min_active_bars_before_switch"]),
                            max(search_space["min_active_bars_before_switch"]),
                        ),
                        "switch_cooldown_bars": trial.suggest_int(
                            "switch_cooldown_bars",
                            min(search_space["switch_cooldown_bars"]),
                            max(search_space["switch_cooldown_bars"]),
                        ),
                        "flow_bias_enabled": trial.suggest_categorical(
                            "flow_bias_enabled", search_space["flow_bias_enabled"]
                        ),
                        "use_ohlcv_fallbacks": trial.suggest_categorical(
                            "use_ohlcv_fallbacks", search_space["use_ohlcv_fallbacks"]
                        ),
                    }
                    next_ticker_cfg = _build_adaptive_candidate_config(
                        original_ticker_config,
                        candidate,
                        request.adaptive_version,
                    )
                    cfg_work["tickers"][ticker] = _prepare_tuner_trial_ticker_config(
                        next_ticker_cfg
                    )
                    if not _save_aos_config(cfg_work, isolated_aos_config_str):
                        raise RuntimeError(
                            "Failed to save temporary AOS config for tuner trial"
                        )

                    result = await _evaluate_adaptive_tuner_candidate(
                        job_id=job_id,
                        ticker=ticker,
                        dates=dates,
                        trial_index=idx,
                        candidate=candidate,
                        request=request,
                        aos_config_path=isolated_aos_config_str,
                    )
                    score = float(result["score"])
                    study.tell(trial, score)
                    job["trials"].append(result)
                    current_best = job.get("best_trial")
                    if not isinstance(current_best, dict) or score > float(
                        current_best.get("score", -1e12)
                    ):
                        job["best_trial"] = result
                    job["progress"]["completed_trials"] = idx

            best_trial = job.get("best_trial")
            persist_result = await _persist_tuner_result_to_primary_aos(
                ticker=ticker,
                request=request,
                method_used=method_used,
                dates=dates,
                best_trial=best_trial if isinstance(best_trial, dict) else None,
            )
            saved_profile = persist_result.get("saved_profile")
            if persist_result.get("persist_best_applied"):
                job.setdefault("notes", []).append(
                    "Best candidate was persisted to aos_config.json."
                )

            job["status"] = "completed"
            job["method_used"] = method_used
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"
            job["summary"] = {
                "ticker": ticker,
                "date_from": dates[0] if dates else request.date_from,
                "date_to": dates[-1] if dates else request.date_to,
                "evaluated_days": len(dates),
                "source_effective_days": int(
                    job.get("source_effective_days", len(dates)) or len(dates)
                ),
                "trials": int(job["progress"].get("completed_trials", 0)),
                "best_score": (
                    float(best_trial.get("score", 0.0))
                    if isinstance(best_trial, dict)
                    else None
                ),
                "score_metric": request.score_metric,
                "adaptive_version": request.adaptive_version,
                "persist_best": bool(request.persist_best),
                "l2_required": bool(request.l2_required),
                "l2_only": bool(request.l2_only),
                "quick_mode": bool(request.quick_mode),
                "quick_max_days": _normalize_clamped_int(
                    request.quick_max_days, default=2, min_value=1, max_value=30
                ),
                "quick_trial_boost": trial_budget["boost"],
                "requested_trials": trial_budget["requested"],
                "effective_trial_budget": trial_budget["effective"],
            }
            if isinstance(saved_profile, dict):
                job["saved_profile"] = {
                    "profile_id": saved_profile.get("profile_id"),
                    "created_at": saved_profile.get("created_at"),
                }
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
            job["finished_at"] = datetime.utcnow().isoformat() + "Z"
        finally:
            _cleanup_isolated_tuner_aos_config(isolated_aos_config_path)
