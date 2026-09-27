"""MCP server exposing personal-finance analytics tools.

Run directly (stdio transport, the default MCP client transport):

    finance-mcp-server
    # or
    python -m finance_mcp.server

Point any MCP client (Claude Desktop, Claude Code, etc.) at this command
and it gets tools to record transactions, query spending, and track
budgets against a local SQLite ledger -- no cloud account required.
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from finance_mcp import db

mcp = FastMCP(
    name="finance-mcp-server",
    instructions=(
        "Tools for managing a personal finance ledger stored in local SQLite. "
        "Use add_transaction to record income/expenses, list_transactions and "
        "spending_by_category to inspect them, get_summary for a quick overview, "
        "and set_budget/get_budget_status to track monthly limits."
    ),
)


@mcp.tool()
def add_transaction(
    amount: float,
    category: str,
    occurred_on: Optional[str] = None,
    merchant: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    """Record a transaction. Use a positive amount for income, negative for an expense.

    Args:
        amount: Signed amount (positive = income, negative = expense).
        category: Category name, e.g. "Groceries" or "Salary". Created if new.
        occurred_on: Date as YYYY-MM-DD. Defaults to today if omitted.
        merchant: Optional merchant/payer name.
        note: Optional free-text note.
    """
    db.init_db()
    result = db.add_transaction(
        amount=amount, category=category, occurred_on=occurred_on, merchant=merchant, note=note
    )
    return result.__dict__


@mcp.tool()
def list_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List transactions, most recent first, with optional date-range/category filters.

    Args:
        start_date: Inclusive lower bound, YYYY-MM-DD.
        end_date: Inclusive upper bound, YYYY-MM-DD.
        category: Filter to a single category name.
        limit: Max rows to return (default 50).
    """
    db.init_db()
    return db.list_transactions(start_date=start_date, end_date=end_date, category=category, limit=limit)


@mcp.tool()
def spending_by_category(start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[dict]:
    """Aggregate income/expense totals grouped by category over an optional date range."""
    db.init_db()
    return db.spending_by_category(start_date=start_date, end_date=end_date)


@mcp.tool()
def get_summary(start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    """Get total income, total expense, net, and top 5 expense categories for a period."""
    db.init_db()
    return db.summary(start_date=start_date, end_date=end_date)


@mcp.tool()
def set_budget(category: str, monthly_limit: float) -> dict:
    """Set (or update) a monthly spending limit for a category.

    Args:
        category: Category name (created if it doesn't exist).
        monthly_limit: Positive monthly limit in the same currency as transactions.
    """
    db.init_db()
    return db.set_budget(category=category, monthly_limit=monthly_limit)


@mcp.tool()
def get_budget_status(month: str) -> list[dict]:
    """Get spend-vs-limit status for every budgeted category in a given month.

    Args:
        month: Month as YYYY-MM, e.g. "2026-09".
    """
    db.init_db()
    return db.budget_status(month=month)


def main() -> None:
    db.init_db()
    mcp.run()


if __name__ == "__main__":
    main()
