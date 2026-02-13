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
| `src/l2_data_manager.py` | yes | 564 | `5ba62b7 2026-02-08` |
| `src/l2_feature_service.py` | yes | 177 | `b21f28a 2026-02-11` |
| `src/order_flow_engine.py` | yes | 336 | `5ba62b7 2026-02-08` |
| `src/intrabar_frame_builder.py` | yes | 314 | `5ba62b7 2026-02-08` |
| `src/l2_feature_aggregator.py` | yes | 226 | `5ba62b7 2026-02-08` |
| `src/run_artifact_store.py` | yes | 245 | `5ba62b7 2026-02-08` |
| `src/databento_service.py` | yes | 1106 | `64da33c 2026-02-10` |
| `scripts/download_l2_data.py` | yes | 69 | `583f2bc 2026-02-06` |
| `scripts/convert_l2_to_parquet.py` | yes | 43 | `583f2bc 2026-02-06` |
| `scripts/verify_l2_data.py` | yes | 31 | `583f2bc 2026-02-06` |
| `docs/L2_DEFINITIONS.md` | yes | 52 | `5ba62b7 2026-02-08` |

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
- `class` `L2DataManager` (line 12)

### `src/l2_feature_service.py`
- `class` `L2FeatureService` (line 18)

### `src/order_flow_engine.py`
- `class` `OrderFlowSnapshot` (line 32)
- `class` `OrderFlowEngine` (line 60)

### `src/intrabar_frame_builder.py`
- `class` `IntrabarFrameBuilder` (line 26)

### `src/l2_feature_aggregator.py`
- `class` `AggregationResult` (line 17)
- `class` `L2FeatureAggregator` (line 32)

### `src/run_artifact_store.py`
- `class` `RunArtifactStore` (line 23)

### `src/databento_service.py`
- `class` `CatalogEntry` (line 31)
- `class` `DataCatalog` (line 50)
- `class` `DatabentoService` (line 115)

### `scripts/download_l2_data.py`
- `function` `download_l2_data` (line 6)

### `scripts/convert_l2_to_parquet.py`
- `function` `convert_to_parquet` (line 8)

## Endpoint Summary

| Method | Path | Handler | File |
|---|---|---|---|
| `-` | `-` | `-` | `-` |

## Prompt Primer

Load this domain pack with `bmad/context/generated/00-index.md` and `bmad/context/generated/00-machine-index.json`, then keep edits scoped to mapped files unless interface changes are explicit.
