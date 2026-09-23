"""Local login for the web app.

First-run accounts are created only when the users table is empty:
- username ``manager`` / password from STORE_MANAGER_PASSWORD (default ``manager123``)
- username ``cashier`` / password from STORE_CASHIER_PASSWORD (default ``cashier123``)

Change these passwords after the first login. They are for a single local store.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from core.db import TIMESTAMP_FORMAT, _now_str, get_connection

DEFAULT_MANAGER_USERNAME = "manager"
DEFAULT_CASHIER_USERNAME = "cashier"
DEFAULT_MANAGER_PASSWORD = "manager123"
DEFAULT_CASHIER_PASSWORD = "cashier123"
SESSION_HOURS = 12
PBKDF2_ITERATIONS = 260000
COOKIE_NAME = "store_session"


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password, password_hash):
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except (AttributeError, ValueError):
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def _public_user(row):
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def seed_default_users(db_path):
    """Insert the two local accounts when no users exist yet."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    now = _now_str()
    manager_password = os.environ.get("STORE_MANAGER_PASSWORD", DEFAULT_MANAGER_PASSWORD)
    cashier_password = os.environ.get("STORE_CASHIER_PASSWORD", DEFAULT_CASHIER_PASSWORD)
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?, ?, 'manager', 1, ?)",
        (DEFAULT_MANAGER_USERNAME, hash_password(manager_password), now),
    )
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?, ?, 'cashier', 1, ?)",
        (DEFAULT_CASHIER_USERNAME, hash_password(cashier_password), now),
    )
    conn.commit()
    conn.close()


def authenticate(username, password, db_path):
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", ((username or "").strip(),))
        row = cursor.fetchone()
    finally:
        conn.close()
    if not row or not row["is_active"]:
        return None
    if not verify_password(password or "", row["password_hash"]):
        return None
    return _public_user(row)


def create_session(user_id, db_path):
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(hours=SESSION_HOURS)).strftime(TIMESTAMP_FORMAT)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO auth_sessions (token, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token, user_id, expires_at, _now_str()),
    )
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token, db_path):
    if not token:
        return None
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT u.*
        FROM auth_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
        """,
        (token, _now_str()),
    )
    row = cursor.fetchone()
    conn.close()
    return _public_user(row)


def delete_session(token, db_path):
    if not token:
        return
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def list_users(db_path):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY username")
    rows = cursor.fetchall()
    conn.close()
    return [_public_user(row) for row in rows]


def _active_manager_count(cursor, exclude_user_id=None):
    if exclude_user_id is None:
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'manager' AND is_active = 1")
        return cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'manager' AND is_active = 1 AND id != ?",
        (exclude_user_id,),
    )
    return cursor.fetchone()[0]


def create_user(username, password, role, db_path):
    username = (username or "").strip()
    password = password or ""
    if role not in {"manager", "cashier"}:
        return False, "الدور يجب أن يكون مديراً أو كاشير"
    if len(username) < 3:
        return False, "اسم المستخدم قصير جداً"
    if len(password) < 4:
        return False, "كلمة المرور قصيرة جداً"
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
            (username, hash_password(password), role, _now_str()),
        )
        user_id = cursor.lastrowid
        conn.commit()
        return True, user_id
    except Exception:
        conn.rollback()
        return False, "اسم المستخدم مستخدم مسبقاً"
    finally:
        conn.close()


def update_user(user_id, db_path, role=None, is_active=None, password=None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False, "المستخدم غير موجود"
        next_role = role if role is not None else row["role"]
        next_active = row["is_active"] if is_active is None else (1 if is_active else 0)
        if next_role not in {"manager", "cashier"}:
            return False, "الدور يجب أن يكون مديراً أو كاشير"
        if password is not None and password != "" and len(password) < 4:
            return False, "كلمة المرور قصيرة جداً"
        loses_manager = row["role"] == "manager" and row["is_active"] and (next_role != "manager" or not next_active)
        if loses_manager and _active_manager_count(cursor, exclude_user_id=user_id) == 0:
            return False, "يجب أن يبقى مدير نشط واحد على الأقل"
        cursor.execute(
            "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
            (next_role, next_active, user_id),
        )
        if password:
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
        conn.commit()
        return True, "تم تحديث المستخدم"
    except Exception:
        conn.rollback()
        return False, "حدث خطأ، لم يتم حفظ أي تغييرات"
    finally:
        conn.close()
