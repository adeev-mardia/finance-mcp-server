# finance-mcp-server

An [MCP](https://modelcontextprotocol.io) server that gives any MCP client (Claude Desktop, Claude Code, etc.) real tools to manage your actual personal finances against a local SQLite ledger — no cloud account, no external service, no subscription, just a database file that lives on your machine. You can genuinely use this day-to-day: log expenses by talking to your MCP client, import your real bank statement, fix a typo'd entry, and ask questions like "am I over budget on dining out this month?".

## Why

Most MCP server examples wrap a SaaS API as a toy demo. This one wraps a real, useful domain model instead: transactions, categories, and monthly budgets, with proper validation, aggregation queries, editable/deletable entries, and real-bank-statement CSV import — the kind of thing you'd actually want to run against your own money, not just a canned example.

## Tools exposed

| Tool | Description |
|---|---|
| `add_transaction` | Record income (positive amount) or an expense (negative amount) against a category |
| `list_transactions` | List transactions, filterable by date range and category |
| `update_transaction` | Fix a mistake — edit the amount, category, date, merchant, or note on an existing entry |
| `delete_transaction` | Remove a transaction |
| `spending_by_category` | Aggregate totals grouped by category over a date range |
| `get_summary` | Total income, total expense, net, and top 5 expense categories for a period |
| `set_budget` | Set or update a monthly spending limit for a category |
| `get_budget_status` | Spend-vs-limit status for every budgeted category in a given month |
| `list_categories` | See every category currently in use |
| `import_transactions_csv` | Bulk-import a real bank/card statement export (handles varying column layouts) |
| `export_transactions_csv` | Export your ledger to CSV for backup or a spreadsheet |

Categories are created on the fly the first time you reference them — no separate setup step.

## Getting your real data in

You don't have to type every transaction by hand. Most banks let you download your statement as a CSV — export one and ask your MCP client to import it, e.g.:

> "Import the CSV at ~/Downloads/chase_september.csv — the date column is 'Transaction Date', amount is 'Amount', description is 'Description'"

Bank export formats vary a lot (some use one signed amount column, others split spending and deposits into separate "Debit"/"Credit" columns; date formats differ), so `import_transactions_csv` takes explicit column names rather than guessing — tell it what your bank's columns are called and it maps them. Malformed rows (a trailing "pending transactions" summary line, for example) are skipped and reported rather than aborting the whole import. If your bank shows expenses as positive numbers, pass `flip_sign: true`.

From there, everyday use is conversational: "add a $12 lunch at Chipotle today", "how much have I spent on groceries this month", "set my dining out budget to $150/month", "I mis-entered that coffee as $40, fix it to $4".

## Install

```bash
git clone https://github.com/adeev-mardia/finance-mcp-server.git
cd finance-mcp-server
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Run it

As a standalone process (stdio transport):

```bash
finance-mcp-server
# or
python -m finance_mcp.server
```

### Connect it to Claude Desktop / Claude Code

Add to your MCP client config (e.g. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "finance": {
      "command": "finance-mcp-server",
      "env": {
        "FINANCE_MCP_DB": "/absolute/path/to/finance.db"
      }
    }
  }
}
```

`FINANCE_MCP_DB` is optional — it defaults to `data/finance.db` relative to the package if unset.

### Get started

Point `FINANCE_MCP_DB` at wherever you want your real ledger to live (it's created automatically on first use) and start talking to it through your MCP client — add transactions as they happen, or import a bank CSV export to backfill history in one go (see "Getting your real data in" below).

If you just want to poke around the tools before committing real data, `python scripts/seed_demo_data.py` seeds a separate database with ~3 months of fake sample transactions and budgets — useful for a first look, not meant to be your real ledger.

## Architecture

```
src/finance_mcp/
├── db.py       # SQLite schema + query layer (stdlib sqlite3 only, no ORM)
├── csv_io.py   # Bank statement CSV import + ledger CSV export
└── server.py   # FastMCP tool definitions — thin wrappers around db.py / csv_io.py
```

The persistence layer (`db.py`) has no dependency on the `mcp` package, so it's independently testable and reusable outside an MCP context (e.g. a CLI or web UI could sit on top of it too).

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

26 tests cover the query layer (`test_db.py`), CSV import/export against real-shaped bank export data — signed-amount and debit/credit column layouts, US date formats, malformed rows, sign-flipped exports (`test_csv_io.py`) — and the MCP tool functions as they'll actually be invoked by a client (`test_server_tools.py`), including edge cases like invalid dates, new-category creation, date-range filtering, editing/deleting a transaction, and over-budget detection.

## Design notes

- **Signed amounts, not separate income/expense tables.** A transaction's sign determines its kind; categories still carry a `kind` for aggregation, so "how much did I earn" and "how much did I spend" are simple `WHERE` clauses, not joins across tables.
- **Categories are get-or-create.** An MCP client (or the person prompting it) shouldn't need to pre-register categories before recording a transaction — friction there defeats the point of a conversational interface.
- **No ORM.** For a schema this small, stdlib `sqlite3` keeps the whole persistence layer in one readable file and avoids a dependency that would otherwise dominate `pip install -e .`.

## License

MIT
