# Claude Handoff Pack - Architecture (2026-02-13)

Purpose: give Claude enough current-state context to refactor/clean up the unified adaptive + momentum-diversification + L2 + CVD architecture without spending time on repo discovery.

Primary routing domain for this task: `strategy-engine`.

Cross-domain touch points that are already coupled and must be considered together:
- `orchestration` (runner start/config resolution/tuner wiring)
- `data-l2` (feature names + sessionization + intrabar payload)
- `frontend` (config editors that build the same payloads)

## Contents
- `CURRENT_STATE_MAP.md`: end-to-end flow map with exact file/function anchors.
- `ARCHITECTURE_GAPS.md`: concrete structural gaps and why the current system feels "without head/tail".
- `FILE_INDEX.md`: prioritized navigation list for fast implementation entry.
- `MU_CONFIG_SNAPSHOT.json`: compact snapshot of active MU config/tuner profile state.
- `CLAUDE_PROMPT.md`: copy-paste prompt for Claude implementation.

## Recommended Reading Order
1. `CURRENT_STATE_MAP.md`
2. `ARCHITECTURE_GAPS.md`
3. `FILE_INDEX.md`
4. `MU_CONFIG_SNAPSHOT.json`
5. `CLAUDE_PROMPT.md`

## Non-Negotiable Invariants
- No look-ahead in bars/L2/session logic.
- No same-bar execution (`signal_bar_index < entry_bar_index`).
- `comparable_mode=true` must force cold start and ignore warm checkpoint load.
- L2 sessionized metrics must reset per market day when enabled.

## Validation Commands (after any refactor)
- `python3 scripts/generate_context_pack.py`
- `python3 scripts/validate_llm_context.py`
- `python3 scripts/validate_llm_context.py --strict`
- Runner safety: `pytest tests/test_no_lookahead.py tests/test_api_server_l2_sessionized.py tests/test_session_runner_markers.py`
- Strategy safety: `pytest /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_strategy_selection_mode.py /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_day_trading_manager_positioning_defaults.py`
