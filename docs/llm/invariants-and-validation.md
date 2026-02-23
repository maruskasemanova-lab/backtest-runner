# Invariants And Validation

Critical invariants and required validation workflow for safe LLM-assisted changes.

## Critical Invariants

### No-Lookahead

- Runner bar stepping cannot access future bars.
- Strategy feature calculations and decision logic use only current/past data.
- L2 aggregation/sessionization cannot leak future minute data.
- Intrabar quote payload (`intrabar_quotes_1s`) may include only the current minute's 1-second snapshots for the processed bar.

### Execution And Risk

- No same-bar execution (`signal_bar_index < entry_bar_index`).
- Fill/risk caps must respect configured execution defaults.
- Exit reason and cost fields remain traceable in markers and summaries.

### Reset/Checkpoint Semantics

- `comparable_mode=true` forces cold-start behavior.
- `comparable_mode=true` cold-start semantics must hold even when progressive range loading is enabled.
- Warm-start checkpoint load must remain explicit and opt-in.
- Session reset and full reset scopes must remain distinct.

### Contract Stability

- Runner and strategy APIs should remain backward compatible when possible.
- Cross-domain contract changes require explicit documentation in the same change.

## Required Validation Workflow

### Context validation

```bash
python3 scripts/generate_context_pack.py
python3 scripts/validate_llm_context.py
```

### Strict validation

```bash
python3 scripts/validate_llm_context.py --strict
```

### Runner regression safety

```bash
pytest tests/test_no_lookahead.py tests/test_api_server_l2_sessionized.py tests/test_session_runner_markers.py
```

### Strategy regression safety

```bash
pytest /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_trading_orchestrator_reset.py /Users/hotovo/.gemini/antigravity/scratch/market_regime_detection/tests/test_checkpoint.py
```

## Minimum Acceptance Checklist

- Generated machine index contains both services and route catalog entries.
- Each domain pack includes critical invariants and test targets.
- `.claude/commands` files include schema-first output expectations.
- Validation scripts pass without errors.
