# Brick contract: enrich-person-profile

| Field | Value |
|---|---|
| family | enrich (contact level) |
| target | contacts |
| method | cost-ordered verified waterfall: FullEnrich people search (free) → LinkedIn SERP via Bright Data (indexed snippets) → team/press page; optional structured LinkedIn record (pro tools) |
| cost | free for most rows (rung A) · ~1-2 Bright Data credits per row reaching rungs B/C · per-record for the optional structured rung |

## IN

- `contacts` rows with `full_name`, `profile_status='pending'`, company
  not disqualified — nor kill-rule-flagged in `memory/` (flags count as
  out-of-scope until the score brick ships; flagged rows are never
  claimed).
- Rows with `left_company=1` are never in scope — the identity columns
  of a departed person stay frozen.
- A resolvable company per contact: `company_name` or `company_id`;
  `domain` (via enrich-firmographics) sharpens rung A matching.
- Existing `linkedin_url` upgrades rung A to an exact URL lookup.
- Optional: FullEnrich MCP (rung A), Bright Data MCP (rungs B/C, optional
  structured rung). Missing → those rungs are skipped and the receipt
  says so.

## OUT

- `role` (current title, verbatim from the source), `seniority`
  (FullEnrich vocabulary on rung A; conservative title-derived
  otherwise, empty over guessed), `linkedin_url`, `profile_source` =
  `fullenrich-search` | `linkedin-serp` | `team-page` | `linkedin-record`.
- `profile_status` → `done` | `not_found` | `failed`.
- Never overwrites a non-empty value with a weaker-rung one. Never
  creates contact rows — discovered people are receipt suggestions
  (adding people = enrich-buying-committee's job).

## Errors

- FullEnrich disconnected → rung A skipped (searches are free, so this
  is the only reason to skip it).
- Snippet/page ambiguity (name collision, stale role) → next rung, then
  `not_found`. Never an invented or unverified value.
- LinkedIn profile pages are behind the login wall — `scrape_as_markdown`
  on `/in/` URLs is never attempted (confirmed dead end).

## Guardrails

- Verification at every rung: name + role + company must cohere in the
  source itself; masked search names match on first name + last initial.
  Primacy over relays: a title observed at a DIFFERENT company than the
  row's is never written — mismatch reported, row closed `not_found`.
- Never log into LinkedIn (ToS + burned accounts) — indexed snippets and
  official records only.
- Paid budget announced ONCE up front (max ~2 credits per row that can
  reach rungs B/C), one explicit confirmation for the whole run (§8);
  subagents write to staging, `db.py` commits.
- Low-presence prior: no-domain artisan/tiny companies make rung B
  opt-in — default skip, registry title → seniority instead.
- French legal titles (gérant, président, PDG, DG, founder as registry
  executive) → `C-Level`, overriding provider labels.
- Idempotent re-runs via `profile_status`; `done` rows never reprocessed.
