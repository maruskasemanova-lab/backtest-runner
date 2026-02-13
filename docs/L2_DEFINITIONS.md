# L2 Feature Vector Definitions (l2fv-1.0)

Schema version: `l2fv-1.0`

## Flow Metrics

| Field | Unit | Description |
|-------|------|-------------|
| `l2_schema_version` | string | Version identifier ("l2fv-1.0") |
| `l2_delta` | shares | Buy volume − Sell volume |
| `l2_buy_volume` | shares | Total buy trade volume |
| `l2_sell_volume` | shares | Total sell trade volume |
| `l2_volume` | shares | Total volume (buy + sell) |
| `l2_imbalance` | ratio [-1,1] | delta / volume (size-weighted) |
| `l2_signed_aggression` | ratio [-1,1] | Alias for imbalance |
| `l2_cumulative_delta` | shares | Running sum within session |
| `l2_delta_acceleration` | shares | delta[t] − delta[t-1] |
| `l2_delta_price_divergence` | float | signed_aggression − normalized_price |

## Book Metrics

| Field | Unit | Description |
|-------|------|-------------|
| `l2_bid_depth_total` | shares | Mean sum of bid sizes (levels 0-9) |
| `l2_ask_depth_total` | shares | Mean sum of ask sizes (levels 0-9) |
| `l2_book_pressure` | ratio [-1,1] | (bid − ask) / (bid + ask) |
| `l2_book_pressure_change` | ratio | book_pressure[t] − book_pressure[t-1] |
| `l2_top_heavy_bid` | ratio [0,1] | bid_sz_00 / bid_depth_total |
| `l2_top_heavy_ask` | ratio [0,1] | ask_sz_00 / ask_depth_total |

## Iceberg Detection

| Field | Unit | Description |
|-------|------|-------------|
| `l2_iceberg_buy_count` | count | Detected icebergs on buy side |
| `l2_iceberg_sell_count` | count | Detected icebergs on sell side |
| `l2_iceberg_bias` | count | buy_count − sell_count |

## Quality Metrics

| Field | Type | Description |
|-------|------|-------------|
| `l2_quality_coverage_ratio` | float [0,1] | Minutes with data / expected minutes |
| `l2_quality_trade_ticks` | int | Trade events in this minute |
| `l2_quality_book_updates` | int | Book update events in this minute |

## Aggressor Classification

Priority order:
1. `side` field from source ("B" = buy, "A" = sell)
2. Price vs BBO: price ≥ ask → buy; price ≤ bid → sell
3. Price vs mid: price ≥ mid → buy; price < mid → sell
