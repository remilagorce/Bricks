# Find

Sources companies and contacts matching your ICP and writes them to the
workspace database.

- FullEnrich (OAuth via `/mcp`) for firmographic segments: preview 10,
  confirm the volume, export CSV, import with a dedup key.
- Bright Data / web search for niche or local targets.
- Every write goes through `db.py` — dynamic columns, duplicate skipping,
  JSON receipts.

Say: *"trouve 20 agences web à Nantes"*.
