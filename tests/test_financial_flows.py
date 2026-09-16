import os
import sqlite3
import tempfile
import unittest

from core.db import (
    add_expense,
    calculate_session_summary,
    close_pos_session,
    delete_expense,
    ensure_product_unit,
    get_active_pos_session,
    get_connection,
    get_generic_customer_id,
    get_pos_session,
    get_product_units,
    get_returnable_sale_items,
    get_sale_returns,
    get_session_expenses,
    init_db,
    open_pos_session,
    preview_sale_return,
    record_sale,
    record_sale_return,
)


class StoreDbTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_store.db")
        init_db(self.db_path, seed_sample_data=False)
        self.seed_basic_data()

    def tearDown(self):
        self.temp_dir.cleanup()

    def seed_basic_data(self):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO categories (name, description) VALUES (?, ?)", ("عام", "عام"))
        cursor.execute(
            "INSERT INTO suppliers (name, contact_person, phone, email, address) VALUES (?, ?, ?, ?, ?)",
            ("المورد", "مسؤول", "0500000000", "supplier@example.com", "الرياض"),
        )
        supplier_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity, reorder_level, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("SKU-A", "منتج أ", 1, 60.0, 100.0, 100, 5, supplier_id),
        )
        self.product_a_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity, reorder_level, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("SKU-B", "منتج ب", 1, 40.0, 80.0, 100, 5, supplier_id),
        )
        self.product_b_id = cursor.lastrowid
        cursor.execute("INSERT INTO customers (name, phone, email, loyalty_points) VALUES (?, ?, ?, ?)", ("عميل عام (نقدي)", "غير محدد", "N/A", 0))
        self.generic_customer_id = cursor.lastrowid
        cursor.execute("INSERT INTO customers (name, phone, email, loyalty_points) VALUES (?, ?, ?, ?)", ("عميل اختبار", "0551111111", "customer@example.com", 0))
        self.customer_id = cursor.lastrowid
        conn.commit()
        conn.close()

    def open_session(self, opening_balance=500.0):
        success, result = open_pos_session(opening_balance, db_path=self.db_path)
        self.assertTrue(success, result)
        return result

    def record_sale_helper(self, session_id, items, payment_method="كاش (نقدي)", customer_id=None, discount=0.0, tax_amount=0.0):
        total_amount = sum(item["subtotal"] for item in items) + tax_amount - discount
        success, result = record_sale(
            customer_id if customer_id is not None else self.customer_id,
            items,
            total_amount,
            discount,
            tax_amount,
            payment_method,
            session_id=session_id,
            db_path=self.db_path,
        )
        self.assertTrue(success, result)
        return result

    def get_stock(self, product_id):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id=?", (product_id,))
        stock = cursor.fetchone()[0]
        conn.close()
        return stock

    def get_customer_points(self, customer_id=None):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT loyalty_points FROM customers WHERE id=?", (customer_id or self.customer_id,))
        points = cursor.fetchone()[0]
        conn.close()
        return points

    def test_product_units_store_user_defined_conversion_and_default_piece_unit(self):
        default_units = get_product_units(self.product_a_id, db_path=self.db_path)
        self.assertTrue(default_units)
        default_piece = next((unit for unit in default_units if unit["is_default"]), None)
        self.assertIsNotNone(default_piece)
        self.assertEqual(default_piece["pieces_per_unit"], 1.0)

        success, result = ensure_product_unit(
            self.product_a_id,
            "Carton",
            240,
            cost_price=250,
            selling_price=350,
            db_path=self.db_path,
        )
        self.assertTrue(success, result)

        units = get_product_units(self.product_a_id, db_path=self.db_path)
        carton = next((unit for unit in units if unit["unit_name"] == "Carton"), None)
        self.assertIsNotNone(carton)
        self.assertEqual(carton["pieces_per_unit"], 240.0)
        self.assertEqual(carton["selling_price"], 350.0)

    def test_sale_uses_product_unit_conversion_for_stock_and_price(self):
        default_units = get_product_units(self.product_a_id, db_path=self.db_path)
        base_unit = next((unit for unit in default_units if unit["is_default"]), None)
        self.assertIsNotNone(base_unit)

        success, result = ensure_product_unit(
            self.product_a_id,
            "Carton",
            500,
            cost_price=2500,
            selling_price=3500,
            db_path=self.db_path,
        )
        self.assertTrue(success, result)

        carton = next((unit for unit in get_product_units(self.product_a_id, db_path=self.db_path) if unit["unit_name"] == "Carton"), None)
        self.assertIsNotNone(carton)

        session_id = self.open_session(0)
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity=? WHERE id=?", (2000, self.product_a_id))
        conn.commit()
        conn.close()

        success, sale_id = record_sale(
            self.customer_id,
            [{
                "product_id": self.product_a_id,
                "product_unit_id": carton["id"],
                "unit_name": "Carton",
                "quantity": 3,
                "unit_price": 3500.0,
                "pieces_per_unit": 500,
                "base_quantity": 1500,
                "subtotal": 10500.0,
            }],
            10500.0,
            0.0,
            0.0,
            "كاش (نقدي)",
            session_id=session_id,
            db_path=self.db_path,
        )
        self.assertTrue(success, sale_id)
        self.assertEqual(self.get_stock(self.product_a_id), 500)

    def test_product_unit_stock_validation_rejects_quantity_exceeding_converted_inventory(self):
        success, result = ensure_product_unit(
            self.product_a_id,
            "Carton",
            240,
            cost_price=200,
            selling_price=300,
            db_path=self.db_path,
        )
        self.assertTrue(success, result)

        carton = next((unit for unit in get_product_units(self.product_a_id, db_path=self.db_path) if unit["unit_name"] == "Carton"), None)
        self.assertIsNotNone(carton)

        session_id = self.open_session(0)
        success, message = record_sale(
            self.customer_id,
            [{
                "product_id": self.product_a_id,
                "product_unit_id": carton["id"],
                "unit_name": "Carton",
                "quantity": 5,
                "unit_price": 300.0,
                "pieces_per_unit": 240,
                "base_quantity": 1200,
                "subtotal": 1500.0,
            }],
            1500.0,
            0.0,
            0.0,
            "كاش (نقدي)",
            session_id=session_id,
            db_path=self.db_path,
        )
        self.assertFalse(success)
        self.assertIn("غير متوفرة", message)

    def test_open_session_validation_and_single_active_session(self):
        success, message = open_pos_session(-1, db_path=self.db_path)
        self.assertFalse(success)
        self.assertEqual(message, "الرصيد الافتتاحي غير صحيح")

        success, message = open_pos_session("abc", db_path=self.db_path)
        self.assertFalse(success)
        self.assertEqual(message, "الرصيد الافتتاحي غير صحيح")

        session_id = self.open_session(500)
        active = get_active_pos_session(self.db_path)
        self.assertIsNotNone(active)
        self.assertEqual(active["id"], session_id)

        success, message = open_pos_session(100, db_path=self.db_path)
        self.assertFalse(success)
        self.assertEqual(message, "يوجد بالفعل جلسة مفتوحة")

    def test_session_close_balanced_shortage_and_increase(self):
        session_id = self.open_session(500)
        sale_id = self.record_sale_helper(session_id, [{"product_id": self.product_a_id, "quantity": 1, "unit_price": 1000.0, "subtotal": 1000.0}], customer_id=self.generic_customer_id)
        self.assertIsInstance(sale_id, int)
        success, result = close_pos_session(session_id, 1500, db_path=self.db_path)
        self.assertTrue(success, result)
        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["difference"], 0.0)

        session_id = self.open_session(500)
        self.record_sale_helper(session_id, [{"product_id": self.product_a_id, "quantity": 1, "unit_price": 200.0, "subtotal": 200.0}], customer_id=self.generic_customer_id)
        success, result = close_pos_session(session_id, 650, db_path=self.db_path)
        self.assertTrue(success, result)
        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["difference"], -50.0)

        session_id = self.open_session(500)
        self.record_sale_helper(session_id, [{"product_id": self.product_a_id, "quantity": 1, "unit_price": 200.0, "subtotal": 200.0}], customer_id=self.generic_customer_id)
        success, result = close_pos_session(session_id, 725, db_path=self.db_path)
        self.assertTrue(success, result)
        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["difference"], 25.0)

    def test_cash_and_card_sales_affect_expected_cash_and_closed_sessions_reject_sales(self):
        session_id = self.open_session(500)
        self.record_sale_helper(session_id, [{"product_id": self.product_a_id, "quantity": 1, "unit_price": 1000.0, "subtotal": 1000.0}], payment_method="كاش (نقدي)", customer_id=self.generic_customer_id)
        self.record_sale_helper(session_id, [{"product_id": self.product_b_id, "quantity": 1, "unit_price": 400.0, "subtotal": 400.0}], payment_method="بطاقة ائتمان", customer_id=self.generic_customer_id)

        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["cash_sales"], 1000.0)
        self.assertEqual(summary["card_sales"], 400.0)
        self.assertEqual(summary["expected_cash_balance"], 1500.0)

        success, result = close_pos_session(session_id, 1500, db_path=self.db_path)
        self.assertTrue(success, result)
        success, message = record_sale(
            self.generic_customer_id,
            [{"product_id": self.product_a_id, "quantity": 1, "unit_price": 10.0, "subtotal": 10.0}],
            10.0,
            0.0,
            0.0,
            "كاش (نقدي)",
            session_id=session_id,
            db_path=self.db_path,
        )
        self.assertFalse(success)
        self.assertEqual(message, "لا يمكن تسجيل عملية على جلسة مغلقة")

    def test_expenses_affect_cash_by_payment_type_and_cannot_delete_after_close(self):
        session_id = self.open_session(500)
        success, expense_id = add_expense(session_id, "نقل وشحن", "شحنة", 100, payment_method="كاش", db_path=self.db_path)
        self.assertTrue(success, expense_id)
        success, second_expense_id = add_expense(session_id, "صيانة", "صيانة جهاز", 50, payment_method="بطاقة", db_path=self.db_path)
        self.assertTrue(success, second_expense_id)

        expenses = get_session_expenses(session_id, db_path=self.db_path)
        self.assertEqual(len(expenses), 2)
        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["cash_expenses"], 100.0)
        self.assertEqual(summary["non_cash_expenses"], 50.0)
        self.assertEqual(summary["expected_cash_balance"], 400.0)

        success, message = add_expense(session_id, "صيانة", "محاولة", 0, db_path=self.db_path)
        self.assertFalse(success)
        self.assertEqual(message, "يجب أن يكون مبلغ المصروف أكبر من صفر")

        success, result = close_pos_session(session_id, 400, db_path=self.db_path)
        self.assertTrue(success, result)

        success, message = delete_expense(expense_id, db_path=self.db_path)
        self.assertFalse(success)
        self.assertEqual(message, "لا يمكن تعديل عملية مالية بعد إغلاق الجلسة")

    def test_return_partial_and_multiple_partial_quantities_restore_stock(self):
        session_id = self.open_session(0)
        sale_id = self.record_sale_helper(
            session_id,
            [{"product_id": self.product_a_id, "quantity": 5, "unit_price": 100.0, "subtotal": 500.0}],
            payment_method="كاش (نقدي)",
        )
        self.assertEqual(self.get_stock(self.product_a_id), 95)

        items = get_returnable_sale_items(sale_id, db_path=self.db_path)
        success, result = record_sale_return(
            sale_id,
            session_id,
            [{"original_sale_item_id": items[0]["id"], "quantity": 2}],
            "كاش",
            reason="طلب العميل",
            db_path=self.db_path,
        )
        self.assertTrue(success, result)
        self.assertEqual(self.get_stock(self.product_a_id), 97)

        items = get_returnable_sale_items(sale_id, db_path=self.db_path)
        self.assertEqual(items[0]["available_return_quantity"], 3)

        success, message = record_sale_return(
            sale_id,
            session_id,
            [{"original_sale_item_id": items[0]["id"], "quantity": 4}],
            "كاش",
            reason="طلب العميل",
            db_path=self.db_path,
        )
        self.assertFalse(success)
        self.assertEqual(message, "الكمية المرتجعة أكبر من الكمية المتاحة")

        success, result = record_sale_return(
            sale_id,
            session_id,
            [{"original_sale_item_id": items[0]["id"], "quantity": 3}],
            "بطاقة ائتمان",
            reason="طلب العميل",
            db_path=self.db_path,
        )
        self.assertTrue(success, result)
        self.assertEqual(self.get_stock(self.product_a_id), 100)

    def test_return_multiple_products_preserves_original_sale_and_links_returns(self):
        session_id = self.open_session(0)
        sale_id = self.record_sale_helper(
            session_id,
            [
                {"product_id": self.product_a_id, "quantity": 2, "unit_price": 100.0, "subtotal": 200.0},
                {"product_id": self.product_b_id, "quantity": 1, "unit_price": 80.0, "subtotal": 80.0},
            ],
            payment_method="كاش (نقدي)",
        )

        items = get_returnable_sale_items(sale_id, db_path=self.db_path)
        payload = [{"original_sale_item_id": item["id"], "quantity": 1} for item in items]
        success, return_id = record_sale_return(sale_id, session_id, payload, "كاش", reason="خطأ في الفاتورة", db_path=self.db_path)
        self.assertTrue(success, return_id)

        returns = get_sale_returns(sale_id=sale_id, db_path=self.db_path)
        self.assertEqual(len(returns), 1)
        self.assertEqual(returns[0]["original_sale_id"], sale_id)

        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM sale_items WHERE sale_id=? ORDER BY id", (sale_id,))
        original_quantities = [row[0] for row in cursor.fetchall()]
        conn.close()
        self.assertEqual(original_quantities, [2, 1])
        self.assertEqual(self.get_stock(self.product_a_id), 99)
        self.assertEqual(self.get_stock(self.product_b_id), 100)

    def test_loyalty_points_decrease_and_never_become_negative(self):
        session_id = self.open_session(0)
        sale_id = self.record_sale_helper(
            session_id,
            [{"product_id": self.product_a_id, "quantity": 2, "unit_price": 100.0, "subtotal": 200.0}],
            payment_method="كاش (نقدي)",
            customer_id=self.customer_id,
        )
        self.assertEqual(self.get_customer_points(), 20)

        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE customers SET loyalty_points = 1 WHERE id=?", (self.customer_id,))
        conn.commit()
        conn.close()

        items = get_returnable_sale_items(sale_id, db_path=self.db_path)
        success, result = record_sale_return(sale_id, session_id, [{"original_sale_item_id": items[0]["id"], "quantity": 2}], "كاش", reason="طلب العميل", db_path=self.db_path)
        self.assertTrue(success, result)
        self.assertEqual(self.get_customer_points(), 0)

    def test_cash_return_affects_expected_cash_and_non_cash_return_does_not(self):
        session_id = self.open_session(0)
        sale_id = self.record_sale_helper(
            session_id,
            [{"product_id": self.product_a_id, "quantity": 5, "unit_price": 100.0, "subtotal": 500.0}],
            payment_method="كاش (نقدي)",
            customer_id=self.generic_customer_id,
        )
        items = get_returnable_sale_items(sale_id, db_path=self.db_path)

        success, result = record_sale_return(sale_id, session_id, [{"original_sale_item_id": items[0]["id"], "quantity": 1}], "بطاقة ائتمان", reason="طلب العميل", db_path=self.db_path)
        self.assertTrue(success, result)
        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["expected_cash_balance"], 500.0)

        items = get_returnable_sale_items(sale_id, db_path=self.db_path)
        success, result = record_sale_return(sale_id, session_id, [{"original_sale_item_id": items[0]["id"], "quantity": 2}], "كاش", reason="طلب العميل", db_path=self.db_path)
        self.assertTrue(success, result)
        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["cash_returns"], 200.0)
        self.assertEqual(summary["expected_cash_balance"], 300.0)

    def test_return_preview_uses_proportional_tax_discount_and_caps_total(self):
        session_id = self.open_session(0)
        sale_id = self.record_sale_helper(
            session_id,
            [{"product_id": self.product_a_id, "quantity": 5, "unit_price": 100.0, "subtotal": 500.0}],
            payment_method="كاش (نقدي)",
            customer_id=self.customer_id,
            discount=25.0,
            tax_amount=40.0,
        )
        items = get_returnable_sale_items(sale_id, db_path=self.db_path)
        sale_item_id = items[0]["id"]

        success, preview = preview_sale_return(sale_id, [{"original_sale_item_id": sale_item_id, "quantity": 2}], "كاش", db_path=self.db_path)
        self.assertTrue(success, preview)
        self.assertEqual(preview["totals"]["subtotal"], 200.0)
        self.assertEqual(preview["totals"]["tax_amount"], 16.0)
        self.assertEqual(preview["totals"]["discount_amount"], 10.0)
        self.assertEqual(preview["totals"]["total_amount"], 206.0)

        success, result = record_sale_return(sale_id, session_id, [{"original_sale_item_id": sale_item_id, "quantity": 2}], "كاش", reason="طلب العميل", db_path=self.db_path)
        self.assertTrue(success, result)
        success, result = record_sale_return(sale_id, session_id, [{"original_sale_item_id": sale_item_id, "quantity": 2}], "كاش", reason="طلب العميل", db_path=self.db_path)
        self.assertTrue(success, result)
        success, preview = preview_sale_return(sale_id, [{"original_sale_item_id": sale_item_id, "quantity": 1}], "كاش", db_path=self.db_path)
        self.assertTrue(success, preview)
        self.assertEqual(preview["totals"]["tax_amount"], 8.0)
        self.assertEqual(preview["totals"]["discount_amount"], 5.0)
        self.assertEqual(preview["totals"]["total_amount"], 103.0)

        success, result = record_sale_return(sale_id, session_id, [{"original_sale_item_id": sale_item_id, "quantity": 1}], "كاش", reason="طلب العميل", db_path=self.db_path)
        self.assertTrue(success, result)
        returns = get_sale_returns(sale_id=sale_id, db_path=self.db_path)
        self.assertAlmostEqual(sum(row["total_amount"] for row in returns), 515.0)

    def test_returns_require_open_session_and_missing_sale_is_rejected(self):
        session_id = self.open_session(0)
        sale_id = self.record_sale_helper(
            session_id,
            [{"product_id": self.product_a_id, "quantity": 1, "unit_price": 100.0, "subtotal": 100.0}],
            payment_method="كاش (نقدي)",
        )
        items = get_returnable_sale_items(sale_id, db_path=self.db_path)

        success, result = close_pos_session(session_id, 100, db_path=self.db_path)
        self.assertTrue(success, result)
        success, message = record_sale_return(sale_id, session_id, [{"original_sale_item_id": items[0]["id"], "quantity": 1}], "كاش", reason="طلب العميل", db_path=self.db_path)
        self.assertFalse(success)
        self.assertEqual(message, "لا يمكن تسجيل عملية على جلسة مغلقة")

        new_session_id = self.open_session(0)
        success, message = record_sale_return(99999, new_session_id, [{"original_sale_item_id": items[0]["id"], "quantity": 1}], "كاش", reason="طلب العميل", db_path=self.db_path)
        self.assertFalse(success)
        self.assertEqual(message, "رقم الفاتورة غير موجود")

    def test_existing_null_session_sales_are_preserved_by_migration(self):
        legacy_db_path = os.path.join(self.temp_dir.name, "legacy_store.db")
        conn = sqlite3.connect(legacy_db_path)
        cursor = conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT);
            CREATE TABLE suppliers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, contact_person TEXT, phone TEXT, email TEXT, address TEXT);
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category_id INTEGER,
                cost_price REAL NOT NULL,
                selling_price REAL NOT NULL,
                stock_quantity INTEGER NOT NULL DEFAULT 0,
                reorder_level INTEGER NOT NULL DEFAULT 5,
                supplier_id INTEGER
            );
            CREATE TABLE customers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT UNIQUE, email TEXT, loyalty_points INTEGER DEFAULT 0);
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_date TEXT NOT NULL,
                customer_id INTEGER,
                total_amount REAL NOT NULL,
                discount REAL DEFAULT 0,
                tax_amount REAL DEFAULT 0,
                payment_method TEXT NOT NULL
            );
            CREATE TABLE sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL
            );
            CREATE TABLE purchase_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, po_date TEXT NOT NULL, supplier_id INTEGER NOT NULL, total_cost REAL NOT NULL, status TEXT NOT NULL);
            CREATE TABLE purchase_order_items (id INTEGER PRIMARY KEY AUTOINCREMENT, po_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_cost REAL NOT NULL);
            """
        )
        cursor.execute("INSERT INTO categories (name, description) VALUES (?, ?)", ("عام", "عام"))
        cursor.execute("INSERT INTO suppliers (name, contact_person, phone, email, address) VALUES (?, ?, ?, ?, ?)", ("المورد", "مسؤول", "0500000000", "supplier@example.com", "الرياض"))
        cursor.execute("INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity, reorder_level, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("LEG-1", "منتج قديم", 1, 10.0, 20.0, 5, 1, 1))
        cursor.execute("INSERT INTO customers (name, phone, email, loyalty_points) VALUES (?, ?, ?, ?)", ("عميل قديم", "0559999999", "old@example.com", 0))
        cursor.execute("INSERT INTO sales (sale_date, customer_id, total_amount, discount, tax_amount, payment_method) VALUES (?, ?, ?, ?, ?, ?)", ("2026-08-01 10:00:00", 1, 20.0, 0.0, 0.0, "كاش (نقدي)"))
        sale_id = cursor.lastrowid
        cursor.execute("INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)", (sale_id, 1, 1, 20.0, 20.0))
        conn.commit()
        conn.close()

        init_db(legacy_db_path, seed_sample_data=False)
        conn = get_connection(legacy_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(sales)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn("session_id", columns)
        cursor.execute("SELECT session_id FROM sales WHERE id=?", (sale_id,))
        self.assertIsNone(cursor.fetchone()[0])
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pos_sessions'")
        self.assertIsNotNone(cursor.fetchone())
        conn.close()

    def test_end_to_end_cash_reconciliation(self):
        session_id = self.open_session(500)
        sale_id = self.record_sale_helper(session_id, [{"product_id": self.product_a_id, "quantity": 10, "unit_price": 100.0, "subtotal": 1000.0}], payment_method="كاش (نقدي)", customer_id=self.generic_customer_id)
        self.record_sale_helper(session_id, [{"product_id": self.product_b_id, "quantity": 5, "unit_price": 80.0, "subtotal": 400.0}], payment_method="بطاقة ائتمان", customer_id=self.generic_customer_id)
        success, expense_id = add_expense(session_id, "مصروفات أخرى", "مصروف يومي", 100, payment_method="كاش", db_path=self.db_path)
        self.assertTrue(success, expense_id)

        items = get_returnable_sale_items(sale_id, db_path=self.db_path)
        success, result = record_sale_return(sale_id, session_id, [{"original_sale_item_id": items[0]["id"], "quantity": 2}], "كاش", reason="طلب العميل", db_path=self.db_path)
        self.assertTrue(success, result)

        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["expected_cash_balance"], 1200.0)

        success, result = close_pos_session(session_id, 1150, db_path=self.db_path)
        self.assertTrue(success, result)
        summary = calculate_session_summary(session_id, db_path=self.db_path)
        self.assertEqual(summary["difference"], -50.0)
        session = get_pos_session(session_id, db_path=self.db_path)
        self.assertEqual(session["status"], "CLOSED")


if __name__ == "__main__":
    unittest.main()
