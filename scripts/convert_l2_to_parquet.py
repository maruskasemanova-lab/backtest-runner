import databento as db
import pandas as pd
import os
import glob

DATA_DIR = "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data/l2"


def convert_to_parquet():
    files = glob.glob(os.path.join(DATA_DIR, "*.mbn"))

    for mbn_file in files:
        parquet_file = mbn_file.replace(".mbn", ".parquet")

        # Skip if parquet exists and is newer
        if os.path.exists(parquet_file):
            if os.path.getmtime(parquet_file) > os.path.getmtime(mbn_file):
                print(f"Skipping {mbn_file} (Parquet exists and is newer)")
                continue

        print(f"Converting {mbn_file} to Parquet...")
        try:
            stored_data = db.DBNStore.from_file(mbn_file)

            # We iterate in chunks to avoid memory issues if file is huge
            # But DBNStore to_df() loads all into memory.
            # DBNStore isn't an iterator itself easily without client.
            # But we can use `db.DBNStore.from_file` then `to_df`?
            # If it's too big, we might need a different approach.
            # For 1 day of MU, it should fit in memory (couple hundred MB).

            df = stored_data.to_df()

            # Ensure index is standard column if needed, or keep as index?
            # Parquet handles datetime index well.

            df.to_parquet(parquet_file, compression="snappy")
            print(f"Saved {parquet_file}")

        except Exception as e:
            print(f"Error converting {mbn_file}: {e}")


if __name__ == "__main__":
    convert_to_parquet()
