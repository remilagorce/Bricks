---
name: enrich
description: Enrich rows of an existing table in the current Bricks workspace database with new data columns (employees, funding, tech stack, emails…). Use when the user says "enrich", "enrichis", "complète les données", "add data to my list".
---

# Enrich

Adds or fills columns on existing rows of a workspace table — the Clay-like
column-by-column enrichment. An enrichment column `X` always comes with its
`X_status` column (`pending | running | done | not_found | failed`) — that
is what makes runs resumable, idempotent and parallelizable.

## Before anything: three mandatory gates

**Gate 1 — the right source for the column.** Two kinds of enrichment,
two sources:

- **Contact/firmographic data** (emails, phones, employees, funding…) →
  the `fullenrich` MCP server (waterfall over 20+ providers). Check that
  `mcp__fullenrich__*` tools are available; if not, the user is not signed
  in: STOP and tell them to run `/mcp`, pick `fullenrich`, sign in in the
  browser, then retry. Never fabricate enrichment values as a fallback,
  and never scrape around this gate.
- **Web-content data** (what the site says: pitch, positioning, offering,
  language, hiring page…) → read the sites. PREFER Bright Data
  `scrape_as_markdown` when `mcp__brightdata__*` is available — JS
  rendering and anti-bot handled, ~1 credit/page (money gate §8 at
  volume). Plain WebFetch is the fallback for simple pages only. Rows
  that fail on a 403/blocked fetch: retry ONCE through Bright Data
  automatically before marking them `failed` — do not ask permission to
  retry, that is what the tool is for.

**Gate 2 — workspace.** Follow the mandatory procedure in
`${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2. This skill needs existing
tables; if `status` shows none, tell the user to run find first (or ask
which data to import) instead of inventing rows.

**Gate 3 — context.** Read `context/offer.md` and `context/icp.md`. If the
request contradicts them, apply the drift guardrail (CONVENTIONS §3). If
`icp.md` has kill rules that map to columns being enriched, flag matching
rows in the receipt (do not disqualify silently — confirm with the user).

## Workflow

1. **Scope** — confirm with the user: which table, which rows (all or a
   filter), which column(s), from which source. Run `db.py schema` and
   `db.py count` (CONVENTIONS §5) for the table's schema and pending count
   before committing to a plan.

   FullEnrich consumes credits (~0.25/contact): announce the estimated
   cost before launching a bulk job and use the free previews to validate
   targeting.

2. **Initialize the status column** (first run only) — run `db.py modify
   --set X_status=pending --where …` (§5) on rows in scope that don't have
   it yet (excluding disqualified rows).

3. **Select and claim** — ONE command: `db.py claim <table> X_status
   --limit 25 --cols _id,domain` (§5) atomically selects the pending
   rows AND marks them `running` before you start working them.

4. **Enrich in waves, write per wave (§9)** — never one row at a time:
   - **Batch tools first**: N contacts to enrich → ONE FullEnrich
     `enrich_bulk` job (async — store the job id in `memory/state.json`
     so an interrupted run fetches results later instead of paying
     twice, §8.5). N pages to read → ONE Bright Data `scrape_batch`
     call, not N `scrape_as_markdown` calls.
   - **No batch variant** → fire the whole wave's calls IN PARALLEL in
     one message (all the fetches, then all the fallbacks on misses).
   - As each wave completes, ONE `db.py modify --updates` writes its
     values and final statuses (`done` / `not_found` / `failed`).

   `not_found` is a result, not an error — write it as the status and
   leave the value empty. `failed` means retryable. Never fabricate.
   Above ~40 rows, switch to subagent batches per §9.5: 5-8 rows each,
   up to 10 launched IN PARALLEL (in one message), findings appended to
   `staging/` — the main thread does every `db.py` write itself (§5),
   passing the absolute `bricks.db` path; subagents never touch the
   database.

5. **Close the run** — a re-run picks up `pending` (and `failed` on
   request) rows automatically; no cursor needed. Update
   `memory/state.json` (quotas, job ids) and `NOTES.md`, then report the
   receipt: "employees: 43 done, 5 not_found, 2 failed (re-run to retry)."
