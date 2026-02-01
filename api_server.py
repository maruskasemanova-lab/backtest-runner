"""
Unified Backtest Runner API Server.
Orchestrates the look-ahead free data feeding and strategy evaluation.
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import logging
from pathlib import Path

from data_loader import DataLoader
from session_runner import SessionRunner, RunConfig
from decision_tracker import MarkerType
from available_data import get_discovery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BacktestRunner")

# ============ App Setup ============
app = FastAPI(
    title="Unified Backtest Runner",
    description="Walk-forward backtesting with strategy evaluation and decision visualization",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Global State ============
data_loader = DataLoader()
active_runners: Dict[str, SessionRunner] = {}
connected_clients: List[WebSocket] = []


# ============ Pydantic Models ============
class StartRunRequest(BaseModel):
    run_id: str
    ticker: str
    date: str
    data_file: Optional[str] = None  # If None, auto-discover from available data
    strategy_api_url: str = "http://localhost:8001"
    regime_detection_minutes: int = 15


class PlayRequest(BaseModel):
    speed_ms: int = 100  # Delay between bars in ms


# ============ WebSocket Management ============
async def broadcast(message: Dict[str, Any]):
    """Broadcast message to all connected WebSocket clients."""
    if not connected_clients:
        return
    
    message_text = json.dumps(message, default=str)
    disconnected = []
    
    for client in connected_clients:
        try:
            await client.send_text(message_text)
        except Exception:
            disconnected.append(client)
    
    for client in disconnected:
        connected_clients.remove(client)


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await websocket.accept()
    connected_clients.append(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                
                # Handle client commands
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg.get("type") == "subscribe":
                    run_id = msg.get("run_id")
                    await websocket.send_json({
                        "type": "subscribed",
                        "run_id": run_id
                    })
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {len(connected_clients)}")


# ============ API Endpoints ============

@app.get("/")
async def root():
    return {
        "name": "Unified Backtest Runner",
        "version": "1.0.0",
        "active_runs": len(active_runners)
    }


@app.get("/api/health")
async def health():
    return {"status": "healthy"}


@app.get("/api/available-data")
async def get_available_data():
    """Get available tickers and date ranges from data files."""
    discovery = get_discovery()
    return discovery.to_dict()


@app.get("/api/data/files")
async def list_data_files():
    """List available data files."""
    return data_loader.list_available_files()


@app.post("/api/run/start")
async def start_run(request: StartRunRequest):
    """Start a new backtest run."""
    run_key = f"{request.run_id}:{request.ticker}:{request.date}"
    
    if run_key in active_runners:
        raise HTTPException(400, f"Run already exists: {run_key}")
    
    # Load data
    data_file = request.data_file
    
    # Auto-discover data file if not provided
    if not data_file:
        discovery = get_discovery()
        data_file = discovery.get_file_for_date(request.ticker, request.date)
    
    if data_file:
        try:
            if data_file.endswith('.parquet') or data_file.endswith('.parq'):
                df = data_loader.load_parquet(data_file)
            else:
                df = data_loader.load_csv(data_file)
            df = data_loader.filter_trading_day(df, request.date)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))
    else:
        # No data file found - generate mock data
        logger.warning(f"No data file found for {request.ticker} on {request.date}, using mock data")
        df = data_loader.generate_mock_data(
            ticker=request.ticker,
            date=request.date
        )
    
    # Convert to list of bar dicts
    bars = list(data_loader.get_bars_iterator(df))
    
    if not bars:
        raise HTTPException(400, "No data available for the specified date")
    
    # Create runner
    config = RunConfig(
        run_id=request.run_id,
        ticker=request.ticker,
        date=request.date,
        strategy_api_url=request.strategy_api_url,
        regime_detection_minutes=request.regime_detection_minutes
    )
    
    runner = SessionRunner(config)
    runner.load_bars(bars)
    
    # Register callbacks for broadcasting
    async def on_bar(bar):
        await broadcast({
            "type": "bar",
            "run_id": request.run_id,
            "bar": bar
        })
    
    async def on_decision(marker):
        await broadcast({
            "type": "decision",
            "run_id": request.run_id,
            "marker": marker
        })
    
    runner.on_bar(on_bar)
    runner.on_decision(on_decision)
    
    active_runners[run_key] = runner
    
    logger.info(f"Started run {run_key} with {len(bars)} bars")
    
    return {
        "success": True,
        "run_key": run_key,
        "total_bars": len(bars),
        "first_bar": bars[0] if bars else None,
        "last_bar": bars[-1] if bars else None
    }


@app.get("/api/run/{run_id}/{ticker}/{date}/state")
async def get_run_state(run_id: str, ticker: str, date: str):
    """Get current state of a run."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    return runner.get_state()


@app.post("/api/run/{run_id}/{ticker}/{date}/step")
async def step_run(run_id: str, ticker: str, date: str):
    """Advance the run by one bar."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    result = await runner.step()
    
    return result


@app.post("/api/run/{run_id}/{ticker}/{date}/play")
async def play_run(run_id: str, ticker: str, date: str, request: PlayRequest):
    """Start auto-advancing through bars."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    
    if runner.is_running:
        return {"success": False, "error": "Run already in progress"}
    
    # Start in background
    asyncio.create_task(runner.run_all(speed_ms=request.speed_ms))
    
    return {"success": True, "speed_ms": request.speed_ms}


@app.post("/api/run/{run_id}/{ticker}/{date}/pause")
async def pause_run(run_id: str, ticker: str, date: str):
    """Pause a running backtest."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    runner.pause()
    
    return {"success": True, "is_paused": True}


@app.post("/api/run/{run_id}/{ticker}/{date}/resume")
async def resume_run(run_id: str, ticker: str, date: str):
    """Resume a paused backtest."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    runner.resume()
    
    return {"success": True, "is_paused": False}


@app.post("/api/run/{run_id}/{ticker}/{date}/stop")
async def stop_run(run_id: str, ticker: str, date: str):
    """Stop a running backtest."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    runner.stop()
    
    return {"success": True, "stopped": True}


@app.get("/api/run/{run_id}/{ticker}/{date}/bars")
async def get_processed_bars(run_id: str, ticker: str, date: str):
    """Get all processed bars so far."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    return {
        "bars": runner.get_processed_bars(),
        "current_index": runner.current_bar_index,
        "total_bars": len(runner.bars)
    }


@app.get("/api/run/{run_id}/{ticker}/{date}/markers")
async def get_markers(run_id: str, ticker: str, date: str, marker_type: Optional[str] = None):
    """Get all decision markers."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    
    if marker_type:
        try:
            mt = MarkerType(marker_type)
            return runner.tracker.get_markers(mt)
        except ValueError:
            raise HTTPException(400, f"Invalid marker type: {marker_type}")
    
    return runner.get_markers()


@app.get("/api/run/{run_id}/{ticker}/{date}/chart-annotations")
async def get_chart_annotations(run_id: str, ticker: str, date: str):
    """Get markers formatted for chart display."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    return runner.get_chart_annotations()


@app.get("/api/run/{run_id}/{ticker}/{date}/summary")
async def get_run_summary(run_id: str, ticker: str, date: str):
    """Get session summary."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    return runner.get_summary()


@app.delete("/api/run/{run_id}/{ticker}/{date}")
async def delete_run(run_id: str, ticker: str, date: str):
    """Delete a run from memory."""
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]
    runner.stop()
    del active_runners[run_key]
    
    return {"success": True, "deleted": run_key}


@app.get("/api/runs")
async def list_runs():
    """List all active runs."""
    runs = []
    for key, runner in active_runners.items():
        runs.append(runner.get_state())
    return runs


# ============ Static Files (Frontend) ============
frontend_path = Path(__file__).parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")


# ============ Main ============
if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )
