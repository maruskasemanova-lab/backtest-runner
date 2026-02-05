#!/bin/bash
# Start all services for the Unified Backtest Runner

echo "🚀 Starting Unified Backtest Runner..."
echo ""

# Check if ports are available
check_port() {
    if lsof -i :$1 > /dev/null 2>&1; then
        echo "⚠️  Port $1 is already in use"
        return 1
    fi
    return 0
}

# Start Strategy Evaluator on port 8001
echo "📊 Starting Strategy Evaluator on port 8001..."
cd /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection
python3 -m uvicorn api_server:app --port 8001 &
STRATEGY_PID=$!
sleep 2

# Start Backtest Runner on port 8002
echo "🎯 Starting Backtest Runner API on port 8002..."
cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner
python3 -m uvicorn api_server:app --port 8002 &
RUNNER_PID=$!
sleep 2

# Start Frontend on port 5173
echo "🖥️  Starting Frontend on port 5173..."
cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ All services started!"
echo ""
echo "   Strategy API:    http://localhost:8001"
echo "   Backtest Runner: http://localhost:8002"
echo "   Frontend:        http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait and cleanup
trap "kill $STRATEGY_PID $RUNNER_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
