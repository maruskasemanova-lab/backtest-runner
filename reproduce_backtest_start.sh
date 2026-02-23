#!/bin/bash
# Reproduction script for verifying run start connectivity
# Usage: ./reproduce_backtest_start.sh

echo "Requesting backtest start for MU 2025-10-01 to 2025-10-28..."
curl -v -X POST "http://localhost:8002/api/run/start" \
     -H "Content-Type: application/json" \
     -d '{
           "run_id": "verify_fix_run",
           "ticker": "MU",
           "date_from": "2025-10-01",
           "date_to": "2025-10-28",
           "account_size_usd": 100000,
           "risk_per_trade_pct": 1,
           "max_position_notional_pct": 100,
           "max_fill_participation_rate": 0.1,
           "min_fill_ratio": 0.5,
           "strategy_api_url": "http://localhost:8001"
         }'

echo ""
echo "Check output above for 'success': true and 'failed_strategies' array (should be empty if fix worked)."
