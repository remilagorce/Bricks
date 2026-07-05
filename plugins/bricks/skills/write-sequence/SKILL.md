---
name: write-sequence
description: Write the outbound email sequence (3 emails, day 0 / +3 / +7) for contacts that have a verified email — personalized from context/offer.md, personas and enriched company columns. Drafts only, never sends. "Rédige les séquences", "écris les emails de relance".
---

# Write the 3-email sequence

Writes a personalized 3-step sequence per contact into the `messages`
table, as drafts. The strategy was decided in `context/` — this skill
applies it, it does not invent positioning. Contract in this directory's
BRICK.md.

## Before anything: resolve the workspace and read the context

Follow `${CLAUDE_PLUGIN_ROOT}/CONVENTIONS.md` §2 and §3 — and enforce the
context gate STRICTLY here: if `context/offer.md` is missing or still a
TODO placeholder, STOP and offer to fill it first. Refuse to write generic
spam — garbage in, garbage out. Read `context/personas/*.md`; pick each
contact's persona from their `role`.

## Workflow

1. **Work list** — ask `db-writer`: "select contacts where
   email_status='done' AND sequence_status is pending (create the column on
   first use) AND status != 'disqualified' AND left_company is not set,
   limit 20" (a departed contact must never receive a sequence about
   their old company — signal-person freezes those rows), then "select the
   companies rows for these company_ids" (pitch, language, and any enriched
   columns worth an angle: hiring, news…).
2. **Claim** — batches of 5 contacts; `db-writer`: "set
   sequence_status='running' for these ids".
3. **Write, per contact** — three emails:
   - step 1 (send_day 0): icebreaker anchored in THEIR reality — company
     pitch, an enriched column, or a `signals` row. Signals rule: only
     `freshness='fresh'` signals (≤ 60 days — re-check `date` at write
     time) may be treated as news ("congrats on…", "saw you're
     hiring…"); `context` signals are background, never congratulated.
     ONE outcome from the offer; one clear, low-friction ask.
     ≤ 120 words.
   - step 2 (send_day 3): follow-up with a proof point from `offer.md`
     (number, client story) — a new angle, never "just bumping this".
     ≤ 120 words.
   - step 3 (send_day 7): breakup — short, human, door open. ≤ 60 words.
   Language: the company's `language` column, else the offer's language.
   Persona: best match from `context/personas/` on the contact's role —
   follow its angle and style. No placeholder brackets may remain. No
   invented facts: if it is not in `context/` or an enriched column, it
   does not exist.
4. **Store immediately** — after EACH contact, `db-writer`: "insert 3 rows
   into `messages` — contact_id, step (1|2|3), send_day (0|3|7), subject,
   body, status='draft', dedup on msg_key='<contact_id>-<step>'" — then
   "set sequence_status='done' for this contact". The msg_key dedup makes
   re-runs skip already-written sequences.
5. **Close the run** — receipt: "Sequences written for X contacts (3 drafts
   each), Y skipped as already written. Nothing is sent — drafts await
   human approval (CONVENTIONS §5)." Show ONE full example sequence so the
   user can judge tone — one, not all.
