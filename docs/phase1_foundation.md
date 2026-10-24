# Phase 1 — Database and Decimal Foundation

Phase 1 prepares decimal storage and empty supporting tables. It does not change how sales, purchases, returns, stock, prices, or profit are calculated.

## Decimal storage

SQLite has no fixed-precision DECIMAL. `NUMERIC` and `REAL` columns store non-integers as IEEE-754 binary floating point. Phase 1 does not rely on that for the new values.

New decimal values use `TEXT`. Python `Decimal` is quantized, then written with `format(value, "f")`. The text is read back with `Decimal`. `float` and `bool` are rejected. See `core/decimals.py`.

| Use | Decimal places | Quantum | Rounding |
| --- | --- | --- | --- |
| Quantity and conversion factor | 4 | `0.0001` | half up, away from zero |
| Currency | 2 | `0.01` | half up, away from zero |
| Average cost | 6 | `0.000001` | half up, away from zero |

Existing `INTEGER` and `REAL` columns stay the live columns. `round_amount` and `calculate_base_quantity` still return binary floats. They are not rewired in this phase, so current invoices do not change.

## Schema added by migration 19

Nullable columns, with no defaults and no backfill:

- `products.base_unit_id` — intended reference `units.id`, not assigned
- `products.stock_quantity_decimal` — future on-hand quantity, left null so it cannot drift from `stock_quantity`
- `products.reorder_level_decimal` — left null
- `products.average_cost` — future weighted average, left null; current `cost_price` is not copied
- `product_units.conversion_factor_decimal` — future exact conversion; `pieces_per_unit`, `cost_price`, and `selling_price` are not copied or overwritten
- `sale_items.quantity_decimal`, `base_quantity_decimal`, `base_unit_cost`, `cogs_amount` — snapshots stay null
- `sale_return_items.quantity_decimal`, `base_quantity_decimal`, `cost_snapshot`, `cogs_amount` — stay null
- `purchase_order_items.purchase_unit_id`, `quantity_decimal`, `conversion_factor_decimal`, `base_quantity_decimal`, `base_unit_cost` — stay null; `purchase_unit_id` will refer to `product_units.id` when purchasing is activated

Empty tables:

- `opening_balances`
- `inventory_adjustments`
- `posting_keys`
- `purchase_returns`

No rows are inserted. New integer columns do not declare SQL foreign keys, because SQLite cannot drop a column that is part of a foreign key. The new tables do declare foreign keys.

`init_db` skips migration 19 when the database path is the repository `store.db`. Starting the API against that file does not apply Phase 1. `migrate_database` and `rollback_database` refuse the same path.

## Rollback

Production rollback is file recovery, not a down migration:

1. Stop the application.
2. Restore the snapshot taken before migration. Use a SQLite backup when a WAL file exists; do not copy `store.db` alone in that case.
3. Run the code from before Phase 1.

On a development or test database that has not posted any Phase 1 values, `core.phase1_foundation.rollback_database` drops the new indexes, tables, and columns and deletes schema version 19. Rollback refuses to run if any new column is non-null or any new table has a row. Do not use that function on `store.db`.

## Work left for Phase 2

Phase 2 is the quantity and conversion cutover. It is not enabled.

- Stop truncating quantities with `int(...)` in `record_sale`.
- Accept fractional quantities in `SaleItemIn`, `ReturnItemIn`, `POItemIn`, `StockIn`, and `ProductIn` (`api/schemas.py`). The POS page still requires an integer quantity, and the inventory page still sends numeric unit fields through `Number(...)`.
- Replace `calculate_base_quantity`, which multiplies binary floats and rounds to currency precision, with `convert_to_base_quantity`.
- Replace `ensure_product_unit`, which stores `pieces_per_unit` through `float`.
- Write `stock_quantity_decimal` and the sale, return, and purchase decimal columns in the same transaction that stops writing the old quantity columns. Do not keep two live quantity columns.
- Confirm `base_unit_id` only from the Phase 0 reconciliation. Do not guess a purchase unit, and do not treat quantity 1 as a piece or a carton.
- Review the 9 products whose unit cost differs from header cost times conversion before a base unit is trusted.
- Keep `base_unit_cost` and `cogs_amount` null on the existing sale. Do not recalculate that invoice.
- Post opening stock only from a signed `opening_balances` row. Leave `average_cost` null until that document exists.
- Desktop `ui/pos_view.py` and `ui/inventory_view.py` use the same integer and float unit math and need the same cutover.

## Work left for Phase 3

Phase 3 is weighted average cost and profit. It is not enabled.

- Update `average_cost` only when a receipt or a signed opening balance is posted. A quantity-only adjustment must snapshot the average and must not change it.
- Persist sale and return COGS from the snapshot in the new columns. `get_financial_overview` currently uses `sale_items.quantity * products.cost_price`, which is the current header cost and the selling-unit quantity.
- Customer returns must restore base quantity and reverse the snapshotted COGS. `record_sale_return` currently adds the selling-unit `quantity` back to `stock_quantity`.
- Purchase receipts must store the purchase unit, conversion, base quantity, and base-unit acquisition cost. `mark_po_received` currently adds the raw integer quantity and ignores `unit_cost`.
- Purchase returns remove stock at the current average and record the supplier refund and the variance separately. There is no purchase-return posting yet.
- Inventory adjustments need previous quantity, new quantity, difference, average snapshot, value, reason, user, and time, with a `posting_keys` row in the same `BEGIN IMMEDIATE` transaction.
- Tax remains 8% of the pre-discount subtotal. Profit must continue to exclude collected tax.
