---
name: find
description: Find companies and contacts matching an ICP and write them into the current Bricks workspace database. Use when the user wants to source leads, build a prospect list, "trouve des entreprises", "find companies", "build a list".
---

# Find

Sources entities (companies, contacts) matching the user's criteria and
writes them into the current workspace's database.

## Before anything: resolve the workspace and read the context

Follow the mandatory procedure in `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`:

1. `python3 "${CLAUDE_PLUGIN_ROOT}/tools/workspace.py" status`
2. Not initialized → run `init` automatically. No current workspace →
   create one named after the search (e.g. `new saas-france --goal "..."`)
   or ask. After `new`/`switch`, display the returned banner + welcome line
   (CONVENTIONS §2).
3. **Context gate** — read `context/offer.md` and `context/icp.md`. If the
   request contradicts them, apply the drift guardrail (CONVENTIONS §3):
   stop and ask (switch / new workspace / update context). If they are
   TODOs and the user has stated criteria, offer to write them in.
4. Read `memory/state.json` and `memory/NOTES.md` — a previous find run may
   be resumable.

## Workflow

1. **Clarify the target** — ICP, geography, size, signals; default to
   `context/icp.md` when the user is vague. Write the agreed criteria to
   `memory/NOTES.md` so later runs (and enrich) know the intent.
2. **Source** — in priority order:
   1. **FullEnrich search** when `mcp__fullenrich__*` tools are present
      and the target is a firmographic segment (industry, size,
      geography, titles): free preview (10 results + total count), then
      confirm the export volume per the money gate (§8). If FullEnrich is
      NOT connected, say so once ("run `/mcp` → fullenrich to unlock the
      B2B database") and fall back — never silently skip it.
   2. **Bright Data** (`search_engine`, or the find-directory-scrape
      skill for listing pages) when the target is niche/local commerce
      that B2B databases cover poorly.
   3. **Built-in web search** as the last resort — verify every domain.
   State in the receipt which source was used and why.
   For small runs (≲ 50 results, single session), collect and commit
   directly. For large or interruptible runs, append raw results to
   `staging/find-<YYYY-MM-DD>/raw-results.jsonl` batch by batch and keep
   source cursors in `memory/state.json` (see CONVENTIONS §6).
3. **Commit** — validate, then ask the `db-writer` agent to insert the
   rows, deduped on `domain` for companies / `email` for contacts (e.g.
   "insert these N company rows into `companies`, dedup on domain" with the
   validated rows attached). `db-writer` skips rows whose key already
   exists and reports how many.

   Standard columns — `companies`: `name, domain, source, status` ("new").
   `contacts`: `company_id` (the company's `_id`), `full_name, role, email,
   linkedin_url, source, status`. Add criteria-specific columns freely —
   `db-writer` creates them on the fly.
4. **Close the run** — update `memory/state.json` (sources covered,
   counts), append a summary line to `NOTES.md`, report a receipt to the
   user: how many found, how many duplicates skipped, how many rejected
   and why, which table. Max 3 sample rows in the chat — the data lives in
   the database.

Never write half-validated rows to the database — that is what `staging/`
is for. Never touch `bricks.db` yourself — always go through `db-writer`.
