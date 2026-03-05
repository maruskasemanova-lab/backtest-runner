from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass
class MutableTickerConfigState:
    ticker: str
    aos_config: Dict[str, Any]
    positioning_config: Dict[str, Any]
    ticker_config: Dict[str, Any]
    positioning_ticker_config: Dict[str, Any]


def _ensure_tickers(config: Any) -> Dict[str, Any]:
    normalized = config if isinstance(config, dict) else {}
    tickers = normalized.get("tickers")
    if not isinstance(tickers, dict):
        normalized["tickers"] = {}
    return normalized


def load_mutable_ticker_config_state(
    *,
    ticker: str,
    load_aos_config: Callable[[], Dict[str, Any]],
    load_positioning_config: Callable[[], Dict[str, Any]],
) -> MutableTickerConfigState:
    ticker_upper = str(ticker or "").upper().strip()
    aos_config = _ensure_tickers(load_aos_config())
    positioning_config = _ensure_tickers(load_positioning_config())

    aos_ticker = aos_config["tickers"].get(ticker_upper, {})
    positioning_ticker = positioning_config["tickers"].get(ticker_upper, {})

    return MutableTickerConfigState(
        ticker=ticker_upper,
        aos_config=aos_config,
        positioning_config=positioning_config,
        ticker_config=deepcopy(aos_ticker) if isinstance(aos_ticker, dict) else {},
        positioning_ticker_config=(
            deepcopy(positioning_ticker) if isinstance(positioning_ticker, dict) else {}
        ),
    )


def save_ticker_aos_config(
    *,
    state: MutableTickerConfigState,
    save_aos_config: Callable[[Dict[str, Any]], bool],
) -> bool:
    aos_config = _ensure_tickers(state.aos_config)
    aos_config["tickers"][state.ticker] = (
        state.ticker_config if isinstance(state.ticker_config, dict) else {}
    )
    return bool(save_aos_config(aos_config))


def save_ticker_positioning_config(
    *,
    state: MutableTickerConfigState,
    save_positioning_config: Callable[[Dict[str, Any]], bool],
    allow_empty: bool = False,
) -> bool:
    positioning_config = _ensure_tickers(state.positioning_config)
    tickers = positioning_config["tickers"]
    positioning_ticker = (
        state.positioning_ticker_config
        if isinstance(state.positioning_ticker_config, dict)
        else {}
    )
    if positioning_ticker or allow_empty:
        tickers[state.ticker] = positioning_ticker
    else:
        tickers.pop(state.ticker, None)
    return bool(save_positioning_config(positioning_config))


def remove_ticker_positioning_config(state: MutableTickerConfigState) -> None:
    positioning_config = _ensure_tickers(state.positioning_config)
    positioning_config["tickers"].pop(state.ticker, None)
    state.positioning_ticker_config = {}
