# Brick contract: playbook-outbound

| Field | Value |
|---|---|
| family | playbook (explicit dispatch — the deterministic orchestrator for the outbound motion) |
| target | dispatches bricks; owns no data of its own — everything flows through the base |
| method | fixed phase order: gates+chain GO → enrich (firmo → committee/roster → profiles) → score → free signals → plan-outreach → write-outreach → human hand-over; runtime discovery of installed bricks |
| cost | the sum of its phases, announced ONCE at the chain GO; free-lane bricks preferred throughout |

## IN

- A workspace with context/ filled (TODO → dispatches gtm-onboard
  first) and at least companies rows (else the user is routed to a
  find brick before this playbook makes sense).
- The chain GO: per-phase counts + worst-case budgets + the three
  strategy facts (deal size, maturity, audience), confirmed once.

## OUT

- The pipeline's artifacts, each written by its own brick: enriched
  columns, `disqualified`/`tier`, fresh `signals`,
  `context/strategy.md` + `channel_plan`, `messages` drafts.
- `memory/state.json` phase log (resumable) + NOTES.md lines.

## Errors

- Required artifact missing mid-chain → the phase stops with the
  exact fix (never improvises around a hard gate).
- Optional brick not installed (score, signal-person) → skipped and
  stated; downstream bricks degrade as their own contracts define.

## Guardrails

- Explicit dispatch only — the playbook never re-decides the route,
  never lets auto-delegation pick a different brick mid-run.
- ONE chain GO (§8); the only legitimate mid-chain stop is a strategy
  CONTRADICTION at phase 4 (a reversal is a human decision) or an
  unplanned cost.
- Kill gate respected from phase 2 on: nothing is ever spent on
  `disqualified` rows.
- Ends where approval begins: drafts are handed to the human; no
  send, ever, from this playbook.
