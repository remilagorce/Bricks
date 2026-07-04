# Brick contract: find-crm-lookalike

| Field | Value |
|---|---|
| id | `find-crm-lookalike` |
| family | find |
| target | companies (reads seeds, writes candidates) |
| method | agent (pattern analysis + similarity search), subagent fan-out |
| cost | free to cheap — search via Bright Data `search_engine` (1 credit/query) or built-in web search |
| kill-rule compatible | no |

## IN

- Seed rows: `companies WHERE segment='seed'` — the won customers, 3 to 10
  recommended. Seeds live in the SAME companies table so that every
  enrichment brick (present and future) can enrich them with a simple WHERE.
- If no seeds exist, the brick collects them itself from ONE of: a CSV
  (columns name,domain) or a dictated list ("mes 5 meilleurs clients
  sont…"), and writes them with `segment='seed'`, `source=csv|dictated`.
  CRM imports are NOT this brick's job: crm-import-* bricks (hubspot,
  salesforce, pipedrive, notion…) will write the same seed rows later.
- The richer the seed rows (pitch, hiring, tech…), the better the pattern —
  run enrichment bricks on `segment='seed'` first (see playbook-lookalike).
- Optional: `context/icp.md` to cross-check the deduced pattern.

## OUT

- `companies`: candidate rows upserted on `domain` — `name`, `domain`,
  `segment='prospect'` (default), `source='lookalike:<seed-domain>'`.
- Seed rows are never modified except their own upsert at collection time.

## Error handling

- No seeds and user has none to give → stop gracefully, suggest
  find-directory-scrape instead.
- No search capability at all → stop with the Bright Data setup note.
- A seed with no findable website: keep it (name only), skip its site skim.

## Guardrails

- The deduced pattern is stated to the user for confirmation BEFORE searching.
- Max 5 lookalikes per seed, 50 candidates per run without explicit override.
- A candidate must have a real, live website — never invent domains.
- Before upserting a candidate, check its domain is not a seed
  (`segment='seed'`) — customers never become prospects, and an upsert must
  never overwrite a seed row.
- Announce search credit usage when Bright Data is used.
