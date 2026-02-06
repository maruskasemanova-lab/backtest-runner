import databento as db
import os

file_path = "/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data/l2/NVDA_2026-02-03_2026-02-05.mbn"

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
else:
    try:
        stored_data = db.DBNStore.from_file(file_path)
        print(f"File: {file_path}")
        print(f"Size: {os.path.getsize(file_path) / (1024*1024):.2f} MB")
        print(f"Schema: {stored_data.schema}")
        print(f"Start: {stored_data.start}")
        print(f"End: {stored_data.end}")
        # print(f"Symbol: {stored_data.sym_instruments}") # Attribute error
        
        # Read a few rows to confirm content
        df = stored_data.to_df()
        print(f"Total Rows: {len(df)}")
        print("\nFirst 5 rows:")
        print(df.head())
        print("\nColumns:")
        print(df.columns)
        
        # Check unique symbols if possible
        if 'symbol' in df.columns:
            print(f"Symbols: {df['symbol'].unique()}")
        
    except Exception as e:
        print(f"Error reading file: {e}")
