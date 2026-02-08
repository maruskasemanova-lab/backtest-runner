"""
Run Artifact Store: Persist and load L2 artifacts (parquet files).

Manages the storage structure:
    runs/{run_id}/{ticker}/
        bars_1m.parquet
        intrabar_1s.parquet
        metadata.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .intrabar_frame_builder import INTRABAR_SCHEMA_VERSION


class RunArtifactStore:
    """Store and load run artifacts (parquet files)."""
    
    def __init__(self, base_dir: str = "runs"):
        """Initialize artifact store.
        
        Args:
            base_dir: Base directory for run artifacts
        """
        self.base_dir = Path(base_dir).resolve()
    
    def _run_dir(self, run_id: str, ticker: str) -> Path:
        """Get directory for a specific run/ticker."""
        return self.base_dir / run_id / ticker
    
    def _ensure_dir(self, path: Path) -> None:
        """Create directory if it doesn't exist."""
        path.mkdir(parents=True, exist_ok=True)
    
    def save_intrabar_1s(
        self,
        run_id: str,
        ticker: str,
        df: pd.DataFrame,
        date: Optional[str] = None,
    ) -> str:
        """Save 1-second intrabar frames to parquet.
        
        Args:
            run_id: Run identifier
            ticker: Stock ticker
            df: DataFrame with 1s features
            date: Optional date suffix for filename
            
        Returns:
            Path to saved file
        """
        dir_path = self._run_dir(run_id, ticker)
        self._ensure_dir(dir_path)
        
        filename = f"intrabar_1s_{date}.parquet" if date else "intrabar_1s.parquet"
        file_path = dir_path / filename
        
        df.to_parquet(file_path, index=False)
        return str(file_path)
    
    def save_bars_1m(
        self,
        run_id: str,
        ticker: str,
        df: pd.DataFrame,
        date: Optional[str] = None,
    ) -> str:
        """Save 1-minute bars to parquet.
        
        Args:
            run_id: Run identifier
            ticker: Stock ticker
            df: DataFrame with 1m features
            date: Optional date suffix
            
        Returns:
            Path to saved file
        """
        dir_path = self._run_dir(run_id, ticker)
        self._ensure_dir(dir_path)
        
        filename = f"bars_1m_{date}.parquet" if date else "bars_1m.parquet"
        file_path = dir_path / filename
        
        df.to_parquet(file_path, index=False)
        return str(file_path)
    
    def save_metadata(
        self,
        run_id: str,
        ticker: str,
        metadata: Dict[str, Any],
    ) -> str:
        """Save metadata JSON.
        
        Args:
            run_id: Run identifier
            ticker: Stock ticker
            metadata: Metadata dict
            
        Returns:
            Path to saved file
        """
        dir_path = self._run_dir(run_id, ticker)
        self._ensure_dir(dir_path)
        
        file_path = dir_path / "metadata.json"
        
        # Add standard fields
        metadata.setdefault("schema_version", INTRABAR_SCHEMA_VERSION)
        metadata.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        metadata.setdefault("ticker", ticker)
        metadata.setdefault("run_id", run_id)
        
        with open(file_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)
        
        return str(file_path)
    
    def load_intrabar_window(
        self,
        run_id: str,
        ticker: str,
        t0: datetime,
        t1: datetime,
        date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load intrabar frames for a time window.
        
        Args:
            run_id: Run identifier
            ticker: Stock ticker
            t0: Start time (inclusive)
            t1: End time (inclusive)
            date: Optional date for specific file
            
        Returns:
            DataFrame with filtered 1s features
        """
        dir_path = self._run_dir(run_id, ticker)
        
        # Find matching file(s)
        if date:
            file_path = dir_path / f"intrabar_1s_{date}.parquet"
            if not file_path.exists():
                return pd.DataFrame()
            files = [file_path]
        else:
            files = list(dir_path.glob("intrabar_1s*.parquet"))
        
        if not files:
            return pd.DataFrame()
        
        frames = []
        for f in files:
            df = pd.read_parquet(f)
            if "ts_sec" in df.columns:
                # Convert to datetime if needed
                if not pd.api.types.is_datetime64_any_dtype(df["ts_sec"]):
                    df["ts_sec"] = pd.to_datetime(df["ts_sec"])
                
                # Make timezone aware if needed
                if df["ts_sec"].dt.tz is None:
                    df["ts_sec"] = df["ts_sec"].dt.tz_localize("UTC")
                
                # Filter to window
                mask = (df["ts_sec"] >= t0) & (df["ts_sec"] <= t1)
                df = df[mask]
            frames.append(df)
        
        if not frames:
            return pd.DataFrame()
        
        return pd.concat(frames, ignore_index=True)
    
    def load_bars_1m(
        self,
        run_id: str,
        ticker: str,
        date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load 1-minute bars.
        
        Args:
            run_id: Run identifier
            ticker: Stock ticker
            date: Optional date for specific file
            
        Returns:
            DataFrame with 1m features
        """
        dir_path = self._run_dir(run_id, ticker)
        
        if date:
            file_path = dir_path / f"bars_1m_{date}.parquet"
        else:
            file_path = dir_path / "bars_1m.parquet"
        
        if not file_path.exists():
            return pd.DataFrame()
        
        return pd.read_parquet(file_path)
    
    def load_metadata(
        self,
        run_id: str,
        ticker: str,
    ) -> Dict[str, Any]:
        """Load metadata JSON.
        
        Args:
            run_id: Run identifier
            ticker: Stock ticker
            
        Returns:
            Metadata dict or empty dict if not found
        """
        file_path = self._run_dir(run_id, ticker) / "metadata.json"
        
        if not file_path.exists():
            return {}
        
        with open(file_path) as f:
            return json.load(f)
    
    def list_runs(self) -> list:
        """List all run IDs."""
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]
    
    def list_tickers(self, run_id: str) -> list:
        """List all tickers for a run."""
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            return []
        return [d.name for d in run_dir.iterdir() if d.is_dir()]
