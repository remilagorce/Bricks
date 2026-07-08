---
name: enrich
description: Enrich rows of an existing table in the current Bricks workspace database with new data columns (employees, funding, tech stack, emails…). Use when the user says "enrich", "enrichis", "complète les données", "add data to my list".
---

# Enrich — fill columns on existing rows

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** — the
shared contract every skill obeys (workspace §2, context gate §3, the
only door §4, the iron gate §5, the two enrichment modes in §6).

The Clay-like column-by-column enrichment. An enrichment column `X`
always comes with its `X_status` column (`pending | running | done |
not_found | failed`) — that is what makes runs resumable, idempotent and
parallelizable. Never iterate rows in the conversation, never fetch
pages per row in the session.

## Gates (before anything)

1. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/workspace.py" status` — a
   current workspace with an existing table is required; if none, tell
   the user to run `/bricks:find` first (or ask which data to import)
   instead of inventing rows.
2. Read `context/icp.md` and `context/offer.md`; on contradiction apply
   the drift guardrail (§3). Kill rules mapping to enriched columns →
   flag matching rows in the receipt, never disqualify silently.
3. `db.py schema <table>` + `db.py count` (§4) for the table's schema
   and pending count before committing to a plan.
4. **The right lane for the column** — two kinds of enrichment, two
   lanes, ONE mode per run (§6, never a third path):
   - **Contact/firmographic provider data** (emails, phones, employees,
     funding…) → **Lane A**, the `fullenrich` MCP server (waterfall over
     20+ providers). Check the FullEnrich MCP tools are available; if
     not, the user is not signed in: STOP and tell them to run `/mcp`,
     pick `fullenrich`, sign in in the browser, then retry. Never
     fabricate enrichment values as a fallback, and never scrape around
     this gate. (French official firmographics have their own free lane:
     `/bricks:enrich-firmographics`.)
   - **Web-content data computed per row** (what the site says: pitch,
     positioning, offering, language, hiring page…) → **Lane B**, the
     engine: `runner.py` → `agent.py`.

## Lane A — provider data through MCP, in waves

FullEnrich consumes credits (~0.25/contact): announce the estimated cost
BEFORE launching a bulk job (money gate §7) and use the free searches to
validate targeting.

1. **Initialize and claim** via `db.py` (§4): `modify --set
   X_status=pending --where …` on rows in scope (first run only,
   excluding disqualified), then ONE `db.py claim <table> X_status
   --limit 25 --cols _id,domain` — pending rows are atomically marked
   `running` before you work them.
2. **Enrich in waves, write per wave** — never one row at a time:
   - **Batch tools first**: N contacts to enrich → ONE FullEnrich
     `enrich_bulk` job (async — store the job id in `memory/state.json`
     (§8) so an interrupted run fetches results later instead of paying
     twice). Beyond ~20 rows, fetch results via
     `export_enrichment_results` → CSV URL → `staging/` → `db.py
     import-csv` (§6) — never `get_enrichment_results` pagination. N
     pages to read → ONE Bright Data `scrape_batch` call (~1
     credit/page), not N `scrape_as_markdown` calls.
   - **No batch variant** → fire the whole wave's calls IN PARALLEL in
     one message (all the fetches, then all the fallbacks on misses).
   - Rows that fail on a 403/blocked fetch: retry ONCE through Bright
     Data automatically before marking them `failed` — do not ask
     permission to retry, that is what the tool is for.
   - As each wave completes, ONE `db.py modify --updates` writes its
     values and final statuses. `not_found` is a result, not an error —
     write the status, leave the value empty; `failed` means retryable;
     NEVER fabricate.
   - Above ~40 rows needing session MCP calls: subagent batches of 5-8
     rows, up to 10 launched IN PARALLEL in one message, findings
     appended to `staging/` as they land — the main thread does every
     `db.py` write itself; subagents never touch the database.

## Lane B — computed per row: the engine

1. **Compile the pipeline** — one prompt template using `{{column}}`
   placeholders + one JSON schema whose properties are exactly the
   columns to write. Frame with the user: table, scope (`--where`),
   target columns, web or not, model (`haiku` by default, §7).
2. **PREVIEW (mandatory, non-skippable)**:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/tools/core/runner.py" run --table companies \
     --status-col hq_status --run-id hq-<date> \
     --ai '{"prompt":"…{{name}} ({{domain}})…","schema":{"type":"object","properties":{"hq_city":{"type":"string"}}},"web":true,"model":"haiku"}' \
     --preview 10
   ```
   The 10 pilot rows are computed, WRITTEN (tagged with the run-id) and
   streamed as NDJSON on **stderr** — relay each `preview_row` to the
   user as it arrives and have them check the rows in
   `/bricks:interface`; stdout is the final receipt only. Long missions:
   compile the params to `prompts/<slug>/params.json` in the workspace
   and pass `--ai @<abs path>/params.json`. `"max_pages":N` caps
   browsing per row.
3. **GO** — one explicit user confirmation.
4. **Commit** — the exact same command with `--preview 10` → `--commit`
   (preview rows are settled, never re-paid; no `--limit` = the whole
   scope, tranche by tranche).

## Close the run

A re-run picks up `pending` rows automatically (`--retry-failed` /
`db.py claim --retry-failed` is the explicit retry pass); no cursor
needed. Update `memory/state.json` (quotas, job ids) and `NOTES.md`,
then the receipt: "employees: 43 done, 5 not_found, 2 failed (re-run to
retry)." — engine runs end with the rollback line (`runner.py rollback
--manifest <run>.manifest.json`). Max 3 sample rows.
