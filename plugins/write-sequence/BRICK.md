# Brick contract: write-sequence

| Field | Value |
|---|---|
| id | `write-sequence` |
| family | write |
| target | people → messages |
| method | agent (copywriting from context + enriched columns) |
| cost | free (subscription tokens only) |
| kill-rule compatible | no |

## IN

- `people`: precondition `email_status = 'done'` AND `sequence_status = 'pending'`
  AND `status != 'disqualified'`.
- `people.first_name`, `people.title`; parent company `name`, `pitch`, `language`.
- `context/offer.md` — required (what we sell, proof points, tone).
- `context/personas/*.md` — used if present to pick the angle.

## OUT

- `messages`: 3 rows per contact — `step` 1/2/3, `send_day` 0/3/7, `subject`,
  `body`, `status='draft'`. UNIQUE(person_id, step) makes re-runs safe.
- `people.sequence_status` → `done` | `failed`.

## Error handling

- `context/offer.md` missing or still TODO → stop, ask the user to fill it
  (garbage in, garbage out — refuse to write generic spam).
- Company pitch missing → write from title + offer only, note it in receipt.

## Guardrails

- Drafts only. This brick NEVER sends anything, and no other brick may flip
  `draft` to `approved` — only a human does.
- Max 120 words per email; step 3 max 60 words. No placeholder brackets left.
- Write in the company's language column value; fall back to the offer's language.
- Batches of 5 contacts per pass to keep quality high.
