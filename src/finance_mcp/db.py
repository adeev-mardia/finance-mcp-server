"""SQLite persistence layer for the finance ledger.

Kept deliberately dependency-free (stdlib `sqlite3` only) so the server has
no external database to stand up -- the whole thing is a single file on disk.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterator, Optional

DEFAULT_DB_PATH = os.environ.get(
    "FINANCE_MCP_DB", os.path.join(os.path.dirname(__file__), "..", "..", "data", "finance.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    kind    TEXT NOT NULL CHECK (kind IN ('income', 'expense')) DEFAULT 'expense'
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_on TEXT NOT NULL,             -- ISO date, e.g. 2026-09-27
    amount      REAL NOT NULL,             -- positive = income, negative = expense
    category_id INTEGER NOT NULL REFERENCES categories(id),
    merchant    TEXT,
    note        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(occurred_on);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);

CREATE TABLE IF NOT EXISTS budgets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id   INTEGER NOT NULL REFERENCES categories(id),
    monthly_limit REAL NOT NULL,
    UNIQUE(category_id)
);
"""

DEFAULT_CATEGORIES = [
    ("Salary", "income"),
    ("Freelance", "income"),
    ("Groceries", "expense"),
    ("Rent", "expense"),
    ("Transport", "expense"),
    ("Dining Out", "expense"),
    ("Subscriptions", "expense"),
    ("Entertainment", "expense"),
    ("Education", "expense"),
    ("Health", "expense"),
    ("Other", "expense"),
]


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    db_path = db_path or DEFAULT_DB_PATH
    _ensure_parent_dir(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None, seed_categories: bool = True) -> None:
    db_path = db_path or DEFAULT_DB_PATH
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        if seed_categories:
            for name, kind in DEFAULT_CATEGORIES:
                conn.execute(
                    "INSERT OR IGNORE INTO categories (name, kind) VALUES (?, ?)",
                    (name, kind),
                )


def _validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"occurred_on must be YYYY-MM-DD, got {value!r}") from exc
    return value


@dataclass
class TransactionResult:
    id: int
    occurred_on: str
    amount: float
    category: str
    merchant: Optional[str]
    note: Optional[str]


def get_or_create_category(conn: sqlite3.Connection, name: str, kind: str = "expense") -> int:
    row = conn.execute("SELECT id FROM categories WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO categories (name, kind) VALUES (?, ?)", (name, kind)
    )
    return cur.lastrowid


def add_transaction(
    amount: float,
    category: str,
    occurred_on: Optional[str] = None,
    merchant: Optional[str] = None,
    note: Optional[str] = None,
    db_path: Optional[str] = None,
) -> TransactionResult:
    occurred_on = _validate_date(occurred_on or date.today().isoformat())
    kind = "income" if amount >= 0 else "expense"
    with get_connection(db_path) as conn:
        cat_id = get_or_create_category(conn, category, kind)
        cur = conn.execute(
            """INSERT INTO transactions (occurred_on, amount, category_id, merchant, note)
               VALUES (?, ?, ?, ?, ?)""",
            (occurred_on, amount, cat_id, merchant, note),
        )
        return TransactionResult(
            id=cur.lastrowid,
            occurred_on=occurred_on,
            amount=amount,
            category=category,
            merchant=merchant,
            note=note,
        )


def list_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None,
) -> list[dict]:
    query = """
        SELECT t.id, t.occurred_on, t.amount, c.name AS category, t.merchant, t.note
        FROM transactions t JOIN categories c ON c.id = t.category_id
        WHERE 1 = 1
    """
    params: list = []
    if start_date:
        query += " AND t.occurred_on >= ?"
        params.append(_validate_date(start_date))
    if end_date:
        query += " AND t.occurred_on <= ?"
        params.append(_validate_date(end_date))
    if category:
        query += " AND c.name = ?"
        params.append(category)
    query += " ORDER BY t.occurred_on DESC, t.id DESC LIMIT ?"
    params.append(limit)

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def spending_by_category(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[str] = None,
) -> list[dict]:
    query = """
        SELECT c.name AS category, c.kind AS kind,
               ROUND(SUM(t.amount), 2) AS total,
               COUNT(*) AS transaction_count
        FROM transactions t JOIN categories c ON c.id = t.category_id
        WHERE 1 = 1
    """
    params: list = []
    if start_date:
        query += " AND t.occurred_on >= ?"
        params.append(_validate_date(start_date))
    if end_date:
        query += " AND t.occurred_on <= ?"
        params.append(_validate_date(end_date))
    query += " GROUP BY c.name, c.kind ORDER BY total ASC"

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    rows = spending_by_category(start_date, end_date, db_path)
    income = round(sum(r["total"] for r in rows if r["kind"] == "income"), 2)
    expense = round(sum(-r["total"] for r in rows if r["kind"] == "expense" and r["total"] < 0), 2)
    # also count expense categories where total happens to be positive-recorded (shouldn't normally happen)
    net = round(income - expense, 2)
    top_expense_categories = sorted(
        (r for r in rows if r["kind"] == "expense"),
        key=lambda r: r["total"],
    )[:5]
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_income": income,
        "total_expense": expense,
        "net": net,
        "top_expense_categories": [
            {"category": r["category"], "total": abs(r["total"])} for r in top_expense_categories
        ],
    }


def set_budget(category: str, monthly_limit: float, db_path: Optional[str] = None) -> dict:
    db_path = db_path or DEFAULT_DB_PATH
    with get_connection(db_path) as conn:
        cat_id = get_or_create_category(conn, category, "expense")
        conn.execute(
            """INSERT INTO budgets (category_id, monthly_limit) VALUES (?, ?)
               ON CONFLICT(category_id) DO UPDATE SET monthly_limit = excluded.monthly_limit""",
            (cat_id, monthly_limit),
        )
        return {"category": category, "monthly_limit": monthly_limit}


def update_transaction(
    transaction_id: int,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    occurred_on: Optional[str] = None,
    merchant: Optional[str] = None,
    note: Optional[str] = None,
    db_path: Optional[str] = None,
) -> TransactionResult:
    """Update one or more fields of an existing transaction. Fields left as
    None are left unchanged. Raises ValueError if the id doesn't exist."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """SELECT t.id, t.occurred_on, t.amount, c.name AS category, t.merchant, t.note
               FROM transactions t JOIN categories c ON c.id = t.category_id
               WHERE t.id = ?""",
            (transaction_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"no transaction with id {transaction_id}")

        new_amount = amount if amount is not None else row["amount"]
        new_occurred_on = _validate_date(occurred_on) if occurred_on else row["occurred_on"]
        new_merchant = merchant if merchant is not None else row["merchant"]
        new_note = note if note is not None else row["note"]

        if category is not None:
            kind = "income" if new_amount >= 0 else "expense"
            cat_id = get_or_create_category(conn, category, kind)
            new_category = category
        else:
            cat_id = conn.execute(
                "SELECT category_id FROM transactions WHERE id = ?", (transaction_id,)
            ).fetchone()["category_id"]
            new_category = row["category"]

        conn.execute(
            """UPDATE transactions
               SET occurred_on = ?, amount = ?, category_id = ?, merchant = ?, note = ?
               WHERE id = ?""",
            (new_occurred_on, new_amount, cat_id, new_merchant, new_note, transaction_id),
        )
        return TransactionResult(
            id=transaction_id,
            occurred_on=new_occurred_on,
            amount=new_amount,
            category=new_category,
            merchant=new_merchant,
            note=new_note,
        )


def delete_transaction(transaction_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a transaction by id. Returns True if a row was deleted."""
    with get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        return cur.rowcount > 0


def list_categories(db_path: Optional[str] = None) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT name, kind FROM categories ORDER BY kind, name").fetchall()
        return [dict(r) for r in rows]


def budget_status(month: str, db_path: Optional[str] = None) -> list[dict]:
    """month: 'YYYY-MM'"""
    db_path = db_path or DEFAULT_DB_PATH
    start = f"{month}-01"
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT c.name AS category, b.monthly_limit AS monthly_limit,
                   COALESCE(ROUND(SUM(-t.amount), 2), 0) AS spent
            FROM budgets b
            JOIN categories c ON c.id = b.category_id
            LEFT JOIN transactions t
                ON t.category_id = b.category_id
                AND t.occurred_on >= ?
                AND t.occurred_on < date(?, '+1 month')
                AND t.amount < 0
            GROUP BY c.name, b.monthly_limit
            ORDER BY c.name
            """,
            (start, start),
        ).fetchall()
        result = []
        for r in rows:
            spent = r["spent"] or 0.0
            limit = r["monthly_limit"]
            result.append(
                {
                    "category": r["category"],
                    "monthly_limit": limit,
                    "spent": spent,
                    "remaining": round(limit - spent, 2),
                    "percent_used": round((spent / limit) * 100, 1) if limit else None,
                    "over_budget": spent > limit,
                }
            )
        return result
