import sys
import os
import pandas as pd
from datetime import datetime, timezone

# Add parent directory to path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.l2_data_manager import L2DataManager

if __name__ == "__main__":
    ticker = "MU"
    date_str = "2026-02-03"
    # Select a time range known to have volume (e.g., market open)
    start_time = f"{date_str} 09:30:00"
    end_time = f"{date_str} 09:31:00"

    start_dt = datetime.fromisoformat(start_time).replace(tzinfo=timezone.utc)
    end_dt = datetime.fromisoformat(end_time).replace(tzinfo=timezone.utc)

    print(f"--- Debugging L2 Footprint for {ticker} ---")
    print(f"Range: {start_dt} to {end_dt}")

    manager = L2DataManager()
    # Force load checks files automatically in load_data implementation I added/modified?
    # Actually load_data takes dates strings.
    manager.load_data(ticker, "2026-02-03", "2026-02-05")

    if ticker not in manager.data:
        print("Failed to load data into manager.")
    else:
        df = manager.data[ticker]
        print(f"Total rows in dataframe: {len(df)}")

        # Check rows in time range
        mask = (df.index >= start_dt) & (df.index <= end_dt)
        chunk = df[mask]
        print(f"Rows in target minute: {len(chunk)}")

        if chunk.empty:
            print("No data in target range.")
            print("Head of dataframe index:", df.index[:5])
        else:
            print("Columns:", chunk.columns.tolist())

            # specialized debug for side/action
            if "action" in chunk.columns:
                print("Unique actions:", chunk["action"].unique())
                # Check count of trades
                trades = chunk[chunk["action"] == "T"]
                print(f"Trade rows (action='T'): {len(trades)}")

                # Check volume by side
                if "side" in trades.columns:
                    n_trades = trades[trades["side"] == "N"]
                    a_trades = trades[trades["side"] == "A"]
                    b_trades = trades[trades["side"] == "B"]
                    print(
                        f"Trades by side: N={len(n_trades)}, A={len(a_trades)}, B={len(b_trades)}"
                    )
                    print(
                        f"Volume by side: N={n_trades['size'].sum()}, A={a_trades['size'].sum()}, B={b_trades['size'].sum()}"
                    )
            else:
                print("No 'action' column found.")

            if "side" in chunk.columns:
                print("Unique sides:", chunk["side"].unique())

            # Run the actual aggregation
            bars = manager.get_footprint_bars(ticker, start_dt, end_dt)
            print(f"Generated {len(bars)} footprint bars.")

            if bars:
                print("Sample Bar 0:")
                print(bars[0])
                print("Levels sample:", list(bars[0]["levels"].items())[:3])
            else:
                print("No bars generated.")
