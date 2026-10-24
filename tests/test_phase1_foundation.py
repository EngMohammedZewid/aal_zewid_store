import hashlib
import os
import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.db import get_all_products, get_connection, init_db, record_sale
from core.decimals import (
    DecimalInputError,
    average_cost_to_storage,
    convert_to_base_quantity,
    currency_to_storage,
    decimal_from_storage,
    quantity_to_storage,
)
from core.phase1_foundation import (
    PHASE1_VERSION,
    ProductionMigrationBlocked,
    migrate_database,
    phase1_has_posted_values,
    production_database_path,
    rollback_database,
)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def financial_rows(path):
    connection = sqlite3.connect(path)
    try:
        return {
            "products": connection.execute(
                "SELECT id, sku, cost_price, selling_price, stock_quantity, reorder_level FROM products ORDER BY id"
            ).fetchall(),
            "units": connection.execute(
                "SELECT id, product_id, pieces_per_unit, cost_price, selling_price, is_default FROM product_units ORDER BY id"
            ).fetchall(),
            "sales": connection.execute(
                "SELECT id, total_amount, discount, tax_amount FROM sales ORDER BY id"
            ).fetchall(),
            "sale_items": connection.execute(
                "SELECT id, quantity, unit_price, pieces_per_unit, base_quantity, subtotal FROM sale_items ORDER BY id"
            ).fetchall(),
            "returns": connection.execute(
                "SELECT id, quantity, unit_price, subtotal FROM sale_return_items ORDER BY id"
            ).fetchall(),
            "purchases": connection.execute(
                "SELECT id, quantity, unit_cost FROM purchase_order_items ORDER BY id"
            ).fetchall(),
        }
    finally:
        connection.close()


class DecimalPolicyTests(unittest.TestCase):
    def test_precision_rounding_and_text_storage(self):
        self.assertEqual(quantity_to_storage("1.23454"), "1.2345")
        self.assertEqual(quantity_to_storage("1.23455"), "1.2346")
        self.assertEqual(currency_to_storage("10.004"), "10.00")
        self.assertEqual(currency_to_storage("10.005"), "10.01")
        self.assertEqual(currency_to_storage("-1.225"), "-1.23")
        self.assertEqual(average_cost_to_storage("0.1234564"), "0.123456")
        self.assertEqual(average_cost_to_storage("0.1234565"), "0.123457")
        self.assertEqual(quantity_to_storage("0.1"), "0.1000")
        self.assertEqual(decimal_from_storage("0.1000"), Decimal("0.1000"))
        self.assertEqual(convert_to_base_quantity("1.25", "2.5"), Decimal("3.1250"))
        self.assertEqual(currency_to_storage(Decimal("0.10") + Decimal("0.20")), "0.30")
        helper_source = Path(__file__).resolve().parents[1].joinpath("core", "decimals.py").read_text(encoding="utf-8")
        self.assertNotIn("float(", helper_source)

    def test_sqlite_text_roundtrip_preserves_exact_decimals(self):
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE amounts (quantity TEXT, money TEXT, average_cost TEXT)")
        connection.execute(
            "INSERT INTO amounts (quantity, money, average_cost) VALUES (?, ?, ?)",
            (quantity_to_storage("1.0001"), currency_to_storage("10.10"), average_cost_to_storage("0.123456")),
        )
        quantity, money, average_cost = connection.execute(
            "SELECT quantity, money, average_cost FROM amounts"
        ).fetchone()
        self.assertEqual(quantity, "1.0001")
        self.assertEqual(money, "10.10")
        self.assertEqual(average_cost, "0.123456")
        self.assertEqual(decimal_from_storage(quantity), Decimal("1.0001"))
        self.assertEqual(decimal_from_storage(money), Decimal("10.10"))
        self.assertEqual(decimal_from_storage(average_cost), Decimal("0.123456"))
        self.assertIsInstance(quantity, str)
        self.assertIsInstance(money, str)
        self.assertIsInstance(average_cost, str)

    def test_float_is_rejected_and_sqlite_real_is_not_the_storage_format(self):
        with self.assertRaises(DecimalInputError):
            quantity_to_storage(0.1)
        with self.assertRaises(DecimalInputError):
            decimal_from_storage(0.1)
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE probe (amount REAL, amount_text TEXT)")
        connection.execute("INSERT INTO probe (amount, amount_text) VALUES (?, ?)", ("0.10", quantity_to_storage("0.10")))
        stored = connection.execute("SELECT amount_text FROM probe").fetchone()[0]
        self.assertEqual(stored, "0.1000")
        self.assertIsInstance(connection.execute("SELECT amount FROM probe").fetchone()[0], float)


class Phase1MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "legacy.db")
        self._create_legacy_database()
        self.before = financial_rows(self.db_path)
        self.before_hash = file_hash(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_legacy_database(self):
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                sku TEXT,
                name TEXT,
                cost_price REAL,
                selling_price REAL,
                stock_quantity INTEGER,
                reorder_level INTEGER
            );
            CREATE TABLE product_units (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                pieces_per_unit REAL,
                cost_price REAL,
                selling_price REAL,
                is_default INTEGER
            );
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY,
                total_amount REAL,
                discount REAL,
                tax_amount REAL
            );
            CREATE TABLE sale_items (
                id INTEGER PRIMARY KEY,
                sale_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                unit_price REAL,
                pieces_per_unit REAL,
                base_quantity REAL,
                subtotal REAL
            );
            CREATE TABLE sale_return_items (
                id INTEGER PRIMARY KEY,
                quantity INTEGER,
                unit_price REAL,
                subtotal REAL
            );
            CREATE TABLE purchase_orders (id INTEGER PRIMARY KEY, status TEXT);
            CREATE TABLE purchase_order_items (
                id INTEGER PRIMARY KEY,
                po_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                unit_cost REAL
            );
            """
        )
        connection.execute(
            "INSERT INTO products VALUES (1, 'DEC-1', 'Decimal product', 12.75, 19.5, 8, 5)"
        )
        connection.execute(
            "INSERT INTO product_units VALUES (1, 1, 2.5, 31.875, 50, 1)"
        )
        connection.execute("INSERT INTO sales VALUES (1, 19.5, 0, 1.56)")
        connection.execute("INSERT INTO sale_items VALUES (1, 1, 1, 1, 19.5, 1, 0, 19.5)")
        connection.execute("INSERT INTO sale_return_items VALUES (1, 1, 19.5, 19.5)")
        connection.execute("INSERT INTO purchase_orders VALUES (1, 'قيد الانتظار')")
        connection.execute("INSERT INTO purchase_order_items VALUES (1, 1, 1, 1, 200.5)")
        connection.commit()
        connection.close()

    def _null_snapshot_counts(self):
        connection = sqlite3.connect(self.db_path)
        try:
            sale_costs = connection.execute(
                "SELECT COUNT(*) FROM sale_items WHERE base_unit_cost IS NOT NULL OR cogs_amount IS NOT NULL OR quantity_decimal IS NOT NULL"
            ).fetchone()[0]
            return_costs = connection.execute(
                "SELECT COUNT(*) FROM sale_return_items WHERE cost_snapshot IS NOT NULL OR cogs_amount IS NOT NULL OR base_quantity_decimal IS NOT NULL"
            ).fetchone()[0]
            purchase_units = connection.execute(
                "SELECT COUNT(*) FROM purchase_order_items WHERE purchase_unit_id IS NOT NULL OR base_quantity_decimal IS NOT NULL OR base_unit_cost IS NOT NULL"
            ).fetchone()[0]
            averages = connection.execute(
                "SELECT COUNT(*) FROM products WHERE average_cost IS NOT NULL OR base_unit_id IS NOT NULL OR stock_quantity_decimal IS NOT NULL"
            ).fetchone()[0]
            conversions = connection.execute(
                "SELECT COUNT(*) FROM product_units WHERE conversion_factor_decimal IS NOT NULL"
            ).fetchone()[0]
            openings = connection.execute("SELECT COUNT(*) FROM opening_balances").fetchone()[0]
            return sale_costs, return_costs, purchase_units, averages, conversions, openings
        finally:
            connection.close()

    def test_migration_is_idempotent_and_preserves_financial_rows(self):
        migrate_database(self.db_path)
        migrate_database(self.db_path)
        self.assertEqual(self.before, financial_rows(self.db_path))
        self.assertNotEqual(self.before_hash, file_hash(self.db_path))
        self.assertEqual(self._null_snapshot_counts(), (0, 0, 0, 0, 0, 0))
        connection = sqlite3.connect(self.db_path)
        try:
            versions = connection.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version = ?",
                (PHASE1_VERSION,),
            ).fetchone()[0]
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('opening_balances', 'inventory_adjustments', 'posting_keys', 'purchase_returns')"
                )
            }
        finally:
            connection.close()
        self.assertEqual(versions, 1)
        self.assertEqual(tables, {"opening_balances", "inventory_adjustments", "posting_keys", "purchase_returns"})

    def test_rollback_recovers_the_legacy_shape_and_refuses_posted_data(self):
        migrate_database(self.db_path)
        rollback_database(self.db_path)
        self.assertEqual(self.before, financial_rows(self.db_path))
        connection = sqlite3.connect(self.db_path)
        try:
            product_columns = [row[1] for row in connection.execute("PRAGMA table_info(products)")]
            self.assertNotIn("average_cost", product_columns)
            self.assertIsNone(
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'opening_balances'"
                ).fetchone()
            )
        finally:
            connection.close()

        migrate_database(self.db_path)
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            "INSERT INTO opening_balances (product_id, quantity_decimal, average_cost, created_at) VALUES (1, '8.0000', '12.750000', '2026-10-24 00:00:00')"
        )
        connection.commit()
        connection.close()
        with self.assertRaises(RuntimeError):
            rollback_database(self.db_path)
        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM opening_balances").fetchone()[0], 1)
            self.assertIn("average_cost", [row[1] for row in connection.execute("PRAGMA table_info(products)")])
        finally:
            connection.close()

    def test_sale_posting_still_leaves_historical_cost_null(self):
        fresh = os.path.join(self.temp_dir.name, "fresh.db")
        init_db(fresh, seed_sample_data=False)
        connection = get_connection(fresh)
        connection.execute(
            "INSERT INTO products (sku, name, cost_price, selling_price, stock_quantity, reorder_level) VALUES ('SKU-1', 'Item', 4.5, 10, 5, 1)"
        )
        connection.commit()
        product_id = connection.execute("SELECT id FROM products").fetchone()["id"]
        connection.close()
        success, sale_id = record_sale(
            None,
            [{"product_id": product_id, "quantity": 1, "unit_price": 10, "subtotal": 10}],
            10.8,
            0,
            0.8,
            "كاش (نقدي)",
            db_path=fresh,
        )
        self.assertTrue(success, sale_id)
        connection = sqlite3.connect(fresh)
        try:
            row = connection.execute(
                "SELECT quantity, base_unit_cost, cogs_amount, quantity_decimal FROM sale_items WHERE sale_id = ?",
                (sale_id,),
            ).fetchone()
            product = connection.execute(
                "SELECT stock_quantity, cost_price, average_cost, stock_quantity_decimal FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()
            self.assertFalse(phase1_has_posted_values(connection.cursor()))
        finally:
            connection.close()
        self.assertEqual(row[0], 1)
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])
        self.assertIsNone(row[3])
        self.assertEqual(product[0], 4)
        self.assertEqual(product[1], 4.5)
        self.assertIsNone(product[2])
        self.assertIsNone(product[3])

    def test_production_database_is_refused_and_init_skips_it(self):
        production = production_database_path()
        before = file_hash(production)
        before_mtime = production.stat().st_mtime_ns
        with self.assertRaises(ProductionMigrationBlocked):
            migrate_database(production)
        with self.assertRaises(ProductionMigrationBlocked):
            rollback_database(production)
        self.assertEqual(before, file_hash(production))
        self.assertEqual(before_mtime, production.stat().st_mtime_ns)

        skipped = os.path.join(self.temp_dir.name, "skipped.db")
        with patch("core.db.is_production_database", return_value=True):
            init_db(skipped, seed_sample_data=False)
        connection = sqlite3.connect(skipped)
        try:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(products)")]
            opening = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'opening_balances'"
            ).fetchone()
        finally:
            connection.close()
        self.assertNotIn("average_cost", columns)
        self.assertIsNone(opening)
        self.assertEqual(before, file_hash(production))

    def test_production_guard_allows_startup_on_existing_database(self):
        existing = os.path.join(self.temp_dir.name, "existing.db")
        os.environ["STORE_MANAGER_PASSWORD"] = "manager123"
        os.environ["STORE_CASHIER_PASSWORD"] = "cashier123"
        init_db(existing, seed_sample_data=True)
        rollback_database(existing)
        stock_before = {row["sku"]: row["stock_quantity"] for row in get_all_products(existing)}
        os.environ["STORE_DB_PATH"] = existing
        from api.app import create_app

        with patch("core.db.is_production_database", return_value=True):
            with TestClient(create_app()) as client:
                login = client.post("/api/auth/login", json={"username": "manager", "password": "manager123"})
                self.assertEqual(login.status_code, 200, login.text)
                products = client.get("/api/products")
                self.assertEqual(products.status_code, 200, products.text)
                body = products.json()
        self.assertTrue(any(item["sku"] == "SKU1001" for item in body))
        stock_after = {row["sku"]: row["stock_quantity"] for row in get_all_products(existing)}
        self.assertEqual(stock_after["SKU1001"], stock_before["SKU1001"])
        self.assertEqual(set(stock_after), set(stock_before))
        connection = sqlite3.connect(existing)
        try:
            product_columns = [row[1] for row in connection.execute("PRAGMA table_info(products)")]
            sale_columns = [row[1] for row in connection.execute("PRAGMA table_info(sale_items)")]
            sale_count = connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        finally:
            connection.close()
        self.assertNotIn("average_cost", product_columns)
        self.assertNotIn("base_unit_cost", sale_columns)
        self.assertNotIn("cogs_amount", sale_columns)
        self.assertGreater(sale_count, 0)


class Phase1ApiCompatibilityTests(unittest.TestCase):
    def test_fractional_sale_quantity_is_not_accepted(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = os.path.join(temp_dir.name, "api.db")
        os.environ["STORE_DB_PATH"] = db_path
        os.environ["STORE_MANAGER_PASSWORD"] = "manager123"
        os.environ["STORE_CASHIER_PASSWORD"] = "cashier123"
        from api.app import create_app

        with TestClient(create_app()) as client:
            login = client.post("/api/auth/login", json={"username": "cashier", "password": "cashier123"})
            self.assertEqual(login.status_code, 200, login.text)
            connection = sqlite3.connect(db_path)
            try:
                sales_before = connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
            finally:
                connection.close()
            response = client.post(
                "/api/pos/sales",
                json={
                    "customer_id": None,
                    "discount": 0,
                    "tax_amount": 0.8,
                    "total_amount": 10.8,
                    "payment_method": "كاش (نقدي)",
                    "items": [{"product_id": 1, "quantity": 1.5, "unit_price": 10}],
                },
            )
        self.assertEqual(response.status_code, 422)
        connection = sqlite3.connect(db_path)
        try:
            sales_after = connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
            filled = connection.execute(
                "SELECT COUNT(*) FROM sale_items WHERE cogs_amount IS NOT NULL OR base_unit_cost IS NOT NULL"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(sales_after, sales_before)
        self.assertEqual(filled, 0)


if __name__ == "__main__":
    unittest.main()
