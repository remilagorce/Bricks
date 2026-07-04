# Statuses — the shared vocabulary

FROZEN CONTRACT. Every brick reads and writes these exact values. `done` means
the same thing in all 43 future bricks, or the star topology collapses.

## Pipeline statuses (per enrichment column: `website_status`, `email_status`, `sequence_status`)

| Status | Meaning | Who sets it |
|---|---|---|
| `pending` | Work not started — this is the default at row creation | schema default |
| `running` | A brick claimed this cell and is working on it | the brick, BEFORE doing the work |
| `done` | Value written, usable by downstream bricks | the brick, immediately after each result |
| `not_found` | Work completed, nothing found (this is a result, not an error) | the brick |
| `failed` | Something broke — eligible for retry | the brick |

## Row statuses (`companies.status`, `people.status`)

| Status | Meaning |
|---|---|
| `new` | Live row, bricks may work on it |
| `disqualified` | Killed by a kill-rule — NO brick may spend anything on it ever again |

## Message statuses (`messages.status`)

| Status | Meaning |
|---|---|
| `draft` | Written by a brick. Nothing with this status ever leaves the machine |
| `approved` | A human validated it |
| `sent` | Actually sent (v0: never — there is no send brick yet) |

## The three iron rules

1. Mark `running` before you work, write the result and final status
   immediately after each row — never batch-write at the end.
2. Selection is always `WHERE <col>_status = 'pending'` (plus `status != 'disqualified'`).
   Re-running a brick must never reprocess `done` rows — idempotence by statuses.
3. Data flows through the database, never through the conversation.
   A brick reports counts (a receipt), not rows.
