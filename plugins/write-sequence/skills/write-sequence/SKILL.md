---
name: write-sequence
description: Use when the user wants to write the outbound email sequence (3 emails, day 0 / +3 / +7) for contacts that have a verified email. Personalizes from context/offer.md, personas, and the company pitch. Drafts only — never sends anything.
---

# Write the 3-email sequence

Write a personalized 3-step sequence per contact and store it as drafts in the
`messages` table. You are a brick and a copywriter: the strategy was decided in
`context/` — you apply it, you do not invent positioning. Contract in BRICK.md.

## Steps

1. Read `context/offer.md`. If missing or still TODO, STOP and ask the user to
   fill it — refuse to write generic spam. Read `context/personas/*.md` and
   `context/icp.md` if present.
2. Select the work list:
   `python3 tools/db.py select people --where "email_status='done' AND sequence_status='pending' AND status!='disqualified'" --cols id,first_name,title,company_id --limit 20`
   Fetch the matching companies:
   `python3 tools/db.py select companies --cols id,name,pitch,language`
3. Process in batches of 5 contacts. Mark each `sequence_status='running'`
   before writing. For each contact, write 3 emails:
   - Step 1 (send_day 0): icebreaker anchored in THEIR reality — use the
     company pitch; connect their world to ONE outcome from the offer. One
     clear, low-friction ask. Max 120 words.
   - Step 2 (send_day 3): follow-up with a proof point (number, client story
     from offer.md). New angle, not a "just bumping this" email. Max 120 words.
   - Step 3 (send_day 7): breakup — short, human, leaves the door open.
     Max 60 words.
   Language: the company's `language` value; fall back to the offer's language.
   Persona: pick the best-matching persona file from the contact's title and
   follow its angle and style. No placeholder brackets may remain.
4. Store each email immediately:
   `python3 tools/db.py insert messages --set person_id=<id> --set step=1 --set send_day=0 --set subject=<s> --set body=<b>`
   (status defaults to `draft`). If the insert fails on UNIQUE(person_id, step),
   the sequence already exists — skip, count as duplicate.
   Then `python3 tools/db.py write people <id> --set sequence_status=done`.
5. Receipt: "Sequences written for X contacts (3 drafts each), Y skipped as
   duplicates. Nothing is sent — review with:
   `python3 tools/db.py show messages --where \"status='draft'\"`"
   Show ONE full example sequence in the conversation so the user can judge
   tone, then stop.

## Guardrails

- Drafts only — never send, never mark approved (humans do that).
- One example sequence max in the conversation; the rest lives in the table.
- No invented facts, clients, or numbers: if it is not in context/ or in an
  enriched column, it does not exist.
