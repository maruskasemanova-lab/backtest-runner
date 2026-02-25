import sqlite3, json, sys

all_trades = []

if len(sys.argv) > 1:
    filename = sys.argv[1]
    with open(filename, 'r') as f:
        data = json.load(f)
        trades = data.get('trades') or data.get('session_summary', {}).get('trades') or []
        all_trades.extend(trades)
else:
    con = sqlite3.connect('data/saas_state.db')
    cur = con.cursor()
    cur.execute('''
        SELECT summary_json 
        FROM run_summaries 
        WHERE run_key LIKE '%batch-MU%' 
        ORDER BY created_at DESC 
        LIMIT 10
    ''')

    for row in cur.fetchall():
        summary = json.loads(row[0])
        trades = summary.get('trades', [])
        if not trades:
            trades = summary.get('session_summary', {}).get('trades', [])
        all_trades.extend(trades)

print(f"Total trades: {len(all_trades)}")
print(f"Total PnL: ${sum(t.get('pnl_dollars', 0) for t in all_trades):.2f}")
win_rate = sum(1 for t in all_trades if t.get('pnl_dollars', 0) > 0) / len(all_trades) if all_trades else 0
print(f"Win rate: {win_rate:.2%}")

all_trades.sort(key=lambda t: t.get('entry_time', ''))

for t in all_trades:
    entry = float(t.get('entry_price', 0))
    pnl = float(t.get('pnl_dollars', 0))
    exit_price = float(t.get('exit_price', 0))
    
    # Try different paths for MFE
    mfe_r = t.get('entry_quality_diagnostics', {}).get('break_even', {}).get('mfe_r', 0)
    if not mfe_r:
        mfe_r = t.get('mfe_r', 0)
    
    print(f"{t.get('entry_time')} | {t.get('side')} {entry:.2f} -> {exit_price:.2f} | PnL: ${pnl:.1f} | Exit: {t.get('exit_reason', 'unknown')} | MFE: {mfe_r:.1f}R | Strategy: {t.get('strategy_key')}")
