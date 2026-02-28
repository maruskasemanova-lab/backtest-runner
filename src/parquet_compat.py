from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

try:
    import polars as pl
except Exception:  # pragma: no cover - import guard for misconfigured runtimes
    pl = None


def _require_polars():
    if pl is None:
        raise RuntimeError("polars is required for parquet reads in this runtime")
    return pl


def scan_parquet_compat(path: str | Path):
    source = str(Path(path))
    polars = _require_polars()
    return polars.scan_parquet(source)


def _read_parquet_with_polars(
    source: str, *, columns: Optional[Iterable[str]] = None
) -> pd.DataFrame:
    lazy_frame = scan_parquet_compat(source)
    cols = [str(col) for col in (columns or []) if str(col).strip()]
    if cols:
        lazy_frame = lazy_frame.select(cols)

    try:
        frame = lazy_frame.collect(engine="streaming")
    except TypeError:
        try:
            frame = lazy_frame.collect(streaming=True)
        except TypeError:
            frame = lazy_frame.collect()

    try:
        return frame.to_pandas(use_pyarrow_extension_array=False)
    except TypeError:
        return frame.to_pandas()
    except Exception:
        return pd.DataFrame(frame.to_dict(as_series=False))


def read_parquet_compat(
    path: str | Path, columns: Optional[Iterable[str]] = None
) -> pd.DataFrame:
    """
    Read parquet through a Polars lazy scan and return pandas for compatibility.

    This path is intentionally Polars-only for runtime performance. The public
    contract still returns a pandas DataFrame for compatibility with legacy
    consumers, but decoding stays in Polars until the final conversion step.
    """
    source = str(Path(path))
    cols = [str(col) for col in (columns or []) if str(col).strip()]
    return _read_parquet_with_polars(source, columns=cols)


def write_parquet_compat(
    df: pd.DataFrame, path: str | Path, *, index: bool = False
) -> None:
    target = str(Path(path))
    try:
        df.to_parquet(target, index=index)
        return
    except Exception as primary_exc:
        try:
            import duckdb  # type: ignore
        except Exception:
            raise primary_exc

        conn = duckdb.connect(database=":memory:")
        try:
            export_df = df if index else df.reset_index(drop=True)
            conn.register("_parquet_frame", export_df)
            escaped_target = target.replace("'", "''")
            conn.execute(f"COPY _parquet_frame TO '{escaped_target}' (FORMAT PARQUET)")
        finally:
            conn.close()
