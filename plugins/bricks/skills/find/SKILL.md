---
name: find
description: Find companies and contacts matching an ICP and write them into the current Bricks workspace database. Use when the user wants to source leads, build a prospect list, "trouve des entreprises", "find companies", "build a list".
---

# Find — source companies & contacts

Read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` first — §2 (workspace), §3
(context gate), §6 (sourcing lands as CSV), §7 (cost gate). The steps below
are the find-specific application.

## Gates

1. Workspace per §2. If `icp.md` is still TODO and the request has no
   targeting criteria → `/bricks:gtm-onboard` before sourcing. If the request
   HAS criteria but `icp.md` is empty, offer to write them in.
2. A previous find run may be resumable — check `memory/state.json` and
   `memory/NOTES.md` (§8) before starting over.

## Workflow

1. **Target** — make the criteria explicit (industry, geography, size,
   signals); default to what `context/icp.md` says. Companies by default;
   people only if explicitly asked. Write the agreed criteria to
   `memory/NOTES.md` so later runs (and `/bricks:enrich`) know the intent.

2. **Source** — in priority order; state in the receipt which source was
   used and why:
   1. **FullEnrich MCP** (`mcp__fullenrich__*` tools) when the target is a
      firmographic segment (industry, size, geography, titles).
      `search_companies` gives a free preview (10 results + total count):
      **render that preview to the user as a readable table** with the MCP's
      information, **and restate the interpreted query in plain language**
      («PME françaises 50-250 salariés, secteur logiciel…»). Confirm the
      preview AND the export volume (§7) before going further. Then
      `export_companies` → download the CSV → `staging/` →
      `db.py import-csv companies <file.csv> --key domain`. Volume flows by
      FILE, never through MCP replies (§6). If the MCP tools are missing,
      say it once («run `/mcp` → fullenrich to unlock the B2B database») and
      fall back — never silently skip it.
   2. **Bright Data** (`search_engine`, or `/bricks:find-directory-scrape`
      for listing pages) when the target is niche/local commerce that B2B
      databases cover poorly.
   3. **Built-in web search** as the last resort — verify every domain.

   Small runs (≲50 results, single session): collect and commit directly.
   Large or interruptible runs: append raw batches to
   `staging/find-<YYYY-MM-DD>/raw-results.jsonl` and keep source cursors in
   `memory/state.json` (§8) — never write half-validated rows to the
   database, that is what `staging/` is for.

3. **Write** — validate, then import deduped:
   `db.py import-csv companies <file.csv> --key domain` (contacts: `--key
   email`). Standard columns — companies: `name, domain, source, status`
   ("new") ; contacts: `company_id` (the company's `_id`), `full_name, role,
   email, linkedin_url, source, status`. Criteria-specific columns are
   welcome — `db.py` creates them on the fly. Never fabricated data, never
   mass `--rows` JSON.

4. **Close** — update `memory/state.json` (sources covered, counts), append
   a summary line to `NOTES.md`, then the receipt: how many found, how many
   duplicates skipped, how many rejected and why, which table. Max 3 sample
   rows — the mass lives in the database (§1).
