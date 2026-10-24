import os
import tempfile
import unittest

from fastapi.testclient import TestClient

from core.db import calculate_tax, get_all_products, round_amount


class WebApiTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "web_store.db")
        os.environ["STORE_DB_PATH"] = self.db_path
        os.environ["STORE_MANAGER_PASSWORD"] = "manager123"
        os.environ["STORE_CASHIER_PASSWORD"] = "cashier123"
        from api.app import create_app

        self.client = TestClient(create_app())
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def login(self, username, password):
        response = self.client.post("/api/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_login_roles_and_money_flow(self):
        denied = self.client.get("/api/dashboard/summary")
        self.assertEqual(denied.status_code, 401)

        bad = self.client.post("/api/auth/login", json={"username": "manager", "password": "wrong"})
        self.assertEqual(bad.status_code, 401)

        cashier = self.login("cashier", "cashier123")
        self.assertEqual(cashier["role"], "cashier")
        blocked = self.client.get("/api/users")
        self.assertEqual(blocked.status_code, 403)
        blocked_product = self.client.post(
            "/api/products",
            json={"sku": "X", "name": "X", "cost_price": 1, "selling_price": 2, "stock_quantity": 1, "reorder_level": 1},
        )
        self.assertEqual(blocked_product.status_code, 403)

        self.client.post("/api/auth/logout")
        manager = self.login("manager", "manager123")
        self.assertEqual(manager["role"], "manager")
        users = self.client.get("/api/users")
        self.assertEqual(users.status_code, 200)
        self.assertEqual(len(users.json()), 2)

        self.client.post("/api/auth/logout")
        self.login("cashier", "cashier123")

        products = get_all_products(self.db_path)
        product = next(item for item in products if item["sku"] == "SKU1001")
        units = self.client.get(f"/api/products/{product['id']}/units")
        self.assertEqual(units.status_code, 200)
        unit = units.json()[0]
        quantity = 2
        unit_price = round_amount(unit["selling_price"])
        subtotal = round_amount(quantity * unit_price)
        tax = calculate_tax(subtotal)
        total = round_amount(subtotal + tax)

        no_session = self.client.post(
            "/api/pos/sales",
            json={
                "customer_id": None,
                "discount": 0,
                "tax_amount": tax,
                "total_amount": total,
                "payment_method": "كاش (نقدي)",
                "items": [{"product_id": product["id"], "product_unit_id": unit["id"], "quantity": quantity, "unit_price": unit_price}],
            },
        )
        self.assertEqual(no_session.status_code, 400)

        opened = self.client.post("/api/pos/session", json={"opening_balance": 100, "notes": "افتتاح"})
        self.assertEqual(opened.status_code, 200, opened.text)
        second = self.client.post("/api/pos/session", json={"opening_balance": 50})
        self.assertEqual(second.status_code, 400)

        mismatch = self.client.post(
            "/api/pos/sales",
            json={
                "discount": 0,
                "tax_amount": 0,
                "total_amount": 1,
                "payment_method": "كاش (نقدي)",
                "items": [{"product_id": product["id"], "product_unit_id": unit["id"], "quantity": quantity, "unit_price": unit_price}],
            },
        )
        self.assertEqual(mismatch.status_code, 400)

        sale = self.client.post(
            "/api/pos/sales",
            json={
                "discount": 0,
                "tax_amount": tax,
                "total_amount": total,
                "payment_method": "كاش (نقدي)",
                "items": [{"product_id": product["id"], "product_unit_id": unit["id"], "quantity": quantity, "unit_price": unit_price}],
            },
        )
        self.assertEqual(sale.status_code, 200, sale.text)
        sale_id = sale.json()["id"]

        lookup = self.client.get(f"/api/pos/returns/lookup/{sale_id}")
        self.assertEqual(lookup.status_code, 200, lookup.text)
        line = lookup.json()["items"][0]
        preview = self.client.post(
            "/api/pos/returns/preview",
            json={
                "original_sale_id": sale_id,
                "refund_method": "كاش",
                "reason": "طلب العميل",
                "items": [{"original_sale_item_id": line["id"], "quantity": 1}],
            },
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertGreater(preview.json()["totals"]["total_amount"], 0)

        returned = self.client.post(
            "/api/pos/returns",
            json={
                "original_sale_id": sale_id,
                "refund_method": "كاش",
                "reason": "طلب العميل",
                "items": [{"original_sale_item_id": line["id"], "quantity": 1}],
            },
        )
        self.assertEqual(returned.status_code, 200, returned.text)

        expense = self.client.post(
            "/api/pos/expenses",
            json={"category": "صيانة", "description": "صيانة", "amount": 10, "payment_method": "كاش"},
        )
        self.assertEqual(expense.status_code, 200, expense.text)

        summary = self.client.get("/api/pos/session").json()["summary"]
        self.assertAlmostEqual(summary["cash_sales"], total, places=2)
        self.assertGreater(summary["cash_returns"], 0)
        self.assertAlmostEqual(summary["cash_expenses"], 10, places=2)

        closed = self.client.post("/api/pos/session/close", json={"actual_balance": summary["expected_cash_balance"], "notes": "إغلاق"})
        self.assertEqual(closed.status_code, 200, closed.text)
        active = self.client.get("/api/pos/session").json()
        self.assertIsNone(active["session"])

        self.client.post("/api/auth/logout")
        self.login("manager", "manager123")
        overview = self.client.get("/api/analytics/overview")
        self.assertEqual(overview.status_code, 200)
        exported = self.client.get("/api/analytics/export.csv")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("بيع", exported.content.decode("utf-8-sig"))

    def test_new_product_sku_follows_category_sequence(self):
        self.login("manager", "manager123")
        categories = self.client.get("/api/categories")
        self.assertEqual(categories.status_code, 200)
        clothes = next(item for item in categories.json() if item["code"] == "CL")

        preview = self.client.get(f"/api/categories/{clothes['id']}/next-sku")
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["sku"], "CL0003")

        created = self.client.post(
            "/api/products",
            json={
                "name": "منتج تجريبي",
                "category_id": clothes["id"],
                "cost_price": 1,
                "selling_price": 2,
                "stock_quantity": 3,
                "reorder_level": 1,
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["sku"], "CL0003")
        self.assertEqual(created.json()["id"] > 0, True)

        nxt = self.client.get(f"/api/categories/{clothes['id']}/next-sku")
        self.assertEqual(nxt.json()["sku"], "CL0004")

        missing = self.client.post(
            "/api/products",
            json={"name": "بدون تصنيف", "cost_price": 1, "selling_price": 2, "stock_quantity": 1, "reorder_level": 1},
        )
        self.assertEqual(missing.status_code, 400)

    def test_category_code_can_be_saved_on_existing_category(self):
        self.login("manager", "manager123")
        created = self.client.post(
            "/api/categories",
            json={"code": "SN", "name": "تصنيف الرمز", "description": "وصف"},
        )
        self.assertEqual(created.status_code, 200, created.text)
        categories = self.client.get("/api/categories").json()
        category = next(item for item in categories if item["name"] == "تصنيف الرمز")
        self.assertEqual(category["code"], "SN")

        renamed = self.client.put(f"/api/categories/{category['id']}", json={"code": "ml"})
        self.assertEqual(renamed.status_code, 200, renamed.text)
        categories = self.client.get("/api/categories").json()
        category = next(item for item in categories if item["id"] == category["id"])
        self.assertEqual(category["code"], "ML")


if __name__ == "__main__":
    unittest.main()
