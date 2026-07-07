---
name: enrich
description: Fill columns on existing rows of the current workspace database, with per-row web research through the runner pipeline. Use when the user says "enrich", "enrichis", "complète les données", "add data to my list".
---

# Enrich — fill columns on existing rows

ONE execution path only: `runner.py` → `agent.py`. Never iterate rows in the
conversation, never fetch pages per row in the session.

## Gates (before anything)

1. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status` — a current
   workspace with an existing table is required (otherwise run `find` first).
2. Read `context/icp.md` and `context/offer.md`;
   `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/db.py" schema <table>` for what exists.
3. Frame with the user: which table, which scope (`--where`), which target
   columns, web research or not, model (`haiku` by default to spare the
   subscription).

## Workflow

1. **Compile the pipeline** — one inline prompt template using `{{column}}`
   placeholders + one JSON schema whose properties are exactly the columns to
   write.
2. **PREVIEW (mandatory, non-skippable)** — run WITHOUT `--commit`:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" --table companies \
     --ai '{"prompt":"...{{name}} ({{domain}})...","schema":{"type":"object","properties":{"hq_city":{"type":"string"}}},"web":true,"model":"haiku"}' \
     --status-col hq_status
   ```
   Show the 10 results to the user. NOTHING is written.
3. **GO** — one explicit user confirmation.
4. **Commit** — the exact same command + `--commit` (no `--limit` = the whole
   table).
5. **Receipt** — e.g. "hq_city: 41 done, 2 failed — re-running the same
   command resumes the pending rows". An empty/not-found value is a result,
   not an error.
