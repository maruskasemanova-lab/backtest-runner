import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.l2_data_manager import L2DataManager
from src.intrabar_frame_builder import IntrabarFrameBuilder

async def main():
    manager = L2DataManager()
    ticker = "MU"
    start_time = pd.Timestamp("2026-02-13 14:30:00", tz="UTC")
    end_time = pd.Timestamp("2026-02-13 14:55:59.999999", tz="UTC")
    
    print(f"Loading data for {ticker} from {start_time} to {end_time}")
    frames = manager.get_intrabar_frames(ticker=ticker, start_time=start_time, end_time=end_time)
    
    if frames is None or frames.empty:
        print("Frames are empty!")
        return

    print("Frames columns:", frames.columns.tolist())
    print("Frames length:", len(frames))
    print("has_book_coverage unique values:", frames["has_book_coverage"].unique())
    print("Sample of frames:")
    print(frames[["ts_sec", "has_book_coverage", "top_bid_px", "top_ask_px"]].head(10))

if __name__ == "__main__":
    asyncio.run(main())
