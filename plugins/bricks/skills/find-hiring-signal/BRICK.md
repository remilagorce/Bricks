# Brick contract: find-hiring-signal

| Field | Value |
|---|---|
| family | find (companies, signal-driven) |
| target | writes companies + signals |
| method | user-confirmed pain matrix → `tools/jobs.py hunt` (deterministic: France Travail + HelloWork parsed, agencies flagged, prescore 65/100, companies grouped — free, seconds) → SERP escalation only for ATS/LinkedIn/Indeed lanes → judgment points + cut → commit via db-writer |
| cost | 0 credits on the script lanes; ~1 credit per query/page only on SERP escalation (caps 30/40); one upfront GO covers the run |

## IN

- `context/offer.md` + `context/icp.md` — REQUIRED (hard gate: the
  pain matrix derives from them; TODO placeholders → stop).
- Bright Data MCP preferred (SERP + scraping;
  `web_data_linkedin_job_listings` optional); the free web channel
  (built-in search + fetch) is the proven fallback engine when it is
  down. FullEnrich not used.
- `memory/state.json.hiring_matrix` when it exists (confirmed matrix,
  reused silently; re-asked only if context/ changed).

## OUT

- `companies` rows: `name`, `domain` (verified, never guessed),
  `source='hiring-signal'`, `status='new'`, `hiring_score` (0-100),
  `hiring_angle` (contextual-proof phrasing, never "j'ai vu que vous
  recrutez") — dedup on domain; pre-existing companies get the signal
  added, not a duplicate row.
- `signals` rows: `kind='hiring'`, `date` = freshest offer,
  `freshness` = `fresh` (≤ 60 days) | `context`, summary
  (roles + pains + offer volume), `evidence_url`, `sig_key` dedup.
- Staging: `offers.jsonl` (raw extracted offers) + `rejected.jsonl`
  (with reasons) under `staging/hiring-<date>/`.

## Errors

- Employer unidentifiable / recruitment agency without a named end
  client / stage-alternance / empty description → rejected.jsonl with
  reason, never committed.
- No date readable on the offer page → offer kept only as `context`,
  never `fresh`.
- Bright Data down → the 1-credit health control detects it and the
  free channel takes over; the brick refuses to run only when BOTH
  channels are unavailable.

## Guardrails

- Every query encodes one GTM hypothesis (title+tool+pain+geo+source);
  no date operators in queries (field-tested useless — freshness is
  read on the page).
- ONE GO per run: matrix + budget + score cut confirmed together; caps
  30 queries / 40 page reads without explicit override; the run never
  re-asks unless reality invalidates the plan.
- 1-credit channel health control first; staffing agencies excluded in
  the queries (negative keywords), not post-hoc; one db-writer
  dispatch per phase, never per row.
- Subagents write to staging only; `db-writer` commits.
- Company-level data only — no candidate/recruiter personal data
  (CNIL).
- Sourcing score ≠ ICP score: the score brick still runs on these rows.
