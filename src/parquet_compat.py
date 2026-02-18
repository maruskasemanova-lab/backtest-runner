from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


def _quote_ident(name: str) -> str:
    token = str(name or "").replace('"', '""')
    return f'"{token}"'


def read_parquet_compat(path: str | Path, columns: Optional[Iterable[str]] = None) -> pd.DataFrame:
    """
    Read parquet with a lightweight fallback when pyarrow is unavailable.

    Vercel serverless size limits make pyarrow impractical for this project.
    DuckDB keeps parquet support available with a much smaller dependency.
    """
    source = str(Path(path))
    cols = [str(col) for col in (columns or []) if str(col).strip()]

    try:
        if cols:
            return pd.read_parquet(source, columns=cols)
        return pd.read_parquet(source)
    except Exception as primary_exc:
        try:
            import duckdb  # type: ignore
        except Exception:
            raise primary_exc

        conn = duckdb.connect(database=":memory:")
        try:
            if cols:
                select_sql = ", ".join(_quote_ident(col) for col in cols)
            else:
                select_sql = "*"
            query = f"SELECT {select_sql} FROM read_parquet(?)"
            return conn.execute(query, [source]).fetch_df()
        finally:
            conn.close()


def write_parquet_compat(df: pd.DataFrame, path: str | Path, *, index: bool = False) -> None:
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
