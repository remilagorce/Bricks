# Brick contract: write-outreach (renamed from write-sequence, 0.9.0)

| Field | Value |
|---|---|
| family | write |
| target | contacts → messages (multi-channel) |
| method | executes context/strategy.md per contact's `channel_plan`; CPPC copywriting from offer + persona (recipient) + voice.md (sender) + fresh signals; via db.py |
| cost | free (subscription tokens only) |

## IN

- `contacts`: `channel_plan` set AND `sequence_status` pending AND
  `status != 'disqualified'` AND no `left_company`; lane prerequisites:
  email lane defaults to `email_status='done'` (GO opt-in may draft
  earlier — sending stays gated), linkedin lanes need `linkedin_url`.
  Signature: user-provided only, never inferred.
- `context/strategy.md` — REQUIRED (hard gate: templates, cadence,
  tier treatments; absent → "run plan-outreach first").
- `context/offer.md` — REQUIRED (hard gate, unchanged).
- `context/voice.md` — soft gate (sender voice; missing → defaults
  proposed in the GO and file written).
- `context/personas/*.md` (recipient angle) + `signals`
  (`freshness='fresh'` only as news; `hiring_angle` ready-made).

## OUT

- `messages`: one row per step — `contact_id`, `channel` = `email` |
  `linkedin-invite` | `linkedin-dm`, `step`, `send_day`, `subject`
  (email only), `body`, `status='draft'`,
  `msg_key='<contact_id>-<channel>-<step>'` (dedup → idempotent).
- `contacts.sequence_status` → `done | failed`.
- Email drafts feed the future outreach-send (`channel='email'`,
  approval human); LinkedIn drafts are copy-paste material — automated
  LinkedIn sending is out by doctrine.

## Errors

- strategy.md missing → stop (route to plan-outreach).
- offer.md TODO → stop (never generic spam); a chain GO must have
  satisfied it at plan time.
- One lane's prerequisite missing on a combined plan → the other lane
  runs, receipt says why.

## Guardrails

- Drafts only, forever: never sends, never sets `approved` —
  approval is a human act (CONVENTIONS §5).
- CPPC · email < 100 words · LinkedIn = chat (DM 2-4 lines;
  **invitations always WITHOUT a note** — the invite row is an action
  item, not copy) · ONE question per message · plain subjects · no
  placeholders · no invented facts.
- Only `fresh` (≤ 60 days, date re-checked) signals presented as news;
  `context` signals are background.
- One example sequence in the chat, the rest in the table; batches of
  5; receipts are statements, never questions.
