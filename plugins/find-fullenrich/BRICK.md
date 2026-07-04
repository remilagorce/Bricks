# Brick contract: find-fullenrich

| Field | Value |
|---|---|
| id | `find-fullenrich` |
| family | find |
| target | companies + people |
| method | MCP (FullEnrich search) |
| cost | free preview (10 results + total count), then 0.25 credit per exported contact |
| kill-rule compatible | no |

## IN

- Search criteria: from the user's request, completed with `context/icp.md`
  (industry, size, geography, title patterns).
- Requires: the `fullenrich` MCP server connected (workspace `.mcp.json`,
  OAuth in browser on first use).

## OUT

- `companies`: upsert on key `domain` — sets `name`, `domain`, `source='fullenrich'`.
  New rows get the schema defaults (`website_status='pending'`, `status='new'`).
- `people`: insert — sets `first_name`, `last_name`, `title`, `linkedin_url`,
  `company_id`, `source='fullenrich'`. Defaults: `email_status='pending'`,
  `sequence_status='pending'`.

## Error handling

- MCP not connected → tell the user to run `/mcp` and authenticate, stop.
- Search returns 0 → report, suggest loosening one filter, stop.

## Guardrails

- ALWAYS preview first (free), announce the total count, and get explicit user
  confirmation before any export that consumes credits.
- Hard cap without explicit override: 100 contacts per run.
