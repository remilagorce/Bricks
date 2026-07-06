# Brick contract: plan-outreach

| Field | Value |
|---|---|
| family | plan (strategy — reads everything, writes context + one column) |
| target | reads context/ + companies + contacts + signals; writes context/strategy.md + contacts.channel_plan |
| method | evidence summary (firmo, tiers, signals, channel coverage) + 3 user facts → decision doctrine (2026 GTM corpus distilled) → ONE confirmed strategy, persisted |
| cost | free (reads receipts, writes artifacts — no external calls) |

## IN

- HARD gate: `context/offer.md`, `icp.md`, `personas/` filled.
- Evidence via db.py: company firmo columns, `tier` distribution
  (score absent → uniform-degraded strategy, stated), `signals`
  freshness, contact coverage (% linkedin_url, % verified emails,
  seniority mix).
- Three phase-0 facts folded into the single GO: deal size, maturity
  (pre-PMF / first-100 / scaling), existing audience.

## OUT

- `context/strategy.md`: motion, channel mix, cadence/volumes,
  per-tier treatment (A hot-manual · B standard · C light/none),
  sequence templates per lane (steps + send_days), evidence and date.
  User-confirmed once, persisted; re-proposed only on material
  context/evidence change.
- `contacts.channel_plan` = `email` | `linkedin` | `linkedin+email` |
  `hot-manual` (per-row, evidence-based, via db.py, batched).
- `memory/state.json.outreach_strategy` + NOTES.md line.

## Errors

- Context TODO → stop, route to gtm-onboard (hard gate).
- No tier column → strategy still produced, uniform, flagged
  ("run score for per-tier treatment").
- Zero contacts → strategy produced for the sourcing phase, channel
  assignment deferred (nothing to assign).

## Guardrails

- Runs AFTER enrichment/score — evidence first, doctrine second,
  never vibes.
- ONE GO (plan + 3 facts + assignment counts in one block); receipts
  are statements, never questions.
- Never writes messages, never sends, never calls another brick —
  artifacts on the bus only (star model).
- channel_plan never assigned to disqualified or `left_company` rows.
