from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Callable, Dict, List, MutableMapping, Optional

try:
    import polars as pl
except Exception:  # pragma: no cover - polars optional in some environments
    pl = None


ToUtcDatetime = Callable[[Any], datetime]
QuoteRow = Dict[str, float]
QuoteRows = Optional[List[QuoteRow]]
QuoteCache = MutableMapping[int, QuoteRows]


class IntrabarQuoteProvider:
    def __init__(
        self,
        *,
        ticker: str,
        to_utc_datetime: ToUtcDatetime,
        logger: logging.Logger,
    ):
        self._ticker = str(ticker)
        self._to_utc_datetime = to_utc_datetime
        self._logger = logger

    @staticmethod
    def resolve_eval_step_seconds(raw_step_seconds: Any) -> int:
        try:
            parsed = int(raw_step_seconds)
        except (TypeError, ValueError):
            parsed = 1
        return max(1, min(60, parsed))

    def apply_eval_step(
        self,
        quotes: QuoteRows,
        *,
        raw_step_seconds: Any,
    ) -> QuoteRows:
        if not quotes:
            return None

        step = self.resolve_eval_step_seconds(raw_step_seconds)
        if step <= 1:
            return quotes

        last_index = len(quotes) - 1
        selected: List[QuoteRow] = []
        for idx, quote in enumerate(quotes):
            sec_raw = quote.get("s")
            try:
                sec = int(sec_raw)
            except (TypeError, ValueError):
                sec = -1
            include = idx == 0 or idx == last_index or (sec >= 0 and sec % step == 0)
            if not include:
                continue
            if selected:
                prev_sec = selected[-1].get("s")
                try:
                    if int(prev_sec) == sec:
                        continue
                except (TypeError, ValueError):
                    pass
            selected.append(quote)

        if not selected:
            return quotes
        return selected

    def load_quotes_for_timestamp(
        self,
        *,
        timestamp: datetime,
        l2_manager: Any,
        cache: QuoteCache,
        raw_step_seconds: Any,
    ) -> QuoteRows:
        """
        Load compact 1-second bid/ask quotes for one minute.

        Returns cached payload format:
          [{"s": second, "bid": top_bid_px, "ask": top_ask_px}, ...]
        """
        if l2_manager is None:
            return None

        ts_utc = self._to_utc_datetime(timestamp)
        minute_start = ts_utc.replace(second=0, microsecond=0)
        minute_key = int(minute_start.timestamp())
        if minute_key in cache:
            return self.apply_eval_step(
                cache[minute_key],
                raw_step_seconds=raw_step_seconds,
            )

        minute_end = minute_start + timedelta(seconds=59, microseconds=999999)
        try:
            frames = l2_manager.get_intrabar_frames(
                ticker=self._ticker,
                start_time=minute_start,
                end_time=minute_end,
            )
            self._logger.warning(
                "[INTRABAR-DEEP-DEBUG] get_intrabar_frames returned %s frames. type=%s",
                self._frame_len_token(frames),
                type(frames),
            )
            if not self._frame_is_empty(frames):
                self._logger.warning(
                    "[INTRABAR-DEEP-DEBUG] first row has_book_coverage=%s",
                    self._first_row_book_coverage(frames),
                )
        except Exception as exc:
            import traceback

            self._logger.warning(
                "[INTRABAR-DEEP-DEBUG] Intrabar quote load exc for %s @ %s: %s\n%s",
                self._ticker,
                minute_start,
                exc,
                traceback.format_exc(),
            )
            cache[minute_key] = None
            return None

        if self._frame_is_empty(frames):
            self._logger.warning("[INTRABAR-DEEP-DEBUG] Frames empty or None!")
            cache[minute_key] = None
            return None

        quote_rows = self._extract_quote_rows(frames, minute_start=minute_start)
        cached = quote_rows if quote_rows else None

        self._logger.warning(
            "[INTRABAR-DEEP-DEBUG] quote_rows built: %s quotes.",
            len(quote_rows),
        )
        if not quote_rows:
            self._logger.warning(
                "[INTRABAR-DEEP-DEBUG] Why empty? Sample row: %s",
                self._sample_row(frames),
            )

        cache[minute_key] = cached
        return self.apply_eval_step(cached, raw_step_seconds=raw_step_seconds)

    @staticmethod
    def _frame_len_token(frames: Any) -> Any:
        if frames is None:
            return "None"
        try:
            return len(frames)
        except Exception:
            return "?"

    @staticmethod
    def _frame_is_empty(frames: Any) -> bool:
        if frames is None:
            return True
        empty_attr = getattr(frames, "empty", None)
        if isinstance(empty_attr, bool):
            return empty_attr
        is_empty = getattr(frames, "is_empty", None)
        if callable(is_empty):
            try:
                return bool(is_empty())
            except Exception:
                pass
        try:
            return len(frames) == 0
        except Exception:
            return False

    @staticmethod
    def _first_row_book_coverage(frames: Any) -> Any:
        if hasattr(frames, "iloc"):
            return frames["has_book_coverage"].iloc[0]
        if hasattr(frames, "row"):
            return frames.row(0, named=True).get("has_book_coverage")
        return None

    def _extract_quote_rows(
        self,
        frames: Any,
        *,
        minute_start: datetime,
    ) -> List[QuoteRow]:
        used_polars = False
        quote_rows: List[QuoteRow] = []

        if pl is not None:
            try:
                pl_frame = (
                    frames if isinstance(frames, pl.DataFrame) else pl.from_pandas(frames)
                )
                pl_quotes = (
                    pl_frame.with_columns(
                        [
                            pl.col("has_book_coverage")
                            .cast(pl.Boolean, strict=False)
                            .fill_null(False)
                            .alias("has_book_coverage"),
                            pl.col("top_bid_px")
                            .cast(pl.Float64, strict=False)
                            .alias("bid"),
                            pl.col("top_ask_px")
                            .cast(pl.Float64, strict=False)
                            .alias("ask"),
                            pl.col("ts_sec")
                            .map_elements(
                                lambda ts: (
                                    self._to_utc_datetime(ts).second
                                    if ts is not None
                                    else None
                                ),
                                return_dtype=pl.Int64,
                            )
                            .alias("s"),
                        ]
                    )
                    .filter(pl.col("has_book_coverage"))
                    .filter((pl.col("bid") > 0.0) | (pl.col("ask") > 0.0))
                    .filter(pl.col("s").is_not_null())
                    .select(["s", "bid", "ask"])
                    .sort("s")
                )
                quote_rows = [
                    {
                        "s": int(row["s"]),
                        "bid": round(float(row["bid"]), 6),
                        "ask": round(float(row["ask"]), 6),
                    }
                    for row in pl_quotes.to_dicts()
                ]
                used_polars = True
            except Exception as exc:
                self._logger.warning(
                    "[INTRABAR-DEEP-DEBUG] polars parse fallback for %s @ %s: %s",
                    self._ticker,
                    minute_start,
                    exc,
                )

        if used_polars:
            return quote_rows

        for _, row in frames.iterrows():
            if not bool(row.get("has_book_coverage", False)):
                continue

            try:
                bid = float(row.get("top_bid_px", 0.0) or 0.0)
                ask = float(row.get("top_ask_px", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue

            if bid <= 0.0 and ask <= 0.0:
                continue

            ts_sec = row.get("ts_sec")
            try:
                second = int(self._to_utc_datetime(ts_sec).second)
            except Exception:
                continue

            quote_rows.append(
                {
                    "s": second,
                    "bid": round(bid, 6),
                    "ask": round(ask, 6),
                }
            )

        quote_rows.sort(key=lambda item: item["s"])
        return quote_rows

    @staticmethod
    def _sample_row(frames: Any) -> Dict[str, Any]:
        if hasattr(frames, "iloc"):
            return dict(frames.iloc[0].to_dict())
        if hasattr(frames, "row"):
            sample = frames.row(0, named=True)
            return dict(sample) if isinstance(sample, dict) else {}
        return {}
