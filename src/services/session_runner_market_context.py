from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Callable, Dict, List, Optional

try:
    import polars as pl
except Exception:  # pragma: no cover - polars may be unavailable
    pl = None


SafeFloat = Callable[[Any], Optional[float]]
NormalizedBar = tuple[Any, ...]
MetricRow = tuple[Any, ...]

_METRIC_COLUMNS = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "candle_range",
    "candle_body",
    "body_to_range_ratio",
    "upper_wick",
    "lower_wick",
    "close_location_pct",
    "bar_return_pct",
    "close_to_vwap_pct",
    "close_change_1_bar_pct",
    "close_change_3_bar_pct",
    "close_change_5_bar_pct",
    "close_change_10_bar_pct",
    "close_change_20_bar_pct",
    "realized_volatility_5_bar_pct",
    "realized_volatility_20_bar_pct",
    "session_open_price",
    "session_high_so_far",
    "session_low_so_far",
    "distance_from_session_open_pct",
    "distance_from_session_high_pct",
    "distance_from_session_low_pct",
    "avg_volume_5_bar",
    "avg_volume_20_bar",
    "volume_vs_avg_5_ratio",
    "volume_vs_avg_20_ratio",
)


class MarketContextProvider:
    def __init__(self, bars: List[Dict[str, Any]], safe_float: SafeFloat):
        self._safe_float = safe_float
        self._normalized_bars = self._normalize_bars(bars)
        self._bar_count = len(self._normalized_bars)
        self._contexts = self._build_contexts(self._normalized_bars)

    def build_context(self, bar_index: int) -> Dict[str, Any]:
        if not self._contexts:
            return {
                "timestamp": "",
                "bar_index": int(bar_index),
                "total_bars": 0,
                "progress_pct": 0.0,
                "bar_ohlcv": {},
                "candle": {},
                "price_evolution": {},
                "volume_context": {},
                "recent_bars": [],
            }

        resolved_index = min(max(int(bar_index), 0), len(self._contexts) - 1)
        payload = self._compose_context_payload(
            metrics=self._contexts[resolved_index],
            recent_bars=self._build_recent_bars_for_index(resolved_index),
        )
        payload["bar_index"] = resolved_index
        payload["total_bars"] = self._bar_count
        payload["progress_pct"] = (
            ((resolved_index + 1) / self._bar_count * 100.0)
            if self._bar_count
            else 0.0
        )
        return payload

    @staticmethod
    def _timestamp_token(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _pct_change(
        current: Optional[float], baseline: Optional[float]
    ) -> Optional[float]:
        if current is None or baseline is None or baseline == 0:
            return None
        return ((current - baseline) / baseline) * 100.0

    @staticmethod
    def _average(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return sum(values) / len(values)

    @staticmethod
    def _stddev(values: List[float]) -> Optional[float]:
        if len(values) < 2:
            return None
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(max(variance, 0.0))

    def _normalize_bars(self, bars: List[Dict[str, Any]]) -> List[NormalizedBar]:
        normalized: List[NormalizedBar] = []
        for bar in bars:
            normalized.append(
                (
                    self._timestamp_token(bar.get("timestamp")),
                    self._safe_float(bar.get("open")),
                    self._safe_float(bar.get("high")),
                    self._safe_float(bar.get("low")),
                    self._safe_float(bar.get("close")),
                    self._safe_float(bar.get("volume")),
                    self._safe_float(bar.get("vwap")),
                    self._safe_float(bar.get("l2_signed_aggression")),
                    self._safe_float(bar.get("l2_imbalance")),
                    self._safe_float(bar.get("l2_book_pressure")),
                )
            )
        return normalized

    @staticmethod
    def _snapshot_bar(item: NormalizedBar) -> Dict[str, Any]:
        (
            timestamp,
            open_px,
            high_px,
            low_px,
            close_px,
            volume,
            vwap,
            l2_signed_aggression,
            l2_imbalance,
            l2_book_pressure,
        ) = item
        return {
            "timestamp": timestamp,
            "open": open_px,
            "high": high_px,
            "low": low_px,
            "close": close_px,
            "volume": volume,
            "vwap": vwap,
            "l2_signed_aggression": l2_signed_aggression,
            "l2_imbalance": l2_imbalance,
            "l2_book_pressure": l2_book_pressure,
        }

    def _build_recent_bars_for_index(self, bar_index: int) -> List[Dict[str, Any]]:
        start = max(0, int(bar_index) - 4)
        return [
            self._snapshot_bar(item)
            for item in self._normalized_bars[start : int(bar_index) + 1]
        ]

    @staticmethod
    def _compose_context_payload(
        *, metrics: MetricRow, recent_bars: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        (
            timestamp,
            open_px,
            high_px,
            low_px,
            close_px,
            volume,
            vwap,
            candle_range,
            candle_body,
            body_to_range_ratio,
            upper_wick,
            lower_wick,
            close_location_pct,
            bar_return_pct,
            close_to_vwap_pct,
            close_change_1_bar_pct,
            close_change_3_bar_pct,
            close_change_5_bar_pct,
            close_change_10_bar_pct,
            close_change_20_bar_pct,
            realized_volatility_5_bar_pct,
            realized_volatility_20_bar_pct,
            session_open_price,
            session_high_so_far,
            session_low_so_far,
            distance_from_session_open_pct,
            distance_from_session_high_pct,
            distance_from_session_low_pct,
            avg_volume_5_bar,
            avg_volume_20_bar,
            volume_vs_avg_5_ratio,
            volume_vs_avg_20_ratio,
        ) = metrics
        return {
            "timestamp": timestamp,
            "bar_ohlcv": {
                "open": open_px,
                "high": high_px,
                "low": low_px,
                "close": close_px,
                "volume": volume,
                "vwap": vwap,
            },
            "candle": {
                "range": candle_range,
                "body": candle_body,
                "body_to_range_ratio": body_to_range_ratio,
                "upper_wick": upper_wick,
                "lower_wick": lower_wick,
                "close_location_pct": close_location_pct,
                "bar_return_pct": bar_return_pct,
                "close_to_vwap_pct": close_to_vwap_pct,
            },
            "price_evolution": {
                "close_change_1_bar_pct": close_change_1_bar_pct,
                "close_change_3_bar_pct": close_change_3_bar_pct,
                "close_change_5_bar_pct": close_change_5_bar_pct,
                "close_change_10_bar_pct": close_change_10_bar_pct,
                "close_change_20_bar_pct": close_change_20_bar_pct,
                "realized_volatility_5_bar_pct": realized_volatility_5_bar_pct,
                "realized_volatility_20_bar_pct": realized_volatility_20_bar_pct,
                "session_open_price": session_open_price,
                "session_high_so_far": session_high_so_far,
                "session_low_so_far": session_low_so_far,
                "distance_from_session_open_pct": distance_from_session_open_pct,
                "distance_from_session_high_pct": distance_from_session_high_pct,
                "distance_from_session_low_pct": distance_from_session_low_pct,
            },
            "volume_context": {
                "avg_volume_5_bar": avg_volume_5_bar,
                "avg_volume_20_bar": avg_volume_20_bar,
                "volume_vs_avg_5_ratio": volume_vs_avg_5_ratio,
                "volume_vs_avg_20_ratio": volume_vs_avg_20_ratio,
            },
            "recent_bars": recent_bars,
        }

    @staticmethod
    def _pct_change_expr(current: Any, baseline: Any) -> Any:
        current_expr = pl.col(current) if isinstance(current, str) else current
        baseline_expr = pl.col(baseline) if isinstance(baseline, str) else baseline
        return (
            pl.when(
                current_expr.is_not_null()
                & baseline_expr.is_not_null()
                & (baseline_expr != 0)
            )
            .then(((current_expr - baseline_expr) / baseline_expr) * 100.0)
            .otherwise(None)
        )

    def _build_contexts_polars(
        self,
        normalized_bars: List[NormalizedBar],
    ) -> List[MetricRow]:
        if pl is None:
            return self._build_contexts_fallback(normalized_bars)

        first_close = next((row[4] for row in normalized_bars if row[4] is not None), None)
        metrics_df = pl.DataFrame(
            {
                "timestamp": [row[0] for row in normalized_bars],
                "open": [row[1] for row in normalized_bars],
                "high": [row[2] for row in normalized_bars],
                "low": [row[3] for row in normalized_bars],
                "close": [row[4] for row in normalized_bars],
                "volume": [row[5] for row in normalized_bars],
                "vwap": [row[6] for row in normalized_bars],
            }
        ).with_columns(
            [
                (pl.col("high") - pl.col("low")).alias("candle_range"),
                (pl.col("close") - pl.col("open")).alias("candle_body"),
                pl.when(
                    pl.col("high").is_not_null()
                    & pl.col("open").is_not_null()
                    & pl.col("close").is_not_null()
                )
                .then(pl.col("high") - pl.max_horizontal("open", "close"))
                .otherwise(None)
                .alias("upper_wick"),
                pl.when(
                    pl.col("low").is_not_null()
                    & pl.col("open").is_not_null()
                    & pl.col("close").is_not_null()
                )
                .then(pl.min_horizontal("open", "close") - pl.col("low"))
                .otherwise(None)
                .alias("lower_wick"),
                self._pct_change_expr("close", "open").alias("bar_return_pct"),
                self._pct_change_expr("close", "vwap").alias("close_to_vwap_pct"),
                self._pct_change_expr("close", pl.col("close").shift(1)).alias(
                    "close_change_1_bar_pct"
                ),
                self._pct_change_expr("close", pl.col("close").shift(3)).alias(
                    "close_change_3_bar_pct"
                ),
                self._pct_change_expr("close", pl.col("close").shift(5)).alias(
                    "close_change_5_bar_pct"
                ),
                self._pct_change_expr("close", pl.col("close").shift(10)).alias(
                    "close_change_10_bar_pct"
                ),
                self._pct_change_expr("close", pl.col("close").shift(20)).alias(
                    "close_change_20_bar_pct"
                ),
                self._pct_change_expr("close", pl.lit(first_close)).alias(
                    "distance_from_session_open_pct"
                ),
                pl.col("high").cum_max().alias("session_high_so_far"),
                pl.col("low").cum_min().alias("session_low_so_far"),
                pl.col("volume")
                .rolling_mean(window_size=5, min_samples=1)
                .alias("avg_volume_5_bar"),
                pl.col("volume")
                .rolling_mean(window_size=20, min_samples=1)
                .alias("avg_volume_20_bar"),
                self._pct_change_expr("close", pl.col("close").shift(1)).alias(
                    "close_return_pct"
                ),
            ]
        ).with_columns(
            [
                pl.when(
                    pl.col("candle_body").is_not_null()
                    & pl.col("candle_range").is_not_null()
                    & (pl.col("candle_range") != 0)
                )
                .then(pl.col("candle_body").abs() / pl.col("candle_range"))
                .otherwise(None)
                .alias("body_to_range_ratio"),
                pl.when(
                    pl.col("candle_range").is_not_null()
                    & (pl.col("candle_range") > 0)
                    & pl.col("close").is_not_null()
                    & pl.col("low").is_not_null()
                )
                .then(((pl.col("close") - pl.col("low")) / pl.col("candle_range")) * 100.0)
                .otherwise(None)
                .alias("close_location_pct"),
                pl.lit(first_close).alias("session_open_price"),
                pl.col("close_return_pct")
                .rolling_std(window_size=5, min_samples=2, ddof=0)
                .alias("realized_volatility_5_bar_pct"),
                pl.col("close_return_pct")
                .rolling_std(window_size=20, min_samples=2, ddof=0)
                .alias("realized_volatility_20_bar_pct"),
            ]
        ).with_columns(
            [
                self._pct_change_expr("close", "session_high_so_far").alias(
                    "distance_from_session_high_pct"
                ),
                self._pct_change_expr("close", "session_low_so_far").alias(
                    "distance_from_session_low_pct"
                ),
                pl.when(
                    pl.col("volume").is_not_null()
                    & pl.col("avg_volume_5_bar").is_not_null()
                    & (pl.col("avg_volume_5_bar") != 0)
                )
                .then(pl.col("volume") / pl.col("avg_volume_5_bar"))
                .otherwise(None)
                .alias("volume_vs_avg_5_ratio"),
                pl.when(
                    pl.col("volume").is_not_null()
                    & pl.col("avg_volume_20_bar").is_not_null()
                    & (pl.col("avg_volume_20_bar") != 0)
                )
                .then(pl.col("volume") / pl.col("avg_volume_20_bar"))
                .otherwise(None)
                .alias("volume_vs_avg_20_ratio"),
            ]
        )

        return list(metrics_df.select(list(_METRIC_COLUMNS)).iter_rows())

    def _build_contexts_fallback(
        self,
        normalized_bars: List[NormalizedBar],
    ) -> List[MetricRow]:
        metrics_rows: List[MetricRow] = []
        closes: List[float] = []
        highs: List[float] = []
        lows: List[float] = []
        volumes: List[float] = []
        returns: List[float] = []

        for row in normalized_bars:
            (
                timestamp,
                open_px,
                high_px,
                low_px,
                close_px,
                volume,
                vwap,
                _l2_signed_aggression,
                _l2_imbalance,
                _l2_book_pressure,
            ) = row

            if close_px is not None:
                if closes:
                    change = self._pct_change(close_px, closes[-1])
                    if change is not None:
                        returns.append(change)
                closes.append(close_px)
            if high_px is not None:
                highs.append(high_px)
            if low_px is not None:
                lows.append(low_px)
            if volume is not None:
                volumes.append(volume)

            candle_range = (
                high_px - low_px if high_px is not None and low_px is not None else None
            )
            candle_body = (
                close_px - open_px
                if close_px is not None and open_px is not None
                else None
            )
            upper_wick = (
                high_px - max(open_px, close_px)
                if high_px is not None and open_px is not None and close_px is not None
                else None
            )
            lower_wick = (
                min(open_px, close_px) - low_px
                if low_px is not None and open_px is not None and close_px is not None
                else None
            )
            close_location_pct = None
            if (
                candle_range is not None
                and candle_range > 0
                and close_px is not None
                and low_px is not None
            ):
                close_location_pct = ((close_px - low_px) / candle_range) * 100.0

            def _lookback_close_pct(lookback_bars: int) -> Optional[float]:
                if close_px is None or lookback_bars <= 0 or len(closes) <= lookback_bars:
                    return None
                return self._pct_change(close_px, closes[-(lookback_bars + 1)])

            avg_volume_5 = self._average(volumes[-5:])
            avg_volume_20 = self._average(volumes[-20:])
            session_open = closes[0] if closes else None
            session_high = max(highs) if highs else None
            session_low = min(lows) if lows else None

            metrics_rows.append(
                (
                    timestamp,
                    open_px,
                    high_px,
                    low_px,
                    close_px,
                    volume,
                    vwap,
                    candle_range,
                    candle_body,
                    (
                        (abs(candle_body) / candle_range)
                        if candle_body is not None and candle_range not in (None, 0)
                        else None
                    ),
                    upper_wick,
                    lower_wick,
                    close_location_pct,
                    self._pct_change(close_px, open_px),
                    self._pct_change(close_px, vwap),
                    _lookback_close_pct(1),
                    _lookback_close_pct(3),
                    _lookback_close_pct(5),
                    _lookback_close_pct(10),
                    _lookback_close_pct(20),
                    self._stddev(returns[-5:]),
                    self._stddev(returns[-20:]),
                    session_open,
                    session_high,
                    session_low,
                    self._pct_change(close_px, session_open),
                    self._pct_change(close_px, session_high),
                    self._pct_change(close_px, session_low),
                    avg_volume_5,
                    avg_volume_20,
                    (
                        (volume / avg_volume_5)
                        if volume is not None and avg_volume_5 not in (None, 0)
                        else None
                    ),
                    (
                        (volume / avg_volume_20)
                        if volume is not None and avg_volume_20 not in (None, 0)
                        else None
                    ),
                )
            )
        return metrics_rows

    def _build_contexts(
        self, normalized_bars: List[NormalizedBar]
    ) -> List[MetricRow]:
        if not normalized_bars:
            return []
        if pl is not None:
            try:
                return self._build_contexts_polars(normalized_bars)
            except Exception:
                pass
        return self._build_contexts_fallback(normalized_bars)
