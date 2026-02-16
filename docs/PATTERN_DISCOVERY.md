# Pattern Discovery Engine

Experimental module for discovering recurring market patterns from backtest data.

## Overview

The Pattern Discovery Engine (PDE) is a standalone service that:

1. **Discovers patterns** from historical backtest data using clustering and sequential mining
2. **Matches patterns** in real-time during trading
3. **Provides evidence** to the strategy engine's EvidenceDecisionEngine
4. **Tunes parameters** through integration with the adaptive tuner

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pattern Discovery Service                     │
│                         (Port 8003)                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Extractor   │  │  Clustering  │  │  Sequential Mining   │  │
│  │              │→ │              │  │                      │  │
│  │  Snapshots   │  │  K-Means/GMM │  │  N-gram Patterns     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│           │                │                    │               │
│           └────────────────┼────────────────────┘               │
│                            ▼                                    │
│                  ┌──────────────────┐                           │
│                  │  Pattern Library │                           │
│                  │    (JSON files)  │                           │
│                  └──────────────────┘                           │
│                            │                                    │
│                            ▼                                    │
│                  ┌──────────────────┐                           │
│                  │  Pattern Matcher │                           │
│                  │   (Real-time)    │                           │
│                  └──────────────────┘                           │
│                            │                                    │
│                            ▼                                    │
│                  ┌──────────────────┐                           │
│                  │ Evidence Source  │                           │
│                  └──────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼ API
┌─────────────────────────────────────────────────────────────────┐
│                      Strategy Engine                            │
│                  EvidenceDecisionEngine                         │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Start the Pattern Discovery Service

```bash
# Set environment variables
export PATTERN_DISCOVERY_PORT=8003
export RUNNER_API_URL=http://localhost:8002
export STRATEGY_API_URL=http://localhost:8001

# Start the service
python -m src.pattern_discovery.api_server
```

### 2. Discover Patterns from Historical Data

```bash
# Using CLI
python scripts/run_pattern_discovery.py \
    --discover \
    --ticker MU \
    --date-from 2025-11-02 \
    --date-to 2026-02-10 \
    --min-support 10 \
    --min-win-rate 0.55

# Or using API
curl -X POST http://localhost:8003/api/pattern-discovery/discover \
    -H "Content-Type: application/json" \
    -d '{
        "ticker": "MU",
        "date_from": "2025-11-02",
        "date_to": "2026-02-10",
        "discovery_config": {
            "clustering_enabled": true,
            "sequential_enabled": true,
            "min_support": 10,
            "min_win_rate": 0.55
        }
    }'
```

### 3. Match Patterns in Real-time

```bash
# Using CLI
python scripts/run_pattern_discovery.py \
    --match \
    --ticker MU \
    --features '{"momentum_z": 1.5, "l2_delta_z": 2.0, "l2_aggression_z": 1.8}'

# Or using API
curl -X POST http://localhost:8003/api/pattern-discovery/match \
    -H "Content-Type: application/json" \
    -d '{
        "ticker": "MU",
        "feature_vector": {
            "momentum_z": 1.5,
            "l2_delta_z": 2.0,
            "l2_aggression_z": 1.8
        }
    }'
```

## API Endpoints

### Discovery

| Method | Endpoint                               | Description                 |
| ------ | -------------------------------------- | --------------------------- |
| POST   | `/api/pattern-discovery/discover`      | Start pattern discovery job |
| GET    | `/api/pattern-discovery/jobs/{job_id}` | Get job status/results      |
| GET    | `/api/pattern-discovery/jobs`          | List recent jobs            |

### Library Management

| Method | Endpoint                                          | Description             |
| ------ | ------------------------------------------------- | ----------------------- |
| GET    | `/api/pattern-discovery/patterns/{ticker}`        | Get patterns for ticker |
| GET    | `/api/pattern-discovery/libraries`                | List all libraries      |
| GET    | `/api/pattern-discovery/libraries/{ticker}/stats` | Get library statistics  |

### Matching

| Method | Endpoint                                   | Description                      |
| ------ | ------------------------------------------ | -------------------------------- |
| POST   | `/api/pattern-discovery/match`             | Match patterns against features  |
| GET    | `/api/pattern-discovery/evidence/{ticker}` | Get evidence for strategy engine |

### Tuning

| Method | Endpoint                           | Description                |
| ------ | ---------------------------------- | -------------------------- |
| POST   | `/api/pattern-discovery/tuner/run` | Start pattern-aware tuning |

## Configuration

### Environment Variables

```bash
# Service configuration
PATTERN_DISCOVERY_PORT=8003
PATTERN_DISCOVERY_HOST=0.0.0.0

# Integration URLs
RUNNER_API_URL=http://localhost:8002
STRATEGY_API_URL=http://localhost:8001

# Storage
PATTERN_LIBRARY_PATH=pattern_library
```

### Discovery Configuration

```python
from src.pattern_discovery import DiscoveryConfig

config = DiscoveryConfig(
    # Clustering settings
    clustering_enabled=True,
    clustering_k_range=(50, 200),  # Range of cluster counts to try
    clustering_method="kmeans",    # "kmeans" or "gmm"

    # Sequential mining settings
    sequential_enabled=True,
    n_gram_range=(2, 5),           # N-gram lengths to mine

    # Filtering thresholds
    min_support=10,                # Minimum pattern occurrences
    min_win_rate=0.55,             # Minimum historical win rate
    min_sharpe=1.0,                # Minimum Sharpe ratio

    # Feature extraction
    lookback_bars=20,              # Context lookback
    forward_bars=10,               # Outcome lookahead
)
```

### Match Configuration

```python
from src.pattern_discovery import MatchConfig

config = MatchConfig(
    min_similarity=0.7,            # Minimum similarity threshold
    max_matches=3,                 # Maximum matches to return
    direction_filter="any",        # "any", "bullish_only", "bearish_only"
    min_win_rate=0.50,             # Minimum historical win rate
    min_support=5,                 # Minimum pattern support
)
```

## Integration with Strategy Engine

The Pattern Discovery Engine integrates with the strategy engine's EvidenceDecisionEngine as an additional evidence source.

### Using the API

```python
import httpx
import json

async def get_pattern_evidence(ticker: str, feature_vector: dict) -> dict:
    """Get pattern evidence for strategy engine."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8003/api/pattern-discovery/evidence/{ticker}",
            params={
                "feature_vector_json": json.dumps(feature_vector),
            }
        )
        return response.json()

# Use in strategy engine
evidence = await get_pattern_evidence("MU", {
    "momentum_z": 1.5,
    "l2_delta_z": 2.0,
    # ... other features
})

# evidence = {
#     "source_type": "pattern",
#     "source_name": "bullish_high_delta_spike",
#     "direction": "bullish",
#     "strength": 61.2,
#     "calibrated": 0.72,
#     "reasoning": "Pattern 'bullish_high_delta_spike' matched..."
# }
```

### Direct Integration

```python
from src.pattern_discovery import PatternMatcher, PatternEvidenceSource

# Load matcher
matcher = PatternMatcher.for_ticker("MU")

# Create evidence source
evidence_source = PatternEvidenceSource(matcher=matcher)

# Get evidence
evidence = evidence_source.get_evidence(feature_vector)
```

## Pattern Types

### Cluster Patterns

Cluster patterns are discovered through K-Means or Gaussian Mixture Model clustering of feature vectors. Each cluster represents a similar market state.

**Example:**

```json
{
  "pattern_id": "cluster_42",
  "pattern_name": "bullish_high_delta_spike",
  "win_rate": 0.72,
  "support": 45,
  "direction": "bullish",
  "feature_importance": {
    "l2_delta_z": 0.35,
    "momentum_z": 0.25
  }
}
```

### Sequential Patterns

Sequential patterns are discovered through n-gram mining of discrete state sequences. Each pattern represents a sequence of market states that historically led to profitable outcomes.

**Example:**

```json
{
  "pattern_id": "seq_up_spike_normal_high",
  "pattern_name": "bullish_seq_delta_spike",
  "sequence": ["up_spike_up_normal", "up_normal_high"],
  "win_rate": 0.68,
  "support": 25,
  "direction": "bullish"
}
```

## Pattern-Aware Tuning

The Pattern Discovery Engine integrates with the adaptive tuner to optimize pattern matching parameters:

```bash
curl -X POST http://localhost:8003/api/pattern-discovery/tuner/run \
    -H "Content-Type: application/json" \
    -d '{
        "ticker": "MU",
        "date_from": "2025-11-02",
        "date_to": "2026-02-10",
        "pattern_config": {
            "pattern_min_similarity_options": [0.6, 0.7, 0.8],
            "pattern_min_win_rate_options": [0.50, 0.55, 0.60],
            "pattern_evidence_weight_options": [0.0, 0.1, 0.15]
        }
    }'
```

## File Structure

```
src/pattern_discovery/
├── __init__.py           # Module exports
├── models.py             # Pydantic models
├── extractor.py          # Feature snapshot extraction
├── clustering.py         # K-Means/GMM pattern discovery
├── sequential.py         # N-gram pattern mining
├── library.py            # Pattern library persistence
├── matcher.py            # Real-time pattern matching
├── evidence.py           # Evidence source for strategy engine
└── api_server.py         # FastAPI routes

pattern_library/          # Saved pattern libraries
├── MU_patterns_v1.json
└── GOOGL_patterns_v1.json

scripts/
└── run_pattern_discovery.py  # CLI tool

tests/
└── test_pattern_discovery.py # Unit tests
```

## Performance Considerations

- **Discovery**: Typically takes 1-5 minutes for 3 months of data
- **Matching**: < 10ms per bar for real-time use
- **Memory**: Pattern libraries are typically < 1MB per ticker

## Best Practices

1. **Discovery Frequency**: Run discovery weekly or monthly to update patterns
2. **Validation**: Always validate patterns on out-of-sample data
3. **Minimum Support**: Use min_support >= 10 to avoid overfitting
4. **Win Rate Threshold**: Use min_win_rate >= 0.55 for reliable patterns
5. **Similarity Threshold**: Use min_similarity >= 0.7 for quality matches

## Troubleshooting

### No patterns discovered

- Check that backtest reports exist in the `reports/` directory
- Lower `min_support` and `min_win_rate` thresholds
- Ensure date range has sufficient data

### Low win rates

- Patterns may be overfitting; increase `min_support`
- Check for regime changes in the data
- Consider separating patterns by regime

### API connection errors

- Verify the service is running on the correct port
- Check CORS settings if calling from frontend
- Ensure network connectivity between services
