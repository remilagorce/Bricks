---
name: find-directory-scrape
description: Source companies from an online directory, exhibitor list, curated listicle or ranking page — "scrape les exposants de ce salon", "récupère les boutiques de cet article". Uses Bright Data for robust scraping (JS rendering + anti-bot handled) and writes company rows into the current workspace database.
---

# Find via directory scraping (Bright Data)

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`** (§2
workspace, §3 context gate).

Turns any listing page into company rows. Scraping robustness is delegated
to Bright Data — never hand-roll fetching when its tools are available.

**Bright Data gate** — check whether `mcp__brightdata__*` tools are present:

- Present → proceed.
- Absent → the plugin ships the hosted server (`.mcp.json`), it only needs
  the user's token: free account at brightdata.com (5,000 requests/month,
  no credit card), then set `BRIGHTDATA_API_TOKEN` (in `~/.bricks/env`),
  restart the session. If the user cannot do it now, offer the degraded
  fallback — built-in WebFetch, static pages only — their call.

## Workflow

1. **Input** — a directory URL. If the user only describes it ("les
   exposants de Maison&Objet"), locate it with `search_engine` and confirm
   the URL before scraping.
2. **Scout** — `scrape_as_markdown` on page 1. Identify: the repeating
   entry pattern (name + link), whether links go to external company sites
   or internal detail pages, and the pagination.
3. **Announce the plan** (§7): entries per page, page count, ~1 credit per
   page. Hard cap 10 pages / 200 entries per run without an explicit
   override.
4. **Extract and commit** — sourcing goes through a CSV (§6):
   - Land the extracted entries in
     `bricks/tmp/find-directory-<date>/companies.csv` (header `name,domain,
     source,...`), then ONE `db.py import-csv companies <file> --key domain`,
     `source='directory:<host>'`. Entries with no external site: insert
     only if no row with the same name exists; NEVER invent a domain.
   - > 3 pages: delegate page batches to subagents (general-purpose). Each
     subagent scrapes its pages and appends raw entries to
     `bricks/tmp/find-directory-<date>/raw-results.jsonl` — subagents never
     touch the database. Back in the main thread: validate the raw file
     (dedup, live domains, rejects to `rejected.jsonl` with reasons), build
     the CSV, commit once.
5. **Optional second pass** — propose, never force: internal detail pages
   holding the websites → `scrape_batch` them in batches of 10 (announce
   the extra credits); or resolve still-domain-less entries via
   `search_engine` per name.
6. **Receipt** — X companies added (Y with domain, Z without), W duplicates
   skipped, P pages (~P credits), skipped pages if any. Max 3 sample rows.
   Next step as a statement: "Next: `/bricks:enrich` — dis le mot."
