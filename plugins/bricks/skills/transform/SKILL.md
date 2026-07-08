---
name: transform
description: Transform tables in the current workspace database — clean, deduplicate, filter, derive columns, split or merge tables, zero external fetch. Use when the user says "transform", "nettoie", "déduplique", "filtre", "reformate ma table". For scoring against natural-language rules, see /bricks:score.
---

# Transform — reshape existing tables

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** — the shared
contract every skill obeys (workspace, context gate, the only door, the iron
gate). Zero external fetch: a transform only reads and writes `bricks.db`.

## Gates (before anything)

1. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status` — a current
   workspace with an existing table is required (otherwise run `/bricks:find`
   first).
2. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" schema <table>` + a
   `select --limit 5` for the shape, and state what you see. Read
   `context/icp.md` when the transform encodes intent (kill rules, segments).
3. Confirm with the user if the transformation is destructive (deleting rows,
   overwriting a column).

## Workflow

All writes through `db.py` (§4) — never any other path:

- **Derived/cleaned columns** → compute the values in the session (small
  tables) or via a `--step` function through `runner.py` (large tables,
  iron gate §5 applies), then ONE `db.py modify --updates '[...]'` wave —
  never one call per row. Unknown columns are created automatically.
- **Disqualifying rows (kill rules)** → prefer `modify` setting
  `status=disqualified` over deleting — downstream skills filter them out
  with `--where` and the data stays auditable.
- **Dropping rows for real** → `db.py select <table> --where ... --cols _id
  --limit -1` first, show the user the `matching` count, then `db.py remove
  <table> --ids '[...]'` with the collected ids.
- **New table (split, merge, aggregate)** → `select` from the sources, then
  `add` into the new table (`--key` for dedup); keep the sources intact.
- **Deduplication** → re-import through the dedup key when possible
  (`select` → CSV → `import-csv --key domain` into a fresh table), or
  collect duplicate `_id`s and `remove` them after user review.

Prefer new columns over destroyed data — e.g. write `domain_normalized`
next to `domain` rather than overwriting, unless the user explicitly wants
in-place cleanup.

## Receipt

Report before/after counts ("deduplicated companies on domain: 50 → 43
rows") — receipts, never raw table dumps in the conversation.
