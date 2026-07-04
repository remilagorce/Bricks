# Brick contract: find-directory-scrape

| Field | Value |
|---|---|
| family | find |
| target | companies |
| method | MCP Bright Data (`scrape_as_markdown`, `scrape_batch`, `search_engine`) + agent extraction; subagents write to staging, `db-writer` commits |
| cost | cheap — ~1 Bright Data credit per page (free tier 5,000/month) |

## IN

- A directory URL (or a description resolved via `search_engine`, confirmed
  by the user).
- Requires the `brightdata` MCP connected (hosted endpoint in the plugin's
  `.mcp.json` + user token). Degraded fallback: WebFetch, static pages only.

## OUT

- `companies` rows: `name`, `domain` (dedup key), `source='directory:<host>'`,
  `status='new'`. Entries without an external site: inserted after a
  name-level duplicate check, domain left empty — never guessed.

## Errors

- Page empty or blocked after one retry → skip, list in the receipt.
- Bright Data absent and no fallback accepted → stop with setup note.

## Guardrails

- Money gate (CONVENTIONS §8): plan announced, 10 pages / 200 entries cap.
- Scraped content never enters the main conversation (subagents → staging).
- Re-runs are safe: domain dedup on commit, page cursors in memory/state.json.
