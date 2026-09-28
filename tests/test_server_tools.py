"""Smoke tests that the MCP tool functions (unwrapped) behave like the db layer.

FastMCP wraps functions in Tool objects; we call the underlying .fn to test
the business logic without spinning up a client/transport.
"""

import os
import tempfile

import pytest

from finance_mcp import db, server


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    monkeypatch.setattr(db, "DEFAULT_DB_PATH", path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def _fn(tool_name):
    return server.mcp._tool_manager._tools[tool_name].fn


def test_add_transaction_tool():
    result = _fn("add_transaction")(amount=-25.0, category="Transport", occurred_on="2026-09-05")
    assert result["amount"] == -25.0
    assert result["category"] == "Transport"


def test_summary_tool_reflects_added_transactions():
    _fn("add_transaction")(amount=1000.0, category="Salary", occurred_on="2026-09-01")
    _fn("add_transaction")(amount=-100.0, category="Groceries", occurred_on="2026-09-02")
    summary = _fn("get_summary")(start_date="2026-09-01", end_date="2026-09-30")
    assert summary["total_income"] == 1000.0
    assert summary["total_expense"] == 100.0


def test_budget_tools_round_trip():
    _fn("set_budget")(category="Entertainment", monthly_limit=100.0)
    _fn("add_transaction")(amount=-40.0, category="Entertainment", occurred_on="2026-09-10")
    status = _fn("get_budget_status")(month="2026-09")
    entry = next(s for s in status if s["category"] == "Entertainment")
    assert entry["spent"] == 40.0
    assert entry["remaining"] == 60.0


def test_update_and_delete_transaction_tools():
    added = _fn("add_transaction")(amount=-30.0, category="Transport", occurred_on="2026-09-05")
    updated = _fn("update_transaction")(transaction_id=added["id"], amount=-35.0)
    assert updated["amount"] == -35.0

    deleted = _fn("delete_transaction")(transaction_id=added["id"])
    assert deleted["deleted"] is True


def test_list_categories_tool():
    categories = _fn("list_categories")()
    assert any(c["name"] == "Groceries" for c in categories)


def test_import_and_export_csv_tools(tmp_path):
    import csv

    src = tmp_path / "import.csv"
    with open(src, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Date", "Amount", "Description"])
        writer.writeheader()
        writer.writerow({"Date": "2026-09-01", "Amount": "-15.00", "Description": "Bookstore"})

    result = _fn("import_transactions_csv")(file_path=str(src))
    assert result["imported"] == 1

    out = tmp_path / "export.csv"
    export_result = _fn("export_transactions_csv")(file_path=str(out))
    assert export_result["rows_written"] == 1
    assert out.exists()
