# Domain: L2 Data & Features

**ID:** `data-l2`

## Mission

Own L2 acquisition, conversion, minute alignment, intrabar frames, and flow-feature extraction.

## Depends On

- `orchestration`
- `strategy-engine`

## Entrypoints

- `src/l2_data_manager.py`
- `src/l2_feature_service.py`
- `src/order_flow_engine.py`
- `src/intrabar_frame_builder.py`

## File Inventory

| File | Exists | Lines | Last Commit |
|---|---:|---:|---|
| `src/l2_data_manager.py` | yes | 1114 | `1273b21 2026-02-23` |
| `src/l2_feature_service.py` | yes | 227 | `1273b21 2026-02-23` |
| `src/order_flow_engine.py` | yes | 449 | `1273b21 2026-02-23` |
| `src/intrabar_frame_builder.py` | yes | 365 | `c70aa9e 2026-02-24` |
| `src/l2_feature_aggregator.py` | yes | 254 | `1273b21 2026-02-23` |
| `src/databento_service.py` | yes | 2046 | `1273b21 2026-02-23` |
| `scripts/download_l2_data.py` | yes | 63 | `1273b21 2026-02-23` |
| `scripts/convert_l2_to_parquet.py` | yes | 45 | `1273b21 2026-02-23` |
| `scripts/verify_l2_data.py` | yes | 31 | `1273b21 2026-02-23` |
| `docs/L2_DEFINITIONS.md` | yes | 73 | `b9accc6 2026-02-18` |

## Change Checks

- Preserve timezone normalization to UTC.
- Do not leak future L2 events into current bar features.
- Keep feature names consistent with strategy API payload.
- Coverage and sanity flags must remain machine-readable.

## Critical Invariants

- L2 minute aggregation uses only events within the same minute window.
- Sessionized cumulative metrics must reset per market day when requested.
- Intrabar 1s artifacts must preserve schema version metadata.
- Feature fields consumed by strategy API remain stable and documented.

## Test Targets

- `tests/test_l2_feature_aggregator.py`
- `tests/test_intrabar_frame_builder.py`
- `tests/test_api_server_l2_sessionized.py`
- `tests/test_databento_daily_coverage.py`
- `tests/test_databento_ohlcv_effective_range.py`

## Key Symbols

### `src/l2_data_manager.py`
- `class` `L2DataManager` (line 14)

### `src/l2_feature_service.py`
- `class` `L2FeatureService` (line 20)

### `src/order_flow_engine.py`
- `class` `OrderFlowSnapshot` (line 35)
- `class` `OrderFlowEngine` (line 64)

### `src/intrabar_frame_builder.py`
- `class` `IntrabarFrameBuilder` (line 28)

### `src/l2_feature_aggregator.py`
- `class` `AggregationResult` (line 18)
- `class` `L2FeatureAggregator` (line 33)

### `src/databento_service.py`
- `class` `CatalogEntry` (line 41)
- `class` `DataCatalog` (line 60)
- `class` `DatabentoService` (line 126)

### `scripts/convert_l2_to_parquet.py`
- `function` `convert_to_parquet` (line 9)

## Endpoint Summary

| Method | Path | Handler | File |
|---|---|---|---|
| `-` | `-` | `-` | `-` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
