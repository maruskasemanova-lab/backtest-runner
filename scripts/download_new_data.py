"""
Download new OHLCV data from Databento to extend existing dataset.
"""
import databento as db
import pandas as pd
import os
from datetime import datetime

# Configuration
API_KEY = "db-3hQkGYx4SRQ8TYpVYskMfmT5q8HKE"
DATA_DIR = "/Users/hotovo/.gemini/antigravity/scratch/ibkr-l2-script/databento_data"
TICKERS = ["NVDA", "TSLA", "AAPL", "AMD", "GOOGL", "META", "MSFT", "MU"]

# Date range for new data
START_DATE = "2026-01-29"
END_DATE = "2026-02-03"

def download_ticker_data(client, ticker, start_date, end_date):
    """Download OHLCV 1-minute data for a ticker."""
    print(f"Downloading {ticker} from {start_date} to {end_date}...")
    
    try:
        data = client.timeseries.get_range(
            dataset="XNAS.ITCH",
            symbols=[ticker],
            schema="ohlcv-1m",
            start=start_date,
            end=end_date,
        )
        
        # Convert to DataFrame
        df = data.to_df()
        
        if len(df) == 0:
            print(f"  No data returned for {ticker}")
            return None
            
        print(f"  Downloaded {len(df)} bars")
        return df
        
    except Exception as e:
        print(f"  Error downloading {ticker}: {e}")
        return None

def merge_with_existing(ticker, new_df, data_dir):
    """Merge new data with existing CSV files."""
    # Find existing file
    existing_files = [f for f in os.listdir(data_dir) 
                      if f.startswith(f"{ticker}_ohlcv-1m_") and f.endswith(".csv")]
    
    if not existing_files:
        # Create new file
        output_file = os.path.join(data_dir, f"{ticker}_ohlcv-1m_{START_DATE}_{END_DATE}.csv")
        new_df.to_csv(output_file)
        print(f"  Created new file: {output_file}")
        return
    
    # Find the main file (longest date range)
    main_file = None
    for f in existing_files:
        if "2025-08-01" in f:  # Main historical file
            main_file = f
            break
    
    if main_file is None:
        main_file = existing_files[0]
    
    main_path = os.path.join(data_dir, main_file)
    
    # Load existing
    existing_df = pd.read_csv(main_path)
    print(f"  Existing data: {len(existing_df)} bars")
    
    # Reset index if needed
    if 'ts_event' in new_df.columns:
        new_df = new_df.reset_index()
    
    # Merge
    combined = pd.concat([existing_df, new_df], ignore_index=True)
    
    # Remove duplicates based on timestamp
    if 'ts_event' in combined.columns:
        combined = combined.drop_duplicates(subset=['ts_event'], keep='last')
    
    combined = combined.sort_values(by=['ts_event'] if 'ts_event' in combined.columns else combined.columns[0])
    
    # Determine new date range
    # Parse dates from filename and extend
    parts = main_file.replace(".csv", "").split("_")
    old_start = parts[2]
    new_end = END_DATE
    
    new_filename = f"{ticker}_ohlcv-1m_{old_start}_{new_end}.csv"
    new_path = os.path.join(data_dir, new_filename)
    
    combined.to_csv(new_path, index=False)
    print(f"  Merged data: {len(combined)} bars -> {new_filename}")
    
    # Optionally remove old file if name changed
    if new_filename != main_file:
        print(f"  Note: Old file {main_file} can be removed manually")

def main():
    print("=" * 60)
    print(f"Databento Data Download")
    print(f"Tickers: {', '.join(TICKERS)}")
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print("=" * 60)
    
    # Initialize client
    client = db.Historical(key=API_KEY)
    
    for ticker in TICKERS:
        print(f"\n--- {ticker} ---")
        new_df = download_ticker_data(client, ticker, START_DATE, END_DATE)
        
        if new_df is not None:
            merge_with_existing(ticker, new_df, DATA_DIR)
    
    print("\n" + "=" * 60)
    print("Download complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
