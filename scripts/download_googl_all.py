import os
import databento as db
from datetime import datetime, timedelta
from pathlib import Path

API_KEY = "db-eLpabYrDC7jnS7XukeVkB4FWRTpsy"
TICKER = "GOOGL"

DATA_ROOT = Path("/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/data")
L2_DIR = DATA_ROOT / "l2"
TCBBO_DIR = DATA_ROOT # TCBBO files are usually dropped in the data root based on find_tcbbo_files
L2_DIR.mkdir(exist_ok=True)

DATES = ["2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24"]

def download_data():
    client = db.Historical(API_KEY)
    
    for day in DATES:
        dt = datetime.strptime(day, "%Y-%m-%d")
        end_dt = dt + timedelta(days=1)
        end_str = end_dt.strftime("%Y-%m-%d")
        
        print(f"\n--- Processing {day} for {TICKER} ---")
        
        # 1. OHLCV (CSV)
        ohlcv_path = DATA_ROOT / f"{TICKER}_ohlcv-1m_{day}_{day}.csv"
        if not ohlcv_path.exists():
            print(f"Downloading OHLCV...")
            try:
                data = client.timeseries.get_range(
                    dataset="XNAS.ITCH",
                    symbols=[TICKER],
                    schema="ohlcv-1m",
                    start=day,
                    end=end_str,
                    stype_in="raw_symbol"
                )
                df = data.to_df()
                if not df.empty:
                    df.to_csv(str(ohlcv_path))
                    print(f"  OK: {len(df)} rows")
                else:
                    print("  WARN: empty response")
            except Exception as e:
                print(f"  ERR: {e}")
        else:
            print(f"OHLCV already exists: {ohlcv_path.name}")
            
        # 2. L2 mbp-10 (Parquet)
        l2_path = L2_DIR / f"{TICKER}_{day}_{day}.parquet"
        if not l2_path.exists():
            print(f"Downloading L2...")
            try:
                data = client.timeseries.get_range(
                    dataset="XNAS.ITCH",
                    symbols=[TICKER],
                    schema="mbp-10",
                    start=day,
                    end=end_str,
                    stype_in="raw_symbol"
                )
                df = data.to_df()
                if not df.empty:
                    df.to_parquet(str(l2_path))
                    print(f"  OK: {len(df)} rows")
                else:
                    print("  WARN: empty response")
            except Exception as e:
                print(f"  ERR: {e}")
        else:
            print(f"L2 already exists: {l2_path.name}")
            
        # 3. TCBBO (Parquet)
        # Expected format: GOOGL_OPRA_tcbbo_20260223_20260223.parquet
        day_nodash = day.replace("-", "")
        tcbbo_path = TCBBO_DIR / f"{TICKER}_OPRA_tcbbo_{day_nodash}_{day_nodash}.parquet"
        if not tcbbo_path.exists():
            print(f"Downloading TCBBO...")
            try:
                data = client.timeseries.get_range(
                    dataset="OPRA.PILLAR",
                    symbols=[f"{TICKER}.OPT"],
                    schema="tcbbo",
                    start=day,
                    end=end_str,
                    stype_in="parent"
                )
                df = data.to_df()
                if not df.empty:
                    df.to_parquet(str(tcbbo_path))
                    print(f"  OK: {len(df)} rows")
                else:
                    print("  WARN: empty response")
            except Exception as e:
                print(f"  ERR: {e}")
        else:
            print(f"TCBBO already exists: {tcbbo_path.name}")

if __name__ == "__main__":
    download_data()
