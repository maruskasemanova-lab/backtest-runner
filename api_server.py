"""
Unified Backtest Runner API Server.
Orchestrates the look-ahead free data feeding and strategy evaluation.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import logging
from pathlib import Path
import aiohttp
import pandas as pd

from data_loader import DataLoader
from session_runner import SessionRunner, RunConfig
from decision_tracker import MarkerType
from available_data import get_discovery, reset_discovery
from src.config_io import (
    extract_multilayer_payload,
    load_json_file,
    save_json_file,
)
from src.l2_data_manager import L2DataManager
from src.l2_feature_service import L2FeatureService
from src.databento_service import DatabentoService

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
l2_manager = L2DataManager()
l2_features = L2FeatureService(manager=l2_manager, logger=logger)
active_runners: Dict[str, SessionRunner] = {}
connected_clients: List[WebSocket] = []
databento_svc = DatabentoService()
STRATEGY_OVERRIDES_PATH = Path(__file__).parent / "strategy_overrides.json"
AOS_CONFIG_PATH = Path(__file__).parent / "aos_optimization" / "aos_config.json"


def _load_strategy_overrides() -> Dict[str, Any]:
    return load_json_file(STRATEGY_OVERRIDES_PATH, default={})


def _load_aos_config() -> Dict[str, Any]:
    """Load AOS optimization config from JSON file."""
    return load_json_file(AOS_CONFIG_PATH, default={"version": "1.0.0", "tickers": {}})


def _save_aos_config(config: Dict[str, Any]) -> bool:
    """Save AOS optimization config to JSON file."""
    ok = save_json_file(AOS_CONFIG_PATH, payload=config)
    if not ok:
        logger.error("Failed to save AOS config.")
    return ok


async def _apply_strategy_overrides(strategy_api_url: str, ticker: str) -> None:
    overrides = _load_strategy_overrides().get(ticker.upper())
    if not overrides:
        return
    async with aiohttp.ClientSession() as session:
        for strat_name, params in overrides.items():
            try:
                async with session.post(
                    f"{strategy_api_url}/api/strategies/update",
                    json={"strategy_name": strat_name, "params": params},
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"Override failed for {ticker}:{strat_name} (HTTP {resp.status})"
                        )
            except Exception as e:
                logger.warning(f"Override error for {ticker}:{strat_name}: {e}")


async def _apply_global_trailing(strategy_api_url: str, trailing_stop_pct: Optional[float]) -> None:
    if trailing_stop_pct is None:
        return
    if trailing_stop_pct <= 0:
        logger.warning("Global trailing_stop_pct ignored (must be > 0).")
        return
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{strategy_api_url}/api/strategies") as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to fetch strategies for global trailing (HTTP {resp.status})")
                    return
                strategies = await resp.json()
            for name in strategies.keys():
                try:
                    async with session.post(
                        f"{strategy_api_url}/api/strategies/update",
                        json={"strategy_name": name, "params": {"trailing_stop_pct": trailing_stop_pct}},
                    ) as upd:
                        if upd.status != 200:
                            logger.warning(
                                f"Global trailing update failed for {name} (HTTP {upd.status})"
                            )
                except Exception as e:
                    logger.warning(f"Global trailing update error for {name}: {e}")
    except Exception as e:
        logger.warning(f"Global trailing update failed: {e}")


def _extract_multilayer_payload(ticker_config: Dict[str, Any]) -> Dict[str, Any]:
    return extract_multilayer_payload(ticker_config)


async def _apply_aos_optimizations(strategy_api_url: str, ticker: str) -> Dict[str, Any]:
    """Apply AOS optimizations (time filter, long_only, params) to strategy API."""
    aos_config = _load_aos_config()
    ticker_config = aos_config.get("tickers", {}).get(ticker.upper(), {})
    
    if not ticker_config:
        return {}
    
    applied = {}
    
    # Get the strategy name from AOS config
    strategy_name = ticker_config.get("strategy")
    params = dict(ticker_config.get("params", {}))
    if "long_only" in ticker_config and "long_only" not in params:
        params["long_only"] = bool(ticker_config["long_only"])
    
    multilayer_payload = _extract_multilayer_payload(ticker_config)

    try:
        async with aiohttp.ClientSession() as session:
            if strategy_name and params:
                async with session.post(
                    f"{strategy_api_url}/api/strategies/update",
                    json={"strategy_name": strategy_name, "params": params},
                ) as resp:
                    if resp.status == 200:
                        applied["strategy"] = strategy_name
                        applied["params"] = params
                        logger.info(f"Applied AOS params for {ticker}: {params}")
                    else:
                        logger.warning(f"AOS update failed for {ticker}:{strategy_name} (HTTP {resp.status})")

            if multilayer_payload:
                async with session.post(
                    f"{strategy_api_url}/api/multilayer/config",
                    json=multilayer_payload,
                ) as ml_resp:
                    if ml_resp.status == 200:
                        applied["multilayer"] = multilayer_payload
                        logger.info(f"Applied AOS multilayer config for {ticker}: {multilayer_payload}")
                    else:
                        logger.warning(
                            f"AOS multilayer update failed for {ticker} (HTTP {ml_resp.status})"
                        )
    except Exception as e:
        logger.warning(f"AOS update error for {ticker}: {e}")
    
    # Store time and directional filters for session to use
    applied["trading_hours"] = ticker_config.get("trading_hours")
    applied["long_only"] = bool(ticker_config.get("long_only", params.get("long_only", False)))
    applied["time_filter_enabled"] = bool(
        ticker_config.get("time_filter_enabled", bool(ticker_config.get("trading_hours")))
    )
    if isinstance(ticker_config.get("l2"), dict):
        applied["l2"] = ticker_config.get("l2", {})
    
    return applied


async def _configure_session(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
    date: str,
    regime_detection_minutes: int,
    regime_refresh_bars: int,
    account_size_usd: float,
    risk_per_trade_pct: float = 1.0,
    max_position_notional_pct: float = 100.0,
    max_fill_participation_rate: float = 0.20,
    min_fill_ratio: float = 0.35,
    enable_partial_take_profit: bool = True,
    partial_take_profit_rr: float = 1.0,
    partial_take_profit_fraction: float = 0.5,
    time_exit_bars: int = 40,
    adverse_flow_exit_enabled: bool = True,
    adverse_flow_threshold: float = 0.12,
    adverse_flow_min_hold_bars: int = 3,
    l2_confirm_enabled: bool = False,
    l2_min_delta: float = 0.0,
    l2_min_imbalance: float = 0.0,
    l2_min_iceberg_bias: float = 0.0,
    l2_lookback_bars: int = 3,
    l2_min_participation_ratio: float = 0.0,
    l2_min_directional_consistency: float = 0.0,
    l2_min_signed_aggression: float = 0.0,
) -> None:
    params = {
        "run_id": run_id,
        "ticker": ticker,
        "date": date,
        "regime_detection_minutes": int(regime_detection_minutes),
        "regime_refresh_bars": int(regime_refresh_bars),
        "account_size_usd": float(account_size_usd),
        "risk_per_trade_pct": float(risk_per_trade_pct),
        "max_position_notional_pct": float(max_position_notional_pct),
        "max_fill_participation_rate": float(max_fill_participation_rate),
        "min_fill_ratio": float(min_fill_ratio),
        "enable_partial_take_profit": int(bool(enable_partial_take_profit)),
        "partial_take_profit_rr": float(partial_take_profit_rr),
        "partial_take_profit_fraction": float(partial_take_profit_fraction),
        "time_exit_bars": int(time_exit_bars),
        "adverse_flow_exit_enabled": int(bool(adverse_flow_exit_enabled)),
        "adverse_flow_threshold": float(adverse_flow_threshold),
        "adverse_flow_min_hold_bars": int(adverse_flow_min_hold_bars),
        "l2_confirm_enabled": int(bool(l2_confirm_enabled)),
        "l2_min_delta": float(l2_min_delta),
        "l2_min_imbalance": float(l2_min_imbalance),
        "l2_min_iceberg_bias": float(l2_min_iceberg_bias),
        "l2_lookback_bars": int(l2_lookback_bars),
        "l2_min_participation_ratio": float(l2_min_participation_ratio),
        "l2_min_directional_consistency": float(l2_min_directional_consistency),
        "l2_min_signed_aggression": float(l2_min_signed_aggression),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/session/config",
                params=params,
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        f"Session config failed (HTTP {resp.status}) for {run_id}:{ticker}:{date}"
                    )
    except Exception as e:
        logger.warning(f"Session config error for {run_id}:{ticker}:{date}: {e}")


async def _clear_remote_strategy_sessions(
    strategy_api_url: str,
    run_id: str,
    ticker: str,
) -> None:
    """
    Best-effort cleanup of strategy API session state.

    This prevents sticky per-run state (phase/cooldown/session caches) from
    affecting subsequent replays with the same run_id+ticker.
    """
    normalized_ticker = ticker.upper()

    async def _clear_v2(session: aiohttp.ClientSession) -> bool:
        async with session.delete(
            f"{strategy_api_url}/api/session/run",
            params={"run_id": run_id, "ticker": normalized_ticker},
        ) as resp:
            if resp.status == 200:
                return True
            # Endpoint might not exist on older strategy API builds.
            if resp.status in (404, 405):
                return False
            logger.warning(
                f"Session run-clear failed (HTTP {resp.status}) for {run_id}:{normalized_ticker}"
            )
            return False

    async def _clear_legacy(session: aiohttp.ClientSession) -> None:
        try:
            async with session.get(f"{strategy_api_url}/api/sessions") as resp:
                if resp.status != 200:
                    logger.warning(
                        f"Session list failed (HTTP {resp.status}) for {run_id}:{normalized_ticker}"
                    )
                    return
                payload = await resp.json()
        except Exception as exc:
            logger.warning(f"Session list error for {run_id}:{normalized_ticker}: {exc}")
            return

        if not isinstance(payload, dict):
            return

        dates_to_clear: List[str] = []
        for session_state in payload.values():
            if not isinstance(session_state, dict):
                continue
            if session_state.get("run_id") != run_id:
                continue
            if str(session_state.get("ticker", "")).upper() != normalized_ticker:
                continue
            date_val = session_state.get("date")
            if isinstance(date_val, str) and date_val:
                dates_to_clear.append(date_val)

        for date_val in sorted(set(dates_to_clear)):
            try:
                async with session.delete(
                    f"{strategy_api_url}/api/session",
                    params={
                        "run_id": run_id,
                        "ticker": normalized_ticker,
                        "date": date_val,
                    },
                ) as resp:
                    if resp.status not in (200, 404):
                        logger.warning(
                            f"Legacy session clear failed (HTTP {resp.status}) "
                            f"for {run_id}:{normalized_ticker}:{date_val}"
                        )
            except Exception as exc:
                logger.warning(
                    f"Legacy session clear error for {run_id}:{normalized_ticker}:{date_val}: {exc}"
                )

    try:
        async with aiohttp.ClientSession() as session:
            used_v2 = await _clear_v2(session)
            if not used_v2:
                await _clear_legacy(session)
    except Exception as exc:
        logger.warning(f"Remote session cleanup error for {run_id}:{normalized_ticker}: {exc}")


async def _reset_remote_orchestrator_state(strategy_api_url: str) -> bool:
    """
    Best-effort full reset of remote strategy/orchestrator state.

    Returns True when a reset endpoint acknowledged the request, False when the
    endpoint is unavailable or reset failed.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": "all", "clear_sessions": "true"},
            ) as resp:
                if resp.status == 200:
                    return True
                if resp.status in (404, 405):
                    # Older strategy API builds do not expose this endpoint.
                    return False
                logger.warning(
                    f"Remote orchestrator reset failed (HTTP {resp.status}) at {strategy_api_url}"
                )
                return False
    except Exception as exc:
        logger.warning(f"Remote orchestrator reset error at {strategy_api_url}: {exc}")
        return False


async def _reset_remote_orchestrator_state_scoped(
    strategy_api_url: str, scope: str = "session"
) -> bool:
    """Reset remote orchestrator with a specific scope (session/learning/all)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/reset",
                params={"scope": scope, "clear_sessions": "true"},
            ) as resp:
                return resp.status == 200
    except Exception as exc:
        logger.warning(f"Remote orchestrator scoped reset error: {exc}")
        return False


async def _load_remote_checkpoint(
    strategy_api_url: str, checkpoint_path: str
) -> Optional[Dict]:
    """Load a checkpoint on the remote strategy API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/load",
                params={"path": checkpoint_path},
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(
                    f"Remote checkpoint load failed (HTTP {resp.status}): {checkpoint_path}"
                )
                return None
    except Exception as exc:
        logger.warning(f"Remote checkpoint load error: {exc}")
        return None


async def _save_remote_checkpoint(
    strategy_api_url: str,
    run_id: str = "",
    ticker: str = "",
    date_from: str = "",
    date_to: str = "",
) -> Optional[str]:
    """Auto-save checkpoint after a successful backtest run."""
    try:
        params = {
            k: v for k, v in {
                "run_id": run_id, "ticker": ticker,
                "date_from": date_from, "date_to": date_to,
            }.items() if v
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{strategy_api_url}/api/orchestrator/checkpoint/save",
                params=params,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    path = result.get("path")
                    logger.info(f"Auto-saved checkpoint: {path}")
                    return path
                return None
    except Exception as exc:
        logger.warning(f"Checkpoint auto-save error: {exc}")
        return None


def _to_utc_datetime(value: Any) -> datetime:
    return l2_features.to_utc_datetime(value)


def _build_l2_feature_map(
    ticker: str,
    start_dt_utc: datetime,
    end_dt_utc: datetime,
) -> tuple[Dict[int, Dict[str, float]], Dict[str, Any]]:
    return l2_features.build_feature_map(
        ticker=ticker,
        start_dt_utc=start_dt_utc,
        end_dt_utc=end_dt_utc,
    )


def _attach_l2_features(
    bars: List[Dict[str, Any]],
    feature_map: Dict[int, Dict[str, float]],
    l2_only: bool = False,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    return l2_features.attach_features(
        bars=bars,
        feature_map=feature_map,
        l2_only=l2_only,
    )


# ============ Pydantic Models ============
class StartRunRequest(BaseModel):
    run_id: str
    ticker: str
    date: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    data_file: Optional[str] = None  # If None, auto-discover from available data
    strategy_api_url: str = "http://localhost:8001"
    regime_detection_minutes: int = 15
    regime_refresh_bars: int = 12
    trailing_stop_pct: Optional[float] = None
    account_size_usd: float = 10_000.0
    risk_per_trade_pct: float = 1.0
    max_position_notional_pct: float = 100.0
    max_fill_participation_rate: float = 0.20
    min_fill_ratio: float = 0.35
    enable_partial_take_profit: bool = True
    partial_take_profit_rr: float = 1.0
    partial_take_profit_fraction: float = 0.5
    time_exit_bars: int = 40
    adverse_flow_exit_enabled: bool = True
    adverse_flow_threshold: float = 0.12
    adverse_flow_min_hold_bars: int = 3
    allow_mock_data: bool = False
    l2_only: bool = False
    l2_confirm_enabled: bool = False
    l2_min_delta: float = 0.0
    l2_min_imbalance: float = 0.0
    l2_min_iceberg_bias: float = 0.0
    l2_lookback_bars: int = 3
    l2_min_participation_ratio: float = 0.0
    l2_min_directional_consistency: float = 0.0
    l2_min_signed_aggression: float = 0.0
    # Checkpoint: warm-start from a previous backtest's learning state
    checkpoint_path: Optional[str] = None
    auto_save_checkpoint: bool = True


class PlayRequest(BaseModel):
    # Accept strings like "max" / "10hz" as well as raw millisecond values.
    speed_ms: Optional[Union[int, str]] = 100


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
    return databento_svc.get_available_data_summary(refresh=False)


@app.get("/api/strategy-overrides")
async def get_strategy_overrides():
    """Get optimized strategy parameters per ticker."""
    return _load_strategy_overrides()


@app.get("/api/strategy-overrides/{ticker}")
async def get_ticker_overrides(ticker: str):
    """Get optimized strategy parameters for a specific ticker."""
    overrides = _load_strategy_overrides()
    return overrides.get(ticker.upper(), {})


@app.get("/api/data/files")
async def list_data_files():
    """List available data files."""
    return data_loader.list_available_files()


@app.get("/api/aos-config")
async def get_aos_config():
    """Get full AOS optimization config."""
    return _load_aos_config()


@app.get("/api/aos-config/{ticker}")
async def get_ticker_aos_config(ticker: str):
    """Get AOS config for a specific ticker."""
    config = _load_aos_config()
    ticker_config = config.get("tickers", {}).get(ticker.upper(), {})
    return ticker_config


class AOSUpdateRequest(BaseModel):
    ticker: str
    config: Dict[str, Any]


@app.post("/api/aos-config/update")
async def update_aos_config(request: AOSUpdateRequest):
    """Update AOS config for a specific ticker."""
    config = _load_aos_config()
    
    if "tickers" not in config:
        config["tickers"] = {}
    
    # Merge with existing config
    ticker_upper = request.ticker.upper()
    existing = config["tickers"].get(ticker_upper, {})
    existing.update(request.config)
    config["tickers"][ticker_upper] = existing
    
    # Save
    if _save_aos_config(config):
        logger.info(f"Updated AOS config for {ticker_upper}: {request.config}")
        return {"success": True, "config": existing}
    else:
        raise HTTPException(500, "Failed to save AOS config")


@app.post("/api/run/start")
async def start_run(request: StartRunRequest):
    """Start a new backtest run."""
    ticker = request.ticker.upper()

    # Resolve date range
    if request.date_from and request.date_to:
        range_start = request.date_from
        range_end = request.date_to
    elif request.date:
        range_start = request.date
        range_end = request.date
    else:
        raise HTTPException(400, "Either date or date_from/date_to must be provided")

    run_date_label = (
        f"{range_start}_to_{range_end}"
        if range_start != range_end or request.date_from or request.date_to
        else range_start
    )

    run_key = f"{request.run_id}:{ticker}:{run_date_label}"
    
    if run_key in active_runners:
        raise HTTPException(400, f"Run already exists: {run_key}")

    # Orchestrator state reset: cold start (full) or warm start (session-only).
    checkpoint_loaded = None
    if request.checkpoint_path:
        # Warm start: reset only per-session state, then load checkpoint
        orchestrator_reset = await _reset_remote_orchestrator_state_scoped(
            request.strategy_api_url, scope="session"
        )
        checkpoint_loaded = await _load_remote_checkpoint(
            request.strategy_api_url, request.checkpoint_path
        )
    else:
        # Cold start (default): full reset for deterministic backtests
        orchestrator_reset = await _reset_remote_orchestrator_state(request.strategy_api_url)

    # Defensive cleanup in strategy API for reruns with the same run_id+ticker.
    await _clear_remote_strategy_sessions(request.strategy_api_url, request.run_id, ticker)

    # Apply per-ticker strategy overrides (best-effort)
    await _apply_strategy_overrides(request.strategy_api_url, ticker)
    # Apply AOS optimizations (time filter, long_only, params)
    aos_applied = await _apply_aos_optimizations(request.strategy_api_url, ticker)
    # Apply global trailing (best-effort, overrides per-ticker trailing)
    await _apply_global_trailing(request.strategy_api_url, request.trailing_stop_pct)

    # Load data
    data_file = request.data_file
    
    # Auto-discover data file(s) if not provided
    if not data_file:
        # Prefer centralized catalog (Data Manager + runner use the same inventory).
        databento_svc.scan_existing_files()
        data_files = databento_svc.get_files_for_range(
            ticker=ticker,
            start_date=range_start,
            end_date=range_end,
            schema_prefix="ohlcv-",
        )
        if not data_files:
            # Backward-compatible fallback only when centralized catalog has no
            # OHLCV entries for this ticker at all.
            catalog_rows = databento_svc.list_catalog(refresh=False, ticker=ticker)
            has_catalog_ohlcv = any(
                str(row.get("schema", "")).lower().startswith("ohlcv-")
                and row.get("status") == "ready"
                for row in catalog_rows
            )
            if not has_catalog_ohlcv:
                discovery = get_discovery()
                data_files = discovery.get_files_for_range(ticker, range_start, range_end)
    else:
        data_files = [data_file]

    if data_files:
        dfs = []
        skipped_files = []
        for file in data_files:
            try:
                if file.endswith('.parquet') or file.endswith('.parq'):
                    dfs.append(data_loader.load_parquet(file))
                else:
                    dfs.append(data_loader.load_csv(file))
            except FileNotFoundError as e:
                raise HTTPException(404, str(e))
            except Exception as e:
                logger.warning(f"Skipping invalid data file {file}: {e}")
                skipped_files.append(file)
                continue

        if not dfs:
            skipped_note = f" Skipped files: {', '.join(skipped_files)}" if skipped_files else ""
            raise HTTPException(400, f"No usable data files for the specified date/range.{skipped_note}")

        df = pd.concat(dfs, ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df = data_loader.filter_trading_range(df, range_start, range_end)
        if aos_applied.get("time_filter_enabled") and aos_applied.get("trading_hours"):
            df = data_loader.filter_trading_hours(df, aos_applied.get("trading_hours"))
    else:
        if not request.allow_mock_data:
            raise HTTPException(
                404,
                f"No data files found for {ticker} in range {range_start} to {range_end}. "
                "Backtest aborted to avoid mock-data contamination."
            )
        logger.warning(
            f"No data file found for {ticker} in range {range_start} to {range_end}, using mock data (allow_mock_data=True)"
        )
        df = data_loader.generate_mock_data(ticker=ticker, date=range_start)
    
    # Convert to list of bar dicts
    bars = list(data_loader.get_bars_iterator(df))
    
    if not bars:
        raise HTTPException(400, "No data available for the specified date/range")

    aos_l2_cfg = aos_applied.get("l2", {}) if isinstance(aos_applied.get("l2"), dict) else {}

    def _pick_l2_float(request_value: Any, cfg_key: str) -> float:
        try:
            req = float(request_value)
        except (TypeError, ValueError):
            req = 0.0
        if abs(req) > 1e-12:
            return req
        try:
            return float(aos_l2_cfg.get(cfg_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    requested_l2_only = bool(request.l2_only)
    requested_l2_confirm = bool(
        request.l2_confirm_enabled or bool(aos_l2_cfg.get("confirm_enabled", False))
    )
    l2_min_delta = _pick_l2_float(request.l2_min_delta, "min_delta")
    l2_min_imbalance = _pick_l2_float(request.l2_min_imbalance, "min_imbalance")
    l2_min_iceberg_bias = _pick_l2_float(request.l2_min_iceberg_bias, "min_iceberg_bias")
    l2_min_participation_ratio = _pick_l2_float(
        request.l2_min_participation_ratio, "min_participation_ratio"
    )
    l2_min_directional_consistency = _pick_l2_float(
        request.l2_min_directional_consistency, "min_directional_consistency"
    )
    l2_min_signed_aggression = _pick_l2_float(
        request.l2_min_signed_aggression, "min_signed_aggression"
    )

    # Keep request value unless left at default and AOS provides an override.
    if int(request.l2_lookback_bars) != 3:
        l2_lookback_bars = max(1, int(request.l2_lookback_bars))
    else:
        try:
            l2_lookback_bars = max(1, int(aos_l2_cfg.get("lookback_bars", request.l2_lookback_bars)))
        except (TypeError, ValueError):
            l2_lookback_bars = max(1, int(request.l2_lookback_bars))

    # Optional L2 feature enrichment and filtering.
    l2_stats: Dict[str, Any] = {
        "requested_l2_only": requested_l2_only,
        "requested_l2_confirm_enabled": requested_l2_confirm,
        "aos_l2_config_applied": bool(aos_l2_cfg),
        "has_l2": False,
        "footprint_bars": 0,
        "icebergs": 0,
        "covered_minutes": 0,
        "bars_with_l2": 0,
        "bars_total": len(bars),
        "bars_after_filter": len(bars),
    }
    use_l2 = bool(requested_l2_only or requested_l2_confirm)
    if use_l2:
        # Expand slightly to include last bar bucket in inclusive range.
        first_ts_utc = _to_utc_datetime(bars[0]["timestamp"])
        last_ts_utc = _to_utc_datetime(bars[-1]["timestamp"]) + timedelta(minutes=1)
        feature_map, build_stats = _build_l2_feature_map(
            ticker=ticker,
            start_dt_utc=first_ts_utc,
            end_dt_utc=last_ts_utc,
        )
        l2_stats.update(build_stats)
        bars, attach_stats = _attach_l2_features(bars, feature_map, l2_only=requested_l2_only)
        l2_stats.update(attach_stats)
        # Guard against false positives where files exist but requested range has zero overlap.
        l2_stats["has_l2"] = bool(l2_stats.get("bars_with_l2", 0) > 0)

        if requested_l2_only and not bars:
            raise HTTPException(
                400,
                f"L2-only mode requested but no L2-aligned bars found for {ticker} "
                f"in range {range_start} to {range_end}.",
            )
        if requested_l2_confirm and not l2_stats.get("has_l2"):
            logger.warning(
                f"L2 confirmation requested for {ticker}, but no L2 data was found. "
                "Falling back to non-L2 confirmation for this run."
            )
    
    # Configure session defaults after strategy/multi-layer updates and after
    # we know whether L2 confirmation is actually feasible for this run.
    effective_l2_confirm = bool(requested_l2_confirm and l2_stats.get("has_l2"))
    await _configure_session(
        request.strategy_api_url,
        request.run_id,
        ticker,
        range_start,
        request.regime_detection_minutes,
        request.regime_refresh_bars,
        request.account_size_usd,
        risk_per_trade_pct=request.risk_per_trade_pct,
        max_position_notional_pct=request.max_position_notional_pct,
        max_fill_participation_rate=request.max_fill_participation_rate,
        min_fill_ratio=request.min_fill_ratio,
        enable_partial_take_profit=request.enable_partial_take_profit,
        partial_take_profit_rr=request.partial_take_profit_rr,
        partial_take_profit_fraction=request.partial_take_profit_fraction,
        time_exit_bars=request.time_exit_bars,
        adverse_flow_exit_enabled=request.adverse_flow_exit_enabled,
        adverse_flow_threshold=request.adverse_flow_threshold,
        adverse_flow_min_hold_bars=request.adverse_flow_min_hold_bars,
        l2_confirm_enabled=effective_l2_confirm,
        l2_min_delta=l2_min_delta,
        l2_min_imbalance=l2_min_imbalance,
        l2_min_iceberg_bias=l2_min_iceberg_bias,
        l2_lookback_bars=l2_lookback_bars,
        l2_min_participation_ratio=l2_min_participation_ratio,
        l2_min_directional_consistency=l2_min_directional_consistency,
        l2_min_signed_aggression=l2_min_signed_aggression,
    )

    if not bars:
        raise HTTPException(400, "No data available for the specified date/range")

    # Load QQQ reference bars for cross-asset context (best-effort)
    ref_bars_map = {}
    if ticker.upper() != 'QQQ':
        try:
            databento_svc.scan_existing_files()
            qqq_files = databento_svc.get_files_for_range(
                ticker='QQQ', start_date=range_start, end_date=range_end,
                schema_prefix="ohlcv-",
            )
            if not qqq_files:
                discovery = get_discovery()
                qqq_files = discovery.get_files_for_range('QQQ', range_start, range_end)
            if qqq_files:
                qqq_dfs = []
                for f in qqq_files:
                    try:
                        if f.endswith('.parquet') or f.endswith('.parq'):
                            qqq_dfs.append(data_loader.load_parquet(f))
                        else:
                            qqq_dfs.append(data_loader.load_csv(f))
                    except Exception:
                        continue
                if qqq_dfs:
                    qqq_df = pd.concat(qqq_dfs, ignore_index=True)
                    qqq_df = data_loader.filter_trading_range(qqq_df, range_start, range_end)
                    for qqq_bar in data_loader.get_bars_iterator(qqq_df):
                        ts = qqq_bar.get('timestamp')
                        ts_key = (ts.isoformat() if hasattr(ts, 'isoformat')
                                  else str(ts))
                        qqq_bar['ticker'] = 'QQQ'
                        ref_bars_map[ts_key] = qqq_bar
                    logger.info(f"Loaded {len(ref_bars_map)} QQQ reference bars for cross-asset")
        except Exception as e:
            logger.debug(f"Could not load QQQ reference data: {e}")

    # Create runner
    config = RunConfig(
        run_id=request.run_id,
        ticker=ticker,
        date=run_date_label,
        date_from=range_start,
        date_to=range_end,
        strategy_api_url=request.strategy_api_url,
        regime_detection_minutes=request.regime_detection_minutes
    )

    runner = SessionRunner(config)
    runner.ref_bars_map = ref_bars_map
    runner.load_bars(bars)
    
    # Register callbacks for broadcasting
    async def on_bar(bar):
        await broadcast({
            "type": "bar",
            "run_id": request.run_id,
            "ticker": ticker,
            "bar": bar
        })
    
    async def on_decision(marker):
        await broadcast({
            "type": "decision",
            "run_id": request.run_id,
            "ticker": ticker,
            "marker": marker
        })
    
    runner.on_bar(on_bar)
    runner.on_decision(on_decision)
    
    # Store checkpoint auto-save metadata on runner for use after run_all
    runner._checkpoint_auto_save = request.auto_save_checkpoint
    runner._checkpoint_strategy_url = request.strategy_api_url
    runner._checkpoint_loaded = checkpoint_loaded

    active_runners[run_key] = runner

    logger.info(f"Started run {run_key} with {len(bars)} bars")

    return {
        "success": True,
        "run_key": run_key,
        "ticker": ticker,
        "total_bars": len(bars),
        "strategy_state_reset": orchestrator_reset,
        "checkpoint_loaded": checkpoint_loaded,
        "data_files": data_files,
        "aos_applied": aos_applied,
        "l2_applied": {
            **l2_stats,
            "effective_l2_confirm_enabled": effective_l2_confirm,
            "l2_min_delta": l2_min_delta,
            "l2_min_imbalance": l2_min_imbalance,
            "l2_min_iceberg_bias": l2_min_iceberg_bias,
            "l2_lookback_bars": l2_lookback_bars,
            "l2_min_participation_ratio": l2_min_participation_ratio,
            "l2_min_directional_consistency": l2_min_directional_consistency,
            "l2_min_signed_aggression": l2_min_signed_aggression,
        },
        "execution_config": {
            "account_size_usd": request.account_size_usd,
            "risk_per_trade_pct": request.risk_per_trade_pct,
            "max_position_notional_pct": request.max_position_notional_pct,
            "max_fill_participation_rate": request.max_fill_participation_rate,
            "min_fill_ratio": request.min_fill_ratio,
            "enable_partial_take_profit": request.enable_partial_take_profit,
            "partial_take_profit_rr": request.partial_take_profit_rr,
            "partial_take_profit_fraction": request.partial_take_profit_fraction,
            "time_exit_bars": request.time_exit_bars,
            "adverse_flow_exit_enabled": request.adverse_flow_exit_enabled,
            "adverse_flow_threshold": request.adverse_flow_threshold,
            "adverse_flow_min_hold_bars": request.adverse_flow_min_hold_bars,
        },
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
async def play_run(
    run_id: str,
    ticker: str,
    date: str,
    request: Optional[PlayRequest] = Body(default=None),
    speed_ms: Optional[Union[int, str]] = None,
    raw_request: Request = None,
):
    """Start or resume auto-advancing through bars.
    - Accepts JSON body `{ "speed_ms": ... }` but also query param `speed_ms`.
    - Defaults to max speed when not provided.
    - If paused, simply resumes without restarting.
    """
    run_key = f"{run_id}:{ticker}:{date}"
    
    if run_key not in active_runners:
        raise HTTPException(404, f"Run not found: {run_key}")
    
    runner = active_runners[run_key]

    # If we were paused, just resume.
    if runner.is_running and runner.is_paused:
        runner.resume()
        return {"success": True, "resumed": True, "speed_ms": runner.last_run_speed if hasattr(runner, "last_run_speed") else "unknown"}
    
    if runner.is_running:
        return {"success": False, "error": "Run already in progress"}

    # Ingest speed from body, query string, or default to max.
    raw_speed = None
    if request and request.speed_ms is not None:
        raw_speed = request.speed_ms
    elif speed_ms is not None:
        raw_speed = speed_ms
    else:
        # Best-effort fallback for odd clients sending raw JSON without schema
        try:
            if raw_request:
                payload = await raw_request.json()
                raw_speed = payload.get("speed_ms") if isinstance(payload, dict) else None
        except Exception:
            raw_speed = None
    if raw_speed is None:
        raw_speed = "max"

    # Normalize common aliases so downstream handling is consistent
    if isinstance(raw_speed, str):
        normalized = raw_speed.strip().lower()
        if normalized in {"instant", "max", "fast"}:
            raw_speed = "max"
        elif normalized.endswith("hz") and normalized[:-2].isdigit():
            raw_speed = f"{int(normalized[:-2])}hz"
        elif normalized in {"", "null", "none"}:
            raw_speed = "max"
    
    # Start in background with optional checkpoint auto-save on completion
    runner.last_run_speed = raw_speed  # cache for resume info

    async def _run_and_maybe_save():
        await runner.run_all(speed_ms=raw_speed)
        if getattr(runner, '_checkpoint_auto_save', False):
            url = getattr(runner, '_checkpoint_strategy_url', '')
            if url:
                await _save_remote_checkpoint(
                    url,
                    run_id=runner.config.run_id,
                    ticker=runner.config.ticker,
                    date_from=runner.config.date_from or runner.config.date,
                    date_to=runner.config.date_to or runner.config.date,
                )

    asyncio.create_task(_run_and_maybe_save())

    return {"success": True, "speed_ms": raw_speed}


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
    await _clear_remote_strategy_sessions(
        runner.config.strategy_api_url,
        runner.config.run_id,
        runner.config.ticker,
    )
    del active_runners[run_key]
    
    return {"success": True, "deleted": run_key}


@app.get("/api/runs")
async def list_runs():
    """List all active runs."""
    runs = []
    for key, runner in active_runners.items():
        runs.append(runner.get_state())
    return runs


@app.get("/api/l2/footprint/{ticker}")
async def get_footprint_data(ticker: str, start_time: str, end_time: str, timeframe: str = "1min"):
    """Get L2 Footprint data for a specific time range."""
    # Parse times
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "Invalid timestamp format. Use ISO 8601.")
        
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")
    
    # Ensure data is loaded
    # Simple logic: try loading data for the dates involved. 
    # TODO: Optimize to avoid reloading if already in memory
    l2_manager.load_data(ticker, start_date, end_date) 
    
    # Get aggregated bars
    bars = l2_manager.get_footprint_bars(ticker, start_dt, end_dt, timeframe)
    
    return {"ticker": ticker, "timeframe": timeframe, "bars": bars}


@app.get("/api/l2/icebergs/{ticker}")
async def get_icebergs(ticker: str, start_time: str, end_time: str):
    """Get detected iceberg orders for a specific time range."""
    # Parse times
    try:
        start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "Invalid timestamp format. Use ISO 8601.")
        
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")
    
    # Ensure data is loaded
    l2_manager.load_data(ticker, start_date, end_date)
    
    # Run detection
    icebergs = l2_manager.detect_icebergs(ticker, start_dt, end_dt)
    
    return icebergs


# ============ Data Loader Endpoints ============

class DownloadRequest(BaseModel):
    ticker: str
    data_schema: str = "mbp-10"
    start_date: str
    end_date: str
    dataset: str = "XNAS.ITCH"
    convert_to_parquet: bool = True


class CostEstimateRequest(BaseModel):
    ticker: str
    data_schema: str = "mbp-10"
    start_date: str
    end_date: str
    dataset: str = "XNAS.ITCH"


class DeleteDataRequest(BaseModel):
    ticker: str
    data_schema: str
    start_date: str
    end_date: str


class DataSettingsRequest(BaseModel):
    ohlcv_data_dirs: Optional[List[str]] = None
    l2_data_dirs: Optional[List[str]] = None


class DatabentoApiKeyRequest(BaseModel):
    api_key: str


@app.get("/api/data-loader/catalog")
async def get_data_catalog(
    refresh: bool = False,
    ticker: Optional[str] = None,
    schema: Optional[str] = None,
    file_format: Optional[str] = None,
    source: Optional[str] = None,
    managed: Optional[bool] = None,
):
    """List unified data catalog entries with optional filters."""
    return databento_svc.list_catalog(
        refresh=refresh,
        ticker=ticker,
        schema=schema,
        file_format=file_format,
        source=source,
        managed=managed,
    )


@app.get("/api/data-loader/catalog/{ticker}")
async def get_ticker_catalog(ticker: str):
    """List catalog data for a specific ticker."""
    return databento_svc.list_catalog(ticker=ticker.upper())


@app.get("/api/data-loader/settings")
async def get_data_loader_settings():
    """Read centralized data manager settings."""
    return databento_svc.get_settings()


@app.put("/api/data-loader/settings")
async def update_data_loader_settings(request: DataSettingsRequest):
    """Update OHLCV/L2 data roots used by catalog discovery."""
    global data_loader, l2_manager
    try:
        settings = databento_svc.update_data_dirs(
            ohlcv_data_dirs=request.ohlcv_data_dirs,
            l2_data_dirs=request.l2_data_dirs,
        )
        # Recreate loaders so run execution + L2 charts use the same updated roots.
        data_loader = DataLoader()
        l2_manager = L2DataManager()
        l2_features.manager = l2_manager
        reset_discovery()
        return settings
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@app.put("/api/data-loader/api-key")
async def set_databento_api_key(request: DatabentoApiKeyRequest):
    """Set Databento API key for this system (persisted in settings)."""
    try:
        settings = databento_svc.set_api_key(request.api_key)
        return {"status": "ok", **settings}
    except RuntimeError as e:
        raise HTTPException(500, str(e))


@app.get("/api/data-loader/schemas")
async def get_supported_schemas():
    """List supported Databento schemas."""
    return databento_svc.get_schemas()


@app.post("/api/data-loader/cost-estimate")
async def get_cost_estimate(request: CostEstimateRequest):
    """Get Databento cost estimate before downloading."""
    try:
        return databento_svc.get_cost_estimate(
            ticker=request.ticker.upper(),
            schema=request.data_schema,
            start=request.start_date,
            end=request.end_date,
            dataset=request.dataset,
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        raise HTTPException(400, f"Cost estimate failed: {e}")


@app.post("/api/data-loader/download")
async def start_download(request: DownloadRequest):
    """Start a data download from Databento (runs in background)."""
    ticker = request.ticker.upper()

    try:
        coverage = databento_svc.get_range_coverage(
            ticker=ticker,
            schema=request.data_schema,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Invalid date range: {e}")

    if coverage.get("fully_covered"):
        return {"status": "already_exists", "coverage": coverage}

    async def _broadcast(msg):
        await broadcast(msg)

    # Run download in background task
    async def _do_download():
        try:
            entry = await databento_svc.download(
                ticker=ticker,
                schema=request.data_schema,
                start_date=request.start_date,
                end_date=request.end_date,
                dataset=request.dataset,
                convert_to_parquet=request.convert_to_parquet,
                broadcast_fn=_broadcast,
            )
            logger.info(f"Download complete: {ticker} {request.data_schema} -> {entry.status}")
        except Exception as e:
            logger.error(f"Download failed: {e}")

    asyncio.create_task(_do_download())
    return {
        "status": "started",
        "ticker": ticker,
        "schema": request.data_schema,
        "days_total": coverage.get("total_days", 0),
        "days_to_download": len(coverage.get("missing_days", [])),
        "days_already_covered": len(coverage.get("covered_days", [])),
    }


@app.get("/api/data-loader/downloads/active")
async def get_active_downloads():
    """Get list of currently downloading jobs."""
    return databento_svc.get_active_downloads()


@app.delete("/api/data-loader/entry")
async def delete_data_entry(request: DeleteDataRequest):
    """Delete a downloaded data entry and its files."""
    existing = databento_svc.catalog.find(
        request.ticker.upper(), request.data_schema, request.start_date, request.end_date
    )
    if not existing:
        raise HTTPException(404, "Entry not found")
    if not bool(existing.get("managed", True)):
        raise HTTPException(
            403,
            "Refusing to delete unmanaged/external entry. Remove file manually if needed.",
        )
    success = databento_svc.delete_entry(
        request.ticker.upper(), request.data_schema, request.start_date, request.end_date
    )
    if not success:
        raise HTTPException(500, "Delete failed")
    return {"status": "deleted"}


@app.post("/api/data-loader/scan")
async def scan_existing_data():
    """Scan data directories and register untracked files."""
    from dataclasses import asdict
    entries = databento_svc.scan_existing_files()
    return {"scanned": len(entries), "entries": [asdict(e) for e in entries]}


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
