"""Read-only Phase 0 inventory and financial data audit.

Opens SQLite with mode=ro, copies a consistent snapshot through the backup API,
and writes reconciliation reports. It does not call init_db, run migrations, or
post stock, cost, invoice, or opening-balance changes.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


MONEY_TOLERANCE = Decimal("0.01")
QUANTITY_TOLERANCE = Decimal("0.0000001")
UNAVAILABLE = "unavailable"
UNKNOWN_UNIT = "unknown"
NOT_SUPPORTED = "not_supported"

INVENTORY_FIELDS = [
    "product_id",
    "sku",
    "product_name",
    "stock_quantity",
    "cost_price",
    "selling_price",
    "current_inventory_value",
    "reorder_level",
    "active_status",
    "stock_balance_finding",
]

UNIT_FIELDS = [
    "product_id",
    "sku",
    "product_name",
    "unit_row_id",
    "unit_id",
    "unit_name",
    "conversion_factor",
    "unit_selling_price",
    "unit_cost_price",
    "is_default",
    "is_active",
    "default_count_for_product",
    "conversion_status",
    "base_cost_times_conversion",
    "unit_cost_matches_base_conversion",
    "findings",
]

PURCHASE_FIELDS = [
    "purchase_order_id",
    "purchase_date",
    "product_id",
    "sku",
    "product_name",
    "purchased_quantity",
    "purchase_unit_cost",
    "total_purchase_value",
    "purchase_status",
    "receipt_date",
    "receipt_date_available",
    "purchase_unit",
    "purchase_unit_known",
]

SALES_FIELDS = [
    "record_type",
    "sale_id",
    "sale_item_id",
    "sale_date",
    "product_id",
    "sku",
    "product_name",
    "sold_quantity",
    "pieces_per_unit",
    "stored_base_quantity",
    "base_quantity_status",
    "conversion_status",
    "stored_base_matches_conversion",
    "return_id",
    "return_item_id",
    "return_date",
    "returned_quantity",
    "expected_base_quantity_for_return",
    "quantity_recorded_on_return",
    "restore_vs_original_base",
    "historical_unit_cost",
    "historical_cogs",
    "historical_cogs_reason",
]

OPENING_FIELDS = [
    "product_id",
    "sku",
    "product_name",
    "system_stock_quantity",
    "system_cost_price",
    "verified_opening_stock_base_units",
    "confirmed_base_unit",
    "declared_opening_average_cost",
    "reconciliation_notes",
    "verified_by",
    "verification_date",
]

REPORT_FILES = {
    "inventory": "Product_Inventory_Audit.csv",
    "units": "Product_Units_Audit.csv",
    "purchasing": "Purchasing_Audit.csv",
    "sales": "Sales_Returns_Audit.csv",
    "opening": "Opening_Balance_Reconciliation_Template.csv",
    "summary": "Audit_Summary.md",
}

RECEIVED_STATUSES = {"تم الاستلام", "received"}
COST_SNAPSHOT_COLUMNS = ("unit_cost", "cost_price", "cogs", "cost_snapshot", "historical_cogs")
PURCHASE_UNIT_COLUMNS = ("unit_id", "unit_name", "purchase_unit", "pieces_per_unit")
RECEIPT_DATE_COLUMNS = ("receipt_date", "received_at", "received_date")


def parse_decimal(value):
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return Decimal(text)


def format_decimal(value):
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def decimals_close(left, right, tolerance):
    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance


def connect_readonly(path):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _temp_snapshot_path():
    temp_handle = tempfile.NamedTemporaryFile(prefix="phase0_audit_", suffix=".db", delete=False)
    snapshot_path = Path(temp_handle.name)
    temp_handle.close()
    return snapshot_path


def _sidecar(source, suffix):
    return Path(str(source) + suffix)


def snapshot_database(source_path):
    """Take a consistent snapshot without writing the source database.

    When no WAL, shared-memory, or rollback journal file is present, every
    committed page is in the main file, so the snapshot is a byte copy. The
    live file is not opened, which avoids creating WAL sidecars.

    When a WAL or journal is present, the SQLite backup API reads the main
    file and those transactions together. A plain copy is not used in that case.
    """
    source = Path(source_path)
    wal = _sidecar(source, "-wal")
    shm = _sidecar(source, "-shm")
    journal = _sidecar(source, "-journal")
    snapshot_path = _temp_snapshot_path()
    if not wal.exists() and not shm.exists() and not journal.exists():
        before = (source.stat().st_mtime_ns, source.stat().st_size)
        shutil.copyfile(source, snapshot_path)
        after = (source.stat().st_mtime_ns, source.stat().st_size)
        if before == after and not wal.exists() and not shm.exists() and not journal.exists():
            return snapshot_path
        remove_sqlite_family(snapshot_path)
        snapshot_path = _temp_snapshot_path()

    source_connection = connect_readonly(source)
    destination = sqlite3.connect(snapshot_path)
    try:
        source_connection.backup(destination)
    finally:
        destination.close()
        source_connection.close()
    return snapshot_path


def remove_sqlite_family(path):
    target = Path(path)
    for candidate in (target, Path(str(target) + "-wal"), Path(str(target) + "-shm")):
        if candidate.exists():
            candidate.unlink()


def table_names(connection):
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def column_names(connection, table):
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [row["name"] for row in rows]


def require_table(names, table):
    if table not in names:
        raise RuntimeError(f"Required table is missing: {table}")


def text_column(column):
    return f"CAST({column} AS TEXT)"


def yes_no(value):
    return "yes" if value else "no"


def write_csv(path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def load_products(connection):
    columns = set(column_names(connection, "products"))
    active_sql = text_column("is_active") if "is_active" in columns else "NULL"
    rows = connection.execute(
        f"""
        SELECT
            {text_column("id")} AS product_id,
            sku,
            name AS product_name,
            {text_column("stock_quantity")} AS stock_quantity,
            {text_column("cost_price")} AS cost_price,
            {text_column("selling_price")} AS selling_price,
            {text_column("reorder_level")} AS reorder_level,
            {active_sql} AS active_status
        FROM products
        ORDER BY id
        """
    ).fetchall()
    return [dict(row) for row in rows], "is_active" in columns


def load_units(connection):
    rows = connection.execute(
        f"""
        SELECT
            {text_column("pu.id")} AS unit_row_id,
            {text_column("pu.product_id")} AS product_id,
            {text_column("pu.unit_id")} AS unit_id,
            u.name AS unit_name,
            {text_column("pu.pieces_per_unit")} AS conversion_factor,
            {text_column("pu.selling_price")} AS unit_selling_price,
            {text_column("pu.cost_price")} AS unit_cost_price,
            {text_column("pu.is_default")} AS is_default,
            {text_column("pu.is_active")} AS is_active
        FROM product_units pu
        LEFT JOIN units u ON u.id = pu.unit_id
        ORDER BY pu.product_id, pu.id
        """
    ).fetchall()
    grouped = {}
    for row in rows:
        grouped.setdefault(row["product_id"], []).append(dict(row))
    return grouped


def received_product_ids(connection):
    statuses = connection.execute(
        "SELECT id, status FROM purchase_orders"
    ).fetchall()
    received_ids = {
        str(row["id"])
        for row in statuses
        if str(row["status"] or "").strip().lower() in RECEIVED_STATUSES or str(row["status"] or "").strip() in RECEIVED_STATUSES
    }
    if not received_ids:
        return set()
    placeholders = ",".join("?" for _ in received_ids)
    rows = connection.execute(
        f"SELECT DISTINCT product_id FROM purchase_order_items WHERE po_id IN ({placeholders})",
        tuple(int(po_id) for po_id in received_ids),
    ).fetchall()
    return {str(row["product_id"]) for row in rows}


def inventory_rows(products, units_by_product, received_ids, active_supported):
    rows = []
    suspicious_ids = set()
    for product in products:
        stock = parse_decimal(product["stock_quantity"])
        cost = parse_decimal(product["cost_price"])
        selling = parse_decimal(product["selling_price"])
        findings = []
        if stock is None:
            findings.append("missing_stock")
        elif stock < 0:
            findings.append("negative_stock")
        product_units = units_by_product.get(product["product_id"], [])
        has_converted_unit = any(
            (parse_decimal(unit["conversion_factor"]) or Decimal("0")) != 1
            for unit in product_units
        )
        if product["product_id"] in received_ids and has_converted_unit:
            findings.append("received_quantity_not_converted")
        if findings:
            suspicious_ids.add(product["product_id"])
        inventory_value = ""
        if stock is not None and cost is not None:
            inventory_value = format_decimal(stock * cost)
        if active_supported:
            active_status = product["active_status"] or ""
        else:
            active_status = NOT_SUPPORTED
        rows.append(
            {
                "product_id": product["product_id"],
                "sku": product["sku"] or "",
                "product_name": product["product_name"] or "",
                "stock_quantity": format_decimal(stock),
                "cost_price": format_decimal(cost),
                "selling_price": format_decimal(selling),
                "current_inventory_value": inventory_value,
                "reorder_level": format_decimal(parse_decimal(product["reorder_level"])),
                "active_status": active_status,
                "stock_balance_finding": "; ".join(findings),
            }
        )
    return rows, suspicious_ids


def unit_rows(products, units_by_product):
    rows = []
    verification_ids = set()
    for product in products:
        product_units = units_by_product.get(product["product_id"], [])
        base_cost = parse_decimal(product["cost_price"])
        default_count = sum(1 for unit in product_units if str(unit["is_default"]) == "1")
        if not product_units:
            verification_ids.add(product["product_id"])
            rows.append(_blank_unit_row(product, "no_units"))
            continue
        if default_count != 1:
            verification_ids.add(product["product_id"])
        for unit in product_units:
            conversion = parse_decimal(unit["conversion_factor"])
            unit_cost = parse_decimal(unit["unit_cost_price"])
            findings = []
            if default_count > 1:
                findings.append("multiple_defaults")
            elif default_count == 0:
                findings.append("no_default_unit")
            if conversion is None or conversion <= 0:
                conversion_status = "invalid"
                findings.append("invalid_conversion")
                comparison = ""
                matches = ""
            else:
                conversion_status = "valid"
                if base_cost is None or unit_cost is None:
                    comparison = ""
                    matches = "cannot_compare"
                    findings.append("unit_cost_cannot_be_compared")
                else:
                    expected = base_cost * conversion
                    comparison = format_decimal(expected)
                    matches = yes_no(decimals_close(unit_cost, expected, MONEY_TOLERANCE))
                    if matches == "no":
                        findings.append("unit_cost_differs_from_base_times_conversion")
            if findings:
                verification_ids.add(product["product_id"])
            rows.append(
                {
                    "product_id": product["product_id"],
                    "sku": product["sku"] or "",
                    "product_name": product["product_name"] or "",
                    "unit_row_id": unit["unit_row_id"] or "",
                    "unit_id": unit["unit_id"] or "",
                    "unit_name": unit["unit_name"] or "",
                    "conversion_factor": format_decimal(conversion),
                    "unit_selling_price": format_decimal(parse_decimal(unit["unit_selling_price"])),
                    "unit_cost_price": format_decimal(unit_cost),
                    "is_default": yes_no(str(unit["is_default"]) == "1"),
                    "is_active": yes_no(str(unit["is_active"]) == "1"),
                    "default_count_for_product": str(default_count),
                    "conversion_status": conversion_status,
                    "base_cost_times_conversion": comparison,
                    "unit_cost_matches_base_conversion": matches,
                    "findings": "; ".join(findings),
                }
            )
    return rows, verification_ids


def _blank_unit_row(product, finding):
    return {
        "product_id": product["product_id"],
        "sku": product["sku"] or "",
        "product_name": product["product_name"] or "",
        "unit_row_id": "",
        "unit_id": "",
        "unit_name": "",
        "conversion_factor": "",
        "unit_selling_price": "",
        "unit_cost_price": "",
        "is_default": "",
        "is_active": "",
        "default_count_for_product": "0",
        "conversion_status": "",
        "base_cost_times_conversion": "",
        "unit_cost_matches_base_conversion": "",
        "findings": finding,
    }


def purchase_rows(connection):
    order_columns = set(column_names(connection, "purchase_orders"))
    item_columns = set(column_names(connection, "purchase_order_items"))
    receipt_column = next((name for name in RECEIPT_DATE_COLUMNS if name in order_columns), None)
    unit_column = next((name for name in PURCHASE_UNIT_COLUMNS if name in item_columns), None)
    receipt_sql = text_column(f"po.{receipt_column}") if receipt_column else "NULL"
    unit_sql = text_column(f"poi.{unit_column}") if unit_column else "NULL"
    rows = connection.execute(
        f"""
        SELECT
            {text_column("po.id")} AS purchase_order_id,
            po.po_date AS purchase_date,
            po.status AS purchase_status,
            {text_column("poi.id")} AS purchase_item_id,
            {text_column("poi.product_id")} AS product_id,
            p.sku,
            p.name AS product_name,
            {text_column("poi.quantity")} AS purchased_quantity,
            {text_column("poi.unit_cost")} AS purchase_unit_cost,
            {receipt_sql} AS receipt_date,
            {unit_sql} AS stored_purchase_unit
        FROM purchase_order_items poi
        JOIN purchase_orders po ON po.id = poi.po_id
        JOIN products p ON p.id = poi.product_id
        ORDER BY po.id, poi.id
        """
    ).fetchall()
    exported = []
    unknown_count = 0
    for row in rows:
        quantity = parse_decimal(row["purchased_quantity"])
        unit_cost = parse_decimal(row["purchase_unit_cost"])
        stored_unit = (row["stored_purchase_unit"] or "").strip()
        if unit_column and stored_unit:
            purchase_unit = stored_unit
            known = "yes"
        else:
            purchase_unit = UNKNOWN_UNIT
            known = "no"
            unknown_count += 1
        receipt = (row["receipt_date"] or "").strip()
        exported.append(
            {
                "purchase_order_id": row["purchase_order_id"],
                "purchase_date": row["purchase_date"] or "",
                "product_id": row["product_id"],
                "sku": row["sku"] or "",
                "product_name": row["product_name"] or "",
                "purchased_quantity": format_decimal(quantity),
                "purchase_unit_cost": format_decimal(unit_cost),
                "total_purchase_value": format_decimal(quantity * unit_cost) if quantity is not None and unit_cost is not None else "",
                "purchase_status": row["purchase_status"] or "",
                "receipt_date": receipt,
                "receipt_date_available": yes_no(bool(receipt)),
                "purchase_unit": purchase_unit,
                "purchase_unit_known": known,
            }
        )
    schema = {
        "purchase_unit_column": unit_column or "",
        "receipt_date_column": receipt_column or "",
    }
    return exported, unknown_count, schema


def sales_rows(connection):
    item_columns = set(column_names(connection, "sale_items"))
    snapshot_column = next((name for name in COST_SNAPSHOT_COLUMNS if name in item_columns), None)
    snapshot_sql = text_column(f"si.{snapshot_column}") if snapshot_column else "NULL"
    base_sql = text_column("si.base_quantity") if "base_quantity" in item_columns else "NULL"
    pieces_sql = text_column("si.pieces_per_unit") if "pieces_per_unit" in item_columns else "NULL"
    sale_lines = connection.execute(
        f"""
        SELECT
            {text_column("si.id")} AS sale_item_id,
            {text_column("si.sale_id")} AS sale_id,
            s.sale_date,
            {text_column("si.product_id")} AS product_id,
            p.sku,
            p.name AS product_name,
            {text_column("si.quantity")} AS sold_quantity,
            {pieces_sql} AS pieces_per_unit,
            {base_sql} AS stored_base_quantity,
            {snapshot_sql} AS historical_unit_cost
        FROM sale_items si
        JOIN sales s ON s.id = si.sale_id
        JOIN products p ON p.id = si.product_id
        ORDER BY si.sale_id, si.id
        """
    ).fetchall()
    returns_by_item = {}
    if "sale_return_items" in table_names(connection):
        return_rows = connection.execute(
            f"""
            SELECT
                {text_column("sri.id")} AS return_item_id,
                {text_column("sri.return_id")} AS return_id,
                sr.return_date,
                {text_column("sri.original_sale_item_id")} AS sale_item_id,
                {text_column("sri.quantity")} AS returned_quantity
            FROM sale_return_items sri
            JOIN sale_returns sr ON sr.id = sri.return_id
            ORDER BY sri.id
            """
        ).fetchall()
        for row in return_rows:
            returns_by_item.setdefault(row["sale_item_id"], []).append(dict(row))

    exported = []
    missing_cost_ids = set()
    for line in sale_lines:
        sale = dict(line)
        related_returns = returns_by_item.get(sale["sale_item_id"], [])
        if not related_returns:
            exported.append(_sale_export_row(sale, None, snapshot_column, missing_cost_ids))
        else:
            for return_line in related_returns:
                exported.append(_sale_export_row(sale, return_line, snapshot_column, missing_cost_ids))
    return exported, len(missing_cost_ids), {"cost_snapshot_column": snapshot_column or ""}


def _sale_export_row(sale, return_line, snapshot_column, missing_cost_ids):
    sold = parse_decimal(sale["sold_quantity"])
    conversion = parse_decimal(sale["pieces_per_unit"])
    stored_base = parse_decimal(sale["stored_base_quantity"])
    historical_cost = parse_decimal(sale["historical_unit_cost"]) if snapshot_column else None

    if sold is not None and sold > 0 and (stored_base is None or stored_base == 0):
        base_status = "missing"
    elif stored_base is None:
        base_status = "missing"
    else:
        base_status = "present"

    if conversion is None:
        conversion_status = "missing"
    elif conversion <= 0:
        conversion_status = "invalid"
    else:
        conversion_status = "valid"

    if stored_base is not None and conversion_status == "valid" and sold is not None:
        base_matches = yes_no(decimals_close(stored_base, sold * conversion, QUANTITY_TOLERANCE))
    else:
        base_matches = "cannot_determine"

    if snapshot_column and historical_cost is not None:
        historical_unit_cost = format_decimal(historical_cost)
        historical_cogs = format_decimal(historical_cost * sold) if sold is not None else UNAVAILABLE
        historical_reason = "snapshot stored on the sale line"
    else:
        historical_unit_cost = UNAVAILABLE
        historical_cogs = UNAVAILABLE
        historical_reason = "no cost snapshot is stored on the sale line; current product cost was not used"
        missing_cost_ids.add(sale["sale_item_id"])

    returned = parse_decimal(return_line["returned_quantity"]) if return_line else None
    expected_base = ""
    restore_status = "not_a_return"
    if return_line is not None:
        expected = _expected_return_base(sold, stored_base, conversion, returned)
        if expected is None or returned is None:
            restore_status = "cannot_determine"
        elif decimals_close(expected, returned, QUANTITY_TOLERANCE):
            restore_status = "matches"
            expected_base = format_decimal(expected)
        else:
            restore_status = "differs"
            expected_base = format_decimal(expected)

    return {
        "record_type": "return_line" if return_line else "sale_line",
        "sale_id": sale["sale_id"],
        "sale_item_id": sale["sale_item_id"],
        "sale_date": sale["sale_date"] or "",
        "product_id": sale["product_id"],
        "sku": sale["sku"] or "",
        "product_name": sale["product_name"] or "",
        "sold_quantity": format_decimal(sold),
        "pieces_per_unit": format_decimal(conversion),
        "stored_base_quantity": format_decimal(stored_base),
        "base_quantity_status": base_status,
        "conversion_status": conversion_status,
        "stored_base_matches_conversion": base_matches,
        "return_id": return_line["return_id"] if return_line else "",
        "return_item_id": return_line["return_item_id"] if return_line else "",
        "return_date": return_line["return_date"] if return_line else "",
        "returned_quantity": format_decimal(returned) if return_line else "",
        "expected_base_quantity_for_return": expected_base,
        "quantity_recorded_on_return": format_decimal(returned) if return_line else "",
        "restore_vs_original_base": restore_status,
        "historical_unit_cost": historical_unit_cost,
        "historical_cogs": historical_cogs,
        "historical_cogs_reason": historical_reason,
    }


def _expected_return_base(sold, stored_base, conversion, returned):
    if returned is None:
        return None
    if stored_base is not None and stored_base > 0 and sold is not None and sold > 0:
        return (stored_base * returned) / sold
    if conversion is not None and conversion > 0:
        return returned * conversion
    return None


def opening_rows(products):
    rows = []
    for product in products:
        rows.append(
            {
                "product_id": product["product_id"],
                "sku": product["sku"] or "",
                "product_name": product["product_name"] or "",
                "system_stock_quantity": format_decimal(parse_decimal(product["stock_quantity"])),
                "system_cost_price": format_decimal(parse_decimal(product["cost_price"])),
                "verified_opening_stock_base_units": "",
                "confirmed_base_unit": "",
                "declared_opening_average_cost": "",
                "reconciliation_notes": "",
                "verified_by": "",
                "verification_date": "",
            }
        )
    return rows


def observation_counts(units, sales, purchases):
    def product_ids(code):
        return {row["product_id"] for row in units if code in row["findings"].split("; ")}

    def sale_ids(predicate):
        return {row["sale_item_id"] for row in sales if predicate(row)}

    return {
        "products_without_units": len(product_ids("no_units")),
        "products_with_multiple_defaults": len(product_ids("multiple_defaults")),
        "products_with_invalid_conversion": len(product_ids("invalid_conversion")),
        "products_with_unit_cost_difference": len(product_ids("unit_cost_differs_from_base_times_conversion")),
        "unit_rows_with_cost_difference": sum(
            1 for row in units if "unit_cost_differs_from_base_times_conversion" in row["findings"].split("; ")
        ),
        "sales_missing_base_quantity": len(sale_ids(lambda row: row["base_quantity_status"] == "missing")),
        "sales_with_invalid_conversion": len(sale_ids(lambda row: row["conversion_status"] == "invalid")),
        "returns_that_differ_from_base": sum(1 for row in sales if row["restore_vs_original_base"] == "differs"),
        "returns_whose_base_cannot_be_determined": sum(
            1 for row in sales if row["restore_vs_original_base"] == "cannot_determine"
        ),
        "purchase_lines": len(purchases),
    }


def render_summary(db_path, counts, schema_notes, observed):
    risks = [
        "Historical sale cost is not reconstructable where the sale line has no cost snapshot. Current product cost must not be copied back onto old sales.",
        "A purchase quantity without a stored unit cannot be converted. A quantity of 1 is not evidence of a piece, a carton, or any other unit.",
        "Received purchase quantities were posted without a unit conversion, while sales remove base quantity. Stock for products sold in a converted unit needs a physical count before it is trusted.",
        "Return lines store a selling-unit quantity and do not store the base quantity that should re-enter stock. Lines marked differs or cannot_determine need review before migration.",
        "Unit cost is stored independently of base cost times conversion. A mismatch is a finding, not a corrected cost.",
        "Products with no unit, more than one default unit, no default unit, or an invalid conversion have no reliable base unit yet.",
        "Opening balances in the reconciliation template are blank. This audit did not post stock or average cost.",
    ]
    if not schema_notes["active_supported"]:
        risks.append("Products have no active/inactive column. Active status is reported as not_supported.")
    if not schema_notes["purchase_unit_column"]:
        risks.append(
            "purchase_order_items has no unit column. "
            f"{observed['purchase_lines']} purchase lines were inspected, and a missing unit is left unknown."
        )
    if not schema_notes["receipt_date_column"]:
        risks.append("purchase_orders has no receipt-date column. Receipt status alone does not provide a receipt timestamp.")
    if not schema_notes["cost_snapshot_column"]:
        risks.append("sale_items has no cost snapshot column. Every existing sale is missing reliable historical cost.")

    lines = [
        "# Phase 0 Inventory and Financial Data Audit",
        "",
        "This report is read-only. No migration ran, and no stock, cost, invoice, or opening balance was posted.",
        "",
        f"- Database: `{db_path}`",
        "- Access: consistent snapshot. A checkpointed database is copied without opening it. A database with a WAL or rollback journal is read with SQLite mode=ro through the backup API.",
        f"- Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "- Customer and supplier contact details were not exported.",
        "",
        "## Counts",
        "",
        "| Item | Count |",
        "| --- | ---: |",
        f"| Products audited | {counts['products']} |",
        f"| Products requiring unit verification | {counts['unit_verification']} |",
        f"| Products with suspicious stock balances | {counts['suspicious_stock']} |",
        f"| Purchase lines with unknown units | {counts['unknown_purchase_units']} |",
        f"| Sales missing reliable cost information | {counts['sales_missing_cost']} |",
        "",
        "## Observed findings",
        "",
        f"- Products with no units: {observed['products_without_units']}",
        f"- Products with more than one default unit: {observed['products_with_multiple_defaults']}",
        f"- Products with an invalid conversion: {observed['products_with_invalid_conversion']}",
        f"- Products whose unit cost differs from base cost times conversion: {observed['products_with_unit_cost_difference']} ({observed['unit_rows_with_cost_difference']} unit rows)",
        f"- Sale lines with a missing base quantity: {observed['sales_missing_base_quantity']}",
        f"- Sale lines with an invalid conversion: {observed['sales_with_invalid_conversion']}",
        f"- Return lines whose recorded quantity differs from the original base quantity: {observed['returns_that_differ_from_base']}",
        f"- Return lines whose original base quantity cannot be determined: {observed['returns_whose_base_cannot_be_determined']}",
        f"- Purchase lines inspected: {observed['purchase_lines']}",
        "",
        "## Critical risks that must be resolved before migration",
        "",
    ]
    lines.extend(f"- {risk}" for risk in risks)
    lines.extend(
        [
            "",
            "## Report notes",
            "",
            "- `current_inventory_value` is the current header cost multiplied by the current stock quantity. It is not an audited opening value.",
            "- `base_cost_times_conversion` is a comparison figure. It is not a replacement unit cost.",
            "- `historical_cogs` is `unavailable` when the sale line has no stored cost. The blank is intentional.",
            "- `purchase_unit` is `unknown` when the purchase line has no stored unit. The audit does not infer one.",
            "- System stock and system cost on the opening template are reference values only. The confirmation fields are left blank for a physical count.",
            "",
        ]
    )
    return "\n".join(lines)


def run_audit(db_path, output_dir):
    source = Path(db_path)
    if not source.exists():
        raise FileNotFoundError(f"Database not found: {source}")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    snapshot_path = snapshot_database(source)
    try:
        connection = connect_readonly(snapshot_path)
        try:
            names = table_names(connection)
            for table in ("products", "product_units", "units", "purchase_orders", "purchase_order_items", "sales", "sale_items"):
                require_table(names, table)
            products, active_supported = load_products(connection)
            units_by_product = load_units(connection)
            received_ids = received_product_ids(connection)
            inventory, suspicious_ids = inventory_rows(products, units_by_product, received_ids, active_supported)
            units, verification_ids = unit_rows(products, units_by_product)
            purchases, unknown_units, purchase_schema = purchase_rows(connection)
            sales, missing_cost, sales_schema = sales_rows(connection)
            opening = opening_rows(products)
        finally:
            connection.close()
    finally:
        remove_sqlite_family(snapshot_path)

    write_csv(destination / REPORT_FILES["inventory"], INVENTORY_FIELDS, inventory)
    write_csv(destination / REPORT_FILES["units"], UNIT_FIELDS, units)
    write_csv(destination / REPORT_FILES["purchasing"], PURCHASE_FIELDS, purchases)
    write_csv(destination / REPORT_FILES["sales"], SALES_FIELDS, sales)
    write_csv(destination / REPORT_FILES["opening"], OPENING_FIELDS, opening)

    counts = {
        "products": len(products),
        "unit_verification": len(verification_ids),
        "suspicious_stock": len(suspicious_ids),
        "unknown_purchase_units": unknown_units,
        "sales_missing_cost": missing_cost,
    }
    schema_notes = {
        "active_supported": active_supported,
        "purchase_unit_column": purchase_schema["purchase_unit_column"],
        "receipt_date_column": purchase_schema["receipt_date_column"],
        "cost_snapshot_column": sales_schema["cost_snapshot_column"],
    }
    observed = observation_counts(units, sales, purchases)
    summary = render_summary(source.resolve(), counts, schema_notes, observed)
    (destination / REPORT_FILES["summary"]).write_text(summary, encoding="utf-8")
    return {"output_dir": str(destination.resolve()), "counts": counts, "schema": schema_notes}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only Phase 0 inventory and financial data audit")
    parser.add_argument("--db-path", required=True, help="SQLite database to audit. A backup path is preferred.")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for the CSV and Markdown reports. Defaults to exports/phase0_audit_<timestamp>.",
    )
    args = parser.parse_args(argv)
    output_dir = args.output_dir
    if not output_dir:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("exports") / f"phase0_audit_{stamp}"
    result = run_audit(args.db_path, output_dir)
    print(f"Audit reports written to {result['output_dir']}")
    for key, value in result["counts"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
