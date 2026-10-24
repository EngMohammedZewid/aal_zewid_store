# Phase 0 Inventory and Financial Data Audit

This report is read-only. No migration ran, and no stock, cost, invoice, or opening balance was posted.

- Database: `D:\My work\aal_zewid_store_webApp\aal_zewid_store-1\store.db`
- Access: consistent snapshot. A checkpointed database is copied without opening it. A database with a WAL or rollback journal is read with SQLite mode=ro through the backup API.
- Generated at: 2026-10-24 14:29:57 UTC
- Customer and supplier contact details were not exported.

## Counts

| Item | Count |
| --- | ---: |
| Products audited | 180 |
| Products requiring unit verification | 9 |
| Products with suspicious stock balances | 0 |
| Purchase lines with unknown units | 0 |
| Sales missing reliable cost information | 1 |

## Observed findings

- Products with no units: 0
- Products with more than one default unit: 0
- Products with an invalid conversion: 0
- Products whose unit cost differs from base cost times conversion: 9 (16 unit rows)
- Sale lines with a missing base quantity: 0
- Sale lines with an invalid conversion: 0
- Return lines whose recorded quantity differs from the original base quantity: 0
- Return lines whose original base quantity cannot be determined: 0
- Purchase lines inspected: 0

## Critical risks that must be resolved before migration

- Historical sale cost is not reconstructable where the sale line has no cost snapshot. Current product cost must not be copied back onto old sales.
- A purchase quantity without a stored unit cannot be converted. A quantity of 1 is not evidence of a piece, a carton, or any other unit.
- Received purchase quantities were posted without a unit conversion, while sales remove base quantity. Stock for products sold in a converted unit needs a physical count before it is trusted.
- Return lines store a selling-unit quantity and do not store the base quantity that should re-enter stock. Lines marked differs or cannot_determine need review before migration.
- Unit cost is stored independently of base cost times conversion. A mismatch is a finding, not a corrected cost.
- Products with no unit, more than one default unit, no default unit, or an invalid conversion have no reliable base unit yet.
- Opening balances in the reconciliation template are blank. This audit did not post stock or average cost.
- Products have no active/inactive column. Active status is reported as not_supported.
- purchase_order_items has no unit column. 0 purchase lines were inspected, and a missing unit is left unknown.
- purchase_orders has no receipt-date column. Receipt status alone does not provide a receipt timestamp.
- sale_items has no cost snapshot column. Every existing sale is missing reliable historical cost.

## Report notes

- `current_inventory_value` is the current header cost multiplied by the current stock quantity. It is not an audited opening value.
- `base_cost_times_conversion` is a comparison figure. It is not a replacement unit cost.
- `historical_cogs` is `unavailable` when the sale line has no stored cost. The blank is intentional.
- `purchase_unit` is `unknown` when the purchase line has no stored unit. The audit does not infer one.
- System stock and system cost on the opening template are reference values only. The confirmation fields are left blank for a physical count.
