# Brick contract: enrich-website

| Field | Value |
|---|---|
| id | `enrich-website` |
| family | enrich (company level) |
| target | companies |
| method | agent (web reading), delegated to subagents in batches |
| cost | free |
| kill-rule compatible | yes (cheap column, safe to run early) |

## IN

- `companies.domain` — required.
- Precondition: `website_status = 'pending'` AND `status != 'disqualified'`.
- Optional user scope: a WHERE filter or a row limit.

## OUT

- `companies.pitch` — one sentence: what the company does, for whom.
- `companies.language` — main website language, ISO code (fr, en, …).
- `companies.size_hint` — solo | small | mid | large (heuristic).
- `companies.website_status` → `done` | `not_found` (no site / unreachable) | `failed`.

## Error handling

- No domain on the row → `not_found`, never guess a domain.
- Unreachable site after one retry → `failed` (eligible for re-run).

## Guardrails

- Batches of 5 per subagent; subagents write to the database themselves and
  return counts only. No page content in the main conversation, ever.
