import sqlite3, json

con = sqlite3.connect('data/saas_state.db')
cur = con.cursor()
cur.execute('''
    SELECT run_key 
    FROM run_summaries 
    WHERE run_key LIKE '%batch-MU%' 
    ORDER BY created_at DESC 
    LIMIT 1
''')
row = cur.fetchone()
last_run_key = row[0]
run_id = last_run_key.split(':')[0]

cur.execute('''
    SELECT summary_json 
    FROM run_summaries 
    WHERE run_key LIKE ? 
    ORDER BY created_at ASC
''', (f"{run_id}:batch-MU:%",))

all_trades = []
for row in cur.fetchall():
    summary = json.loads(row[0])
    trades = summary.get('trades', [])
    if not trades:
        trades = summary.get('session_summary', {}).get('trades', [])
    all_trades.extend(trades)

print(f'Batch run ID: {run_id}')
print(f'Total trades: {len(all_trades)}')
print(f'Total PnL: ${sum(t.get("pnl", 0) for t in all_trades):.2f}')
for t in all_trades:
    entry = float(t.get('entry_price', 0))
    sl = float(t.get('initial_stop_loss', 0))
    highest = float(t.get('mfe_highest_price', entry))
    lowest = float(t.get('mfe_lowest_price', entry))
    risk = abs(entry - sl) if sl > 0 else 0
    mfe_abs = (highest - entry) if str(t.get('side')).lower() == 'long' else (entry - lowest)
    mfe_r = (mfe_abs / risk) if risk > 0 else 0
    t['mfe_r'] = mfe_r
    
    print(f"{t.get('entry_time')} | {t.get('side')} {entry:.2f} -> {t.get('exit_price', 0):.2f} | PnL: ${t.get('pnl', 0):.2f} | Exit: {t.get('exit_reason', 'unknown')} | MFE: {t.get('mfe_r', 0):.2f}R")
