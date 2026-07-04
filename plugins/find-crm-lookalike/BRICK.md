# Brick contract: find-crm-lookalike

| Field | Value |
|---|---|
| id | `find-crm-lookalike` |
| family | find |
| target | companies (reads seed_customers) |
| method | agent (pattern analysis + similarity search), subagent fan-out |
| cost | free to cheap — search via Bright Data `search_engine` (1 credit/query) or built-in web search |
| kill-rule compatible | no |

## IN

- `seed_customers` rows — 3 to 10 recommended. If the table is empty, the
  brick collects seeds itself from ONE of: a CSV (columns name,domain) or a
  dictated list ("mes 5 meilleurs clients sont…"), and writes them to
  `seed_customers` first.
- CRM-agnostic by design: this brick NEVER talks to a CRM. Any future import
  brick (crm-best-customers-hubspot / -salesforce / -pipedrive…) feeds the
  same `seed_customers` table; this brick only reads it.
- Optional: `context/icp.md` to cross-check the deduced pattern.

## OUT

- `seed_customers`: filled/updated (source = dictated | csv | <crm>).
- `companies`: upsert on `domain` — `name`, `domain`,
  `source='lookalike:<seed-domain>'`. Schema defaults apply
  (`website_status='pending'`).

## Error handling

- No seeds and user has none to give → stop gracefully, suggest starting with
  find-directory-scrape instead.
- No search capability at all → stop with the Bright Data setup note.
- A seed with no findable website: keep it as seed (name only), skip site
  skim for it.

## Guardrails

- The deduced pattern is stated to the user for confirmation BEFORE searching.
- Max 5 lookalikes per seed, 50 candidates per run without explicit override.
- A candidate must have a real, live website — never invent domains.
- Never add a seed customer as a prospect (drop candidates whose domain is in
  seed_customers).
- Announce search credit usage when Bright Data is used.
