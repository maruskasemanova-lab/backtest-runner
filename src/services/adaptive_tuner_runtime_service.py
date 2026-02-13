from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException

from src.models.tuner_requests import AdaptiveTunerRequest


@dataclass
class AdaptiveTunerRuntimeDeps:
    active_runners: Dict[str, Any]
    start_run: Callable[[Any], Awaitable[Dict[str, Any]]]
    start_run_request_cls: Any
    normalize_strategy_selection_mode: Callable[[Any], str]
    normalize_clamped_int: Callable[..., Any]
    compute_tuner_score: Callable[..., float]
    compute_tuner_score_robust: Callable[[List[Dict[str, Any]]], float]
    apply_strategy_param_map: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]
    adaptive_tuner_merge_lock: Any
    load_aos_config: Callable[[], Dict[str, Any]]
    save_aos_config: Callable[[Dict[str, Any]], bool]
    build_tuner_profile_entry: Callable[..., Dict[str, Any]]
    normalize_tuner_profiles: Callable[[Any], Any]
    build_v2_candidate_config: Callable[..., Dict[str, Any]]
    build_adaptive_candidate_config: Callable[..., Dict[str, Any]]


async def evaluate_adaptive_tuner_candidate(
    *,
    job_id: str,
    ticker: str,
    dates: List[str],
    trial_index: int,
    candidate: Dict[str, Any],
    request: AdaptiveTunerRequest,
    deps: AdaptiveTunerRuntimeDeps,
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    StartRunRequest = deps.start_run_request_cls
    _normalize_strategy_selection_mode = deps.normalize_strategy_selection_mode
    _normalize_clamped_int = deps.normalize_clamped_int
    _compute_tuner_score = deps.compute_tuner_score
    _compute_tuner_score_robust = deps.compute_tuner_score_robust
    start_run = deps.start_run
    active_runners = deps.active_runners

    total_pnl_pct = 0.0
    total_pnl_dollars = 0.0
    total_win_rate_pct = 0.0
    total_trades = 0
    valid_days = 0
    day_results: List[Dict[str, Any]] = []
    for day_idx, date in enumerate(dates):
        run_id = f"adaptive-tuner-{job_id[:8]}-{trial_index}-{day_idx}"
        run_request = StartRunRequest(
            run_id=run_id,
            ticker=ticker,
            date=date,
            strategy_api_url=request.strategy_api_url,
            aos_config_path=aos_config_path,
            allow_mock_data=bool(request.allow_mock_data),
            comparable_mode=bool(request.comparable_mode),
            apply_ticker_overrides_on_start=False,
            apply_positioning_config_on_start=False,
            l2_confirm_enabled=bool(request.l2_confirm_enabled),
            l2_only=bool(request.l2_only),
            intrabar_execution_recalc_1s=False,
            strategy_selection_mode=_normalize_strategy_selection_mode(
                candidate.get("strategy_selection_mode")
            ),
            max_active_strategies=_normalize_clamped_int(
                candidate.get("max_active_strategies"), default=3, min_value=1, max_value=20
            ),
        )
        run_key: Optional[str] = None
        try:
            start_result = await start_run(run_request)
            run_key = str(start_result.get("run_key", ""))
            runner = active_runners.get(run_key)
            if runner is None:
                raise RuntimeError(f"Runner not found for key {run_key}")
            await runner.run_all(speed_ms=0)
            summary_payload = runner.get_summary()
            session_summary = summary_payload.get("session_summary") if isinstance(summary_payload, dict) else None
            summary = session_summary if isinstance(session_summary, dict) else {}
            pnl_pct = float(summary.get("total_pnl_pct", 0.0) or 0.0)
            pnl_dollars = float(summary.get("total_pnl_dollars", 0.0) or 0.0)
            win_rate_pct = float(summary.get("win_rate", 0.0) or 0.0)
            trades = int(summary.get("total_trades", 0) or 0)
            total_pnl_pct += pnl_pct
            total_pnl_dollars += pnl_dollars
            total_win_rate_pct += win_rate_pct
            total_trades += trades
            valid_days += 1
            day_results.append(
                {
                    "date": date,
                    "success": True,
                    "pnl_pct": pnl_pct,
                    "pnl_dollars": pnl_dollars,
                    "win_rate_pct": win_rate_pct,
                    "trades": trades,
                }
            )
        except HTTPException as exc:
            day_results.append(
                {
                    "date": date,
                    "success": False,
                    "error": f"HTTP {exc.status_code}: {exc.detail}",
                }
            )
        except Exception as exc:
            day_results.append(
                {
                    "date": date,
                    "success": False,
                    "error": str(exc),
                }
            )
        finally:
            if run_key:
                active_runners.pop(run_key, None)

    avg_win_rate_pct = (total_win_rate_pct / valid_days) if valid_days > 0 else 0.0
    if str(request.score_metric or "").strip().lower() == "robust":
        score = _compute_tuner_score_robust(day_results)
    else:
        score = _compute_tuner_score(
            score_metric=request.score_metric,
            total_pnl_pct=total_pnl_pct,
            total_pnl_dollars=total_pnl_dollars,
            avg_win_rate_pct=avg_win_rate_pct,
            total_trades=total_trades,
            valid_days=valid_days,
        )
    return {
        "trial_index": trial_index,
        "candidate": candidate,
        "score": round(float(score), 6),
        "metrics": {
            "valid_days": valid_days,
            "total_days": len(dates),
            "total_trades": total_trades,
            "total_pnl_pct": round(total_pnl_pct, 4),
            "avg_pnl_pct": round((total_pnl_pct / valid_days), 4) if valid_days > 0 else 0.0,
            "total_pnl_dollars": round(total_pnl_dollars, 4),
            "avg_pnl_dollars": round((total_pnl_dollars / valid_days), 4) if valid_days > 0 else 0.0,
            "avg_win_rate_pct": round(avg_win_rate_pct, 4),
        },
        "day_results": day_results,
        "completed_at": datetime.utcnow().isoformat() + "Z",
    }


async def evaluate_v2_candidate(
    *,
    job_id: str,
    ticker: str,
    dates: List[str],
    trial_index: int,
    candidate: Dict[str, Any],
    request: AdaptiveTunerRequest,
    deps: AdaptiveTunerRuntimeDeps,
    aos_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate a v2 candidate — same as v1 but with enriched metrics and v2 config injection."""
    StartRunRequest = deps.start_run_request_cls
    _normalize_strategy_selection_mode = deps.normalize_strategy_selection_mode
    _normalize_clamped_int = deps.normalize_clamped_int
    _compute_tuner_score = deps.compute_tuner_score
    _compute_tuner_score_robust = deps.compute_tuner_score_robust
    _apply_strategy_param_map = deps.apply_strategy_param_map
    start_run = deps.start_run
    active_runners = deps.active_runners

    total_pnl_pct = 0.0
    total_pnl_dollars = 0.0
    total_win_rate_pct = 0.0
    total_trades = 0
    valid_days = 0
    day_results: List[Dict[str, Any]] = []

    for day_idx, date in enumerate(dates):
        run_id = f"adaptive-v2-{job_id[:8]}-{trial_index}-{day_idx}"
        run_request = StartRunRequest(
            run_id=run_id,
            ticker=ticker,
            date=date,
            strategy_api_url=request.strategy_api_url,
            aos_config_path=aos_config_path,
            allow_mock_data=bool(request.allow_mock_data),
            comparable_mode=bool(request.comparable_mode),
            apply_ticker_overrides_on_start=False,
            apply_positioning_config_on_start=False,
            l2_confirm_enabled=bool(request.l2_confirm_enabled),
            l2_only=bool(request.l2_only),
            intrabar_execution_recalc_1s=False,
            strategy_selection_mode=_normalize_strategy_selection_mode(
                candidate.get("strategy_selection_mode")
            ),
            max_active_strategies=_normalize_clamped_int(
                candidate.get("max_active_strategies"), default=3, min_value=1, max_value=20
            ),
        )
        run_key: Optional[str] = None
        try:
            start_result = await start_run(run_request)
            run_key = str(start_result.get("run_key", ""))
            runner = active_runners.get(run_key)
            if runner is None:
                raise RuntimeError(f"Runner not found for key {run_key}")

            # Push per-strategy param overrides (v2) before running the backtest
            v2_param_overrides = {}
            for pkey in ("min_confidence", "atr_stop_multiplier", "rr_ratio", "trailing_stop_pct"):
                pval = candidate.get(pkey)
                if pval is not None:
                    try:
                        v2_param_overrides[pkey] = float(pval)
                    except (TypeError, ValueError):
                        pass
            if v2_param_overrides:
                enabled_strats = candidate.get("enabled_strategies", [])
                if isinstance(enabled_strats, list) and enabled_strats:
                    param_map = {
                        str(s).strip(): dict(v2_param_overrides) for s in enabled_strats if s
                    }
                    if param_map:
                        try:
                            await _apply_strategy_param_map(request.strategy_api_url, param_map)
                        except Exception:
                            pass  # best-effort

            await runner.run_all(speed_ms=0)
            summary_payload = runner.get_summary()
            session_summary = summary_payload.get("session_summary") if isinstance(summary_payload, dict) else None
            summary = session_summary if isinstance(session_summary, dict) else {}
            pnl_pct = float(summary.get("total_pnl_pct", 0.0) or 0.0)
            pnl_dollars = float(summary.get("total_pnl_dollars", 0.0) or 0.0)
            win_rate_pct = float(summary.get("win_rate", 0.0) or 0.0)
            trades = int(summary.get("total_trades", 0) or 0)
            total_pnl_pct += pnl_pct
            total_pnl_dollars += pnl_dollars
            total_win_rate_pct += win_rate_pct
            total_trades += trades
            valid_days += 1
            day_results.append({
                "date": date,
                "success": True,
                "pnl_pct": pnl_pct,
                "pnl_dollars": pnl_dollars,
                "win_rate_pct": win_rate_pct,
                "trades": trades,
                "regime_breakdown": summary.get("regime_trade_breakdown", {}),
                "l2_avg_score": float(summary.get("l2_avg_confirmation_score", 0.0) or 0.0),
            })
        except HTTPException as exc:
            day_results.append({
                "date": date,
                "success": False,
                "error": f"HTTP {exc.status_code}: {exc.detail}",
            })
        except Exception as exc:
            day_results.append({
                "date": date,
                "success": False,
                "error": str(exc),
            })
        finally:
            if run_key:
                active_runners.pop(run_key, None)

    avg_win_rate_pct = (total_win_rate_pct / valid_days) if valid_days > 0 else 0.0
    if str(request.score_metric or "").strip().lower() == "robust":
        # 3-fold temporal cross-validation: score = average of validation-fold scores
        # This prevents candidates from winning on lucky day subsets
        successful_results = [d for d in day_results if d.get("success")]
        n_successful = len(successful_results)
        if n_successful >= 3:
            fold_size = max(1, n_successful // 3)
            val_scores = []
            for fold_idx in range(3):
                fold_start = fold_idx * fold_size
                fold_end = fold_start + fold_size if fold_idx < 2 else n_successful
                val_fold = successful_results[fold_start:fold_end]
                if val_fold:
                    val_scores.append(_compute_tuner_score_robust(val_fold))
            score = sum(val_scores) / len(val_scores) if val_scores else -1_000_000.0
        else:
            # Too few days for CV — use direct score but with heavy penalty
            score = _compute_tuner_score_robust(day_results) * 0.5
    else:
        score = _compute_tuner_score(
            score_metric=request.score_metric,
            total_pnl_pct=total_pnl_pct,
            total_pnl_dollars=total_pnl_dollars,
            avg_win_rate_pct=avg_win_rate_pct,
            total_trades=total_trades,
            valid_days=valid_days,
        )
    return {
        "trial_index": trial_index,
        "candidate": candidate,
        "score": round(float(score), 6),
        "metrics": {
            "valid_days": valid_days,
            "total_days": len(dates),
            "total_trades": total_trades,
            "total_pnl_pct": round(total_pnl_pct, 4),
            "avg_pnl_pct": round((total_pnl_pct / valid_days), 4) if valid_days > 0 else 0.0,
            "total_pnl_dollars": round(total_pnl_dollars, 4),
            "avg_pnl_dollars": round((total_pnl_dollars / valid_days), 4) if valid_days > 0 else 0.0,
            "avg_win_rate_pct": round(avg_win_rate_pct, 4),
        },
        # V2 enriched metadata
        "vector_dimensions": {
            "enabled_strategies": candidate.get("enabled_strategies", []),
            "regime_filter": candidate.get("regime_filter", []),
            "l2_min_imbalance": candidate.get("l2_min_imbalance"),
            "l2_min_signed_aggression": candidate.get("l2_min_signed_aggression"),
            "base_threshold": candidate.get("base_threshold"),
            "min_confirming_sources": candidate.get("min_confirming_sources"),
            "momentum_min_cvd": candidate.get("momentum_min_cvd"),
            "momentum_min_directional_price_change_pct": candidate.get(
                "momentum_min_directional_price_change_pct"
            ),
            "momentum_min_price_trend_efficiency": candidate.get(
                "momentum_min_price_trend_efficiency"
            ),
        },
        "day_results": day_results,
        "completed_at": datetime.utcnow().isoformat() + "Z",
    }


async def persist_tuner_result_to_primary_aos(
    *,
    ticker: str,
    request: AdaptiveTunerRequest,
    method_used: str,
    dates: List[str],
    best_trial: Optional[Dict[str, Any]],
    deps: AdaptiveTunerRuntimeDeps,
    vector_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merge tuner profile into primary aos_config.json under a short critical section.

    Trial-level candidate writes happen against isolated per-job configs, so only
    this final merge touches the shared config.
    """
    adaptive_tuner_merge_lock = deps.adaptive_tuner_merge_lock
    _load_aos_config = deps.load_aos_config
    _save_aos_config = deps.save_aos_config
    _build_tuner_profile_entry = deps.build_tuner_profile_entry
    _normalize_tuner_profiles = deps.normalize_tuner_profiles
    _build_v2_candidate_config = deps.build_v2_candidate_config
    _build_adaptive_candidate_config = deps.build_adaptive_candidate_config

    async with adaptive_tuner_merge_lock:
        final_config = _load_aos_config()
        if "tickers" not in final_config or not isinstance(final_config.get("tickers"), dict):
            final_config["tickers"] = {}

        updated_ticker_cfg = copy.deepcopy(final_config["tickers"].get(ticker, {}))
        saved_profile = None
        persist_best_applied = False

        if isinstance(best_trial, dict):
            saved_profile = _build_tuner_profile_entry(
                ticker=ticker,
                request=request,
                method_used=method_used,
                dates=dates,
                best_trial=best_trial,
            )
            if vector_analysis:
                saved_profile["vector_analysis"] = vector_analysis

            existing_profiles = _normalize_tuner_profiles(
                updated_ticker_cfg.get("adaptive_tuner_profiles", [])
            )
            existing_profiles.insert(0, saved_profile)
            updated_ticker_cfg["adaptive_tuner_profiles"] = existing_profiles[:30]

            if request.persist_best:
                best_candidate = best_trial.get("candidate", {})
                if int(request.adaptive_version or 1) == 2:
                    updated_ticker_cfg = _build_v2_candidate_config(
                        updated_ticker_cfg,
                        best_candidate if isinstance(best_candidate, dict) else {},
                        request.adaptive_version,
                    )
                else:
                    updated_ticker_cfg = _build_adaptive_candidate_config(
                        updated_ticker_cfg,
                        best_candidate if isinstance(best_candidate, dict) else {},
                        request.adaptive_version,
                    )
                updated_ticker_cfg["active_adaptive_tuner_profile_id"] = saved_profile["profile_id"]
                persist_best_applied = True
            else:
                updated_ticker_cfg["active_adaptive_tuner_profile_id"] = str(
                    updated_ticker_cfg.get("active_adaptive_tuner_profile_id", "")
                ).strip() or saved_profile["profile_id"]

        final_config["tickers"][ticker] = updated_ticker_cfg
        if not _save_aos_config(final_config):
            raise RuntimeError("Failed to save final AOS tuner result")

    return {
        "saved_profile": saved_profile,
        "persist_best_applied": persist_best_applied,
    }
