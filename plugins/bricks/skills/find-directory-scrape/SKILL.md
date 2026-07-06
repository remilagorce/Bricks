---
name: find-directory-scrape
description: Source companies from an online directory, exhibitor list, curated listicle or ranking page — "scrape les exposants de ce salon", "récupère les boutiques de cet article". Uses Bright Data for robust scraping (JS rendering + anti-bot handled) and writes company rows into the current Bricks workspace database.
---

# Find via directory scraping (Bright Data)

Turns any listing page into company rows. Scraping robustness is delegated
to Bright Data — never hand-roll fetching when its tools are available.
Contract in this directory's BRICK.md.

## Before anything: resolve the workspace and read the context

Follow the mandatory procedure in `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`
(§2 workspace resolution, §3 context gate and drift guardrail).

**Bright Data gate** — check whether `mcp__brightdata__*` tools are present:

- Present → proceed.
- Absent → the plugin ships the hosted server (`.mcp.json`), it only needs
  the user's token: free account at brightdata.com (5,000 requests/month,
  no credit card), then set `BRIGHTDATA_API_TOKEN` or paste the token in
  the server URL, restart the session. If the user cannot do it now, offer
  the degraded fallback — built-in WebFetch, static pages only — their call.

## Workflow

1. **Input** — a directory URL. If the user only describes it ("les
   exposants de Maison&Objet"), locate it with `search_engine` and confirm
   the URL before scraping.
2. **Scout** — `scrape_as_markdown` on page 1. Identify: the repeating
   entry pattern (name + link), whether links go to external company sites
   or internal detail pages, and the pagination.
3. **Announce the plan** (money gate, CONVENTIONS §8): entries per page,
   page count, ~1 credit per page. Hard cap 10 pages / 200 entries per run
   without an explicit override.
4. **Extract and commit**:
   - ≤ 3 pages: extract as you go and insert the rows with `db.py add
     companies --key domain` (§5), source `directory:<host>`. Entries with
     no external site: insert only if no row with the same name exists;
     NEVER invent a domain.
   - > 3 pages: delegate page batches to subagents (general-purpose). Each
     subagent scrapes its pages and appends raw entries to
     `staging/find-directory-scrape-<date>/raw-results.jsonl`
     (CONVENTIONS §6) — subagents never touch the database. Back in the
     main thread: validate the staging file (dedup, live domains, rejects
     to `rejected.jsonl` with reasons), then commit via `db.py` in one
     batch. Page cursors go to `memory/state.json` so an interrupted run
     resumes where it stopped.
5. **Optional second pass** — propose, never force: internal detail pages
   holding the websites → `scrape_batch` them in batches of 10 (announce
   the extra credits); or resolve still-domain-less entries via
   `search_engine` per name.
6. **Close the run** — update `memory/state.json` (URL, pages covered),
   append a summary line to `NOTES.md`, report the receipt: X companies
   added (Y with domain, Z without), W duplicates skipped, P pages
   (~P credits), skipped pages if any. Max 3 sample rows.
