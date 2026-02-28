import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

con = sqlite3.connect(str(REPO_ROOT / "data" / "saas_state.db"))
cur = con.cursor()
cur.execute('''
    SELECT summary_json 
    FROM run_summaries 
    WHERE run_key LIKE '%batch-MU%' 
    ORDER BY created_at DESC 
    LIMIT 10
''')

strategy_pnl = {}
trades = []

for row in cur.fetchall():
    summary = json.loads(row[0])
    day_trades = summary.get('trades', [])
    if not day_trades:
        day_trades = summary.get('session_summary', {}).get('trades', [])
    trades.extend(day_trades)

for t in trades:
    strat = t.get('strategy', 'unknown')
    pnl = float(t.get('pnl_dollars', 0))
    if strat not in strategy_pnl:
        strategy_pnl[strat] = {'pnl': 0, 'trades': 0, 'wins': 0}
    strategy_pnl[strat]['pnl'] += pnl
    strategy_pnl[strat]['trades'] += 1
    if pnl > 0:
        strategy_pnl[strat]['wins'] += 1

print("Strategy Analysis over last 10 'batch-MU' runs:")
for strat, stats in sorted(strategy_pnl.items(), key=lambda x: x[1]['pnl']):
    win_rate = stats['wins'] / stats['trades'] * 100 if stats['trades'] > 0 else 0
    print(f"Strategy: {strat:<30} | Trades: {stats['trades']:<4} | WinRate: {win_rate:5.1f}% | PnL: ${stats['pnl']:.2f}")

print("\nDetailed Losing Trades:")
for t in trades:
    pnl = float(t.get('pnl_dollars', 0))
    if pnl < 0:
        print(f"[{t.get('entry_time')}] {t.get('strategy')}: Entry={t.get('entry_price')} Exit={t.get('exit_price')} PnL=${pnl:.2f} Reason={t.get('exit_reason')}")
