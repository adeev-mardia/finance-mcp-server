import csv
import os
import tempfile

import pytest

from finance_mcp import csv_io, db


@pytest.fixture()
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)
    db.init_db(db_path=path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def _write_csv(tmp_path, name, rows, fieldnames):
    path = os.path.join(tmp_path, name)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_import_csv_single_signed_amount_column(temp_db, tmp_path):
    path = _write_csv(
        str(tmp_path),
        "export.csv",
        [
            {"Date": "2026-09-01", "Amount": "-42.50", "Description": "Whole Foods"},
            {"Date": "2026-09-02", "Amount": "2000.00", "Description": "Employer Inc"},
        ],
        ["Date", "Amount", "Description"],
    )
    result = csv_io.import_csv(path, db_path=temp_db)
    assert result["imported"] == 2
    assert result["skipped"] == 0

    txns = db.list_transactions(db_path=temp_db)
    assert len(txns) == 2
    amounts = {t["amount"] for t in txns}
    assert amounts == {-42.5, 2000.0}


def test_import_csv_handles_us_date_format(temp_db, tmp_path):
    path = _write_csv(
        str(tmp_path), "export.csv", [{"Date": "09/15/2026", "Amount": "-10.00", "Description": "Coffee"}], ["Date", "Amount", "Description"]
    )
    result = csv_io.import_csv(path, db_path=temp_db)
    assert result["imported"] == 1
    txns = db.list_transactions(db_path=temp_db)
    assert txns[0]["occurred_on"] == "2026-09-15"


def test_import_csv_debit_credit_columns(temp_db, tmp_path):
    path = _write_csv(
        str(tmp_path),
        "export.csv",
        [
            {"Date": "2026-09-01", "Debit": "40.00", "Credit": "", "Description": "Gas Station"},
            {"Date": "2026-09-02", "Debit": "", "Credit": "1500.00", "Description": "Paycheck"},
        ],
        ["Date", "Debit", "Credit", "Description"],
    )
    result = csv_io.import_csv(path, amount_column=None, debit_column="Debit", credit_column="Credit", db_path=temp_db)
    assert result["imported"] == 2
    txns = db.list_transactions(db_path=temp_db)
    amounts = {t["amount"] for t in txns}
    assert amounts == {-40.0, 1500.0}


def test_import_csv_flip_sign(temp_db, tmp_path):
    # some exports show expenses as positive numbers
    path = _write_csv(str(tmp_path), "export.csv", [{"Date": "2026-09-01", "Amount": "25.00", "Description": "Store"}], ["Date", "Amount", "Description"])
    result = csv_io.import_csv(path, flip_sign=True, db_path=temp_db)
    assert result["imported"] == 1
    txns = db.list_transactions(db_path=temp_db)
    assert txns[0]["amount"] == -25.0


def test_import_csv_skips_malformed_rows_without_aborting(temp_db, tmp_path):
    path = _write_csv(
        str(tmp_path),
        "export.csv",
        [
            {"Date": "2026-09-01", "Amount": "-10.00", "Description": "Good row"},
            {"Date": "not-a-date", "Amount": "-5.00", "Description": "Bad row"},
        ],
        ["Date", "Amount", "Description"],
    )
    result = csv_io.import_csv(path, db_path=temp_db)
    assert result["imported"] == 1
    assert result["skipped"] == 1
    assert len(result["errors"]) == 1


def test_import_csv_requires_amount_or_debit_credit(temp_db, tmp_path):
    path = _write_csv(str(tmp_path), "export.csv", [{"Date": "2026-09-01", "Description": "x"}], ["Date", "Description"])
    with pytest.raises(ValueError):
        csv_io.import_csv(path, amount_column=None, db_path=temp_db)


def test_export_csv_round_trip(temp_db, tmp_path):
    db.add_transaction(amount=-42.5, category="Groceries", occurred_on="2026-09-01", merchant="Whole Foods", db_path=temp_db)
    db.add_transaction(amount=2000.0, category="Salary", occurred_on="2026-09-02", db_path=temp_db)

    out_path = os.path.join(str(tmp_path), "out.csv")
    result = csv_io.export_csv(out_path, db_path=temp_db)
    assert result["rows_written"] == 2
    assert os.path.exists(out_path)

    with open(out_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert {r["category"] for r in rows} == {"Groceries", "Salary"}
