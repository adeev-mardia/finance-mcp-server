import os
import tempfile

import pytest

from finance_mcp import db


@pytest.fixture()
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # let init_db create it fresh
    db.init_db(db_path=path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_init_db_seeds_categories(temp_db):
    with db.get_connection(temp_db) as conn:
        rows = conn.execute("SELECT name FROM categories").fetchall()
    names = {r["name"] for r in rows}
    assert "Groceries" in names
    assert "Salary" in names


def test_add_and_list_transaction(temp_db):
    result = db.add_transaction(
        amount=-42.50, category="Groceries", occurred_on="2026-09-01", merchant="Whole Foods",
        db_path=temp_db,
    )
    assert result.id > 0
    assert result.amount == -42.50

    txns = db.list_transactions(db_path=temp_db)
    assert len(txns) == 1
    assert txns[0]["category"] == "Groceries"
    assert txns[0]["merchant"] == "Whole Foods"


def test_add_transaction_creates_new_category(temp_db):
    db.add_transaction(amount=-10.0, category="Pet Supplies", occurred_on="2026-09-01", db_path=temp_db)
    txns = db.list_transactions(category="Pet Supplies", db_path=temp_db)
    assert len(txns) == 1


def test_add_transaction_rejects_bad_date(temp_db):
    with pytest.raises(ValueError):
        db.add_transaction(amount=-10.0, category="Groceries", occurred_on="09/01/2026", db_path=temp_db)


def test_spending_by_category_and_summary(temp_db):
    db.add_transaction(amount=2000.0, category="Salary", occurred_on="2026-09-01", db_path=temp_db)
    db.add_transaction(amount=-500.0, category="Rent", occurred_on="2026-09-02", db_path=temp_db)
    db.add_transaction(amount=-150.0, category="Groceries", occurred_on="2026-09-03", db_path=temp_db)
    db.add_transaction(amount=-50.0, category="Groceries", occurred_on="2026-09-10", db_path=temp_db)

    by_cat = db.spending_by_category(db_path=temp_db)
    groceries = next(r for r in by_cat if r["category"] == "Groceries")
    assert groceries["total"] == -200.0
    assert groceries["transaction_count"] == 2

    s = db.summary(db_path=temp_db)
    assert s["total_income"] == 2000.0
    assert s["total_expense"] == 700.0
    assert s["net"] == 1300.0
    assert s["top_expense_categories"][0]["category"] == "Rent"


def test_date_range_filtering(temp_db):
    db.add_transaction(amount=-10.0, category="Dining Out", occurred_on="2026-08-15", db_path=temp_db)
    db.add_transaction(amount=-20.0, category="Dining Out", occurred_on="2026-09-15", db_path=temp_db)

    september_only = db.list_transactions(start_date="2026-09-01", end_date="2026-09-30", db_path=temp_db)
    assert len(september_only) == 1
    assert september_only[0]["occurred_on"] == "2026-09-15"


def test_budget_status(temp_db):
    db.set_budget("Groceries", 300.0, db_path=temp_db)
    db.add_transaction(amount=-150.0, category="Groceries", occurred_on="2026-09-03", db_path=temp_db)
    db.add_transaction(amount=-100.0, category="Groceries", occurred_on="2026-09-20", db_path=temp_db)
    # transaction in a different month should not count
    db.add_transaction(amount=-999.0, category="Groceries", occurred_on="2026-08-01", db_path=temp_db)

    status = db.budget_status("2026-09", db_path=temp_db)
    groceries_status = next(r for r in status if r["category"] == "Groceries")
    assert groceries_status["spent"] == 250.0
    assert groceries_status["remaining"] == 50.0
    assert groceries_status["over_budget"] is False


def test_budget_status_over_budget(temp_db):
    db.set_budget("Dining Out", 50.0, db_path=temp_db)
    db.add_transaction(amount=-80.0, category="Dining Out", occurred_on="2026-09-05", db_path=temp_db)

    status = db.budget_status("2026-09", db_path=temp_db)
    dining = next(r for r in status if r["category"] == "Dining Out")
    assert dining["over_budget"] is True
    assert dining["remaining"] == -30.0


def test_update_transaction_changes_only_given_fields(temp_db):
    result = db.add_transaction(amount=-40.0, category="Groceries", occurred_on="2026-09-01", merchant="Store A", db_path=temp_db)

    updated = db.update_transaction(result.id, amount=-45.0, db_path=temp_db)
    assert updated.amount == -45.0
    assert updated.category == "Groceries"  # unchanged
    assert updated.merchant == "Store A"  # unchanged


def test_update_transaction_can_change_category(temp_db):
    result = db.add_transaction(amount=-20.0, category="Groceries", occurred_on="2026-09-01", db_path=temp_db)
    updated = db.update_transaction(result.id, category="Dining Out", db_path=temp_db)
    assert updated.category == "Dining Out"

    txns = db.list_transactions(category="Dining Out", db_path=temp_db)
    assert len(txns) == 1


def test_update_transaction_missing_id_raises(temp_db):
    with pytest.raises(ValueError):
        db.update_transaction(99999, amount=-1.0, db_path=temp_db)


def test_delete_transaction(temp_db):
    result = db.add_transaction(amount=-20.0, category="Groceries", occurred_on="2026-09-01", db_path=temp_db)
    assert db.delete_transaction(result.id, db_path=temp_db) is True
    assert db.list_transactions(db_path=temp_db) == []
    assert db.delete_transaction(result.id, db_path=temp_db) is False


def test_list_categories_includes_defaults(temp_db):
    categories = db.list_categories(db_path=temp_db)
    names = {c["name"] for c in categories}
    assert "Groceries" in names
    assert "Salary" in names
    kinds = {c["name"]: c["kind"] for c in categories}
    assert kinds["Salary"] == "income"
    assert kinds["Groceries"] == "expense"
