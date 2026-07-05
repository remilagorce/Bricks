# Brick contract: enrich-buying-committee

| Field | Value |
|---|---|
| family | enrich (bridge: companies → contacts) |
| target | reads companies, writes contacts |
| method | targeting plan (user-confirmed) + cost-ordered waterfall: registry relay → FullEnrich search → LinkedIn SERP (Bright Data) → team page |
| cost | free for most rows (rungs A/B) · ~1-2 Bright Data credits per row that reaches rungs C/D |

## IN

- `companies` rows with `committee_status='pending'`, ideally already
  through enrich-firmographics: `employees`, `executives`,
  `parent_company`, `company_category` (column relay — run it first).
- `context/offer.md` + `context/icp.md` (Buying roles) + `personas/` —
  the raw material of the targeting plan.
- Optional: FullEnrich MCP (free searches) and Bright Data MCP (rungs
  C/D). Missing → the waterfall skips those rungs and says so.

## OUT

- `contacts` rows: `company_id`, `full_name`, `role` (actual title),
  `role_type` = `decision-maker` | `champion` (ONE per company, chosen
  by the plan — never both), `linkedin_url` when available, `source` =
  `registry` | `fullenrich-search` | `linkedin-serp` | `team-page`.
- `companies.committee_status` → `done` | `not_found` | `failed`.
- `memory/state.json.targeting_plan` — the confirmed doctrine, reused on
  re-runs.

## Errors

- Corporate officer as sole executive (holding) → registry rung skipped,
  group noted, human hunted via B-D.
- Nothing verifiable after all rungs → plan's fallback rule, else
  `not_found`. Never an invented or unverified person.

## Guardrails

- The targeting plan is presented and confirmed BEFORE any hunting;
  champion vs decision-maker per size bucket comes from ICP + offer, not
  improvisation.
- Verification at every rung: name + role + company must cohere in the
  source itself (LinkedIn = indexed snippets only, never logged-in).
- One contact per company; dedup on (company_id + full_name).
- SERP credits announced at volume (money gate §8); subagents write to
  staging, `db-writer` commits.
