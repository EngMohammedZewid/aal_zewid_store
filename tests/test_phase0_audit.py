import csv
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.phase0_inventory_audit import REPORT_FILES, run_audit


SENTINEL_CUSTOMER = "SECRET_CUSTOMER_ZEWID"
SENTINEL_SUPPLIER = "SECRET_SUPPLIER_ZEWID"
SENTINEL_PHONE = "0500000099"
CURRENT_COST_NOT_HISTORICAL = "77.77"


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class Phase0AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "audit_source.db"
        self.output_dir = Path(self.temp_dir.name) / "reports"
        self._create_source()
        self.before_hash = file_hash(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_source(self):
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, phone TEXT);
            CREATE TABLE suppliers (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, email TEXT);
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                sku TEXT,
                name TEXT,
                cost_price REAL,
                selling_price REAL,
                stock_quantity REAL,
                reorder_level REAL,
                supplier_id INTEGER
            );
            CREATE TABLE units (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE product_units (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                unit_id INTEGER,
                pieces_per_unit REAL,
                cost_price REAL,
                selling_price REAL,
                is_default INTEGER,
                is_active INTEGER
            );
            CREATE TABLE purchase_orders (
                id INTEGER PRIMARY KEY,
                po_date TEXT,
                supplier_id INTEGER,
                total_cost REAL,
                status TEXT
            );
            CREATE TABLE purchase_order_items (
                id INTEGER PRIMARY KEY,
                po_id INTEGER,
                product_id INTEGER,
                quantity REAL,
                unit_cost REAL
            );
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                sale_date TEXT,
                customer_id INTEGER,
                total_amount REAL
            );
            CREATE TABLE sale_items (
                id INTEGER PRIMARY KEY,
                sale_id INTEGER,
                product_id INTEGER,
                quantity REAL,
                pieces_per_unit REAL,
                base_quantity REAL,
                unit_price REAL
            );
            CREATE TABLE sale_returns (
                id INTEGER PRIMARY KEY,
                original_sale_id INTEGER,
                return_date TEXT
            );
            CREATE TABLE sale_return_items (
                id INTEGER PRIMARY KEY,
                return_id INTEGER,
                original_sale_item_id INTEGER,
                product_id INTEGER,
                quantity REAL
            );
            """
        )
        connection.execute(
            "INSERT INTO customers (id, name, phone) VALUES (1, ?, ?)",
            (SENTINEL_CUSTOMER, SENTINEL_PHONE),
        )
        connection.execute(
            "INSERT INTO suppliers (id, name, phone) VALUES (1, ?, ?)",
            (SENTINEL_SUPPLIER, SENTINEL_PHONE),
        )
        connection.executemany(
            "INSERT INTO units (id, name) VALUES (?, ?)",
            [(1, "قطعة"), (2, "كرتون")],
        )
        connection.executemany(
            """
            INSERT INTO products
                (id, sku, name, cost_price, selling_price, stock_quantity, reorder_level, supplier_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "DEC-1", "Decimal product", "12.75", "19.50", "8.25", "5", 1),
                (2, "NONE-1", "No unit product", "4.00", "6.00", "3", "1", 1),
                (3, "NEG-1", "Negative product", CURRENT_COST_NOT_HISTORICAL, "9.00", "-2.5", "1", 1),
                (4, "MIX-1", "Converted product", "10.00", "40.00", "20", "2", 1),
            ],
        )
        connection.executemany(
            """
            INSERT INTO product_units
                (id, product_id, unit_id, pieces_per_unit, cost_price, selling_price, is_default, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, 1, 1, "2.5", "31.875", "50.00", 1, 1),
                (2, 3, 1, "0", "10.00", "9.00", 1, 1),
                (3, 3, 2, "6", "20.00", "30.00", 1, 1),
                (4, 4, 2, "6", "10.00", "40.00", 1, 1),
            ],
        )
        connection.executemany(
            "INSERT INTO purchase_orders (id, po_date, supplier_id, total_cost, status) VALUES (?, ?, ?, ?, ?)",
            [
                (1, "2026-01-15", 1, "200.50", "تم الاستلام"),
                (2, "2026-02-01", 1, "15.00", "قيد الانتظار"),
            ],
        )
        connection.executemany(
            "INSERT INTO purchase_order_items (id, po_id, product_id, quantity, unit_cost) VALUES (?, ?, ?, ?, ?)",
            [
                (1, 1, 4, "1", "200.50"),
                (2, 2, 1, "1", "15.00"),
            ],
        )
        connection.executemany(
            "INSERT INTO sales (id, sale_date, customer_id, total_amount) VALUES (?, ?, ?, ?)",
            [
                (1, "2026-03-01", 1, "50.00"),
                (2, "2026-03-02", 1, "19.50"),
                (3, "2026-03-03", 1, "9.00"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO sale_items
                (id, sale_id, product_id, quantity, pieces_per_unit, base_quantity, unit_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, 1, 4, "2", "6", "0", "40.00"),
                (2, 2, 1, "3", "1", "3", "19.50"),
                (3, 3, 3, "1", "0", None, "9.00"),
            ],
        )
        connection.executemany(
            "INSERT INTO sale_returns (id, original_sale_id, return_date) VALUES (?, ?, ?)",
            [(1, 1, "2026-03-04"), (2, 2, "2026-03-05")],
        )
        connection.executemany(
            """
            INSERT INTO sale_return_items
                (id, return_id, original_sale_item_id, product_id, quantity)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(1, 1, 1, 4, "2"), (2, 2, 2, 1, "3")],
        )
        connection.commit()
        connection.close()

    def test_audit_is_read_only_and_reports_are_explicit(self):
        source = Path(__file__).resolve().parents[1] / "tools" / "phase0_inventory_audit.py"
        module_text = source.read_text(encoding="utf-8")
        self.assertNotIn("init_db(", module_text)
        self.assertNotIn("core.db", module_text)

        result = run_audit(self.db_path, self.output_dir)

        self.assertEqual(self.before_hash, file_hash(self.db_path))
        self.assertFalse(Path(str(self.db_path) + "-wal").exists())
        self.assertFalse(Path(str(self.db_path) + "-shm").exists())

        for name in REPORT_FILES.values():
            self.assertTrue((self.output_dir / name).exists(), name)

        inventory = read_csv(self.output_dir / REPORT_FILES["inventory"])
        units = read_csv(self.output_dir / REPORT_FILES["units"])
        purchases = read_csv(self.output_dir / REPORT_FILES["purchasing"])
        sales = read_csv(self.output_dir / REPORT_FILES["sales"])
        opening = read_csv(self.output_dir / REPORT_FILES["opening"])
        summary = (self.output_dir / REPORT_FILES["summary"]).read_text(encoding="utf-8")

        decimal_product = next(row for row in inventory if row["sku"] == "DEC-1")
        self.assertEqual(decimal_product["stock_quantity"], "8.25")
        self.assertEqual(decimal_product["cost_price"], "12.75")
        self.assertEqual(decimal_product["selling_price"], "19.5")
        self.assertEqual(decimal_product["current_inventory_value"], "105.1875")
        self.assertEqual(decimal_product["active_status"], "not_supported")
        self.assertEqual(decimal_product["stock_balance_finding"], "")

        negative = next(row for row in inventory if row["sku"] == "NEG-1")
        self.assertEqual(negative["stock_quantity"], "-2.5")
        self.assertIn("negative_stock", negative["stock_balance_finding"])

        converted = next(row for row in inventory if row["sku"] == "MIX-1")
        self.assertIn("received_quantity_not_converted", converted["stock_balance_finding"])

        self.assertEqual(result["counts"]["products"], 4)
        self.assertEqual(result["counts"]["suspicious_stock"], 2)
        self.assertEqual(result["counts"]["unit_verification"], 3)
        self.assertEqual(result["counts"]["unknown_purchase_units"], 2)
        self.assertEqual(result["counts"]["sales_missing_cost"], 3)

        no_unit = next(row for row in units if row["sku"] == "NONE-1")
        self.assertEqual(no_unit["findings"], "no_units")
        self.assertEqual(no_unit["unit_name"], "")

        matching_unit = next(row for row in units if row["sku"] == "DEC-1")
        self.assertEqual(matching_unit["conversion_factor"], "2.5")
        self.assertEqual(matching_unit["unit_cost_price"], "31.875")
        self.assertEqual(matching_unit["base_cost_times_conversion"], "31.875")
        self.assertEqual(matching_unit["unit_cost_matches_base_conversion"], "yes")
        self.assertEqual(matching_unit["findings"], "")

        negative_units = [row for row in units if row["sku"] == "NEG-1"]
        self.assertTrue(all("multiple_defaults" in row["findings"] for row in negative_units))
        invalid = next(row for row in negative_units if row["conversion_status"] == "invalid")
        self.assertIn("invalid_conversion", invalid["findings"])

        mismatched = next(row for row in units if row["sku"] == "MIX-1")
        self.assertEqual(mismatched["unit_cost_price"], "10")
        self.assertEqual(mismatched["base_cost_times_conversion"], "60")
        self.assertEqual(mismatched["unit_cost_matches_base_conversion"], "no")
        self.assertNotEqual(mismatched["unit_cost_price"], mismatched["base_cost_times_conversion"])

        self.assertTrue(purchases)
        self.assertTrue(all(row["purchase_unit"] == "unknown" for row in purchases))
        self.assertTrue(all(row["purchase_unit_known"] == "no" for row in purchases))
        self.assertTrue(all(row["receipt_date"] == "" for row in purchases))
        self.assertTrue(all(row["receipt_date_available"] == "no" for row in purchases))
        received = next(row for row in purchases if row["purchase_status"] == "تم الاستلام")
        self.assertEqual(received["purchased_quantity"], "1")
        self.assertEqual(received["purchase_unit_cost"], "200.5")
        self.assertEqual(received["total_purchase_value"], "200.5")
        self.assertNotIn(received["purchase_unit"], {"piece", "carton", "قطعة", "كرتون", "1"})

        missing_base = next(row for row in sales if row["sale_item_id"] == "1")
        self.assertEqual(missing_base["base_quantity_status"], "missing")
        self.assertEqual(missing_base["restore_vs_original_base"], "differs")
        self.assertEqual(missing_base["returned_quantity"], "2")
        self.assertEqual(missing_base["expected_base_quantity_for_return"], "12")
        self.assertEqual(missing_base["historical_unit_cost"], "unavailable")
        self.assertEqual(missing_base["historical_cogs"], "unavailable")

        matched_return = next(row for row in sales if row["sale_item_id"] == "2")
        self.assertEqual(matched_return["base_quantity_status"], "present")
        self.assertEqual(matched_return["restore_vs_original_base"], "matches")

        invalid_sale = next(row for row in sales if row["sale_item_id"] == "3")
        self.assertEqual(invalid_sale["conversion_status"], "invalid")
        self.assertEqual(invalid_sale["base_quantity_status"], "missing")
        self.assertEqual(invalid_sale["historical_cogs"], "unavailable")

        sales_text = (self.output_dir / REPORT_FILES["sales"]).read_text(encoding="utf-8")
        self.assertNotIn(CURRENT_COST_NOT_HISTORICAL, sales_text)

        confirmation_fields = [
            "verified_opening_stock_base_units",
            "confirmed_base_unit",
            "declared_opening_average_cost",
            "reconciliation_notes",
            "verified_by",
            "verification_date",
        ]
        self.assertEqual(len(opening), 4)
        for row in opening:
            for field in confirmation_fields:
                self.assertEqual(row[field], "")

        for report_name in REPORT_FILES.values():
            report_text = (self.output_dir / report_name).read_text(encoding="utf-8")
            self.assertNotIn(SENTINEL_CUSTOMER, report_text)
            self.assertNotIn(SENTINEL_SUPPLIER, report_text)
            self.assertNotIn(SENTINEL_PHONE, report_text)

        self.assertIn("Products audited | 4", summary)
        self.assertIn("Products requiring unit verification | 3", summary)
        self.assertIn("Products with suspicious stock balances | 2", summary)
        self.assertIn("Purchase lines with unknown units | 2", summary)
        self.assertIn("Sales missing reliable cost information | 3", summary)
        self.assertIn("Products with no units: 1", summary)
        self.assertIn("Products with more than one default unit: 1", summary)
        self.assertIn("Products with an invalid conversion: 1", summary)
        self.assertIn("Products whose unit cost differs from base cost times conversion: 2 (2 unit rows)", summary)
        self.assertIn("Sale lines with a missing base quantity: 2", summary)
        self.assertIn("Return lines whose recorded quantity differs from the original base quantity: 1", summary)
        self.assertIn("Purchase lines inspected: 2", summary)
        self.assertIn("Critical risks", summary)

        counts = self._table_counts()
        run_audit(self.db_path, self.output_dir)
        self.assertEqual(self.before_hash, file_hash(self.db_path))
        self.assertEqual(counts, self._table_counts())

    def _table_counts(self):
        connection = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)
        try:
            rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            return {
                name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for (name,) in rows
            }
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
