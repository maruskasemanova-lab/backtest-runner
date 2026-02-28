"""
TCBBO (Trade with Consolidated Best Bid/Offer) Options Flow Analyzer.

5-phase pipeline:
  1. Data Ingestion   – Load parquet, parse OCC option symbols
  2. Lee-Ready        – Classify aggressor side from trade price vs BBO
  3. Premium Engine   – Convert to USD premium with bull/bear sentiment
  4. Sweep Aggregator – Detect whale sweeps (clustered large-premium trades)
  5. Options CVD      – Cumulative net premium flow for AOS gate signals
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .parquet_compat import read_parquet_compat, scan_parquet_compat

logger = logging.getLogger("TCBBOAnalyzer")

MARKET_TZ = ZoneInfo("America/New_York")

# OCC symbol layout: "MU    260213C00417500"
#   [0:6]   underlying (left-padded with spaces)
#   [6:12]  expiry YYMMDD
#   [12]    C or P
#   [13:21] strike * 1000
_OCC_RE = re.compile(
    r"^(?P<underlying>.{6})"
    r"(?P<expiry>\d{6})"
    r"(?P<opt_type>[CP])"
    r"(?P<strike>\d{8})$"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ParsedSymbol:
    underlying: str
    expiry: date
    opt_type: str  # "C" or "P"
    strike: float
    raw: str


@dataclass
class SweepCluster:
    """A group of trades hitting the same contract within a short window."""

    symbol: str
    underlying: str
    expiry: str
    strike: float
    opt_type: str
    start_time: str
    end_time: str
    trade_count: int
    total_contracts: int
    total_premium_usd: float
    sentiment: str  # "bullish" / "bearish" / "mixed"
    avg_price: float
    exchanges: int  # number of distinct publisher_ids


@dataclass
class FlowBar:
    """Minute-level aggregated options flow."""

    timestamp: str
    call_premium_buy: float
    call_premium_sell: float
    put_premium_buy: float
    put_premium_sell: float
    net_premium: float  # bullish - bearish
    cumulative_net_premium: float
    trade_count: int
    contract_volume: int
    sweep_count: int


@dataclass
class AnalysisResult:
    """Full TCBBO analysis output."""

    ticker: str
    date_start: str
    date_end: str
    total_trades: int
    classified_trades: int
    neutral_trades: int

    # Premium summary
    total_bullish_premium: float
    total_bearish_premium: float
    net_premium: float
    put_call_premium_ratio: float

    # Sweep summary
    sweep_count: int
    sweep_premium_usd: float

    # Timeseries available via separate endpoints
    flow_bars_count: int


# ---------------------------------------------------------------------------
# Symbol parser
# ---------------------------------------------------------------------------


def parse_occ_symbol(raw: str) -> Optional[ParsedSymbol]:
    """Parse an OCC-format options symbol string."""
    m = _OCC_RE.match(raw)
    if not m:
        return None
    underlying = m.group("underlying").strip()
    exp_str = m.group("expiry")
    try:
        expiry = datetime.strptime(exp_str, "%y%m%d").date()
    except ValueError:
        return None
    opt_type = m.group("opt_type")
    strike = int(m.group("strike")) / 1000.0
    return ParsedSymbol(
        underlying=underlying,
        expiry=expiry,
        opt_type=opt_type,
        strike=strike,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Core analyzer
# ---------------------------------------------------------------------------


class TCBBOAnalyzer:
    """Stateless TCBBO analysis engine. Each call processes a parquet file."""

    def __init__(
        self,
        sweep_window_ms: int = 1000,
        sweep_min_premium_usd: float = 50_000.0,
        flow_bar_freq: str = "1min",
    ):
        self.sweep_window_ms = sweep_window_ms
        self.sweep_min_premium_usd = sweep_min_premium_usd
        self.flow_bar_freq = flow_bar_freq

    @staticmethod
    def _preferred_parquet_columns() -> List[str]:
        return [
            "ts_event",
            "symbol",
            "price",
            "size",
            "bid_px_00",
            "ask_px_00",
            "publisher_id",
        ]

    @staticmethod
    def _required_parquet_columns() -> set[str]:
        return {"ts_event", "symbol", "price", "size", "bid_px_00", "ask_px_00"}

    @staticmethod
    def _parquet_schema_columns(path: str | Path) -> List[str]:
        schema = scan_parquet_compat(path).collect_schema()
        try:
            return [str(name) for name in schema.names()]
        except Exception:
            return [str(name) for name in dict(schema).keys()]

    @classmethod
    def _existing_parquet_columns(
        cls,
        path: str | Path,
        columns: List[str],
    ) -> List[str]:
        available = set(cls._parquet_schema_columns(path))
        return [col for col in columns if col in available]

    # ------------------------------------------------------------------
    # Phase 1: Ingestion
    # ------------------------------------------------------------------

    def load(self, path: str | Path) -> pd.DataFrame:
        """Load TCBBO parquet and parse symbols."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"TCBBO file not found: {p}")

        selected_columns = self._existing_parquet_columns(
            p, self._preferred_parquet_columns()
        )
        missing_required = self._required_parquet_columns() - set(selected_columns)
        if missing_required:
            raise ValueError(
                f"TCBBO parquet missing required columns: {sorted(missing_required)}"
            )

        df = read_parquet_compat(str(p), columns=selected_columns)
        logger.info("Loaded %d rows from %s", len(df), p.name)

        # Parse timestamps
        df["ts_event"] = pd.to_datetime(df["ts_event"], utc=True)

        if "publisher_id" not in df.columns:
            df["publisher_id"] = 0

        # Parse OCC symbols
        df["underlying"] = df["symbol"].str[:6].str.strip()
        df["expiry"] = df["symbol"].str[6:12]
        df["opt_type"] = df["symbol"].str[12:13]
        df["strike"] = df["symbol"].str[13:21].astype(float) / 1000.0

        # Drop rows with missing BBO (can't classify)
        valid_bbo = df["bid_px_00"].notna() & df["ask_px_00"].notna()
        dropped = (~valid_bbo).sum()
        if dropped > 0:
            logger.info("Dropped %d rows with missing BBO", dropped)
            df = df[valid_bbo].copy()

        return df

    # ------------------------------------------------------------------
    # Phase 2: Lee-Ready classification
    # ------------------------------------------------------------------

    def classify_trades(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply Lee-Ready algorithm to classify trade aggressor side.

        Rules (priority order):
          1. price >= ask → aggressive buy
          2. price <= bid → aggressive sell
          3. price > midpoint → buy
          4. price < midpoint → sell
          5. else → neutral
        """
        mid = (df["bid_px_00"] + df["ask_px_00"]) / 2.0

        conditions = [
            df["price"] >= df["ask_px_00"],
            df["price"] <= df["bid_px_00"],
            df["price"] > mid,
            df["price"] < mid,
        ]
        choices = ["buy", "sell", "buy", "sell"]

        df = df.copy()
        df["trade_side"] = np.select(conditions, choices, default="neutral")
        return df

    # ------------------------------------------------------------------
    # Phase 3: Premium engine
    # ------------------------------------------------------------------

    def compute_premium(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute USD premium and bull/bear sentiment for each trade.

        Premium_USD = size * price * 100  (1 contract = 100 shares)

        Sentiment mapping:
          Aggressive buy  Call → bullish  (+)
          Aggressive sell Put  → bullish  (+)
          Aggressive buy  Put  → bearish  (-)
          Aggressive sell Call → bearish  (-)
        """
        df = df.copy()
        df["premium_usd"] = df["size"] * df["price"] * 100.0

        # Sentiment sign: +1 bullish, -1 bearish, 0 neutral
        is_call = df["opt_type"] == "C"
        is_put = df["opt_type"] == "P"
        is_buy = df["trade_side"] == "buy"
        is_sell = df["trade_side"] == "sell"

        sentiment = np.zeros(len(df), dtype=np.int8)
        sentiment[is_buy & is_call] = 1  # aggressive buy call = bullish
        sentiment[is_sell & is_put] = 1  # aggressive sell put = bullish
        sentiment[is_buy & is_put] = -1  # aggressive buy put = bearish
        sentiment[is_sell & is_call] = -1  # aggressive sell call = bearish

        df["sentiment_sign"] = sentiment
        df["signed_premium"] = df["premium_usd"] * df["sentiment_sign"]
        return df

    # ------------------------------------------------------------------
    # Phase 4: Sweep aggregator
    # ------------------------------------------------------------------

    def detect_sweeps(self, df: pd.DataFrame) -> List[SweepCluster]:
        """Detect whale sweeps: clusters of trades on the same contract
        within `sweep_window_ms` whose total premium exceeds threshold."""
        if df.empty:
            return []

        # Work only with classified trades (non-neutral)
        active = df[df["trade_side"] != "neutral"].copy()
        if active.empty:
            return []

        # Group by symbol, then find time clusters
        sweeps: List[SweepCluster] = []
        for symbol, group in active.groupby("symbol", sort=False):
            group = group.sort_values("ts_event")
            ts = group["ts_event"].values.astype("int64")  # nanoseconds
            window_ns = self.sweep_window_ms * 1_000_000

            # Sliding cluster detection
            cluster_start = 0
            for i in range(1, len(ts) + 1):
                # End of group or gap exceeds window
                if i == len(ts) or (ts[i] - ts[i - 1]) > window_ns:
                    cluster = group.iloc[cluster_start:i]
                    total_prem = cluster["premium_usd"].sum()

                    if total_prem >= self.sweep_min_premium_usd and len(cluster) >= 2:
                        parsed = parse_occ_symbol(symbol)
                        bull_prem = cluster.loc[
                            cluster["sentiment_sign"] == 1, "premium_usd"
                        ].sum()
                        bear_prem = cluster.loc[
                            cluster["sentiment_sign"] == -1, "premium_usd"
                        ].sum()

                        if bull_prem > bear_prem * 2:
                            sent = "bullish"
                        elif bear_prem > bull_prem * 2:
                            sent = "bearish"
                        else:
                            sent = "mixed"

                        sweeps.append(
                            SweepCluster(
                                symbol=symbol,
                                underlying=parsed.underlying if parsed else "",
                                expiry=parsed.expiry.isoformat() if parsed else "",
                                strike=parsed.strike if parsed else 0.0,
                                opt_type=parsed.opt_type if parsed else "",
                                start_time=str(cluster["ts_event"].iloc[0]),
                                end_time=str(cluster["ts_event"].iloc[-1]),
                                trade_count=len(cluster),
                                total_contracts=int(cluster["size"].sum()),
                                total_premium_usd=round(total_prem, 2),
                                sentiment=sent,
                                avg_price=round(
                                    (cluster["price"] * cluster["size"]).sum()
                                    / cluster["size"].sum(),
                                    4,
                                ),
                                exchanges=int(cluster["publisher_id"].nunique()),
                            )
                        )

                    cluster_start = i

        # Sort by premium descending
        sweeps.sort(key=lambda s: s.total_premium_usd, reverse=True)
        return sweeps

    # ------------------------------------------------------------------
    # Phase 5: Options CVD (flow bars)
    # ------------------------------------------------------------------

    def compute_flow_bars(
        self,
        df: pd.DataFrame,
        sweeps: Optional[List[SweepCluster]] = None,
    ) -> List[FlowBar]:
        """Aggregate trades into time bars with cumulative net premium."""
        if df.empty:
            return []

        df = df.copy()
        df["bar"] = df["ts_event"].dt.floor(self.flow_bar_freq)

        # Build sweep timestamp set for counting sweeps per bar
        sweep_bars: Dict[Any, int] = {}
        if sweeps:
            for sw in sweeps:
                try:
                    sw_ts = pd.Timestamp(sw.start_time).floor(self.flow_bar_freq)
                    sweep_bars[sw_ts] = sweep_bars.get(sw_ts, 0) + 1
                except Exception:
                    pass

        is_call = df["opt_type"] == "C"
        is_put = df["opt_type"] == "P"
        is_buy = df["trade_side"] == "buy"
        is_sell = df["trade_side"] == "sell"

        df["call_prem_buy"] = np.where(is_call & is_buy, df["premium_usd"], 0.0)
        df["call_prem_sell"] = np.where(is_call & is_sell, df["premium_usd"], 0.0)
        df["put_prem_buy"] = np.where(is_put & is_buy, df["premium_usd"], 0.0)
        df["put_prem_sell"] = np.where(is_put & is_sell, df["premium_usd"], 0.0)

        agg = (
            df.groupby("bar")
            .agg(
                call_premium_buy=("call_prem_buy", "sum"),
                call_premium_sell=("call_prem_sell", "sum"),
                put_premium_buy=("put_prem_buy", "sum"),
                put_premium_sell=("put_prem_sell", "sum"),
                net_premium=("signed_premium", "sum"),
                trade_count=("size", "count"),
                contract_volume=("size", "sum"),
            )
            .sort_index()
            .reset_index()
        )

        cumulative = agg["net_premium"].cumsum().to_numpy()

        bars: List[FlowBar] = []
        for idx, row in enumerate(agg.itertuples(index=False)):
            ts = row.bar
            bars.append(
                FlowBar(
                    timestamp=ts.isoformat(),
                    call_premium_buy=round(row.call_premium_buy, 2),
                    call_premium_sell=round(row.call_premium_sell, 2),
                    put_premium_buy=round(row.put_premium_buy, 2),
                    put_premium_sell=round(row.put_premium_sell, 2),
                    net_premium=round(row.net_premium, 2),
                    cumulative_net_premium=round(float(cumulative[idx]), 2),
                    trade_count=int(row.trade_count),
                    contract_volume=int(row.contract_volume),
                    sweep_count=sweep_bars.get(ts, 0),
                )
            )

        return bars

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def analyze(
        self,
        path: str | Path,
        date_filter: Optional[str] = None,
    ) -> Tuple[AnalysisResult, List[SweepCluster], List[FlowBar], pd.DataFrame]:
        """Run full 5-phase pipeline. Returns (summary, sweeps, flow_bars, df)."""
        # Phase 1
        df = self.load(path)

        # Optional date filter
        if date_filter:
            target = pd.Timestamp(date_filter, tz="UTC")
            market_start = target.replace(hour=0, minute=0, second=0)
            market_end = target.replace(hour=23, minute=59, second=59)
            df = df[(df["ts_event"] >= market_start) & (df["ts_event"] <= market_end)]

        if df.empty:
            return (
                AnalysisResult(
                    ticker="",
                    date_start="",
                    date_end="",
                    total_trades=0,
                    classified_trades=0,
                    neutral_trades=0,
                    total_bullish_premium=0,
                    total_bearish_premium=0,
                    net_premium=0,
                    put_call_premium_ratio=0,
                    sweep_count=0,
                    sweep_premium_usd=0,
                    flow_bars_count=0,
                ),
                [],
                [],
                df,
            )

        total_trades = len(df)

        # Phase 2
        df = self.classify_trades(df)
        neutral_count = (df["trade_side"] == "neutral").sum()

        # Phase 3
        df = self.compute_premium(df)
        bullish_prem = df.loc[df["sentiment_sign"] == 1, "premium_usd"].sum()
        bearish_prem = df.loc[df["sentiment_sign"] == -1, "premium_usd"].sum()

        call_prem = df.loc[df["opt_type"] == "C", "premium_usd"].sum()
        put_prem = df.loc[df["opt_type"] == "P", "premium_usd"].sum()
        pc_ratio = round(put_prem / call_prem, 4) if call_prem > 0 else 0.0

        # Phase 4
        sweeps = self.detect_sweeps(df)
        sweep_prem = sum(s.total_premium_usd for s in sweeps)

        # Phase 5
        flow_bars = self.compute_flow_bars(df, sweeps)

        ticker = df["underlying"].iloc[0] if not df.empty else ""
        date_start = str(df["ts_event"].min().date())
        date_end = str(df["ts_event"].max().date())

        summary = AnalysisResult(
            ticker=ticker,
            date_start=date_start,
            date_end=date_end,
            total_trades=total_trades,
            classified_trades=total_trades - int(neutral_count),
            neutral_trades=int(neutral_count),
            total_bullish_premium=round(bullish_prem, 2),
            total_bearish_premium=round(bearish_prem, 2),
            net_premium=round(bullish_prem - bearish_prem, 2),
            put_call_premium_ratio=pc_ratio,
            sweep_count=len(sweeps),
            sweep_premium_usd=round(sweep_prem, 2),
            flow_bars_count=len(flow_bars),
        )

        return summary, sweeps, flow_bars, df


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def find_tcbbo_files(
    data_dir: str = "data",
    ticker: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Discover TCBBO parquet files in the data directory."""
    roots: List[Path] = []
    seen_roots = set()

    def _push_root(value: Path | str) -> None:
        try:
            candidate = Path(value).expanduser().resolve()
        except Exception:
            candidate = Path(value).expanduser()
        key = str(candidate)
        if key in seen_roots:
            return
        seen_roots.add(key)
        roots.append(candidate)

    # Preserve explicit caller-provided root first.
    _push_root(data_dir)

    # Runtime-friendly fallback: when callers use the default local "data" path
    # (e.g., git worktrees), also scan configured/shared data roots.
    try:
        is_default_local = str(data_dir).strip() in {"", ".", "data"}
        if is_default_local:
            try:
                from src.system_settings import SystemSettings

                for configured_dir in SystemSettings().get_ohlcv_dirs(existing_only=False):
                    _push_root(configured_dir)
            except Exception:
                pass
    except Exception:
        pass

    pattern = "*_OPRA_tcbbo_*.parquet"
    if ticker:
        pattern = f"{ticker.upper()}_OPRA_tcbbo_*.parquet"

    results = []
    seen_files = set()
    for root in roots:
        if not root.exists():
            continue
        for p in sorted(root.glob(pattern)):
            try:
                resolved_file = str(p.resolve())
            except Exception:
                resolved_file = str(p)
            if resolved_file in seen_files:
                continue
            seen_files.add(resolved_file)
            parts = p.stem.split("_")
            # Expected: {TICKER}_OPRA_tcbbo_{START}_{END}
            if len(parts) >= 5:
                results.append(
                    {
                        "file": resolved_file,
                        "ticker": parts[0],
                        "start_date": parts[3],
                        "end_date": parts[4],
                        "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                        "search_root": str(root),
                    }
                )
    return results


# ---------------------------------------------------------------------------
# Bar enrichment helper (for session_runner integration)
# ---------------------------------------------------------------------------


def build_tcbbo_feature_map(
    path: str | Path,
    sweep_window_ms: int = 1000,
    sweep_min_premium_usd: float = 50_000.0,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Build a minute-keyed feature map from TCBBO data for bar enrichment.

    Returns:
        (feature_map, stats) where feature_map is keyed by ISO timestamp string
        and each value is a dict of tcbbo_* fields to attach to bars.
    """
    analyzer = TCBBOAnalyzer(
        sweep_window_ms=sweep_window_ms,
        sweep_min_premium_usd=sweep_min_premium_usd,
        flow_bar_freq="1min",
    )

    summary, sweeps, flow_bars, _df = analyzer.analyze(path)

    # Build sweep lookup: minute_iso -> list of sweep sentiments
    sweep_by_minute: Dict[str, List[str]] = {}
    sweep_prem_by_minute: Dict[str, float] = {}
    for sw in sweeps:
        try:
            sw_ts = pd.Timestamp(sw.start_time).floor("1min")
            key = sw_ts.isoformat()
            sweep_by_minute.setdefault(key, []).append(sw.sentiment)
            sweep_prem_by_minute[key] = (
                sweep_prem_by_minute.get(key, 0.0) + sw.total_premium_usd
            )
        except Exception:
            pass

    feature_map: Dict[str, Dict[str, Any]] = {}
    for bar in flow_bars:
        ts_key = bar.timestamp
        feature_map[ts_key] = {
            "tcbbo_net_premium": bar.net_premium,
            "tcbbo_cumulative_net_premium": bar.cumulative_net_premium,
            "tcbbo_call_buy_premium": bar.call_premium_buy,
            "tcbbo_put_buy_premium": bar.put_premium_buy,
            "tcbbo_call_sell_premium": bar.call_premium_sell,
            "tcbbo_put_sell_premium": bar.put_premium_sell,
            "tcbbo_sweep_count": bar.sweep_count,
            "tcbbo_sweep_premium": sweep_prem_by_minute.get(ts_key, 0.0),
            "tcbbo_trade_count": bar.trade_count,
            "tcbbo_has_data": True,
        }

    stats = {
        "tcbbo_file": str(path),
        "tcbbo_total_trades": summary.total_trades,
        "tcbbo_classified_trades": summary.classified_trades,
        "tcbbo_sweep_count": summary.sweep_count,
        "tcbbo_net_premium": summary.net_premium,
        "tcbbo_minutes_covered": len(feature_map),
    }
    logger.info(
        "TCBBO feature map built: %d minutes, %d sweeps, net_premium=$%.0f",
        len(feature_map),
        summary.sweep_count,
        summary.net_premium,
    )
    return feature_map, stats
