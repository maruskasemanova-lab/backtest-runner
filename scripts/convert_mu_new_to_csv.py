import databento as db
import pandas as pd
import os

INPUT_FILE = "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data/l2/MU_2026-02-04_2026-02-05.parquet"
OUTPUT_DIR = "/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/databento_data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "MU_ohlcv-1m_2026-02-04_2026-02-05.csv")

if __name__ == "__main__":
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Input file not found at {INPUT_FILE}")
    else:
        print(f"Loading {INPUT_FILE}...")
        try:
            # Load Parquet directly
            df = pd.read_parquet(INPUT_FILE)

            print(f"Loaded {len(df)} rows. Columns: {df.columns.tolist()}")

            # Ensure timestamp index
            if not isinstance(df.index, pd.DatetimeIndex):
                # Try to find timestamp column if index is not it
                if "ts_event" in df.columns:
                    df["ts_event"] = pd.to_datetime(df["ts_event"])
                    df = df.set_index("ts_event")
                elif "ts_recv" in df.columns:
                    df["ts_recv"] = pd.to_datetime(df["ts_recv"])
                    df = df.set_index("ts_recv")

            # Filter for trades
            # Databento: action 'T' is Trade.
            # Check if 'action' column exists
            if "action" in df.columns:
                trades = df[df["action"] == "T"].copy()
            else:
                # Maybe it's 'T' in 'side' or 'flags'?
                # Actually, standard MBP-10 schema has 'action'.
                # If strictly trades schema, it's always trades.
                # But MBP-10 has book updates too.
                print(
                    "Warning: 'action' column not found, assuming all rows are valid updates (might be wrong for volume)."
                )
                trades = df.copy()

            print(f"Filtered to {len(trades)} trade rows.")

            # Resample to 1-minute OHLCV
            # price is the trade price
            # size is volume

            # Check price and size columns
            if "price" not in trades.columns:
                # Databento prices are fixed precision int64 usually in DBN, but to_df() might convert float?
                # If it's 'px', rename.
                pass

            # Resample
            ohlcv = trades.resample("1min").agg(
                {
                    "price": ["first", "max", "min", "last"],
                    "size": "sum",
                }
            )

            # Flatten columns
            ohlcv.columns = ["open", "high", "low", "close", "volume"]

            # Add timestamp column from index
            ohlcv = ohlcv.reset_index()
            ohlcv = ohlcv.rename(
                columns={"index": "timestamp", "ts_event": "timestamp"}
            )
            # (index name might vary)

            # Drop empty intervals (no trades)
            ohlcv = ohlcv[ohlcv["volume"] > 0]

            # Save
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            ohlcv.to_csv(OUTPUT_FILE, index=False)

            print(f"Saved {len(ohlcv)} bars to {OUTPUT_FILE}")
            print("Preview:")
            print(ohlcv.head())

        except Exception as e:
            print(f"Conversion failed: {e}")
            import traceback

            traceback.print_exc()
