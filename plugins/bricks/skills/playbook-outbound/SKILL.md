---
name: playbook-outbound
description: The full outbound motion as ONE deterministic run — complete the evidence (enrich), score, decide the strategy (plan-outreach), write the drafts (write-outreach) — with guards between phases and a single chain GO. Use when the user says "lance mon outbound", "déroule le pipeline complet", "fais tourner la machine", "playbook outbound". Dispatches installed bricks explicitly, in a fixed order; stops where approval is human.
---

# Playbook: full outbound motion

You are the orchestrator following a recipe: chain the bricks through
the database, phase by phase, dispatching EXPLICITLY — this playbook
names its steps, you do not re-decide the route. Discover what is
installed at runtime: a missing OPTIONAL brick is skipped and said; a
missing REQUIRED artifact stops the phase with the exact fix.

## Phase 0 — gates and the chain GO

Resolve the workspace (§2). `context/` TODO → dispatch gtm-onboard
first (its interview IS the fix). Then present ONE plan for the whole
run: what each phase will do on THIS base (real counts from
`db.py count`), each phase's worst-case budget, and the phase-0 facts
plan-outreach needs (deal size, maturity, audience) — collected here
so no downstream hard gate can interrupt. §8 applies to the WHOLE
chain: total worst case below the big-spend threshold (default 50
credits) → the chain STARTS announced-but-unasked; above it → ONE
chain GO. After that: receipts flow, zero questions, and only an
UNPLANNED cost or a strategy contradiction (phase 4) may surface.

## Phase 1 — complete the evidence (cheap first)

Companies: enrich-firmographics on pending rows (free official API).
Contacts: enrich-buying-committee (ONE door per account — default) or
find-company-people (full roster) when the user asked for
multi-threading; then enrich-person-profile on thin rows. Free rungs
first; paid rungs live inside the GO's budget. Receipt per brick.

## Phase 2 — score (if installed)

Dispatch the score brick: kill gate (`disqualified` stops all
downstream spend) + tiers A/B/C. Not installed or `scoring.yaml`
missing → say so and continue uniform — plan-outreach degrades
gracefully.

## Phase 3 — signals (optional, free passes only)

signal-person job-change + hiring on the survivors (script lanes,
0 credit) — fresh icebreakers for the writing. Paid passes stay out
of this playbook unless the GO budgeted them.

## Phase 4 — strategy

Dispatch plan-outreach. Its recommendation was pre-framed by the
chain GO's phase-0 facts: when the evidence CONFIRMS the frame, the
strategy is presented as a receipt and the chain continues; when the
evidence CONTRADICTS it (e.g. "you assumed email-only but 80 % of
contacts have LinkedIn"), this is the ONE legitimate mid-chain
checkpoint — a strategy reversal is a human decision, like approval.

## Phase 5 — write

Dispatch write-outreach: drafts per `channel_plan`, all gates already
satisfied (strategy.md just written, offer.md checked at phase 0,
voice.md defaults folded into the GO).

## Phase 6 — hand over (the human acts)

Final receipt for the whole run: rows at each stage (sourced →
enriched → scored → planned → drafted), spend vs the GO's budget, and
where the human acts next — approve email drafts (→ outreach-send
when it ships), copy-paste LinkedIn drafts (automated LinkedIn
sending is out by doctrine). Update `memory/state.json` + NOTES.md at
EVERY phase: this motion is long, it must survive interruption and
resume where it stopped. Statements, never questions.
