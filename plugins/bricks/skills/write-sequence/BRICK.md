# Brick contract: write-sequence

| Field | Value |
|---|---|
| family | write |
| target | contacts → messages |
| method | agent (copywriting from context + enriched columns) via `db-writer` |
| cost | free (subscription tokens only) |

## IN

- `contacts`: `email_status='done'` AND `sequence_status` pending AND
  `status != 'disqualified'`; their `role`, `full_name`.
- Parent `companies` rows: `pitch`, `language`, any signal columns.
- `context/offer.md` — REQUIRED (hard gate: refuses on TODO).
- `context/personas/*.md` — persona picked from the contact's role.

## OUT

- `messages`: 3 rows per contact — `contact_id`, `step` 1|2|3, `send_day`
  0|3|7, `subject`, `body`, `status='draft'`,
  `msg_key='<contact_id>-<step>'` (dedup key → idempotent re-runs).
- `contacts.sequence_status` → `done` | `failed`.

## Errors

- `offer.md` missing/TODO → stop, offer the 3 context questions.
- Company pitch missing → write from role + offer only, note it in receipt.

## Guardrails

- Drafts only, forever: this skill never sends, never sets `approved` —
  approval is a human act (CONVENTIONS §5).
- ≤ 120 words (steps 1-2), ≤ 60 words (step 3); no leftover placeholders;
  no invented facts, clients or numbers.
- One example sequence in the chat, the rest in the table. Batches of 5.
