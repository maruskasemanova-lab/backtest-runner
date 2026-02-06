# Domain: L2 Data & Features

**ID:** `data-l2`

## Mission

Own L2 acquisition, conversion, minute alignment, and flow-feature extraction.

## Depends On

- `orchestration`
- `strategy-engine`

## Entrypoints

- `src/l2_data_manager.py`
- `src/l2_feature_service.py`

## File Inventory

| File | Exists | Lines | Last Commit |
|---|---:|---:|---|
| `src/l2_data_manager.py` | yes | 426 | `583f2bc 2026-02-06` |
| `src/l2_feature_service.py` | yes | 189 | `2971a5a 2026-02-06` |
| `scripts/download_l2_data.py` | yes | 69 | `583f2bc 2026-02-06` |
| `scripts/convert_l2_to_parquet.py` | yes | 43 | `583f2bc 2026-02-06` |
| `scripts/verify_l2_data.py` | yes | 31 | `583f2bc 2026-02-06` |

## Change Checks

- Preserve timezone normalization to UTC.
- Do not leak future L2 events into current bar features.
- Keep feature names consistent with strategy API payload.

## Prompt Primer

Load this file plus `bmad/context/generated/00-index.md`, then keep edits scoped to the file inventory unless interface changes are explicitly required.
