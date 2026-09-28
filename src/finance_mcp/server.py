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

from finance_mcp import csv_io, db

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


@mcp.tool()
def update_transaction(
    transaction_id: int,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    occurred_on: Optional[str] = None,
    merchant: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    """Edit an existing transaction by id. Only the fields you pass are changed.

    Args:
        transaction_id: The id of the transaction to edit (from add_transaction or list_transactions).
        amount: New signed amount, if changing it.
        category: New category name, if changing it.
        occurred_on: New date (YYYY-MM-DD), if changing it.
        merchant: New merchant/payer, if changing it.
        note: New note, if changing it.
    """
    db.init_db()
    result = db.update_transaction(
        transaction_id=transaction_id,
        amount=amount,
        category=category,
        occurred_on=occurred_on,
        merchant=merchant,
        note=note,
    )
    return result.__dict__


@mcp.tool()
def delete_transaction(transaction_id: int) -> dict:
    """Delete a transaction by id. Use list_transactions first to find the id."""
    db.init_db()
    deleted = db.delete_transaction(transaction_id=transaction_id)
    return {"transaction_id": transaction_id, "deleted": deleted}


@mcp.tool()
def list_categories() -> list[dict]:
    """List every category currently in use, with whether it's income or expense."""
    db.init_db()
    return db.list_categories()


@mcp.tool()
def import_transactions_csv(
    file_path: str,
    date_column: str = "Date",
    amount_column: Optional[str] = "Amount",
    debit_column: Optional[str] = None,
    credit_column: Optional[str] = None,
    description_column: Optional[str] = "Description",
    category_column: Optional[str] = None,
    default_category: str = "Uncategorized",
    date_format: Optional[str] = None,
    flip_sign: bool = False,
) -> dict:
    """Import a real bank or credit card CSV export into the ledger.

    Point this at the CSV your bank lets you download and tell it which
    columns are which -- exports vary a lot, so nothing is guessed.

    Args:
        file_path: Path to the CSV file on disk.
        date_column: Header name of the date column (default "Date").
        amount_column: Header name of a single signed amount column, if your
            export has one. Leave unset if using debit_column/credit_column instead.
        debit_column: Header name of a debit/withdrawal column, if your export
            splits debits and credits into separate columns.
        credit_column: Header name of a credit/deposit column.
        description_column: Header name to use as the transaction merchant/description.
        category_column: Header name holding a category, if your export has one.
        default_category: Category to use for rows with no category (default "Uncategorized").
        date_format: Explicit strptime format (e.g. "%m/%d/%Y") if auto-detection fails.
        flip_sign: Set True if expenses come in as positive numbers in your export.
    """
    db.init_db()
    return csv_io.import_csv(
        file_path=file_path,
        date_column=date_column,
        amount_column=amount_column,
        debit_column=debit_column,
        credit_column=credit_column,
        description_column=description_column,
        category_column=category_column,
        default_category=default_category,
        date_format=date_format,
        flip_sign=flip_sign,
    )


@mcp.tool()
def export_transactions_csv(
    file_path: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> dict:
    """Export transactions to a CSV file on disk, e.g. for backup or a spreadsheet.

    Args:
        file_path: Where to write the CSV.
        start_date: Optional inclusive lower bound, YYYY-MM-DD.
        end_date: Optional inclusive upper bound, YYYY-MM-DD.
        category: Optional single-category filter.
    """
    db.init_db()
    return csv_io.export_csv(file_path=file_path, start_date=start_date, end_date=end_date, category=category)


def main() -> None:
    db.init_db()
    mcp.run()


if __name__ == "__main__":
    main()
