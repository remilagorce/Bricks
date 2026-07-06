# Brick contract: find-company-people

| Field | Value |
|---|---|
| family | find (bridge: companies → contacts, roster-wide) |
| target | reads companies, writes MULTIPLE contacts per company |
| method | title pattern (user or ICP Buying roles) → cost-ordered waterfall WITHOUT stop-at-first-hit: FullEnrich people search (free, `max_per_company`) → LinkedIn SERP (capped) → team page; per-company cap, default 4 |
| cost | free for most rows (rung A) · ~1-2 Bright Data credits per company that needs rungs B/C · one upfront worst-case budget, single GO |

## IN

- `companies` rows with `people_status='pending'`, `status !=
  'disqualified'`, not kill-rule-flagged in `memory/` (never claimed);
  `tier` A/B default scope when the score brick has run.
- A title pattern: from the user's request, else `context/icp.md`
  (Buying roles) + `personas/`.
- Optional: FullEnrich MCP (rung A — the free engine), Bright Data
  MCP (rungs B/C). Either missing → those rungs skipped and said so.

## OUT

- MULTIPLE `contacts` rows per company: `company_id` +
  `company_name` (denormalized), `full_name`, `role` (verbatim),
  `linkedin_url` when sourced, `source` = `fullenrich-search` |
  `linkedin-serp` | `team-page`, `status='new'`;
  `profile_status='pending'` initialized on thin rows (bus relay to
  enrich-person-profile).
- `companies.people_status` → `done | not_found | failed`.
- Dedup on (company_id + full_name), email secondary; existing
  contacts (e.g. the committee's pick) never duplicated, their
  `role_type` never touched.

## Errors

- Masked names ("Hakim A.") are NEVER inserted — resolved via B/C or
  receipt-mentioned only.
- Ambiguous person (name collision, stale role) → that person is
  skipped, the company sweep continues.
- Nothing verifiable at any rung → `people_status='not_found'`,
  zero invention.

## Guardrails

- ONE GO per run: pattern + cap + scope + worst-case budget in a
  single confirmation (§8); free-only resolution never re-asks. Chain
  GO supported: follow-on bricks named by the user are budgeted in the
  same plan, zero mid-chain confirmations.
- Receipts end with statements, never questions; a user-named absent
  company is added (`source='user'`, flagged) and swept, never asked
  about; workspace outage notes gate rungs B/C to the free channel.
- Rung A-bis: registry executives via `tools/firmo.py` (free, full
  first names — resolves initial-only site mentions).
- Verification at every rung: name + role + company cohere in the
  source itself; LinkedIn = indexed snippets only, never logged in.
- Per-company cap (default 4): closest-to-pattern kept, runners-up
  named in the receipt.
- Boundary with enrich-buying-committee is explicit: committee picks
  THE contact (one, by doctrine, `role_type` set); this brick lists
  ALL matching contacts (no `role_type`).
- Batched db.py writes (5-8 companies), staging at volume;
  idempotent re-runs via `people_status`.
