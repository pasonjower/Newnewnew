# Metric calculations

The Python engine consolidates raw Shopify exports and vendor metadata into a clean metrics payload. Below are the formulas used.

## Core aggregations

- **Demand window**: 90 trailing days from the latest order date (configurable via `DEMAND_WINDOW_DAYS`).
- **Daily demand**: group orders by SKU and day, sum quantity.
- **Average daily demand**: `mean(daily_quantity)` over the demand window.
- **Demand volatility**: `std(daily_quantity)`; used for safety stock.
- **Total revenue**: `sum(quantity * unit_price)`.
- **Gross margin $**: `revenue - total_net_cost` per SKU.

## Inventory metrics

- **On-hand units**: sum of `inventory.on_hand` across all locations.
- **Sell-through %**: `units_sold / (units_sold + on_hand_units)`.
- **Stock-to-sales ratio**: `(on_hand_units / demand_window_days) / average_daily_demand` expressed as days.
- **Weeks-of-supply (WOS)**: `(on_hand_units / average_daily_demand) / 7`.

## Metal costing

1. Lookup the latest spot price per metal.
2. Compute **gross metal grams** = `grams_per_unit * (1 + finishing_loss_pct/100)`.
3. Compute **net metal grams** = `gross_grams * (1 - shrinkage_pct/100)`.
4. **Gross metal cost** = `gross_grams * spot_price`.
5. **Net metal cost** = `net_grams * spot_price`.
6. **Net unit cost** = `base_unit_cost + net_metal_cost` (overrides vendor unit cost if provided).
7. **Unit margin** = `list_price - net_unit_cost`.

## ABC classifications

- **Revenue ABC**: sort SKUs by total revenue, compute cumulative % of revenue.
  - `A`: cumulative <= 80%
  - `B`: cumulative <= 95%
  - `C`: remainder
- **Margin ABC**: same methodology but using gross margin dollars.

## Safety stock and reorder point

- **Safety stock** = `SERVICE_LEVEL * demand_std * sqrt(lead_time_days)` with `SERVICE_LEVEL = 1.65` (95% service level).
- **Reorder point** = `(lead_time_days * average_daily_demand) + safety_stock`.
- **Recommended order qty** = `max(reorder_point - on_hand_units, 0)` rounded up to the nearest MOQ increment.

## SKU health score (0–100)

A weighted composite:

| Component | Weight | Notes |
|-----------|--------|-------|
| Inventory coverage vs. reorder point | 30% | High score when coverage near reorder point. |
| Gross margin rate | 25% | Normalized using list price. |
| Revenue velocity | 20% | Based on percentile rank of revenue. |
| ABC consistency | 15% | Bonus if revenue & margin classes both A/B. |
| Stock aging penalty | 10% | Deduct if weeks-of-supply > 12. |

Scores are capped between 0 and 100 to make UI coloring simple.

## Prioritized lists

- **Replenish Now**: `on_hand_units < reorder_point` **and** `average_daily_demand > 0`.
- **Cut / Defer**: `gross_margin_rate < 0` **or** `weeks_of_supply > 16` **or** (`revenue_percentile < 0.2` and `gross_margin_rate < 0.15`).
- **Double-Down**: `weeks_of_supply < 3` **and** `gross_margin_rate >= 0.35` **and** `revenue_percentile >= 0.6`.

Each list includes: SKU, description, vendor, recommended quantity, target PO date (`today + lead_time_days`), projected stockout date (`today + (on_hand_units / avg_daily_demand)`), and rationale tags.

## KPI tiles

The dashboard tiles consume the following:

- **Inventory Turnover** = `(total_units_sold / average_inventory)` with average inventory approximated by `(starting_inventory + ending_inventory) / 2`. Starting inventory defaults to `on_hand_units + units_sold - receipts` (receipts omitted in demo data).
- **Days on Hand** = `on_hand_units / average_daily_demand`.
- **% In-Stock** = `SKUs with on_hand_units > 0 / total_active_skus`.
- **Gross Margin $** = `sum(gross_margin_dollars)`.
- **Aged inventory $** = `sum(on_hand_units * net_unit_cost)` for SKUs where `weeks_of_supply > 12`.

Thresholds for conditional formatting live in `compute_metrics.py` and can be tuned without changing the UI.
