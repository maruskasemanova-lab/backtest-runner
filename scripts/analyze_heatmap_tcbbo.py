import argparse
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import polars as pl
except Exception:
    pl = None

from src.system_settings import SystemSettings

MARKET_TZ = ZoneInfo("America/New_York")


def get_heatmap_levels(
    db_path: Path, ticker: str, date_str: str, bin_size: float
) -> pd.DataFrame:
    """Fetch all heatmap levels by daily volume for a specific ticker/date."""
    conn = sqlite3.connect(str(db_path))
    query = """
    SELECT price_bin, day_volume, cumulative_volume
    FROM daily_price_heatmap_levels
    WHERE ticker = ? AND as_of_date = ? AND bin_size = ?
    ORDER BY day_volume DESC
    """
    df = pd.read_sql(
        query,
        conn,
        params=(ticker.upper(), date_str, float(bin_size)),
    )
    conn.close()
    return df


def find_l2_file(ticker: str, date_str: str) -> Path | None:
    search_dirs = [Path("data/l2")]
    try:
        settings = SystemSettings()
        for d in settings.get_l2_dirs(existing_only=True):
            if Path(d) not in search_dirs:
                search_dirs.append(Path(d))
    except Exception:
        pass

    pattern = f"{ticker.upper()}_{date_str}_{date_str}.parquet"
    for d in search_dirs:
        p = d / pattern
        if p.exists():
            return p

    for d in search_dirs:
        for p in d.glob(f"{ticker.upper()}_*{date_str}*.parquet"):
            return p

    return None


def analyze_touches_fast(df_pl: pl.DataFrame, levels: list[float], band: float = 0.03) -> pd.DataFrame:
    """Optimized touch event extraction using Polars and Numpy."""
    
    # Pre-calculate mid price
    df = df_pl.with_columns([
        ((pl.col("bid_px_00") + pl.col("ask_px_00")) / 2.0).alias("mid_price")
    ])
    
    # Classify L2 event trade trades (Lee-Ready approximate)
    df = df.with_columns([
        pl.when(pl.col("price") >= pl.col("ask_px_00")).then(pl.lit("buy"))
        .when(pl.col("price") <= pl.col("bid_px_00")).then(pl.lit("sell"))
        .when(pl.col("price") > pl.col("mid_price")).then(pl.lit("buy"))
        .when(pl.col("price") < pl.col("mid_price")).then(pl.lit("sell"))
        .otherwise(pl.lit("neutral")).alias("trade_side")
    ])
    
    df = df.with_columns([
        pl.when(pl.col("trade_side") == "buy").then(1)
        .when(pl.col("trade_side") == "sell").then(-1)
        .otherwise(0).alias("sentiment_sign"),
        
        pl.when(pl.col("trade_side") == "neutral").then(1).otherwise(0).alias("is_mid_trade"),
        pl.when(pl.col("price") <= pl.col("bid_px_00")).then(1).otherwise(0).alias("is_bid_trade"),
        pl.when(pl.col("price") >= pl.col("ask_px_00")).then(1).otherwise(0).alias("is_ask_trade"),
    ])
    
    df = df.with_columns([
        (pl.col("size") * pl.col("sentiment_sign")).alias("signed_flow")
    ])
    
    pdf = df.to_pandas()
    pdf["ts_event"] = pd.to_datetime(pdf["ts_event"]).dt.tz_convert("UTC" if pdf["ts_event"].dt.tz is None else pdf["ts_event"].dt.tz)
    
    all_events = []
    
    ts_array = pdf["ts_event"].values
    mid_array = pdf["mid_price"].values
    bid_px_array = pdf["bid_px_00"].values
    ask_px_array = pdf["ask_px_00"].values
    bid_sz_array = pdf["bid_sz_00"].values
    ask_sz_array = pdf["ask_sz_00"].values
    signed_flow_array = pdf["signed_flow"].values
    size_array = pdf["size"].values
    is_mid_array = pdf["is_mid_trade"].values
    
    n_rows = len(pdf)
    
    for lvl in levels:
        
        in_band = (mid_array >= (lvl - band)) & (mid_array <= (lvl + band))
        band_changed = np.concatenate(([in_band[0]], in_band[1:] != in_band[:-1]))
        enters = np.where(band_changed & in_band)[0]
        
        last_exit_idx = -1
        
        for e_idx in enters:
            if e_idx <= last_exit_idx:
                continue
                
            t0 = ts_array[e_idx]
            
            # Find exit
            t1_limit = t0 + np.timedelta64(30, 's')
            
            exit_idx = e_idx
            while exit_idx < n_rows:
                if ts_array[exit_idx] > t1_limit:
                    break
                if mid_array[exit_idx] < (lvl - band) or mid_array[exit_idx] > (lvl + band):
                    break
                exit_idx += 1
                
            if exit_idx >= n_rows:
                exit_idx = n_rows - 1
                
            t1 = ts_array[exit_idx]
            last_exit_idx = exit_idx
            
            pre_start_ts = t0 - np.timedelta64(3, 's')
            post_end_ts = t1 + np.timedelta64(3, 's')
            lookahead_ts = t1 + np.timedelta64(30, 's')
            
            pre_start_idx = np.searchsorted(ts_array, pre_start_ts)
            post_end_idx = np.searchsorted(ts_array, post_end_ts, side='right')
            lookahead_end_idx = np.searchsorted(ts_array, lookahead_ts, side='right')
            
            if exit_idx > e_idx:
                event_asks = ask_px_array[e_idx:exit_idx]
                event_bids = bid_px_array[e_idx:exit_idx]
                avg_spread = np.nanmean(event_asks - event_bids) / 0.01
                
                ev_sizes = size_array[e_idx:exit_idx]
                ev_sf = signed_flow_array[e_idx:exit_idx]
                trade_mask = ev_sizes > 0
                sf_event = np.sum(ev_sf[trade_mask])
                buy_flow = np.sum(ev_sf[trade_mask & (ev_sf > 0)])
                sell_flow = np.sum(ev_sf[trade_mask & (ev_sf < 0)])
                
                mid_prints_pct = np.mean(is_mid_array[e_idx:exit_idx][trade_mask]) if np.sum(trade_mask) > 0 else 0.0
            else:
                avg_spread = np.nan
                sf_event = 0.0
                buy_flow = 0.0
                sell_flow = 0.0
                mid_prints_pct = np.nan
                
            if pre_start_idx < e_idx:
                p_bid_sz = bid_sz_array[pre_start_idx:e_idx]
                p_ask_sz = ask_sz_array[pre_start_idx:e_idx]
                denom = p_bid_sz + p_ask_sz + 1e-9
                avg_q_imb_pre = np.mean((p_bid_sz - p_ask_sz) / denom)
                
                p_sizes = size_array[pre_start_idx:e_idx]
                p_sf = signed_flow_array[pre_start_idx:e_idx]
                t_mask = p_sizes > 0
                sf_pre = np.sum(p_sf[t_mask])
                buy_flow_pre = np.sum(p_sf[t_mask & (p_sf > 0)])
                sell_flow_pre = np.sum(p_sf[t_mask & (p_sf < 0)])
                
                approach_start = mid_array[pre_start_idx]
                is_support = approach_start >= lvl
                direction = "support" if is_support else "resistance"
            else:
                avg_q_imb_pre = 0.0
                sf_pre = 0.0
                buy_flow_pre = 0.0
                sell_flow_pre = 0.0
                is_support = True
                direction = "support"
                approach_start = lvl
                
            if e_idx < post_end_idx:
                po_bid_sz = bid_sz_array[e_idx:post_end_idx]
                po_ask_sz = ask_sz_array[e_idx:post_end_idx]
                denom = po_bid_sz + po_ask_sz + 1e-9
                avg_q_imb_post = np.mean((po_bid_sz - po_ask_sz) / denom)
            else:
                avg_q_imb_post = 0.0
                
            # MFE, MAE, and Path Constrained Bounce
            mfe_ticks = 0.0
            mae_ticks = 0.0
            is_bounce = False
            is_stop = False
            is_no_event = False
            exit_p = mid_array[exit_idx]
            
            if exit_idx < lookahead_end_idx:
                look_mids = mid_array[exit_idx:lookahead_end_idx]
                
                if len(look_mids) > 0:
                    if is_support:
                        diffs = look_mids - exit_p
                        mfe_ticks = np.max(diffs) / 0.01
                        mae_ticks = np.min(diffs) / 0.01
                        
                        stop_hits = np.where(diffs <= -0.03)[0] # -3 ticks MAE
                        tp_hits = np.where(diffs >= 0.20)[0]   # +20 ticks MFE
                        
                    else:
                        diffs = exit_p - look_mids
                        mfe_ticks = np.max(diffs) / 0.01
                        mae_ticks = np.min(diffs) / 0.01
                        
                        stop_hits = np.where(diffs <= -0.03)[0]
                        tp_hits = np.where(diffs >= 0.20)[0]
                        
                    first_stop = stop_hits[0] if len(stop_hits) > 0 else 999999
                    first_tp = tp_hits[0] if len(tp_hits) > 0 else 999999
                    
                    if first_tp < first_stop and first_tp != 999999:
                        is_bounce = True
                    elif first_stop < first_tp and first_stop != 999999:
                        is_stop = True
                    else:
                        is_no_event = True
                        
            # Opposing Pressure & Impact
            if is_support:
                lowest_p = np.min(mid_array[pre_start_idx:exit_idx+1]) if exit_idx >= pre_start_idx else approach_start
                impact_ticks = max(0.0, (approach_start - lowest_p) / 0.01)
                opposing_flow = abs(sell_flow_pre + sell_flow)
            else:
                highest_p = np.max(mid_array[pre_start_idx:exit_idx+1]) if exit_idx >= pre_start_idx else approach_start
                impact_ticks = max(0.0, (highest_p - approach_start) / 0.01)
                opposing_flow = abs(buy_flow_pre + buy_flow)
                        
            all_events.append({
                "level": lvl,
                "t0": pd.Timestamp(t0),
                "duration_s": (t1 - t0) / np.timedelta64(1, 's'),
                "direction": direction,
                "spread_ticks": avg_spread,
                "q_imb_pre": avg_q_imb_pre,
                "q_imb_post": avg_q_imb_post,
                "signed_flow_pre": sf_pre,
                "signed_flow_event": sf_event,
                "mfe_ticks": mfe_ticks,
                "mae_ticks": mae_ticks,
                "is_bounce": is_bounce,
                "is_stop": is_stop,
                "is_no_event": is_no_event,
                "opposing_flow": opposing_flow,
                "impact_ticks": impact_ticks,
                "mid_prints_pct": mid_prints_pct,
            })
            
    return all_events


def analyze_heatmap_tcbbo(
    db_path: Path, 
    ticker: str, 
    date_str: str, 
    bin_size: float = 0.5,
    max_spread: float = 20.0,
):
    print(f"--- Analyzing Heatmap L2 Info for {ticker} on {date_str} ---")
    
    print("\n1. Loading Heatmap Levels...")
    t0 = time.time()
    all_levels_df = get_heatmap_levels(db_path, ticker, date_str, bin_size)
    if all_levels_df.empty:
        print(f"  [!] No heatmap levels found for {ticker} on {date_str} (bin_size={bin_size}).")
        return
        
    print(f"  Found {len(all_levels_df)} total levels.")
    
    print("\n2. Finding L2 Data...")
    l2_file = find_l2_file(ticker, date_str)
    if not l2_file:
        print(f"  [!] No L2 parquet file found for {ticker} on {date_str}.")
        return
    print(f"  Loading {l2_file.name} (Polars fast loading)...")
    
    df_l2_pl = pl.scan_parquet(str(l2_file))
    cols = ["ts_event", "price", "size", "bid_px_00", "ask_px_00", "bid_sz_00", "ask_sz_00"]
    
    # Filter out missing BBO, negative prices, and anomalous wide spreads (> $5)
    df_l2_pl = df_l2_pl.select(cols).drop_nulls(subset=["bid_px_00", "ask_px_00"])
    df_l2_pl = df_l2_pl.filter(
        (pl.col("bid_px_00") > 0) & 
        (pl.col("ask_px_00") > pl.col("bid_px_00")) &
        ((pl.col("ask_px_00") - pl.col("bid_px_00")) < 5.0)
    )
    
    df_l2_pl = df_l2_pl.with_columns(
        pl.col("ts_event").cast(pl.Datetime("us", "UTC")).dt.convert_time_zone("America/New_York").alias("ts_et")
    )
    df_l2_pl = df_l2_pl.filter(
        (pl.col("ts_et").dt.hour() >= 9) & 
        ((pl.col("ts_et").dt.hour() > 9) | (pl.col("ts_et").dt.minute() >= 30)) &
        (pl.col("ts_et").dt.hour() < 16)
    )
    df_l2_pl = df_l2_pl.sort("ts_event")
    
    print("  Evaluating Polars pipeline...")
    df_l2 = df_l2_pl.collect()
    print(f"  Loaded {df_l2.height:,} cleaned regular session L2 events. Fast filter took {time.time()-t0:.1f}s.")
    
    print("\n3. Extracting Touch Events...")
    t1 = time.time()
    
    levels_to_check = all_levels_df["price_bin"].tolist()
    all_events = analyze_touches_fast(df_l2, levels_to_check, band=0.03)
    
    if not all_events:
        print("  No touch events found.")
        return
        
    events_df = pd.DataFrame(all_events)
    print(f"  Extracted {len(events_df)} total touch events across {len(levels_to_check)} levels. Took {time.time()-t1:.1f}s.")
    
    # SPREAD FILTER: Ensures Apples-to-Apples Comparison
    pre_filter_len = len(events_df)
    events_df = events_df[events_df["spread_ticks"] <= max_spread].copy()
    print(f"  Filtered out {pre_filter_len - len(events_df)} events with spread > {max_spread} ticks.")
    
    # Count touches per level and filter
    touches_per_lvl = events_df.groupby("level").size().reset_index(name="touch_count")
    valid_levels = touches_per_lvl[touches_per_lvl["touch_count"] >= 5]["level"]
    events_df = events_df[events_df["level"].isin(valid_levels)].copy()
    
    if events_df.empty:
        print("  No levels had at least 5 clean touches.")
        return
        
    print(f"  {len(valid_levels)} levels had >= 5 clean touches ({len(events_df)} valid events).")
    
    # Merge heatmap stats for valid levels
    events_df = events_df.merge(all_levels_df[["price_bin", "day_volume"]], left_on="level", right_on="price_bin")
    
    # Define HIGH/LOW heatmap using percentiles over VALID levels only
    valid_heatmap_volumes = all_levels_df[all_levels_df["price_bin"].isin(valid_levels)]["day_volume"]
    p80 = valid_heatmap_volumes.quantile(0.80)
    p20 = valid_heatmap_volumes.quantile(0.20)
    
    def get_heatmap_class(vol):
        if vol >= p80:
            return "HIGH"
        elif vol <= p20:
            return "LOW"
        return "MID"
        
    events_df["heatmap_class"] = events_df["day_volume"].apply(get_heatmap_class)
    
    print("\n4. Segmenting by Direction, Heatmap Percentiles, and Opposing Pressure...")
    
    for direction in ["support", "resistance"]:
        print(f"\n--- {direction.upper()} TOUCHES ---")
        dir_df = events_df[events_df["direction"] == direction].copy()
        
        if dir_df.empty:
            print("  No events.")
            continue
            
        # Segregate by "Opposing Pressure" (e.g. at support, how many sell orders actually executed)
        median_pres = dir_df["opposing_flow"].median()
        dir_df["is_high_pressure"] = dir_df["opposing_flow"] >= median_pres
        
        grouped = dir_df.groupby(["heatmap_class", "is_high_pressure"]).agg(
            event_count=("level", "count"),
            bounce_prob=("is_bounce", "mean"),
            stop_prob=("is_stop", "mean"),
            none_prob=("is_no_event", "mean"),
            avg_impact=("impact_ticks", "mean"),
            avg_opp_flow=("opposing_flow", "mean"),
            avg_spread=("spread_ticks", "mean"),
        ).reset_index()
        
        for h_class in ["HIGH", "LOW"]:
            for is_high_pres in [True, False]:
                subset = grouped[(grouped["heatmap_class"] == h_class) & (grouped["is_high_pressure"] == is_high_pres)]
                if subset.empty:
                    continue
                row = subset.iloc[0]
                
                pres_label = "STRONG" if is_high_pres else "WEAK  "
                
                print(f"  Heatmap={h_class} | OpposingFlow={pres_label} -> "
                      f"Events: {int(row['event_count']):3d} | "
                      f"Bounce/Stop/None: {row['bounce_prob']*100:4.1f}%/{row['stop_prob']*100:4.1f}%/{row['none_prob']*100:4.1f}% | "
                      f"Impact: {row['avg_impact']:4.1f}t | Spread: {row['avg_spread']:4.1f}t")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze TCBBO L2 traits at Heatmap levels.")
    parser.add_argument("--db-path", default="data/saas_state.db", help="SQLite DB path")
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g. MU)")
    parser.add_argument("--date", required=True, help="Trading date (YYYY-MM-DD)")
    parser.add_argument("--bin-size", type=float, default=0.5, help="Heatmap bin size (default: 0.5)")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
        
    analyze_heatmap_tcbbo(db_path, args.ticker, args.date, args.bin_size, max_spread=20.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
