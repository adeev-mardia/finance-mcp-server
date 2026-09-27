# finance-mcp-server

An [MCP](https://modelcontextprotocol.io) server that gives any MCP client (Claude Desktop, Claude Code, etc.) tools to manage a personal finance ledger backed by local SQLite — no cloud account, no external service, just a single database file.

## Why

Most MCP server examples wrap a SaaS API. This one wraps a real, useful domain model instead: transactions, categories, and monthly budgets, with proper validation, aggregation queries, and budget-vs-actual tracking — the kind of thing you'd actually want an assistant to reason over.

## Tools exposed

| Tool | Description |
|---|---|
| `add_transaction` | Record income (positive amount) or an expense (negative amount) against a category |
| `list_transactions` | List transactions, filterable by date range and category |
| `spending_by_category` | Aggregate totals grouped by category over a date range |
| `get_summary` | Total income, total expense, net, and top 5 expense categories for a period |
| `set_budget` | Set or update a monthly spending limit for a category |
| `get_budget_status` | Spend-vs-limit status for every budgeted category in a given month |

Categories are created on the fly the first time you reference them — no separate setup step.

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

### Try it with demo data

```bash
python scripts/seed_demo_data.py   # seeds ~3 months of realistic transactions + budgets
```

Then ask your MCP client things like "what did I spend on groceries last month?" or "am I over budget on dining out this month?".

## Architecture

```
src/finance_mcp/
├── db.py       # SQLite schema + query layer (stdlib sqlite3 only, no ORM)
└── server.py   # FastMCP tool definitions — thin wrappers around db.py
```

The persistence layer (`db.py`) has no dependency on the `mcp` package, so it's independently testable and reusable outside an MCP context (e.g. a CLI or web UI could sit on top of it too).

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

11 tests cover the query layer directly (`test_db.py`) and the MCP tool functions as they'll actually be invoked by a client (`test_server_tools.py`), including edge cases like invalid dates, new-category creation, date-range filtering, and over-budget detection.

## Design notes

- **Signed amounts, not separate income/expense tables.** A transaction's sign determines its kind; categories still carry a `kind` for aggregation, so "how much did I earn" and "how much did I spend" are simple `WHERE` clauses, not joins across tables.
- **Categories are get-or-create.** An MCP client (or the person prompting it) shouldn't need to pre-register categories before recording a transaction — friction there defeats the point of a conversational interface.
- **No ORM.** For a schema this small, stdlib `sqlite3` keeps the whole persistence layer in one readable file and avoids a dependency that would otherwise dominate `pip install -e .`.

## License

MIT
