"""Additive Phase 1 schema for decimal inventory.

The migration adds nullable columns and empty supporting tables. It does not
update stock, cost, selling price, invoices, purchase lines, or unit costs.
Historical cost snapshots are left null. No opening average cost is assigned.

SQLite cannot drop a column that is part of a foreign key. The new columns are
therefore plain INTEGER or TEXT, with the intended references documented in
``docs/phase1_foundation.md``. New tables do use foreign keys; rollback drops
those tables before it drops columns.

Production ``store.db`` is refused by ``migrate_database`` and
``rollback_database``. ``init_db`` also skips this migration when its path is
that file, so starting the application does not change production.
"""

import sqlite3
from pathlib import Path


PHASE1_VERSION = 19
PHASE1_DESCRIPTION = (
    "Phase 1 decimal foundation: nullable decimal columns and empty supporting tables. "
    "Historical costs and opening averages were not filled."
)

NEW_COLUMNS = {
    "products": (
        ("base_unit_id", "INTEGER"),
        ("stock_quantity_decimal", "TEXT"),
        ("reorder_level_decimal", "TEXT"),
        ("average_cost", "TEXT"),
    ),
    "product_units": (("conversion_factor_decimal", "TEXT"),),
    "sale_items": (
        ("quantity_decimal", "TEXT"),
        ("base_quantity_decimal", "TEXT"),
        ("base_unit_cost", "TEXT"),
        ("cogs_amount", "TEXT"),
    ),
    "sale_return_items": (
        ("quantity_decimal", "TEXT"),
        ("base_quantity_decimal", "TEXT"),
        ("cost_snapshot", "TEXT"),
        ("cogs_amount", "TEXT"),
    ),
    "purchase_order_items": (
        ("purchase_unit_id", "INTEGER"),
        ("quantity_decimal", "TEXT"),
        ("conversion_factor_decimal", "TEXT"),
        ("base_quantity_decimal", "TEXT"),
        ("base_unit_cost", "TEXT"),
    ),
}

NEW_TABLES = (
    "purchase_returns",
    "inventory_adjustments",
    "opening_balances",
    "posting_keys",
)

NEW_INDEXES = (
    "idx_products_base_unit",
    "idx_opening_balances_product",
    "idx_inventory_adjustments_product",
    "idx_purchase_returns_product",
    "idx_purchase_returns_order",
)

TABLE_SQL = (
    """
    CREATE TABLE IF NOT EXISTS posting_keys (
        posting_key TEXT PRIMARY KEY,
        scope TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS opening_balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        base_unit_id INTEGER,
        quantity_decimal TEXT,
        average_cost TEXT,
        notes TEXT,
        verified_by TEXT,
        verification_date TEXT,
        created_at TEXT NOT NULL,
        posting_key TEXT UNIQUE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
        FOREIGN KEY (base_unit_id) REFERENCES units(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        previous_quantity_decimal TEXT,
        new_quantity_decimal TEXT,
        difference_decimal TEXT,
        average_cost_snapshot TEXT,
        value_amount TEXT,
        reason TEXT,
        user_id INTEGER,
        created_at TEXT NOT NULL,
        posting_key TEXT UNIQUE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS purchase_returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_order_id INTEGER,
        purchase_order_item_id INTEGER,
        product_id INTEGER NOT NULL,
        quantity_decimal TEXT,
        base_quantity_decimal TEXT,
        original_unit_cost TEXT,
        average_cost_snapshot TEXT,
        refund_amount TEXT,
        variance_amount TEXT,
        user_id INTEGER,
        created_at TEXT NOT NULL,
        posting_key TEXT UNIQUE,
        FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON DELETE RESTRICT,
        FOREIGN KEY (purchase_order_item_id) REFERENCES purchase_order_items(id) ON DELETE RESTRICT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """,
)

INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_products_base_unit ON products(base_unit_id)",
    "CREATE INDEX IF NOT EXISTS idx_opening_balances_product ON opening_balances(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_adjustments_product ON inventory_adjustments(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_purchase_returns_product ON purchase_returns(product_id)",
    "CREATE INDEX IF NOT EXISTS idx_purchase_returns_order ON purchase_returns(purchase_order_id)",
)


class ProductionMigrationBlocked(RuntimeError):
    """Phase 1 was pointed at the repository production database."""


def production_database_path():
    return Path(__file__).resolve().parents[1] / "store.db"


def is_production_database(db_path):
    if not db_path:
        return False
    return Path(db_path).expanduser().resolve() == production_database_path()


def _connect(db_path):
    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_exists(cursor, table_name):
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None


def _column_names(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def apply_phase1(cursor):
    """Add Phase 1 objects. Existing financial values are not updated."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            description TEXT
        )
        """
    )
    for table_name, columns in NEW_COLUMNS.items():
        if not _table_exists(cursor, table_name):
            continue
        present = set(_column_names(cursor, table_name))
        for column_name, column_type in columns:
            if column_name not in present:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
    for statement in TABLE_SQL:
        cursor.execute(statement)
    for statement in INDEX_SQL:
        cursor.execute(statement)
    cursor.execute(
        "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) VALUES (?, datetime('now'), ?)",
        (PHASE1_VERSION, PHASE1_DESCRIPTION),
    )


def phase1_has_posted_values(cursor):
    """True when a later phase has stored data that rollback must not discard."""
    for table_name, columns in NEW_COLUMNS.items():
        if not _table_exists(cursor, table_name):
            continue
        present = set(_column_names(cursor, table_name))
        usable = [column_name for column_name, _column_type in columns if column_name in present]
        if not usable:
            continue
        predicate = " OR ".join(f"{column_name} IS NOT NULL" for column_name in usable)
        cursor.execute(f"SELECT 1 FROM {table_name} WHERE {predicate} LIMIT 1")
        if cursor.fetchone() is not None:
            return True
    for table_name in NEW_TABLES:
        if not _table_exists(cursor, table_name):
            continue
        cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
        if cursor.fetchone() is not None:
            return True
    return False


def rollback_phase1(cursor):
    """Remove Phase 1 objects when none of them contain posted values."""
    if phase1_has_posted_values(cursor):
        raise RuntimeError("Phase 1 rollback refused because new columns or supporting tables contain data")
    for index_name in NEW_INDEXES:
        cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
    for table_name in NEW_TABLES:
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    for table_name, columns in NEW_COLUMNS.items():
        if not _table_exists(cursor, table_name):
            continue
        present = set(_column_names(cursor, table_name))
        for column_name, _column_type in columns:
            if column_name in present:
                cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
    if _table_exists(cursor, "schema_migrations"):
        cursor.execute("DELETE FROM schema_migrations WHERE version = ?", (PHASE1_VERSION,))


def migrate_database(db_path):
    if is_production_database(db_path):
        raise ProductionMigrationBlocked(
            f"Refusing to migrate the production database: {production_database_path()}"
        )
    connection = _connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        apply_phase1(cursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def rollback_database(db_path):
    if is_production_database(db_path):
        raise ProductionMigrationBlocked(
            f"Refusing to roll back the production database: {production_database_path()}"
        )
    connection = _connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        rollback_phase1(cursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
