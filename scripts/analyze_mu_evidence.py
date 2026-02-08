#!/usr/bin/env python3
"""
Analyze MU data to understand what evidence sources fire and when.
Standalone - minimal imports, directly loads CSV and computes signals.
"""
import sys
import os
import math

# Set up paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MRD_ROOT = os.path.join(os.path.dirname(PROJECT_ROOT), 'market_regime_detection')
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, MRD_ROOT)

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, time, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo

# Import from market_regime_detection
from src.feature_store import FeatureStore, FeatureVector
from src.adaptive_regime import AdaptiveRegimeDetector, RegimeState
from src.strategies.candlestick_patterns import CandlestickPatternDetector, PatternDirection

DATA_FILE = os.path.join(PROJECT_ROOT, "data/MU_ohlcv-1m_2026-01-20_2026-02-06.csv")
ET = ZoneInfo("America/New_York")


def load_data():
    """Load MU OHLCV CSV."""
    df = pd.read_csv(DATA_FILE)
    # Parse timestamps
    if 'ts_recv' in df.columns:
        df['timestamp'] = pd.to_datetime(df['ts_recv'], utc=True)
    elif 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    else:
        raise ValueError(f"No timestamp column found. Columns: {df.columns.tolist()}")

    df = df.sort_values('timestamp').reset_index(drop=True)
    return df


def filter_rth(df, date_str):
    """Filter for regular trading hours (9:30-16:00 ET) on a given date."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    rth_start = datetime(dt.year, dt.month, dt.day, 9, 30, tzinfo=ET)
    rth_end = datetime(dt.year, dt.month, dt.day, 16, 0, tzinfo=ET)

    mask = (df['timestamp'] >= rth_start) & (df['timestamp'] < rth_end)
    return df[mask].copy()


def analyze_daily(df, date_str):
    """Analyze a single day for evidence signals and forward returns."""
    day_df = filter_rth(df, date_str)
    if day_df.empty or len(day_df) < 30:
        return None

    feature_store = FeatureStore(zscore_window=100, percentile_window=200)
    regime_detector = AdaptiveRegimeDetector()
    pattern_detector = CandlestickPatternDetector()

    results = {
        'date': date_str,
        'bars': len(day_df),
        'open': float(day_df.iloc[0]['open']),
        'close': float(day_df.iloc[-1]['close']),
        'high': float(day_df['high'].max()),
        'low': float(day_df['low'].min()),
        'patterns_detected': 0,
        'bullish_patterns': 0,
        'bearish_patterns': 0,
        'feature_signals': 0,
        'rsi_extremes': 0,
        'momentum_extremes': 0,
        'vwap_extremes': 0,
        'volume_spikes': 0,
        'regime_direction_signals': 0,
        'regimes': defaultdict(int),
        'micro_regimes': defaultdict(int),
        'pattern_details': [],
        'feature_signal_details': [],
    }

    bars_list = []
    ohlcv_history = {'open': [], 'high': [], 'low': [], 'close': [], 'volume': []}

    for _, row in day_df.iterrows():
        bar = {
            'timestamp': row['timestamp'],
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row['volume']),
        }
        bars_list.append(bar)
        bar_idx = len(bars_list) - 1

        ohlcv_history['open'].append(bar['open'])
        ohlcv_history['high'].append(bar['high'])
        ohlcv_history['low'].append(bar['low'])
        ohlcv_history['close'].append(bar['close'])
        ohlcv_history['volume'].append(bar['volume'])

        # Update feature store
        fv = feature_store.update(bar)

        # Detect regime (after warmup)
        if len(bars_list) >= 30:
            regime_state = regime_detector.detect(fv)
            results['regimes'][regime_state.primary] += 1
            results['micro_regimes'][regime_state.micro_regime] += 1

            if regime_state.confidence > 0.55 and regime_state.micro_regime in (
                'TRENDING_UP', 'TRENDING_DOWN', 'BREAKOUT'
            ):
                results['regime_direction_signals'] += 1

        # Detect candlestick patterns (need >= 5 bars)
        if len(bars_list) >= 5:
            patterns = pattern_detector.detect(ohlcv_history, {})
            if patterns:
                bullish_p = [p for p in patterns if p.direction == PatternDirection.BULLISH]
                bearish_p = [p for p in patterns if p.direction == PatternDirection.BEARISH]
                results['patterns_detected'] += len(patterns)
                results['bullish_patterns'] += len(bullish_p)
                results['bearish_patterns'] += len(bearish_p)

                for p in patterns:
                    results['pattern_details'].append({
                        'bar_idx': bar_idx,
                        'time': str(bar['timestamp']),
                        'name': p.name,
                        'direction': p.direction.value,
                        'strength': p.strength,
                        'price': bar['close'],
                    })

        # Feature extremes (need >= 50 bars warmup)
        if len(bars_list) >= 50 and fv is not None:
            # RSI extreme
            if abs(fv.rsi_z) > 1.5:
                results['rsi_extremes'] += 1
                results['feature_signals'] += 1
                direction = 'bullish' if fv.rsi_z < -1.5 else 'bearish'
                results['feature_signal_details'].append({
                    'bar_idx': bar_idx, 'time': str(bar['timestamp']),
                    'type': 'rsi_extreme', 'direction': direction,
                    'z_score': round(fv.rsi_z, 2), 'price': bar['close'],
                })

            # Momentum extreme
            if abs(fv.momentum_z) > 1.2:
                results['momentum_extremes'] += 1
                results['feature_signals'] += 1
                direction = 'bullish' if fv.momentum_z > 1.2 else 'bearish'
                results['feature_signal_details'].append({
                    'bar_idx': bar_idx, 'time': str(bar['timestamp']),
                    'type': 'momentum_extreme', 'direction': direction,
                    'z_score': round(fv.momentum_z, 2), 'price': bar['close'],
                })

            # VWAP extreme
            if abs(fv.vwap_dist_z) > 2.0:
                results['vwap_extremes'] += 1
                results['feature_signals'] += 1
                direction = 'bullish' if fv.vwap_dist_z < -2.0 else 'bearish'
                results['feature_signal_details'].append({
                    'bar_idx': bar_idx, 'time': str(bar['timestamp']),
                    'type': 'vwap_extreme', 'direction': direction,
                    'z_score': round(fv.vwap_dist_z, 2), 'price': bar['close'],
                })

            # Volume spike + directional move
            if fv.volume_z > 2.0 and abs(fv.roc_5) > 0.2:
                results['volume_spikes'] += 1
                results['feature_signals'] += 1
                direction = 'bullish' if fv.roc_5 > 0 else 'bearish'
                results['feature_signal_details'].append({
                    'bar_idx': bar_idx, 'time': str(bar['timestamp']),
                    'type': 'volume_spike', 'direction': direction,
                    'z_score': round(fv.volume_z, 2), 'roc': round(fv.roc_5, 3),
                    'price': bar['close'],
                })

            # Also check less restrictive thresholds
            if abs(fv.rsi_z) > 1.0:
                results.setdefault('rsi_moderate', 0)
                results['rsi_moderate'] += 1
            if abs(fv.momentum_z) > 0.8:
                results.setdefault('momentum_moderate', 0)
                results['momentum_moderate'] += 1

    # Daily return and range
    results['daily_return_pct'] = round(
        (results['close'] - results['open']) / results['open'] * 100, 2
    )
    results['daily_range_pct'] = round(
        (results['high'] - results['low']) / results['open'] * 100, 2
    )

    # Calculate forward returns for all signals
    for detail_list in [results['pattern_details'], results['feature_signal_details']]:
        for detail in detail_list:
            bar_idx = detail['bar_idx']
            price = detail['price']
            direction = detail['direction']

            for horizon in [5, 10, 15, 20]:
                key = f'move_{horizon}bar_pct'
                if bar_idx + horizon < len(bars_list):
                    future_price = bars_list[bar_idx + horizon]['close']
                    move_pct = (future_price - price) / price * 100
                    if direction == 'bearish':
                        move_pct = -move_pct
                    detail[key] = round(move_pct, 3)
                else:
                    detail[key] = None

    return results


def print_signal_effectiveness(name, details, label=""):
    """Print effectiveness stats for a group of signals."""
    if not details:
        print(f"  {name}: no signals")
        return

    for horizon in [5, 10, 15, 20]:
        key = f'move_{horizon}bar_pct'
        moves = [d[key] for d in details if d.get(key) is not None]
        if not moves:
            continue
        wins = len([m for m in moves if m > 0])
        avg = sum(moves) / len(moves)
        median = sorted(moves)[len(moves) // 2]
        wr = wins / len(moves) * 100
        print(f"    {horizon}-bar: avg={avg:+.3f}% med={median:+.3f}% "
              f"WR={wr:.0f}% ({wins}/{len(moves)})")


def main():
    print("=" * 80)
    print("MU EVIDENCE ANALYSIS - Standalone")
    print("=" * 80)

    df = load_data()
    print(f"Loaded {len(df)} bars from {DATA_FILE}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

    # Generate trading dates
    start = datetime(2026, 1, 20)
    end = datetime(2026, 2, 6)
    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    all_results = []
    all_pattern_details = []
    all_feature_details = []

    for date in dates:
        result = analyze_daily(df, date)
        if result is None:
            print(f"\n{date}: No data or too few bars")
            continue

        all_results.append(result)
        all_pattern_details.extend(result['pattern_details'])
        all_feature_details.extend(result['feature_signal_details'])

        print(f"\n{date}: O={result['open']:.2f} C={result['close']:.2f} "
              f"Ret={result['daily_return_pct']:+.2f}% Rng={result['daily_range_pct']:.2f}%")
        print(f"  Bars={result['bars']} | Pat={result['patterns_detected']} "
              f"(B:{result['bullish_patterns']} S:{result['bearish_patterns']}) "
              f"| Feat={result['feature_signals']} "
              f"(RSI:{result['rsi_extremes']} Mom:{result['momentum_extremes']} "
              f"VWAP:{result['vwap_extremes']} Vol:{result['volume_spikes']})")
        print(f"  RegDir={result['regime_direction_signals']} | "
              f"ModRSI={result.get('rsi_moderate',0)} ModMom={result.get('momentum_moderate',0)}")
        regime_str = ", ".join(f"{k}:{v}" for k, v in sorted(result['regimes'].items()))
        micro_str = ", ".join(f"{k}:{v}" for k, v in sorted(result['micro_regimes'].items()))
        print(f"  Regimes: {regime_str}")
        print(f"  Micro: {micro_str}")

    # ── SUMMARY ──
    print("\n" + "=" * 80)
    print("SUMMARY ACROSS ALL DAYS")
    print("=" * 80)
    total_days = len(all_results)
    total_patterns = sum(r['patterns_detected'] for r in all_results)
    total_features = sum(r['feature_signals'] for r in all_results)
    total_regime = sum(r['regime_direction_signals'] for r in all_results)
    total_mod_rsi = sum(r.get('rsi_moderate', 0) for r in all_results)
    total_mod_mom = sum(r.get('momentum_moderate', 0) for r in all_results)

    print(f"Days: {total_days}")
    print(f"Patterns (strict): {total_patterns}")
    print(f"Feature signals (strict): {total_features}")
    print(f"  RSI moderate (|z|>1.0): {total_mod_rsi}")
    print(f"  Momentum moderate (|z|>0.8): {total_mod_mom}")
    print(f"Regime directional signals: {total_regime}")

    # ── PATTERN EFFECTIVENESS ──
    print("\n--- PATTERN EFFECTIVENESS ---")
    pattern_by_name = defaultdict(list)
    for d in all_pattern_details:
        pattern_by_name[d['name']].append(d)

    for name, details in sorted(pattern_by_name.items(), key=lambda x: -len(x[1])):
        print(f"\n  {name} (n={len(details)}, "
              f"dir={','.join(set(d['direction'] for d in details))}):")
        print_signal_effectiveness(name, details)

    # All patterns combined
    print(f"\n  ALL PATTERNS COMBINED (n={len(all_pattern_details)}):")
    print_signal_effectiveness("all", all_pattern_details)

    # ── FEATURE SIGNAL EFFECTIVENESS ──
    print("\n--- FEATURE SIGNAL EFFECTIVENESS ---")
    feature_by_type = defaultdict(list)
    for d in all_feature_details:
        feature_by_type[d['type']].append(d)

    for ftype, details in sorted(feature_by_type.items(), key=lambda x: -len(x[1])):
        print(f"\n  {ftype} (n={len(details)}, "
              f"dir={','.join(set(d['direction'] for d in details))}):")
        print_signal_effectiveness(ftype, details)

    # All features combined
    print(f"\n  ALL FEATURES COMBINED (n={len(all_feature_details)}):")
    print_signal_effectiveness("all", all_feature_details)

    # ── COINCIDENCE ANALYSIS ──
    print("\n--- COMBINED EVIDENCE COINCIDENCE ---")
    all_signals = []
    for d in all_pattern_details:
        all_signals.append({
            'date': d['time'][:10], 'bar_idx': d['bar_idx'],
            'source': 'pattern', 'name': d['name'],
            'direction': d['direction'],
            'move_5bar': d.get('move_5bar_pct'),
            'move_10bar': d.get('move_10bar_pct'),
        })
    for d in all_feature_details:
        all_signals.append({
            'date': d['time'][:10], 'bar_idx': d['bar_idx'],
            'source': 'feature', 'name': d['type'],
            'direction': d['direction'],
            'move_5bar': d.get('move_5bar_pct'),
            'move_10bar': d.get('move_10bar_pct'),
        })

    by_date = defaultdict(list)
    for s in all_signals:
        by_date[s['date']].append(s)

    coincidences = []
    for date, signals in by_date.items():
        signals.sort(key=lambda x: x['bar_idx'])
        for i, s1 in enumerate(signals):
            cluster = [s1]
            for s2 in signals[i + 1:]:
                if abs(s2['bar_idx'] - s1['bar_idx']) <= 3 and s1['direction'] == s2['direction']:
                    cluster.append(s2)
            if len(cluster) >= 2:
                sources = [f"{s['source']}:{s['name']}" for s in cluster]
                coincidences.append({
                    'date': date, 'bar_idx': s1['bar_idx'],
                    'sources': sources, 'direction': s1['direction'],
                    'move_5bar': s1.get('move_5bar'),
                    'move_10bar': s1.get('move_10bar'),
                    'n_sources': len(cluster),
                })

    print(f"  Coincidences (>=2 sources within 3 bars, same direction): {len(coincidences)}")
    for c in coincidences[:30]:
        m5 = f"{c['move_5bar']:+.3f}%" if c['move_5bar'] is not None else "N/A"
        m10 = f"{c['move_10bar']:+.3f}%" if c['move_10bar'] is not None else "N/A"
        print(f"    {c['date']} bar {c['bar_idx']:3d}: [{c['n_sources']} src] "
              f"{' + '.join(c['sources'][:3])} ({c['direction']}) → 5b={m5} 10b={m10}")

    if coincidences:
        m5 = [c['move_5bar'] for c in coincidences if c['move_5bar'] is not None]
        m10 = [c['move_10bar'] for c in coincidences if c['move_10bar'] is not None]
        if m5:
            avg5 = sum(m5) / len(m5)
            w5 = len([m for m in m5 if m > 0])
            print(f"\n  Coincidence 5-bar: avg={avg5:+.3f}% WR={w5/len(m5)*100:.0f}% (n={len(m5)})")
        if m10:
            avg10 = sum(m10) / len(m10)
            w10 = len([m for m in m10 if m > 0])
            print(f"  Coincidence 10-bar: avg={avg10:+.3f}% WR={w10/len(m10)*100:.0f}% (n={len(m10)})")

    # ── DAILY PRICE BEHAVIOR ──
    print("\n" + "=" * 80)
    print("MU PRICE BEHAVIOR")
    print("=" * 80)
    total_return = sum(r['daily_return_pct'] for r in all_results)
    avg_range = sum(r['daily_range_pct'] for r in all_results) / len(all_results)
    up_days = len([r for r in all_results if r['daily_return_pct'] > 0])
    down_days = len([r for r in all_results if r['daily_return_pct'] < 0])

    print(f"Period return: {total_return:+.2f}%")
    print(f"Up/Down days: {up_days}/{down_days}")
    print(f"Avg daily range: {avg_range:.2f}%")
    print(f"Range: ${all_results[0]['open']:.2f} → ${all_results[-1]['close']:.2f}")

    # Intraday volatility by hour (use ET)
    print("\n--- INTRADAY VOLATILITY BY HOUR (ET) ---")
    df_copy = df.copy()
    df_copy['et_hour'] = df_copy['timestamp'].dt.tz_convert(ET).dt.hour
    for hour in range(9, 16):
        hdf = df_copy[df_copy['et_hour'] == hour]
        if hdf.empty:
            continue
        ranges = ((hdf['high'] - hdf['low']) / hdf['open'] * 100)
        vols = hdf['volume']
        print(f"  {hour:02d}:00 ET - range: {ranges.mean():.3f}% (med {ranges.median():.3f}%) "
              f"vol: {vols.mean():.0f} (n={len(hdf)})")

    # ── KEY INSIGHT: What evidence threshold would generate trades? ──
    print("\n" + "=" * 80)
    print("THRESHOLD SENSITIVITY ANALYSIS")
    print("=" * 80)
    for z_threshold in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
        rsi_count = 0
        mom_count = 0
        for r in all_results:
            for d in r.get('feature_signal_details', []):
                pass  # Already counted at strict
        # Recount at different thresholds
        print(f"\n  Z-threshold = {z_threshold}:")
        # We need to recompute - let's do a quick pass on the feature vectors
        # This is approximate - just counting how many bars exceed thresholds

    # Actually do the threshold sweep properly
    print("\n  (Sweeping thresholds on first day sample...)")
    sample_date = dates[0] if dates else None
    if sample_date:
        sample_df = filter_rth(df, sample_date)
        if not sample_df.empty:
            fs = FeatureStore(zscore_window=100, percentile_window=200)
            fv_list = []
            for _, row in sample_df.iterrows():
                bar = {
                    'open': float(row['open']), 'high': float(row['high']),
                    'low': float(row['low']), 'close': float(row['close']),
                    'volume': float(row['volume']),
                }
                fv = fs.update(bar)
                if fv is not None:
                    fv_list.append(fv)

            for z_th in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
                rsi_hits = sum(1 for f in fv_list if abs(f.rsi_z) > z_th)
                mom_hits = sum(1 for f in fv_list if abs(f.momentum_z) > z_th)
                vwap_hits = sum(1 for f in fv_list if abs(f.vwap_dist_z) > z_th)
                vol_hits = sum(1 for f in fv_list if f.volume_z > z_th)
                print(f"    z>{z_th}: RSI={rsi_hits}/{len(fv_list)} "
                      f"Mom={mom_hits}/{len(fv_list)} "
                      f"VWAP={vwap_hits}/{len(fv_list)} "
                      f"Vol={vol_hits}/{len(fv_list)}")


if __name__ == "__main__":
    main()
