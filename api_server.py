"""
Unified Backtest Runner API Server.
Orchestrates the look-ahead free data feeding and strategy evaluation.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
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
from available_data import get_discovery
from src.l2_data_manager import L2DataManager

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
active_runners: Dict[str, SessionRunner] = {}
connected_clients: List[WebSocket] = []
STRATEGY_OVERRIDES_PATH = Path(__file__).parent / "strategy_overrides.json"
AOS_CONFIG_PATH = Path(__file__).parent / "aos_optimization" / "aos_config.json"


def _load_strategy_overrides() -> Dict[str, Any]:
    if not STRATEGY_OVERRIDES_PATH.exists():
        return {}
    try:
        return json.loads(STRATEGY_OVERRIDES_PATH.read_text())
    except Exception:
        return {}


def _load_aos_config() -> Dict[str, Any]:
    """Load AOS optimization config from JSON file."""
    if not AOS_CONFIG_PATH.exists():
        return {"version": "1.0.0", "tickers": {}}
    try:
        return json.loads(AOS_CONFIG_PATH.read_text())
    except Exception:
        return {"version": "1.0.0", "tickers": {}}


def _save_aos_config(config: Dict[str, Any]) -> bool:
    """Save AOS optimization config to JSON file."""
    try:
        AOS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        AOS_CONFIG_PATH.write_text(json.dumps(config, indent=2))
        return True
    except Exception as e:
        logger.error(f"Failed to save AOS config: {e}")
        return False


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


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _extract_multilayer_payload(ticker_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ticker-specific multi-layer/candlestick settings from AOS config."""
    allowed_core = {"pattern_weight", "strategy_weight", "threshold", "require_pattern"}
    allowed_detector = {
        "body_doji_pct",
        "wick_ratio_hammer",
        "engulfing_min_body_pct",
        "volume_confirm_ratio",
        "vwap_proximity_pct",
    }

    raw: Dict[str, Any] = {}

    # Preferred schema keys in ticker config
    for key in ("multilayer", "multi_layer"):
        block = ticker_config.get(key)
        if isinstance(block, dict):
            raw.update(block)

    # Optional candlestick namespace
    candlestick = ticker_config.get("candlestick")
    if isinstance(candlestick, dict):
        nested_ml = candlestick.get("multilayer")
        if isinstance(nested_ml, dict):
            raw.update(nested_ml)
        detector = candlestick.get("detector")
        if isinstance(detector, dict):
            raw.update(detector)
        for key in allowed_core.union(allowed_detector):
            if key in candlestick:
                raw[key] = candlestick[key]

    # Backward-compatible flattened ticker-level keys
    for key in allowed_core.union(allowed_detector):
        if key in ticker_config and key not in raw:
            raw[key] = ticker_config[key]

    # Optional nested detector object under multilayer
    detector_block = raw.get("detector")
    if isinstance(detector_block, dict):
        for key in allowed_detector:
            if key in detector_block and key not in raw:
                raw[key] = detector_block[key]

    payload: Dict[str, Any] = {}
    for key in ("pattern_weight", "strategy_weight", "threshold"):
        if key not in raw:
            continue
        try:
            payload[key] = float(raw[key])
        except (TypeError, ValueError):
            continue

    if "require_pattern" in raw:
        payload["require_pattern"] = _coerce_bool(raw["require_pattern"], default=True)

    for key in allowed_detector:
        if key not in raw:
            continue
        try:
            payload[key] = float(raw[key])
        except (TypeError, ValueError):
            continue

    return payload


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


def _to_utc_datetime(value: Any) -> datetime:
    """Best-effort conversion to timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = pd.to_datetime(value).to_pydatetime()

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _epoch_minute_key(value: Any) -> int:
    dt_utc = _to_utc_datetime(value)
    return int(dt_utc.timestamp() // 60)


def _build_l2_feature_map(
    ticker: str,
    start_dt_utc: datetime,
    end_dt_utc: datetime,
) -> tuple[Dict[int, Dict[str, float]], Dict[str, Any]]:
    """
    Build minute-level L2 features keyed by UTC epoch-minute.

    Features:
    - l2_delta
    - l2_buy_volume / l2_sell_volume / l2_volume
    - l2_imbalance
    - l2_iceberg_buy_count / l2_iceberg_sell_count / l2_iceberg_bias
    """
    feature_map: Dict[int, Dict[str, float]] = {}
    stats = {
        "has_l2": False,
        "footprint_bars": 0,
        "icebergs": 0,
        "covered_minutes": 0,
    }

    start_date = start_dt_utc.strftime("%Y-%m-%d")
    end_date = end_dt_utc.strftime("%Y-%m-%d")
    loaded = l2_manager.load_data(ticker, start_date, end_date)
    if loaded is None:
        return feature_map, stats

    try:
        fp_bars = l2_manager.get_footprint_bars(
            ticker=ticker,
            start_time=start_dt_utc,
            end_time=end_dt_utc,
            timeframe="1min",
        )
    except Exception as e:
        logger.warning(f"L2 footprint aggregation failed for {ticker}: {e}")
        fp_bars = []

    stats["footprint_bars"] = len(fp_bars)
    for fp in fp_bars:
        try:
            minute_key = int(float(fp.get("time", 0)) // 60)
        except (TypeError, ValueError):
            continue

        levels = fp.get("levels") or {}
        buy_volume = 0.0
        sell_volume = 0.0
        if isinstance(levels, dict):
            for level in levels.values():
                if not isinstance(level, dict):
                    continue
                buy_volume += float(level.get("buy", 0) or 0)
                sell_volume += float(level.get("sell", 0) or 0)

        total_volume = float(fp.get("volume", 0) or 0)
        # Prefer explicit volume, fallback to summed footprint levels.
        if total_volume <= 0:
            total_volume = buy_volume + sell_volume

        denom = buy_volume + sell_volume
        imbalance = ((buy_volume - sell_volume) / denom) if denom > 0 else 0.0

        feature_map[minute_key] = {
            "l2_delta": float(fp.get("delta", 0) or 0),
            "l2_buy_volume": buy_volume,
            "l2_sell_volume": sell_volume,
            "l2_volume": total_volume,
            "l2_imbalance": imbalance,
            "l2_iceberg_buy_count": 0.0,
            "l2_iceberg_sell_count": 0.0,
            "l2_iceberg_bias": 0.0,
        }

    try:
        icebergs = l2_manager.detect_icebergs(
            ticker=ticker,
            start_time=start_dt_utc,
            end_time=end_dt_utc,
        )
    except Exception as e:
        logger.warning(f"L2 iceberg detection failed for {ticker}: {e}")
        icebergs = []

    stats["icebergs"] = len(icebergs)
    for ice in icebergs:
        ts = ice.get("time")
        if not ts:
            continue
        try:
            minute_key = _epoch_minute_key(ts)
        except Exception:
            continue

        bucket = feature_map.setdefault(
            minute_key,
            {
                "l2_delta": 0.0,
                "l2_buy_volume": 0.0,
                "l2_sell_volume": 0.0,
                "l2_volume": 0.0,
                "l2_imbalance": 0.0,
                "l2_iceberg_buy_count": 0.0,
                "l2_iceberg_sell_count": 0.0,
                "l2_iceberg_bias": 0.0,
            },
        )
        side = str(ice.get("side", "")).lower()
        if side == "buy":
            bucket["l2_iceberg_buy_count"] += 1.0
        elif side == "sell":
            bucket["l2_iceberg_sell_count"] += 1.0
        bucket["l2_iceberg_bias"] = (
            bucket["l2_iceberg_buy_count"] - bucket["l2_iceberg_sell_count"]
        )

    stats["covered_minutes"] = len(feature_map)
    # Consider L2 "available" only when at least one aligned minute exists.
    stats["has_l2"] = stats["covered_minutes"] > 0
    return feature_map, stats


def _attach_l2_features(
    bars: List[Dict[str, Any]],
    feature_map: Dict[int, Dict[str, float]],
    l2_only: bool = False,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Attach minute-aligned L2 features to bars and optionally keep only covered bars."""
    if not bars:
        return bars, {"bars_with_l2": 0, "bars_total": 0}

    enriched: List[Dict[str, Any]] = []
    bars_with_l2 = 0
    for bar in bars:
        minute_key = _epoch_minute_key(bar.get("timestamp"))
        feats = feature_map.get(minute_key)
        if feats:
            bars_with_l2 += 1
            bar = {**bar, **feats}
        if not l2_only or feats:
            enriched.append(bar)

    stats = {
        "bars_with_l2": bars_with_l2,
        "bars_total": len(bars),
        "bars_after_filter": len(enriched),
    }
    return enriched, stats


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
    discovery = get_discovery()
    data = discovery.to_dict()
    
    # Add L2 availability
    # This is a simple file check in data/l2 directory
    l2_tickers = []
    l2_dir = Path("data/l2")
    if l2_dir.exists():
        for pattern in ("*.mbn", "*.parquet"):
            for f in l2_dir.glob(pattern):
                # Filename format: TICKER_START_END.<ext>
                stem = f.stem
                parts = stem.split('_')
                if len(parts) < 3:
                    continue

                ticker = parts[0]
                start = parts[1]
                end = parts[2]
                l2_tickers.append(ticker)

                if ticker not in data["tickers"]:
                    data["tickers"].append(ticker)

                if ticker not in data["date_ranges"]:
                    data["date_ranges"][ticker] = {
                        "start": start,
                        "end": end,
                        "files": [f.name],
                    }
                    continue

                current = data["date_ranges"][ticker]
                if "files" not in current:
                    current["files"] = []
                current["files"].append(f.name)
                if start < current["start"]:
                    current["start"] = start
                if end > current["end"]:
                    current["end"] = end

    data["tickers"].sort()
    data["l2_tickers"] = list(set(l2_tickers))
    return data


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
    
    active_runners[run_key] = runner
    
    logger.info(f"Started run {run_key} with {len(bars)} bars")
    
    return {
        "success": True,
        "run_key": run_key,
        "ticker": ticker,
        "total_bars": len(bars),
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
    
    # Start in background
    runner.last_run_speed = raw_speed  # cache for resume info
    asyncio.create_task(runner.run_all(speed_ms=raw_speed))
    
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
