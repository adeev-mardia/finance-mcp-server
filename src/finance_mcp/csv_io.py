"""Import real bank/card statement exports into the ledger, and export the
ledger back out to CSV.

Bank CSV exports are inconsistent enough (different column names, some use
one signed "Amount" column, others split "Debit"/"Credit" into two columns,
date formats vary) that a single hardcoded schema won't work. `import_csv`
takes an explicit column mapping instead of guessing, so it works with
whatever your bank actually gives you -- point it at the export, tell it
which column is which, and it categorizes and inserts every row.
"""

from __future__ import annotations

import csv
from datetime import datetime
from typing import Optional

from finance_mcp import db


def _parse_amount(value: str) -> float:
    cleaned = value.replace(",", "").replace("$", "").strip()
    if not cleaned:
        return 0.0
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    return float(cleaned)


def _parse_date(value: str, date_format: Optional[str]) -> str:
    value = value.strip()
    formats = [date_format] if date_format else ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%d-%m-%Y"]
    for fmt in formats:
        if not fmt:
            continue
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(
        f"could not parse date {value!r} with format {date_format!r}; pass an explicit date_format "
        "(e.g. '%m/%d/%Y') matching your bank export"
    )


def import_csv(
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
    db_path: Optional[str] = None,
) -> dict:
    """Import a bank/card CSV export into the ledger.

    Supports two common export shapes:
      - one signed "Amount" column (set `amount_column`); or
      - separate "Debit"/"Credit" columns (set `debit_column`/`credit_column`,
        leave `amount_column=None`).

    Some banks export expenses as positive numbers (you spent $40 shows as
    "40.00", not "-40.00"); set `flip_sign=True` if imported expenses come in
    with the wrong sign in your first test run -- there is no reliable way to
    detect this automatically across different banks.

    Rows that fail to parse (bad date/amount) are skipped and counted rather
    than aborting the whole import, since a single malformed row (e.g. a
    trailing "Pending" summary line some exports append) is common and
    shouldn't lose the rest of a real statement.

    Returns {"imported": int, "skipped": int, "errors": [str, ...]}.
    """
    if amount_column and (debit_column or credit_column):
        raise ValueError("pass either amount_column or debit_column/credit_column, not both")
    if not amount_column and not (debit_column or credit_column):
        raise ValueError("must specify amount_column, or debit_column and/or credit_column")

    imported = 0
    skipped = 0
    errors: list[str] = []

    with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):  # header is line 1
            try:
                occurred_on = _parse_date(row[date_column], date_format)

                if amount_column:
                    amount = _parse_amount(row[amount_column])
                else:
                    debit = _parse_amount(row[debit_column]) if debit_column and row.get(debit_column) else 0.0
                    credit = _parse_amount(row[credit_column]) if credit_column and row.get(credit_column) else 0.0
                    # debit columns are conventionally the spend side; store as negative
                    amount = credit - abs(debit)

                if flip_sign:
                    amount = -amount

                category = row[category_column].strip() if category_column and row.get(category_column) else default_category
                if not category:
                    category = default_category

                merchant = row[description_column].strip() if description_column and row.get(description_column) else None

                db.add_transaction(
                    amount=amount,
                    category=category,
                    occurred_on=occurred_on,
                    merchant=merchant,
                    note="imported from CSV",
                    db_path=db_path,
                )
                imported += 1
            except (KeyError, ValueError) as exc:
                skipped += 1
                errors.append(f"line {line_num}: {exc}")

    return {"imported": imported, "skipped": skipped, "errors": errors}


def export_csv(
    file_path: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict:
    """Export transactions to a CSV file, e.g. for backup or opening in a spreadsheet."""
    rows = db.list_transactions(
        start_date=start_date, end_date=end_date, category=category, limit=1_000_000, db_path=db_path
    )
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "occurred_on", "amount", "category", "merchant", "note"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return {"file_path": file_path, "rows_written": len(rows)}
