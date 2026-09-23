import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

DEFAULT_DB_PATH = "store.db"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
TAX_RATE = Decimal("0.08")

PAYMENT_BUCKET_CASH = "cash"
PAYMENT_BUCKET_CARD = "card"
PAYMENT_BUCKET_ELECTRONIC = "electronic"
PAYMENT_BUCKET_OTHER = "other"


def get_connection(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _now_str():
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def round_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        amount = Decimal("0")
    return float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _to_decimal(value):
    return Decimal(str(round_amount(value)))


def _normalize_text(value):
    return str(value or "").strip().lower()


def is_cash_payment(payment_method):
    normalized = _normalize_text(payment_method)
    return normalized == "كاش" or "نقد" in normalized or normalized == "cash"


def classify_payment_method(payment_method):
    normalized = _normalize_text(payment_method)
    if is_cash_payment(normalized):
        return PAYMENT_BUCKET_CASH
    if "بطاق" in normalized or "credit" in normalized or "debit" in normalized:
        return PAYMENT_BUCKET_CARD
    if "إلكتر" in normalized or "مدى" in normalized or "تحويل" in normalized or "electronic" in normalized:
        return PAYMENT_BUCKET_ELECTRONIC
    return PAYMENT_BUCKET_OTHER


def calculate_tax(subtotal):
    return round_amount(_to_decimal(subtotal) * TAX_RATE)


def calculate_loyalty_points(amount):
    return int(round_amount(amount) // 10)


def _is_generic_customer_row(customer_row):
    if not customer_row:
        return False
    if isinstance(customer_row, sqlite3.Row):
        name = _normalize_text(customer_row["name"])
        phone = _normalize_text(customer_row["phone"])
    else:
        name = _normalize_text(customer_row.get("name"))
        phone = _normalize_text(customer_row.get("phone"))
    return "عميل عام" in name or phone in {"غير محدد", "n/a", "na"}


def _get_generic_customer_id(cursor):
    cursor.execute("SELECT id, name, phone FROM customers ORDER BY id")
    for row in cursor.fetchall():
        if _is_generic_customer_row(row):
            return row["id"]
    return None


def _ensure_non_negative_amount(value, allow_zero=True):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        raise ValueError("invalid_amount")
    amount = float(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if amount < 0 or (not allow_zero and amount <= 0):
        raise ValueError("invalid_amount")
    return amount


def calculate_base_quantity(quantity, pieces_per_unit):
    try:
        qty = float(quantity)
        pieces = float(pieces_per_unit)
    except (TypeError, ValueError):
        raise ValueError("invalid_quantity")
    if qty <= 0 or pieces <= 0:
        raise ValueError("invalid_quantity")
    return round_amount(qty * pieces)


def validate_unit_stock(product_id, quantity, pieces_per_unit, db_path=DEFAULT_DB_PATH):
    try:
        required_base_quantity = calculate_base_quantity(quantity, pieces_per_unit)
    except ValueError:
        return False, "كمية الوحدة غير صحيحة"

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT stock_quantity FROM products WHERE id=?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False, "المنتج غير موجود"
    if row["stock_quantity"] < required_base_quantity:
        return False, "الكمية المطلوبة غير متوفرة في المخزون"
    return True, required_base_quantity


def _get_or_create_unit(cursor, unit_name):
    unit_name = (unit_name or "").strip()
    if not unit_name:
        raise ValueError("unit_name_required")
    cursor.execute("SELECT id FROM units WHERE name = ?", (unit_name,))
    row = cursor.fetchone()
    if row:
        return row["id"]
    cursor.execute("INSERT INTO units (name, created_at, is_active) VALUES (?, ?, 1)", (unit_name, _now_str()))
    return cursor.lastrowid


def ensure_product_unit(product_id, unit_name, pieces_per_unit, cost_price=None, selling_price=None, is_default=False, is_active=True, db_path=DEFAULT_DB_PATH):
    try:
        pieces_per_unit = float(pieces_per_unit)
    except (TypeError, ValueError):
        return False, "مقدار القطع داخل الوحدة غير صحيح"
    if pieces_per_unit <= 0:
        return False, "يجب أن يكون عدد القطع داخل الوحدة أكبر من صفر"

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, cost_price, selling_price FROM products WHERE id=?", (product_id,))
        product_row = cursor.fetchone()
        if not product_row:
            return False, "المنتج غير موجود"

        unit_id = _get_or_create_unit(cursor, unit_name)

        if cost_price is None:
            cost_price = product_row["cost_price"]
        if selling_price is None:
            selling_price = product_row["selling_price"]

        try:
            cost_price = _ensure_non_negative_amount(cost_price)
            selling_price = _ensure_non_negative_amount(selling_price)
        except ValueError:
            return False, "يجب أن تكون أسعار التكلفة والسعر النهائي غير سلبية"

        cursor.execute(
            "SELECT id, is_default FROM product_units WHERE product_id=? AND unit_id=?",
            (product_id, unit_id),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                """
                UPDATE product_units
                SET pieces_per_unit=?, cost_price=?, selling_price=?, is_default=?, is_active=?, updated_at=?
                WHERE id=?
                """,
                (pieces_per_unit, cost_price, selling_price, 1 if is_default else row["is_default"], 1 if is_active else 0, _now_str(), row["id"]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO product_units (product_id, unit_id, pieces_per_unit, cost_price, selling_price, is_default, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (product_id, unit_id, pieces_per_unit, cost_price, selling_price, 1 if is_default else 0, 1 if is_active else 0, _now_str(), _now_str()),
            )

        if is_default:
            cursor.execute("UPDATE product_units SET is_default = 0 WHERE product_id=? AND id != ?", (product_id, cursor.lastrowid if row is None else row["id"]))

        conn.commit()
        return True, "تم حفظ الوحدة بنجاح"
    except Exception:
        conn.rollback()
        return False, "حدث خطأ أثناء حفظ الوحدة"
    finally:
        conn.close()


def get_product_units(product_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, cost_price, selling_price FROM products WHERE id=?", (product_id,))
    product_row = cursor.fetchone()
    if product_row:
        cursor.execute("SELECT id FROM product_units WHERE product_id=?", (product_id,))
        if cursor.fetchone() is None:
            ensure_product_unit(product_id, "Piece", 1, cost_price=product_row["cost_price"], selling_price=product_row["selling_price"], is_default=True, db_path=db_path)
    cursor.execute(
        """
        SELECT pu.*, u.name AS unit_name, u.id AS unit_id
        FROM product_units pu
        JOIN units u ON pu.unit_id = u.id
        WHERE pu.product_id = ? AND pu.is_active = 1
        ORDER BY pu.is_default DESC, u.name ASC
        """,
        (product_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_product_unit(product_id, unit_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pu.*, u.name AS unit_name
        FROM product_units pu
        JOIN units u ON pu.unit_id = u.id
        WHERE pu.product_id=? AND pu.unit_id=? AND pu.is_active=1
        LIMIT 1
        """,
        (product_id, unit_id),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_default_product_unit(product_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pu.*, u.name AS unit_name
        FROM product_units pu
        JOIN units u ON pu.unit_id = u.id
        WHERE pu.product_id = ? AND pu.is_active = 1
        ORDER BY pu.is_default DESC, pu.id ASC
        LIMIT 1
        """,
        (product_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_unit_price(product_id, unit_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT pu.selling_price, pu.pieces_per_unit, u.name AS unit_name FROM product_units pu JOIN units u ON pu.unit_id = u.id WHERE pu.product_id=? AND pu.unit_id=? AND pu.is_active=1 LIMIT 1",
        (product_id, unit_id),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def _seed_default_product_units(cursor):
    cursor.execute("SELECT id, cost_price, selling_price FROM products")
    for row in cursor.fetchall():
        cursor.execute("SELECT id FROM units WHERE name = ?", ("Piece",))
        unit_row = cursor.fetchone()
        if not unit_row:
            cursor.execute("INSERT INTO units (name, created_at, is_active) VALUES (?, ?, 1)", ("Piece", _now_str()))
            unit_id = cursor.lastrowid
        else:
            unit_id = unit_row["id"]

        cursor.execute(
            "SELECT id FROM product_units WHERE product_id=? AND unit_id=?",
            (row["id"], unit_id),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                """
                INSERT INTO product_units (product_id, unit_id, pieces_per_unit, cost_price, selling_price, is_default, is_active, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, 1, 1, ?, ?)
                """,
                (row["id"], unit_id, row["cost_price"], row["selling_price"], _now_str(), _now_str()),
            )


def _create_schema(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            description TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            address TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category_id INTEGER,
            cost_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            stock_quantity INTEGER NOT NULL DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 5,
            supplier_id INTEGER,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS product_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            unit_id INTEGER NOT NULL,
            pieces_per_unit REAL NOT NULL CHECK (pieces_per_unit > 0),
            cost_price REAL NOT NULL CHECK (cost_price >= 0),
            selling_price REAL NOT NULL CHECK (selling_price >= 0),
            is_default INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(product_id, unit_id),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE,
            email TEXT,
            loyalty_points INTEGER DEFAULT 0
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('manager', 'cashier')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pos_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            opening_balance REAL NOT NULL DEFAULT 0 CHECK (opening_balance >= 0),
            expected_closing_balance REAL,
            actual_closing_balance REAL,
            balance_difference REAL,
            status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
            opening_notes TEXT,
            closing_notes TEXT,
            opened_by_user_id INTEGER,
            closed_by_user_id INTEGER,
            FOREIGN KEY (opened_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (closed_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_date TEXT NOT NULL,
            customer_id INTEGER,
            total_amount REAL NOT NULL,
            discount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            payment_method TEXT NOT NULL,
            session_id INTEGER,
            user_id INTEGER,
            FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE SET NULL,
            FOREIGN KEY (session_id) REFERENCES pos_sessions (id) ON DELETE RESTRICT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_unit_id INTEGER,
            unit_name TEXT,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            pieces_per_unit REAL DEFAULT 1,
            base_quantity REAL DEFAULT 0,
            subtotal REAL NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT,
            FOREIGN KEY (product_unit_id) REFERENCES product_units(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sale_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_sale_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            return_date TEXT NOT NULL,
            total_amount REAL NOT NULL CHECK (total_amount >= 0),
            refund_method TEXT NOT NULL,
            reason TEXT,
            notes TEXT,
            user_id INTEGER,
            FOREIGN KEY (original_sale_id) REFERENCES sales(id) ON DELETE RESTRICT,
            FOREIGN KEY (session_id) REFERENCES pos_sessions(id) ON DELETE RESTRICT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sale_return_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_id INTEGER NOT NULL,
            original_sale_item_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price REAL NOT NULL CHECK (unit_price >= 0),
            subtotal REAL NOT NULL CHECK (subtotal >= 0),
            tax_amount REAL NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
            discount_amount REAL NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
            line_total REAL NOT NULL DEFAULT 0 CHECK (line_total >= 0),
            FOREIGN KEY (return_id) REFERENCES sale_returns(id) ON DELETE CASCADE,
            FOREIGN KEY (original_sale_item_id) REFERENCES sale_items(id) ON DELETE RESTRICT,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            expense_date TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            payment_method TEXT NOT NULL DEFAULT 'كاش',
            reference_number TEXT,
            notes TEXT,
            user_id INTEGER,
            FOREIGN KEY (session_id) REFERENCES pos_sessions(id) ON DELETE RESTRICT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_date TEXT NOT NULL,
            supplier_id INTEGER NOT NULL,
            total_cost REAL NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE RESTRICT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY (po_id) REFERENCES purchase_orders (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE RESTRICT
        )
        """
    )

def _create_indexes(cursor):
    statements = [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_pos_sessions_single_open ON pos_sessions(status) WHERE status = 'OPEN'",
        "CREATE INDEX IF NOT EXISTS idx_pos_sessions_status ON pos_sessions(status)",
        "CREATE INDEX IF NOT EXISTS idx_pos_sessions_opened_at ON pos_sessions(opened_at)",
        "CREATE INDEX IF NOT EXISTS idx_pos_sessions_closed_at ON pos_sessions(closed_at)",
        "CREATE INDEX IF NOT EXISTS idx_sales_session_id ON sales(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_sales_sale_date ON sales(sale_date)",
        "CREATE INDEX IF NOT EXISTS idx_sale_returns_original_sale ON sale_returns(original_sale_id)",
        "CREATE INDEX IF NOT EXISTS idx_sale_returns_session_id ON sale_returns(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_sale_returns_return_date ON sale_returns(return_date)",
        "CREATE INDEX IF NOT EXISTS idx_sale_return_items_return_id ON sale_return_items(return_id)",
        "CREATE INDEX IF NOT EXISTS idx_sale_return_items_sale_item_id ON sale_return_items(original_sale_item_id)",
        "CREATE INDEX IF NOT EXISTS idx_sale_return_items_product_id ON sale_return_items(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_session_id ON expenses(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_expense_date ON expenses(expense_date)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)",
    ]
    for statement in statements:
        cursor.execute(statement)


def _table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def _column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cursor.fetchall())


def _record_migration(cursor, version, description):
    cursor.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
        (version, _now_str(), description),
    )


def _database_requires_migration(cursor):
    if not _table_exists(cursor, "units"):
        return True
    if not _table_exists(cursor, "product_units"):
        return True
    if not _table_exists(cursor, "pos_sessions"):
        return True
    if not _table_exists(cursor, "expenses"):
        return True
    if not _table_exists(cursor, "sale_returns"):
        return True
    if not _table_exists(cursor, "sale_return_items"):
        return True
    if not _column_exists(cursor, "sales", "session_id"):
        return True
    if not _column_exists(cursor, "sale_items", "product_unit_id"):
        return True
    if not _column_exists(cursor, "sale_items", "pieces_per_unit"):
        return True
    if not _column_exists(cursor, "sale_items", "base_quantity"):
        return True
    if not _table_exists(cursor, "users"):
        return True
    if not _table_exists(cursor, "auth_sessions"):
        return True
    if not _column_exists(cursor, "pos_sessions", "opened_by_user_id"):
        return True
    if not _column_exists(cursor, "pos_sessions", "closed_by_user_id"):
        return True
    if not _column_exists(cursor, "sales", "user_id"):
        return True
    if not _column_exists(cursor, "sale_returns", "user_id"):
        return True
    if not _column_exists(cursor, "expenses", "user_id"):
        return True
    return False


def _backup_database_if_needed(db_path):
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return None
    backup_name = f"{os.path.splitext(db_path)[0]}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(db_path, backup_name)
    return backup_name


def _run_migrations(cursor):
    if not _table_exists(cursor, "units"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        _record_migration(cursor, 1, "Created units table")

    if not _table_exists(cursor, "product_units"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS product_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                unit_id INTEGER NOT NULL,
                pieces_per_unit REAL NOT NULL CHECK (pieces_per_unit > 0),
                cost_price REAL NOT NULL CHECK (cost_price >= 0),
                selling_price REAL NOT NULL CHECK (selling_price >= 0),
                is_default INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(product_id, unit_id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE RESTRICT
            )
            """
        )
        _record_migration(cursor, 2, "Created product_units table")

    if not _column_exists(cursor, "sales", "session_id"):
        cursor.execute("ALTER TABLE sales ADD COLUMN session_id INTEGER REFERENCES pos_sessions(id) ON DELETE RESTRICT")
        _record_migration(cursor, 3, "Added sales.session_id column")

    if not _column_exists(cursor, "sale_items", "product_unit_id"):
        cursor.execute("ALTER TABLE sale_items ADD COLUMN product_unit_id INTEGER REFERENCES product_units(id) ON DELETE SET NULL")
        _record_migration(cursor, 4, "Added sale_items.product_unit_id column")
    if not _column_exists(cursor, "sale_items", "unit_name"):
        cursor.execute("ALTER TABLE sale_items ADD COLUMN unit_name TEXT")
        _record_migration(cursor, 5, "Added sale_items.unit_name column")
    if not _column_exists(cursor, "sale_items", "pieces_per_unit"):
        cursor.execute("ALTER TABLE sale_items ADD COLUMN pieces_per_unit REAL DEFAULT 1")
        _record_migration(cursor, 6, "Added sale_items.pieces_per_unit column")
    if not _column_exists(cursor, "sale_items", "base_quantity"):
        cursor.execute("ALTER TABLE sale_items ADD COLUMN base_quantity REAL DEFAULT 0")
        _record_migration(cursor, 7, "Added sale_items.base_quantity column")

    if not _table_exists(cursor, "pos_sessions"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pos_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                opening_balance REAL NOT NULL DEFAULT 0 CHECK (opening_balance >= 0),
                expected_closing_balance REAL,
                actual_closing_balance REAL,
                balance_difference REAL,
                status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
                opening_notes TEXT,
                closing_notes TEXT
            )
            """
        )
        _record_migration(cursor, 2, "Created pos_sessions table")

    if not _table_exists(cursor, "expenses"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                expense_date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                payment_method TEXT NOT NULL DEFAULT 'كاش',
                reference_number TEXT,
                notes TEXT,
                FOREIGN KEY (session_id) REFERENCES pos_sessions(id) ON DELETE RESTRICT
            )
            """
        )
        _record_migration(cursor, 8, "Created expenses table")

    if not _table_exists(cursor, "sale_returns"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sale_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_sale_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                return_date TEXT NOT NULL,
                total_amount REAL NOT NULL CHECK (total_amount >= 0),
                refund_method TEXT NOT NULL,
                reason TEXT,
                notes TEXT,
                FOREIGN KEY (original_sale_id) REFERENCES sales(id) ON DELETE RESTRICT,
                FOREIGN KEY (session_id) REFERENCES pos_sessions(id) ON DELETE RESTRICT
            )
            """
        )
        _record_migration(cursor, 9, "Created sale_returns table")

    if not _table_exists(cursor, "sale_return_items"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sale_return_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_id INTEGER NOT NULL,
                original_sale_item_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL CHECK (unit_price >= 0),
                subtotal REAL NOT NULL CHECK (subtotal >= 0),
                tax_amount REAL NOT NULL DEFAULT 0 CHECK (tax_amount >= 0),
                discount_amount REAL NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
                line_total REAL NOT NULL DEFAULT 0 CHECK (line_total >= 0),
                FOREIGN KEY (return_id) REFERENCES sale_returns(id) ON DELETE CASCADE,
                FOREIGN KEY (original_sale_item_id) REFERENCES sale_items(id) ON DELETE RESTRICT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
            )
            """
        )
        _record_migration(cursor, 10, "Created sale_return_items table")

    if not _table_exists(cursor, "users"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('manager', 'cashier')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        _record_migration(cursor, 11, "Created users table")

    if not _table_exists(cursor, "auth_sessions"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        _record_migration(cursor, 12, "Created auth_sessions table")

    if _table_exists(cursor, "pos_sessions") and not _column_exists(cursor, "pos_sessions", "opened_by_user_id"):
        cursor.execute("ALTER TABLE pos_sessions ADD COLUMN opened_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        _record_migration(cursor, 13, "Added pos_sessions.opened_by_user_id")
    if _table_exists(cursor, "pos_sessions") and not _column_exists(cursor, "pos_sessions", "closed_by_user_id"):
        cursor.execute("ALTER TABLE pos_sessions ADD COLUMN closed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        _record_migration(cursor, 14, "Added pos_sessions.closed_by_user_id")
    if _table_exists(cursor, "sales") and not _column_exists(cursor, "sales", "user_id"):
        cursor.execute("ALTER TABLE sales ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        _record_migration(cursor, 15, "Added sales.user_id")
    if _table_exists(cursor, "sale_returns") and not _column_exists(cursor, "sale_returns", "user_id"):
        cursor.execute("ALTER TABLE sale_returns ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        _record_migration(cursor, 16, "Added sale_returns.user_id")
    if _table_exists(cursor, "expenses") and not _column_exists(cursor, "expenses", "user_id"):
        cursor.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        _record_migration(cursor, 17, "Added expenses.user_id")

    _create_indexes(cursor)


def init_db(db_path=DEFAULT_DB_PATH, seed_sample_data=True):
    db_exists_before_init = os.path.exists(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    needs_backup = db_exists_before_init and _database_requires_migration(cursor)
    conn.close()

    if needs_backup:
        try:
            _backup_database_if_needed(db_path)
        except OSError as exc:
            raise RuntimeError("تعذر إنشاء نسخة احتياطية قبل الترقية.") from exc

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        _create_schema(cursor)
        _run_migrations(cursor)
        _seed_default_product_units(cursor)
        conn.commit()

        if seed_sample_data and not db_exists_before_init:
            cursor.execute("SELECT COUNT(*) FROM categories")
            if cursor.fetchone()[0] == 0:
                _insert_sample_data(cursor)
                conn.commit()
    finally:
        conn.close()


def reset_db(db_path=DEFAULT_DB_PATH):
    """Drop all tables and recreate an empty schema (without seed data)."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF")
    cursor.executescript(
        """
        DROP TABLE IF EXISTS auth_sessions;
        DROP TABLE IF EXISTS sale_return_items;
        DROP TABLE IF EXISTS sale_returns;
        DROP TABLE IF EXISTS expenses;
        DROP TABLE IF EXISTS sale_items;
        DROP TABLE IF EXISTS sales;
        DROP TABLE IF EXISTS pos_sessions;
        DROP TABLE IF EXISTS purchase_order_items;
        DROP TABLE IF EXISTS purchase_orders;
        DROP TABLE IF EXISTS product_units;
        DROP TABLE IF EXISTS units;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS suppliers;
        DROP TABLE IF EXISTS categories;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS schema_migrations;
        """
    )
    _create_schema(cursor)
    _create_indexes(cursor)
    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    conn.close()


def _insert_sample_data(cursor):
    try:
        print("إعداد قاعدة البيانات بالبيانات الافتراضية الأولية...")
    except UnicodeEncodeError:
        print("Seeding initial sample data...")
    categories = [
        ("ملابس وأزياء", "ملابس وإكسسوارات عصرية"),
        ("إلكترونيات", "أجهزة ذكية، هواتف، وكابلات تقنية"),
        ("أدوات منزلية ومطبخ", "أواني طهي، ديكورات ومستلزمات المنزل"),
        ("مشروبات", "مشروبات غازية، قهوة متخصصة، وشاي فاخر"),
    ]
    cursor.executemany("INSERT INTO categories (name, description) VALUES (?, ?)", categories)

    suppliers = [
        ("شركة التوريدات التقنية", "أحمد عبدالله", "0501234567", "support@techsupply.com", "الرياض, المنطقة الصناعية"),
        ("المركز العالمي للأزياء", "خالد الفارسي", "0502345678", "orders@fashionhub.com", "جدة, شارع التحلية"),
        ("مؤسسة الأواني الممتازة", "نورة السالم", "0503456789", "sales@primekitchen.com", "الدمام, حي السوق"),
        ("موزعو المشروبات النقية", "سعد المري", "0504567890", "info@purebev.com", "القاهرة, مدينة نصر"),
    ]
    cursor.executemany(
        "INSERT INTO suppliers (name, contact_person, phone, email, address) VALUES (?, ?, ?, ?, ?)",
        suppliers,
    )

    products = [
        ("SKU1001", "تيشيرت قطن فاخر", 1, 25.0, 75.0, 45, 10, 2),
        ("SKU1002", "بنطلون جينز كلاسيك", 1, 60.0, 150.0, 25, 8, 2),
        ("SKU1003", "سماعات أذن لاسلكية برو", 2, 100.0, 299.0, 15, 5, 1),
        ("SKU1004", "بنك طاقة سريع الشحن", 2, 45.0, 120.0, 30, 10, 1),
        ("SKU1005", "زجاجة مياه ستانلس ستيل", 3, 20.0, 55.0, 60, 15, 3),
        ("SKU1006", "مقلاة طهي غير لاصقة", 3, 40.0, 95.0, 20, 5, 3),
        ("SKU1007", "شاي أخضر عضوي (50 كيس)", 4, 12.0, 35.0, 100, 20, 4),
        ("SKU1008", "قهوة كولد برو الحرفية", 4, 8.0, 22.0, 80, 25, 4),
        ("SKU1009", "كابل HDMI فائق الدقة", 2, 10.0, 35.0, 4, 10, 1),
    ]
    cursor.executemany(
        """
        INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity, reorder_level, supplier_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        products,
    )

    customers = [
        ("عميل عام (نقدي)", "غير محدد", "N/A", 0),
        ("فاطمة أحمد", "0551000101", "fatima@example.com", 120),
        ("محمد محمود", "0551000102", "mohamed@example.com", 45),
        ("مريم عبدالرحمن", "0551000103", "maryam@example.com", 210),
    ]
    cursor.executemany("INSERT INTO customers (name, phone, email, loyalty_points) VALUES (?, ?, ?, ?)", customers)

    now = datetime.now()
    sample_sales = [
        (now - timedelta(days=5), 2, 449.0, 0.0, 31.43, "بطاقة ائتمان"),
        (now - timedelta(days=3), 1, 120.0, 0.0, 8.40, "كاش (نقدي)"),
        (now - timedelta(days=1), 4, 150.0, 10.0, 9.80, "دفع إلكتروني (مدى)"),
        (now, 3, 70.0, 0.0, 4.90, "كاش (نقدي)"),
    ]
    for index, sale_data in enumerate(sample_sales):
        cursor.execute(
            """
            INSERT INTO sales (sale_date, customer_id, total_amount, discount, tax_amount, payment_method, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sale_data[0].strftime(TIMESTAMP_FORMAT), sale_data[1], sale_data[2], sale_data[3], sale_data[4], sale_data[5], None),
        )
        sale_id = cursor.lastrowid
        if index == 0:
            cursor.execute("INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)", (sale_id, 3, 1, 299.0, 299.0))
            cursor.execute("INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)", (sale_id, 2, 1, 150.0, 150.0))
        elif index == 1:
            cursor.execute("INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)", (sale_id, 4, 1, 120.0, 120.0))
        elif index == 2:
            cursor.execute("INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)", (sale_id, 2, 1, 150.0, 150.0))
        elif index == 3:
            cursor.execute("INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)", (sale_id, 9, 2, 35.0, 70.0))

    po_date_str = (now - timedelta(days=10)).strftime(TIMESTAMP_FORMAT)
    cursor.execute("INSERT INTO purchase_orders (po_date, supplier_id, total_cost, status) VALUES (?, ?, ?, ?)", (po_date_str, 1, 1000.0, "تم الاستلام"))
    po_id = cursor.lastrowid
    cursor.execute("INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_cost) VALUES (?, ?, ?, ?)", (po_id, 3, 10, 100.0))


def get_all_products(db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.*, c.name AS category_name, s.name AS supplier_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        ORDER BY p.name
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_low_stock_products(db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.*, c.name AS category_name, s.name AS supplier_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.stock_quantity <= p.reorder_level
        ORDER BY p.stock_quantity ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def search_products(query, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    q = f"%{query}%"
    cursor.execute(
        """
        SELECT p.*, c.name AS category_name, s.name AS supplier_name
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.name LIKE ? OR p.sku LIKE ? OR c.name LIKE ?
        ORDER BY p.name
        """,
        (q, q, q),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_product(sku, name, category_id, cost_price, selling_price, stock_quantity, reorder_level, supplier_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO products (sku, name, category_id, cost_price, selling_price, stock_quantity, reorder_level, supplier_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sku, name, category_id, round_amount(cost_price), round_amount(selling_price), stock_quantity, reorder_level, supplier_id),
        )
        product_id = cursor.lastrowid
        _seed_default_product_units(cursor)
        ensure_product_unit(product_id, "Piece", 1, cost_price=cost_price, selling_price=selling_price, is_default=True, db_path=db_path)
        conn.commit()
        return True, "تمت إضافة المنتج بنجاح!"
    except sqlite3.IntegrityError:
        return False, "خطأ: كود المنتج (SKU) مسجل مسبقاً."
    except Exception:
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def update_product(product_id, sku, name, category_id, cost_price, selling_price, stock_quantity, reorder_level, supplier_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE products
            SET sku=?, name=?, category_id=?, cost_price=?, selling_price=?, stock_quantity=?, reorder_level=?, supplier_id=?
            WHERE id=?
            """,
            (sku, name, category_id, round_amount(cost_price), round_amount(selling_price), stock_quantity, reorder_level, supplier_id, product_id),
        )
        product_unit = get_default_product_unit(product_id, db_path=db_path)
        if product_unit is None:
            ensure_product_unit(product_id, "Piece", 1, cost_price=cost_price, selling_price=selling_price, is_default=True, db_path=db_path)
        else:
            cursor.execute(
                "UPDATE product_units SET cost_price=?, selling_price=?, updated_at=? WHERE product_id=? AND is_default=1",
                (round_amount(cost_price), round_amount(selling_price), _now_str(), product_id),
            )
        conn.commit()
        return True, "تم تعديل بيانات المنتج بنجاح!"
    except sqlite3.IntegrityError:
        return False, "خطأ: كود المنتج (SKU) مسجل مسبقاً."
    except Exception:
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def delete_product(product_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()
        return True, "تم حذف المنتج بنجاح!"
    except sqlite3.IntegrityError:
        return False, "خطأ: لا يمكن حذف المنتج لارتباطه بعمليات بيع أو فواتير سابقة."
    except Exception:
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def adjust_stock(product_id, new_quantity, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE products SET stock_quantity=? WHERE id=?", (new_quantity, product_id))
        conn.commit()
        return True, "تم تعديل كمية المخزون بنجاح."
    except Exception:
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def get_all_categories(db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_category(name, description, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name, description) VALUES (?, ?)", (name, description))
        conn.commit()
        return True, "تمت إضافة التصنيف بنجاح."
    except sqlite3.IntegrityError:
        return False, "هذا التصنيف موجود مسبقاً."
    finally:
        conn.close()


def get_all_customers(db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_generic_customer_id(db_path=DEFAULT_DB_PATH):
    """Return the generic walk-in customer id when such a record exists."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    customer_id = _get_generic_customer_id(cursor)
    conn.close()
    return customer_id


def add_customer(name, phone, email, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO customers (name, phone, email) VALUES (?, ?, ?)", (name, phone, email))
        conn.commit()
        return True, "تم تسجيل العميل بنجاح."
    except sqlite3.IntegrityError:
        return False, "يوجد عميل مسجل بنفس رقم الهاتف."
    finally:
        conn.close()


def update_customer(cust_id, name, phone, email, points, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE customers SET name=?, phone=?, email=?, loyalty_points=? WHERE id=?", (name, phone, email, points, cust_id))
        conn.commit()
        return True, "تم تحديث بيانات العميل بنجاح."
    except Exception:
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def get_customer_sales(customer_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sales WHERE customer_id = ? ORDER BY sale_date DESC", (customer_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_customer(cust_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone FROM customers WHERE id=?", (cust_id,))
    customer = cursor.fetchone()
    if _is_generic_customer_row(customer):
        conn.close()
        return False, "لا يمكن حذف العميل الافتراضي العام."
    try:
        cursor.execute("DELETE FROM customers WHERE id=?", (cust_id,))
        conn.commit()
        return True, "تم حذف العميل بنجاح."
    except Exception:
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def get_all_suppliers(db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_supplier(name, contact, phone, email, address, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO suppliers (name, contact_person, phone, email, address) VALUES (?, ?, ?, ?, ?)", (name, contact, phone, email, address))
        conn.commit()
        return True, "تمت إضافة المورّد بنجاح."
    except Exception:
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def get_all_purchase_orders(db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT po.*, s.name AS supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        ORDER BY po.po_date DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_po_items(po_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT poi.*, p.name AS product_name, p.sku
        FROM purchase_order_items poi
        JOIN products p ON poi.product_id = p.id
        WHERE poi.po_id = ?
        """,
        (po_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_purchase_order(supplier_id, items, total_cost, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO purchase_orders (po_date, supplier_id, total_cost, status) VALUES (?, ?, ?, ?)", (_now_str(), supplier_id, round_amount(total_cost), "قيد الانتظار"))
        po_id = cursor.lastrowid
        for product_id, quantity, unit_cost in items:
            cursor.execute("INSERT INTO purchase_order_items (po_id, product_id, quantity, unit_cost) VALUES (?, ?, ?, ?)", (po_id, product_id, quantity, round_amount(unit_cost)))
        conn.commit()
        return True, "تم إنشاء أمر الشراء بنجاح!"
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def mark_po_received(po_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT status FROM purchase_orders WHERE id=?", (po_id,))
        row = cursor.fetchone()
        if not row:
            return False, "أمر الشراء غير موجود."
        if row["status"] == "تم الاستلام":
            return False, "أمر الشراء مسجل كـ 'تم الاستلام' مسبقاً."

        cursor.execute("UPDATE purchase_orders SET status='تم الاستلام' WHERE id=?", (po_id,))
        cursor.execute("SELECT product_id, quantity FROM purchase_order_items WHERE po_id=?", (po_id,))
        for item in cursor.fetchall():
            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (item["quantity"], item["product_id"]))
        conn.commit()
        return True, "تم استلام أمر الشراء وإضافة الكميات إلى المخزون بنجاح!"
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def get_active_pos_session(db_path=DEFAULT_DB_PATH):
    """Return the currently open POS session, if any."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pos_sessions WHERE status='OPEN' ORDER BY opened_at DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pos_session(session_id, db_path=DEFAULT_DB_PATH):
    """Return a POS session by its id."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pos_sessions WHERE id=?", (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pos_sessions(limit=None, db_path=DEFAULT_DB_PATH):
    """Return POS session history ordered from newest to oldest."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    sql = "SELECT * FROM pos_sessions ORDER BY opened_at DESC"
    params = ()
    if limit:
        sql += " LIMIT ?"
        params = (limit,)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def open_pos_session(opening_balance, notes=None, db_path=DEFAULT_DB_PATH, opened_by_user_id=None):
    """Open a new cashier session if no other session is currently open."""
    try:
        opening_balance = _ensure_non_negative_amount(opening_balance)
    except ValueError:
        return False, "الرصيد الافتتاحي غير صحيح"
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM pos_sessions WHERE status='OPEN' LIMIT 1")
        if cursor.fetchone():
            return False, "يوجد بالفعل جلسة مفتوحة"
        cursor.execute(
            "INSERT INTO pos_sessions (opened_at, opening_balance, status, opening_notes, opened_by_user_id) VALUES (?, ?, 'OPEN', ?, ?)",
            (_now_str(), opening_balance, (notes or "").strip() or None, opened_by_user_id),
        )
        session_id = cursor.lastrowid
        conn.commit()
        return True, session_id
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, "يوجد بالفعل جلسة مفتوحة"
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def _get_open_session_or_error(cursor, session_id):
    cursor.execute("SELECT * FROM pos_sessions WHERE id=?", (session_id,))
    session = cursor.fetchone()
    if not session:
        return None, "لا توجد جلسة بيع مفتوحة"
    if session["status"] != "OPEN":
        return None, "لا يمكن تسجيل عملية على جلسة مغلقة"
    return session, None


def _aggregate_payment_totals(rows, amount_key, method_key):
    totals = {
        PAYMENT_BUCKET_CASH: 0.0,
        PAYMENT_BUCKET_CARD: 0.0,
        PAYMENT_BUCKET_ELECTRONIC: 0.0,
        PAYMENT_BUCKET_OTHER: 0.0,
        "total": 0.0,
    }
    for row in rows:
        amount = round_amount(row[amount_key] or 0.0)
        bucket = classify_payment_method(row[method_key])
        totals[bucket] += amount
        totals["total"] += amount
    for key in list(totals.keys()):
        totals[key] = round_amount(totals[key])
    return totals


def get_session_expenses(session_id, db_path=DEFAULT_DB_PATH):
    """Return all expenses for the selected POS session."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM expenses WHERE session_id=? ORDER BY expense_date DESC, id DESC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_expense(expense_id, db_path=DEFAULT_DB_PATH):
    """Return a single expense record."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM expenses WHERE id=?", (expense_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_expenses_summary(session_id, db_path=DEFAULT_DB_PATH):
    """Return total and categorized expense metrics for a session."""
    expenses = get_session_expenses(session_id, db_path=db_path)
    totals = _aggregate_payment_totals(expenses, "amount", "payment_method")
    by_category = {}
    for expense in expenses:
        category = expense["category"]
        by_category[category] = round_amount(by_category.get(category, 0.0) + expense["amount"])
    return {
        "expense_count": len(expenses),
        "total_expenses": totals["total"],
        "cash_expenses": totals[PAYMENT_BUCKET_CASH],
        "non_cash_expenses": round_amount(totals[PAYMENT_BUCKET_CARD] + totals[PAYMENT_BUCKET_ELECTRONIC] + totals[PAYMENT_BUCKET_OTHER]),
        "card_expenses": totals[PAYMENT_BUCKET_CARD],
        "electronic_expenses": totals[PAYMENT_BUCKET_ELECTRONIC],
        "other_expenses": totals[PAYMENT_BUCKET_OTHER],
        "expenses_by_category": by_category,
    }


def add_expense(session_id, category, description, amount, payment_method="كاش", reference_number=None, notes=None, db_path=DEFAULT_DB_PATH, user_id=None):
    """Add a new session expense after validating the active session."""
    category = (category or "").strip()
    description = (description or "").strip()
    payment_method = (payment_method or "").strip()
    reference_number = (reference_number or "").strip() or None
    notes = (notes or "").strip() or None
    if not category:
        return False, "نوع المصروف مطلوب"
    if not description:
        return False, "الوصف مطلوب"
    if not payment_method:
        return False, "طريقة الدفع مطلوبة"
    try:
        amount = _ensure_non_negative_amount(amount, allow_zero=False)
    except ValueError:
        return False, "يجب أن يكون مبلغ المصروف أكبر من صفر"

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        _, error_message = _get_open_session_or_error(cursor, session_id)
        if error_message:
            return False, "لا توجد جلسة كاشير مفتوحة"
        cursor.execute(
            """
            INSERT INTO expenses (session_id, expense_date, category, description, amount, payment_method, reference_number, notes, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, _now_str(), category, description, amount, payment_method, reference_number, notes, user_id),
        )
        expense_id = cursor.lastrowid
        conn.commit()
        return True, expense_id
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def delete_expense(expense_id, db_path=DEFAULT_DB_PATH):
    """Delete an expense only while its parent session remains open."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT e.id, s.status
            FROM expenses e
            JOIN pos_sessions s ON e.session_id = s.id
            WHERE e.id=?
            """,
            (expense_id,),
        )
        row = cursor.fetchone()
        if not row:
            return False, "المصروف غير موجود"
        if row["status"] != "OPEN":
            return False, "لا يمكن تعديل عملية مالية بعد إغلاق الجلسة"
        cursor.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        conn.commit()
        return True, "تم حذف المصروف بنجاح"
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def record_sale(customer_id, items, total_amount, discount, tax_amount, payment_method, session_id=None, db_path=DEFAULT_DB_PATH, user_id=None):
    """
    Record a sale atomically.

    items is a list of dicts:
    [{'product_id': id, 'quantity': q, 'unit_price': p, 'subtotal': s}, ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        total_amount = _ensure_non_negative_amount(total_amount)
        discount = _ensure_non_negative_amount(discount)
        tax_amount = _ensure_non_negative_amount(tax_amount)
        if not items:
            return False, "سلة المشتريات فارغة"

        if session_id is not None:
            _, error_message = _get_open_session_or_error(cursor, session_id)
            if error_message:
                return False, error_message

        cursor.execute(
            """
            INSERT INTO sales (sale_date, customer_id, total_amount, discount, tax_amount, payment_method, session_id, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (_now_str(), customer_id, total_amount, discount, tax_amount, payment_method, session_id, user_id),
        )
        sale_id = cursor.lastrowid

        for item in items:
            product_id = item["product_id"]
            quantity = int(item["quantity"])
            unit_price = round_amount(item.get("unit_price", 0.0))
            subtotal = round_amount(item.get("subtotal", 0.0))
            if quantity <= 0:
                raise ValueError("invalid_quantity")

            cursor.execute("SELECT stock_quantity, selling_price FROM products WHERE id=?", (product_id,))
            product_row = cursor.fetchone()
            if not product_row:
                return False, "أحد المنتجات لم يعد موجودًا"

            product_unit_id = item.get("product_unit_id")
            unit_name = item.get("unit_name")
            pieces_per_unit = item.get("pieces_per_unit")
            if product_unit_id is not None:
                cursor.execute(
                    "SELECT pu.pieces_per_unit, pu.selling_price, u.name AS unit_name FROM product_units pu JOIN units u ON u.id = pu.unit_id WHERE pu.id=? AND pu.product_id=? AND pu.is_active=1",
                    (product_unit_id, product_id),
                )
                unit_row = cursor.fetchone()
                if unit_row:
                    pieces_per_unit = unit_row["pieces_per_unit"]
                    unit_name = unit_name or unit_row["unit_name"]
                    if unit_price == 0:
                        unit_price = round_amount(unit_row["selling_price"])
            elif pieces_per_unit is None:
                default_unit = get_default_product_unit(product_id, db_path=db_path)
                if default_unit:
                    pieces_per_unit = default_unit["pieces_per_unit"]
                    unit_name = unit_name or default_unit["unit_name"]
                else:
                    pieces_per_unit = 1
                    unit_name = unit_name or "Piece"

            if pieces_per_unit is None:
                pieces_per_unit = 1

            required_base_quantity = calculate_base_quantity(quantity, pieces_per_unit)
            if product_row["stock_quantity"] < required_base_quantity:
                return False, "الكمية المطلوبة غير متوفرة في المخزون"

            if unit_price <= 0 and product_row["selling_price"] > 0:
                unit_price = round_amount(product_row["selling_price"])

            if subtotal <= 0:
                subtotal = round_amount(quantity * unit_price)

            cursor.execute(
                """
                INSERT INTO sale_items (sale_id, product_id, product_unit_id, unit_name, quantity, unit_price, pieces_per_unit, base_quantity, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sale_id, product_id, product_unit_id, unit_name, quantity, unit_price, pieces_per_unit, required_base_quantity, subtotal),
            )
            cursor.execute("UPDATE products SET stock_quantity = stock_quantity - ? WHERE id=?", (required_base_quantity, product_id))

        generic_customer_id = _get_generic_customer_id(cursor)
        if customer_id and customer_id != generic_customer_id:
            points_earned = calculate_loyalty_points(total_amount)
            if points_earned > 0:
                cursor.execute("UPDATE customers SET loyalty_points = loyalty_points + ? WHERE id=?", (points_earned, customer_id))

        conn.commit()
        return True, sale_id
    except ValueError:
        conn.rollback()
        return False, "بيانات البيع غير صحيحة"
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def get_recent_sales(limit=50, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.*, c.name AS customer_name
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        ORDER BY s.sale_date DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_sale_details(sale_id, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT si.*, p.name AS product_name, p.sku
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        WHERE si.sale_id = ?
        ORDER BY si.id
        """,
        (sale_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_sale_for_return(sale_id, db_path=DEFAULT_DB_PATH):
    """Return sale header details enriched with return totals for refund workflows."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.*, c.name AS customer_name,
               COALESCE(SUM(si.subtotal), 0) AS subtotal_amount,
               COALESCE((SELECT SUM(sr.total_amount) FROM sale_returns sr WHERE sr.original_sale_id = s.id), 0) AS returned_total
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        LEFT JOIN sale_items si ON si.sale_id = s.id
        WHERE s.id = ?
        GROUP BY s.id, c.name
        """,
        (sale_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    sale = dict(row)
    sale["subtotal_amount"] = round_amount(sale["subtotal_amount"])
    sale["returned_total"] = round_amount(sale["returned_total"])
    sale["remaining_returnable_amount"] = round_amount(max(0.0, sale["total_amount"] - sale["returned_total"]))
    return sale


def get_previously_returned_quantity(sale_item_id, db_path=DEFAULT_DB_PATH):
    """Return how many units have already been returned for a sale line."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM sale_return_items WHERE original_sale_item_id=?", (sale_item_id,))
    value = cursor.fetchone()[0] or 0
    conn.close()
    return value


def get_returnable_sale_items(sale_id, db_path=DEFAULT_DB_PATH):
    """Return original sale lines with returned and remaining quantities."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT si.id,
               si.sale_id,
               si.product_id,
               si.quantity,
               si.unit_price,
               si.subtotal,
               p.name AS product_name,
               p.sku,
               COALESCE((SELECT SUM(sri.quantity) FROM sale_return_items sri WHERE sri.original_sale_item_id = si.id), 0) AS returned_quantity
        FROM sale_items si
        JOIN products p ON p.id = si.product_id
        WHERE si.sale_id = ?
        ORDER BY si.id
        """,
        (sale_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    items = []
    for row in rows:
        item = dict(row)
        item["available_return_quantity"] = max(0, item["quantity"] - item["returned_quantity"])
        items.append(item)
    return items


def _allocate_header_amounts(original_items, total_tax, total_discount):
    allocations = {}
    subtotal = sum(_to_decimal(item["subtotal"]) for item in original_items)
    running_tax = Decimal("0.00")
    running_discount = Decimal("0.00")
    total_tax_dec = _to_decimal(total_tax)
    total_discount_dec = _to_decimal(total_discount)
    for index, item in enumerate(original_items):
        line_key = item["id"]
        line_subtotal = _to_decimal(item["subtotal"])
        if subtotal > 0:
            tax_share_raw = total_tax_dec * line_subtotal / subtotal
            discount_share_raw = total_discount_dec * line_subtotal / subtotal
        else:
            tax_share_raw = Decimal("0.00")
            discount_share_raw = Decimal("0.00")
        if index == len(original_items) - 1:
            line_tax = max(Decimal("0.00"), total_tax_dec - running_tax)
            line_discount = max(Decimal("0.00"), total_discount_dec - running_discount)
        else:
            line_tax = Decimal(str(round_amount(tax_share_raw)))
            line_discount = Decimal(str(round_amount(discount_share_raw)))
            running_tax += line_tax
            running_discount += line_discount
        allocations[line_key] = {
            "tax_total": round_amount(line_tax),
            "discount_total": round_amount(line_discount),
        }
    return allocations


def _get_returned_line_amounts(cursor, sale_item_id):
    cursor.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS returned_qty,
               COALESCE(SUM(tax_amount), 0) AS returned_tax,
               COALESCE(SUM(discount_amount), 0) AS returned_discount,
               COALESCE(SUM(line_total), 0) AS returned_total
        FROM sale_return_items
        WHERE original_sale_item_id = ?
        """,
        (sale_item_id,),
    )
    row = cursor.fetchone()
    return {
        "returned_qty": row["returned_qty"] or 0,
        "returned_tax": round_amount(row["returned_tax"] or 0.0),
        "returned_discount": round_amount(row["returned_discount"] or 0.0),
        "returned_total": round_amount(row["returned_total"] or 0.0),
    }


def _build_return_payload(cursor, original_sale_id, requested_map, refund_method):
    cursor.execute(
        """
        SELECT s.*, c.name AS customer_name, c.phone AS customer_phone
        FROM sales s
        LEFT JOIN customers c ON s.customer_id = c.id
        WHERE s.id=?
        """,
        (original_sale_id,),
    )
    sale_row = cursor.fetchone()
    if not sale_row:
        return None, None, None, "رقم الفاتورة غير موجود"

    cursor.execute(
        """
        SELECT si.*, p.sku, p.name AS product_name
        FROM sale_items si
        JOIN products p ON p.id = si.product_id
        WHERE si.sale_id=?
        ORDER BY si.id
        """,
        (original_sale_id,),
    )
    original_items = [dict(row) for row in cursor.fetchall()]
    if not original_items:
        return None, None, None, "لا توجد عناصر قابلة للاسترجاع في هذه الفاتورة"

    allocations = _allocate_header_amounts(original_items, sale_row["tax_amount"], sale_row["discount"])
    original_item_map = {item["id"]: item for item in original_items}
    return_lines = []
    total_return_amount = 0.0
    total_return_subtotal = 0.0
    total_return_tax = 0.0
    total_return_discount = 0.0

    for sale_item_id, quantity in requested_map.items():
        original_item = original_item_map.get(sale_item_id)
        if not original_item:
            return None, None, None, "المنتج غير موجود في الفاتورة الأصلية"

        returned_state = _get_returned_line_amounts(cursor, sale_item_id)
        available_quantity = original_item["quantity"] - returned_state["returned_qty"]
        if available_quantity <= 0:
            return None, None, None, "لا توجد كميات متاحة للاسترجاع"
        if quantity > available_quantity:
            return None, None, None, "الكمية المرتجعة أكبر من الكمية المتاحة"

        allocated_tax_total = allocations[sale_item_id]["tax_total"]
        allocated_discount_total = allocations[sale_item_id]["discount_total"]
        remaining_tax = round_amount(max(0.0, allocated_tax_total - returned_state["returned_tax"]))
        remaining_discount = round_amount(max(0.0, allocated_discount_total - returned_state["returned_discount"]))
        return_subtotal = round_amount(quantity * original_item["unit_price"])

        if original_item["quantity"] > 0:
            return_ratio = Decimal(quantity) / Decimal(original_item["quantity"])
        else:
            return_ratio = Decimal("0")

        if quantity == available_quantity:
            return_tax = remaining_tax
            return_discount = remaining_discount
        else:
            return_tax = round_amount(Decimal(str(allocated_tax_total)) * return_ratio)
            return_discount = round_amount(Decimal(str(allocated_discount_total)) * return_ratio)
            return_tax = min(return_tax, remaining_tax)
            return_discount = min(return_discount, remaining_discount)

        line_total = round_amount(max(0.0, return_subtotal + return_tax - return_discount))
        line = {
            "original_sale_item_id": sale_item_id,
            "product_id": original_item["product_id"],
            "product_name": original_item["product_name"],
            "sku": original_item["sku"],
            "quantity": quantity,
            "unit_price": round_amount(original_item["unit_price"]),
            "subtotal": return_subtotal,
            "tax_amount": return_tax,
            "discount_amount": return_discount,
            "line_total": line_total,
            "sold_quantity": original_item["quantity"],
            "returned_quantity": returned_state["returned_qty"],
            "available_return_quantity": available_quantity,
        }
        return_lines.append(line)
        total_return_amount = round_amount(total_return_amount + line_total)
        total_return_subtotal = round_amount(total_return_subtotal + return_subtotal)
        total_return_tax = round_amount(total_return_tax + return_tax)
        total_return_discount = round_amount(total_return_discount + return_discount)

    if total_return_amount > round_amount(sale_row["total_amount"]):
        return None, None, None, "إجمالي الاسترجاع أكبر من قيمة الفاتورة الأصلية"

    resolved_refund_method = sale_row["payment_method"] if refund_method == "نفس طريقة الدفع الأصلية" else refund_method
    resolved_refund_method = (resolved_refund_method or "").strip()
    if not resolved_refund_method:
        return None, None, None, "طريقة الاسترجاع مطلوبة"

    payload = {
        "return_lines": return_lines,
        "totals": {
            "subtotal": total_return_subtotal,
            "tax_amount": total_return_tax,
            "discount_amount": total_return_discount,
            "total_amount": total_return_amount,
        },
    }
    return sale_row, resolved_refund_method, payload, None


def preview_sale_return(original_sale_id, items, refund_method="نفس طريقة الدفع الأصلية", db_path=DEFAULT_DB_PATH):
    """Return an exact refund preview using the same calculation rules as commit-time returns."""
    if not items:
        return False, "اختر منتجًا واحدًا على الأقل للاسترجاع"
    requested_map = {}
    for item in items:
        try:
            sale_item_id = int(item["original_sale_item_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            return False, "بيانات الاسترجاع غير صحيحة"
        if quantity <= 0:
            return False, "لا توجد كميات متاحة للاسترجاع"
        if sale_item_id in requested_map:
            return False, "لا يمكن تكرار نفس الصنف في فاتورة الاسترجاع"
        requested_map[sale_item_id] = quantity

    conn = get_connection(db_path)
    cursor = conn.cursor()
    sale_row, resolved_refund_method, payload, error_message = _build_return_payload(
        cursor, original_sale_id, requested_map, refund_method
    )
    conn.close()
    if error_message:
        return False, error_message

    return True, {
        "sale": dict(sale_row),
        "refund_method": resolved_refund_method,
        "items": payload["return_lines"],
        "totals": payload["totals"],
    }


def record_sale_return(original_sale_id, session_id, items, refund_method, reason=None, notes=None, db_path=DEFAULT_DB_PATH, user_id=None):
    """Create a full or partial return linked to an original sale in one transaction."""
    if not items:
        return False, "اختر منتجًا واحدًا على الأقل للاسترجاع"
    requested_map = {}
    for item in items:
        try:
            sale_item_id = int(item["original_sale_item_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            return False, "بيانات الاسترجاع غير صحيحة"
        if quantity <= 0:
            return False, "لا توجد كميات متاحة للاسترجاع"
        if sale_item_id in requested_map:
            return False, "لا يمكن تكرار نفس الصنف في فاتورة الاسترجاع"
        requested_map[sale_item_id] = quantity

    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        _, error_message = _get_open_session_or_error(cursor, session_id)
        if error_message:
            return False, "لا توجد جلسة كاشير مفتوحة" if "لا توجد" in error_message else error_message

        sale_row, resolved_refund_method, payload, error_message = _build_return_payload(
            cursor, original_sale_id, requested_map, refund_method
        )
        if error_message:
            return False, error_message
        return_lines = payload["return_lines"]
        total_return_amount = payload["totals"]["total_amount"]

        cursor.execute(
            """
            INSERT INTO sale_returns (original_sale_id, session_id, return_date, total_amount, refund_method, reason, notes, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (original_sale_id, session_id, _now_str(), total_return_amount, resolved_refund_method, (reason or "").strip() or None, (notes or "").strip() or None, user_id),
        )
        return_id = cursor.lastrowid

        for line in return_lines:
            cursor.execute(
                """
                INSERT INTO sale_return_items (
                    return_id, original_sale_item_id, product_id, quantity,
                    unit_price, subtotal, tax_amount, discount_amount, line_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (line["return_id"] if "return_id" in line else return_id, line["original_sale_item_id"], line["product_id"], line["quantity"], line["unit_price"], line["subtotal"], line["tax_amount"], line["discount_amount"], line["line_total"]),
            )
            cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (line["quantity"], line["product_id"]))

        generic_customer_id = _get_generic_customer_id(cursor)
        if sale_row["customer_id"] and sale_row["customer_id"] != generic_customer_id:
            points_to_deduct = calculate_loyalty_points(total_return_amount)
            if points_to_deduct > 0:
                cursor.execute(
                    """
                    UPDATE customers
                    SET loyalty_points = CASE
                        WHEN loyalty_points >= ? THEN loyalty_points - ?
                        ELSE 0
                    END
                    WHERE id=?
                    """,
                    (points_to_deduct, points_to_deduct, sale_row["customer_id"]),
                )

        conn.commit()
        return True, return_id
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def get_sale_returns(sale_id=None, session_id=None, db_path=DEFAULT_DB_PATH):
    """Return sales return documents filtered by sale or session."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    conditions = []
    params = []
    if sale_id is not None:
        conditions.append("sr.original_sale_id = ?")
        params.append(sale_id)
    if session_id is not None:
        conditions.append("sr.session_id = ?")
        params.append(session_id)
    sql = "SELECT sr.*, s.customer_id, c.name AS customer_name FROM sale_returns sr JOIN sales s ON s.id = sr.original_sale_id LEFT JOIN customers c ON c.id = s.customer_id"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY sr.return_date DESC, sr.id DESC"
    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_return_details(return_id, db_path=DEFAULT_DB_PATH):
    """Return a return header and all of its line items."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT sr.*, s.sale_date, s.payment_method AS original_payment_method,
               s.customer_id, c.name AS customer_name,
               ps.opened_at AS session_opened_at
        FROM sale_returns sr
        JOIN sales s ON s.id = sr.original_sale_id
        LEFT JOIN customers c ON c.id = s.customer_id
        JOIN pos_sessions ps ON ps.id = sr.session_id
        WHERE sr.id=?
        """,
        (return_id,),
    )
    header = cursor.fetchone()
    if not header:
        conn.close()
        return None
    cursor.execute(
        """
        SELECT sri.*, p.name AS product_name, p.sku
        FROM sale_return_items sri
        JOIN products p ON p.id = sri.product_id
        WHERE sri.return_id = ?
        ORDER BY sri.id
        """,
        (return_id,),
    )
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"header": dict(header), "items": items}


def calculate_session_summary(session_id, db_path=DEFAULT_DB_PATH):
    """Calculate sales, returns, expenses, and reconciliation figures for a session."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pos_sessions WHERE id=?", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return None

    cursor.execute("SELECT id, total_amount, payment_method FROM sales WHERE session_id=?", (session_id,))
    sales_rows = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT id, total_amount, refund_method FROM sale_returns WHERE session_id=?", (session_id,))
    return_rows = [dict(row) for row in cursor.fetchall()]
    cursor.execute("SELECT id, amount, payment_method, category FROM expenses WHERE session_id=?", (session_id,))
    expense_rows = [dict(row) for row in cursor.fetchall()]

    sales_totals = _aggregate_payment_totals(sales_rows, "total_amount", "payment_method")
    return_totals = _aggregate_payment_totals(return_rows, "total_amount", "refund_method")
    expense_totals = _aggregate_payment_totals(expense_rows, "amount", "payment_method")

    expense_categories = {}
    for row in expense_rows:
        expense_categories[row["category"]] = round_amount(expense_categories.get(row["category"], 0.0) + row["amount"])

    expected_cash = round_amount(session["opening_balance"] + sales_totals[PAYMENT_BUCKET_CASH] - return_totals[PAYMENT_BUCKET_CASH] - expense_totals[PAYMENT_BUCKET_CASH])
    difference = None
    if session["actual_closing_balance"] is not None:
        difference = round_amount(session["actual_closing_balance"] - expected_cash)

    conn.close()
    return {
        "session_id": session["id"],
        "opened_at": session["opened_at"],
        "closed_at": session["closed_at"],
        "opening_balance": round_amount(session["opening_balance"]),
        "opening_notes": session["opening_notes"],
        "closing_notes": session["closing_notes"],
        "sales_count": len(sales_rows),
        "total_sales": sales_totals["total"],
        "cash_sales": sales_totals[PAYMENT_BUCKET_CASH],
        "card_sales": sales_totals[PAYMENT_BUCKET_CARD],
        "electronic_sales": sales_totals[PAYMENT_BUCKET_ELECTRONIC],
        "other_sales": sales_totals[PAYMENT_BUCKET_OTHER],
        "returns_count": len(return_rows),
        "total_returns": return_totals["total"],
        "cash_returns": return_totals[PAYMENT_BUCKET_CASH],
        "card_returns": return_totals[PAYMENT_BUCKET_CARD],
        "electronic_returns": return_totals[PAYMENT_BUCKET_ELECTRONIC],
        "other_returns": return_totals[PAYMENT_BUCKET_OTHER],
        "expenses_count": len(expense_rows),
        "total_expenses": expense_totals["total"],
        "cash_expenses": expense_totals[PAYMENT_BUCKET_CASH],
        "card_expenses": expense_totals[PAYMENT_BUCKET_CARD],
        "electronic_expenses": expense_totals[PAYMENT_BUCKET_ELECTRONIC],
        "other_expenses": expense_totals[PAYMENT_BUCKET_OTHER],
        "non_cash_expenses": round_amount(expense_totals[PAYMENT_BUCKET_CARD] + expense_totals[PAYMENT_BUCKET_ELECTRONIC] + expense_totals[PAYMENT_BUCKET_OTHER]),
        "expected_cash_balance": expected_cash,
        "actual_closing_balance": round_amount(session["actual_closing_balance"]) if session["actual_closing_balance"] is not None else None,
        "difference": difference if difference is not None else (round_amount(session["balance_difference"]) if session["balance_difference"] is not None else None),
        "status": session["status"],
        "expenses_by_category": expense_categories,
        "expected_closing_balance": round_amount(session["expected_closing_balance"]) if session["expected_closing_balance"] is not None else expected_cash,
        "balance_difference": difference if difference is not None else (round_amount(session["balance_difference"]) if session["balance_difference"] is not None else None),
    }


def close_pos_session(session_id, actual_balance, notes=None, db_path=DEFAULT_DB_PATH, closed_by_user_id=None):
    """Close an open session after recalculating reconciliation totals."""
    try:
        actual_balance = _ensure_non_negative_amount(actual_balance)
    except ValueError:
        return False, "أدخل الرصيد الفعلي الموجود في الدرج"
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        _, error_message = _get_open_session_or_error(cursor, session_id)
        if error_message:
            return False, "لا توجد جلسة كاشير مفتوحة" if "لا توجد" in error_message else error_message
        summary = calculate_session_summary(session_id, db_path=db_path)
        expected_balance = round_amount(summary["expected_cash_balance"])
        difference = round_amount(actual_balance - expected_balance)
        cursor.execute(
            """
            UPDATE pos_sessions
            SET closed_at=?,
                expected_closing_balance=?,
                actual_closing_balance=?,
                balance_difference=?,
                closing_notes=?,
                status='CLOSED',
                closed_by_user_id=?
            WHERE id=? AND status='OPEN'
            """,
            (_now_str(), expected_balance, actual_balance, difference, (notes or "").strip() or None, closed_by_user_id, session_id),
        )
        if cursor.rowcount == 0:
            return False, "لا يمكن إغلاق جلسة مغلقة بالفعل"
        conn.commit()
        return True, session_id
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()


def get_dashboard_summary(db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS total_items, SUM(cost_price * stock_quantity) AS total_val FROM products")
    product_row = cursor.fetchone()
    total_products = product_row["total_items"] or 0
    inventory_value = round_amount(product_row["total_val"] or 0.0)
    cursor.execute("SELECT COUNT(*) FROM products WHERE stock_quantity <= reorder_level")
    low_stock = cursor.fetchone()[0]

    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE sale_date LIKE ?", (f"{today_str}%",))
    sales_today = round_amount(cursor.fetchone()[0] or 0.0)
    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sale_returns WHERE return_date LIKE ?", (f"{today_str}%",))
    returns_today = round_amount(cursor.fetchone()[0] or 0.0)
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE expense_date LIKE ?", (f"{today_str}%",))
    expenses_today = round_amount(cursor.fetchone()[0] or 0.0)
    conn.close()

    active_session = get_active_pos_session(db_path=db_path)
    session_summary = calculate_session_summary(active_session["id"], db_path=db_path) if active_session else None
    return {
        "total_products": total_products,
        "inventory_value": inventory_value,
        "low_stock": low_stock,
        "sales_today": sales_today,
        "returns_today": returns_today,
        "expenses_today": expenses_today,
        "net_sales_today": round_amount(sales_today - returns_today),
        "current_session_status": "مفتوحة" if active_session else "لا توجد جلسة كاشير مفتوحة",
        "current_session_id": active_session["id"] if active_session else None,
        "current_session_expected_cash": session_summary["expected_cash_balance"] if session_summary else 0.0,
        "current_session_opened_at": active_session["opened_at"] if active_session else None,
        "net_cash_movement_today": round_amount((session_summary["cash_sales"] if session_summary else 0.0) - (session_summary["cash_returns"] if session_summary else 0.0) - (session_summary["cash_expenses"] if session_summary else 0.0)),
    }


def get_sales_chart_data(db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    days = []
    revenues = []
    months_ar = {
        1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
        7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
    }
    for index in range(6, -1, -1):
        current_day = datetime.now() - timedelta(days=index)
        date_string = current_day.strftime("%Y-%m-%d")
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales WHERE sale_date LIKE ?", (f"{date_string}%",))
        gross_sales = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sale_returns WHERE return_date LIKE ?", (f"{date_string}%",))
        returns = cursor.fetchone()[0] or 0.0
        days.append(f"{current_day.day} {months_ar[current_day.month]}")
        revenues.append(round_amount(gross_sales - returns))
    conn.close()
    return days, revenues


def get_top_selling_products_data(limit=5, db_path=DEFAULT_DB_PATH):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT p.name,
               COALESCE(SUM(si.quantity), 0) - COALESCE((SELECT SUM(sri.quantity) FROM sale_return_items sri WHERE sri.product_id = p.id), 0) AS net_sold
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
        GROUP BY si.product_id, p.name
        ORDER BY net_sold DESC, p.name ASC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    names = [row["name"] for row in rows if row["net_sold"] > 0]
    quantities = [row["net_sold"] for row in rows if row["net_sold"] > 0]
    return names, quantities


def get_financial_overview(db_path=DEFAULT_DB_PATH):
    """Return analytics metrics adjusted for returns and expenses."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sales")
    gross_sales = round_amount(cursor.fetchone()[0] or 0.0)
    cursor.execute("SELECT COALESCE(SUM(total_amount), 0) FROM sale_returns")
    returns_total = round_amount(cursor.fetchone()[0] or 0.0)
    cursor.execute("SELECT COALESCE(SUM(si.quantity * p.cost_price), 0) FROM sale_items si JOIN products p ON si.product_id = p.id")
    gross_cogs = round_amount(cursor.fetchone()[0] or 0.0)
    cursor.execute("SELECT COALESCE(SUM(sri.quantity * p.cost_price), 0) FROM sale_return_items sri JOIN products p ON sri.product_id = p.id")
    returned_cogs = round_amount(cursor.fetchone()[0] or 0.0)
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
    expenses_total = round_amount(cursor.fetchone()[0] or 0.0)
    conn.close()

    net_sales = round_amount(gross_sales - returns_total)
    net_cogs = round_amount(gross_cogs - returned_cogs)
    gross_profit = round_amount(net_sales - net_cogs)
    operating_result = round_amount(gross_profit - expenses_total)
    margin = round_amount((gross_profit / net_sales * 100) if net_sales > 0 else 0.0)
    return {
        "gross_sales": gross_sales,
        "returns_total": returns_total,
        "net_sales": net_sales,
        "gross_cogs": gross_cogs,
        "returned_cogs": returned_cogs,
        "net_cogs": net_cogs,
        "gross_profit_after_returns": gross_profit,
        "expenses_total": expenses_total,
        "operating_result": operating_result,
        "profit_margin": margin,
    }


def get_combined_report_rows(db_path=DEFAULT_DB_PATH):
    """Return unified sale, return, and expense rows for CSV export."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 'Sale' AS transaction_type,
               s.id AS document_id,
               NULL AS original_sale_id,
               s.session_id,
               s.sale_date AS transaction_date,
               COALESCE(c.name, 'عميل عام (نقدي)') AS subject_name,
               s.total_amount AS amount,
               s.payment_method AS payment_method,
               NULL AS category,
               NULL AS notes
        FROM sales s
        LEFT JOIN customers c ON c.id = s.customer_id
        UNION ALL
        SELECT 'Return' AS transaction_type,
               sr.id AS document_id,
               sr.original_sale_id,
               sr.session_id,
               sr.return_date AS transaction_date,
               COALESCE(c.name, 'عميل عام (نقدي)') AS subject_name,
               sr.total_amount AS amount,
               sr.refund_method AS payment_method,
               sr.reason AS category,
               sr.notes AS notes
        FROM sale_returns sr
        JOIN sales s ON s.id = sr.original_sale_id
        LEFT JOIN customers c ON c.id = s.customer_id
        UNION ALL
        SELECT 'Expense' AS transaction_type,
               e.id AS document_id,
               NULL AS original_sale_id,
               e.session_id,
               e.expense_date AS transaction_date,
               e.description AS subject_name,
               e.amount AS amount,
               e.payment_method AS payment_method,
               e.category AS category,
               e.notes AS notes
        FROM expenses e
        ORDER BY transaction_date DESC, document_id DESC
        """
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows