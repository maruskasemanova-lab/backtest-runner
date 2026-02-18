# Unified Backtest Runner

Walk-forward backtesting system that connects a look-ahead free backtest engine with a session-based strategy evaluator, featuring real-time visualization with decision markers.

## Features

- 📊 **TradingView Charts** - Candlestick visualization with volume
- ▶️ **Playback Controls** - Step, play, pause with adjustable speed
- 🎯 **Decision Markers** - Visual markers for regime detection, entries, exits
- 📝 **Explanations** - Detailed reasoning for each trading decision
- 📈 **Session Summary** - PnL, win rate, regime and strategy info

## Quick Start

### 1. Start Strategy Evaluator (port 8001)

```bash
cd /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection
python -m uvicorn api_server:app --port 8001 --reload
```

### 2. Start Backtest Runner API (port 8002)

```bash
cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner
python -m uvicorn api_server:app --port 8002 --reload
```

### 3. Start Frontend (port 5173)

```bash
cd /Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend
npm run dev
```

### 4. Open Browser

Navigate to: **http://localhost:5173**

## Cloud Deploy

Recommended production stack (stateful + low latency):

- Cloudflare Pages frontend + Fly.io APIs:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/DEPLOY_CLOUDFLARE_STACK.md`

Alternative:

- Fly stack guide:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/DEPLOY_FLY_STACK.md`
- Free-stack variant (Netlify + Render + Supabase):
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/DEPLOY_FREE_STACK.md`

Frontend split routing supports serverless + persistent hybrid:

- `VITE_API_BASE_URL` for general API (for example Vercel)
- `VITE_PLAYBACK_API_BASE_URL` for stateful `/api/run*` playback (must be persistent backend)

Important: interactive `/api/run/*` playback is stateful (in-memory). Do not host the backend on pure serverless runtimes (for example Vercel Python/Lambda).

## Usage

1. Configure run parameters (Run ID, Ticker, Date)
2. Click **Start Backtest**
3. Use playback controls:
   - **Step** (⏭) - Advance one bar
   - **Play** (▶) - Auto-advance at set speed
   - **Pause** (⏸) - Stop auto-advance
   - **Reset** (🔄) - Clear run
4. Click on decision markers in the right panel to see detailed explanations

## LLM Workflow (BMAD Ready)

For structured Claude/Codex work on large changes, use:

- `BMAD_QUICKSTART.md`
- `bmad/README.md`
- `docs/llm/README.md`
- official BMAD install in `_bmad/` with `/bmad-help`

Refresh domain context packs:

```bash
python3 scripts/generate_context_pack.py
```

Validate LLM context consistency:

```bash
python3 scripts/validate_llm_context.py
```

Generated assets include:

- `bmad/context/generated/00-machine-index.json`
- `bmad/context/generated/00-endpoint-map.md`

Bootstrap/refresh full BMAD-METHOD:

```bash
./scripts/bootstrap_bmad.sh
```

Run Codex with project-local BMAD prompts:

```bash
./scripts/codex-project.sh
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Trading Data   │────▶│  Backtest Runner │────▶│ Strategy API    │
│  (CSV/Parquet)  │     │    (port 8002)   │     │  (port 8001)    │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                 │
                                 │ WebSocket
                                 ▼
                        ┌─────────────────┐
                        │    Frontend     │
                        │  (port 5173)    │
                        └─────────────────┘
```

## API Endpoints

| Endpoint                                | Method    | Description                        |
| --------------------------------------- | --------- | ---------------------------------- |
| `/api/run/start`                        | POST      | Start new backtest run             |
| `/api/run/{id}/{ticker}/{date}/step`    | POST      | Advance one bar                    |
| `/api/run/{id}/{ticker}/{date}/play`    | POST      | Start auto-advance                 |
| `/api/run/{id}/{ticker}/{date}/pause`   | POST      | Pause auto-advance                 |
| `/api/run/{id}/{ticker}/{date}/markers` | GET       | Get all decision markers           |
| `/api/run/{id}/{ticker}/{date}/summary` | GET       | Get session summary                |
| `/ws/live`                              | WebSocket | Real-time bar and decision updates |

## Decision Marker Types

| Marker               | Description                                          |
| -------------------- | ---------------------------------------------------- |
| 🎯 Regime Detected   | Market regime classification (Trending/Choppy/Mixed) |
| 📋 Strategy Selected | Trading strategy chosen for the regime               |
| 🟢 Entry Executed    | Position opened                                      |
| 🔴 Stop Loss Hit     | Position closed at stop loss                         |
| 💰 Take Profit Hit   | Position closed at take profit                       |
| ⚪ Exit Executed     | Position closed (other reason)                       |
