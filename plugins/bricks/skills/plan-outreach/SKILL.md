---
name: plan-outreach
description: Decide the outreach strategy from evidence — motion, channel mix (LinkedIn / email / both), cadence, volumes, per-tier treatment. Use when the user says "définis la stratégie", "on attaque par où ?", "LinkedIn ou email ?", "stratégie de prospection", "plan outreach". Runs AFTER enrichment and scoring; writes context/strategy.md (user-confirmed, persisted) + contacts.channel_plan. It never writes a message — write-outreach executes.
---

# Plan outreach

The strategy brick. It turns the workspace's EVIDENCE into one
confirmed outreach strategy — it sits LATE in the pipeline, after
find/enrich/score have filled the table, because a strategy without
evidence is vibes. It decides; write-outreach executes; the
orchestrator (the session, or playbook-outbound) sequences. It never
writes a message and never talks to another brick — its output is
artifacts on the bus. Contract in this directory's BRICK.md.

## Before anything

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3. HARD gate:
`context/offer.md` + `icp.md` + `personas/` filled (TODO → run
gtm-onboard first). Then read the EVIDENCE from the base via
`db.py select`/`count` (§5, receipts only, never dumps): company sizes and sectors
(firmo), `tier` distribution (score run? absent → the strategy is
uniform-degraded and SAYS SO, recommending score first), fresh
signals (hiring, news, job changes), and contact coverage — % with a
`linkedin_url`, % with a verified email, seniority mix. These numbers
ARE the strategy's raw material.

## Phase 0 — the facts data cannot tell (folded into the single GO)

Three questions asked ONCE, inside the plan presentation:
1. Deal size / pricing (high-ticket flips the doctrine to hot/manual).
2. Maturity: pre-PMF validation, first-100-clients, or scaling?
3. Existing audience/content (warm paths available?).

## The decision doctrine (distilled from the team's 2026 GTM corpus)

| Situation (evidence + answers) | Motion |
|---|---|
| pre-PMF | LinkedIn validation — learn, don't close |
| first 100 clients, reachable SMB | founder outbound — ONE channel, deep |
| high-ticket / agency / enterprise | hot outreach / ABM top-down: few accounts, manual research per account, warm intros first |
| decision-makers demonstrably on LinkedIn (high `linkedin_url` coverage) | LinkedIn authority + invite for familiarity, email to convert |
| market needs education | content + lead magnet + warm email (warm ≈ 21 % reply vs cold ≈ 15 %) |
| audience/traffic already exists | media system + warm email + scoring |
| PLG / self-serve product | bottom-up on product signals |
| physical product / distribution | omnichannel incl. phone and salons |

Channel rules: **LinkedIn + email is the B2B default**; **email-only**
when the target is easy to list and LinkedIn coverage is poor (the
artisan ICPs — the evidence decides, not the fashion); LinkedIn-only
for pure credibility plays; one channel deep when starting. Cadence:
steady volume at cruise (~200-250 contacts/week), multichannel
sequence (invite → email → follow-ups → DM → breakup). Per-tier
treatment: **A** = hot/manual with a mini-audit per account, **B** =
standard sequence, **C** = light touch or none. Forbidden:
spray-and-pray, inbound-only waiting, talking to off-ICP accounts
because they are easy.

## The GO — one block, one confirmation

Present ≤ 12 lines: the evidence summary (coverage numbers, tiers,
fresh signals) → recommended motion + channel mix + cadence +
per-tier treatment → what it means concretely ("14 contacts: 9
linkedin+email, 5 email-only; the 3 tier-A get the manual
treatment") → the phase-0 questions still open. ONE GO. Persisted;
re-proposed only when context/ or the evidence shifts materially (new
tiers, a big signal wave, a channel's coverage doubling).

## Writes

- **`context/strategy.md`** — the strategy document, human-readable:
  motion, channel mix, cadence and volumes, per-tier treatment, the
  sequence template per lane (steps + send_days write-outreach will
  follow), the evidence that justified each choice, and the date.
- **`contacts.channel_plan`** = `email` | `linkedin` |
  `linkedin+email` | `hot-manual` — assigned per row from evidence
  (verified email? linkedin_url? tier?) via `db.py modify`, batched.
  Contacts of DISQUALIFIED companies and `left_company` rows get NO
  channel_plan — excluded at assignment time, not caught downstream
  (field-tested: a disqualified GE's contact got a plan and
  write-outreach had to intercept it).
- `memory/state.json` (`outreach_strategy` summary) + one NOTES.md
  line.

Receipt: the channel_plan distribution + the strategy in 5 lines +
the next step as a statement ("Next: write-outreach — dis le mot").
Never a question, never a message written, never a send.
