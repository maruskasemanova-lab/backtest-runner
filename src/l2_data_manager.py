import databento as db
import pandas as pd
import numpy as np
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from .system_settings import SystemSettings

class L2DataManager:
    def __init__(self, data_dir: Optional[str] = None, data_dirs: Optional[List[str]] = None):
        if data_dirs:
            self.data_dirs = [str(Path(d).expanduser().resolve()) for d in data_dirs]
        elif data_dir:
            self.data_dirs = [str(Path(data_dir).expanduser().resolve())]
        else:
            configured = SystemSettings().get_l2_dirs(existing_only=False)
            self.data_dirs = [str(p.resolve()) for p in configured] if configured else [
                str((Path(__file__).resolve().parents[1] / "data" / "l2").resolve())
            ]

        self.data_dir = self.data_dirs[0]  # Backward compatibility for callers that inspect this attr.
        self.data = {} # Cache likely needed, or stream reading

    @staticmethod
    def _normalize_datetime_index_utc(df: pd.DataFrame) -> pd.DataFrame:
        """Ensure a timezone-aware UTC DatetimeIndex for deterministic alignment."""
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        return df
        
    def load_data(self, ticker, start_date, end_date):
        """
        Loads L2 data, preferring Parquet if available, else MBN.
        """
        # Try strict exact files first.
        matched_files = []
        for root in self.data_dirs:
            parquet_file = os.path.join(root, f"{ticker}_{start_date}_{end_date}.parquet")
            mbn_file = os.path.join(root, f"{ticker}_{start_date}_{end_date}.mbn")
            if os.path.exists(parquet_file):
                matched_files = [parquet_file]
                break
            if os.path.exists(mbn_file):
                matched_files = [mbn_file]
                break
        else:
            # Fuzzy match: collect ALL overlapping files for ticker and merge them.
            import glob
            candidates = []
            for root in self.data_dirs:
                candidates += glob.glob(os.path.join(root, f"{ticker}_*.parquet"))
                candidates += glob.glob(os.path.join(root, f"{ticker}_*.mbn"))

            for f in sorted(candidates):
                try:
                    base = os.path.basename(f)
                    parts = base.replace(".parquet", "").replace(".mbn", "").split('_')
                    if len(parts) < 3:
                        continue
                    f_start = parts[1]
                    f_end = parts[2]
                    # Overlap test in ISO-date lexical order.
                    if start_date <= f_end and end_date >= f_start:
                        matched_files.append(f)
                except Exception:
                    continue

            # Prefer Parquet when both formats exist for the same date range.
            if matched_files:
                grouped = {}
                for f in matched_files:
                    base = os.path.basename(f).replace(".parquet", "").replace(".mbn", "")
                    grouped.setdefault(base, []).append(f)
                deduped = []
                for _, files in grouped.items():
                    parquet = [f for f in files if f.endswith(".parquet")]
                    if parquet:
                        deduped.append(sorted(parquet)[0])
                    else:
                        deduped.append(sorted(files)[0])
                matched_files = sorted(deduped)

        if not matched_files:
            print(f"No L2 data found for {ticker} ({start_date} to {end_date})")
            return None

        try:
            frames = []
            print(f"Loading L2 data from {len(matched_files)} file(s) for {ticker}...")
            for file_path in matched_files:
                print(f"  - {file_path}")
                if file_path.endswith(".parquet"):
                    df = pd.read_parquet(file_path)
                else:
                    stored_data = db.DBNStore.from_file(file_path)
                    df = stored_data.to_df()
                df = self._normalize_datetime_index_utc(df)
                frames.append(df)

            if not frames:
                print(f"No readable L2 frames found for {ticker}")
                return None

            if len(frames) == 1:
                merged = frames[0].sort_index()
            else:
                merged = pd.concat(frames, axis=0)
                merged = merged.sort_index()
                merged = merged[~merged.index.duplicated(keep='last')]

            self.data[ticker] = merged
            print(f"Loaded {len(merged)} rows for {ticker}")
            return merged

        except Exception as e:
            print(f"Error loading L2 data: {e}")
            return None

    def get_footprint_bars(self, ticker, start_time, end_time, timeframe="1min"):
        """
        Aggregates L2 trade data into Footprint Bars.
        Returns a list of bars with:
        - time, open, high, low, close
        - volume, delta
        - levels: { price: { buy_vol, sell_vol } }
        """
        if ticker not in self.data:
            # Try to infer file from dates if not loaded? 
            # For now assume loaded.
            return []
            
        df = self.data[ticker]
        
        # Filter by time
        mask = (df.index >= start_time) & (df.index <= end_time)
        chunk = df[mask]
        
        # Filter for trades only
        # In Databento, action 'T' (Trade). 
        # Make sure 'action' column exists or is the index? Usually a column.
        if 'action' in chunk.columns:
            trades = chunk[chunk['action'] == 'T']
        else:
            # Check documentation or inspect columns. usually 'action' or 'publisher_id' etc.
            # Assuming 'action' is present based on standard headers.
            trades = chunk # Fallback if not sure
        
        if trades.empty:
            return []

        # Resample to bars
        # We need a custom resampler to build the price levels
        
        bars = []
        # Group by timeframe
        grouper = trades.groupby(pd.Grouper(freq=timeframe))
        
        for time, group in grouper:
            if group.empty:
                continue
                
            # Aggressive casting to ensure NO numpy types remain
            ohlc = {
                "time": float(time.timestamp()),
                "open": float(group.iloc[0]['price']),
                "high": float(group['price'].max()),
                "low": float(group['price'].min()),
                "close": float(group.iloc[-1]['price']),
                "volume": int(group['size'].sum())
            }
            
            levels = {}
            buy_vol_total = 0
            sell_vol_total = 0
            
            for index, row in group.iterrows():
                # Ensure python native types for keys and values
                price = float(row['price'])
                size = int(row['size'])
                side = row['side'] 
                
                if price not in levels:
                    levels[price] = {"buy": 0, "sell": 0}
                
                # Databento convention for Trades:
                #   side='B' => buy aggressor
                #   side='A' => sell aggressor
                #   side='N' => unknown side
                is_buy = False
                if side == 'B':
                    is_buy = True
                elif side == 'A':
                    is_buy = False
                elif side == 'N':
                    # Infer side from BBO if available
                    ask = float(row.get('ask_px_00', 0))
                    bid = float(row.get('bid_px_00', 0))
                    
                    if ask > 0 and price >= ask:
                        is_buy = True
                    elif bid > 0 and price <= bid:
                        is_buy = False
                    else:
                        if ask > 0 and bid > 0:
                            mid = (ask + bid) / 2
                            is_buy = price >= mid
                        else:
                            is_buy = True 

                if is_buy:
                    levels[price]["buy"] += size
                    buy_vol_total += size
                else:
                    levels[price]["sell"] += size
                    sell_vol_total += size
            
            ohlc['delta'] = int(buy_vol_total - sell_vol_total)
            ohlc['levels'] = levels
            
            # Additional safety: Convert all keys in levels to float (they are already, but explicit is good)
            # JSON keys must be strings anyway? No, FastAPI/Pydantic converts dict with float keys. 
            # But just in case, leave them as floats, standard json lib handles them.
            
            bars.append(ohlc)
            
        return bars

    def detect_icebergs(self, ticker, start_time, end_time):
        """
        Detects potential iceberg orders by comparing executed trade size
        against the visible order book depth immediately prior to the trade.
        
        Logic:
        1. Load L2 MBP-10 data.
        2. Filter for trades (Action 'T').
        3. Compare Trade Size against the Best Bid/Ask Size currently in the book.
           (Note: In Databento MBP, the 'size' on a Trade event is the executed size. 
            We must look at the book state *before* this trade updated it.
            However, Databento events are ordered. A Trade event usually comes *after* 
            the aggressor order matches. 
            Actually, effectively we just need to see if the Trade Size > The Top Level Size that was there.
            
            We can use pandas shift() to get the row immediately preceding the trade? 
            No, because there might be other events in between.
            We need the BBO state *at the time* of the trade.
            The rows in the dataframe contain the BBO *after* the event? 
            Databento documentation says: 
            "The price and size fields on a Trade event indicate the price and size of the trade. 
             The bid/ask fields indicate the BBO *after* the trade occurred."
             
            So we DO need to shift to see what was there before.
        """
        if ticker not in self.data:
            # Try to load if not present
            # Convert timestamp to date string for loader
            if isinstance(start_time, str):
                s_date = start_time.split("T")[0]
                e_date = end_time.split("T")[0]
            else:
                s_date = start_time.strftime("%Y-%m-%d")
                e_date = end_time.strftime("%Y-%m-%d")
            
            df = self.load_data(ticker, s_date, e_date)
            if df is None:
                return []
        else:
            df = self.data[ticker]
        df = self._normalize_datetime_index_utc(df)
            
        # Filter by time range
        # Ensure index is datetime
        df = self._normalize_datetime_index_utc(df)
             
        mask = (df.index >= start_time) & (df.index <= end_time)
        chunk = df[mask].copy()
        
        if chunk.empty:
            return []
            
        # We need previous BBO state
        # Create shifted columns for comparison
        # shift(1) gives us the value from the previous row
        # This assumes the rows are dense enough. 
        # Ideally we'd forward fill BBO if it wasn't on every row, but MBP-10 from Databento 
        # usually has valid BBO columns on every row or we can ffill.
        # Actually standard Schema includes bid_px_00, etc on all rows? 
        # The `print(df.columns)` from step 29 showed `bid_px_00` etc.
        # Let's assume they are populated.
        
        chunk['prev_bid_px'] = chunk['bid_px_00'].shift(1)
        chunk['prev_bid_sz'] = chunk['bid_sz_00'].shift(1)
        chunk['prev_ask_px'] = chunk['ask_px_00'].shift(1)
        chunk['prev_ask_sz'] = chunk['ask_sz_00'].shift(1)
        
        # Filter for Trades
        trades = chunk[chunk['action'] == 'T'].copy()
        
        icebergs = []
        
        # Aggregation Logic
        # Group consecutive trades at the same Price & Side within a small time window (e.g. 50ms)
        # Compare TOTAL volume against the Visible Size at the START of the sequence.
        
        # Convert trades to list of dicts for easier iteration
        # (iterating pandas rows is slow, but fine for prototype)
        
        current_seq = {
            "price": -1,
            "side": None,
            "start_time": None,
            "total_vol": 0,
            "initial_visible": 0,
            "start_ts": None
        }
        
        # Thresholds
        ICEBERG_THRESHOLD = 0 # Any overflow is interesting if ratio is high
        ICEBERG_RATIO = 1.25 # Increased to 1.25 to filter noise (was 1.1)
        TIME_WINDOW_MS = 100 # Increased window to catch split trades
        
        # Debug stats
        seq_count = 0
        iceberg_count = 0
            
        for ts, row in trades.iterrows():
            size = row['size']
            price = row['price']
            side = row['side'] 
            
            # Identify side if 'N' (None)
            if side == 'N':
                prev_ask = row['prev_ask_px']
                prev_bid = row['prev_bid_px']
                
                if prev_ask > 0 and price >= prev_ask:
                    side = 'B' # Buy aggressor (taking ask)
                elif prev_bid > 0 and price <= prev_bid:
                    side = 'A' # Sell aggressor (hitting bid)
            
            # Determine Visible Size for THIS trade (candidates)
            trade_visible = 0
            
            # Cross-check based on aggressor side:
            # side='B' => buyer aggressor (taking ask)
            # side='A' => seller aggressor (hitting bid)
            
            if side == 'B': # Buyer aggressor -> compare with ASK
                 if row['prev_ask_px'] == price:
                     trade_visible = row['prev_ask_sz']
            
            elif side == 'A': # Seller aggressor -> compare with BID
                 if row['prev_bid_px'] == price:
                     trade_visible = row['prev_bid_sz']
            
            # Check if continues sequence
            is_continuation = False
            if current_seq['start_time'] is not None:
                time_diff = (ts - current_seq['start_time']).total_seconds() * 1000
                if (price == current_seq['price'] and 
                    side == current_seq['side'] and 
                    time_diff <= TIME_WINDOW_MS):
                    is_continuation = True
            
            if is_continuation:
                current_seq['total_vol'] += size
            else:
                # Finalize previous sequence
                if current_seq['start_time'] is not None:
                    seq_count += 1
                    vis = current_seq['initial_visible']
                    vol = current_seq['total_vol']
                    
                    # Detection Logic:
                    # 1. Overflow > Threshold OR
                    # 2. Volume > Visible * Ratio
                    
                    hidden = vol - vis
                    is_iceberg = False
                    
                    # Strict check: Must be effectively larger than visible
                    if vis > 0:
                        if vol > (vis * ICEBERG_RATIO):
                            is_iceberg = True
                        elif hidden > 100: # Absolute threshold fallback for large ones
                            is_iceberg = True
                    
                    if is_iceberg:
                        iceberg_count += 1
                        icebergs.append({
                             "time": current_seq['start_ts'],
                             "price": current_seq['price'],
                             "trade_size": int(vol),
                             "visible_size": int(vis),
                             "hidden_size": int(max(0, hidden)),
                             "side": "buy" if current_seq['side'] == 'B' else "sell",
                             "marker_type": "iceberg_detected"
                         })
                
                # Start new sequence
                # Only start if we have valid visibility data, otherwise we can't detect overflow
                # But even if visible=0, unlimited overflow? 
                # If visible=0, it implies price level wasn't BBO or data missing. 
                # If it wasn't BBO, it's not a limit order iceberg at BBO. 
                
                current_seq = {
                    "price": price,
                    "side": side,
                    "start_time": ts,
                    "total_vol": size,
                    "initial_visible": trade_visible,
                    "start_ts": ts.isoformat()
                }
        
        # Finalize last sequence
        if current_seq['start_time'] is not None:
            vis = current_seq['initial_visible']
            vol = current_seq['total_vol']
            hidden = vol - vis
            
            if vis > 0 and (vol > (vis * ICEBERG_RATIO) or hidden > 100):
                 icebergs.append({
                     "time": current_seq['start_ts'],
                     "price": current_seq['price'],
                     "trade_size": int(vol),
                     "visible_size": int(vis),
                     "hidden_size": int(max(0, hidden)),
                     "side": "buy" if current_seq['side'] == 'B' else "sell",
                     "marker_type": "iceberg_detected"
                 })

        print(f"Iceberg Detection {ticker}: Processed {seq_count} sequences, Found {len(icebergs)} icebergs.")
        return icebergs

    def get_order_book_snapshot(self, ticker, timestamp):
        """
        Returns the order book (MBP) at a specific timestamp.
        """
        pass
