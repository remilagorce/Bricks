# Brick contract: enrich-email

| Field | Value |
|---|---|
| id | `enrich-email` |
| family | enrich (person level) |
| target | people |
| method | MCP (FullEnrich enrichment) |
| cost | PAID — credits debited per enriched contact |
| kill-rule compatible | no (expensive column — run it late, after scoring/kill) |

## IN

- `people.first_name`, `people.last_name` — required.
- `companies.domain` (via `people.company_id`) or `people.linkedin_url` — at
  least one required.
- Precondition: `email_status = 'pending'` AND `people.status != 'disqualified'`
  AND parent company `status != 'disqualified'`.
- Requires: the `fullenrich` MCP server connected.

## OUT

- `people.email` — verified professional email when found.
- `people.email_status` → `done` | `not_found` | `failed`.

## Error handling

- Missing name or domain/linkedin → `not_found` (do not guess, do not spend).
- MCP error on a contact → `failed` (eligible for re-run), continue the batch.

## Guardrails

- PAID brick: announce the exact volume and get explicit confirmation before
  enriching. Hard cap without explicit override: 50 contacts per run.
- Enrich in batches of 10; write each result immediately.
