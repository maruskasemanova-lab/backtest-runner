from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List

from fastapi import HTTPException

from src.models.tuner_requests import AdaptiveTunerRequest


@dataclass
class AdaptiveTunerOrchestrationDeps:
    adaptive_tuner_jobs: Dict[str, Dict[str, Any]]
    max_parallel_adaptive_tuners: int
    normalize_non_negative_int: Callable[..., Any]
    normalize_clamped_int: Callable[..., Any]
    iter_date_strings: Callable[[str, str], List[str]]
    resolve_l2_tuning_dates: Callable[..., List[str]]
    sample_evenly_spaced_days: Callable[..., List[str]]
    run_v1_job: Callable[[str, AdaptiveTunerRequest, List[str]], Any]
    run_v2_job: Callable[[str, AdaptiveTunerRequest, List[str]], Any]
    create_task: Callable[[Any], Any]
    uuid4_factory: Callable[[], Any]


async def run_adaptive_tuner(
    request: AdaptiveTunerRequest,
    deps: AdaptiveTunerOrchestrationDeps,
) -> Dict[str, Any]:
    """Start an adaptive-tuner job (v1 or v2) and return a job id for polling."""
    ticker = str(request.ticker or "").upper().strip()
    if not ticker:
        raise HTTPException(400, "ticker is required")
    version = deps.normalize_non_negative_int(request.adaptive_version, default=1, max_value=10)
    if version not in (1, 2):
        raise HTTPException(400, "Only adaptive versions 1 and 2 are supported by this tuner.")

    requested_dates = deps.iter_date_strings(request.date_from, request.date_to)
    if not requested_dates:
        raise HTTPException(400, "No dates to tune.")
    effective_dates = deps.resolve_l2_tuning_dates(
        ticker=ticker,
        date_from=request.date_from,
        date_to=request.date_to,
        l2_required=bool(request.l2_required),
    )
    if not effective_dates:
        raise HTTPException(
            400,
            "No eligible dates found for adaptive tuning in the requested range."
            " Check OHLCV/L2 coverage for this ticker.",
        )
    source_effective_dates = list(effective_dates)

    quick_mode = bool(request.quick_mode)
    quick_max_days = deps.normalize_clamped_int(
        request.quick_max_days, default=2, min_value=1, max_value=30
    )
    quick_trial_boost = deps.normalize_clamped_int(
        request.quick_trial_boost, default=3, min_value=1, max_value=10
    )
    if quick_mode:
        effective_dates = deps.sample_evenly_spaced_days(effective_dates, max_days=quick_max_days)
        if not effective_dates:
            raise HTTPException(
                400,
                "Quick mode could not find representative dates in requested range.",
            )

    job_id = deps.uuid4_factory().hex
    method = str(request.method or ("random" if version == 2 else "grid")).strip().lower()
    if method not in {"grid", "random", "optuna"}:
        method = "random" if version == 2 else "grid"

    deps.adaptive_tuner_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "request": request.model_dump() if hasattr(request, "model_dump") else request.dict(),
        "progress": {"completed_trials": 0, "total_trials": 0, "method": method},
        "trials": [],
        "best_trial": None,
        "notes": [],
        "requested_date_from": request.date_from,
        "requested_date_to": request.date_to,
        "source_effective_dates": source_effective_dates,
        "source_effective_date_from": source_effective_dates[0] if source_effective_dates else None,
        "source_effective_date_to": source_effective_dates[-1] if source_effective_dates else None,
        "source_effective_days": len(source_effective_dates),
        "effective_dates": effective_dates,
        "effective_date_from": effective_dates[0] if effective_dates else None,
        "effective_date_to": effective_dates[-1] if effective_dates else None,
        "effective_days": len(effective_dates),
        "quick_mode": quick_mode,
        "quick_max_days": quick_max_days,
        "quick_trial_boost": quick_trial_boost,
        "adaptive_version": version,
        "max_parallel_jobs": deps.max_parallel_adaptive_tuners,
        "isolated_aos_config_path": None,
    }
    active_same_strategy_url = [
        existing
        for existing in deps.adaptive_tuner_jobs.values()
        if existing.get("job_id") != job_id
        and str(existing.get("request", {}).get("strategy_api_url", "")).strip()
        == str(request.strategy_api_url).strip()
        and str(existing.get("status", "")).lower() in {"queued", "running"}
    ]
    if active_same_strategy_url:
        deps.adaptive_tuner_jobs[job_id]["notes"].append(
            "WARNING: Another tuner job is using the same strategy_api_url. "
            "For true parallel tuning without orchestrator-state interference, "
            "run each tuner against a different strategy API port."
        )
    if quick_mode:
        deps.adaptive_tuner_jobs[job_id]["notes"].append(
            "Quick mode enabled: sampled "
            f"{len(effective_dates)}/{len(source_effective_dates)} days; "
            f"trial budget multiplier x{quick_trial_boost}."
        )

    if version == 2:
        deps.create_task(deps.run_v2_job(job_id, request, effective_dates))
    else:
        deps.create_task(deps.run_v1_job(job_id, request, effective_dates))

    return {
        "job_id": job_id,
        "status": "queued",
        "ticker": ticker,
        "date_from": request.date_from,
        "date_to": request.date_to,
        "adaptive_version": version,
        "effective_days": len(effective_dates),
        "source_effective_days": len(source_effective_dates),
        "effective_date_from": effective_dates[0] if effective_dates else None,
        "effective_date_to": effective_dates[-1] if effective_dates else None,
        "l2_required": bool(request.l2_required),
        "quick_mode": quick_mode,
        "quick_max_days": quick_max_days,
        "quick_trial_boost": quick_trial_boost,
        "max_parallel_jobs": deps.max_parallel_adaptive_tuners,
    }


def get_adaptive_tuner_job(job_id: str, deps: AdaptiveTunerOrchestrationDeps) -> Dict[str, Any]:
    """Get current status and results of an adaptive tuner job."""
    job = deps.adaptive_tuner_jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Adaptive tuner job not found: {job_id}")
    return job


def list_adaptive_tuner_jobs(
    deps: AdaptiveTunerOrchestrationDeps,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """List recent adaptive tuner jobs."""
    limit = max(1, min(100, int(limit)))
    jobs = list(deps.adaptive_tuner_jobs.values())
    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return jobs[:limit]
