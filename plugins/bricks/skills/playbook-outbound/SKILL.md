---
name: playbook-outbound
description: The full outbound motion as ONE deterministic run — complete the evidence (enrich), score, decide the strategy (plan-outreach), write the drafts (write-outreach) — with guards between phases and a single chain GO. Use when the user says "lance mon outbound", "déroule le pipeline complet", "fais tourner la machine", "playbook outbound". Dispatches installed bricks explicitly, in a fixed order; stops where approval is human.
---

# Playbook: full outbound motion

**Before anything, read `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md`.**

You are the orchestrator following a recipe: chain the bricks through
the database, phase by phase, dispatching EXPLICITLY by slash command —
this playbook names its steps, you do not re-decide the route. A missing
OPTIONAL brick is skipped and said; a missing REQUIRED artifact stops
the phase with the exact fix.

## Phase 0 — gates and the chain GO

Resolve the workspace (§2). `context/` TODO → dispatch
`/bricks:gtm-onboard` first (its interview IS the fix). Then present ONE
plan for the whole run: what each phase will do on THIS base (real
`matching` counts from `db.py select`), each phase's worst-case budget,
and the phase-0 facts `/bricks:plan-outreach` needs (deal size,
maturity, audience) — collected here so no downstream hard gate can
interrupt. §7 applies to the WHOLE chain: a free/near-free chain STARTS
announced-but-unasked; real credit spend → ONE chain GO. After that:
receipts flow, zero questions, and only an UNPLANNED cost or a strategy
contradiction (phase 4) may surface.

## Phase 1 — complete the evidence (cheap first)

Companies: `/bricks:enrich-firmographics` on pending rows (free official
API). Contacts: `/bricks:enrich-buying-committee` (ONE door per account —
default) or `/bricks:find-company-people` (full roster) when the user
asked for multi-threading; then `/bricks:enrich-person-profile` on thin
rows. Free rungs first; paid rungs live inside the GO's budget. Receipt
per brick.

## Phase 2 — score

Dispatch `/bricks:score`: kill gate (`disqualified` stops all downstream
spend) + tiers A/B/C. No scoring rules from the user and none derivable
from the ICP → say so and continue uniform — `/bricks:plan-outreach`
degrades gracefully.

## Phase 3 — signals (optional, free passes only)

`/bricks:signal-person` job-change + hiring on the survivors (script
lanes, 0 credit) — fresh icebreakers for the writing. Paid passes stay
out of this playbook unless the GO budgeted them.

## Phase 3b — rank

Dispatch `/bricks:rank-accounts`: fuse `tier` + the fresh signals into
`priority_score` / `priority_tier` (now/week/nurture) + a `why_now` per
account (deterministic, free, instant). This orders the call-list and
feeds the writing: `/bricks:plan-outreach` reads `priority_tier` for
per-priority treatment, `/bricks:write-outreach` reads `why_now` as the
opener. No signals yet → fit-only ranking (honest, no error).

## Phase 4 — strategy

Dispatch `/bricks:plan-outreach`. Its recommendation was pre-framed by
the chain GO's phase-0 facts: when the evidence CONFIRMS the frame, the
strategy is presented as a receipt and the chain continues; when the
evidence CONTRADICTS it (e.g. "you assumed email-only but 80 % of
contacts have LinkedIn"), this is the ONE legitimate mid-chain
checkpoint — a strategy reversal is a human decision, like approval.

## Phase 5 — write

Dispatch `/bricks:write-outreach`: drafts per `channel_plan`, all gates
already satisfied (strategy.md just written, offer.md checked at phase
0, voice.md defaults folded into the GO).

## Phase 6 — hand over (the human acts)

Final receipt for the whole run: rows at each stage (sourced → enriched
→ scored → planned → drafted), spend vs the GO's budget, and where the
human acts next — approve email drafts, copy-paste LinkedIn drafts
(automated LinkedIn sending is out by doctrine). The statuses written by
each brick are the checkpoints: this motion is long, and an interrupted
run resumes from them. Statements, never questions.
