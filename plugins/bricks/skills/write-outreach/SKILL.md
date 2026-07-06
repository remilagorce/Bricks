---
name: write-outreach
description: Write multi-channel outreach drafts — email sequences AND LinkedIn invites/DMs — from the confirmed strategy, each contact's persona and the sender's voice. Use when the user says "écris les séquences", "rédige les messages", "prépare l'outreach", "écris les DM LinkedIn", "write outreach". CPPC copywriting, <100 words, one question per message; drafts only, never sends. Renamed and extended from write-sequence (0.9.0).
---

# Write outreach

Writes personalized multi-channel drafts into `messages`. The strategy
was decided upstream by plan-outreach (`context/strategy.md` +
`contacts.channel_plan`) — this skill EXECUTES it, per contact, in the
contact's assigned lane(s). It applies the context, it does not invent
positioning. Drafts forever: nothing leaves the machine without a
human. Contract in this directory's BRICK.md.

## Before anything — three gates

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3, then:

1. **`context/strategy.md` (HARD)** — absent → stop: "run
   plan-outreach first". The sequence templates, cadence and tier
   treatments live there; without them this brick would guess.
2. **`context/offer.md` (HARD, unchanged from write-sequence)** — TODO
   → stop and collect it; refuse to write generic spam. In a chain,
   the GO must have satisfied this gate at plan time — hard gates are
   never overridden.
3. **`context/voice.md` (SOFT)** — the SENDER's voice: tu/vous, direct
   or warm, forbidden words, signature. Missing → propose 3 sane
   defaults inside the single GO and write the file. Personas keep the
   RECIPIENT's angle; voice.md is how WE sound. **The signature is
   never inferred** (a machine username is not an identity —
   field-tested slip): if the GO's answer does not actually contain
   the name, re-ask THAT field alone; a guessed signature is never
   written into a draft.

## Work list

Run `db.py select` (§5): contacts with `channel_plan` set AND
`sequence_status` pending AND `status != 'disqualified'` AND no
`left_company` — plus the lane prerequisite: the `email` lane needs
`email_status='done'`; the `linkedin` lanes need a `linkedin_url`. A
`linkedin+email` contact missing one prerequisite runs the other lane,
and the receipt says why. **Email drafts before the address exists**:
the default is to WAIT for `email_status='done'` (drafts written for
addresses that never materialize go stale); drafting early is allowed
when the user opts in at the GO — drafts are text, sending stays
gated either way. Then read their companies (pitch, language)
and their `signals`: only `freshness='fresh'` rows (re-check `date`)
may be treated as news; `hiring_angle` is a ready-made opener;
`context` signals are background, never congratulated.

## The copy doctrine (distilled from the team's 2026 corpus)

- **CPPC**: Contexte (« pourquoi je VOUS contacte » — one line, one
  relevant signal) → Problème (posed as the segment's topic, never
  asserted: « c'est souvent un sujet chez… ») → Proposition (ONE
  outcome from the offer) → Call-to-conversation (ONE question — a
  conversation, not a sale).
- **Length**: email < 100 words. LinkedIn is a CHAT: DM 2-4 short
  lines. **Invitations carry NO note, ever** (house rule 0.9.2, from
  the corpus: add without a message, let the profile and content do
  the credibility work) — the `linkedin-invite` row is an ACTION item
  ("send the invite, no note, profile: <url>"), not copy.
- **Subjects**: plain, never slogans — « prise de contact »,
  « document », « je clôture ? ».
- **Personalization = one relevant signal connected to the problem**,
  never decorative trivia. Fresh signals and `hiring_angle` first;
  enriched columns second; nothing → the company pitch.
- **Tier treatment from strategy.md**: `hot-manual` accounts get the
  mini-audit opener (2 concrete observations about THEIR business);
  warm contacts (lead-magnet, prior interaction) get a feedback ask,
  not a pitch.
- **Forbidden**: talking about yourself, selling inside the message,
  stacked CTAs, over-personalization, placeholders left in, invented
  facts — if it is not in `context/` or an enriched column, it does
  not exist.

## Write — the sequence each channel_plan dictates

Templates come from `strategy.md`. Defaults: combined lane = invite J0
→ email J+2 → follow-up email J+5 → DM J+7 → breakup email J+10;
email-only = J0 / +3 / +7 (the historic sequence); linkedin-only =
invite J0 → DM J+2 → 2 relances (value, then soft close). Batches of
5 contacts, claim `running`; store as each batch completes — ONE
`db.py add` per batch of 5 (§9.4), never one write per contact and
never the whole run at the end: one `messages` row per step — `contact_id`, `channel` =
`email` | `linkedin-invite` | `linkedin-dm`, `step`, `send_day`,
`subject` (email only), `body`, `status='draft'`,
`msg_key='<contact_id>-<channel>-<step>'` (idempotent re-runs) — then
`sequence_status='done'`. Language: the company's, else the offer's.

## Close the run

Receipt: "X contacts → Y drafts (A email, B LinkedIn) ; Z lanes
skipped (missing prerequisite, named). Nothing sent — email drafts
await human approval (→ outreach-send when it ships); LinkedIn drafts
are yours to copy-paste, automated LinkedIn sending stays out by
doctrine." Show ONE full example sequence — one, not all. Statements,
never questions.
