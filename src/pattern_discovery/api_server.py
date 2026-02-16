"""
Pattern Discovery API Server - FastAPI routes for pattern discovery service.

Provides REST API endpoints for:
- Pattern discovery jobs
- Pattern library management
- Real-time pattern matching
- Evidence for strategy engine
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models import (
    PatternInput,
    PatternMatch,
    PatternSnapshot,
    PatternLibrary,
    ClusterPattern,
    SequentialPattern,
    DiscoveryConfig,
    MatchConfig,
    DiscoverRequest,
    DiscoverResponse,
    MatchRequest,
    MatchResponse,
    EvidenceRequest,
    EvidenceResponse,
)
from .extractor import extract_snapshots_from_backtest, FeatureExtractor
from .clustering import discover_cluster_patterns
from .sequential import discover_sequential_patterns
from .library import PatternLibraryManager, get_pattern_library_path
from .matcher import PatternMatcher
from .evidence import format_evidence_for_api, PatternEvidenceSource

logger = logging.getLogger(__name__)

# Configuration from environment
PATTERN_DISCOVERY_PORT = int(os.getenv("PATTERN_DISCOVERY_PORT", "8003"))
PATTERN_DISCOVERY_HOST = os.getenv("PATTERN_DISCOVERY_HOST", "0.0.0.0")
RUNNER_API_URL = os.getenv("RUNNER_API_URL", "http://localhost:8002")
STRATEGY_API_URL = os.getenv("STRATEGY_API_URL", "http://localhost:8001")
PATTERN_LIBRARY_PATH = Path(os.getenv("PATTERN_LIBRARY_PATH", "pattern_library"))

# Global state
discovery_jobs: Dict[str, Dict[str, Any]] = {}
pattern_matchers: Dict[str, PatternMatcher] = {}
library_manager = PatternLibraryManager(PATTERN_LIBRARY_PATH)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Pattern Discovery API starting up...")
    PATTERN_LIBRARY_PATH.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Shutdown
    logger.info("Pattern Discovery API shutting down...")


app = FastAPI(
    title="Pattern Discovery API",
    description="API for discovering and matching market patterns",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health & Status
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "pattern-discovery",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# ============================================================================
# Pattern Discovery Jobs
# ============================================================================

@app.post("/api/pattern-discovery/discover", response_model=DiscoverResponse)
async def start_discovery(
    request: DiscoverRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a pattern discovery job.
    
    Extracts features from backtest data, discovers patterns through
    clustering and sequential mining, and saves to pattern library.
    """
    job_id = f"pd-{uuid.uuid4().hex[:12]}"
    
    # Initialize job state
    discovery_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "request": request.model_dump(),
        "progress": {
            "phase": "initializing",
            "current": 0,
            "total": 100,
        },
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "results": None,
        "errors": [],
    }
    
    # Start background task
    background_tasks.add_task(
        run_discovery_job,
        job_id,
        request,
    )
    
    return DiscoverResponse(
        job_id=job_id,
        status="pending",
        progress=discovery_jobs[job_id]["progress"],
    )


@app.get("/api/pattern-discovery/jobs/{job_id}")
async def get_discovery_job(job_id: str):
    """Get status and results of a discovery job."""
    job = discovery_jobs.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@app.get("/api/pattern-discovery/jobs")
async def list_discovery_jobs(limit: int = Query(20, ge=1, le=100)):
    """List recent discovery jobs."""
    jobs = list(discovery_jobs.values())
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return jobs[:limit]


async def run_discovery_job(
    job_id: str,
    request: DiscoverRequest,
):
    """Run pattern discovery job in background."""
    job = discovery_jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()
    
    try:
        # Phase 1: Extract snapshots
        job["progress"] = {"phase": "extracting_snapshots", "current": 0, "total": 100}
        
        reports_dir = Path("reports")
        snapshots = extract_snapshots_from_backtest(
            ticker=request.ticker,
            date_from=request.date_from,
            date_to=request.date_to,
            reports_dir=reports_dir,
            config=request.discovery_config,
        )
        
        job["progress"] = {"phase": "extracting_snapshots", "current": 30, "total": 100}
        
        if not snapshots:
            raise ValueError("No snapshots extracted from backtest data")
        
        # Phase 2: Cluster pattern discovery
        job["progress"] = {"phase": "clustering", "current": 30, "total": 100}
        
        cluster_patterns = []
        if request.discovery_config.clustering_enabled:
            cluster_patterns = discover_cluster_patterns(
                snapshots=snapshots,
                config=request.discovery_config,
                ticker=request.ticker,
            )
        
        job["progress"] = {"phase": "clustering", "current": 60, "total": 100}
        
        # Phase 3: Sequential pattern mining
        job["progress"] = {"phase": "sequential_mining", "current": 60, "total": 100}
        
        sequential_patterns = []
        if request.discovery_config.sequential_enabled:
            sequential_patterns = discover_sequential_patterns(
                snapshots=snapshots,
                config=request.discovery_config,
                ticker=request.ticker,
            )
        
        job["progress"] = {"phase": "sequential_mining", "current": 80, "total": 100}
        
        # Phase 4: Save library
        job["progress"] = {"phase": "saving_library", "current": 80, "total": 100}
        
        library = library_manager.create_library(
            ticker=request.ticker,
            cluster_patterns=cluster_patterns,
            sequential_patterns=sequential_patterns,
            total_snapshots=len(snapshots),
            discovery_config=request.discovery_config,
        )
        
        library_path = library_manager.save_library(library)
        
        # Update job state
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow().isoformat()
        job["progress"] = {"phase": "completed", "current": 100, "total": 100}
        job["results"] = {
            "snapshots_extracted": len(snapshots),
            "cluster_patterns_found": len(cluster_patterns),
            "sequential_patterns_found": len(sequential_patterns),
            "total_patterns_saved": len(cluster_patterns) + len(sequential_patterns),
            "library_path": str(library_path),
            "best_pattern": _get_best_pattern_info(cluster_patterns, sequential_patterns),
        }
        
        # Cache matcher for this ticker
        pattern_matchers[request.ticker] = PatternMatcher(library=library)
        
    except Exception as e:
        logger.exception(f"Discovery job {job_id} failed")
        job["status"] = "failed"
        job["completed_at"] = datetime.utcnow().isoformat()
        job["errors"].append(str(e))
        job["results"] = None


def _get_best_pattern_info(
    cluster_patterns: List[ClusterPattern],
    sequential_patterns: List[SequentialPattern],
) -> Optional[Dict[str, Any]]:
    """Get info about the best pattern."""
    all_patterns = list(cluster_patterns) + list(sequential_patterns)
    if not all_patterns:
        return None
    
    best = max(all_patterns, key=lambda p: p.win_rate * p.support)
    return {
        "pattern_id": best.pattern_id,
        "win_rate": best.win_rate,
        "support": best.support,
        "avg_pnl_pct": best.avg_pnl_pct,
    }


# ============================================================================
# Pattern Library Management
# ============================================================================

@app.get("/api/pattern-discovery/patterns/{ticker}")
async def get_patterns_for_ticker(ticker: str):
    """Get pattern library for a ticker."""
    ticker = ticker.upper()
    library = library_manager.load_library_for_ticker(ticker)
    
    if not library:
        raise HTTPException(
            status_code=404,
            detail=f"No pattern library found for {ticker}"
        )
    
    return {
        "ticker": library.ticker,
        "version": library.version,
        "created_at": library.created_at.isoformat(),
        "updated_at": library.updated_at.isoformat(),
        "cluster_patterns": [
            {
                "pattern_id": p.pattern_id,
                "pattern_name": p.pattern_name,
                "direction": p.direction.value,
                "win_rate": p.win_rate,
                "support": p.support,
                "avg_pnl_pct": p.avg_pnl_pct,
                "confidence_interval": list(p.confidence_interval),
                "feature_importance": p.feature_importance,
            }
            for p in library.cluster_patterns
        ],
        "sequential_patterns": [
            {
                "pattern_id": p.pattern_id,
                "pattern_name": p.pattern_name,
                "sequence": p.sequence,
                "direction": p.direction.value,
                "win_rate": p.win_rate,
                "support": p.support,
                "avg_pnl_pct": p.avg_pnl_pct,
            }
            for p in library.sequential_patterns
        ],
        "total_snapshots_analyzed": library.total_snapshots_analyzed,
        "best_pattern_id": library.best_pattern_id,
    }


@app.get("/api/pattern-discovery/libraries")
async def list_libraries():
    """List all available pattern libraries."""
    return library_manager.list_libraries()


@app.get("/api/pattern-discovery/libraries/{ticker}/stats")
async def get_library_stats(ticker: str):
    """Get statistics for a ticker's pattern library."""
    ticker = ticker.upper()
    library = library_manager.load_library_for_ticker(ticker)
    
    if not library:
        raise HTTPException(
            status_code=404,
            detail=f"No pattern library found for {ticker}"
        )
    
    return library_manager.get_library_stats(library)


# ============================================================================
# Pattern Matching
# ============================================================================

@app.post("/api/pattern-discovery/match", response_model=MatchResponse)
async def match_patterns(request: MatchRequest):
    """
    Match current market state against patterns.
    
    Returns list of matching patterns with evidence for trading decisions.
    """
    ticker = request.ticker.upper()
    
    # Get or create matcher
    matcher = pattern_matchers.get(ticker)
    if not matcher:
        library = library_manager.load_library_for_ticker(ticker)
        if not library:
            return MatchResponse(
                matches=[],
                best_match=None,
            )
        matcher = PatternMatcher(library=library, config=request.config)
        pattern_matchers[ticker] = matcher
    
    # Convert feature vector to PatternInput
    features = PatternInput.from_feature_vector(request.feature_vector)
    
    # Match patterns
    matches = matcher.match(features, request.recent_states)
    
    # Format response
    return MatchResponse(
        matches=matches,
        best_match=matches[0] if matches else None,
    )


@app.get("/api/pattern-discovery/evidence/{ticker}")
async def get_evidence(
    ticker: str,
    feature_vector_json: str = Query(...),
    recent_states_json: str = Query("[]"),
):
    """
    Get pattern evidence for strategy engine.
    
    This endpoint is called by the strategy engine to get
    pattern evidence for the EvidenceDecisionEngine.
    """
    ticker = ticker.upper()
    
    try:
        feature_vector = json.loads(feature_vector_json)
        recent_states = json.loads(recent_states_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    # Get matcher
    matcher = pattern_matchers.get(ticker)
    if not matcher:
        library = library_manager.load_library_for_ticker(ticker)
        if not library:
            return EvidenceResponse(
                source_name="no_library",
                direction="neutral",
                strength=0.0,
                calibrated=0.0,
                reasoning=f"No pattern library found for {ticker}",
            )
        matcher = PatternMatcher(library=library)
        pattern_matchers[ticker] = matcher
    
    # Get evidence
    features = PatternInput.from_feature_vector(feature_vector)
    best_match = matcher.get_best_match(features, recent_states)
    
    if not best_match:
        return EvidenceResponse(
            source_name="no_match",
            direction="neutral",
            strength=0.0,
            calibrated=0.0,
            reasoning="No matching pattern found",
        )
    
    return EvidenceResponse(
        source_name=best_match.pattern_name,
        direction=best_match.direction.value,
        strength=round(best_match.evidence_strength, 2),
        calibrated=round(best_match.historical_win_rate, 4),
        reasoning=best_match.evidence_reasoning,
    )


# ============================================================================
# Pattern-Aware Tuning
# ============================================================================

class PatternTunerRequest(BaseModel):
    """Request for pattern-aware tuning."""
    ticker: str
    date_from: str
    date_to: str
    pattern_config: Dict[str, Any] = {}
    tuner_config: Dict[str, Any] = {}
    strategy_api_url: str = "http://localhost:8001"
    runner_api_url: str = "http://localhost:8002"


@app.post("/api/pattern-discovery/tuner/run")
async def start_pattern_tuner(
    request: PatternTunerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start a pattern-aware adaptive tuning job.
    
    Tunes pattern matching parameters along with strategy parameters.
    """
    job_id = f"pt-{uuid.uuid4().hex[:12]}"
    
    # Initialize job state
    discovery_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "type": "pattern_tuner",
        "request": request.model_dump(),
        "progress": {
            "phase": "initializing",
            "current": 0,
            "total": 100,
        },
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "completed_at": None,
        "results": None,
        "errors": [],
    }
    
    # Start background task
    background_tasks.add_task(
        run_pattern_tuner_job,
        job_id,
        request,
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "created_at": discovery_jobs[job_id]["created_at"],
    }


async def run_pattern_tuner_job(
    job_id: str,
    request: PatternTunerRequest,
):
    """Run pattern-aware tuning job."""
    job = discovery_jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()
    
    try:
        # This would integrate with the existing adaptive tuner
        # For now, we'll do a simplified version
        
        job["progress"] = {"phase": "loading_library", "current": 10, "total": 100}
        
        library = library_manager.load_library_for_ticker(request.ticker)
        if not library:
            raise ValueError(f"No pattern library found for {request.ticker}")
        
        job["progress"] = {"phase": "tuning", "current": 50, "total": 100}
        
        # Extract pattern tuning dimensions
        pattern_config = request.pattern_config
        min_similarity_options = pattern_config.get(
            "pattern_min_similarity_options", [0.6, 0.7, 0.8]
        )
        min_win_rate_options = pattern_config.get(
            "pattern_min_win_rate_options", [0.50, 0.55, 0.60]
        )
        evidence_weight_options = pattern_config.get(
            "pattern_evidence_weight_options", [0.0, 0.1, 0.15]
        )
        
        # Run tuning trials (simplified - would use Optuna in production)
        best_config = {
            "pattern_min_similarity": min_similarity_options[0],
            "pattern_min_win_rate": min_win_rate_options[0],
            "pattern_evidence_weight": evidence_weight_options[0],
        }
        best_score = 0.0
        
        for sim in min_similarity_options:
            for wr in min_win_rate_options:
                for ew in evidence_weight_options:
                    # Evaluate configuration
                    # In production, this would run backtests
                    score = _evaluate_pattern_config(
                        library=library,
                        min_similarity=sim,
                        min_win_rate=wr,
                        evidence_weight=ew,
                    )
                    
                    if score > best_score:
                        best_score = score
                        best_config = {
                            "pattern_min_similarity": sim,
                            "pattern_min_win_rate": wr,
                            "pattern_evidence_weight": ew,
                        }
        
        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow().isoformat()
        job["progress"] = {"phase": "completed", "current": 100, "total": 100}
        job["results"] = {
            "best_config": best_config,
            "best_score": best_score,
            "library_used": str(library_manager.library_dir / f"{request.ticker}_patterns_{library.version}.json"),
        }
        
    except Exception as e:
        logger.exception(f"Pattern tuner job {job_id} failed")
        job["status"] = "failed"
        job["completed_at"] = datetime.utcnow().isoformat()
        job["errors"].append(str(e))


def _evaluate_pattern_config(
    library: PatternLibrary,
    min_similarity: float,
    min_win_rate: float,
    evidence_weight: float,
) -> float:
    """
    Evaluate a pattern configuration.
    
    Simplified scoring - in production would run actual backtests.
    """
    # Count patterns that pass filters
    valid_patterns = [
        p for p in library.cluster_patterns
        if p.win_rate >= min_win_rate
    ]
    
    if not valid_patterns:
        return 0.0
    
    # Score based on pattern quality and coverage
    avg_win_rate = sum(p.win_rate for p in valid_patterns) / len(valid_patterns)
    total_support = sum(p.support for p in valid_patterns)
    
    # Combine metrics
    score = avg_win_rate * min(1.0, total_support / 100) * (1 + evidence_weight)
    
    return score


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the Pattern Discovery API server."""
    import uvicorn
    
    uvicorn.run(
        "src.pattern_discovery.api_server:app",
        host=PATTERN_DISCOVERY_HOST,
        port=PATTERN_DISCOVERY_PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
