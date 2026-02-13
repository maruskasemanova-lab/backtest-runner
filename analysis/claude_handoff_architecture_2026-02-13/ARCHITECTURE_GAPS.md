# Architecture Gaps (Why It Feels "Without Head/Tail")

## G1) Same logical schema normalized in multiple independent places

Evidence:
- Runner normalization: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/momentum_diversification.py:105`
- Strategy normalization: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:756`
- Frontend runtime override builder: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/RunConfig.jsx:260`
- Frontend AOS builder: `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AOSOptimizations.jsx:274`

Impact:
- Drift risk in defaults, clamping, and optional-field handling.
- Hard to reason about "what config is actually in effect".

## G2) Momentum config has dual representation (flat + nested)

Evidence:
- V2 candidate supports flat keys (`momentum_min_cvd`, etc.) and optional nested object merge:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_v2_service.py:583`
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/adaptive_tuner_v2_service.py:605`
- Runtime extraction repeats flatten->nested conversion:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/strategy_api_profiles_service.py:114`
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/strategy_api_profiles_service.py:159`

Impact:
- Precedence and merge order become non-obvious.
- Bugs can hide when one path writes nested and another reads flat.

## G3) Effective config precedence is spread across multiple layers

Evidence:
- Runner start precedence for momentum source:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_service.py:379`
- Execution-mode precedence (selection mode, max_active, risk/exits):
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/start_run_execution_config_service.py:52`
- Profile runtime override extraction:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/services/strategy_api_profiles_service.py:65`

Impact:
- No single deterministic "effective config builder" boundary.
- Refactors are risky because behavior is encoded in 3+ modules.

## G4) L2 book-pressure delta naming mismatch across services

Evidence:
- Runner sends `l2_book_pressure_delta`:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/session_runner.py:46`
- Strategy API model expects `l2_book_pressure_change`:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/api_models.py:48`
- Strategy flow metrics read `l2_book_pressure_change`:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:1780`

Impact:
- This metric can be silently dropped at API boundary (Pydantic ignores unknown fields).
- Downstream flow metrics/gates can operate on missing values.

## G5) Selection, routing, gating, and exits are tightly coupled in one large class

Evidence (single class ownership):
- Strategy selection: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:2118`
- Momentum route building: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:2036`
- Momentum gate: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:3740`
- Fail-fast exit: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:3825`
- L2 confirmation gate: `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:3987`

Impact:
- Low cohesion, high change blast radius.
- Hard to unit test policy pieces independently.

## G6) Flow metric computation is reused with different windows and contexts

Evidence:
- Core metric builder (lookback based):
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:1734`
- Called in selection context with one window and in fail-fast with shorter window:
  - selection path around `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:2176`
  - fail-fast path around `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:3847`

Impact:
- Same feature names can represent different horizons depending on call site.
- Debugging threshold behavior becomes difficult.

## G7) Run defaults are written and reapplied through multiple entry points

Evidence:
- Strategy API `/api/session/config` sets session and calls `set_run_defaults`:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/api_server.py:506`
- Defaults are reapplied per bar in `process_bar`:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:1163`

Impact:
- Hidden state coupling between config time and bar-processing time.
- Increased complexity when trying to reason about per-run determinism.

## G8) Active MU config state is large and noisy

Evidence:
- `MU` contains long history of tuner profiles and strategy-combo profiles in:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/aos_optimization/aos_config.json`
- Snapshot in this handoff: `MU_CONFIG_SNAPSHOT.json`.

Impact:
- Hard to identify "current intended baseline" from raw config alone.
- Operators may activate one profile while many stale alternatives remain.

## G9) L2 contract is richer than what strategy currently consumes directly

Evidence:
- Runner L2 feature map includes many fields (`l2_delta_acceleration`, `l2_delta_price_divergence`, etc.):
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/src/order_flow_engine.py:254`
- Strategy recomputes many flow metrics from core bar fields:
  - `/Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/src/day_trading_manager.py:1734`

Impact:
- Two semi-overlapping feature semantics (precomputed vs recomputed).
- Extra room for divergence and confusion in calibration.

## G10) Frontend has duplicated default/clamp logic in two separate editors

Evidence:
- Runtime override editor defaults/clamps:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/RunConfig.jsx:160`
- AOS editor defaults/clamps:
  - `/Users/hotovo/.gemini/antigravity/scratch/backtest-runner/frontend/src/components/AOSOptimizations.jsx:55`

Impact:
- UI can drift from backend validation logic.
- User may see accepted values in one editor but different behavior in runtime.
