# Brick contract: find-directory-scrape

| Field | Value |
|---|---|
| id | `find-directory-scrape` |
| family | find |
| target | companies |
| method | MCP (Bright Data `scrape_as_markdown` / `scrape_batch` / `search_engine`) + agent extraction |
| cost | cheap — 1 Bright Data credit per page request (free tier: 5,000 credits/month) |
| kill-rule compatible | no |

## IN

- A directory URL (exhibitor list, curated listicle, industry directory,
  ranking page) — or a description of one, resolved via `search_engine` and
  confirmed by the user.
- Requires: the `brightdata` MCP server in the workspace `.mcp.json`
  (hosted endpoint, needs a Bright Data API token).

## OUT

- `companies`: upsert on key `domain` — sets `name`, `domain`,
  `source='directory:<host>'`. New rows get schema defaults
  (`website_status='pending'`, `status='new'`).
- Entries with no external website: inserted with NULL domain after a
  name-level duplicate check, counted separately in the receipt.

## Error handling

- Bright Data MCP missing → give the 2-minute setup (API token) and offer the
  degraded WebFetch fallback (static pages only) — user chooses.
- Page empty or blocked after one retry → report the page, continue with the
  rest, list skipped pages in the receipt.
- Never invent or guess a domain. A directory entry whose website is unknown
  stays domain-less until another brick resolves it.

## Guardrails

- Announce the plan before scraping: detected entries per page, page count,
  credit estimate. Hard cap without explicit override: 10 pages / 200 entries.
- Beyond 3 pages, delegate page batches to subagents that write to the
  database themselves and return counts — scraped content never enters the
  main conversation.
- Optional second pass (resolving detail pages or missing domains via
  `scrape_batch` / `search_engine`) is opt-in: announce extra credits first.
