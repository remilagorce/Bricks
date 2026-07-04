# Brick contract: find-lookalike

| Field | Value |
|---|---|
| family | find |
| target | companies (reads seeds, writes candidates) |
| method | agent (pattern analysis + similarity search); subagents → staging, `db-writer` commits |
| cost | free to cheap — `search_engine` ~1 credit/query, or built-in web search |

## IN

- Seeds: `companies WHERE segment='seed'` (3-10 recommended) — fed by CRM
  export, CSV or dictated list; collected by this skill if absent.
- The seeds' enriched columns, whatever exists — more columns = sharper
  pattern (see playbook-lookalike for the enrich-seeds-first motion).
- Optional: `context/icp.md`.

## OUT

- `companies` candidate rows: `name`, `domain` (dedup key),
  `source='lookalike:<seed-domain>'`, default `segment` (prospect).
- Seed rows are never modified (dedup-on-insert skips existing keys).

## Errors

- No seeds and none provided → stop, suggest find-directory-scrape.
- No search capability → stop with Bright Data setup note.

## Guardrails

- Pattern confirmed by the user BEFORE any search.
- Max 5 candidates/seed, 50/run without explicit override; money gate §8.
- Live website required; no invented domains; seed domains dropped from
  candidates (customers never become prospects).
