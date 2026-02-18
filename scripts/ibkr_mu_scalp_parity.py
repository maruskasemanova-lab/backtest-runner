#!/usr/bin/env python3
"""
Build MU short-scalp fixtures from IBKR transactions and compare them to backtest output.

This script intentionally works without running runner HTTP API; it invokes the same
start/run flow through local service functions.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import api_server
from src.models.run_requests import StartRunRequest


@dataclass
class IbkrFill:
    row_index: int
    trade_date: date
    trade_timestamp_utc: Optional[datetime]
    transaction_type: str
    symbol: str
    quantity: float
    price: float
    gross_amount: float
    commission: float
    net_amount: float
    open_close_indicator: str = ""


@dataclass
class ShortRoundTrip:
    trade_id: int
    entry_date: date
    exit_date: date
    entry_time_utc: Optional[datetime]
    exit_time_utc: Optional[datetime]
    quantity: float
    entry_price: float
    exit_price: float
    net_pnl: float
    holding_days: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat(),
            "entry_time_utc": self.entry_time_utc.isoformat() if self.entry_time_utc else None,
            "exit_time_utc": self.exit_time_utc.isoformat() if self.exit_time_utc else None,
            "quantity": round(self.quantity, 6),
            "entry_price": round(self.entry_price, 6),
            "exit_price": round(self.exit_price, 6),
            "net_pnl": round(self.net_pnl, 6),
            "holding_days": int(self.holding_days),
        }


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_date(value: str) -> date:
    return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()


def _parse_flex_date(value: str) -> date:
    return datetime.strptime(str(value).strip(), "%Y%m%d").date()


def _parse_flex_datetime_to_utc(value: str, *, tz_name: str) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        local_tz = timezone.utc

    try:
        local_dt = datetime.strptime(raw, "%Y%m%d;%H%M%S").replace(tzinfo=local_tz)
    except ValueError:
        return None
    return local_dt.astimezone(timezone.utc)


def _parse_any_iso_datetime_to_utc(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_forced_replay_types() -> Tuple[Any, Any]:
    """
    Load DayTradingManager + Position from sibling strategy repo.
    Avoid importing local backtest `src` package by using workspace root package path.
    """
    workspace_root = ROOT_DIR.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from market_regime_detection.src.day_trading_manager import DayTradingManager  # type: ignore
    from market_regime_detection.src.strategies.base_strategy import Position  # type: ignore

    return DayTradingManager, Position


def load_ibkr_fills_from_csv(
    *,
    csv_path: Path,
    ticker: str,
    date_from: date,
    date_to: date,
) -> List[IbkrFill]:
    fills: List[IbkrFill] = []
    with csv_path.open("r", newline="") as handle:
        reader = csv.reader(handle)
        for row_index, row in enumerate(reader):
            if len(row) < 13:
                continue
            if row[0] != "Transaction History" or row[1] != "Data":
                continue

            symbol = str(row[6]).strip().upper()
            if symbol != ticker:
                continue

            transaction_type = str(row[5]).strip()
            if transaction_type not in {"Buy", "Sell"}:
                continue

            trade_date = _parse_date(row[2])
            if trade_date < date_from or trade_date > date_to:
                continue

            fills.append(
                IbkrFill(
                    row_index=row_index,
                    trade_date=trade_date,
                    trade_timestamp_utc=None,
                    transaction_type=transaction_type,
                    symbol=symbol,
                    quantity=_safe_float(row[7]),
                    price=_safe_float(row[8]),
                    gross_amount=_safe_float(row[10]),
                    commission=_safe_float(row[11]),
                    net_amount=_safe_float(row[12]),
                    open_close_indicator="",
                )
            )
    return fills


def load_ibkr_fills_from_xml(
    *,
    xml_path: Path,
    ticker: str,
    date_from: date,
    date_to: date,
    ibkr_timezone: str,
) -> List[IbkrFill]:
    fills: List[IbkrFill] = []
    root = ET.parse(xml_path).getroot()
    for row_index, trade in enumerate(root.findall(".//Trade")):
        symbol = str(trade.attrib.get("symbol", "")).strip().upper()
        if symbol != ticker:
            continue

        trade_date_raw = str(trade.attrib.get("tradeDate", "")).strip()
        if not trade_date_raw:
            continue
        trade_date = _parse_flex_date(trade_date_raw)
        if trade_date < date_from or trade_date > date_to:
            continue

        buy_sell = str(trade.attrib.get("buySell", "")).strip().upper()
        if buy_sell == "BUY":
            transaction_type = "Buy"
        elif buy_sell == "SELL":
            transaction_type = "Sell"
        else:
            continue

        fills.append(
            IbkrFill(
                row_index=row_index,
                trade_date=trade_date,
                trade_timestamp_utc=_parse_flex_datetime_to_utc(
                    trade.attrib.get("dateTime", ""),
                    tz_name=ibkr_timezone,
                ),
                transaction_type=transaction_type,
                symbol=symbol,
                quantity=_safe_float(trade.attrib.get("quantity")),
                price=_safe_float(trade.attrib.get("tradePrice")),
                gross_amount=_safe_float(trade.attrib.get("tradeMoney")),
                commission=_safe_float(trade.attrib.get("ibCommission")),
                net_amount=_safe_float(trade.attrib.get("netCash")),
                open_close_indicator=str(trade.attrib.get("openCloseIndicator", "")).strip().upper(),
            )
        )
    return fills


def load_ibkr_fills(
    *,
    source_path: Path,
    ticker: str,
    date_from: date,
    date_to: date,
    source_format: str,
    ibkr_timezone: str,
) -> List[IbkrFill]:
    normalized = str(source_format).strip().lower()
    if normalized == "xml":
        return load_ibkr_fills_from_xml(
            xml_path=source_path,
            ticker=ticker,
            date_from=date_from,
            date_to=date_to,
            ibkr_timezone=ibkr_timezone,
        )

    return load_ibkr_fills_from_csv(
        csv_path=source_path,
        ticker=ticker,
        date_from=date_from,
        date_to=date_to,
    )


def _is_short_open_fill(fill: IbkrFill) -> bool:
    if fill.transaction_type != "Sell" or fill.quantity >= 0:
        return False
    indicator = str(fill.open_close_indicator or "").strip().upper()
    if indicator == "C":
        return False
    return True


def _is_short_close_fill(fill: IbkrFill) -> bool:
    if fill.transaction_type != "Buy" or fill.quantity <= 0:
        return False
    indicator = str(fill.open_close_indicator or "").strip().upper()
    if indicator == "O":
        return False
    return True


def match_short_round_trips(
    fills: Iterable[IbkrFill],
) -> Tuple[List[ShortRoundTrip], float, float]:
    ordered = sorted(
        fills,
        key=lambda item: (
            item.trade_timestamp_utc
            if item.trade_timestamp_utc is not None
            else datetime.combine(item.trade_date, datetime.min.time(), tzinfo=timezone.utc),
            item.row_index,
        ),
    )
    open_short_lots: Deque[Dict[str, Any]] = deque()
    matched: List[ShortRoundTrip] = []
    unmatched_buy_quantity = 0.0
    trade_id = 0

    for fill in ordered:
        if _is_short_open_fill(fill):
            open_short_lots.append(
                {
                    "entry_date": fill.trade_date,
                    "entry_time_utc": fill.trade_timestamp_utc,
                    "qty_remaining": abs(fill.quantity),
                    "entry_price": fill.price,
                    "entry_net_remaining": fill.net_amount,
                }
            )
            continue

        if not _is_short_close_fill(fill):
            continue

        buy_qty_remaining = fill.quantity
        buy_unit_net = fill.net_amount / fill.quantity if fill.quantity else 0.0

        while buy_qty_remaining > 1e-9 and open_short_lots:
            lot = open_short_lots[0]
            lot_qty = float(lot["qty_remaining"])
            if lot_qty <= 1e-9:
                open_short_lots.popleft()
                continue

            take_qty = min(buy_qty_remaining, lot_qty)
            sell_unit_net = float(lot["entry_net_remaining"]) / lot_qty
            net_pnl = (sell_unit_net * take_qty) + (buy_unit_net * take_qty)
            entry_date = lot["entry_date"]
            if isinstance(entry_date, date):
                parsed_entry_date = entry_date
            else:
                parsed_entry_date = _parse_date(str(entry_date))

            trade_id += 1
            matched.append(
                ShortRoundTrip(
                    trade_id=trade_id,
                    entry_date=parsed_entry_date,
                    exit_date=fill.trade_date,
                    entry_time_utc=lot.get("entry_time_utc"),
                    exit_time_utc=fill.trade_timestamp_utc,
                    quantity=take_qty,
                    entry_price=float(lot["entry_price"]),
                    exit_price=fill.price,
                    net_pnl=net_pnl,
                    holding_days=(fill.trade_date - parsed_entry_date).days,
                )
            )

            buy_qty_remaining -= take_qty
            lot["qty_remaining"] = lot_qty - take_qty
            lot["entry_net_remaining"] = float(lot["entry_net_remaining"]) - (sell_unit_net * take_qty)
            if float(lot["qty_remaining"]) <= 1e-9:
                open_short_lots.popleft()

        if buy_qty_remaining > 1e-9:
            unmatched_buy_quantity += buy_qty_remaining

    open_short_qty_remaining = sum(float(lot.get("qty_remaining", 0.0)) for lot in open_short_lots)
    return matched, open_short_qty_remaining, unmatched_buy_quantity


def build_daily_summary(round_trips: Iterable[ShortRoundTrip]) -> Dict[str, Dict[str, float]]:
    summary: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"trade_count": 0.0, "net_pnl": 0.0, "quantity": 0.0}
    )
    for trade in round_trips:
        day = trade.exit_date.isoformat()
        bucket = summary[day]
        bucket["trade_count"] += 1.0
        bucket["net_pnl"] += trade.net_pnl
        bucket["quantity"] += trade.quantity

    ordered_days = sorted(summary.keys())
    return {
        day: {
            "trade_count": int(summary[day]["trade_count"]),
            "net_pnl": round(summary[day]["net_pnl"], 6),
            "quantity": round(summary[day]["quantity"], 6),
        }
        for day in ordered_days
    }


def _round_trip_gross_pnl(round_trip: Dict[str, Any]) -> float:
    qty = _safe_float(round_trip.get("quantity"))
    entry = _safe_float(round_trip.get("entry_price"))
    exit_px = _safe_float(round_trip.get("exit_price"))
    # Round-trip objects represent short trades (sell then buy).
    return (entry - exit_px) * qty


def forced_replay_short_round_trips_with_engine(
    *,
    ticker: str,
    short_round_trips: Iterable[Dict[str, Any]],
    same_day_only: bool = True,
) -> Dict[str, Any]:
    """
    Replay provided short round-trips directly through engine trade accounting.

    This bypasses signal/strategy selection logic and uses engine cost + PnL math only.
    """
    DayTradingManager, Position = _load_forced_replay_types()
    dtm = DayTradingManager()
    run_id = "ibkr-forced-replay"

    per_day: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "ibkr_trade_count": 0.0,
            "ibkr_net_pnl_dollars": 0.0,
            "ibkr_gross_pnl_dollars": 0.0,
            "engine_trade_count": 0.0,
            "engine_net_pnl_dollars": 0.0,
            "engine_total_costs_dollars": 0.0,
            "engine_gross_pnl_dollars": 0.0,
        }
    )

    replayed = 0
    trades_with_execution_timestamps = 0
    trades_without_execution_timestamps = 0
    for trade in short_round_trips:
        holding_days = int(_safe_float(trade.get("holding_days")))
        if same_day_only and holding_days != 0:
            continue

        entry_date = str(trade.get("entry_date", "")).strip()
        exit_date = str(trade.get("exit_date", "")).strip()
        if not entry_date or not exit_date:
            continue

        qty = _safe_float(trade.get("quantity"))
        entry_price = _safe_float(trade.get("entry_price"))
        exit_price = _safe_float(trade.get("exit_price"))
        if qty <= 0 or entry_price <= 0 or exit_price <= 0:
            continue

        session = dtm.get_or_create_session(run_id=run_id, ticker=ticker, date=entry_date)

        entry_time = _parse_any_iso_datetime_to_utc(trade.get("entry_time_utc"))
        exit_time = _parse_any_iso_datetime_to_utc(trade.get("exit_time_utc"))
        if entry_time and exit_time:
            trades_with_execution_timestamps += 1
        else:
            trades_without_execution_timestamps += 1
            # Date-only fallback keeps deterministic replay for CSV-based fixtures.
            entry_time = entry_time or datetime.fromisoformat(f"{entry_date}T15:30:00+00:00")
            exit_time = exit_time or datetime.fromisoformat(f"{exit_date}T15:31:00+00:00")
            if exit_time <= entry_time:
                exit_time = entry_time + timedelta(seconds=1)

        position = Position(
            strategy_name="manual_replay",
            entry_price=entry_price,
            entry_time=entry_time,
            side="short",
            size=qty,
        )
        engine_trade = dtm._build_trade_record(
            session=session,
            pos=position,
            exit_price=exit_price,
            exit_time=exit_time,
            reason="manual_replay",
            shares=qty,
            bar_volume=None,
        )

        ibkr_net = _safe_float(trade.get("net_pnl"))
        ibkr_gross = _round_trip_gross_pnl(trade)

        bucket = per_day[exit_date]
        bucket["ibkr_trade_count"] += 1.0
        bucket["ibkr_net_pnl_dollars"] += ibkr_net
        bucket["ibkr_gross_pnl_dollars"] += ibkr_gross
        bucket["engine_trade_count"] += 1.0
        bucket["engine_net_pnl_dollars"] += _safe_float(getattr(engine_trade, "pnl_dollars", 0.0))
        bucket["engine_total_costs_dollars"] += _safe_float(getattr(engine_trade, "total_costs", 0.0))
        bucket["engine_gross_pnl_dollars"] += _safe_float(_safe_float(getattr(engine_trade, "pnl_dollars", 0.0)) + _safe_float(getattr(engine_trade, "total_costs", 0.0)))
        replayed += 1

    ordered_days = sorted(per_day.keys())
    per_day_rows: List[Dict[str, Any]] = []
    totals = {
        "ibkr_trade_count": 0,
        "ibkr_net_pnl_dollars": 0.0,
        "ibkr_gross_pnl_dollars": 0.0,
        "engine_trade_count": 0,
        "engine_net_pnl_dollars": 0.0,
        "engine_total_costs_dollars": 0.0,
        "engine_gross_pnl_dollars": 0.0,
    }

    for day in ordered_days:
        row = per_day[day]
        ibkr_count = int(row["ibkr_trade_count"])
        engine_count = int(row["engine_trade_count"])
        ibkr_net = row["ibkr_net_pnl_dollars"]
        engine_net = row["engine_net_pnl_dollars"]
        ibkr_gross = row["ibkr_gross_pnl_dollars"]
        engine_gross = row["engine_gross_pnl_dollars"]
        engine_costs = row["engine_total_costs_dollars"]
        ibkr_costs = ibkr_gross - ibkr_net

        per_day_rows.append(
            {
                "date": day,
                "ibkr_trade_count": ibkr_count,
                "engine_trade_count": engine_count,
                "trade_count_delta": engine_count - ibkr_count,
                "ibkr_net_pnl_dollars": round(ibkr_net, 6),
                "engine_net_pnl_dollars": round(engine_net, 6),
                "net_pnl_delta_dollars": round(engine_net - ibkr_net, 6),
                "ibkr_implied_total_costs_dollars": round(ibkr_costs, 6),
                "engine_total_costs_dollars": round(engine_costs, 6),
                "cost_delta_dollars": round(engine_costs - ibkr_costs, 6),
                "ibkr_gross_pnl_dollars": round(ibkr_gross, 6),
                "engine_gross_pnl_dollars": round(engine_gross, 6),
                "gross_pnl_delta_dollars": round(engine_gross - ibkr_gross, 6),
            }
        )

        totals["ibkr_trade_count"] += ibkr_count
        totals["ibkr_net_pnl_dollars"] += ibkr_net
        totals["ibkr_gross_pnl_dollars"] += ibkr_gross
        totals["engine_trade_count"] += engine_count
        totals["engine_net_pnl_dollars"] += engine_net
        totals["engine_total_costs_dollars"] += engine_costs
        totals["engine_gross_pnl_dollars"] += engine_gross

    total_ibkr_costs = totals["ibkr_gross_pnl_dollars"] - totals["ibkr_net_pnl_dollars"]
    timestamp_resolution = "execution_timestamp" if trades_with_execution_timestamps > 0 else "date_only"
    return {
        "timestamp_resolution": timestamp_resolution,
        "trades_with_execution_timestamps": int(trades_with_execution_timestamps),
        "trades_without_execution_timestamps": int(trades_without_execution_timestamps),
        "same_day_only": bool(same_day_only),
        "replayed_trades": int(replayed),
        "ibkr_trade_count": int(totals["ibkr_trade_count"]),
        "engine_trade_count": int(totals["engine_trade_count"]),
        "trade_count_delta": int(totals["engine_trade_count"] - totals["ibkr_trade_count"]),
        "ibkr_net_pnl_dollars": round(totals["ibkr_net_pnl_dollars"], 6),
        "engine_net_pnl_dollars": round(totals["engine_net_pnl_dollars"], 6),
        "net_pnl_delta_dollars": round(totals["engine_net_pnl_dollars"] - totals["ibkr_net_pnl_dollars"], 6),
        "ibkr_implied_total_costs_dollars": round(total_ibkr_costs, 6),
        "engine_total_costs_dollars": round(totals["engine_total_costs_dollars"], 6),
        "cost_delta_dollars": round(totals["engine_total_costs_dollars"] - total_ibkr_costs, 6),
        "ibkr_gross_pnl_dollars": round(totals["ibkr_gross_pnl_dollars"], 6),
        "engine_gross_pnl_dollars": round(totals["engine_gross_pnl_dollars"], 6),
        "gross_pnl_delta_dollars": round(totals["engine_gross_pnl_dollars"] - totals["ibkr_gross_pnl_dollars"], 6),
        "per_day": per_day_rows,
    }


def _extract_session_summary(summary_payload: Any) -> Dict[str, Any]:
    if isinstance(summary_payload, dict):
        nested = summary_payload.get("session_summary")
        if isinstance(nested, dict):
            return nested
        return summary_payload
    return {}


async def run_backtest_for_day(
    *,
    ticker: str,
    trade_date: str,
    strategy_api_url: str,
    include_extended_hours: Optional[bool],
) -> Dict[str, Any]:
    run_id = f"ibkr-parity-{ticker}-{trade_date}-{uuid.uuid4().hex[:8]}"
    run_key: Optional[str] = None
    parts: Tuple[str, str, str] = ("", "", "")

    try:
        payload: Dict[str, Any] = {
            "run_id": run_id,
            "ticker": ticker,
            "date": trade_date,
            "strategy_api_url": strategy_api_url,
        }
        if include_extended_hours is not None:
            payload["include_extended_hours"] = bool(include_extended_hours)

        start_response = await api_server.start_run(StartRunRequest(**payload))
        run_key = str(start_response.get("run_key", "")).strip()
        key_parts = run_key.split(":", 2)
        if len(key_parts) != 3:
            raise RuntimeError(f"Invalid run_key from start_run: {run_key}")
        parts = (key_parts[0], key_parts[1], key_parts[2])

        runner = api_server.active_runners.get(run_key)
        if runner is None:
            raise RuntimeError(f"Runner not found in registry for run_key={run_key}")

        await runner.run_all(speed_ms="max")

        summary_payload = runner.get_summary()
        session_summary = _extract_session_summary(summary_payload)
        trades_raw = session_summary.get("trades", [])
        trades = trades_raw if isinstance(trades_raw, list) else []
        short_trades = [trade for trade in trades if str(trade.get("side", "")).strip().lower() == "short"]

        short_trade_count = len(short_trades)
        short_trade_pnl = sum(_safe_float(trade.get("pnl_dollars")) for trade in short_trades)

        return {
            "date": trade_date,
            "backtest_total_trades": int(_safe_float(session_summary.get("total_trades"))),
            "backtest_total_pnl_dollars": round(_safe_float(session_summary.get("total_pnl_dollars")), 6),
            "backtest_short_trades": short_trade_count,
            "backtest_short_pnl_dollars": round(short_trade_pnl, 6),
            "error": None,
        }
    except Exception as exc:
        return {
            "date": trade_date,
            "backtest_total_trades": 0,
            "backtest_total_pnl_dollars": 0.0,
            "backtest_short_trades": 0,
            "backtest_short_pnl_dollars": 0.0,
            "error": str(exc),
        }
    finally:
        if run_key and all(parts):
            try:
                await api_server.delete_run(parts[0], parts[1], parts[2])
            except Exception:
                pass


async def run_backtest_for_days(
    *,
    ticker: str,
    days: Iterable[str],
    strategy_api_url: str,
    include_extended_hours: Optional[bool],
) -> Dict[str, Dict[str, Any]]:
    results: Dict[str, Dict[str, Any]] = {}
    for day in sorted(set(days)):
        results[day] = await run_backtest_for_day(
            ticker=ticker,
            trade_date=day,
            strategy_api_url=strategy_api_url,
            include_extended_hours=include_extended_hours,
        )
    return results


def compare_scalp_daily_to_backtest(
    *,
    ibkr_scalp_daily: Dict[str, Dict[str, float]],
    backtest_daily: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    per_day: List[Dict[str, Any]] = []
    ibkr_total_pnl = 0.0
    ibkr_total_trades = 0
    backtest_total_pnl = 0.0
    backtest_total_trades = 0
    compared_days = 0
    failed_days = 0

    for day in sorted(ibkr_scalp_daily.keys()):
        ibkr_day = ibkr_scalp_daily[day]
        backtest_day = backtest_daily.get(day, {})
        error = str(backtest_day.get("error") or "").strip() or None

        ibkr_count = int(ibkr_day.get("trade_count", 0))
        ibkr_pnl = _safe_float(ibkr_day.get("net_pnl"))
        backtest_count = int(_safe_float(backtest_day.get("backtest_short_trades")))
        backtest_pnl = _safe_float(backtest_day.get("backtest_short_pnl_dollars"))

        if error:
            failed_days += 1
        else:
            compared_days += 1
            backtest_total_pnl += backtest_pnl
            backtest_total_trades += backtest_count

        ibkr_total_pnl += ibkr_pnl
        ibkr_total_trades += ibkr_count

        per_day.append(
            {
                "date": day,
                "ibkr_short_scalp_trades": ibkr_count,
                "ibkr_short_scalp_net_pnl_dollars": round(ibkr_pnl, 6),
                "backtest_short_trades": backtest_count,
                "backtest_short_pnl_dollars": round(backtest_pnl, 6),
                "trade_count_delta": backtest_count - ibkr_count,
                "pnl_delta_dollars": round(backtest_pnl - ibkr_pnl, 6),
                "error": error,
            }
        )

    return {
        "compared_days": compared_days,
        "failed_days": failed_days,
        "ibkr_total_short_scalp_trades": ibkr_total_trades,
        "ibkr_total_short_scalp_net_pnl_dollars": round(ibkr_total_pnl, 6),
        "backtest_total_short_trades": backtest_total_trades,
        "backtest_total_short_pnl_dollars": round(backtest_total_pnl, 6),
        "total_trade_count_delta": backtest_total_trades - ibkr_total_trades,
        "total_pnl_delta_dollars": round(backtest_total_pnl - ibkr_total_pnl, 6),
        "per_day": per_day,
    }


def _resolve_include_extended_hours(args: argparse.Namespace) -> Optional[bool]:
    if args.include_extended_hours and args.regular_hours_only:
        raise SystemExit("Cannot set both --include-extended-hours and --regular-hours-only.")
    if args.include_extended_hours:
        return True
    if args.regular_hours_only:
        return False
    return None


def _default_fixture_path(ticker: str, date_from: str, date_to: str) -> Path:
    safe_ticker = str(ticker).strip().upper()
    return Path(f"tests/fixtures/ibkr_{safe_ticker}_short_scalps_{date_from}_{date_to}.json")


def _default_report_path(ticker: str) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_ticker = str(ticker).strip().upper()
    return Path(f"reports/ibkr_{safe_ticker}_short_scalp_parity_{ts}.json")


def _resolve_source_format(source_path: Path, source_format_arg: str) -> str:
    normalized = str(source_format_arg).strip().lower()
    if normalized in {"csv", "xml"}:
        return normalized
    suffix = source_path.suffix.lower()
    if suffix == ".xml":
        return "xml"
    return "csv"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create MU short-scalp fixtures from IBKR CSV/XML and compare to local backtest output."
    )
    parser.add_argument(
        "--ibkr-csv",
        default="/Users/hotovo/.gemini/antigravity/scratch/ibkr-realtime-trader/U23351242.TRANSACTIONS.1Y.csv",
        help="Path to IBKR transactions source (CSV export or Flex XML).",
    )
    parser.add_argument(
        "--ibkr-format",
        choices=["auto", "csv", "xml"],
        default="auto",
        help="Input source format (auto detects by file extension).",
    )
    parser.add_argument(
        "--ibkr-timezone",
        default="America/New_York",
        help="Timezone used to interpret Flex XML dateTime values before converting to UTC.",
    )
    parser.add_argument("--ticker", default="MU", help="Ticker symbol to analyze.")
    parser.add_argument("--date-from", default="2025-10-01", help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--date-to", default="2026-02-13", help="Inclusive end date (YYYY-MM-DD).")
    parser.add_argument(
        "--strategy-api-url",
        default="http://127.0.0.1:8001",
        help="Strategy API URL used by local backtest start flow.",
    )
    parser.add_argument(
        "--fixture-out",
        default=None,
        help="Output path for generated fixture JSON.",
    )
    parser.add_argument(
        "--report-out",
        default=None,
        help="Output path for parity report JSON.",
    )
    parser.add_argument(
        "--skip-backtest",
        action="store_true",
        help="Only generate fixtures; do not run parity backtest comparison.",
    )
    parser.add_argument(
        "--include-extended-hours",
        action="store_true",
        help="Force include_extended_hours=true in backtest runs.",
    )
    parser.add_argument(
        "--regular-hours-only",
        action="store_true",
        help="Force include_extended_hours=false in backtest runs.",
    )
    args = parser.parse_args()

    ticker = str(args.ticker).strip().upper()
    source_path = Path(args.ibkr_csv)
    if not source_path.exists():
        raise SystemExit(f"IBKR source not found: {source_path}")
    source_format = _resolve_source_format(source_path, args.ibkr_format)

    date_from = _parse_date(args.date_from)
    date_to = _parse_date(args.date_to)
    if date_from > date_to:
        raise SystemExit("date-from must be <= date-to")

    include_extended_hours = _resolve_include_extended_hours(args)
    fixture_out = Path(args.fixture_out) if args.fixture_out else _default_fixture_path(ticker, args.date_from, args.date_to)
    report_out = Path(args.report_out) if args.report_out else _default_report_path(ticker)

    fills = load_ibkr_fills(
        source_path=source_path,
        ticker=ticker,
        date_from=date_from,
        date_to=date_to,
        source_format=source_format,
        ibkr_timezone=str(args.ibkr_timezone),
    )
    fill_days = sorted({fill.trade_date.isoformat() for fill in fills})
    fills_first_date = fill_days[0] if fill_days else None
    fills_last_date = fill_days[-1] if fill_days else None

    short_round_trips, open_short_qty_remaining, unmatched_buy_quantity = match_short_round_trips(fills)
    same_day_scalps = [trade for trade in short_round_trips if trade.holding_days == 0]

    short_round_trip_daily = build_daily_summary(short_round_trips)
    same_day_scalp_daily = build_daily_summary(same_day_scalps)

    fixture_payload: Dict[str, Any] = {
        "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source_path": str(source_path),
        "source_format": source_format,
        "source_csv": str(source_path),
        "ticker": ticker,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "fills_in_range": len(fills),
        "fills_trade_days": len(fill_days),
        "fills_first_date": fills_first_date,
        "fills_last_date": fills_last_date,
        "matched_short_round_trips": len(short_round_trips),
        "same_day_short_scalps": len(same_day_scalps),
        "open_short_qty_remaining": round(open_short_qty_remaining, 6),
        "unmatched_buy_qty": round(unmatched_buy_quantity, 6),
        "daily_short_round_trip_summary": short_round_trip_daily,
        "daily_same_day_short_scalp_summary": same_day_scalp_daily,
        "short_round_trips": [trade.to_dict() for trade in short_round_trips],
    }

    fixture_out.parent.mkdir(parents=True, exist_ok=True)
    fixture_out.write_text(json.dumps(fixture_payload, indent=2))

    report_payload: Dict[str, Any] = {
        "generated_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "fixture_path": str(fixture_out),
        "ticker": ticker,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "source_path": str(source_path),
        "source_format": source_format,
        "ibkr_fixture_summary": {
            "fills_in_range": len(fills),
            "fills_trade_days": len(fill_days),
            "fills_first_date": fills_first_date,
            "fills_last_date": fills_last_date,
            "matched_short_round_trips": len(short_round_trips),
            "same_day_short_scalps": len(same_day_scalps),
            "days_with_same_day_short_scalps": len(same_day_scalp_daily),
            "open_short_qty_remaining": round(open_short_qty_remaining, 6),
            "unmatched_buy_qty": round(unmatched_buy_quantity, 6),
        },
        "parity": None,
        "forced_replay": None,
    }

    if not args.skip_backtest and same_day_scalp_daily:
        backtest_daily = asyncio.run(
            run_backtest_for_days(
                ticker=ticker,
                days=same_day_scalp_daily.keys(),
                strategy_api_url=str(args.strategy_api_url),
                include_extended_hours=include_extended_hours,
            )
        )
        parity = compare_scalp_daily_to_backtest(
            ibkr_scalp_daily=same_day_scalp_daily,
            backtest_daily=backtest_daily,
        )
        report_payload["parity"] = {
            "mode": "same_day_short_scalps_vs_backtest_short_trades",
            "strategy_api_url": str(args.strategy_api_url),
            "include_extended_hours": include_extended_hours,
            "backtest_daily": backtest_daily,
            "comparison": parity,
        }

    # Always compute forced replay parity because it does not depend on strategy selection.
    report_payload["forced_replay"] = forced_replay_short_round_trips_with_engine(
        ticker=ticker,
        short_round_trips=fixture_payload.get("short_round_trips", []),
        same_day_only=True,
    )

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report_payload, indent=2))

    print(f"Fixture written: {fixture_out}")
    print(f"Report written:  {report_out}")
    if report_payload.get("parity"):
        comparison = report_payload["parity"]["comparison"]
        print("Parity summary:")
        print(
            f"  IBKR scalps: {comparison['ibkr_total_short_scalp_trades']} trades, "
            f"${comparison['ibkr_total_short_scalp_net_pnl_dollars']:.4f}"
        )
        print(
            f"  Backtest short: {comparison['backtest_total_short_trades']} trades, "
            f"${comparison['backtest_total_short_pnl_dollars']:.4f}"
        )
        print(
            f"  Delta: trades {comparison['total_trade_count_delta']:+d}, "
            f"PnL ${comparison['total_pnl_delta_dollars']:+.4f}"
        )
    forced = report_payload.get("forced_replay") or {}
    if forced:
        print("Forced replay summary (same trades through engine accounting):")
        print(
            f"  IBKR: {forced.get('ibkr_trade_count', 0)} trades, "
            f"${_safe_float(forced.get('ibkr_net_pnl_dollars')):.4f}"
        )
        print(
            f"  Engine: {forced.get('engine_trade_count', 0)} trades, "
            f"${_safe_float(forced.get('engine_net_pnl_dollars')):.4f}"
        )
        print(
            f"  Delta: trades {int(_safe_float(forced.get('trade_count_delta'))):+d}, "
            f"PnL ${_safe_float(forced.get('net_pnl_delta_dollars')):+.4f}, "
            f"cost delta ${_safe_float(forced.get('cost_delta_dollars')):+.4f}"
        )


if __name__ == "__main__":
    main()
