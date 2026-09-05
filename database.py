"""
Database layer for the Wedding Expense Tracker.

Responsible for:
- Creating/migrating the SQLite schema
- CRUD operations on expenses
- Visibility-aware reads (filtering happens in SQL, not in the UI)
- Simple key/value application settings (e.g. cross-side visibility)

No Streamlit or UI code lives here — keep this module UI-agnostic.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DEFAULT_SETTINGS

DB_PATH = Path("wedding_expenses.db")


@contextmanager
def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _table_exists(conn, table_name):
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _column_names(conn, table_name):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def _create_fresh_expenses_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT NOT NULL,
            entered_by TEXT NOT NULL DEFAULT 'Groom',
            expense_for TEXT NOT NULL DEFAULT 'Shared',
            purchased_for TEXT NOT NULL DEFAULT 'Both',
            category TEXT NOT NULL,
            expense_type TEXT,
            description TEXT NOT NULL,
            vendor TEXT,
            quantity REAL DEFAULT 1,
            planned_amount REAL DEFAULT 0,
            actual_amount REAL DEFAULT 0,
            paid_amount REAL DEFAULT 0,
            paid_by TEXT,
            status TEXT NOT NULL DEFAULT 'Planned',
            due_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _migrate_legacy_schema(conn):
    """
    Migrates the original schema (where the `expense_type` column
    actually held Groom/Bride ownership, i.e. what is now
    `expense_for`) into the new schema, without losing any rows.

    Safe to call multiple times — every step checks column
    existence first.
    """

    columns = _column_names(conn, "expenses")

    # Old schema signature: has "expense_type" but no "expense_for" yet.
    is_legacy = "expense_type" in columns and "expense_for" not in columns

    if is_legacy:
        # The old "expense_type" column held Groom/Bride semantics —
        # that concept is now called "expense_for".
        conn.execute(
            "ALTER TABLE expenses RENAME COLUMN expense_type TO expense_for"
        )
        columns = _column_names(conn, "expenses")

    # Add any columns that are missing (works for both legacy and
    # partially-upgraded databases).
    if "entered_by" not in columns:
        conn.execute("ALTER TABLE expenses ADD COLUMN entered_by TEXT")
    if "purchased_for" not in columns:
        conn.execute("ALTER TABLE expenses ADD COLUMN purchased_for TEXT")
    if "expense_for" not in columns:
        # Extremely defensive fallback in case neither old nor new
        # column existed for some reason.
        conn.execute(
            "ALTER TABLE expenses ADD COLUMN expense_for TEXT NOT NULL DEFAULT 'Shared'"
        )
    if "expense_type" not in columns:
        # Re-add expense_type with its NEW meaning (specific item),
        # since the old column of that name was renamed above.
        conn.execute("ALTER TABLE expenses ADD COLUMN expense_type TEXT")

    # Backfill sensible defaults for pre-existing rows so nothing is
    # left NULL. Best-effort assumption: whoever the expense was FOR
    # is also who entered/purchased it, unless already set.
    conn.execute(
        "UPDATE expenses SET entered_by = expense_for "
        "WHERE entered_by IS NULL OR entered_by = ''"
    )
    conn.execute(
        "UPDATE expenses SET purchased_for = expense_for "
        "WHERE purchased_for IS NULL OR purchased_for = ''"
    )
    conn.execute(
        "UPDATE expenses SET expense_for = 'Shared' "
        "WHERE expense_for IS NULL OR expense_for = ''"
    )
    conn.execute(
        "UPDATE expenses SET entered_by = 'Groom' "
        "WHERE entered_by NOT IN ('Groom', 'Bride')"
    )


def _ensure_indexes(conn):
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_entered_by ON expenses(entered_by)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_expense_for ON expenses(expense_for)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_expense_date ON expenses(expense_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_expenses_status ON expenses(status)"
    )


def _ensure_settings_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )


def init_db():
    """
    Creates the database if it doesn't exist, or migrates an
    existing (older) database in place. Never drops data.
    """

    with get_connection() as conn:
        if _table_exists(conn, "expenses"):
            _migrate_legacy_schema(conn)
        else:
            _create_fresh_expenses_table(conn)

        _ensure_indexes(conn)
        _ensure_settings_table(conn)


# ============================================================
# SETTINGS
# ============================================================

def get_setting(key, default=None):
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row["value"] if row else default


def get_bool_setting(key, default=False):
    value = get_setting(key, "1" if default else "0")
    return str(value) == "1"


def set_setting(key, value):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )


def get_all_settings():
    with get_connection() as conn:
        cursor = conn.execute("SELECT key, value FROM settings")
        return {row["key"]: row["value"] for row in cursor.fetchall()}


# ============================================================
# EXPENSES — WRITE
# ============================================================

def add_expense(
    expense_date,
    entered_by,
    expense_for,
    purchased_for,
    category,
    expense_type,
    description,
    vendor,
    quantity,
    planned_amount,
    actual_amount,
    paid_amount,
    paid_by,
    status,
    due_date,
    notes,
):
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO expenses (
                expense_date,
                entered_by,
                expense_for,
                purchased_for,
                category,
                expense_type,
                description,
                vendor,
                quantity,
                planned_amount,
                actual_amount,
                paid_amount,
                paid_by,
                status,
                due_date,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expense_date,
                entered_by,
                expense_for,
                purchased_for,
                category,
                expense_type,
                description,
                vendor,
                quantity,
                planned_amount,
                actual_amount,
                paid_amount,
                paid_by,
                status,
                due_date,
                notes,
            ),
        )

        return cursor.lastrowid


def update_expense(
    expense_id,
    expense_date,
    entered_by,
    expense_for,
    purchased_for,
    category,
    expense_type,
    description,
    vendor,
    quantity,
    planned_amount,
    actual_amount,
    paid_amount,
    paid_by,
    status,
    due_date,
    notes,
):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE expenses
            SET
                expense_date = ?,
                entered_by = ?,
                expense_for = ?,
                purchased_for = ?,
                category = ?,
                expense_type = ?,
                description = ?,
                vendor = ?,
                quantity = ?,
                planned_amount = ?,
                actual_amount = ?,
                paid_amount = ?,
                paid_by = ?,
                status = ?,
                due_date = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                expense_date,
                entered_by,
                expense_for,
                purchased_for,
                category,
                expense_type,
                description,
                vendor,
                quantity,
                planned_amount,
                actual_amount,
                paid_amount,
                paid_by,
                status,
                due_date,
                notes,
                expense_id,
            ),
        )


def delete_expense(expense_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))


# ============================================================
# EXPENSES — READ (visibility enforced here, at the query level)
# ============================================================

def get_expenses(allowed_entered_by=None):
    """
    Returns expense rows, restricted to the given `entered_by`
    values. Pass `None` for unrestricted (admin) access.

    Enforcing this filter in SQL — rather than fetching everything
    and hiding rows in the UI — ensures a user can never retrieve
    data they aren't permitted to see, regardless of what the UI
    does with it.
    """

    with get_connection() as conn:
        if allowed_entered_by is None:
            cursor = conn.execute(
                "SELECT * FROM expenses ORDER BY expense_date DESC, id DESC"
            )
        else:
            allowed_entered_by = list(allowed_entered_by)

            if not allowed_entered_by:
                return []

            placeholders = ",".join("?" for _ in allowed_entered_by)
            cursor = conn.execute(
                f"""
                SELECT * FROM expenses
                WHERE entered_by IN ({placeholders})
                ORDER BY expense_date DESC, id DESC
                """,
                allowed_entered_by,
            )

        return cursor.fetchall()


def get_expense_by_id(expense_id, allowed_entered_by=None):
    """
    Fetches a single expense by id, but only if it falls within
    `allowed_entered_by` (or unrestricted if None). Returns None
    if not found or not permitted — callers must treat both cases
    identically so visibility can't be probed by id.
    """

    with get_connection() as conn:
        if allowed_entered_by is None:
            cursor = conn.execute(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            )
        else:
            allowed_entered_by = list(allowed_entered_by)

            if not allowed_entered_by:
                return None

            placeholders = ",".join("?" for _ in allowed_entered_by)
            cursor = conn.execute(
                f"""
                SELECT * FROM expenses
                WHERE id = ? AND entered_by IN ({placeholders})
                """,
                [expense_id, *allowed_entered_by],
            )

        return cursor.fetchone()
