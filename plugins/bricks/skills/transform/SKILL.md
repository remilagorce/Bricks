---
name: transform
description: Transform tables in the current Bricks workspace database — clean, deduplicate, filter, derive columns, score, split or merge tables. Use when the user says "transform", "nettoie", "déduplique", "score", "filtre", "reformate ma table".
---

# Transform

Reshapes existing workspace tables: cleaning, deduplication, filtering,
derived columns (scores, segments, normalized values), splits and merges.

## Before anything: resolve the workspace and read the context

Follow the mandatory procedure in `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`:

1. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" status`
2. This skill requires existing tables — if there are none, say so and
   point to find.
3. Read `context/icp.md` and `memory/NOTES.md` for the workspace's intent —
   most transforms (scoring, filtering, kill rules) depend on them. Apply
   the drift guardrail (CONVENTIONS §3) if the request contradicts the
   context.

## Workflow

1. **Read before writing** — run `db.py schema` / `db.py select` (§5) for
   the table's schema and a handful of sample rows, and state what you see.
   Confirm the transformation with the user if it is destructive (deleting
   rows, overwriting a column).

2. **Apply through `db.py`** (CONVENTIONS §5) — never any other write path:
   - Derived/cleaned columns → `db.py modify --updates` by `_id` (unknown
     columns are created automatically), or `db.py modify --set … --where`
     for uniform assignments.
   - Disqualifying rows (kill rules) → prefer `db.py modify --set
     status=disqualified --where <kill condition>` over deleting —
     downstream skills skip them and the data stays auditable.
   - Dropping rows for real → `db.py count --where …` first, show the user,
     then `db.py remove --ids`/`--where`.
   - New table (split, merge, aggregate) → `db.py select` from the sources,
     then `db.py add` into a new table; keep the source tables intact.

3. **Prefer new columns over destroyed data** — e.g. write
   `domain_normalized` next to `domain` rather than overwriting, unless
   the user explicitly wants in-place cleanup.

4. **Close the run** — update `memory/state.json` and append to `NOTES.md`
   what was transformed and why (e.g. "deduplicated companies on domain:
   50 → 43 rows"). Report the before/after counts to the user — receipts,
   not dumps.
